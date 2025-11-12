# %%
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import os
import random
import datetime
from collections import defaultdict

# %%

def find_name(track):
    return track['name']

def find_album_id(track):
    return track['album']['id']

def find_id(track):
    return track['id']

def find_dur(track):
    return track['duration_ms']

def find_artist_ids(track, return_artists = False):
    artists = track['artists']
    if return_artists:
        return artists

    ids = []
    for artist in artists:
        ids.append(artist['id'])

    return ids

# %%

load_dotenv()
client_id = client_id = os.getenv("SPOTIPY_CLIENT_ID")
client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")
redirect_uri = os.getenv("SPOTIPY_REDIRECT_URI")
playlistId = os.getenv("SPOTIFY_PLAYLIST_ID")
scope = "playlist-modify-public,playlist-modify-private,user-library-read"


# %%
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri=redirect_uri,
    scope=scope
))

# %%
# find ids of the albums of every album in backlog
backlog_ids = []
backlog_ids_set = set()

results = sp.playlist(playlistId)
while results:
    for item in results['tracks']['items']:
        track = item['track']
        album_id = find_album_id(track)

        if album_id in backlog_ids_set:
            continue

        backlog_ids_set.add(album_id)
        backlog_ids.append(find_album_id(track))

    try:
        if results['next']:
            results = sp.next(results)
        else:
            break
    except:
        break

# %%
# new_backlog = backlog_ids[47:]

# %%
def pick_random_track(tracks, num_tracks):
    rand_num = random.randint(0, num_tracks - 1)
    rand_track = tracks[rand_num]
    return rand_track

# %%
def pick_random_album(backlog_ids):
    rand_num = random.randint(0, len(backlog_ids) - 1)
    return sp.album_tracks(backlog_ids[rand_num])['items']

# %%
# CHANGE THESE TO YOUR PREFERENCE
max_tracks = 16
max_runtime = 60
max_artist = 2

max_runtime_ms = max_runtime * 60 * 1000
total_runtime = 0
# doesn't try to find a 15 second interlude to add to playlist if
# normal songs go over limit
times_denied = 0
new_playlist_ids = []
artist_counts = defaultdict(int)

# while len(new_playlist_ids) <= max_tracks or total_runtime <= max_runtime_ms:
while total_runtime <= max_runtime_ms:
    tracks = pick_random_album(backlog_ids)
    num_tracks = len(tracks)

    rand_track = pick_random_track(tracks, num_tracks)
    rand_track_id = rand_track['id']
    rand_track_ms = rand_track['duration_ms']
    track_artists = [artist['name'] for artist in rand_track['artists']]

    name = rand_track['name']

    if sp.current_user_saved_tracks_contains([rand_track_id])[0]:
        print(name, " is saved")
        continue

    if any(artist_counts[artist] >= max_artist for artist in track_artists):
        print(name, " has too many artists in the list")
        continue

    # if total_runtime + rand_track_ms > max_runtime_ms:
    #     print(name, ' would make playlist too long')
    #     if times_denied > 10:
    #         break
    #     times_denied += 1
    #     continue


    print(name, " made it")
    new_playlist_ids.append(rand_track_id)
    total_runtime += rand_track_ms
    for artist in track_artists:
        artist_counts[artist] += 1

# %%
user_id = sp.current_user()['id']
current_week = datetime.datetime.now().isocalendar()[1]
playlist_name = f"Weekly Mix {current_week}"
new_playlist = sp.user_playlist_create(user_id, playlist_name, public=False, description='Your Weekly Mix!')
sp.playlist_add_items(new_playlist['id'], new_playlist_ids)

# %%
playlist_name


