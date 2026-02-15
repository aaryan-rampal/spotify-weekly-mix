# AGENTS.md

This file provides guidelines for agentic coding assistants working in this repository.

## Overview

This is a Spotify playlist automation project using Python and the Spotipy library. The repo generates weekly mix playlists and rolling window playlists from saved artists and tracks.

## Build/Lint/Test Commands

```bash
# Type checking
mypy src/

# Linting and formatting
ruff check src/
ruff format src/

# Run individual scripts
python src/make_weekly_mix.py
python src/make_rolling.py
python src/populate_saved_songs.py

# Run all playlists via scheduler
./scripts/make_all_playlists.sh
```

**Note:** This repository does not have automated tests. Scripts are tested manually by examining log output in `logs/` directory.

## Project Structure

```
src/                    # Python scripts
  make_weekly_mix.py   # Weekly mix generation
  make_rolling.py      # Rolling window playlists (1mo, 3mo)
  populate_saved_songs.py  # Fetch saved tracks to CSV
  generative_discovery.py  # Generative music discovery module (in progress)
scripts/                # Shell scripts
  make_all_playlists.sh    # Master scheduler script
data/                   # Data files
  saved_songs.csv         # Exported saved tracks
logs/                   # Log files (gitignored)
  weekly-mix.log
  rolling.log
  saved-songs.log
  scheduler.log
```

## Code Style Guidelines

### Imports

- Standard library imports first, then third-party imports
- No docstring comments between import groups
- Use `from functools import lru_cache` for memoization
- Import inside functions for local-only dependencies (e.g., `import time` in functions that need it)

```python
import os
import random
import datetime
from collections import defaultdict
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from loguru import logger
```

### File Organization

- Use IPython-style section separators: `# %%` between logical sections
- Setup logging configuration early (after imports, before load_dotenv())
- Load environment variables after logging setup
- Authenticate with Spotify after environment loading

### Logging

- **Primary logger**: `loguru` for all new code
- **Format**: `{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}`
- **Log levels**: DEBUG for detailed flow, INFO for operations, WARNING for non-critical issues, ERROR for failures
- **Dual output**: File handler (DEBUG) + console handler (INFO) via lambda

```python
logger.remove()
logger.add("logs/script-name.log", format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}", level="DEBUG")
logger.add(lambda msg: print(msg, end=""), format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}", level="INFO")
```

- **populate_saved_songs.py exception**: Uses standard `logging` module - follow that pattern for that file only

### Naming Conventions

- **Files**: Snake_case (e.g., `make_weekly_mix.py`, `generative_discovery.py`)
- **Functions**: Snake_case, descriptive names (e.g., `find_name`, `fetch_recent_liked_tracks`)
- **Variables**: Snake_case
- **Constants**: UPPER_SNAKE_CASE (not consistently used, prefer explicit constants)
- **Classes**: CamelCase (e.g., `BatchAction`)

### Spotify API Patterns

- Use `sp.current_user_*()` methods for user data
- **Pagination**: Always handle `results["next"]` with `while` loops
- **Rate limiting**: Implement retry logic with exponential backoff for 429 errors

```python
results = sp.current_user_saved_tracks(limit=50)
while results:
    for item in results["items"]:
        # Process items
    if results["next"]:
        results = sp.next(results)
    else:
        break
```

- **Retry pattern for rate limits**:

```python
def fetch_with_retry(sp, api_call, max_retries=5, initial_delay=1, max_delay=30):
    retry_delay = initial_delay
    for attempt in range(max_retries):
        try:
            return api_call()
        except Exception as e:
            http_status = getattr(e, "http_status", None) or getattr(e, "status", None)
            if http_status == 429 and attempt < max_retries - 1:
                logger.warning(f"Rate limited, retrying in {retry_delay}s")
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_delay)
            else:
                logger.error(f"Error: {e}")
                raise
    return None
```

### Error Handling

- Use try-except blocks around API calls
- Log errors with context: `logger.error(f"Failed to X: {e}")`
- Return empty containers (None, [], {}) on non-critical failures
- Re-raise critical errors after logging

### Data Structures

- Use **lists** for track collections
- Use **sets** for deduplication (e.g., `saved_tracks_set`)
- Use **dicts** for lookups and mappings
- Use **lru_cache** decorator for expensive function calls

### Configuration

- Load with `python-dotenv`: `load_dotenv()`
- Required env vars: `SPOTIPY_CLIENT_ID`, `SPOTIPY_CLIENT_SECRET`, `SPOTIPY_REDIRECT_URI`
- Provide defaults where appropriate (e.g., redirect URI)

### Type Hints

- Not consistently used across codebase
- Add type hints for function signatures when adding new complex functions

### Comments

- Add docstrings for module-level functions (e.g., `"""Entry point called once at script start."""`)
- No inline comments for obvious operations
- Use `# %%` section separators, not blank lines

### File Paths

- Use absolute imports from `src/`: imports are relative to repository root
- For data files in `data/`, use: `Path(__file__).parent.parent / "data" / "filename"`
- For log files in `logs/`, use: `"logs/filename.log"` (relative from root when script runs from repo root)

### Generative Discovery Module (in progress)

- Located in `src/generative_discovery.py`
- Export functions: `initialize_discovery(sp, logger, months_window)`, `discover_track(sp, discovery_state, logger, saved_tracks_set, artist_counts, max_artist)`
- Internal functions: `fetch_recent_liked_tracks`, `analyze_genres`, `analyze_artists`, `genre_based_discovery`, `artist_based_discovery`
- Returns track dict with `discovery_reason` field when generative track found, None otherwise

## Environment Setup

1. Create `.env` file with Spotify credentials (gitignored)
2. Ensure Python 3.12+ with spotipy, python-dotenv, loguru, pathlib packages
3. Launch agent plist uses absolute paths - update if moving scripts

## Git Workflow

- Use Beads issue tracker for task tracking (`bd` commands)
- Follow conventional commits: `feat:`, `fix:`, `refactor:`, etc.
- Reference Beads issue IDs in commit messages (e.g., `feat: add feature (spotify-abc)`)
- Commit related changes together (scripts + documentation + issues)
