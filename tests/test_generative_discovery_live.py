import os
import sys
from pathlib import Path

import pytest
import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyClientCredentials

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from generative_discovery import (
    discover_similar_spotify_artist,
    fetch_similar_artists,
    filter_saved_artist_matches,
    resolve_spotify_artist,
)


load_dotenv()


def require_lastfm_key():
    api_key = os.getenv("LASTFM_API_KEY")
    if not api_key:
        pytest.skip("LASTFM_API_KEY is not set")
    return api_key


def require_spotify_client():
    client_id = os.getenv("SPOTIPY_CLIENT_ID")
    client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")
    if not client_id or not client_secret:
        pytest.skip("SPOTIPY_CLIENT_ID/SPOTIPY_CLIENT_SECRET are not set")

    return spotipy.Spotify(
        auth_manager=SpotifyClientCredentials(
            client_id=client_id,
            client_secret=client_secret,
        )
    )


class TestLogger:
    def debug(self, message):
        self.last_debug = message


@pytest.mark.live
def test_lastfm_artist_getsimilar_returns_scored_artists():
    api_key = require_lastfm_key()

    artists = fetch_similar_artists("Radiohead", api_key, limit=10)

    assert artists
    assert all("name" in artist for artist in artists)
    assert all("match" in artist for artist in artists)
    assert any(float(artist["match"]) > 0 for artist in artists)


@pytest.mark.live
def test_live_saved_artist_filter_removes_lastfm_candidate_by_normalized_name():
    api_key = require_lastfm_key()
    artists = fetch_similar_artists("Radiohead", api_key, limit=10)
    saved_artist_names = {artists[0]["name"]}

    filtered = filter_saved_artist_matches(artists, saved_artist_names)

    assert artists[0]["name"] not in {artist["name"] for artist in filtered}


@pytest.mark.live
def test_spotify_artist_resolution_works_for_real_artist():
    sp = require_spotify_client()

    artist = resolve_spotify_artist(sp, "Radiohead")

    assert artist is not None
    assert artist["id"]
    assert artist["name"].lower() == "radiohead"


@pytest.mark.live
def test_live_lastfm_to_spotify_similar_artist_pipeline():
    api_key = require_lastfm_key()
    sp = require_spotify_client()

    artist = discover_similar_spotify_artist(
        sp=sp,
        seed_artist_name="Radiohead",
        saved_artist_names={"Radiohead"},
        lastfm_api_key=api_key,
        logger=TestLogger(),
    )

    assert artist is not None
    assert artist["id"]
    assert artist["name"]
    assert artist["name"].lower() != "radiohead"
