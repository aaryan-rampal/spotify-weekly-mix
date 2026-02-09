# Rolling Window Playlists Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add 1-month and 3-month rolling window playlists based on liked songs, plus a master script to orchestrate all playlist generation (weekly mix + rolling windows) together.

**Architecture:**
- Two new Python scripts that fetch liked songs within time windows (30/90 days) and update existing playlists by name
- A master shell wrapper script that runs all three generators in sequence (weekly mix conditionally)
- LaunchAgent plist files for scheduling: daily for rolling windows, weekly for weekly mix

**Tech Stack:**
- Python with Spotipy for Spotify API
- Shell scripts for orchestration
- LaunchAgents for scheduling
- Time-based filtering using datetime and `added_at` timestamps from Spotify API

---

## Overview

This plan creates two new playlist generators:
1. **1-Month Rolling Window**: All tracks liked in the last 30 days (playlist name: "1 Month Rolling")
2. **3-Month Rolling Window**: All tracks liked in the last 90 days (playlist name: "3 Month Rolling")

Both scripts will:
- Fetch all saved tracks with their `added_at` timestamps
- Filter tracks by date window (30/90 days back from today)
- Find existing playlist by name and clear it, then add filtered tracks
- Create new playlist if none exists

The master script will:
- Run weekly mix only if current day matches schedule (e.g., Mondays or configurable)
- Always run 1-month and 3-month rolling windows
- Handle environment activation and cleanup

---

## Task 1: Create 1-month rolling window script

**Files:**
- Create: `make-1month-rolling.py`

**Step 1: Write the script structure with Spotify authentication and logging**

```python
# %%
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import os
import datetime
from loguru import logger

# %%
logger.remove()
logger.add(
    "1month_rolling.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
    level="DEBUG",
)
logger.add(
    lambda msg: print(msg, end=""),
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
    level="INFO",
)

load_dotenv()
client_id = os.getenv("SPOTIPY_CLIENT_ID")
client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")
redirect_uri = os.getenv("SPOTIPY_REDIRECT_URI")
scope = (
    "playlist-modify-public,playlist-modify-private,user-library-read"
)

# %%
sp = spotipy.Spotify(
    auth_manager=SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=scope,
    )
)

# %%
playlist_name = "1 Month Rolling"
cutoff_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30)

logger.info(f"Fetching saved tracks added after {cutoff_date.strftime('%Y-%m-%d')}...")
```

**Step 2: Implement track fetching with date filtering**

```python
# Fetch all saved tracks and filter by added_at date
filtered_tracks = []
results = sp.current_user_saved_tracks(limit=50)

while results:
    for item in results["items"]:
        track = item["track"]
        added_at = datetime.datetime.fromisoformat(item["added_at"].replace('Z', '+00:00'))
        
        if added_at >= cutoff_date:
            filtered_tracks.append({
                "id": track["id"],
                "name": track["name"],
                "artists": [a["name"] for a in track["artists"]],
                "added_at": added_at
            })
            logger.debug(f"Track within window: {track['name']} by {track['artists'][0]['name']} (added {added_at.strftime('%Y-%m-%d')})")
    
    if results["next"]:
        results = sp.next(results)
    else:
        break

logger.info(f"Found {len(filtered_tracks)} tracks in the last 30 days")
```

**Step 3: Implement playlist finding/clearing logic**

```python
# Find existing playlist or create new one
user_id = sp.current_user()["id"]
user_playlists = sp.user_playlists(user_id)

existing_playlist = None
while user_playlists:
    for playlist in user_playlists["items"]:
        if playlist["name"] == playlist_name:
            existing_playlist = playlist
            logger.info(f"Found existing playlist: {playlist_name}")
            break
    if user_playlists["next"]:
        user_playlists = sp.next(user_playlists)
    else:
        break

if existing_playlist:
    # Clear existing playlist
    playlist_id = existing_playlist["id"]
    track_ids = sp.playlist_items(playlist_id, limit=50)
    all_track_ids = []
    
    while track_ids:
        for item in track_ids["items"]:
            if item["track"]:
                all_track_ids.append(item["track"]["id"])
        if track_ids["next"]:
            track_ids = sp.next(track_ids)
        else:
            break
    
    if all_track_ids:
        logger.info(f"Clearing {len(all_track_ids)} tracks from existing playlist...")
        sp.playlist_remove_all_occurrences_of_items(playlist_id, all_track_ids)
    
    # Add filtered tracks
    track_ids_to_add = [t["id"] for t in filtered_tracks]
    if track_ids_to_add:
        sp.playlist_add_items(playlist_id, track_ids_to_add)
        logger.info(f"Added {len(track_ids_to_add)} tracks to playlist")
else:
    # Create new playlist
    playlist_id = sp.user_playlist_create(
        user_id,
        playlist_name,
        public=False,
        description=f"Tracks liked in the last 30 days (last updated: {datetime.datetime.now().strftime('%Y-%m-%d')})"
    )["id"]
    
    track_ids_to_add = [t["id"] for t in filtered_tracks]
    if track_ids_to_add:
        sp.playlist_add_items(playlist_id, track_ids_to_add)
        logger.info(f"Created new playlist with {len(track_ids_to_add)} tracks")

logger.info(f"1 Month Rolling playlist updated successfully!")
```

**Step 4: Test the script by running it**

Run: `source /Users/aaryanrampal/env/spotify/bin/activate && python make-1month-rolling.py`
Expected: Script runs without errors, logs track counts, creates/updates playlist

**Step 5: Commit**

```bash
git add make-1month-rolling.py 1month_rolling.log
git commit -m "feat: add 1-month rolling window playlist generator"
```

---

## Task 2: Create 3-month rolling window script

**Files:**
- Create: `make-3month-rolling.py`

**Step 1: Copy and modify 1-month script for 3-month window**

```python
# %%
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import os
import datetime
from loguru import logger

# %%
logger.remove()
logger.add(
    "3month_rolling.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
    level="DEBUG",
)
logger.add(
    lambda msg: print(msg, end=""),
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
    level="INFO",
)

load_dotenv()
client_id = os.getenv("SPOTIPY_CLIENT_ID")
client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")
redirect_uri = os.getenv("SPOTIPY_REDIRECT_URI")
scope = (
    "playlist-modify-public,playlist-modify-private,user-library-read"
)

# %%
sp = spotipy.Spotify(
    auth_manager=SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=scope,
    )
)

# %%
playlist_name = "3 Month Rolling"
cutoff_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=90)

logger.info(f"Fetching saved tracks added after {cutoff_date.strftime('%Y-%m-%d')}...")

# Fetch all saved tracks and filter by added_at date
filtered_tracks = []
results = sp.current_user_saved_tracks(limit=50)

while results:
    for item in results["items"]:
        track = item["track"]
        added_at = datetime.datetime.fromisoformat(item["added_at"].replace('Z', '+00:00'))
        
        if added_at >= cutoff_date:
            filtered_tracks.append({
                "id": track["id"],
                "name": track["name"],
                "artists": [a["name"] for a in track["artists"]],
                "added_at": added_at
            })
            logger.debug(f"Track within window: {track['name']} by {track['artists'][0]['name']} (added {added_at.strftime('%Y-%m-%d')})")
    
    if results["next"]:
        results = sp.next(results)
    else:
        break

logger.info(f"Found {len(filtered_tracks)} tracks in the last 90 days")
```

**Step 2: Add playlist management (find/clear/add logic)**

```python
# Find existing playlist or create new one
user_id = sp.current_user()["id"]
user_playlists = sp.user_playlists(user_id)

existing_playlist = None
while user_playlists:
    for playlist in user_playlists["items"]:
        if playlist["name"] == playlist_name:
            existing_playlist = playlist
            logger.info(f"Found existing playlist: {playlist_name}")
            break
    if user_playlists["next"]:
        user_playlists = sp.next(user_playlists)
    else:
        break

if existing_playlist:
    # Clear existing playlist
    playlist_id = existing_playlist["id"]
    track_ids = sp.playlist_items(playlist_id, limit=50)
    all_track_ids = []
    
    while track_ids:
        for item in track_ids["items"]:
            if item["track"]:
                all_track_ids.append(item["track"]["id"])
        if track_ids["next"]:
            track_ids = sp.next(track_ids)
        else:
            break
    
    if all_track_ids:
        logger.info(f"Clearing {len(all_track_ids)} tracks from existing playlist...")
        sp.playlist_remove_all_occurrences_of_items(playlist_id, all_track_ids)
    
    # Add filtered tracks
    track_ids_to_add = [t["id"] for t in filtered_tracks]
    if track_ids_to_add:
        sp.playlist_add_items(playlist_id, track_ids_to_add)
        logger.info(f"Added {len(track_ids_to_add)} tracks to playlist")
else:
    # Create new playlist
    playlist_id = sp.user_playlist_create(
        user_id,
        playlist_name,
        public=False,
        description=f"Tracks liked in the last 90 days (last updated: {datetime.datetime.now().strftime('%Y-%m-%d')})"
    )["id"]
    
    track_ids_to_add = [t["id"] for t in filtered_tracks]
    if track_ids_to_add:
        sp.playlist_add_items(playlist_id, track_ids_to_add)
        logger.info(f"Created new playlist with {len(track_ids_to_add)} tracks")

logger.info(f"3 Month Rolling playlist updated successfully!")
```

**Step 3: Test the script by running it**

Run: `source /Users/aaryanrampal/env/spotify/bin/activate && python make-3month-rolling.py`
Expected: Script runs without errors, logs track counts, creates/updates playlist with 3-month window

**Step 4: Commit**

```bash
git add make-3month-rolling.py 3month_rolling.log
git commit -m "feat: add 3-month rolling window playlist generator"
```

---

## Task 3: Create master orchestration shell script

**Files:**
- Create: `make_all_playlists.sh`

**Step 1: Write the shell script header and environment setup**

```bash
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
```

**Step 2: Add weekly mix conditional execution logic**

```bash
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
```

**Step 3: Add rolling windows execution (always runs)**

```bash
echo "Running 1-month rolling window..."
python make-1month-rolling.py
ROLLING_1_EXIT_CODE=$?
if [ $ROLLING_1_EXIT_CODE -eq 0 ]; then
    echo "✓ 1-month rolling completed successfully"
else
    echo "✗ 1-month rolling failed with exit code $ROLLING_1_EXIT_CODE"
fi
echo ""

echo "Running 3-month rolling window..."
python make-3month-rolling.py
ROLLING_3_EXIT_CODE=$?
if [ $ROLLING_3_EXIT_CODE -eq 0 ]; then
    echo "✓ 3-month rolling completed successfully"
else
    echo "✗ 3-month rolling failed with exit code $ROLLING_3_EXIT_CODE"
fi
echo ""

echo "=== Playlist generation complete ==="
date
```

**Step 4: Make script executable and test it**

Run: `chmod +x make_all_playlists.sh && ./make_all_playlists.sh`
Expected: Script runs all playlist generators, logs success/failure for each

**Step 5: Commit**

```bash
git add make_all_playlists.sh
git commit -m "feat: add master orchestration script for all playlists"
```

---

## Task 4: Create LaunchAgent plist for daily execution

**Files:**
- Create: `com.aaryan.spotify.daily.plist`

**Step 1: Create the plist file**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.aaryan.spotify.daily</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>/bin/zsh</string>
        <string>/Users/aaryanrampal/personal/programs/spotify/make_all_playlists.sh</string>
    </array>
    
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>9</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    
    <key>StandardOutPath</key>
    <string>/Users/aaryanrampal/personal/programs/spotify/daily_playlist.log</string>
    
    <key>StandardErrorPath</key>
    <string>/Users/aaryanrampal/personal/programs/spotify/daily_playlist_error.log</string>
    
    <key>WorkingDirectory</key>
    <string>/Users/aaryanrampal/personal/programs/spotify</string>
</dict>
</plist>
```

**Step 2: Test loading the plist**

Run: `launchctl load ~/Library/LaunchAgents/com.aaryan.spotify.daily.plist`
Expected: No error output, launches loaded successfully

**Step 3: Verify the plist is loaded**

Run: `launchctl list | grep spotify`
Expected: See entry for com.aaryan.spotify.daily

**Step 4: Commit**

```bash
git add com.aaryan.spotify.daily.plist
git commit -m "feat: add LaunchAgent for daily playlist generation"
```

---

## Task 5: Update .gitignore for log files

**Files:**
- Modify: `.gitignore`

**Step 1: Add log files to gitignore**

```
# Add these lines to .gitignore:
*.log
```

**Step 2: Commit**

```bash
git add .gitignore
git commit -chore: ignore log files"
```

---

## Task 6: Documentation update

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Update CLAUDE.md with new scripts and orchestration**

Add after the "Running the Script" section:

```markdown
## Weekly Mix

**Master orchestration script (runs all playlists):**
```bash
./make_all_playlists.sh
```

The master script runs all three playlist generators:
- **Weekly Mix** (Monday only by default): Random tracks from followed artists
- **1-Month Rolling** (daily): All tracks liked in the last 30 days
- **3-Month Rolling** (daily): All tracks liked in the last 90 days

To change the weekly mix schedule day, edit `WEEKLY_DAY` in `make_all_playlists.sh` (0=Sunday, 1=Monday, etc.)

**Individual rolling window scripts:**
```bash
python make-1month-rolling.py
python make-3month-rolling.py
```

Both rolling window scripts:
- Fetch all saved tracks with `added_at` timestamps
- Filter tracks by date window (30 or 90 days from today)
- Find existing playlist by name and clear it, then add filtered tracks
- Create new playlist if none exists

**Playlist names:**
- "1 Month Rolling" - Tracks liked in last 30 days
- "3 Month Rolling" - Tracks liked in last 90 days

**Scheduling:**

Load the daily LaunchAgent:
```bash
launchctl load ~/Library/LaunchAgents/com.aaryan.spotify.daily.plist
```

Unload the daily LaunchAgent:
```bash
launchctl unload ~/Library/LaunchAgents/com.aaryan.spotify.daily.plist
```

The daily LaunchAgent runs `make_all_playlists.sh` every day at 9:00 AM.
```

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update documentation for rolling window playlists"
```

---

## Task 7: Final verification test

**No files modified**

**Step 1: Run a manual test of all scripts**

Run: `./make_all_playlists.sh`
Expected: All three scripts run successfully, playlists are created/updated

**Step 2: Verify playlists exist in Spotify**

Check your Spotify library for:
- "Weekly Mix [week number]" (if today matches WEEKLY_DAY)
- "1 Month Rolling"
- "3 Month Rolling"

Expected: All playlists present and contain appropriate tracks

**Step 3: Check log files**

Run: `cat daily_playlist.log`
Expected: Shows execution of all three playlist generators with success/failure status

**Step 4: Commit final verification results**

```bash
git commit --allow-empty -m "test: verified all playlist generators working correctly"
```

---

## Notes for Implementation

- **Date filtering**: Use `item["added_at"]` from `current_user_saved_tracks()` API response
- **Time.zone awareness**: Ensure all datetime comparisons use UTC (`datetime.timezone.utc`)
- **Playlist clearing**: Use `playlist_remove_all_occurrences_of_items()` to clear existing playlist
- **Exit codes**: Each Python script should exit with 0 on success, non-zero on failure
- **Conditional execution**: Weekly mix only runs when `CURRENT_DAY == WEEKLY_DAY`, rolling windows always run
- **Error handling**: Shell script captures exit codes and logs success/failure for each component
- **LaunchAgent scheduling**: Runs daily at 9:00 AM, but weekly mix logic in script handles the day-of-week filtering
