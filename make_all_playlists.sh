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

# Weekly mix runs only on specific days (default: Monday (1))
# Change WEEKLY_DAY to 0-6 where 0=Sunday, 1=Monday, etc., or set to empty to run daily
WEEKLY_DAY=1
CURRENT_DAY=$(date +%u)

if [ -z "$WEEKLY_DAY" ] || [ "$CURRENT_DAY" -eq "$WEEKLY_DAY" ]; then
    echo "Running weekly mix..."
    python make-weekly-mix-saved-artists.py
    WEEKLY_EXIT_CODE=$?
    if [ $WEEKLY_EXIT_CODE -eq 0 ]; then
        echo "✓ Weekly mix completed successfully"
    else
        echo "✗ Weekly mix failed with exit code $WEEKLY_EXIT_CODE"
    fi
else
    echo "Skipping weekly mix (scheduled for day $WEEKLY_DAY, today is day $CURRENT_DAY)"
fi
echo ""

echo "Running 1-month and 3 month rolling window..."
python make-rolling.py
ROLLING_EXIT_CODE=$?
if [ $ROLLING_EXIT_CODE -eq 0 ]; then
    echo "✓ 1-month rolling completed successfully"
else
    echo "✗ 1-month rolling failed with exit code $ROLLING_EXIT_CODE"
fi
echo ""

echo "=== Playlist generation complete ==="
date
