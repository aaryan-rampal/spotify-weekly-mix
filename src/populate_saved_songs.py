#!/usr/bin/env python3
"""
Script to fetch all saved tracks from Spotify and populate saved_songs.csv
"""

import csv
import logging
import os
from pathlib import Path

import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("logs/saved-songs.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Authenticate with Spotify
scope = "user-library-read"
sp = spotipy.Spotify(
    auth_manager=SpotifyOAuth(
        client_id=os.getenv("SPOTIPY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
        redirect_uri=os.getenv(
            "SPOTIPY_REDIRECT_URI", "http://localhost:8888/callback"
        ),
        scope=scope,
    )
)

logger.info("Starting to fetch saved tracks from Spotify...")

# Fetch all saved tracks
saved_tracks = []
offset = 0
limit = 50

while True:
    logger.info(f"Fetching saved tracks (offset: {offset})...")
    results = sp.current_user_saved_tracks(limit=limit, offset=offset)

    if not results["items"]:
        break

    for item in results["items"]:
        track = item["track"]

        # Extract track information
        title = track["name"]
        artists = ", ".join([artist["name"] for artist in track["artists"]])
        album = track["album"]["name"]

        # Convert duration from milliseconds to MM:SS format
        duration_ms = track["duration_ms"]
        duration_min = duration_ms // 60000
        duration_sec = (duration_ms % 60000) // 1000
        duration = f"{duration_min}:{duration_sec:02d}"

        release_date = track["album"]["release_date"]
        popularity = track["popularity"]
        spotify_url = track["external_urls"]["spotify"]
        track_uri = track["uri"]

        saved_tracks.append(
            {
                "Title": title,
                "Artists": artists,
                "Album": album,
                "Duration": duration,
                "Release Date": release_date,
                "Popularity": popularity,
                "Spotify URL": spotify_url,
                "Track URI": track_uri,
            }
        )

    offset += limit

    # Break if we've fetched all tracks
    if len(results["items"]) < limit:
        break

logger.info(f"Fetched {len(saved_tracks)} saved tracks")

# Write to CSV
csv_path = Path(__file__).parent.parent / "data" / "saved_songs.csv"
logger.info(f"Writing tracks to {csv_path}...")

with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
    fieldnames = [
        "Title",
        "Artists",
        "Album",
        "Duration",
        "Release Date",
        "Popularity",
        "Spotify URL",
        "Track URI",
    ]
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

    writer.writeheader()
    writer.writerows(saved_tracks)

logger.info(f"Successfully wrote {len(saved_tracks)} tracks to {csv_path}")
print(f"\n✓ Saved {len(saved_tracks)} tracks to saved_songs.csv")
