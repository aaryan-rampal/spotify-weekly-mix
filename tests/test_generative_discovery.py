import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from generative_discovery import (
    filter_saved_artist_matches,
    normalize_artist_name,
    resolve_spotify_artist,
    weighted_choice,
)


class FakeSpotify:
    def __init__(self, artists):
        self.artists = artists
        self.queries = []

    def search(self, q, type, limit):
        self.queries.append((q, type, limit))
        return {"artists": {"items": self.artists}}


def test_normalize_artist_name_removes_spaces_punctuation_and_case():
    assert normalize_artist_name(" The Last-Shadow Puppets! ") == "thelastshadowpuppets"
    assert normalize_artist_name("A$AP Rocky") == "aaprocky"


def test_filter_saved_artist_matches_removes_normalized_saved_names():
    candidates = [
        {"name": "The National", "match": "1"},
        {"name": "Big Thief", "match": "0.9"},
        {"name": "The-National!", "match": "0.8"},
    ]
    saved_artist_names = {"the national"}

    filtered = filter_saved_artist_matches(candidates, saved_artist_names)

    assert filtered == [{"name": "Big Thief", "match": "0.9"}]


def test_weighted_choice_uses_match_scores():
    candidates = [
        {"name": "Low", "match": "0.1"},
        {"name": "High", "match": "0.9"},
    ]

    selected = weighted_choice(candidates, random.Random(0))

    assert selected["name"] == "High"


def test_resolve_spotify_artist_prefers_exact_normalized_match():
    sp = FakeSpotify(
        [
            {"id": "wrong", "name": "The Smile Band"},
            {"id": "right", "name": "The Smile"},
        ]
    )

    artist = resolve_spotify_artist(sp, "The Smile")

    assert artist["id"] == "right"
    assert sp.queries == [('artist:"The Smile"', "artist", 10)]


def test_resolve_spotify_artist_rejects_weak_top_result():
    sp = FakeSpotify([{"id": "wrong", "name": "Smiley Smile"}])

    artist = resolve_spotify_artist(sp, "The Smile")

    assert artist is None
