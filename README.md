# Spotify Playlist Automation

Python toolset for automated Spotify playlist generation from saved artists, tracks, and listening preferences.

## Overview

Generates multiple playlist types:
- **Weekly Mix**: Randomized playlist from saved artists with configurable constraints (track count, runtime, tracks per artist)
- **Rolling Window Playlists**: 1-month and 3-month playlists from recently liked tracks
- **Generative Discovery**: (In progress) AI-powered genre and artist recommendations based on listening patterns

## Project Structure

```
src/                        # Python scripts
  make_weekly_mix.py       # Weekly mix generator
  make_rolling.py          # Rolling window playlists (1mo, 3mo)
  populate_saved_songs.py  # Export saved tracks to CSV
  generative_discovery.py  # Generative music discovery module
scripts/
  make_all_playlists.sh    # Master scheduler for all playlists
data/
  saved_songs.csv          # Exported saved tracks data
logs/                      # Application logs (gitignored)
  weekly-mix.log
  rolling.log
  saved-songs.log
  scheduler.log
```

## Requirements

- Python 3.12+
- Spotify API credentials (Client ID and Secret)
- Packages: spotipy, python-dotenv, loguru, pathlib

## Setup

1. Create `.env` file with Spotify credentials:
```bash
SPOTIPY_CLIENT_ID=your_client_id
SPOTIPY_CLIENT_SECRET=your_client_secret
SPOTIPY_REDIRECT_URI=http://localhost:8888/callback
```

2. Install Python packages spotipy, python-dotenv, loguru

3. (Optional) Configure playlist constraints in `src/make_weekly_mix.py`:
   - `max_tracks`: Maximum playlist track count
   - `max_runtime`: Maximum playlist duration in minutes
   - `max_artist`: Maximum tracks per artist

## Usage

**Run all playlists via scheduler:**
```bash
./scripts/make_all_playlists.sh
```

**Run individual scripts:**
```bash
python src/make_weekly_mix.py
python src/make_rolling.py
python src/populate_saved_songs.py
```

**Scheduler script details:**
- Weekly mix runs weekly (configurable day)
- Rolling playlists run daily
- Logs output to `logs/scheduler.log`

**macOS LaunchAgent scheduling:**
- Scheduler runs daily at 9 AM
- Update `.plist` file path if moving scripts
- Requires symlink from repo root to `~/Library/LaunchAgents/`

## Development

```bash
# Type checking
mypy src/

# Linting and formatting
ruff check src/
ruff format src/
```

See `AGENTS.md` for detailed coding guidelines, Spotify API patterns, and architecture documentation.
