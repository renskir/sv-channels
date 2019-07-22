# Imports
import argparse
import re
import pysam
from pysam import VariantFile
from collections import Counter
from intervaltree import IntervalTree

from collections import defaultdict
import numpy as np
import gzip
import os, errno
from time import time
import json
import logging
from functions import *
import label_classes

with open('parameters.json', 'r') as f:
    config = json.load(f)

HPC_MODE = config["DEFAULT"]["HPC_MODE"]


def read_bedpe(inbedpe):
    # Check file existence
    assert os.path.isfile(inbedpe), inbedpe + ' not found!'
    # Dictionary with chromosome keys to store SVs
    sv_list = []

    with(open(inbedpe, 'r')) as bed:
        for line in bed:
            columns = line.rstrip().split("\t")
            chrom1, pos1_start, pos1_end = str(columns[0]), int(columns[1]), int(columns[2])
            chrom2, pos2_start, pos2_end = str(columns[3]), int(columns[4]), int(columns[5])
            svtype = columns[10]

            if svtype == "DEL":
                sv_list.append((
                    chrom1, pos1_start, pos1_end,
                    chrom2, pos2_start, pos2_end,
                    svtype
                ))

    logging.info('{} SVs'.format(len(sv_list)))

    return sv_list


def overlap(sv_list, cpos_list, win_hlen):
    '''

    :param sv_list: list, list of SVs
    :param cr_pos: list, list of clipped read positions
    :return: list, list of clipped read positions whose window completely overlap either the CIPOS interval
    or the CIEND interval
    '''

    def make_gtrees_from_svlist(sv_list):

        logging.info('Building SV GenomicTrees...')
        # Tree with windows for candidate positions
        trees_start = defaultdict(IntervalTree)
        trees_end = defaultdict(IntervalTree)

        # Populate tree
        for sv in sv_list:
            chrom1, pos1_start, pos1_end, chrom2, pos2_start, pos2_end, svtype = sv
            sv_id = '_'.join((svtype, chrom1, str(pos1_start), chrom2, str(pos2_start)))

            trees_start[chrom1][pos1_start:pos1_end] = (svtype, sv_id)
            trees_end[chrom2][pos2_start:pos2_end] = (svtype, sv_id)

        # print('Tree start')
        # for k in trees_start.keys():
        #     print('{} : {}'.format( k, len(trees_start[k])))
        # print('Tree end')
        # for k in trees_end.keys():
        #     print('{} : {}'.format( k, len(trees_end[k])))

        return trees_start, trees_end

    def search_tree_with_cpos(cpos, trees_start, trees_end):

        logging.info('Searching SV GenomicTrees with candidate positions...')

        lookup_start = []
        lookup_end = []

        # Log info every n_r times
        n_r = 10 ** 6
        last_t = time()

        for i, p in enumerate(cpos, start=1):

            if not i % n_r:
                now_t = time()
                # print(type(now_t))
                logging.info("%d candidate positions processed (%f positions / s)" % (
                    i,
                    n_r / (now_t - last_t)))
                last_t = time()

            chrom1, pos1, chrom2, pos2 = p
            lookup_start.append(trees_start[chrom1][pos1 - win_hlen:pos1 + win_hlen + 1])
            lookup_end.append(trees_end[chrom2][pos2 - win_hlen:pos2 + win_hlen + 1])

        return lookup_start, lookup_end

    trees_start, trees_end = make_gtrees_from_svlist(sv_list)
    lookup_start, lookup_end = search_tree_with_cpos(cpos_list, trees_start, trees_end)

    # print([l for l in lookup_start if len(l) > 0])
    # print([l for l in lookup_end if len(l) > 0])

    labels = dict()

    sv_covered = set()

    for p, lu_start, lu_end in zip(cpos_list, lookup_start, lookup_end):

        chrom1, pos1, chrom2, pos2 = p
        pos_id = '_'.join((chrom1, str(pos1), chrom2, str(pos2)))

        l1 = len(lu_start)
        l2 = len(lu_end)

        if l1 == 1 and l1 == l2:

            # print(lu_start)
            # print(lu_end)
            lu_start_elem_start, lu_start_elem_end, lu_start_elem_data = lu_start.pop()
            lu_end_elem_start, lu_end_elem_end, lu_end_elem_data = lu_end.pop()

            lu_start_elem_svtype, lu_start_elem_svid = lu_start_elem_data
            lu_end_elem_svtype, lu_end_elem_svid = lu_end_elem_data

            if pos1 - win_hlen <= lu_start_elem_start and lu_start_elem_end <= pos1 + win_hlen and \
                    pos2 - win_hlen <= lu_end_elem_start and lu_end_elem_end <= pos2 + win_hlen and \
                    lu_start_elem_svid == lu_end_elem_svid:
                # logging.info(
                #     'Chr1:{}\tpos1:{}-{}\tChr2:{}\tpos2:{}-{}'.format(
                #         chrom1, pos1 - win_hlen, pos1 + win_hlen, chrom2, pos2 - win_hlen, pos2 + win_hlen
                #     )
                # )
                # logging.info(
                #     'LookUp_start:{}-{}_{}\tLookUp_end:{}-{}_{}'.format(
                #         lu_start_elem_start, lu_start_elem_end, lu_start_elem_data,
                #         lu_end_elem_start, lu_end_elem_end, lu_end_elem_data
                #     )
                # )
                sv_covered.add(lu_start_elem_svid)
                labels[pos_id] = lu_start_elem_data

        else:
            # logging.info('CPOS->Partial: %s\t%d\t%d' % (elem, start, end))
            labels[pos_id] = 'noSV'

    logging.info(Counter(labels.values()))

    logging.info('SV coverage: {}/{}={}%'.format(len(sv_covered),
                                                 len(sv_list),
                                                 len(sv_covered)/len(sv_list)*100))

    return labels


# Get labels
def get_labels(ibam, sampleName, win_len, ground_truth, outFile, outDir):
    logging.info('running {}'.format(sampleName))

    def make_gtrees_from_truth_set(truth_set, file_ext):

        # Using IntervalTree for interval search
        trees_start = defaultdict(IntervalTree)
        trees_end = defaultdict(IntervalTree)

        if file_ext == 'VCF':

            for var in sv_list:
                # cipos[0] and ciend[0] are negative in the VCF file
                id_start = var.svtype + '_start'
                id_end = var.svtype + '_end'

                assert var.start <= var.end, "Start: " + str(var.start) + " End: " + str(var.end)

                # logging.info('var start -> %s:%d CIPOS: (%d, %d)' % (
                # var.chrom, var.start, var.cipos[0], var.cipos[1])
                # )
                # logging.info('var end -> %s:%d CIEND: (%d, %d)' % (
                # var.chrom2, var.end, var.ciend[0], var.ciend[1])
                # )

                trees_start['chr' + var.chrom][var.start + var.cipos[0]:var.start + var.cipos[1] + 1] = id_start
                trees_end['chr' + var.chrom2][var.end + var.ciend[0]:var.end + var.ciend[1] + 1] = id_end

        elif file_ext == 'BEDPE':

            for sv in sv_list:
                chrom1, pos1_start, pos1_end, chrom2, pos2_start, pos2_end, svtype = sv

                id_start = svtype + '_start'
                id_end = svtype + '_end'

                trees_start['chr' + chrom1][pos1_start:pos1_end + 1] = id_start
                trees_end['chr' + chrom2][pos2_start:pos2_end + 1] = id_end

        return trees_start, trees_end

    def get_crpos_overlap_with_sv_callsets(sv_dict, cr_pos_dict):

        logging.info('Creating crpos_overlap_with_sv_callsets')
        crpos_all_sv = dict()

        for chrName in chrom_lengths.keys():

            logging.info('Considering Chr{}'.format(chrName))

            # Build two sets: crpos_full_all_sv and crpos_partial_all_sv with clipped read positions that
            # fully/partially overlap at least one SV callset of the caller_list_all_sv
            sv_list_all_sv = dict()
            crpos_full_all_sv_per_caller = dict()
            crpos_partial_all_sv_per_caller = dict()
            caller_list_all_sv = ['manta', 'gridss', 'lumpy', 'delly', 'nanosv']

            for caller in caller_list_all_sv:
                logging.info(caller)
                sv_list_all_sv[caller] = [var for var in sv_dict[caller] if var.chrom == chrName]
                crpos_full_all_sv_per_caller[caller], crpos_partial_all_sv_per_caller[caller] = \
                    get_crpos_win_with_ci_overlap(sv_list_all_sv[caller], cr_pos_dict[chrName], win_hlen)

            crpos_full_all_sv = set()
            crpos_partial_all_sv = set()

            for caller in caller_list_all_sv:
                crpos_full_all_sv = crpos_full_all_sv.union(set(crpos_full_all_sv_per_caller[caller]))
                crpos_partial_all_sv = crpos_partial_all_sv.union(set(crpos_partial_all_sv_per_caller[caller]))

            crpos_all_sv[chrName] = crpos_full_all_sv | crpos_partial_all_sv

        logging.info('Finished crpos_overlap_with_sv_callsets')

        return crpos_all_sv

    # windows half length
    win_hlen = int(int(win_len) / 2)
    # get chromosome lengths
    chr_dict = get_chr_len_dict(ibam)

    cpos_list = load_all_clipped_read_positions(sampleName, win_hlen, chr_dict, outDir)

    sv_list = read_bedpe(ground_truth)

    # Get overlap of candidate positions with all SV breakpoints (all 4 SV callers)
    # crpos_all_sv = get_crpos_overlap_with_sv_callsets(sv_dict, cr_pos_dict)

    # filename, file_extension = os.path.splitext(ground_truth)
    # trees_start, trees_end = make_gtrees_from_truth_set(sv_list, file_extension.upper())

    labels = overlap(sv_list, cpos_list, win_hlen)

    with gzip.GzipFile(outFile, 'wb') as fout:
        fout.write(json.dumps(labels).encode('utf-8'))


def main():
    '''
    Label windows according to truth set
    :return: None
    '''

    wd = '/Users/lsantuari/Documents/Data/HPC/DeepSV/Artificial_data/run_test_INDEL/BAM/'
    inputBAM = wd + "T1_dedup.bam"

    parser = argparse.ArgumentParser(description='Create labels')
    parser.add_argument('-b', '--bam', type=str,
                        default=inputBAM,
                        help="Specify input file (BAM)")
    parser.add_argument('-l', '--logfile', type=str, default='labels_win200.log',
                        help="Specify log file")
    parser.add_argument('-s', '--sample', type=str, default='NA12878',
                        help="Specify sample")
    parser.add_argument('-w', '--window', type=str, default=200,
                        help="Specify window size")
    parser.add_argument('-gt', '--ground_truth', type=str,
                        default=os.path.join('/Users/lsantuari/Documents/Data/svclassify',
                                             'Personalis_1000_Genomes_deduplicated_deletions.bedpe'),
                        help="Specify ground truth VCF/BEDPE file")
    parser.add_argument('-o', '--out', type=str, default='labels.json.gz',
                        help="Specify output")
    parser.add_argument('-p', '--outputpath', type=str,
                        default='/Users/lsantuari/Documents/Processed/channel_maker_output',
                        help="Specify output path")

    args = parser.parse_args()

    # Log file
    cmd_name = 'labels_win' + str(args.window)
    output_dir = os.path.join(args.outputpath, args.sample, cmd_name)
    create_dir(output_dir)
    logfilename = os.path.join(output_dir, args.logfile)
    output_file = os.path.join(output_dir, args.out)

    FORMAT = '%(asctime)s %(message)s'
    logging.basicConfig(
        format=FORMAT,
        filename=logfilename,
        filemode='w',
        level=logging.INFO)

    t0 = time()

    get_labels(ibam=args.bam,
               sampleName=args.sample,
               win_len=args.window,
               ground_truth=args.ground_truth,
               outFile=output_file,
               outDir=args.outputpath,
               )

    logging.info('Elapsed time making labels = %f' % (time() - t0))


if __name__ == '__main__':
    main()
