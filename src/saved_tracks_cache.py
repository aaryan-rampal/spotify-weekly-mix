import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from loguru import logger

# %%
logger.remove()
logger.add(
    "logs/saved-tracks-cache.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
    level="DEBUG",
)
logger.add(
    lambda msg: print(msg, end=""),
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
    level="INFO",
)

# %%
CACHE_FILE = Path(__file__).parent.parent / "data" / "saved_tracks.json"
CACHE_EXPIRY_HOURS = 24


# %%
def get_saved_tracks(sp, force_refresh: bool = False) -> List[Dict]:
    cached = _load_from_cache()
    if cached is not None and not force_refresh:
        logger.info(f"Loaded {len(cached)} tracks from cache")
        return cached

    if force_refresh:
        logger.info("Force refresh requested, fetching from API")
    else:
        logger.info("Cache not available or expired, fetching from API")

    tracks = _fetch_from_api(sp)
    _save_to_cache(tracks)
    logger.info(f"Fetched and cached {len(tracks)} tracks")
    return tracks


def get_tracks_in_date_range(sp, days: int, force_refresh: bool = False) -> List[Dict]:
    all_tracks = get_saved_tracks(sp, force_refresh)

    cutoff_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        days=days
    )

    filtered = [
        t
        for t in all_tracks
        if datetime.datetime.fromisoformat(t["added_at"].replace("Z", "+00:00"))
        >= cutoff_date
    ]

    logger.info(
        f"Filtered to {len(filtered)} tracks from last {days} days (total: {len(all_tracks)})"
    )
    return filtered


def get_saved_track_keys(sp, force_refresh: bool = False) -> Set[Tuple[str, str]]:
    tracks = get_saved_tracks(sp, force_refresh)

    keys = {
        (t["name"].lower().strip(), t["primary_artist"].lower().strip()) for t in tracks
    }

    logger.info(f"Generated {len(keys)} unique track keys for duplicate checking")
    return keys


def _load_from_cache() -> Optional[List[Dict]]:
    if not CACHE_FILE.exists():
        logger.debug("Cache file does not exist")
        return None

    try:
        import json

        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache_data = json.load(f)

        if not _is_cache_valid(cache_data):
            logger.debug("Cache exists but is expired")
            return None

        cached_at = datetime.datetime.fromisoformat(
            cache_data["cached_at"].replace("Z", "+00:00")
        )
        age = datetime.datetime.now(datetime.timezone.utc) - cached_at

        logger.debug(
            f"Cache loaded: {cache_data['track_count']} tracks, {age.seconds // 3600}h old"
        )
        return cache_data["tracks"]
    except Exception as e:
        logger.error(f"Error loading cache: {e}")
        return None


def _save_to_cache(tracks: List[Dict]) -> None:
    try:
        import json

        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

        cache_data = {
            "cached_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "track_count": len(tracks),
            "tracks": tracks,
        }

        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)

        logger.debug(f"Cache saved to {CACHE_FILE}")
    except Exception as e:
        logger.error(f"Error saving cache: {e}")


def _fetch_from_api(sp) -> List[Dict]:
    tracks = []
    results = sp.current_user_saved_tracks(limit=50)

    while results:
        for item in results["items"]:
            track = item["track"]
            if not track:
                continue

            primary_artist = (
                track["artists"][0]["name"] if track["artists"] else "Unknown"
            )

            tracks.append(
                {
                    "id": track["id"],
                    "name": track["name"],
                    "primary_artist": primary_artist,
                    "artists": [a["name"] for a in track["artists"]],
                    "added_at": item["added_at"],
                    "album": track["album"]["name"],
                    "duration_ms": track["duration_ms"],
                    "spotify_url": track["external_urls"]["spotify"],
                }
            )

        if results["next"]:
            results = sp.next(results)
        else:
            break

    return tracks


def _is_cache_valid(cache_data: Dict) -> bool:
    cached_at = datetime.datetime.fromisoformat(
        cache_data["cached_at"].replace("Z", "+00:00")
    )
    age = datetime.datetime.now(datetime.timezone.utc) - cached_at

    is_valid = age.total_seconds() < CACHE_EXPIRY_HOURS * 60 * 60

    if is_valid:
        logger.debug(f"Cache is valid ({age.seconds // 3600}h old)")
    else:
        logger.debug(f"Cache is expired ({age.seconds // 3600}h old)")

    return is_valid
