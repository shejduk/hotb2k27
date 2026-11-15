from neurhon.logging.logger import log as log
from dotenv import load_dotenv
import pylast
import os
import threading
import time

CACHE_TTL_SECONDS = 30 * 60  # listy utworów per tag zmieniają się rzadko

class LastFMApi:
    def __init__(self):
        try:
            load_dotenv()
            self._api_endpoint = pylast.LastFMNetwork(api_key=os.environ["LAST_FM_API_KEY"])
            log.info("Initialized LastFM API")
            self._cache = {}  # (tag, limit) -> (timestamp, [utwory])
            self._cache_lock = threading.Lock()

        except:
            log.fatal("Could not connect to LastFM database")
            raise ValueError("Configure LAstFM api please!")

    def get_songs_based_on_tag(self, num_songs : int, tag_list : list):
        result = []
        if len(tag_list) == 0:
            return []
        limit = max(1, num_songs // len(tag_list))
        for t in tag_list:
            result += self._tag_tracks(t, limit)

        return result

    def _tag_tracks(self, tag_name, limit):
        key = (tag_name, limit)
        with self._cache_lock:
            cached = self._cache.get(key)
        if cached and time.time() - cached[0] < CACHE_TTL_SECONDS:
            return list(cached[1])

        started = time.perf_counter()
        tracks = [i.item for i in self._api_endpoint.get_tag(tag_name).get_top_tracks(limit=limit)]
        log.info(f"[latency] lastfm tag '{tag_name}' {time.perf_counter() - started:.2f}s")
        with self._cache_lock:
            self._cache[key] = (time.time(), tracks)
        return list(tracks)

    def prewarm(self, tag_lists, num_songs):
        """Pobiera tagi w tle (równolegle), żeby pierwszy Next nie czekał na Last.fm."""
        def fetch(tags):
            limit = max(1, num_songs // len(tags))
            for t in tags:
                try:
                    self._tag_tracks(t, limit)
                except Exception as e:
                    log.warning(f"LastFM prewarm failed for '{t}': {e}")
        for tags in tag_lists:
            if tags:
                threading.Thread(target=fetch, args=(tags,), daemon=True).start()



