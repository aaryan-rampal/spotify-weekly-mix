# %%
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import os
import datetime
from loguru import logger
from enum import Enum
from saved_tracks_cache import get_tracks_in_date_range

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
scope = "playlist-modify-public,playlist-modify-private,playlist-read-private,user-library-read"

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


def batch_operation(items, action, playlist_id, batch_size=100, position=None):
    if items:
        logger.debug(f"Starting {action.value} operation for {len(items)} items")
        # Do action in batches of 100 (Spotify API limit)
        for i in range(0, len(items), batch_size):
            batch = items[i : i + batch_size]
            logger.debug(f"Processing batch {i // batch_size + 1}: {len(batch)} items")
            if action == BatchAction.ADD:
                result = sp.playlist_add_items(playlist_id, batch, position=position)
                logger.debug(f"Add operation result: {result}")
            else:
                result = sp.playlist_remove_all_occurrences_of_items(playlist_id, batch)
                logger.debug(f"Remove operation result: {result}")
            logger.info(
                f"{action.value.capitalize()}ed batch {i // batch_size + 1}: {len(batch)} tracks"
            )
        logger.info(
            f"{action.value.capitalize()}ed {len(items)} total tracks to playlist"
        )
    else:
        logger.debug(f"No tracks to {action.value} - items list is empty")


def make_rolling_playlist(playlist_name, days=30, pin=False):
    logger.info(f"Fetching saved tracks for last {days} days...")

    # Fetch and filter tracks by date
    filtered_tracks = get_tracks_in_date_range(sp, days)

    # Convert added_at strings to datetime for sorting
    for track in filtered_tracks:
        track["added_at"] = datetime.datetime.fromisoformat(
            track["added_at"].replace("Z", "+00:00")
        )

    # Sort tracks by added_at date, most recent first
    filtered_tracks.sort(key=lambda x: x["added_at"], reverse=True)
    logger.info(f"Found {len(filtered_tracks)} tracks in the last {days} days")

    # Find existing playlist or create new one
    logger.debug("Fetching user info...")
    user_info = sp.current_user()
    if not user_info:
        logger.error("Failed to fetch user info")
        return
    user_id = user_info["id"]
    logger.debug(f"User ID: {user_id}")
    logger.debug(f"Searching for existing playlist named '{playlist_name}'")

    existing_playlist = None

    logger.debug("Trying search API to find playlist...")
    search_results = sp.search(q=f"playlist:{playlist_name}", type="playlist", limit=10)

    if search_results and "playlists" in search_results:
        logger.debug(
            f"Search results: {search_results['playlists'].get('total', 0)} playlists found"
        )
        for playlist in search_results["playlists"]["items"]:
            if playlist["name"] == playlist_name and playlist["owner"]["id"] == user_id:
                existing_playlist = playlist
                logger.info(
                    f"Found existing playlist via search: {playlist_name} (ID: {playlist['id']})"
                )
                break

    if not existing_playlist:
        logger.debug(
            "Playlist not found via search, trying user playlist enumeration..."
        )
        user_playlists = sp.current_user_playlists(limit=50)
        playlist_count = 0

        while user_playlists:
            logger.debug(
                f"Fetched page with {len(user_playlists.get('items', []))} playlists"
            )
            for playlist in user_playlists["items"]:
                playlist_count += 1
                logger.debug(
                    f"Checking playlist {playlist_count}: {playlist['name']} (ID: {playlist['id']})"
                )
                if playlist["name"] == playlist_name:
                    existing_playlist = playlist
                    logger.info(
                        f"Found existing playlist: {playlist_name} (ID: {playlist['id']})"
                    )
                    break
            if existing_playlist:
                break
            if user_playlists["next"]:
                logger.debug(f"Fetching next page of playlists...")
                user_playlists = sp.next(user_playlists)
            else:
                break

        logger.info(
            f"Searched through {playlist_count} playlists, total available: {user_playlists.get('total', 'unknown') if user_playlists else 'unknown'}"
        )

    if not existing_playlist:
        logger.debug(f"Did not find playlist named '{playlist_name}'")

    existing_playlist = None
    playlist_count = 0

    user_playlists = sp.current_user_playlists(limit=50)

    while user_playlists:
        logger.debug(
            f"Fetched page with {len(user_playlists.get('items', []))} playlists"
        )
        for playlist in user_playlists["items"]:
            playlist_count += 1
            logger.debug(
                f"Checking playlist {playlist_count}: {playlist['name']} (ID: {playlist['id']})"
            )
            if playlist["name"] == playlist_name:
                existing_playlist = playlist
                logger.info(
                    f"Found existing playlist: {playlist_name} (ID: {playlist['id']})"
                )
                break
        if existing_playlist:
            break
        if user_playlists["next"]:
            logger.debug(f"Fetching next page of playlists...")
            user_playlists = sp.next(user_playlists)
        else:
            break

    logger.info(
        f"Searched through {playlist_count} playlists, total available: {user_playlists.get('total', 'unknown') if user_playlists else 'unknown'}"
    )
    if not existing_playlist:
        logger.debug(f"Did not find playlist named '{playlist_name}'")

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

        logger.info(f"Current playlist has {len(all_track_ids)} tracks")
        logger.debug(f"Current track IDs: {all_track_ids}")

        track_ids_set = set(all_track_ids)

        # Add filtered tracks
        logger.info(f"Filtered tracks: {len(filtered_tracks)}")
        logger.debug(f"Filtered track IDs: {[t['id'] for t in filtered_tracks]}")
        track_ids_to_add = [
            t["id"] for t in filtered_tracks if t["id"] not in track_ids_set
        ]
        track_ids_to_remove = list(
            track_ids_set - set(t["id"] for t in filtered_tracks)
        )

        logger.info(f"Tracks to add: {len(track_ids_to_add)}")
        logger.debug(f"Track IDs to add: {track_ids_to_add}")
        logger.info(f"Tracks to remove: {len(track_ids_to_remove)}")
        logger.debug(f"Track IDs to remove: {track_ids_to_remove}")

        batch_operation(
            list(reversed(track_ids_to_add)),
            action=BatchAction.ADD,
            playlist_id=playlist_id,
            position=0,
        )
        batch_operation(
            track_ids_to_remove, action=BatchAction.REMOVE, playlist_id=playlist_id
        )

        # Update playlist description with new timestamp
        new_description = f"Tracks liked in the last {days} days (last updated: {datetime.datetime.now().strftime('%Y-%m-%d')})"
        logger.debug(f"Updating playlist description to: {new_description}")
        sp.playlist_change_details(
            playlist_id,
            description=new_description,
        )
        logger.info("Playlist description updated")
    else:
        # Create new playlist
        logger.debug(f"Creating new playlist: {playlist_name}")
        new_playlist = sp.user_playlist_create(
            user_id,
            playlist_name,
            public=False,
            description=f"Tracks liked in the last {days} days (last updated: {datetime.datetime.now().strftime('%Y-%m-%d')})",
        )
        if not new_playlist:
            logger.error("Failed to create new playlist")
            return
        playlist_id = new_playlist["id"]
        logger.info(f"Created new playlist with ID: {playlist_id}")

        track_ids_to_add = [t["id"] for t in filtered_tracks]
        batch_operation(
            track_ids_to_add, action=BatchAction.ADD, playlist_id=playlist_id
        )

    logger.info(f"{days} Days Rolling playlist updated successfully!")
    if pin:
        pin_playlist(playlist_id, playlist_name)
        logger.info("Playlist pinned successfully!")
    logger.info(f"Playlist URL: https://open.spotify.com/playlist/{playlist_id}")


# %%
make_rolling_playlist("last month", days=30, pin=True)
make_rolling_playlist("last 3 months", days=90, pin=True)
