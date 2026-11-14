import os
import re
import time 

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
from neurhon.logging.logger import log as log

class SpotifyApi:
    def __init__(self):
        load_dotenv()
       
        self._spotify_endpoint = spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=os.getenv("SPOTIFY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
        redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI"),
        scope="user-read-playback-state user-modify-playback-state user-read-currently-playing"
))
        log.info(self._spotify_endpoint.devices())
        log.info(f"Logged as: {self._spotify_endpoint.current_user()["display_name"]}")
        log.info("Spotify API initialization complete")

    def play_track_from_id(self, track_id : str):
        self._spotify_endpoint.next_track()
        self._spotify_endpoint.start_playback(uris=[track_id])
        self._spotify_endpoint.next_track()

        log.info(f"Send play request for track {track_id}")
 
    def search_for_track(self, title : str, author : str):
        log.info(f"Searching for {title} by {author}")
        title = re.sub(r"\(.*?\)|\[.*?\]", "", title).strip()
        result=self._spotify_endpoint.search(q=f"{author} {title}", limit=1, type='track')
        result = result.get("tracks",{}).get("items",{})
        if not result:
            log.info(f"Could not find {author} {title}")
            return ""
        return result[0]['uri']

    def play_track(self, title : str, author : str):
        self.play_track_from_id(self.search_for_track(title, author))



