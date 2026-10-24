"""Find one of the user's own playlists by exact name."""

from typing import Any


def find_owned_playlist(sp: Any, name: str, user_id: str) -> dict[str, Any] | None:
    """The user's own playlist with this exact name, or None.

    Walks the user's library page by page and stops at the first match. Playlists followed from
    other users are ignored even when they share the name.

    Spotify's playlist search is deliberately not used here: its results include null entries,
    which crashed the rolling playlists every night from at least August 2026. Null entries are
    skipped here as well, in case the library listing ever returns them.
    """
    page = sp.current_user_playlists(limit=50)
    while page:
        for playlist in page.get("items") or []:
            if not playlist or playlist.get("name") != name:
                continue
            if (playlist.get("owner") or {}).get("id") == user_id:
                return playlist
        page = sp.next(page) if page.get("next") else None
    return None
