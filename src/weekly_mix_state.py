import datetime
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from warnings import deprecated

import app_time


CURRENT_MARKER_PREFIX = "Generated for ISO week"

# Environment variable used to point the state file at a persistent location
# (e.g. a Docker volume) so it survives `docker run --rm`. See README.
STATE_PATH_ENV_VAR = "WEEKLY_MIX_STATE_PATH"


def _default_state_path() -> Path:
    """Resolve where weekly mix state is persisted.

    Defaults to a `state/` directory (kept out of the image and intended to be
    mounted as a volume) rather than the git-ignored `data/` directory, and can
    be overridden via the ``WEEKLY_MIX_STATE_PATH`` environment variable.
    """
    override = os.environ.get(STATE_PATH_ENV_VAR)
    if override:
        return Path(override)
    return Path(__file__).parent.parent / "state" / "weekly_mix_runs.json"


STATE_PATH = _default_state_path()


@dataclass(frozen=True)
class WeeklyMixIdentity:
    key: str
    playlist_name: str
    description_marker: str


def build_weekly_mix_identity(
    now: datetime.datetime | None = None,
) -> WeeklyMixIdentity:
    """Build the stable identity for the current ISO week."""
    if now is None:
        now = app_time.now()

    iso_year, iso_week, _ = now.isocalendar()
    key = f"{iso_year}-W{iso_week:02d}"

    return WeeklyMixIdentity(
        key=key,
        playlist_name=f"Weekly Mix {iso_week}",
        description_marker=f"{CURRENT_MARKER_PREFIX} {key}",
    )


def load_weekly_mix_runs(state_path: Path = STATE_PATH) -> dict[str, dict[str, Any]]:
    """Load local weekly mix state, returning an empty state if none exists."""
    if not state_path.exists():
        return {}

    with open(state_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Expected weekly mix state to be an object: {state_path}")

    return data


def record_weekly_mix_run(
    state_path: Path,
    identity: WeeklyMixIdentity,
    playlist_id: str,
    playlist_url: str | None = None,
) -> None:
    """Record a successfully created or discovered weekly mix."""
    state = load_weekly_mix_runs(state_path)
    state[identity.key] = {
        "playlist_id": playlist_id,
        "created_at": app_time.now().isoformat(),
        "name": identity.playlist_name,
    }
    if playlist_url:
        state[identity.key]["playlist_url"] = playlist_url

    state_path.parent.mkdir(parents=True, exist_ok=True)
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.write("\n")


@deprecated(
    "The Spotify description-marker lookup is being phased out; weekly-mix "
    "dedup now relies on the persisted state file "
    "(load_weekly_mix_runs / record_weekly_mix_run). This Spotify-side "
    "fallback will be removed in a future release.",
    category=None,
)
def find_current_week_playlist(
    sp: Any,
    user_id: str,
    identity: WeeklyMixIdentity,
    state: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    """Find this week's playlist from local state or Spotify description marker.

    .. deprecated::
        Prefer the persisted state file as the source of truth. The description
        marker was never written to created playlists, so the Spotify-side scan
        cannot reliably detect existing mixes.
    """
    recorded_run = state.get(identity.key)
    if recorded_run:
        return recorded_run

    playlists = sp.current_user_playlists(limit=50)
    while playlists:
        for playlist in playlists.get("items", []):
            if playlist.get("name") != identity.playlist_name:
                continue
            if playlist.get("owner", {}).get("id") != user_id:
                continue
            if identity.description_marker in (playlist.get("description") or ""):
                return playlist

        if playlists.get("next"):
            playlists = sp.next(playlists)
        else:
            break

    return None


@deprecated(
    "The Spotify description-marker lookup is being phased out; check the "
    "persisted state file directly (e.g. `identity.key in state`) instead. "
    "This helper will be removed in a future release.",
    category=None,
)
def has_current_week_mix(
    sp: Any,
    user_id: str,
    identity: WeeklyMixIdentity,
    state: dict[str, dict[str, Any]],
) -> bool:
    """Return whether this week's mix has already been made.

    .. deprecated::
        Prefer ``identity.key in state`` backed by the persisted state file.
    """
    return find_current_week_playlist(sp, user_id, identity, state) is not None
