import random
import re
from typing import Any

import requests


LASTFM_API_URL = "https://ws.audioscrobbler.com/2.0/"


def normalize_artist_name(name: str) -> str:
    """Normalize artist names for loose duplicate detection."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def filter_saved_artist_matches(
    candidates: list[dict[str, Any]],
    saved_artist_names: set[str],
) -> list[dict[str, Any]]:
    """Remove candidates whose normalized name matches a saved artist."""
    saved_names = {normalize_artist_name(name) for name in saved_artist_names}
    return [
        candidate
        for candidate in candidates
        if normalize_artist_name(candidate.get("name", "")) not in saved_names
    ]


def weighted_choice(candidates: list[dict[str, Any]], rng: Any = random) -> dict[str, Any] | None:
    """Pick a candidate using Last.fm match scores as weights."""
    weighted_candidates = []
    total_weight = 0.0

    for candidate in candidates:
        try:
            weight = float(candidate.get("match", 0))
        except (TypeError, ValueError):
            weight = 0.0

        if weight <= 0:
            continue

        total_weight += weight
        weighted_candidates.append((candidate, total_weight))

    if not weighted_candidates:
        return rng.choice(candidates) if candidates else None

    threshold = rng.uniform(0, total_weight)
    for candidate, cumulative_weight in weighted_candidates:
        if threshold <= cumulative_weight:
            return candidate

    return weighted_candidates[-1][0]


def fetch_similar_artists(
    artist_name: str,
    api_key: str,
    limit: int = 50,
    timeout: int = 10,
) -> list[dict[str, Any]]:
    """Fetch similar artists from Last.fm for one artist name."""
    params = {
        "method": "artist.getSimilar",
        "artist": artist_name,
        "api_key": api_key,
        "format": "json",
        "autocorrect": 1,
        "limit": limit,
    }
    try:
        response = requests.get(LASTFM_API_URL, params=params, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(
            f"Last.fm artist.getSimilar request failed for {artist_name}: {e.__class__.__name__}"
        ) from None
    payload = response.json()

    error = payload.get("error")
    if error:
        message = payload.get("message", "Last.fm request failed")
        raise RuntimeError(f"Last.fm artist.getSimilar failed for {artist_name}: {message}")

    artists = payload.get("similarartists", {}).get("artist", [])
    if isinstance(artists, dict):
        return [artists]
    if not isinstance(artists, list):
        return []

    return artists


def resolve_spotify_artist(sp: Any, artist_name: str) -> dict[str, Any] | None:
    """Resolve a Last.fm artist name to a Spotify artist object."""
    results = sp.search(q=f'artist:"{artist_name}"', type="artist", limit=10)
    artists = results.get("artists", {}).get("items", [])
    if not artists:
        return None

    target_name = normalize_artist_name(artist_name)
    for artist in artists:
        if normalize_artist_name(artist.get("name", "")) == target_name:
            return artist

    top_artist = artists[0]
    top_name = normalize_artist_name(top_artist.get("name", ""))
    if target_name and top_name and (target_name in top_name or top_name in target_name):
        return top_artist

    return None


def discover_similar_spotify_artist(
    sp: Any,
    seed_artist_name: str,
    saved_artist_names: set[str],
    lastfm_api_key: str,
    logger: Any,
    rng: Any = random,
) -> dict[str, Any] | None:
    """Find one non-saved Spotify artist similar to the seed artist."""
    candidates = fetch_similar_artists(seed_artist_name, lastfm_api_key)
    candidates = filter_saved_artist_matches(candidates, saved_artist_names)
    if not candidates:
        logger.debug(f"No non-saved Last.fm similar artists for {seed_artist_name}")
        return None

    for _ in range(min(len(candidates), 10)):
        candidate = weighted_choice(candidates, rng)
        if not candidate:
            return None

        candidate_name = candidate.get("name", "")
        spotify_artist = resolve_spotify_artist(sp, candidate_name)
        if spotify_artist:
            spotify_artist["lastfm_seed_artist"] = seed_artist_name
            spotify_artist["lastfm_match"] = candidate.get("match")
            return spotify_artist

        candidates.remove(candidate)
        logger.debug(f"Could not resolve Last.fm artist to Spotify: {candidate_name}")

    return None
