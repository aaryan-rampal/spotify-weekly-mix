# Generative Weekly Mix Design

**Date:** 2026-02-09  
**Topic:** Add AI-driven generative track discovery to weekly mix playlist generator

## Overview

Enhance the existing weekly mix generator to intelligently discover new tracks based on user's recent listening patterns. The hybrid system combines 5-10% generative tracks (configurable) with the existing random selection approach, using a rolling 3-month window of liked songs to inform discovery.

## High-Level Architecture

**Modular Extension Approach**
- Keep existing `make-weekly-mix-saved-artists.py` mostly intact
- Add new `generative_discovery.py` module for AI-driven track discovery
- Main script periodically requests tracks from generative module based on configured ratio

### Components

1. **Existing Script** (`make-weekly-mix-saved-artists.py`)
   - Minimal modifications for generative integration
   - New configurable parameters: `generative_ratio` (~0.08), `generative_attempts_max`
   - Modified main loop to alternate between random and generative selection
   - Preserves all existing constraints (max_runtime, max_artist, deduplication)

2. **New Module** (`generative_discovery.py`)
   - Analyzes recent liked songs (3-month rolling window)
   - Discovers new tracks using two complementary strategies
   - Returns tracks with full observability metadata

## Generative Discovery Module

### Module Interface

**`initialize_discovery(sp: SpotifyOAuth, logger, months_window: int = 3) -> dict`**
- Entry point called once at script start
- Fetches recent liked songs from last 3 months
- Analyzes and categorizes by genre and artist frequency
- Returns discovery state dictionary:
  - `top_genres`: List of dicts with genre and count (ranked by occurrence)
  - `artists`: Dict mapping artist_id -> weight based on frequency
  - `genre_candidates`: Cached pool of genre-based track candidates
  - `artist_candidates`: Cached pool of artist-based track candidates
  - `strategy_toggle`: Boolean flag (True = genre-based, False = artist-based)

**`discover_track(sp: SpotifyOAuth, discovery_state: dict, logger, saved_tracks_set: set, artist_counts: dict, max_artist: int) -> dict or None`**
- Called during main loop for generative tracks
- Alternates between genre-based and artist-based discovery (round-robin)
- Returns dict with:
  ```python
  {
    "track": {
      "id": "...",
      "name": "...",
      "artist": "...",
      "duration_ms": 12345
    },
    "discovery_reason": {
      "strategy": "genre-based" or "artist-based",
      "details": {
        "genre-based": {
          "seed_genres": ["rock", "alternative"],
          "spotify_params": {...}
        },
        "artist-based": {
          "source_artist": "Arctic Monkeys",
          "related_artist": "The Last Shadow Puppets",
          "reason": "User liked 3 Arctic Monkeys tracks recently"
        }
      }
    }
  }
  ```
- Updates discovery_state with new candidates if cache exhausted
- Returns None if no suitable track found (triggers random fallback)

### Internal Functions

**`fetch_recent_liked_tracks(sp, logger, months_window: int) -> list`**
- Uses `sp.current_user_saved_tracks(limit=50, after=timestamp)` with pagination
- Filters to tracks within specified time window
- Handles rate limits with retry logic

**`analyze_genres(tracks: list, logger) -> list`**
- Extracts unique genres from recent liked tracks
- Ranks by occurrence count
- Returns top 3-5 genres
- Handles missing genre data gracefully

**`analyze_artists(tracks: list, logger) -> dict`**
- Categorizes artists by frequency in recent likes
- Returns dict mapping artist_id -> weight (higher = more liked recently)
- Prioritizes artists with >1 occurrence in recent window

**`genre_based_discovery(sp, discovery_state, logger, saved_tracks_set, max_artist) -> dict or None`**
- Takes top 3-5 genres as seed parameters
- Uses `sp.recommendations(seed_genres=[...])` API call
- Retrieves ~20 candidate tracks, filters out already saved
- Randomly selects from candidates
- Respects artist count constraints
- Caches 20 tracks per genre seed

**`artist_based_discovery(sp, discovery_state, logger, saved_tracks_set, artist_counts, max_artist) -> dict or None`**
- Takes high-frequency artists from recent likes
- Uses `sp.artist_related_artists(artist_id)` to find similar artists
- Scans related artists' discographies for tracks
- Filters out tracks in library and artists at max_artist limit
- Randomly selects from candidates
- Caches 20 tracks per top artist

### Discovery Strategy: Round-Robin

The module alternates between two approaches:

1. **Genre-based phase**
   - Seeds: Your top 3-5 genres from recent likes
   - Uses Spotify recommendations API with genre parameters
   - Discovers tracks within those genres you might enjoy

2. **Artist-based phase**
   - Seeds: Artists you've liked multiple times recently
   - Uses Spotify's artist similarity algorithm
   - Discovers tracks from similar artists

Each call toggles a `strategy_toggle` flag, ensuring variety in discovery.

## Observability

When a generative track is added, logs include discovery context:

**Genre-based:**
```
✓ "Do I Wanna Know?" by Arctic Monkeys made it to the playlist! 
  [GENRE-BASED: Discovered via rock/alternative/indie seeds]
```

**Artist-based:**
```
✓ "The Dream Synopsis" by The Last Shadow Puppets made it to the playlist!
  [ARTIST-BASED: Similar to Arctic Monkeys, which you've liked 3 times]
```

Final statistics include breakdown of generative vs random tracks and discovery strategy distribution.

## Main Script Integration

### Configuration Parameters (added after line 192)
```python
generative_ratio = 0.08  # 8% of tracks will be generative
generative_attempts_max = 10  # Max tries before falling back to random
```

### Initialization (added after line 114)
```python
from generative_discovery import initialize_discovery, discover_track

logger.info("Initializing generative discovery...")
discovery_state = initialize_discovery(sp, logger, months_window=3)
logger.info(f"Discovery initialized - {len(discovery_state['top_genres'])} top genres, {len(discovery_state['artists'])} artists analyzed")
```

### Modified Main Loop (around line 207)
```python
import math

# Calculate number of generative tracks needed
total_generative_needed = math.ceil(max_tracks * generative_ratio)
generative_tracks_found = 0

while (...existing loop conditions...):
    attempts += 1
    
    # Determine if we need a generative track
    needs_generative = (
        generative_tracks_found < total_generative_needed and
        (attempts % math.ceil(max_attempts / total_generative_needed) == 0)
    )
    
    if needs_generative:
        result = discover_track(sp, discovery_state, logger, saved_tracks_set, artist_counts, max_artist)
        if result:
            # Add track with discovery reason logging
            # ... (log with strategy info)
            generative_tracks_found += 1
        else:
            # Fall back to random selection
            artist = pick_random_artist(saved_artists)
            rand_track = pick_random_track_from_artist(artist['id'])
    else:
        # Use existing random selection logic
        artist = pick_random_artist(saved_artists)
        rand_track = pick_random_track_from_artist(artist['id'])
    
    # Continue with existing validation (artist count, runtime, etc.)
```

The integration preserves all existing constraints:
- max_tracks
- max_runtime
- max_artist (generative tracks also respect this)
- Deduplication against saved_tracks_set

## Error Handling

**Spotify API failures:**
- Rate limits: Retry logic with exponential backoff
- Recommendations API failure: Log error, return None (random fallback)
- Related artists failure: Try next artist in frequency list
- Partial results: Continue with available data, log warning

**Data quality issues:**
- Insufficient recent likes (< 10): Fall back to last 100 all-time liked tracks
- Missing genre data: Exclude genres from ranking rather than failing
- No related artists: Skip artist, move to next in list

**Cache depletion:**
- Each strategy maintains ~20 candidate tracks
- Refetch when pool has < 3 candidates
- After 3 consecutive failed refetch attempts, return None

**Integration edge cases:**
- `discover_track()` returns None → Automatic random fallback
- Track already in playlist → Discovery module checks both saved_tracks_set and artist_counts
- Exceeds max_runtime → Generative tracks respect same runtime constraints

## Performance and API Efficiency

**Caching:**
- Genre candidates: Cache 20 tracks per genre seed, refresh when < 3 remaining
- Artist candidates: Cache 20 tracks per high-priority artist, refresh when depleted
- Discovery state: All analyses computed once at initialization

**API call optimization:**
- Recent likes: Uses `after` timestamp parameter to fetch only last 3 months
- Genre recommendations: One API call per 20 track batch
- Artist discovery: Batch related artists lookup (3-5 high-priority artists in parallel)

**Execution impact:**
- Initialization: +1-2 seconds for recent likes fetch and analysis
- Per generative track: +50-100ms (cache hit) or +200-500ms (cache miss/refill)
- Overall: ~10-15% increase in total execution time with 8% generative ratio

## Files to Create/Modify

**New file:**
- `generative_discovery.py` - Complete generative discovery module (~350-400 lines)

**Modified file:**
- `make-weekly-mix-saved-artists.py` - Integration changes (~40 lines)

## Success Criteria

1. Playlist generation completes successfully with ~5-10% generative tracks
2. Discovery reasons are clearly logged for each generative track
3. All existing constraints (max_tracks, max_runtime, max_artist) are still honored
4. Generative tracks are not duplicates of already saved tracks
5. Artist distribution remains balanced (generative doesn't overload one artist)
6. Playlist runtime stays within configured limits
7. Performance impact is minimal (< 15% increase in execution time)

## Notes

- Manual testing/validation approach (no automated tests)
- Generative discovery uses local heuristics only (no external AI APIs)
- 3-month rolling window for recent likes
- Round-robin strategy alternation for variety
- Fallback to random selection ensures playlist always completes
