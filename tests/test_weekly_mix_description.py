import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from weekly_mix_description import (
    build_playlist_description,
    format_generative_attribution,
)


def test_format_generative_attribution_includes_seed_and_percent():
    artist = {
        "name": "Portishead",
        "lastfm_seed_artist": "Radiohead",
        "lastfm_match": "0.8734",
    }

    attribution = format_generative_attribution(artist)

    assert attribution == "Portishead recommended by Radiohead (87% match)"


def test_build_playlist_description_excludes_iso_marker():
    description = build_playlist_description([])

    assert description == "Your Weekly Mix from Saved Artists!"
    assert "Generated for ISO week" not in description


def test_build_playlist_description_lists_generative_artists():
    artists = [
        {
            "name": "Portishead",
            "lastfm_seed_artist": "Radiohead",
            "lastfm_match": "0.8734",
        },
        {
            "name": "The Breeders",
            "lastfm_seed_artist": "Pixies",
            "lastfm_match": "0.71",
        },
    ]

    description = build_playlist_description(artists)

    assert "Generated for ISO week" not in description
    assert "Generative artists:" in description
    assert "Portishead recommended by Radiohead (87% match)" in description
    assert "The Breeders recommended by Pixies (71% match)" in description
