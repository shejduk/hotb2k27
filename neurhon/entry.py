import neurhon.data_aquisition.eeg.livestream as ls
import neurhon.analysis.stream_analyzer as sa
from neurhon.logging.logger import log as log
def run():
    #BA EXG8 009
    stream = sa.LiveStreamAnalyzer(device_name="BA MINI 077",timeframe=0.5)
    stream.start_streaming()
    stream.kill_yourself()
