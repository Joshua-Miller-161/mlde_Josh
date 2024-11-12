#!/bin/bash

#SBATCH --job-name=MLDE_Josh_test          # create a short name for your job
#SBATCH --gres=gpu:1                       # Number of GPUs
#SBATCH --partition=orchid                 # Use GPU
#SBATCH --account=orchid                   # Use GPU
#SBATCH --mem=128G                         # Amount of memory (MB)
#SBATCH --time=00:10:00                    # Max. amount of time for job
#SBATCH --output=Outputs/output_%j.out        # Output file
#SBATCH --error=Outputs/error_message_%j.err  # Where to save error message
#SBATCH --mail-type=end                    # send email when job ends
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

mamba activate mlde # EarthTorch?????
##########################################################################
##########################################################################
#                      - Put python script here -
time python3 bin/main.py --config src/ml_downscaling_emulator/configs/subvpsde/ukcp_local_pr_12em_cncsnpp_continuous.py --workdir /work/scratch-nopw2/j_miller/temp --mode train --config.data.dataset_name bham_gcmx-4x_12em_psl-sphum4th-temp4th-vort4th_eqvt_random-season
##########################################################################
##########################################################################
#                      - Print elapsed time -
echo "____________________________________________________________________"
echo " >> Ended on: $(date)"
echo "____________________________________________________________________"