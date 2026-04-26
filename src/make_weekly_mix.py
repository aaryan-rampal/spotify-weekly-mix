# %%
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import os
import random
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
import yaml
from generative_discovery import discover_similar_spotify_artist
from loguru import logger
from saved_tracks_cache import get_saved_track_keys
from weekly_mix_description import (
    build_playlist_description,
    format_generative_attribution,
)
from weekly_mix_state import (
    STATE_PATH,
    build_weekly_mix_identity,
    find_current_week_playlist,
    load_weekly_mix_runs,
    record_weekly_mix_run,
)

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
    "logs/weekly-mix.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
    level="DEBUG",
)
logger.add(
    lambda msg: print(msg, end=""),
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
    level="INFO",
)

load_dotenv()

config_path = Path(__file__).parent.parent / "config.yaml"
with open(config_path) as f:
    config = yaml.safe_load(f)

client_id = os.getenv("SPOTIPY_CLIENT_ID")
client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")
redirect_uri = os.getenv("SPOTIPY_REDIRECT_URI")
lastfm_api_key = os.getenv("LASTFM_API_KEY")
scope = (
    "playlist-modify-public,playlist-modify-private,playlist-read-private,"
    "user-library-read,user-follow-read"
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
user_id = sp.current_user()["id"]
weekly_mix_identity = build_weekly_mix_identity()
weekly_mix_state = load_weekly_mix_runs()
existing_weekly_mix = find_current_week_playlist(
    sp=sp,
    user_id=user_id,
    identity=weekly_mix_identity,
    state=weekly_mix_state,
)

if existing_weekly_mix:
    playlist_id = existing_weekly_mix.get("playlist_id") or existing_weekly_mix["id"]
    logger.info(
        f"Weekly mix already exists for {weekly_mix_identity.key}: {playlist_id}"
    )
    if "playlist_id" not in existing_weekly_mix:
        record_weekly_mix_run(
            state_path=STATE_PATH,
            identity=weekly_mix_identity,
            playlist_id=playlist_id,
            playlist_url=existing_weekly_mix.get("external_urls", {}).get("spotify"),
        )
    raise SystemExit(0)

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
saved_artist_names = {artist["name"] for artist in saved_artists}

# %%
# Get all saved tracks to check for duplicates by name+artist
logger.info("Fetching saved tracks to avoid duplicates...")
saved_tracks_set = get_saved_track_keys(sp)


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
def get_generative_track(sp, saved_artists, saved_artist_names, lastfm_api_key, logger):
    """Get a random track from a Last.fm similar artist."""
    if not lastfm_api_key:
        logger.warning("LASTFM_API_KEY is not set; skipping generative discovery")
        return None
    if not saved_artists:
        logger.error("No saved artists to use for generative discovery")
        return None

    seed_artist = pick_random_artist(saved_artists)
    logger.debug(f"Using {seed_artist['name']} as Last.fm generative seed")
    try:
        similar_artist = discover_similar_spotify_artist(
            sp=sp,
            seed_artist_name=seed_artist["name"],
            saved_artist_names=saved_artist_names,
            lastfm_api_key=lastfm_api_key,
            logger=logger,
        )
    except Exception as e:
        logger.warning(f"Generative discovery failed for {seed_artist['name']}: {e}")
        return None

    if not similar_artist:
        return None

    track = pick_random_track_from_artist(similar_artist["id"])
    if not track:
        logger.debug(f"No tracks found for generative artist {similar_artist['name']}")
        return None

    track["generative_artist"] = similar_artist
    track["discovery_reason"] = f"Last.fm similar to {seed_artist['name']}"
    return track


def should_try_generative(generative_runtime_ms, generative_runtime_target_ms):
    """Return whether the next attempt should use Last.fm discovery."""
    return generative_runtime_ms < generative_runtime_target_ms


def pick_candidate_track():
    """Pick either a Last.fm generative track or a normal saved-artist track."""
    if should_try_generative(generative_runtime_ms, generative_runtime_target_ms):
        track = get_generative_track(
            sp,
            saved_artists,
            saved_artist_names,
            lastfm_api_key,
            logger,
        )
        if track:
            artist = track["generative_artist"]
            return track, artist, True

    artist = pick_random_artist(saved_artists)
    track = pick_random_track_from_artist(artist["id"])
    return track, artist, False


# %%
# LOAD CONFIGURATION FROM config.yaml
max_tracks = config["max_tracks"]
max_runtime = config["max_runtime"]
max_artist = config["max_artist"]
failed_runtime_attempts = config["failed_runtime_attempts"]
generative_percentage_mean = config["generative_percentage_mean"]
generative_percentage_std = config["generative_percentage_std"]
generative_runtime_overrun_percentage = config.get(
    "generative_runtime_overrun_percentage",
    10,
)

max_runtime_ms = max_runtime * 60 * 1000
total_runtime = 0
runtime_limit_hits = 0
new_playlist_ids: list[str] = []
artist_counts: dict[str, int] = defaultdict(int)
generative_artists: list[dict] = []
generative_artist_ids: set[str] = set()
attempts = 0
max_attempts = 200  # Prevent infinite loops
ended_early_reason = ""

generative_percentage = max(
    0,
    min(100, random.gauss(generative_percentage_mean, generative_percentage_std)),
)
generative_runtime_target_ms = int(max_runtime_ms * generative_percentage / 100)
generative_runtime_cap_ms = int(
    generative_runtime_target_ms * (1 + generative_runtime_overrun_percentage / 100)
)
generative_runtime_ms = 0
generative_tracks_added = 0

logger.info(
    f"Creating weekly mix with max {max_tracks} tracks, "
    f"{max_runtime} minutes runtime, max {max_artist} tracks per artist, "
    f"{generative_percentage:.1f}% generative runtime target"
)
if generative_runtime_target_ms and not lastfm_api_key:
    logger.warning("LASTFM_API_KEY is not set; generative discovery is disabled")
    generative_runtime_target_ms = 0
    generative_runtime_cap_ms = 0

while (
    total_runtime <= max_runtime_ms
    and len(new_playlist_ids) < max_tracks
    and attempts < max_attempts
):
    attempts += 1

    rand_track, artist, is_generative = pick_candidate_track()
    artist_name = artist["name"]

    if not rand_track:
        logger.warning(f"No tracks found for {artist_name}")
        continue

    rand_track_id = rand_track["id"]
    rand_track_ms = rand_track["duration_ms"]
    track_name = rand_track["name"]

    # Check if track (or a version of it) is already saved
    track_key = (track_name.lower().strip(), artist_name.lower().strip())
    if track_key in saved_tracks_set:
        logger.debug(
            f"{track_name} by {artist_name} is already saved (or a version of it)"
        )
        continue

    # Check artist count limit
    if artist_counts[artist_name] >= max_artist:
        logger.debug(
            f"{track_name} by {artist_name} - too many tracks by this artist already"
        )
        continue

    # Check if adding this track would exceed runtime
    if total_runtime + rand_track_ms > max_runtime_ms:
        runtime_limit_hits += 1
        logger.debug(f"{track_name} by {artist_name} would make playlist too long")
        if runtime_limit_hits >= failed_runtime_attempts:
            ended_early_reason = (
                "Ended early because too many tracks hit runtime limit, "
                "likely near max time."
            )
            logger.info(ended_early_reason)
            break
        continue

    if is_generative and generative_runtime_ms + rand_track_ms > generative_runtime_cap_ms:
        logger.debug(
            f"{track_name} by {artist_name} would exceed generative runtime cap"
        )
        continue

    new_playlist_ids.append(rand_track_id)
    total_runtime += rand_track_ms
    artist_counts[artist_name] += 1
    if is_generative:
        generative_attribution = format_generative_attribution(
            rand_track["generative_artist"]
        )
        logger.info(
            f"✓ {track_name} by {artist_name} made it to the playlist! "
            f"Generative artist: {generative_attribution}"
        )
        generative_tracks_added += 1
        generative_runtime_ms += rand_track_ms
        generative_artist = rand_track["generative_artist"]
        if generative_artist["id"] not in generative_artist_ids:
            generative_artists.append(generative_artist)
            generative_artist_ids.add(generative_artist["id"])
    else:
        logger.info(f"✓ {track_name} by {artist_name} made it to the playlist!")

logger.info(f"\nPlaylist created with {len(new_playlist_ids)} tracks")
logger.info(f"Total runtime: {total_runtime / 1000 / 60:.1f} minutes")
logger.info(f"Attempts made: {attempts}")
logger.info(f"Runtime limit hits: {runtime_limit_hits}")
logger.info(f"Generative tracks added: {generative_tracks_added}")
logger.info(
    f"Generative runtime: {generative_runtime_ms / 1000 / 60:.1f}/"
    f"{generative_runtime_target_ms / 1000 / 60:.1f} minutes"
)
if ended_early_reason:
    logger.info(ended_early_reason)

# %%
if new_playlist_ids:
    playlist_name = weekly_mix_identity.playlist_name

    logger.info(f"Creating playlist: {playlist_name}")
    new_playlist = sp.user_playlist_create(
        user_id,
        playlist_name,
        public=False,
        description=build_playlist_description(generative_artists),
    )
    sp.playlist_add_items(new_playlist["id"], new_playlist_ids)
    record_weekly_mix_run(
        state_path=STATE_PATH,
        identity=weekly_mix_identity,
        playlist_id=new_playlist["id"],
        playlist_url=new_playlist["external_urls"]["spotify"],
    )

    logger.info(f"Playlist '{playlist_name}' created successfully!")
    logger.info(f"Playlist URL: {new_playlist['external_urls']['spotify']}")
else:
    logger.warning("No tracks were added to the playlist.")

# %%
# Display final artist distribution
logger.info("\nArtist distribution in the playlist:")

# Group artists by track count
tracks_to_artists = defaultdict(list)
for artist, count in artist_counts.items():
    if count > 0:
        tracks_to_artists[count].append(artist)

# Display grouped by count, only showing groups that exist and are <= max_artist
for track_count in sorted(tracks_to_artists.keys()):
    if track_count <= max_artist:
        artists = sorted(tracks_to_artists[track_count])
        plural = "track" if track_count == 1 else "tracks"
        logger.info(f"Artists with {track_count} {plural}:")
        for artist in artists:
            logger.info(f"  - {artist}")

# %%
