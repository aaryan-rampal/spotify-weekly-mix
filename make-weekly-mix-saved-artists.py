# %%
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import os
import random
import datetime
from collections import defaultdict
from functools import lru_cache
from loguru import logger

# %%


def find_name(track):
    return track["name"]


def find_album_id(track):
    return track["album"]["id"]


def find_id(track):
    return track["id"]


def find_dur(track):
    return track["duration_ms"]


def find_artist_ids(track, return_artists=False):
    artists = track["artists"]
    if return_artists:
        return artists

    ids = []
    for artist in artists:
        ids.append(artist["id"])

    return ids


# %%
logger.remove()
logger.add(
    "weekly_mix.log",
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
    "playlist-modify-public,playlist-modify-private,user-library-read,user-follow-read"
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
# Get all saved/followed artists
logger.info("Fetching saved artists...")
saved_artists = []
results = sp.current_user_followed_artists(limit=50)

while results:
    for artist in results["artists"]["items"]:
        saved_artists.append(artist)
        logger.debug(f"Found artist: {artist['name']}")

    if results["artists"]["next"]:
        results = sp.next(results["artists"])
    else:
        break

logger.info(f"Total saved artists found: {len(saved_artists)}")

# %%
# Get all saved tracks to check for duplicates by name+artist
logger.info("Fetching saved tracks to avoid duplicates...")
saved_tracks_set = set()
results = sp.current_user_saved_tracks(limit=50)

while results:
    for item in results["items"]:
        track = item["track"]
        # Create a normalized key: lowercase track name + primary artist name
        track_key = (
            track["name"].lower().strip(),
            track["artists"][0]["name"].lower().strip() if track["artists"] else ""
        )
        saved_tracks_set.add(track_key)
        logger.debug(f"Saved track: {track['name']} by {track['artists'][0]['name'] if track['artists'] else 'Unknown'}")

    if results["next"]:
        results = sp.next(results)
    else:
        break

logger.info(f"Total saved tracks found: {len(saved_tracks_set)}")


# %%
@lru_cache(maxsize=128)
def get_artist_albums(artist_id, limit=50):
    """Get all albums for a specific artist"""
    try:
        all_albums = []
        results = sp.artist_albums(artist_id, album_type="album,single", limit=limit)

        while results:
            for album in results["items"]:
                # Check if the requested artist is actually in this album
                album_artist_ids = [artist["id"] for artist in album["artists"]]
                if artist_id in album_artist_ids:
                    all_albums.append(album)
                else:
                    # If we find an album that doesn't belong to this artist, stop here
                    logger.debug(
                        f"Found album not belonging to artist {artist_id}, stopping pagination"
                    )
                    return tuple(all_albums)

            if results["next"]:
                results = sp.next(results)
            else:
                break

        return tuple(all_albums)  # Return tuple for hashability
    except Exception as e:
        logger.error(f"Error fetching albums for artist {artist_id}: {e}")
        return tuple()


# %%
@lru_cache(maxsize=256)
def get_album_tracks(album_id):
    """Get tracks from a specific album"""
    try:
        tracks = sp.album_tracks(album_id)
        return tuple(tracks["items"])  # Return tuple for hashability
    except Exception as e:
        logger.error(f"Error fetching tracks for album {album_id}: {e}")
        return tuple()


# %%
def pick_random_artist(saved_artists):
    """Pick a random artist from saved artists"""
    rand_num = random.randint(0, len(saved_artists) - 1)
    return saved_artists[rand_num]


# %%
def pick_random_track_from_artist(artist_id):
    """Pick a random track from a random album of the given artist"""
    albums = get_artist_albums(artist_id)
    if not albums:
        return None

    # Pick a random album
    rand_album = random.choice(albums)
    tracks = get_album_tracks(rand_album["id"])

    if not tracks:
        return None

    # Pick a random track from the album
    rand_track = random.choice(tracks)
    return rand_track


# %%
# CHANGE THESE TO YOUR PREFERENCE
max_tracks = 16
max_runtime = 60
max_artist = 2
failed_runtime_attempts = 5

max_runtime_ms = max_runtime * 60 * 1000
total_runtime = 0
runtime_limit_hits = 0
new_playlist_ids = []
artist_counts = defaultdict(int)
attempts = 0
max_attempts = 200  # Prevent infinite loops
ended_early_reason = ""

logger.info(
    f"Creating weekly mix with max {max_tracks} tracks, {max_runtime} minutes runtime, max {max_artist} tracks per artist"
)

while (
    total_runtime <= max_runtime_ms
    and len(new_playlist_ids) < max_tracks
    and attempts < max_attempts
):
    attempts += 1

    # Pick a random artist
    artist = pick_random_artist(saved_artists)
    artist_name = artist["name"]
    artist_id = artist["id"]

    # Get a random track from this artist
    rand_track = pick_random_track_from_artist(artist_id)

    if not rand_track:
        logger.warning(f"No tracks found for {artist_name}")
        continue

    rand_track_id = rand_track["id"]
    rand_track_ms = rand_track["duration_ms"]
    track_name = rand_track["name"]

    # Check if track (or a version of it) is already saved
    track_key = (track_name.lower().strip(), artist_name.lower().strip())
    if track_key in saved_tracks_set:
        logger.debug(f"{track_name} by {artist_name} is already saved (or a version of it)")
        continue

    # Check artist count limit
    if artist_counts[artist_name] >= max_artist:
        logger.debug(f"{track_name} by {artist_name} - too many tracks by this artist already")
        continue

    # Check if adding this track would exceed runtime
    if total_runtime + rand_track_ms > max_runtime_ms:
        runtime_limit_hits += 1
        logger.debug(f"{track_name} by {artist_name} would make playlist too long")
        if runtime_limit_hits >= failed_runtime_attempts:
            ended_early_reason = (
                "Ended early because too many tracks hit runtime limit, likely near max time."
            )
            logger.info(ended_early_reason)
            break
        continue

    logger.info(f"✓ {track_name} by {artist_name} made it to the playlist!")
    new_playlist_ids.append(rand_track_id)
    total_runtime += rand_track_ms
    artist_counts[artist_name] += 1

logger.info(f"\nPlaylist created with {len(new_playlist_ids)} tracks")
logger.info(f"Total runtime: {total_runtime / 1000 / 60:.1f} minutes")
logger.info(f"Attempts made: {attempts}")
logger.info(f"Runtime limit hits: {runtime_limit_hits}")
if ended_early_reason:
    logger.info(ended_early_reason)

# %%
if new_playlist_ids:
    user_id = sp.current_user()["id"]
    current_week = datetime.datetime.now().isocalendar()[1]
    playlist_name = f"Weekly Mix {current_week}"

    logger.info(f"Creating playlist: {playlist_name}")
    new_playlist = sp.user_playlist_create(
        user_id,
        playlist_name,
        public=False,
        description="Your Weekly Mix from Saved Artists!",
    )
    sp.playlist_add_items(new_playlist["id"], new_playlist_ids)

    logger.info(f"Playlist '{playlist_name}' created successfully!")
    logger.info(f"Playlist URL: {new_playlist['external_urls']['spotify']}")
else:
    logger.warning("No tracks were added to the playlist.")

# %%
# Display final artist distribution
logger.info("\nArtist distribution in the playlist:")
for artist, count in artist_counts.items():
    if count == 0:
        continue
    logger.info(f"{artist}: {count} track(s)")

# %%
