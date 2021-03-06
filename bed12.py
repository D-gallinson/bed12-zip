import pandas as pd
import numpy as np
import re
import time

class GTFFormatError(Exception):
	pass


class CustomFormatError(Exception):
	pass


#The input df must be sorted by ['name', 'exon_start']
def cluster(df, cluster_cols):
	df['blockSizes'] = df['blockSizes'].astype(np.str)
	df['blockStarts'] = df['blockStarts'].astype(np.str)
	clustered = df.groupby(cluster_cols, sort=False)
	clustered = clustered.apply(col_join).reset_index()	#OPTIMIZE! 50% of execution time is spent here!
	
	return clustered



def col_join(df):
	result = pd.Series({
		'blockSizes': ','.join(df['blockSizes']),
		'blockStarts': ','.join(df['blockStarts'])
	})

	return result


def exon_sizes(start, end):
	start = start.astype(np.int64)
	end = end.astype(np.int64)
	sizes = (end - start) + 1
	return sizes


def exon_starts(t_start, start):
	trans_start = t_start.astype(np.int64)
	exon_start = start.astype(np.int64)
	starts = exon_start - trans_start
	return starts


#df must by sorted by name due to np.repeat
def exon_count(name_col):
	exon_count = name_col.groupby(name_col, sort=False).count().values
	exon_count = np.repeat(exon_count, exon_count)
	return exon_count



def get_transcript_starts_and_ends(name_col, start_col, end_col):
	df = pd.DataFrame({'name': name_col, 'start': start_col, 'end': end_col})
	groups = df.groupby('name', sort=False)
	counts = groups.count()['start'].values
	t_starts = groups.min()['start'].values
	t_ends = groups.max()['end'].values

	t_starts = np.repeat(t_starts, counts)
	t_ends = np.repeat(t_ends, counts)

	return t_starts, t_ends



def add_strand(rows, strand="."):
	return pd.Series(np.repeat(strand, rows), name="strand")


#Would be most efficient, I assume, to use this after clustering
#It is advisable that the input df has sequential indexes, such as what
#is generated by df.reset_index() - problems occur when concatenating
#drop_name_df to plus_name and minus_name if indexes are not reset.
def add_plus_minus(df):
	plus = add_strand(len(df), "+")
	minus = add_strand(len(df), "-")

	plus_name = df['name'] + "(+)"
	minus_name = df['name'] + "(-)"

	drop_name_df = df.drop('name', axis=1)

	plus_df = pd.concat([drop_name_df, plus_name, plus], axis=1)
	minus_df = pd.concat([drop_name_df, minus_name, minus], axis=1)

	new_df = pd.concat([plus_df, minus_df]).sort_values('name').reset_index(drop=True)
	return new_df



def clean_locus_commas(locus_col):
	return locus_col.str.replace(",", "")


def split_locus(locus_col):
	split = locus_col.str.split(r":|-", expand=True)
	split.columns = ["chrom", "exon_starts", "exon_ends"]
	return split


def parse_locus_col(locus_col):
	clean_col = clean_locus_commas(locus_col)
	locus_df = split_locus(clean_col)
	return locus_df


#Perhaps this should be in a more general "utilities.py" file?
#Basically the same function is used in "extract.py"
def split_gtf_attribute(col):
	attribute_df = col.str.split(";", expand=True)
	attribute_df.iloc[0] = attribute_df.iloc[0].str.strip()
	col_names = attribute_df.iloc[0].str.extract(r"(\w*)")[0].values

	for col in attribute_df:
		attribute_df[col] = attribute_df[col].str.extract(r"\"(.*)\"")
	
	for i in range(len(col_names)):
		name = col_names[i]
		if not name or pd.isnull(name):
			col_names[i] = "att_col_{}".format(i)
	
	attribute_df.columns = col_names
	return attribute_df


def get_attribute_col(df, col_name):
	attribute_df = split_gtf_attribute(df["attribute"])
	check_col_exists(attribute_df, col_name)
	return attribute_df[col_name]


def gen_names(rows, base='transID_'):
	id_num = np.arange(0, rows, 1).astype(np.str)
	bases = np.repeat(base, rows)
	return np.core.defchararray.add(bases, id_num)


def bed12_cols(cluster=False):
	cols = ['chrom', 'chromStart', 'chromEnd', 'name', 'score', 'strand', 'thickStart', 'thickEnd', 'rgb', 'blockCount']
	if not cluster:
		cols += ['blockSizes', 'blockStarts']
	return cols


def get_rows(df, col, search_item, indices=False):
	rows = df[col == search_item]
	if indices:
		return rows, rows.index
	return rows


def get_filetype(fname):
	start = fname.rfind(".") + 1
	return fname[start:]


def df_str(df):
	str_df = pd.DataFrame()
	for col in df:
		str_df[col] = df[col].astype(np.str)

	return str_df


def add_bed12_features(df):
	df_len = len(df)

	df['rgb'] = np.repeat('0,0,255', df_len)
	df['score'] = np.repeat(".", df_len)

	chromStart, chromEnd = get_transcript_starts_and_ends(df['name'], df['exon_starts'], df['exon_ends'])
	df.insert(1, "chromStart", chromStart)
	df.insert(2, "chromEnd", chromEnd)

	df['blockCount'] = exon_count(df['name'])
	df['blockSizes'] = exon_sizes(df['exon_starts'], df['exon_ends'])
	df['blockStarts'] = exon_starts(chromStart, df['exon_starts'])

	df['chromStart'] = df['chromStart'].astype(np.int64) - 1
	df['thickStart'], df['thickEnd'] = df['chromEnd'], df['chromStart']


def check_col_exists(df, col):
	try:
		df[col]
	except KeyError as e:
		df_cols = ", ".join(df.columns.values)
		raise KeyError([df_cols, col])


def check_gtf(path):
	df = pd.read_csv(path, delimiter="\t", header=None, nrows=1)
	col_length = len(df.columns)

	if col_length != 9:
		error_msg = "GTF files must have 9 columns"
		raise GTFFormatError(error_msg)


def check_custom(df):
	columns = df.columns.tolist()
	loc_info = ['chrom', 'exon_starts', 'exon_ends']
	locus_present = 'locus' in columns
	loc_info_present = all([True if val in columns else False for val in loc_info])

	if not locus_present and not loc_info_present:
		raise CustomFormatError('A custom input file must contain either a "locus" column or "chrom", "exon_starts", and "exon_ends" columns')


#Perhaps all constants (eg rgb, thickStart, thickEnd, etc) should be added after clustering - benchmark both methods
def gtf2bed12(path, name_col):
	check_gtf(path)
	col_names = ["chrom", "exon_starts", "exon_ends", "score", "strand", "attribute"]
	df = pd.read_csv(path, delimiter="\t", header=None, usecols=[0,3,4,5,6,8])
	df.columns = col_names
	
	name_col = get_attribute_col(df, name_col)
	df.drop('attribute', axis=1, inplace=True)
	df.insert(3, 'name', name_col)
	df.sort_values(by=['name', 'exon_starts'], inplace=True)

	add_bed12_features(df)
	bed12 = cluster(df, bed12_cols(True))
	
	return bed12


def custom2bed12(path, delim, plus_minus_flag):
	filetype = get_filetype(path)
	if filetype == "xlsx":
		df = pd.read_excel(path)
	else:
		df = pd.read_csv(path, delimiter=delim)

	check_custom(df)
	df.columns = df.columns.str.lower()
	file_cols = list(df.columns.values)
	df_len = len(df)
	cols_to_cluster = bed12_cols(True)

	if 'name' not in file_cols:
		df['name'] = gen_names(df_len)
	if 'strand' not in file_cols and not plus_minus_flag:
		df['strand'] = add_strand(df_len)
	elif 'strand' not in file_cols:
		cols_to_cluster.remove('strand')

	if 'locus' in file_cols:
		locus_df = parse_locus_col(df['locus'])
		df.drop('locus', axis=1, inplace=True)
		df = pd.concat([df, locus_df], axis=1)

	df.sort_values(by=['name', 'exon_starts'], inplace=True)

	add_bed12_features(df)
	bed12 = cluster(df, cols_to_cluster)
	bed12 = df_str(bed12)

	if plus_minus_flag:
		if 'strand' in file_cols:
			unstranded, to_drop = get_rows(bed12, bed12['strand'], ".", True)
			unstranded = unstranded.drop('strand', axis=1).reset_index(drop=True)
			bed12 = bed12.drop(to_drop)
			plus_minus = add_plus_minus(unstranded)
			bed12 = pd.concat([bed12, plus_minus], sort=True).reset_index(drop=True)
		else:
			bed12 = add_plus_minus(bed12)

	bed12 = bed12[bed12_cols()]
	return bed12


def reset_cols(df):
	length = len(df.columns.values)
	new_cols = [i for i in range(length)]
	df.columns = new_cols



def bed12_main(path, name_col=None, delim=",", pm_flag=True, outpath="bed12_out.bed", sort=False):
	print("Converting input file to BED12 format...")
	ftype = get_filetype(path)

	if ftype == 'gtf':
		try:
			bed12 = gtf2bed12(path, name_col)
		except GTFFormatError as e:
			print("Error with GTF format:\n{}".format(e))
			return False
		except KeyError as e:
			args = e.args[0]
			df_cols = args[0]
			col = args[1]
			print("Error extracting \"name\" column in GTF attribute (did you forget to specify a name column?)")
			print(f"GTF column names: [{df_cols}]")
			print(f"Column trying to be extracted (specify this with the \"-n\" argumant): [{col}]")
			return False

	elif ftype in ['csv', 'xlsx']:
		try:
			bed12 = custom2bed12(path, delim, pm_flag)
		except CustomFormatError as e:
			print("Error with custom input file format:\n{}".format(e))
			return False

	else:
		print("Please use a proper input type!")
		return False

	if sort:
		bed12 = bed12.sort_values(by=['name']).reset_index(drop=True)

	print("Done!")
	bed12.to_csv(outpath, header=None, index=False, sep="\t")
	print("BED12 written to: {}".format(outpath))
