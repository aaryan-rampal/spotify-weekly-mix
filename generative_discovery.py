def initialize_discovery(sp, logger, months_window=3):
    """Entry point called once at script start. Returns discovery state dictionary."""
    return {
        "top_genres": [],
        "artists": {},
        "genre_candidates": {},
        "artist_candidates": {},
        "strategy_toggle": True,
    }


def discover_track(
    sp, discovery_state, logger, saved_tracks_set, artist_counts, max_artist
):
    """Called during main loop for generative tracks. Returns track with discovery_reason or None."""
    return None


def fetch_recent_liked_tracks(sp, logger, months_window=3):
    """Fetches recent liked songs using pagination with time window filtering."""
    import time
    import datetime

    from datetime import timezone, timedelta

    tracks = []
    cutoff_time = datetime.datetime.now(timezone.utc).replace(
        microsecond=0
    ) - timedelta(days=months_window * 30)
    after_timestamp = cutoff_time.isoformat() + "Z"

    def fetch_with_retry(sp, api_call, max_retries=5, initial_delay=1, max_delay=30):
        retry_delay = initial_delay
        for attempt in range(max_retries):
            try:
                return api_call()
            except Exception as e:
                http_status = getattr(e, "http_status", None) or getattr(
                    e, "status", None
                )

                if http_status == 429:
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Rate limited, retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries})"
                        )
                        time.sleep(retry_delay)
                        retry_delay = min(retry_delay * 2, max_delay)
                    else:
                        logger.error(f"Max retries exceeded for rate limit")
                        raise
                else:
                    logger.error(f"Error fetching tracks: {e}")
                    raise
        return None

    try:
        results = fetch_with_retry(
            sp, lambda: sp.current_user_saved_tracks(limit=50, after=after_timestamp)
        )

        while results and results["items"]:
            for item in results["items"]:
                tracks.append(item["track"])

            results = fetch_with_retry(sp, lambda: sp.next(results))

    except Exception as e:
        logger.error(f"Error fetching tracks: {e}")
        return []

    if len(tracks) < 10:
        logger.warning(
            f"Only found {len(tracks)} tracks in last {months_window} months, may generate generic playlist"
        )

    logger.info(f"Fetched {len(tracks)} recent tracks from last {months_window} months")
    return tracks


def analyze_genres(tracks, logger):
    """Extracts and ranks genres from recent liked tracks."""
    return []


def analyze_artists(tracks, logger):
    """Categorizes artists by frequency in recent likes."""
    return {}


def genre_based_discovery(sp, discovery_state, logger, saved_tracks_set, max_artist):
    """Discovers track using Spotify recommendations API with genre seeds."""
    return None


def artist_based_discovery(
    sp, discovery_state, logger, saved_tracks_set, artist_counts, max_artist
):
    """Discovers track using artist related artists API."""
    return None
