from typing import Any


BASE_PLAYLIST_DESCRIPTION = "Your Weekly Mix from Saved Artists!"


def format_generative_attribution(artist: dict[str, Any]) -> str:
    """Format one Last.fm generative artist attribution."""
    artist_name = artist.get("name", "Unknown artist")
    seed_artist = artist.get("lastfm_seed_artist", "unknown seed")
    match = artist.get("lastfm_match")

    try:
        match_percent = round(float(match) * 100)
    except (TypeError, ValueError):
        return f"{artist_name} recommended by {seed_artist}"

    return f"{artist_name} recommended by {seed_artist} ({match_percent}% match)"


def build_playlist_description(generative_artists: list[dict[str, Any]]) -> str:
    """Build the Spotify playlist description."""
    if not generative_artists:
        return BASE_PLAYLIST_DESCRIPTION

    attributions = [
        format_generative_attribution(artist) for artist in generative_artists
    ]
    return f"{BASE_PLAYLIST_DESCRIPTION} Generative artists: {'; '.join(attributions)}"
