import neurhon.data_aquisition.livestream as sa
def run():
    stream = sa.DataStreamContinuous(device_name="BA MINI 077",timeframe=0.5)
    stream.start_streaming()
    stream.kill_yourself()
