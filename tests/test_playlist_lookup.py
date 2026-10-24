import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from playlist_lookup import find_owned_playlist

USER = "aaryan"


def playlist(pid, name, owner=USER):
    return {"id": pid, "name": name, "owner": {"id": owner}}


class FakeSpotify:
    """Serves canned pages of the user's playlists and counts page requests."""

    def __init__(self, pages):
        self.pages = pages
        self.requests = 0

    def _page(self, index):
        self.requests += 1
        has_next = index + 1 < len(self.pages)
        return {"items": self.pages[index], "next": "more" if has_next else None, "_i": index}

    def current_user_playlists(self, limit=50):
        return self._page(0)

    def next(self, page):
        return self._page(page["_i"] + 1)


def test_finds_owned_playlist_by_exact_name():
    sp = FakeSpotify([[playlist("a", "last 3 months"), playlist("b", "last month")]])
    assert find_owned_playlist(sp, "last month", USER)["id"] == "b"


def test_skips_null_entries_instead_of_crashing():
    sp = FakeSpotify([[None, playlist("b", "last month"), None]])
    assert find_owned_playlist(sp, "last month", USER)["id"] == "b"


def test_ignores_followed_playlists_owned_by_someone_else():
    sp = FakeSpotify(
        [[playlist("theirs", "last month", owner="someone")], [playlist("mine", "last month")]]
    )
    assert find_owned_playlist(sp, "last month", USER)["id"] == "mine"


def test_walks_later_pages_and_stops_at_the_first_match():
    sp = FakeSpotify([[playlist("a", "x")], [playlist("b", "last month")], [playlist("c", "y")]])
    assert find_owned_playlist(sp, "last month", USER)["id"] == "b"
    assert sp.requests == 2


def test_returns_none_when_missing():
    sp = FakeSpotify([[playlist("a", "x")], [None]])
    assert find_owned_playlist(sp, "last month", USER) is None


def test_handles_a_page_with_no_items():
    sp = FakeSpotify([[]])
    assert find_owned_playlist(sp, "last month", USER) is None
