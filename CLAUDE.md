# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Python tool that automatically generates weekly playlists from your saved/followed artists on Spotify. The script fetches all followed artists, randomly selects tracks from their albums based on configurable constraints, and creates a private playlist in your Spotify account.

## Environment Setup

This project uses a Python virtual environment located at `/Users/aaryanrampal/env/spotify/`.

**Activate the environment:**
```bash
source /Users/aaryanrampal/env/spotify/bin/activate
```

**Required environment variables in `.env`:**
- `SPOTIPY_CLIENT_ID` - Spotify API client ID
- `SPOTIPY_CLIENT_SECRET` - Spotify API client secret
- `SPOTIPY_REDIRECT_URI` - OAuth redirect URI (default: http://localhost:8888/callback)

## Running the Script

**Via shell wrapper (recommended):**
```bash
./make_weekly_mix.sh
```

The shell wrapper handles environment activation and cleans up any stuck processes on port 5173 from previous runs.

**Directly with Python:**
```bash
python make-weekly-mix-saved-artists.py
```

## Code Architecture

### Main Script: `make-weekly-mix-saved-artists.py`

**Core workflow:**
1. **Authentication** (lines 43-60): Uses SpotifyOAuth with `playlist-modify-public`, `playlist-modify-private`, `user-library-read`, and `user-follow-read` scopes
2. **Artist fetching** (lines 63-78): Paginates through all followed artists using `sp.current_user_followed_artists()`
3. **Playlist generation** (lines 151-224): Randomly selects tracks with constraints until limits are reached
4. **Playlist creation** (lines 233-250): Creates a private playlist named "Weekly Mix {week_number}"

**Key functions:**
- `get_artist_albums(artist_id)` (lines 82-110): Cached function that fetches all albums/singles for an artist, stops pagination when encountering albums not belonging to the requested artist
- `get_album_tracks(album_id)` (lines 114-122): Cached function that fetches tracks from a specific album
- `pick_random_artist(saved_artists)` (line 126): Returns a random artist from the saved list
- `pick_random_track_from_artist(artist_id)` (line 133): Selects a random album, then a random track from that album

**Track selection logic** (lines 171-223):
The main loop attempts to add tracks until reaching max_tracks or max_runtime, with these filters:
- Skip tracks already saved to the user's library (line 196)
- Skip if artist already has max_artist tracks in the playlist (line 204)
- Skip if track would exceed max_runtime (line 209)
- Break early after failed_runtime_attempts consecutive runtime rejections (line 212)

**Configurable constraints** (lines 152-156):
- `max_tracks`: Maximum number of tracks (default: 16)
- `max_runtime`: Maximum playlist duration in minutes (default: 60)
- `max_artist`: Maximum tracks per artist (default: 2)
- `failed_runtime_attempts`: Number of runtime limit hits before early termination (default: 5)

### Caching Strategy

The script uses `@lru_cache` decorators on `get_artist_albums` (maxsize=128) and `get_album_tracks` (maxsize=256) to minimize redundant Spotify API calls during track selection.

### Shell Wrapper: `make_weekly_mix.sh`

- Activates the virtual environment
- Changes to the project directory
- Cleans up any processes stuck on port 5173 (lines 6-10)
- Runs the Python script

## Output and Logging

- Execution details are logged to `weekly_mix.log`
- Console output shows artist discovery progress, track selection decisions, and final statistics
- Final output includes playlist URL and artist distribution

## Important Notes

- The script creates playlists named "Weekly Mix {ISO_week_number}" using the current ISO week number
- Track selection is randomized but filtered to avoid duplicating tracks from the user's saved library
- The script has a max_attempts limit (200) to prevent infinite loops
- All created playlists are private by default
