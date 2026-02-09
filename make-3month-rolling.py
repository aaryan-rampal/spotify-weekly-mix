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
scope = "playlist-modify-public,playlist-modify-private,user-library-read"

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
        if not track:
            continue
        added_at = datetime.datetime.fromisoformat(
            item["added_at"].replace("Z", "+00:00")
        )

        if added_at >= cutoff_date:
            filtered_tracks.append(
                {
                    "id": track["id"],
                    "name": track["name"],
                    "artists": [a["name"] for a in track["artists"]],
                    "added_at": added_at,
                }
            )
            logger.debug(
                f"Track within window: {track['name']} by {track['artists'][0]['name']} (added {added_at.strftime('%Y-%m-%d')})"
            )

    if results["next"]:
        results = sp.next(results)
    else:
        break

logger.info(f"Found {len(filtered_tracks)} tracks in the last 90 days")

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
        # Add in batches of 100 (Spotify API limit)
        batch_size = 100
        for i in range(0, len(track_ids_to_add), batch_size):
            batch = track_ids_to_add[i : i + batch_size]
            sp.playlist_add_items(playlist_id, batch)
            logger.info(f"Added batch {i // batch_size + 1}: {len(batch)} tracks")
        logger.info(f"Added {len(track_ids_to_add)} total tracks to playlist")
else:
    # Create new playlist
    playlist_id = sp.user_playlist_create(
        user_id,
        playlist_name,
        public=False,
        description=f"Tracks liked in the last 90 days (last updated: {datetime.datetime.now().strftime('%Y-%m-%d')})",
    )["id"]

    track_ids_to_add = [t["id"] for t in filtered_tracks]
    if track_ids_to_add:
        # Add in batches of 100 (Spotify API limit)
        batch_size = 100
        for i in range(0, len(track_ids_to_add), batch_size):
            batch = track_ids_to_add[i : i + batch_size]
            sp.playlist_add_items(playlist_id, batch)
            logger.info(f"Added batch {i // batch_size + 1}: {len(batch)} tracks")
        logger.info(f"Created new playlist with {len(track_ids_to_add)} tracks")

logger.info(f"3 Month Rolling playlist updated successfully!")
