#!/usr/bin/env python
"""Seed the weekly-mix dedup state with an already-existing playlist.

Run this once after manually cleaning up duplicate "Weekly Mix" playlists, so
the next scheduled run recognizes the surviving playlist instead of creating
yet another one.

Examples:
    # Seed the current ISO week with the playlist you kept
    python scripts/seed_weekly_mix_state.py 37i9dQZF1DX...

    # Seed a specific ISO week and store its URL
    python scripts/seed_weekly_mix_state.py 37i9dQZF1DX... \
        --week 2026-W24 \
        --url https://open.spotify.com/playlist/37i9dQZF1DX...

The state file location honors WEEKLY_MIX_STATE_PATH (see README); in Docker
make sure this runs against the same /app/state volume the scheduler uses.
"""

import argparse
import datetime
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from weekly_mix_state import (  # noqa: E402
    STATE_PATH,
    build_weekly_mix_identity,
    load_weekly_mix_runs,
    record_weekly_mix_run,
)


def _iso_week_to_datetime(week: str) -> datetime.datetime:
    """Convert an ISO week key like '2026-W24' to a datetime in that week."""
    match = re.fullmatch(r"(\d{4})-W(\d{1,2})", week.strip())
    if not match:
        raise argparse.ArgumentTypeError(
            f"Expected an ISO week like 2026-W24, got: {week!r}"
        )
    iso_year, iso_week = int(match.group(1)), int(match.group(2))
    # Day 1 (Monday) of the ISO week.
    return datetime.datetime.fromisocalendar(iso_year, iso_week, 1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("playlist_id", help="Spotify playlist ID to keep")
    parser.add_argument(
        "--week",
        type=_iso_week_to_datetime,
        default=None,
        help="ISO week to seed (e.g. 2026-W24). Defaults to the current week.",
    )
    parser.add_argument(
        "--url", default=None, help="Optional Spotify playlist URL to record"
    )
    args = parser.parse_args()

    identity = build_weekly_mix_identity(args.week)

    existing = load_weekly_mix_runs(STATE_PATH).get(identity.key)
    if existing:
        print(
            f"State for {identity.key} already points at "
            f"{existing.get('playlist_id')}; overwriting with {args.playlist_id}."
        )

    record_weekly_mix_run(
        state_path=STATE_PATH,
        identity=identity,
        playlist_id=args.playlist_id,
        playlist_url=args.url,
    )
    print(f"Recorded {identity.key} -> {args.playlist_id} in {STATE_PATH}")


if __name__ == "__main__":
    main()
