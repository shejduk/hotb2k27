"""MusicController oparty o prawdziwego Spotify (SpotifyApi) i SongScheduler.

UI steruje tym samym odtwarzaczem, który wybiera utwory na podstawie EEG.

Latencja: stan odtwarzacza odświeża wątek w tle (now_playing/is_playing tylko czytają
pamięć, więc nie blokują pętli asyncio), a po play/pause/next stan jest ustawiany
optymistycznie, bo Spotify potrzebuje chwili, żeby odpowiedzieć nowym stanem.
"""

import threading
import time

from neurhon.logging.logger import log
from neurhon.server.interfaces import MusicController, PlaybackState, Track

POLL_SECONDS = 1.0  # jak często wątek w tle pyta Spotify o stan
OPTIMISTIC_SECONDS = 3.0  # tyle czasu ufamy własnej zmianie, zanim Spotify ją potwierdzi


class SpotifyMusicController(MusicController):
    # app.py: autopilot (zmiana utworu przy zmianie nastroju) należy do schedulera
    manages_autoplay = True

    def __init__(self, spotify_api, scheduler):
        self._api = spotify_api
        self._sp = spotify_api.client
        self._scheduler = scheduler
        self._lock = threading.Lock()  # chroni tylko pola poniżej, nigdy nie trzymany podczas HTTP
        self._playback = None  # ostatnia odpowiedź Spotify
        self._polled_at = 0.0
        self._opt_playing = None  # (wartość, do kiedy)
        self._opt_track = None  # (Track, do kiedy)
        self.manual_skip_in_progress = False  # entry.py nie loguje wtedy wyboru schedulera
        self._autopilot_before_wake = None
        self._wake = threading.Event()
        spotify_api.state_provider = self._cached_playback
        threading.Thread(target=self._poll_loop, daemon=True).start()

    # ---- odświeżanie w tle ----
    def _poll_loop(self) -> None:
        while True:
            try:
                started = time.perf_counter()
                value = self._api.current_playback()
                with self._lock:
                    self._playback = value
                    self._polled_at = time.time()
                log.debug(f"[latency] current_playback {time.perf_counter() - started:.2f}s")
            except Exception as error:
                log.error(f"Spotify playback read failed: {error}")
            self._wake.wait(POLL_SECONDS)
            self._wake.clear()

    def _cached_playback(self):
        with self._lock:
            return self._playback

    def _refresh_soon(self) -> None:
        self._wake.set()

    # ---- stan (tylko pamięć) ----
    @property
    def auto_enabled(self) -> bool:
        return self._scheduler.autopilot

    def set_auto(self, enabled: bool) -> None:
        self._scheduler.autopilot = enabled

    def connected(self) -> bool:
        with self._lock:
            return self._playback is not None

    def now_playing(self) -> Track | None:
        with self._lock:
            if self._opt_track and time.time() < self._opt_track[1]:
                return self._opt_track[0]
            item = (self._playback or {}).get("item")
        if not item:
            return None
        artists = item.get("artists") or [{}]
        return Track(item.get("name", ""), artists[0].get("name", ""))

    def is_playing(self) -> bool:
        with self._lock:
            if self._opt_playing and time.time() < self._opt_playing[1]:
                return self._opt_playing[0]
            return bool((self._playback or {}).get("is_playing"))

    def _set_optimistic(self, playing: bool | None = None, track: Track | None = None) -> None:
        until = time.time() + OPTIMISTIC_SECONDS
        with self._lock:
            if playing is not None:
                self._opt_playing = (playing, until)
            if track is not None:
                self._opt_track = (track, until)

    # ---- sterowanie ----
    def play(self) -> None:
        self._set_optimistic(playing=True)
        self._timed("play", self._sp.start_playback)
        self._refresh_soon()

    def pause(self) -> None:
        self._set_optimistic(playing=False)
        self._timed("pause", self._sp.pause_playback)
        self._refresh_soon()

    def next_track(self) -> None:
        self.manual_skip_in_progress = True
        started = time.perf_counter()
        try:
            self._scheduler.skip_current_song()
            picked = self._scheduler.last_picked
            if picked:  # tylko gdy scheduler faktycznie zlecił utwór; inaczej UI pokazałby nieprawdę
                self._set_optimistic(playing=True, track=Track(*picked))
            else:
                log.warning("Next: scheduler did not start any new track")
        except Exception as error:
            log.error(f"Skip failed: {error}")
        finally:
            self.manual_skip_in_progress = False
            log.info(f"[latency] next_track total {time.perf_counter() - started:.2f}s")
            self._refresh_soon()

    def play_track(self, track: Track, volume: int | None = None, repeat: bool = False) -> None:
        if repeat:  # muzyka pobudzająca: scheduler nie może w tym czasie wybierać utworów
            if self._autopilot_before_wake is None:
                self._autopilot_before_wake = self._scheduler.autopilot
            self._scheduler.autopilot = False
        if volume is not None:
            self._timed("volume", self._sp.volume, volume)
        self._timed("repeat", self._sp.repeat, "track" if repeat else "off")
        self._api.play_track(track.title, track.artist)
        self._set_optimistic(playing=True, track=track)
        self._refresh_soon()

    def capture_state(self) -> PlaybackState:
        with self._lock:  # z pamięci: wołane z pętli asyncio, bez sieci
            playback = self._playback or {}
            age_ms = int((time.time() - self._polled_at) * 1000) if self._polled_at else 0
        device = playback.get("device") or {}
        context = playback.get("context") or {}
        item = playback.get("item") or {}
        playing = bool(playback.get("is_playing"))
        progress = (playback.get("progress_ms") or 0) + (age_ms if playing else 0)
        return PlaybackState(
            track=self.now_playing(),
            playing=playing,
            volume=device.get("volume_percent"),
            data={
                "context_uri": context.get("uri"),
                "track_uri": item.get("uri"),
                "progress_ms": progress,
            },
        )

    def restore_state(self, state: PlaybackState, resume: bool) -> None:
        self._timed("repeat", self._sp.repeat, "off")
        if state.volume is not None:
            self._timed("volume", self._sp.volume, state.volume)
        if resume and state.playing and state.data.get("track_uri"):
            # wracamy do utworu sprzed przerwy w tym samym miejscu
            self._timed(
                "resume",
                self._sp.start_playback,
                uris=[state.data["track_uri"]],
                position_ms=state.data.get("progress_ms", 0),
            )
            self._set_optimistic(playing=True, track=state.track)
        else:
            self._timed("pause", self._sp.pause_playback)
            self._set_optimistic(playing=False)
        if self._autopilot_before_wake is not None:
            self._scheduler.autopilot = self._autopilot_before_wake
            self._autopilot_before_wake = None
        self._refresh_soon()

    @staticmethod
    def _timed(name, call, *args, **kwargs) -> None:
        started = time.perf_counter()
        try:
            call(*args, **kwargs)
        except Exception as error:  # np. brak aktywnego urządzenia
            log.error(f"Spotify {name} failed: {error}")
        log.info(f"[latency] spotify {name} {time.perf_counter() - started:.2f}s")
