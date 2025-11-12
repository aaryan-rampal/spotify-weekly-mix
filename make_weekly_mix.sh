#!/bin/zsh
source /opt/homebrew/Caskroom/miniconda/base/etc/profile.d/conda.sh
conda activate spotify
cd /Users/aaryanrampal/personal/programs/spotify
python make-weekly-mix-saved-artists.py
