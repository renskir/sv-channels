import argparse
import pysam
import bz2
import cPickle as pickle
from time import time
import twobitreader as twobit
from collections import Counter

# Return if a read is clipped on the left
def is_left_clipped(read):
    if read.cigartuples is not None:
        if read.cigartuples[0][0] in [4, 5]:
            return True
    return False

# Return if a read is clipped on the right
def is_right_clipped(read):
    if read.cigartuples is not None:
        if read.cigartuples[-1][0] in [4, 5]:
            return True
    return False

# Return if a read is clipped on the right or on the left
def is_clipped(read):
    if read.cigartuples is not None:
        if is_left_clipped(read) or is_right_clipped(read):
            return True
    return False

# Return the mate of a read. Get read mate from BAM file
def get_read_mate(read, bamfile):

    #print(read)
    #print('Mate is mapped')
    iter = bamfile.fetch(read.next_reference_name,
                         read.next_reference_start, read.next_reference_start + 1,
                         multiple_iterators=True)
    for mate in iter:
        if mate.query_name == read.query_name:
            if ( read.is_read1 and mate.is_read2 ) or ( read.is_read2 and mate.is_read1 ):
                #print('Mate is: ' + str(mate))
                return mate
    return None

def get_clipped_read_distance(ibam, chrName, outFile):

    clipped_read_distance = dict()
    for direction in ['forward', 'reverse']:
        clipped_read_distance[direction] = dict()
    for direction in ['forward', 'reverse']:
        for clipped_arrangement in ['c2c', 'nc2c', 'c2nc', 'nc2nc']:
            clipped_read_distance[direction][clipped_arrangement] = dict()

    def get_distance(direction, read, mate):

        if is_clipped(read) and is_clipped(mate):
            if is_left_clipped(read):
                pos = read.get_reference_positions()[0]
                if pos not in clipped_read_distance[direction]['c2c'].keys():
                    clipped_read_distance[direction]['c2c'][pos] = [d]
                else:
                    clipped_read_distance[direction]['c2c'][pos].append(d)
            elif is_right_clipped(read):
                pos = read.get_reference_positions()[-1]
                if pos not in clipped_read_distance[direction]['c2c'].keys():
                    clipped_read_distance[direction]['c2c'][pos] = [d]
                else:
                    clipped_read_distance[direction]['c2c'][pos].append(d)

        elif is_clipped(read) and not is_clipped(mate):
            if is_left_clipped(read):
                pos = read.get_reference_positions()[0]
                if pos not in clipped_read_distance[direction]['c2nc'].keys():
                    clipped_read_distance[direction]['c2nc'][pos] = [d]
                else:
                    clipped_read_distance[direction]['c2nc'][pos].append(d)
            elif is_right_clipped(read):
                pos = read.get_reference_positions()[-1]
                if pos not in clipped_read_distance[direction]['c2nc'].keys():
                    clipped_read_distance[direction]['c2nc'][pos] = [d]
                else:
                    clipped_read_distance[direction]['c2nc'][pos].append(d)
        elif not is_clipped(read) and is_clipped(mate):
            if read.reference_start not in clipped_read_distance[direction]['nc2c'].keys():
                clipped_read_distance[direction]['nc2c'][read.reference_start] = [d]
            else:
                clipped_read_distance[direction]['nc2c'][read.reference_start].append(d)
        elif not is_clipped(read) and not is_clipped(mate):
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
    #print(chrLen)

    iter = bamfile.fetch(chrName, start_pos, stop_pos, multiple_iterators=True)

    for read in iter:
        if not read.is_unmapped and not read.mate_is_unmapped:
            #mate = get_read_mate(read, bamfile)
            mate = read
            if read.reference_name == mate.reference_name:
                d = abs(read.reference_start - mate.reference_start)

                if not read.is_reverse and mate.is_reverse and read.reference_start <= mate.reference_start:
                    #pass
                    get_distance('forward', read, mate)
                elif read.is_reverse and not mate.is_reverse and read.reference_start >= mate.reference_start:
                    #pass
                    get_distance('reverse', read, mate)

    #print(clipped_read_distance)
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
    parser.add_argument('-o', '--out', type=str, default='clipped_reads.pbz2',
                        help="Specify output")

    args = parser.parse_args()

    t0 = time()
    get_clipped_read_distance(ibam=args.bam, chrName=args.chr, outFile=args.out)
    print(time()-t0)

if __name__ == '__main__':
    main()