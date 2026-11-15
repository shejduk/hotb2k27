import neurhon.action.spotify.api as sp
import neurhon.data_aquisition.music.api as lfmp
from neurhon.logging.logger import log as log
from collections import deque
from neurhon.server.interfaces import Mood
import random
import datetime
from threading import Lock

class SongScheduler:
    def __init__(self):
        self._spotify_api = sp.SpotifyApi() 
        self._lastfm_api =  lfmp.LastFMApi()
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


    def update_mood(self, mood_metrics: dict):
        with self._mutex:
            self._mood_history.append(mood_metrics)

            if len(self._mood_history) > 100:
                self._mood_history.pop(0)
        pass

    def skip_current_song(self):
        self.play_next_prediction()

    def play_next_prediction(self):
        target_mood = self._calculate_target_mood()
        log.info(f"Target mood established as: {target_mood}")
        target_tags = self._mood_tags.get(target_mood, [target_mood])
        
        candidates = self._lastfm_api.get_songs_based_on_tag(num_songs=200, tag_list=target_tags)
        random.shuffle(candidates)

        recent_played_titles = {song["title"].lower() for song in self._song_history}
        
        selected_track = None

        for track in candidates:
            title = track.get_title()
            author = track.get_artist().name
            
            if title.lower() not in recent_played_titles:
                selected_track = (title, author)
                break  

        if selected_track:
            title, author = selected_track
            log.info(f"Scheduler picked fresh track: {title} by {author}")
            
            self._song_history.append({
                "title": title, 
                "author": author, 
                "target_mood": target_mood
            })
            
            self._spotify_api.play_track(title, author)
        else:
            log.warning("All candidates were recently played! Clearing history to avoid infinite loop.")
            self._song_history.clear() 
            fallback_track = candidates[0]
            title = fallback_track.get_title()
            author = fallback_track.get_artist().name
            
            self._song_history.append({"title": title, "author": author, "target_mood": target_mood})
            self._spotify_api.play_track(title, author) 
        pass

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
        return self._get_mood_label(v, f, e)
    
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
        last_mood = None
        with self._mutex:
            if len(self._mood_history) > 1:
                last_mood = self._mood_history[-1]
            else:
                last_mood = {"valence" : 0, "focus" : 0, "energy" : 0}
        return Mood(self._get_mood_label(last_mood['valence'],last_mood['focus'],last_mood['energy']),last_mood,0.0)
