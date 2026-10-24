"""Plan and sync the "Weekly Mix Leftovers" playlist.

The playlist holds every track from the user's own "Weekly Mix N" playlists that is not in Liked
Songs (exact track ID), newest mix first. Each run diffs the playlist against that target rather
than rebuilding it, so a run with nothing new changes nothing, a track liked since the last run
drops off, and a new mix's leftovers land at the top without moving the rest.

A weekly mix never changes after the job builds it, so each mix's track list is cached against its
`snapshot_id` in the state volume. Only new or edited mixes cost a Spotify read; after the first
run that is about one mix a week, which keeps the job well inside Spotify's development-mode quota.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger

from weekly_mix_state import STATE_PATH

LEFTOVERS_PLAYLIST_NAME = "Weekly Mix Leftovers"
WEEKLY_MIX_NAME = re.compile(r"^Weekly Mix \d{1,2}$")
CACHE_PATH = STATE_PATH.parent / "weekly_mix_leftovers.json"
SPOTIFY_BATCH_SIZE = 100


@dataclass(frozen=True)
class MixTracks:
    """One weekly mix's tracks, as of a given snapshot.

    Attributes:
        playlist_id: Spotify ID of the mix.
        snapshot_id: Spotify's version ID for the mix's contents; a change means re-read it.
        first_added_at: Earliest item `added_at` (ISO 8601), i.e. when the job built the mix.
            None when Spotify returned no dates. Used to order mixes newest first.
        track_ids: The mix's track IDs in playlist order, episodes and local files left out.
    """

    playlist_id: str
    snapshot_id: str
    first_added_at: str | None
    track_ids: tuple[str, ...]


@dataclass(frozen=True)
class SyncPlan:
    """What to change in the leftovers playlist to make it match the target.

    Attributes:
        to_add: Track IDs to add, in target order.
        to_remove: Track IDs to remove (every occurrence).
        add_at_top: True to insert additions at the top, False to append them. The playlist is
            appended to only when it starts empty, so the first run keeps the full target order.
    """

    to_add: tuple[str, ...]
    to_remove: tuple[str, ...]
    add_at_top: bool


# %% Pure planning


def is_owned_weekly_mix(playlist: dict[str, Any], user_id: str) -> bool:
    """Whether a playlist is one of the user's own "Weekly Mix N" playlists."""
    name = playlist.get("name") or ""
    owner_id = (playlist.get("owner") or {}).get("id")
    return bool(WEEKLY_MIX_NAME.match(name)) and owner_id == user_id


def newest_first(mixes: list[MixTracks]) -> list[MixTracks]:
    """Orders mixes by build date, newest first, with undated mixes last."""
    dated = [mix for mix in mixes if mix.first_added_at]
    undated = [mix for mix in mixes if not mix.first_added_at]
    dated.sort(key=lambda mix: mix.first_added_at or "", reverse=True)
    return dated + undated


def leftover_track_ids(mixes: list[MixTracks], liked_ids: set[str]) -> list[str]:
    """Track IDs from the mixes that are not liked, in mix order, each kept once.

    Args:
        mixes: Mixes in the order their tracks should appear (newest first).
        liked_ids: Track IDs in Liked Songs.

    Returns:
        The target contents of the leftovers playlist. A track in several mixes keeps the
        position of its newest mix.
    """
    seen: set[str] = set()
    result: list[str] = []
    for mix in mixes:
        for track_id in mix.track_ids:
            if track_id in liked_ids or track_id in seen:
                continue
            seen.add(track_id)
            result.append(track_id)
    return result


def plan_sync(current_ids: list[str], desired_ids: list[str]) -> SyncPlan:
    """Diffs the playlist's current tracks against the target.

    Running the plan and then planning again yields an empty plan, which is what makes the
    nightly sync idempotent.
    """
    current = set(current_ids)
    desired = set(desired_ids)
    to_remove = tuple(
        track_id for track_id in dict.fromkeys(current_ids) if track_id not in desired
    )
    to_add = tuple(track_id for track_id in desired_ids if track_id not in current)
    return SyncPlan(to_add=to_add, to_remove=to_remove, add_at_top=bool(current_ids))


# %% Snapshot cache


def load_cache(path: Path) -> dict[str, MixTracks]:
    """Reads cached mix track lists, keyed by playlist ID.

    The cache only saves Spotify calls, so a missing or unreadable file is not an error: the run
    logs a warning and re-reads every mix, then writes a fresh cache.
    """
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return {
            playlist_id: MixTracks(
                playlist_id=playlist_id,
                snapshot_id=entry["snapshot_id"],
                first_added_at=entry.get("first_added_at"),
                track_ids=tuple(entry["track_ids"]),
            )
            for playlist_id, entry in raw["mixes"].items()
        }
    except (OSError, ValueError, KeyError, TypeError) as error:
        logger.warning(f"Ignoring unreadable leftovers cache {path}: {error}; re-reading every mix")
        return {}


def save_cache(path: Path, mixes: list[MixTracks]) -> None:
    """Writes the mix track lists atomically, so a crash never leaves a half-written cache."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "mixes": {
            mix.playlist_id: {
                "snapshot_id": mix.snapshot_id,
                "first_added_at": mix.first_added_at,
                "track_ids": list(mix.track_ids),
            }
            for mix in mixes
        }
    }
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temp_path.replace(path)


# %% Spotify reads and writes


def _paginate(sp: Any, first_page: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Collects the items of every page that follows `next` links."""
    items: list[dict[str, Any]] = []
    page = first_page
    while page:
        items.extend(page.get("items") or [])
        page = sp.next(page) if page.get("next") else None
    return items


def list_user_playlists(sp: Any) -> list[dict[str, Any]]:
    """Every playlist in the user's library: owned and followed, all pages."""
    return _paginate(sp, sp.current_user_playlists(limit=50))


def _track_of(entry: dict[str, Any]) -> dict[str, Any] | None:
    """A playlist entry's track, from the post-Feb-2026 `item` key or the older `track` key."""
    track = entry.get("item") or entry.get("track")
    if not track or track.get("type", "track") != "track" or track.get("is_local"):
        return None
    return track if track.get("id") else None


def read_mix_tracks(sp: Any, playlist: dict[str, Any]) -> MixTracks:
    """Reads a mix's tracks and build date from Spotify."""
    entries = _paginate(sp, sp.playlist_items(playlist["id"], limit=SPOTIFY_BATCH_SIZE))
    track_ids: list[str] = []
    added: list[str] = []
    for entry in entries:
        track = _track_of(entry)
        if track is None:
            continue
        track_ids.append(track["id"])
        if entry.get("added_at"):
            added.append(entry["added_at"])
    return MixTracks(
        playlist_id=playlist["id"],
        snapshot_id=playlist["snapshot_id"],
        first_added_at=min(added) if added else None,
        track_ids=tuple(track_ids),
    )


def collect_mix_tracks(
    sp: Any, mix_playlists: list[dict[str, Any]], cache: dict[str, MixTracks]
) -> tuple[list[MixTracks], int]:
    """Track lists for every mix, from the cache when the snapshot still matches.

    Returns:
        The mixes, and how many had to be read from Spotify.
    """
    mixes: list[MixTracks] = []
    reads = 0
    for playlist in mix_playlists:
        cached = cache.get(playlist["id"])
        if cached is not None and cached.snapshot_id == playlist["snapshot_id"]:
            mixes.append(cached)
            continue
        mixes.append(read_mix_tracks(sp, playlist))
        reads += 1
    return mixes, reads


def find_or_create_leftovers(
    sp: Any, user_id: str, playlists: list[dict[str, Any]]
) -> tuple[str, bool]:
    """Finds the user's own leftovers playlist by name, or creates it private.

    Returns:
        The playlist ID, and whether it was created on this run.
    """
    for playlist in playlists:
        owner_id = (playlist.get("owner") or {}).get("id")
        if playlist.get("name") == LEFTOVERS_PLAYLIST_NAME and owner_id == user_id:
            return playlist["id"], False
    created = sp.user_playlist_create(
        user_id,
        LEFTOVERS_PLAYLIST_NAME,
        public=False,
        description="Songs from your Weekly Mixes that aren't in Liked Songs.",
    )
    return created["id"], True


def read_playlist_track_ids(sp: Any, playlist_id: str) -> list[str]:
    """The playlist's track IDs in order."""
    entries = _paginate(sp, sp.playlist_items(playlist_id, limit=SPOTIFY_BATCH_SIZE))
    return [track["id"] for entry in entries if (track := _track_of(entry)) is not None]


def _batches(items: tuple[str, ...]) -> list[list[str]]:
    return [
        list(items[i : i + SPOTIFY_BATCH_SIZE]) for i in range(0, len(items), SPOTIFY_BATCH_SIZE)
    ]


def apply_plan(sp: Any, playlist_id: str, plan: SyncPlan) -> None:
    """Applies a sync plan, removing first and then adding.

    Additions at the top go in last batch first: each batch is inserted at position 0, so
    inserting in reverse leaves the first batch on top and the target order intact.
    """
    for batch in _batches(plan.to_remove):
        sp.playlist_remove_all_occurrences_of_items(playlist_id, batch)
    batches = _batches(plan.to_add)
    if plan.add_at_top:
        for batch in reversed(batches):
            sp.playlist_add_items(playlist_id, batch, position=0)
    else:
        for batch in batches:
            sp.playlist_add_items(playlist_id, batch, position=None)
