import argparse
import datetime
import os
from collections import defaultdict
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from loguru import logger
from saved_tracks_cache import get_saved_tracks

logger.remove()
logger.add(
    "logs/analyze-unfollowed-artists.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
    level="DEBUG",
)
logger.add(
    lambda msg: print(msg, end=""),
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
    level="INFO",
)

load_dotenv()

client_id = os.getenv("SPOTIPY_CLIENT_ID")
client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")
redirect_uri = os.getenv("SPOTIPY_REDIRECT_URI")
scope = "user-library-read,user-follow-read"

auth_manager = SpotifyOAuth(
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri=redirect_uri,
    scope=scope,
)
sp = spotipy.Spotify(auth_manager=auth_manager)

parser = argparse.ArgumentParser(
    description="Analyze unfollowed artists from saved tracks"
)
parser.add_argument(
    "--days",
    type=int,
    default=None,
    help="Only analyze tracks saved in the last N days",
)
args = parser.parse_args()

logger.info("Fetching saved tracks...")
tracks = get_saved_tracks(sp)

if args.days is not None:
    cutoff_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        days=args.days
    )
    tracks = [
        t
        for t in tracks
        if datetime.datetime.fromisoformat(t["added_at"].replace("Z", "+00:00"))
        >= cutoff_date
    ]
    logger.info(f"Filtered to {len(tracks)} tracks from last {args.days} days")
else:
    logger.info(f"Loaded {len(tracks)} saved tracks")

logger.info("Fetching followed artists...")
followed_artists = set()
results = sp.current_user_followed_artists(limit=50)
while results:
    for artist in results["artists"]["items"]:
        followed_artists.add(artist["name"].lower().strip())
    if results["artists"]["next"]:
        results = sp.next(results["artists"])
    else:
        break
logger.info(f"Found {len(followed_artists)} followed artists")

artist_counts = defaultdict(int)
for track in tracks:
    for artist_name in track.get("artists", []):
        artist_lower = artist_name.lower().strip()
        if artist_lower not in followed_artists:
            artist_counts[artist_lower] += 1

sorted_artists = sorted(artist_counts.items(), key=lambda x: x[1], reverse=True)

logger.info(f"\nFound {len(sorted_artists)} unfollowed artists from saved tracks")
print("\n--- Artists NOT followed (sorted by frequency) ---")
for artist, count in sorted_artists:
    print(f"{count:3d}  {artist}")
