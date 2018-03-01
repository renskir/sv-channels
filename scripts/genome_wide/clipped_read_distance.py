import argparse
import pysam
import bz2
import cPickle as pickle
from time import time
import functions as fun
import twobitreader as twobit
from collections import Counter


def get_clipped_read_distance(ibam, chrName, outFile):

    # Load clipped reads sets
    clipped_pos_file = './T/' + chrName + '_clipped_read_pos.pbz2'
    with bz2.BZ2File(clipped_pos_file, 'rb') as f:
        clipped_pos_cnt, clipped_read_1, clipped_read_2 = pickle.load(f)

    clipped_read_distance = dict()
    for direction in ['forward', 'reverse']:
        clipped_read_distance[direction] = dict()
    for direction in ['forward', 'reverse']:
        for clipped_arrangement in ['c2c', 'nc2c', 'c2nc', 'nc2nc']:
            clipped_read_distance[direction][clipped_arrangement] = dict()

    def get_distance(direction, read):

        mate_is_clipped = read.is_read1 and read.query_name in clipped_read_2 or \
                          read.is_read2 and read.query_name in clipped_read_1

        if fun.is_clipped(read) and mate_is_clipped:
            if fun.is_left_clipped(read):
                pos = read.get_reference_positions()[0]
                if pos not in clipped_read_distance[direction]['c2c'].keys():
                    clipped_read_distance[direction]['c2c'][pos] = [d]
                else:
                    clipped_read_distance[direction]['c2c'][pos].append(d)
            elif fun.is_right_clipped(read):
                pos = read.get_reference_positions()[-1]
                if pos not in clipped_read_distance[direction]['c2c'].keys():
                    clipped_read_distance[direction]['c2c'][pos] = [d]
                else:
                    clipped_read_distance[direction]['c2c'][pos].append(d)

        elif fun.is_clipped(read) and not mate_is_clipped:
            if fun.is_left_clipped(read):
                pos = read.get_reference_positions()[0]
                if pos not in clipped_read_distance[direction]['c2nc'].keys():
                    clipped_read_distance[direction]['c2nc'][pos] = [d]
                else:
                    clipped_read_distance[direction]['c2nc'][pos].append(d)
            elif fun.is_right_clipped(read):
                pos = read.get_reference_positions()[-1]
                if pos not in clipped_read_distance[direction]['c2nc'].keys():
                    clipped_read_distance[direction]['c2nc'][pos] = [d]
                else:
                    clipped_read_distance[direction]['c2nc'][pos].append(d)
        elif not fun.is_clipped(read) and mate_is_clipped:
            if read.reference_start not in clipped_read_distance[direction]['nc2c'].keys():
                clipped_read_distance[direction]['nc2c'][read.reference_start] = [d]
            else:
                clipped_read_distance[direction]['nc2c'][read.reference_start].append(d)
        elif not fun.is_clipped(read) and not mate_is_clipped:
            if read.reference_start not in clipped_read_distance[direction]['nc2nc'].keys():
                if read.reference_start not in clipped_read_distance[direction]['nc2nc'].keys():
                    clipped_read_distance[direction]['nc2nc'][read.reference_start] = [d]
                else:
                    clipped_read_distance[direction]['nc2nc'][read.reference_start].append(d)

    bamfile = pysam.AlignmentFile(ibam, "rb")
    header_dict = bamfile.header

    chrLen = [i['LN'] for i in header_dict['SQ'] if i['SN'] == chrName][0]

    start_pos = 0
    stop_pos = chrLen
    # print(chrLen)

    iter = bamfile.fetch(chrName, start_pos, stop_pos, multiple_iterators=True)

    for read in iter:
        if not read.is_unmapped and not read.mate_is_unmapped:
            # mate = fun.get_read_mate(read, bamfile)
            if read.reference_name == read.next_reference_name:
                d = abs(read.reference_start - read.next_reference_start)

                if not read.is_reverse and read.mate_is_reverse and read.reference_start <= read.next_reference_start:
                    # pass
                    get_distance('forward', read)
                elif read.is_reverse and not read.mate_is_reverse and read.reference_start >= read.next_reference_start:
                    # pass
                    get_distance('reverse', read)

    # print(clipped_read_distance)
    # cPickle data persistence
    with bz2.BZ2File(outFile, 'w') as f:
        pickle.dump(clipped_read_distance, f)


def main():
    wd = "/Users/lsantuari/Documents/Data/HPC/DeepSV/Artificial_data/SURVIVOR-master/Debug/"
    inputBAM = wd + "reads_chr17_SURV10kDEL_INS_Germline2_Somatic1_mapped/GS/mapping/" + "GS_dedup.subsampledto30x.bam"

    parser = argparse.ArgumentParser(description='Create channels with distance between clipped/non-clipped reads')
    parser.add_argument('-b', '--bam', type=str,
                        default=inputBAM,
                        help="Specify input file (BAM)")
    parser.add_argument('-c', '--chr', type=str, default='17',
                        help="Specify chromosome")
    parser.add_argument('-o', '--out', type=str, default='clipped_read_distance.pbz2',
                        help="Specify output")

    args = parser.parse_args()

    t0 = time()
    get_clipped_read_distance(ibam=args.bam, chrName=args.chr, outFile=args.out)
    print(time() - t0)


if __name__ == '__main__':
    main()
