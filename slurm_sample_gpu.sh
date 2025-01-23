#!/bin/bash

#SBATCH --job-name=MLDE_Josh_sample        # create a short name for your job
#SBATCH --gres=gpu:1                       # Number of GPUs
#SBATCH --partition=orchid                 # Use GPU
#SBATCH --account=orchid                   # Use GPU
#SBATCH --mem=64G                         # Amount of memory (MB)
#SBATCH --time=04:00:00                    # Max. amount of time for job
#SBATCH --output=Outputs/output_%j.out        # Output file
#SBATCH --error=Outputs/error_message_%j.err  # Where to save error message
#SBATCH --mail-type=end                       # send email when job ends
#SBATCH --mail-user=ev24133@bristol.ac.uk

###########################################################################
###########################################################################
#                             - Print info - 
echo "____________________________________________________________________"
cd "${SLURM_SUBMIT_DIR}"
echo " >> Running on host $(hostname)"
echo " >> Time is $(date)"
echo " >> Directory is $(pwd)"
echo " >> Slurm job ID is ${SLURM_JOBID}"
echo " >> This jobs runs on the following machines:"
echo " >> ${SLURM_JOB_NODELIST}"
echo "____________________________________________________________________"
###########################################################################
###########################################################################
#                 - Load CUDA, conda and activate environment -
module load cuda/12.1

module load gcc/8.2.0

export KK_SLACK_WH_URL=https://hooks.slack.com

source $HOME/initMamba.sh

mamba activate mlde_Josh # EarthTorch?????
##########################################################################
##########################################################################
#                      - Put python script here -
#time python3 bin/predict.py --checkpoint epoch_10 --dataset bham_gcmx-4x_12em_psl-sphum4th-temp4th-vort4th_eqvt_random-season --split test  --ensemble-member 01 --input-transform-dataset bham_gcmx-4x_12em_psl-sphum4th-temp4th-vort4th_eqvt_random-season --input-transform-key stan --num-samples 1 /gws/nopw/j04/bris_climdyn/j_miller/temp --batch-size 32

time python3 $HOME/mlde_Josh/bin/predict.py --checkpoint epoch_30 --dataset ERA5_IMERG_2002-2004 --split test  --ensemble-member 01 --input-transform-dataset ERA5_IMERG_2002-2004 --input-transform-key stan --num-samples 1 /gws/nopw/j04/bris_climdyn/j_miller/temp --batch-size 32

##########################################################################
##########################################################################
#                      - Print elapsed time -
echo "____________________________________________________________________"
echo " >> Ended on: $(date)"
echo "____________________________________________________________________"