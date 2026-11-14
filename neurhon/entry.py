import neurhon.data_aquisition.eeg.livestream as ls
from neurhon.logging.logger import log as log
def run():
    stream = ls.DataStreamContinuous(device_name="BA MINI 077",timeframe=0.5)
    stream.start_streaming()
    stream.kill_yourself()
