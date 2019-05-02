# adapted from https://github.com/GooglingTheCancerGenome/breakpoint-pairs/blob/master/PlotWindows.py

import numpy as np
import os
import gzip
import matplotlib.pyplot as plt
import errno

HPC_MODE = True

sample_name = 'NA12878'
label_type = 'Mills2011'

# date = '260319'
date = '050419'

if HPC_MODE:

    datapath_prefix = '/hpc/cog_bioinf/ridder/users/lsantuari'
    channel_dir = datapath_prefix + '/Processed/Test/' + \
                  date + '/TestData_' + date + '/' + sample_name + '/TrainingData/'
else:
    channel_dir = '/Users/lsantuari/Documents/Processed/Test/test_060219'


def create_dir(directory):
    '''
    Create a directory if it does not exist. Raises an exception if the directory exists.
    :param directory: directory to create
    :return: None
    '''
    try:
        os.makedirs(directory)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

def get_channel_labels():
    # Fill labels for legend

    labels = list()
    labels.append("coverage")
    labels.append("mean_read_quality")

    labels.append("#left_clipped_reads")
    labels.append("#left_clipped_reads_freq")

    labels.append("#right_clipped_reads")
    labels.append("#right_clipped_reads_freq")

    labels.append("#CIGAR_D_left_reads")
    labels.append("#CIGAR_D_left_reads_freq")

    labels.append("#CIGAR_D_right_reads")
    labels.append("#CIGAR_D_right_reads_freq")

    labels.append("#CIGAR_I_right_reads")
    labels.append("#CIGAR_I_right_reads_freq")

    labels.append("INV_before")
    labels.append("INV_before_freq")

    labels.append("INV_after")
    labels.append("INV_after_freq")

    labels.append("DUP_before")
    labels.append("DUP_before_freq")

    labels.append("DUP_after")
    labels.append("DUP_after_freq")

    labels.append("TRA_opposite")
    labels.append("TRA_opposite_freq")

    labels.append("TRA_same")
    labels.append("TRA_same_freq")

    for direction in ['Forward', 'Reverse']:
        for clipped in ['Left', 'Right', 'All']:
            for value in ['median']:
                labels.append(direction + '_' + clipped + '_Clipped_' + value)

    labels.append("#left split reads")
    labels.append("#left split reads freq")
    labels.append("#right split reads")
    labels.append("#right split reads freq")

    for clipped in ['L', 'R']:
        for value in ['median']:
            labels.append(clipped + '_SplitRead_' + value)

    labels.append("Mappability")

    for nuc in ['A', 'T', 'C', 'G', 'N']:
        labels.append("One_hot_encoding_" + nuc)

    # for k, l in enumerate(labels):
    #     print(str(k) + ':' + l)

    return labels


def data(sample_name, label_type, suffix):

    data_output_file = os.path.join(channel_dir, '_'.join([sample_name, label_type, suffix]))

    with gzip.GzipFile(data_output_file + '.npz.gz', 'rb') as f:

        npzfiles = np.load(f)
        X = npzfiles['X']
        y = npzfiles['y']
        y_binary = npzfiles['y_binary']
        z = npzfiles['z']

    return X, y, y_binary, z


def load_bedpe():

    input_file = '/Users/lsantuari/Documents/Processed/NA12878/'+\
                 'IGV_snaps/SR_models/CV_results_wrong_predictions_10.bedpe'

    content = []
    with open(input_file)as f:
        for line in f:
            l = line.strip().split()
            l = ('_'.join([l[0], l[1], l[4]]), l[6])
            content.append(l)
    #print(content)
    return content


def plot_channels(X, z, l):

    number_channels = X.shape[1]

    label = get_channel_labels()

    plt.title(z+' '+l)

    fig = plt.figure(figsize=(6, 4))
    for i in range(7, 8):
        for j in range(number_channels-1, -1, -1):
            shift = 0
            start = 0
            if sum(X[i][j]) != 0:
                X_win = (X[i][j]-min(X[i][j]))/max(X[i][j])

            else:
                X_win = X[i][j]

            Z = [x + j+1 for x in X_win]
            plt.plot(Z, label=label[j], linewidth=0.9)
            plt.legend(bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=0., prop={'size': 5})
            plt.yticks(range(0, len(label)+1, 1))
            plt.tick_params(axis='both', which='major', labelsize=5)
            plt.axvline(x=200, color='r', linewidth=0.05, alpha=0.5)
            plt.axvline(x=209, color='r', linewidth=0.05, alpha=0.5)

        plt.savefig('plots/Channels_'+z+' '+l+'.png', format='png', dpi=300, bbox_inches='tight')
        plt.show()
    plt.close()


def main():

    create_dir('plots')

    bedpe_lines = load_bedpe()
    X, y, y_binary, z = data('NA12878', 'Mills2011', 'pairs')

    for b in bedpe_lines:

        pos, lab = b
        idx, = np.where(z == pos)
        plot_channels(X[idx,:,:], z[idx], l)


if __name__ == '__main__':
    main()