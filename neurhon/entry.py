import neurhon.analysis.stream_analyzer as ls
import neurhon.scheduler.scheduler as sch
import time
def run():
    stream = ls.LiveStreamAnalyzer(device_name="BA EXG8 009",timeframe=0.5)
    stream.start_streaming()
    stream.kill_yourself()
