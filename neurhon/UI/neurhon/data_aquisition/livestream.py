import time
import numpy as np
import threading
from queue import Queue
from brainaccess.utils import acquisition
from brainaccess import core
from brainaccess.core.eeg_manager import EEGManager
import brainaccess.core.eeg_channel as eeg_channel
from brainaccess.core.gain_mode import (
    GainMode,
)

class DataStreamContinuous:
    def __init__(self,device_name="BA MINI 77",timeframe=4):
        self._timeframe = timeframe
        self._device_name = device_name

        self._dataQueue = Queue()
        self._buffer_offset = 0

    def _put_callback(self, chunk: list, chunk_size : int) -> None:
        samples_left = self._samples_per_buffer - self._buffer_offset
        samples_to_roll = min(samples_left, chunk_size)

        self._queue_buffer = np.roll(self._queue_buffer, -samples_to_roll)
        for i, subchunk in enumerate(chunk):
            self._queue_buffer[i, -samples_to_roll:] = subchunk[:samples_to_roll]
        self._buffer_offset += samples_to_roll
        if self._buffer_offset == self._samples_per_buffer:
            self._dataQueue.put(self._queue_buffer.copy())
            self._buffer_offset = 0



    def _get_last_dataframe(self):
        while True:
            if self._dataQueue.empty() != True:
                result = self._dataQueue.get()
                self._dataQueue.task_done()
                return result

    def _process_data_frame(self, dataFrame):

        print("Processing data_frame, shape ", dataFrame.shape)
        print(dataFrame)

    def start_streaming(self):
        core.init()
        devices = core.scan()
        print("Found devices:", len(devices))
        print(f"Devices: {[device.name for device in devices]}")


        with EEGManager() as mgr:
            print("Connecting to {}...".format(self._device_name))
            _status = mgr.connect(self._device_name)
            if _status > 0:
                print("Failed to connect to device!")
                raise Exception("Connection to {} failed".format(self._device_name))
        
            # battery info
            print(f"battery level: {mgr.get_battery_info().level} %")
            device_features = mgr.get_device_features()
            eeg_channels_number = device_features.electrode_count()
            print("Device has {} channels".format(eeg_channels_number))

            ch_nr = 0
            for i in range(0, eeg_channels_number):
                mgr.set_channel_enabled(eeg_channel.ELECTRODE_MEASUREMENT + i, True)  # noqa
                ch_nr += 1
                mgr.set_channel_gain(
                    eeg_channel.ELECTRODE_MEASUREMENT + i, GainMode.X8
                )
            #mgr.set_channel_bias(eeg_channel.ELECTRODE_MEASUREMENT + i, True)

            eeg_enabled_nr = ch_nr

            mgr.set_channel_enabled(eeg_channel.SAMPLE_NUMBER, True)
            ch_nr += 1

            mgr.set_channel_enabled(eeg_channel.STREAMING, True)
            ch_nr += 1

            sample_rate = mgr.get_sample_frequency()
            num_samples = (int)(sample_rate * self._timeframe)
            self._samples_per_buffer = num_samples
            self._queue_buffer = np.zeros((ch_nr, num_samples))
            print(self._queue_buffer.shape)

            print("Device sample rate: {}".format(sample_rate))
            mgr.set_callback_chunk(self._put_callback)
            print("Data acquisition callback has been set")

            mgr.load_config()
            print("Manager config has been loaded")
            mgr.start_stream()
            print("Stream started, waiting for first signal window...")
            self._timer = time.time()
            while(True):
                dataFrame = self._get_last_dataframe()
                self._process_data_frame(dataFrame)


          
    def kill_yourself(self):
        core.close()
        pass



