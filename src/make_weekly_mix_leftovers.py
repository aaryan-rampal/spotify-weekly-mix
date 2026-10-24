# %%
import os
import time

import spotipy
from dotenv import load_dotenv
from loguru import logger
from spotipy.oauth2 import SpotifyOAuth

import app_time
from saved_tracks_cache import get_saved_tracks
from weekly_mix_leftovers import (
    CACHE_PATH,
    apply_plan,
    collect_mix_tracks,
    find_or_create_leftovers,
    is_owned_weekly_mix,
    leftover_track_ids,
    list_user_playlists,
    load_cache,
    newest_first,
    plan_sync,
    read_playlist_track_ids,
    save_cache,
)

# %%
LOG_FORMAT = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}"
logger.remove()
logger.add("logs/weekly-mix-leftovers.log", format=LOG_FORMAT, level="DEBUG")
logger.add(
    lambda msg: print(msg, end=""),
    format=LOG_FORMAT,
    level=os.getenv("LOG_LEVEL", "INFO"),
)

load_dotenv()
# Same scope string as make_rolling.py on purpose: the cached token in .cache was granted for it,
# and asking for a different scope would make spotipy want an interactive login in the container.
SCOPE = (
    "playlist-modify-public,playlist-modify-private,playlist-read-private,"
    "user-library-read,user-follow-read"
)

# %%
sp = spotipy.Spotify(
    auth_manager=SpotifyOAuth(
        client_id=os.getenv("SPOTIPY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
        redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
        scope=SCOPE,
    )
)


# %%
def sync_leftovers() -> str:
    """Brings the Weekly Mix Leftovers playlist in line with the mixes and Liked Songs.

    Returns:
        The leftovers playlist ID.
    """
    user_id = sp.current_user()["id"]
    playlists = list_user_playlists(sp)
    mix_playlists = [p for p in playlists if is_owned_weekly_mix(p, user_id)]
    logger.info(f"Found {len(mix_playlists)} weekly mixes among {len(playlists)} playlists")

    mixes, reads = collect_mix_tracks(sp, mix_playlists, load_cache(CACHE_PATH))
    save_cache(CACHE_PATH, mixes)
    logger.info(f"Read {reads} mixes from Spotify and {len(mixes) - reads} from {CACHE_PATH}")

    liked_ids = {track["id"] for track in get_saved_tracks(sp)}
    desired = leftover_track_ids(newest_first(mixes), liked_ids)
    entries = sum(len(mix.track_ids) for mix in mixes)
    logger.info(f"{len(desired)} leftovers from {entries} mix entries ({len(liked_ids)} liked)")

    playlist_id, created = find_or_create_leftovers(sp, user_id, playlists)
    current = [] if created else read_playlist_track_ids(sp, playlist_id)
    plan = plan_sync(current, desired)
    where = "at the top" if plan.add_at_top else "in order"
    logger.info(
        f"{'Created' if created else 'Updating'} playlist {playlist_id}: "
        f"adding {len(plan.to_add)} {where}, removing {len(plan.to_remove)}"
    )
    apply_plan(sp, playlist_id, plan)

    sp.playlist_change_details(
        playlist_id,
        description=(
            "Songs from your Weekly Mixes that aren't in Liked Songs, newest mix first. "
            f"{len(desired)} songs, updated {app_time.now():%Y-%m-%d}."
        ),
    )
    sp.current_user_follow_playlist(playlist_id)
    return playlist_id


def main() -> None:
    """Nightly entry point: one sync logged with its duration; failures are logged, then raised."""
    started = time.monotonic()
    logger.info("Weekly Mix Leftovers: sync starting")
    try:
        playlist_id = sync_leftovers()
    except Exception:
        logger.exception(
            f"Weekly Mix Leftovers: sync failed after {time.monotonic() - started:.1f}s; "
            "check the Spotify login in .cache and logs/weekly-mix-leftovers.log"
        )
        raise
    logger.info(
        f"Weekly Mix Leftovers: synced in {time.monotonic() - started:.1f}s, "
        f"https://open.spotify.com/playlist/{playlist_id}"
    )


# %%
if __name__ == "__main__":
    main()
