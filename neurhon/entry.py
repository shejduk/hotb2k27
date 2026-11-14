import neurhon.data_aquisition.eeg.livestream as ls
import neurhon.scheduler.scheduler as sch
import time
def run():
    scheduler = sch.SongScheduler()

    mock_stream = [

        {"Valence": 0.7, "Focus": 0.4, "Energy": 0.3},
        {"Valence": 0.8, "Focus": 0.3, "Energy": 0.4},
        {"Valence": 0.7, "Focus": 0.4, "Energy": 0.35},
        
        {"Valence": 0.6, "Focus": 0.75, "Energy": 0.5},
        {"Valence": 0.5, "Focus": 0.85, "Energy": 0.4},
        {"Valence": 0.6, "Focus": 0.80, "Energy": 0.6},
        
        {"Valence": 0.3, "Focus": 0.5, "Energy": 0.8},
        {"Valence": 0.2, "Focus": 0.6, "Energy": 0.9},
        {"Valence": 0.25, "Focus": 0.5, "Energy": 0.85},
        
        {"Valence": 0.8, "Focus": 0.4, "Energy": 0.9},
        {"Valence": 0.7, "Focus": 0.5, "Energy": 0.8},
        {"Valence": 0.9, "Focus": 0.4, "Energy": 0.85},
    ]

    for i, data_point in enumerate(mock_stream):
        print(f"new mood_state")
        
        scheduler.update_mood(data_point)
        
        if (i + 1) % 3 == 0:
            scheduler.play_next_prediction()
            time.sleep(2)  
    #stream = ls.DataStreamContinuous(device_name="BA MINI 077",timeframe=0.5)
    #stream.start_streaming()
    #stream.kill_yourself()
