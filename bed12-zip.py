import argparse as ag
import bed12

parser = ag.ArgumentParser(description="Convert a GTF file or a custom file to BED12 format.")
parser.add_argument("-i", "--input", dest="input_file", required=True, help="Name of the input file")
parser.add_argument("-o", "--output", dest="output_file", default="bed12_out.bed", help="[OPTIONAL] Name of the output file (default=\"bed12_out.bed\")")
parser.add_argument("-n", "--name_col", dest="name_col", default="name", help="[OPTIONAL] Column containing the gene names/ids to be clustered")
parser.add_argument("-d", "--delim", dest="delim", default=",", help="[OPTIONAL] Delimiter for CSV files (default=\",\")")
parser.add_argument("-pm", "--plus-minus", action="store_true", dest="plus_minus", help="[OPTIONAL] Flag to indicate the bed12 file should include both the + strand and the - strand for entry lacking strand information")
parser.add_argument("-s", "--sort", action="store_true", dest="sort_flag", help="[OPTIONAL] Flag to sort the file by name")
args = parser.parse_args()

bed12.bed12_main(args.input_file, outpath=args.output_file, name_col=args.name_col, delim=args.delim, pm_flag=args.plus_minus, sort=args.sort_flag)