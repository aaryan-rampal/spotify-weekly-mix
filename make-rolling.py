# %%
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import os
import datetime
from loguru import logger
from enum import Enum

# %%
logger.remove()
logger.add(
    "logs/rolling.log",
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
def pin_playlist(playlist_id, playlist_name):
    try:
        sp.current_user_follow_playlist(playlist_id)
        logger.info(f"Pinned playlist: {playlist_name}")
    except Exception as e:
        logger.error(f"Failed to pin playlist: {e}")


class BatchAction(Enum):
    ADD = "add"
    REMOVE = "remove"


def batch_operation(items, action, playlist_id, batch_size=100):
    if items:
        # Do action in batches of 100 (Spotify API limit)
        for i in range(0, len(items), batch_size):
            batch = items[i : i + batch_size]
            if action == BatchAction.ADD:
                sp.playlist_add_items(playlist_id, batch)
            else:
                sp.playlist_remove_all_occurrences_of_items(playlist_id, batch)
            logger.info(
                f"{action.value.capitalize()}ed batch {i // batch_size + 1}: {len(batch)} tracks"
            )
        logger.info(
            f"{action.value.capitalize()}ed {len(items)} total tracks to playlist"
        )


def make_rolling_playlist(playlist_name, days=30, pin=False):
    cutoff_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        days=days
    )

    logger.info(
        f"Fetching saved tracks added after {cutoff_date.strftime('%Y-%m-%d')}..."
    )

    # Fetch all saved tracks and filter by added_at date
    filtered_tracks = []
    results = sp.current_user_saved_tracks(limit=50)

    while results:
        for item in results["items"]:
            track = item["track"]
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

    # Sort tracks by added_at date, most recent first
    filtered_tracks.sort(key=lambda x: x["added_at"], reverse=True)
    logger.info(f"Found {len(filtered_tracks)} tracks in the last {days} days")

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

        track_ids_set = set(all_track_ids)

        # Add filtered tracks
        last_n_days_ids = set([t["id"] for t in filtered_tracks])
        track_ids_to_add = list(last_n_days_ids - track_ids_set)
        track_ids_to_remove = list(track_ids_set - last_n_days_ids)

        batch_operation(
            track_ids_to_add, action=BatchAction.ADD, playlist_id=playlist_id
        )
        batch_operation(
            track_ids_to_remove, action=BatchAction.REMOVE, playlist_id=playlist_id
        )

        # Update playlist description with new timestamp
        sp.playlist_change_details(
            playlist_id,
            description=f"Tracks liked in the last {days} days (last updated: {datetime.datetime.now().strftime('%Y-%m-%d')})",
        )
    else:
        # Create new playlist
        playlist_id = sp.user_playlist_create(
            user_id,
            playlist_name,
            public=False,
            description=f"Tracks liked in the last {days} days (last updated: {datetime.datetime.now().strftime('%Y-%m-%d')})",
        )["id"]

        track_ids_to_add = [t["id"] for t in filtered_tracks]
        batch_operation(
            track_ids_to_add, action=BatchAction.ADD, playlist_id=playlist_id
        )

    logger.info(f"{days} Days Rolling playlist updated successfully!")
    if pin:
        pin_playlist(playlist_id, playlist_name)
        logger.info(f"Playlist pinned successfully!")
    logger.info(f"Playlist URL: https://open.spotify.com/playlist/{playlist_id}")


# %%
make_rolling_playlist("last month", days=30, pin=True)
make_rolling_playlist("last 3 months", days=90, pin=True)
