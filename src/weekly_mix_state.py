import datetime
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CURRENT_MARKER_PREFIX = "Generated for ISO week"
STATE_PATH = Path(__file__).parent.parent / "data" / "weekly_mix_runs.json"


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
        now = datetime.datetime.now()

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
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "name": identity.playlist_name,
    }
    if playlist_url:
        state[identity.key]["playlist_url"] = playlist_url

    state_path.parent.mkdir(parents=True, exist_ok=True)
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.write("\n")


def find_current_week_playlist(
    sp: Any,
    user_id: str,
    identity: WeeklyMixIdentity,
    state: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    """Find this week's playlist from local state or Spotify description marker."""
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


def has_current_week_mix(
    sp: Any,
    user_id: str,
    identity: WeeklyMixIdentity,
    state: dict[str, dict[str, Any]],
) -> bool:
    """Return whether this week's mix has already been made."""
    return find_current_week_playlist(sp, user_id, identity, state) is not None
