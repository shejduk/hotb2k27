"""MusicController oparty o prawdziwego Spotify (SpotifyApi) i SongScheduler.

UI steruje tym samym odtwarzaczem, który wybiera utwory na podstawie EEG.
"""

import threading
import time

from neurhon.logging.logger import log
from neurhon.server.interfaces import MusicController, PlaybackState, Track

CACHE_SECONDS = 1.5  # UI pyta co sekundę; nie męczymy API Spotify


class SpotifyMusicController(MusicController):
    # app.py: autopilot (zmiana utworu przy zmianie nastroju) należy do schedulera
    manages_autoplay = True

    def __init__(self, spotify_api, scheduler):
        self._api = spotify_api
        self._sp = spotify_api.client
        self._scheduler = scheduler
        self._lock = threading.Lock()
        self._cache = (0.0, None)
        self.manual_skip_in_progress = False  # entry.py nie loguje wtedy wyboru schedulera
        self._autopilot_before_wake = None

    # ---- stan ----
    @property
    def auto_enabled(self) -> bool:
        return self._scheduler.autopilot

    def set_auto(self, enabled: bool) -> None:
        self._scheduler.autopilot = enabled

    def connected(self) -> bool:
        return self._playback(force=True) is not None

    def _playback(self, force: bool = False):
        with self._lock:
            stamp, value = self._cache
            if not force and time.time() - stamp < CACHE_SECONDS:
                return value
            try:
                value = self._api.current_playback()
            except Exception as error:
                log.error(f"Spotify playback read failed: {error}")
                value = None
            self._cache = (time.time(), value)
            return value

    def _invalidate(self) -> None:
        with self._lock:
            self._cache = (0.0, None)

    def now_playing(self) -> Track | None:
        item = (self._playback() or {}).get("item")
        if not item:
            return None
        artists = item.get("artists") or [{}]
        return Track(item.get("name", ""), artists[0].get("name", ""))

    def is_playing(self) -> bool:
        return bool((self._playback() or {}).get("is_playing"))

    # ---- sterowanie ----
    def play(self) -> None:
        self._try(self._sp.start_playback)

    def pause(self) -> None:
        self._try(self._sp.pause_playback)

    def next_track(self) -> None:
        self.manual_skip_in_progress = True
        try:
            self._scheduler.skip_current_song()
        except Exception as error:
            log.error(f"Skip failed: {error}")
        finally:
            self.manual_skip_in_progress = False
            self._invalidate()

    def play_track(self, track: Track, volume: int | None = None, repeat: bool = False) -> None:
        if repeat:  # muzyka pobudzająca: scheduler nie może w tym czasie wybierać utworów
            if self._autopilot_before_wake is None:
                self._autopilot_before_wake = self._scheduler.autopilot
            self._scheduler.autopilot = False
        if volume is not None:
            self._try(self._sp.volume, volume)
        self._try(self._sp.repeat, "track" if repeat else "off")
        self._api.play_track(track.title, track.artist)
        self._invalidate()

    def capture_state(self) -> PlaybackState:
        playback = self._playback(force=True) or {}
        device = playback.get("device") or {}
        context = playback.get("context") or {}
        item = playback.get("item") or {}
        return PlaybackState(
            track=self.now_playing(),
            playing=bool(playback.get("is_playing")),
            volume=device.get("volume_percent"),
            data={
                "context_uri": context.get("uri"),
                "track_uri": item.get("uri"),
                "progress_ms": playback.get("progress_ms") or 0,
            },
        )

    def restore_state(self, state: PlaybackState, resume: bool) -> None:
        self._try(self._sp.repeat, "off")
        if state.volume is not None:
            self._try(self._sp.volume, state.volume)
        if resume and state.playing and state.data.get("track_uri"):
            # wracamy do utworu sprzed przerwy w tym samym miejscu
            self._try(
                self._sp.start_playback,
                uris=[state.data["track_uri"]],
                position_ms=state.data.get("progress_ms", 0),
            )
        else:
            self._try(self._sp.pause_playback)
        if self._autopilot_before_wake is not None:
            self._scheduler.autopilot = self._autopilot_before_wake
            self._autopilot_before_wake = None
        self._invalidate()

    @staticmethod
    def _try(call, *args, **kwargs) -> None:
        try:
            call(*args, **kwargs)
        except Exception as error:  # np. brak aktywnego urządzenia
            log.error(f"Spotify call failed: {error}")
