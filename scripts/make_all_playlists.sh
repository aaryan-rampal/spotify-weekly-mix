#!/bin/zsh
source /Users/aaryanrampal/env/spotify/bin/activate
cd /Users/aaryanrampal/personal/programs/spotify

# Kill any existing processes using port 5173 (from previous failed runs)
if lsof -i :5173 >/dev/null 2>&1; then
    echo "Cleaning up stuck process on port 5173..."
    lsof -i :5173 | grep -v COMMAND | awk '{print $2}' | xargs kill -9 2>/dev/null
    sleep 1
fi

echo "=== Starting playlist generation ==="
date
echo ""

echo "Running weekly mix..."
python src/make_weekly_mix.py
WEEKLY_EXIT_CODE=$?
if [ $WEEKLY_EXIT_CODE -eq 0 ]; then
    echo "✓ Weekly mix completed successfully"
else
    echo "✗ Weekly mix failed with exit code $WEEKLY_EXIT_CODE"
fi
echo ""

echo "Running 1-month and 3 month rolling window..."
python src/make_rolling.py
ROLLING_EXIT_CODE=$?
if [ $ROLLING_EXIT_CODE -eq 0 ]; then
    echo "✓ 1-month rolling completed successfully"
else
    echo "✗ 1-month rolling failed with exit code $ROLLING_EXIT_CODE"
fi
echo ""

echo "=== Playlist generation complete ==="
date
