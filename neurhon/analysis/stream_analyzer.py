"""Real-time EEG feature extraction for emotion-aware music recommendation.

Electrode order must match the order enabled by the BrainAccess device:
Fp1, Fp2, F3, F4, F7, F8, Fz, Pz. M1 is the hardware reference and M2 is the
bias electrode; neither is an EEG feature channel in this montage.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable

import numpy as np
from mne.time_frequency import psd_array_welch
from scipy import signal

from neurhon.data_aquisition.eeg.livestream import DataStreamContinuous
from neurhon.logging.logger import log


RawMetrics = dict[str, float]
Features = dict[str, float]
MetricsCallback = Callable[[Features], None]

CHANNELS = ("Fp1", "Fp2", "F3", "F4", "F7", "F8", "Fz", "Pz")
FRONTAL_CHANNELS = ("Fp1", "Fp2", "F3", "F4", "F7", "F8", "Fz")
EPSILON = 1e-12


class LiveStreamAnalyzer(DataStreamContinuous):
    def __init__(
        self,
        device_name: str = "BA MINI 077",
        timeframe: float = 0.5,
        sampling_rate: float = 250,
        buffer_seconds: float = 5,
        calibration_windows: int = 10,
        artifact_limit_uv: float = 500,
        smoothing_windows: int = 5,
        on_features: MetricsCallback | None = None,
    ) -> None:
        super().__init__(device_name=device_name, timeframe=timeframe)
        if sampling_rate <= 0 or buffer_seconds <= 0:
            raise ValueError("sampling_rate and buffer_seconds must be positive")
        if calibration_windows < 2:
            raise ValueError("calibration_windows must be at least 2")
        if smoothing_windows < 1:
            raise ValueError("smoothing_windows must be at least 1")

        self.sampling_rate = float(sampling_rate)
        self.buffer_size = int(self.sampling_rate * buffer_seconds)
        self.data_buffer: deque[np.ndarray] = deque(maxlen=self.buffer_size)
        self.artifact_limit_uv = artifact_limit_uv
        self.on_features_callback = on_features

        self.hp_params = {"order": 2, "fc": 1.0}
        self.lp_params = {"order": 2, "fc": 30.0}
        self._filters_ready = False

        self.calibration_windows = calibration_windows
        self.calibration_complete = False
        self._calibration: dict[str, list[float]] = {
            key: [] for key in self.raw_metric_keys
        }
        self.baseline_median: RawMetrics = {}
        self.baseline_scale: RawMetrics = {}
        self._feature_history: dict[str, deque[float]] = {}
        self.smoothing_windows = smoothing_windows

    @property
    def raw_metric_keys(self) -> tuple[str, ...]:
        return (
            "valence_faa",
            "focus_pope_index",
            "pz_alpha_power",
            "frontal_beta_alpha_ratio",
            "frontal_hjorth_mobility",
        )

    def init_filters(self, channel_count: int) -> None:
        """Create persistent 1–40 Hz Butterworth filters for every channel."""

        self.b_h, self.a_h = signal.iirfilter(
            self.hp_params["order"], self.hp_params["fc"], btype="highpass",
            ftype="butter", fs=self.sampling_rate,
        )
        self.b_l, self.a_l = signal.iirfilter(
            self.lp_params["order"], self.lp_params["fc"], btype="lowpass",
            ftype="butter", fs=self.sampling_rate,
        )
        self.zi_h = np.tile(signal.lfilter_zi(self.b_h, self.a_h), (channel_count, 1))
        self.zi_l = np.tile(signal.lfilter_zi(self.b_l, self.a_l), (channel_count, 1))
        self._filters_ready = True

    def filter_chunk(self, chunk: np.ndarray) -> np.ndarray:
        """Filter one frame while retaining state from previous frames."""

        if not self._filters_ready:
            self.init_filters(chunk.shape[0])
        filtered, self.zi_h = signal.lfilter(
            self.b_h, self.a_h, chunk, axis=1, zi=self.zi_h
        )
        filtered, self.zi_l = signal.lfilter(
            self.b_l, self.a_l, filtered, axis=1, zi=self.zi_l
        )
        return filtered

    def _process_data_frame(self, data_frame: np.ndarray) -> None:

        eeg_chunk = np.asarray(data_frame[: len(CHANNELS), :], dtype=float)
        if eeg_chunk.shape[0] != len(CHANNELS):
            raise ValueError(
                f"Expected {len(CHANNELS)} EEG rows in order {CHANNELS}, "
                f"received {eeg_chunk.shape[0]}"
            )
        if not np.isfinite(eeg_chunk).all():
            log.warning("Rejected frame containing non-finite EEG values")
            return

        filtered_chunk = self.filter_chunk(eeg_chunk)
        # Re-reference to Common Average Reference across the 8 symmetric channels
        filtered_chunk = filtered_chunk - np.mean(filtered_chunk, axis=0, keepdims=True)

        log.info(f"{np.max(np.abs(filtered_chunk))}")
        if np.max(np.abs(filtered_chunk)) > self.artifact_limit_uv:
            log.warning("Rejected frame exceeding %s µV artifact limit", self.artifact_limit_uv)
            return

        self.data_buffer.extend(filtered_chunk.T)
        if len(self.data_buffer) < self.buffer_size:
            return

        raw_metrics = self.calculate_raw_metrics(np.asarray(self.data_buffer).T)
        if not self.calibration_complete:
            self.handle_calibration(raw_metrics)
            return
        self.on_features(self.to_features(raw_metrics))

    def calculate_raw_metrics(self, eeg: np.ndarray) -> RawMetrics:
        """Calculate the unnormalised EEG measurements over a buffered window."""

        powers = self._band_powers(eeg)
        alpha = powers["alpha"]
        beta = powers["beta"]
        theta = powers["theta"]
        index = {channel: position for position, channel in enumerate(CHANNELS)}
        frontal = np.array([index[channel] for channel in FRONTAL_CHANNELS])

        alpha_frontal = float(alpha[frontal].mean())
        beta_frontal = float(beta[frontal].mean())
        theta_frontal = float(theta[frontal].mean())
        alpha_f3 = float(alpha[index["F3"]])
        alpha_f4 = float(alpha[index["F4"]])

        return {
            # Positive FAA conventionally indicates relatively greater left
            # frontal cortical activation because alpha power is inhibitory.
            "valence_faa": float(np.log(alpha_f4 + EPSILON) - np.log(alpha_f3 + EPSILON)),
            # Pope engagement index: beta / (alpha + theta), pooled frontally.
            "focus_pope_index": beta_frontal / (alpha_frontal + theta_frontal + EPSILON),
            "pz_alpha_power": float(alpha[index["Pz"]]),
            "frontal_beta_alpha_ratio": beta_frontal / (alpha_frontal + EPSILON),
            "frontal_hjorth_mobility": self.hjorth_mobility(eeg[frontal]),
        }

    def _band_powers(self, eeg: np.ndarray) -> dict[str, np.ndarray]:
        """Estimate per-channel band powers with overlapping Welch segments."""

        n_fft = min(int(self.sampling_rate * 2), eeg.shape[1])
        if n_fft < 8:
            raise ValueError("EEG window is too short for spectral analysis")
        psd, frequencies = psd_array_welch(
            eeg,
            sfreq=self.sampling_rate,
            fmin=1,
            fmax=40,
            n_fft=n_fft,
            n_overlap=min(int(self.sampling_rate), n_fft - 1),
            average="mean",
            verbose=False,
        )
        return {
            "theta": self.band_power(psd, frequencies, 4, 8),
            "alpha": self.band_power(psd, frequencies, 8, 12),
            "beta": self.band_power(psd, frequencies, 12, 30),
        }

    @staticmethod
    def band_power(psd: np.ndarray, frequencies: np.ndarray, low: float, high: float) -> np.ndarray:
        """Return mean PSD power inside a frequency band for every channel."""

        in_band = (frequencies >= low) & (frequencies <= high)
        if not np.any(in_band):
            raise ValueError(f"No PSD bins available for {low}-{high} Hz")
        return psd[:, in_band].mean(axis=1)

    def hjorth_mobility(self, eeg: np.ndarray) -> float:
        """Mean Hjorth mobility across channels, expressed in inverse seconds."""

        signal_variance = np.var(eeg, axis=1)
        derivative = np.diff(eeg, axis=1) * self.sampling_rate
        derivative_variance = np.var(derivative, axis=1)
        mobility = np.sqrt(derivative_variance / (signal_variance + EPSILON))
        return float(mobility.mean())

    def handle_calibration(self, raw_metrics: RawMetrics) -> None:
        """Build robust per-user baselines before emitting recommendation features."""

        for key, value in raw_metrics.items():
            self._calibration[key].append(value)
        completed_windows = len(self._calibration["valence_faa"])
        if completed_windows < self.calibration_windows:
            log.info("EEG calibration: %s/%s", completed_windows, self.calibration_windows)
            return

        self.baseline_median = {
            key: float(np.median(values)) for key, values in self._calibration.items()
        }
        # MAD is robust to a single noisy calibration window. Its 1.4826 factor
        # puts it on the same scale as a standard deviation for normal data.
        self.baseline_scale = {
            key: max(float(np.median(np.abs(np.asarray(values) - self.baseline_median[key]))) * 1.4826, 1e-6)
            for key, values in self._calibration.items()
        }
        self.calibration_complete = True
        log.info("EEG calibration complete")
        log.info(f"EEG calibration: {self.baseline_median}, {self.baseline_scale}")

    def to_features(self, raw_metrics: RawMetrics) -> Features:
        """Normalise raw measures to the user baseline and derive energy score."""

        z_scores = {
            key: (value - self.baseline_median[key]) / self.baseline_scale[key]
            for key, value in raw_metrics.items()
        }
        # Lower posterior alpha relative to baseline is alpha suppression, hence
        # negating its z-score makes a larger value correspond to more energy.
        posterior_alpha_suppression = -z_scores["pz_alpha_power"]
        energy = float(np.mean((
            posterior_alpha_suppression,
            z_scores["frontal_beta_alpha_ratio"],
            z_scores["frontal_hjorth_mobility"],
        )))
        features = {
            #"valence_faa": raw_metrics["valence_faa"],
            "valence_faa_z": z_scores["valence_faa"],
            #"focus_pope_index": raw_metrics["focus_pope_index"],
            "focus_pope_z": z_scores["focus_pope_index"],
            #"energy_pz_alpha_suppression_z": posterior_alpha_suppression,
            #"energy_frontal_beta_alpha_ratio_z": z_scores["frontal_beta_alpha_ratio"],
            #"energy_hjorth_mobility_z": z_scores["frontal_hjorth_mobility"],
            "energy_score_z": energy,
        }
        log.warning(f"{features['energy_score_z']}")
        return self._smooth_features(features)

    def _smooth_features(self, features: Features) -> Features:
        """Use a short median history so a song choice is not frame-noisy."""

        for key, value in features.items():
            self._feature_history.setdefault(key, deque(maxlen=self.smoothing_windows)).append(value)
        
        smoothed = {key: float(np.median(history)) for key, history in self._feature_history.items()}
        smoothed["valence"] = float(1 / (1 + np.exp(-np.clip(smoothed["valence_faa_z"], -50, 20))))
        smoothed["focus"]   = float(1 / (1 + np.exp(-np.clip(smoothed["focus_pope_z"], -50, 20))))
        smoothed["energy"]  = float(1 / (1 + np.exp(-np.clip(smoothed["energy_score_z"], -50, 20))))
        return smoothed


    def on_features(self, features: Features) -> None:
        """Override this hook or provide ``on_features`` to consume features."""

        if self.on_features_callback is None:
            log.error("EEG recommendation features: %s", features)
        else:
            self.on_features_callback(features)
