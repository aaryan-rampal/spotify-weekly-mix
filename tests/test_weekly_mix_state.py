import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from weekly_mix_state import (
    CURRENT_MARKER_PREFIX,
    build_weekly_mix_identity,
    find_current_week_playlist,
    has_current_week_mix,
    load_weekly_mix_runs,
    record_weekly_mix_run,
)


class FakeSpotify:
    def __init__(self, pages):
        self.pages = pages
        self.next_calls = 0

    def current_user_playlists(self, limit=50):
        return self.pages[0]

    def next(self, page):
        self.next_calls += 1
        next_index = page["next"]
        return self.pages[next_index]


def test_build_weekly_mix_identity_includes_iso_year():
    identity = build_weekly_mix_identity(
        datetime.datetime(2026, 4, 21, 9, 2, tzinfo=datetime.timezone.utc)
    )

    assert identity.key == "2026-W17"
    assert identity.playlist_name == "Weekly Mix 17"
    assert identity.description_marker == f"{CURRENT_MARKER_PREFIX} 2026-W17"


def test_recorded_state_marks_current_week_done(tmp_path):
    state_path = tmp_path / "weekly_mix_runs.json"
    identity = build_weekly_mix_identity(datetime.datetime(2026, 4, 21))

    record_weekly_mix_run(
        state_path=state_path,
        identity=identity,
        playlist_id="playlist-123",
        playlist_url="https://open.spotify.com/playlist/playlist-123",
    )

    state = load_weekly_mix_runs(state_path)
    assert state["2026-W17"]["playlist_id"] == "playlist-123"
    assert has_current_week_mix(
        sp=FakeSpotify([]),
        user_id="user-1",
        identity=identity,
        state=state,
    )


def test_description_marker_fallback_detects_existing_playlist():
    identity = build_weekly_mix_identity(datetime.datetime(2026, 4, 21))
    sp = FakeSpotify(
        [
            {
                "items": [
                    {
                        "id": "old-2025",
                        "name": "Weekly Mix 17",
                        "description": "Generated for ISO week 2025-W17",
                        "owner": {"id": "user-1"},
                    },
                    {
                        "id": "current",
                        "name": "Weekly Mix 17",
                        "description": "Generated for ISO week 2026-W17",
                        "owner": {"id": "user-1"},
                    },
                ],
                "next": None,
            }
        ]
    )

    found_playlist = find_current_week_playlist(
        sp=sp,
        user_id="user-1",
        identity=identity,
        state={},
    )
    assert found_playlist["id"] == "current"
    assert has_current_week_mix(sp=sp, user_id="user-1", identity=identity, state={})
