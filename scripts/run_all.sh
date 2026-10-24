#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "=== Starting playlist generation ==="
date
echo ""

echo "Running weekly mix..."
if uv run python src/make_weekly_mix.py; then
    echo "✓ Weekly mix completed successfully"
else
    echo "✗ Weekly mix failed with exit code $?"
fi
echo ""

echo "Running 1-month and 3-month rolling window..."
if uv run python src/make_rolling.py; then
    echo "✓ Rolling playlists completed successfully"
else
    echo "✗ Rolling playlists failed with exit code $?"
fi
echo ""

echo "Running Weekly Mix Leftovers..."
if uv run python src/make_weekly_mix_leftovers.py; then
    echo "✓ Weekly Mix Leftovers completed successfully"
else
    echo "✗ Weekly Mix Leftovers failed with exit code $?"
fi
echo ""

echo "=== Playlist generation complete ==="
date
