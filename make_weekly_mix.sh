#!/bin/zsh
source /opt/homebrew/Caskroom/miniconda/base/etc/profile.d/conda.sh
conda activate spotify
cd /Users/aaryanrampal/personal/programs/spotify

# Kill any existing processes using port 5173 (from previous failed runs)
if lsof -i :5173 >/dev/null 2>&1; then
    echo "Cleaning up stuck process on port 5173..."
    lsof -i :5173 | grep -v COMMAND | awk '{print $2}' | xargs kill -9 2>/dev/null
    sleep 1
fi

python make-weekly-mix-saved-artists.py
