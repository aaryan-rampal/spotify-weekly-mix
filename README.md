# Spotify Weekly Mix Generator

A Python tool that automatically creates a randomized weekly playlist from your saved artists on Spotify.

## Overview

This project generates a weekly mix playlist by:
- Fetching all your followed/saved artists from Spotify
- Randomly selecting tracks from their albums
- Building a playlist with configurable constraints (track count, runtime, tracks per artist)
- Creating a new private playlist in your Spotify account each week

## Files

- **make-weekly-mix-saved-artists.py** - Main Python script that creates the weekly mix
- **make_weekly_mix.sh** - Shell script wrapper that activates the conda environment and runs the Python script
- **weekly_mix.log** - Log file capturing execution history

## Requirements

- Python 3.12+
- Spotify API credentials (Client ID and Secret)
- Spotipy library for Spotify API access
- Python-dotenv for environment variable management

## Setup

1. Create a `.env` file with your Spotify API credentials:
   ```
   SPOTIPY_CLIENT_ID=your_client_id
   SPOTIPY_CLIENT_SECRET=your_client_secret
   SPOTIPY_REDIRECT_URI=http://localhost:8888/callback
   ```

2. Install dependencies and set up a conda environment

3. Configure the constraints in the Python script (line 152-155):
   - `max_tracks`: Maximum number of tracks in the playlist
   - `max_runtime`: Maximum playlist duration in minutes
   - `max_artist`: Maximum tracks per artist

## Usage

Run the shell script:
```bash
./make_weekly_mix.sh
```

Or run the Python script directly:
```bash
python make-weekly-mix-saved-artists.py
```

The script will create a new private playlist named "Weekly Mix {week_number}" and add it to your Spotify account.
