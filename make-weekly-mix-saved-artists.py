# %%
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import os
import random
import datetime
from collections import defaultdict
from functools import lru_cache

# %%


def find_name(track):
    return track["name"]


def find_album_id(track):
    return track["album"]["id"]


def find_id(track):
    return track["id"]


def find_dur(track):
    return track["duration_ms"]


def find_artist_ids(track, return_artists=False):
    artists = track["artists"]
    if return_artists:
        return artists

    ids = []
    for artist in artists:
        ids.append(artist["id"])

    return ids


# %%

load_dotenv()
client_id = os.getenv("SPOTIPY_CLIENT_ID")
client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")
redirect_uri = os.getenv("SPOTIPY_REDIRECT_URI")
scope = (
    "playlist-modify-public,playlist-modify-private,user-library-read,user-follow-read"
)

# %%
sp = spotipy.Spotify(
    auth_manager=SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=scope,
    )
)

# %%
# Get all saved/followed artists
print("Fetching saved artists...")
saved_artists = []
results = sp.current_user_followed_artists(limit=50)

while results:
    for artist in results["artists"]["items"]:
        saved_artists.append(artist)
        print(f"Found artist: {artist['name']}")

    if results["artists"]["next"]:
        results = sp.next(results["artists"])
    else:
        break

print(f"Total saved artists found: {len(saved_artists)}")


# %%
@lru_cache(maxsize=128)
def get_artist_albums(artist_id, limit=50):
    """Get all albums for a specific artist"""
    try:
        all_albums = []
        results = sp.artist_albums(artist_id, album_type="album,single", limit=limit)

        while results:
            for album in results["items"]:
                # Check if the requested artist is actually in this album
                album_artist_ids = [artist["id"] for artist in album["artists"]]
                if artist_id in album_artist_ids:
                    all_albums.append(album)
                else:
                    # If we find an album that doesn't belong to this artist, stop here
                    print(
                        f"Found album not belonging to artist {artist_id}, stopping pagination"
                    )
                    return tuple(all_albums)

            if results["next"]:
                results = sp.next(results)
            else:
                break

        return tuple(all_albums)  # Return tuple for hashability
    except Exception as e:
        print(f"Error fetching albums for artist {artist_id}: {e}")
        return tuple()


# %%
@lru_cache(maxsize=256)
def get_album_tracks(album_id):
    """Get tracks from a specific album"""
    try:
        tracks = sp.album_tracks(album_id)
        return tuple(tracks["items"])  # Return tuple for hashability
    except Exception as e:
        print(f"Error fetching tracks for album {album_id}: {e}")
        return tuple()


# %%
def pick_random_artist(saved_artists):
    """Pick a random artist from saved artists"""
    rand_num = random.randint(0, len(saved_artists) - 1)
    return saved_artists[rand_num]


# %%
def pick_random_track_from_artist(artist_id):
    """Pick a random track from a random album of the given artist"""
    albums = get_artist_albums(artist_id)
    if not albums:
        return None

    # Pick a random album
    rand_album = random.choice(albums)
    tracks = get_album_tracks(rand_album["id"])

    if not tracks:
        return None

    # Pick a random track from the album
    rand_track = random.choice(tracks)
    return rand_track


# %%
# CHANGE THESE TO YOUR PREFERENCE
max_tracks = 16
max_runtime = 60
max_artist = 2

max_runtime_ms = max_runtime * 60 * 1000
total_runtime = 0
new_playlist_ids = []
artist_counts = defaultdict(int)
attempts = 0
max_attempts = 200  # Prevent infinite loops

print(
    f"Creating weekly mix with max {max_tracks} tracks, {max_runtime} minutes runtime, max {max_artist} tracks per artist"
)

while (
    total_runtime <= max_runtime_ms
    and len(new_playlist_ids) < max_tracks
    and attempts < max_attempts
):
    attempts += 1

    # Pick a random artist
    artist = pick_random_artist(saved_artists)
    artist_name = artist["name"]
    artist_id = artist["id"]

    # Get a random track from this artist
    rand_track = pick_random_track_from_artist(artist_id)

    if not rand_track:
        print(f"No tracks found for {artist_name}")
        continue

    rand_track_id = rand_track["id"]
    rand_track_ms = rand_track["duration_ms"]
    track_name = rand_track["name"]

    # Check if track is already saved
    try:
        if sp.current_user_saved_tracks_contains([rand_track_id])[0]:
            print(f"{track_name} by {artist_name} is already saved")
            continue
    except Exception as e:
        print(f"Error checking if track is saved: {e}")
        continue

    # Check artist count limit
    if artist_counts[artist_name] >= max_artist:
        print(f"{track_name} by {artist_name} - too many tracks by this artist already")
        continue

    # Check if adding this track would exceed runtime
    if total_runtime + rand_track_ms > max_runtime_ms:
        print(f"{track_name} by {artist_name} would make playlist too long")
        continue

    print(f"✓ {track_name} by {artist_name} made it to the playlist!")
    new_playlist_ids.append(rand_track_id)
    total_runtime += rand_track_ms
    artist_counts[artist_name] += 1

print(f"\nPlaylist created with {len(new_playlist_ids)} tracks")
print(f"Total runtime: {total_runtime / 1000 / 60:.1f} minutes")
print(f"Attempts made: {attempts}")

# %%
if new_playlist_ids:
    user_id = sp.current_user()["id"]
    current_week = datetime.datetime.now().isocalendar()[1]
    playlist_name = f"Weekly Mix {current_week}"

    print(f"Creating playlist: {playlist_name}")
    new_playlist = sp.user_playlist_create(
        user_id,
        playlist_name,
        public=False,
        description="Your Weekly Mix from Saved Artists!",
    )
    sp.playlist_add_items(new_playlist["id"], new_playlist_ids)

    print(f"Playlist '{playlist_name}' created successfully!")
    print(f"Playlist URL: {new_playlist['external_urls']['spotify']}")
else:
    print("No tracks were added to the playlist.")

# %%
# Display final artist distribution
print("\nArtist distribution in the playlist:")
for artist, count in artist_counts.items():
    if count == 0:
        continue
    print(f"{artist}: {count} track(s)")

# %%
