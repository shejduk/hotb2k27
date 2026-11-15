import neurhon.analysis.stream_analyzer as ls
import neurhon.scheduler.scheduler as sch
from neurhon.logging.logger import log as log
import time
import threading
import neurhon.server.main as server_main


def run():
   app = MainApp()
   app.run()

class MainApp:
    def __init__(self):
        self.scheduler = sch.SongScheduler()
        self.is_running = True
        
        self.scheduler.play_next_prediction()

    def handle_eeg_data(self, features):

        self.scheduler.update_mood(features)
        
        #log.info(f"Mood: V={features['Valence']:.2f} | F={features['Focus']:.2f} | E={features['Energy']:.2f}")

    def spotify_monitor_loop(self): 
        while self.is_running:
            time.sleep(5)
            
            try: 
                if self.scheduler.is_track_ending_soon():
                    log.info("Choosing next song...")
                    self.scheduler.play_next_prediction()
                    
                    time.sleep(10)
            except Exception as e:
                log.error(f"Spotify error: {e}")

    def run(self):
        monitor_thread = threading.Thread(target=self.spotify_monitor_loop, daemon=True)
        monitor_thread.start()
        
        ui_thread = threading.Thread(target=server_main.main,args=(self.scheduler,), daemon=True)
        ui_thread.start()
        log.info("Initializing calibration. Stand still...")
        
        stream = ls.LiveStreamAnalyzer(
            device_name="BA EXG8 009",  
            timeframe=0.5,              
            on_features=self.handle_eeg_data 
        )
        
        try:
            stream.start_streaming()
        except KeyboardInterrupt:
            stream.kill_yourself()
            self.is_running = False
