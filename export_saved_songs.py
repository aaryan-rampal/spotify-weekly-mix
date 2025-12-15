# %%
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import os
import csv
from datetime import datetime

# %%
# Load environment variables
load_dotenv()
client_id = os.getenv("SPOTIPY_CLIENT_ID")
client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")
redirect_uri = os.getenv("SPOTIPY_REDIRECT_URI")
scope = "user-library-read"

# %%
# Initialize Spotify client
sp = spotipy.Spotify(
    auth_manager=SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=scope,
    )
)


# %%
def format_duration(duration_ms):
    """Convert milliseconds to MM:SS format"""
    total_seconds = duration_ms // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d}"


def extract_artists(track):
    """Extract all artist names from a track"""
    artists = track.get("artists", [])
    return ", ".join([artist["name"] for artist in artists])


# %%
print("Fetching your saved songs from Spotify...")
print("-" * 50)

all_tracks = []
results = sp.current_user_saved_tracks(limit=50)
track_count = 0

# Paginate through all saved tracks
while results:
    for item in results["items"]:
        track = item["track"]

        # Extract track information
        track_data = {
            "Title": track.get("name", "N/A"),
            "Artists": extract_artists(track),
            "Album": track.get("album", {}).get("name", "N/A"),
            "Duration": format_duration(track.get("duration_ms", 0)),
            "Release Date": track.get("album", {}).get("release_date", "N/A"),
            "Popularity": track.get("popularity", "N/A"),
            "Spotify URL": track.get("external_urls", {}).get("spotify", "N/A"),
            "Track URI": track.get("uri", "N/A"),
        }

        all_tracks.append(track_data)
        track_count += 1

        if track_count % 50 == 0:
            print(f"Fetched {track_count} tracks...")

    # Get next batch of results
    if results["next"]:
        results = sp.next(results)
    else:
        break

# %%
# Write to CSV file
output_filename = "saved_songs.csv"
timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

try:
    with open(output_filename, "w", newline="", encoding="utf-8") as csvfile:
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
        writer.writerows(all_tracks)

    print("-" * 50)
    print(f"✓ Successfully exported {track_count} saved songs!")
    print(f"✓ File saved as: {output_filename}")
    print(f"✓ Export completed at: {timestamp}")

except Exception as e:
    print(f"✗ Error writing to CSV: {e}")

# %%
