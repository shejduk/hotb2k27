import os
import time
import threading

import neurhon.analysis.stream_analyzer as ls
import neurhon.scheduler.scheduler as sch
import neurhon.action.spotify.api as sp
import neurhon.server.main as server_main
from neurhon.logging.logger import log as log
from neurhon.server.config import HISTORY_PATH
from neurhon.server.history_jsonl import JsonlHistoryStore
from neurhon.server.interfaces import HistoryEntry, Track
from neurhon.server.spotify_controller import SpotifyMusicController

DEFAULT_DEVICE = "BA EXG8 009"


def run():
   app = MainApp()
   app.run()

class MainApp:
    def __init__(self):
        self.is_running = True
        self.history = JsonlHistoryStore(HISTORY_PATH)

        # jedna instancja Spotify wspólna dla schedulera i UI
        self.spotify = sp.SpotifyApi()
        self.scheduler = sch.SongScheduler(
            spotify_api=self.spotify, on_track_change=self.handle_track_change
        )
        self.music = SpotifyMusicController(self.spotify, self.scheduler)

    def handle_track_change(self, title, author, mood_label):
        """Każdy wybór schedulera ląduje w historii widocznej w UI."""
        if self.music.manual_skip_in_progress:
            return  # ręczny skip loguje już server/app.py
        mood = self.scheduler.get_mood()
        self.history.append(
            HistoryEntry(time.time(), Track(title, author), mood, f"auto: mood became {mood_label}")
        )

    def handle_eeg_data(self, features):
        self.scheduler.update_mood(features)

    def spotify_monitor_loop(self):
        while self.is_running:
            time.sleep(5)

            try:
                if self.scheduler.autopilot and self.scheduler.is_track_ending_soon():
                    log.info("Choosing next song...")
                    self.scheduler.play_next_prediction()

                    time.sleep(10)
            except Exception as e:
                log.error(f"Spotify error: {e}")

    def run(self):
        # UI startuje pierwsze: działa nawet gdy opaska się nie połączy
        ui_thread = threading.Thread(
            target=server_main.main,
            kwargs=dict(
                mood_provider=self.scheduler,
                music=self.music,
                history=self.history,
                port=8000,
                open_browser=True,
            ),
            daemon=True,
        )
        ui_thread.start()

        try:
            self.scheduler.play_next_prediction()
        except Exception as e:
            log.error(f"Could not start the first song: {e}")

        monitor_thread = threading.Thread(target=self.spotify_monitor_loop, daemon=True)
        monitor_thread.start()

        log.info("Initializing calibration. Stand still...")

        stream = ls.LiveStreamAnalyzer(
            device_name=os.getenv("BRAINACCESS_DEVICE", DEFAULT_DEVICE),
            timeframe=0.5,
            on_features=self.handle_eeg_data
        )

        try:
            stream.start_streaming()
        except KeyboardInterrupt:
            stream.kill_yourself()
        except Exception as e:
            log.error(f"EEG stream failed: {e}. UI and music keep running; Ctrl+C to quit.")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
        finally:
            self.is_running = False
