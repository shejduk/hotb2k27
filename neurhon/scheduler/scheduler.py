import neurhon.action.spotify.api as sp
import neurhon.data_aquisition.music.api as lfmp
from neurhon.logging.logger import log as log
from collections import deque
from neurhon.server.interfaces import Mood
import random
import time
from threading import Lock

class SongScheduler:
    def __init__(self, spotify_api=None, on_track_change=None):

        self._spotify_api = spotify_api or sp.SpotifyApi()
        self._lastfm_api =  lfmp.LastFMApi()
        self.on_track_change = on_track_change
        self.autopilot = True
        self._song_history = deque(maxlen=50)
        self._mood_history = []

        self._mood_tags = {
            "focused": ["study", "instrumental", "ambient", "lo-fi"],
            "relaxed": ["chill", "calm", "peaceful", "downtempo"],
            "energetic": ["upbeat", "electronic", "dance"],
            "stressed": ["meditation", "soothing", "acoustic"],
            "sad": ["melancholy", "sad"],
            "ambient": ["ambient"]
        }
        self._mutex = Lock()
        self._played_uris = deque(maxlen=50)  # URI ostatnio granych utworów (Spotify)
        self.last_picked = None  # (title, author) ostatnio wybranego utworu, dla optymistycznego UI
        self._lastfm_api.prewarm(list(self._mood_tags.values()), 200)


    def update_mood(self, mood_metrics: dict):
        with self._mutex:
            self._mood_history.append(mood_metrics)

            if len(self._mood_history) > 100:
                self._mood_history.pop(0)
        pass

    def skip_current_song(self):
        self.play_next_prediction()

    def play_next_prediction(self):
        self.last_picked = None  # ustawiane dopiero, gdy utwór faktycznie zlecono do odtworzenia
        target_mood = self._calculate_target_mood()
        log.info(f"Target mood established as: {target_mood}")
        target_tags = self._mood_tags.get(target_mood, [target_mood])
        
        started = time.perf_counter()
        candidates = self._lastfm_api.get_songs_based_on_tag(num_songs=200, tag_list=target_tags)
        log.info(f"[latency] candidates {time.perf_counter() - started:.2f}s")
        if not candidates:
            log.warning(f"No LastFM candidates for tags {target_tags}")
            return
        random.shuffle(candidates)

        if not self._pick_and_play(candidates, target_mood, avoid_recent=True):
            log.warning("No fresh playable candidate! Clearing history and retrying once.")
            self._song_history.clear()
            self._played_uris.clear()
            if not self._pick_and_play(candidates, target_mood, avoid_recent=False):
                log.error("Scheduler could not find any track Spotify can play")

    MAX_RESOLVE_TRIES = 8

    def _pick_and_play(self, candidates, target_mood, avoid_recent):
        recent_titles = {song["title"].lower() for song in self._song_history} if avoid_recent else set()
        current_uri = self._spotify_api.current_uri()
        tries = 0
        for track in candidates:
            title = track.get_title()
            author = track.get_artist().name
            if title.lower() in recent_titles:
                continue
            if tries >= self.MAX_RESOLVE_TRIES:
                break
            tries += 1

            uri = self._spotify_api.search_for_track(title, author)
            # pusty wynik albo ten sam utwór co teraz gra => Spotify tylko zrestartowałby bieżący
            if not uri or uri == current_uri or uri in self._played_uris:
                log.info(f"Skipping candidate {title} by {author} (uri: {uri or 'not found'})")
                continue

            log.info(f"Scheduler picked fresh track: {title} by {author}")
            self._song_history.append({"title": title, "author": author, "target_mood": target_mood})
            self._played_uris.append(uri)
            self.last_picked = (title, author)
            self._spotify_api.play_track_from_id(uri)
            self._notify_track(title, author, target_mood)
            return True
        return False

    def _notify_track(self, title, author, mood_label):
        if self.on_track_change:
            try:
                self.on_track_change(title, author, mood_label)
            except Exception as e:
                log.error(f"on_track_change failed: {e}")

    def _calculate_target_mood(self):
        if not self._mood_history:
            log.warning("No mood data yet, defaulting to 'relaxed'")
            return "relaxed"
        
        with self._mutex:
            recent = self._mood_history[-3:]
        
        v = sum(m.get('valence', 0.5) for m in recent) / len(recent)
        f = sum(m.get('focus', 0.5) for m in recent) / len(recent)
        e = sum(m.get('energy', 0.5) for m in recent) / len(recent)

        log.debug(f"Averaged metrics - Valence: {v:.2f}, Focus: {f:.2f}, Energy: {e:.2f}")
        return self._get_mood_label(f, v, e)
    
    def _get_mood_label(self, f,v,e):
            if f >= 0.65:
                return "focused"
        
            if e > 0.55:  
                if v >= 0.5:
                    return "energetic"  
                else:
                    return "stressed"   
            else:         
                if v >= 0.5:
                    return "relaxed"    
                else:
                    return "sad"

    def is_track_ending_soon(self):
        playback = self._spotify_api.current_playback()
        if playback is None:
            return False
                
        if not playback.get('is_playing'):
            return False

        item = playback.get('item')
        if item is None:
            return False

        progress_ms = playback.get('progress_ms', 0)
        duration_ms = item.get('duration_ms', 0)

        time_left_ms = duration_ms - progress_ms

        return time_left_ms <= (2 * 1000)

    def get_mood(self):
        with self._mutex:
            last = self._mood_history[-1] if self._mood_history else None
        if last is None:
            return Mood("calibrating", {}, time.time())

        v, f, e = last.get("valence", 0.5), last.get("focus", 0.5), last.get("energy", 0.5)
        scores = {"valence": v, "focus": f, "energy": e}
        return Mood(self._get_mood_label(f, v, e), scores, time.time())
