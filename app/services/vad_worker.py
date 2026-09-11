import numpy as np
from typing import Tuple


class SileroVADWorker:
    """Silero VAD worker & audio pre-processing pipeline for 16kHz PCM streaming."""

    def __init__(self, sample_rate: int = 16000, max_window_sec: float = 2.0):
        self.sample_rate = sample_rate
        self.total_samples = 0
        self.speech_samples = 0
        self.max_window_samples = int(sample_rate * max_window_sec)
        self.buffer = np.array([], dtype=np.float32)
        self.noise_floor = 1e-4

    def process_chunk(self, chunk_bytes: bytes) -> Tuple[float, int, np.ndarray, bool]:
        """
        Ingest raw 16kHz 16-bit PCM chunk.
        Returns (snr_db, accumulated_speech_ms, sliding_window_pcm, is_clipped).
        """
        if not chunk_bytes:
            return 0.0, 0, np.array([], dtype=np.float32), False

        pcm_int16 = np.frombuffer(chunk_bytes, dtype=np.int16)
        if len(pcm_int16) == 0:
            return 0.0, 0, np.array([], dtype=np.float32), False

        pcm_float = pcm_int16.astype(np.float32) / 32768.0
        num_samples = len(pcm_float)
        self.total_samples += num_samples

        # Clipping detection
        is_clipped = bool(np.any(np.abs(pcm_float) >= 0.99))

        # Dynamic noise floor estimation
        rms = float(np.sqrt(np.mean(pcm_float ** 2))) + 1e-9
        if rms < self.noise_floor * 2.0:
            self.noise_floor = 0.9 * self.noise_floor + 0.1 * rms

        snr_db = float(20 * np.log10(rms / (self.noise_floor + 1e-9)))

        # VAD Energy & Zero-Crossing Rate speech activity check
        zcr = float(np.mean(np.abs(np.diff(np.signbit(pcm_float)))))
        is_speech = rms > 0.008 and zcr < 0.45

        if is_speech:
            self.speech_samples += num_samples

        # Maintain sliding window buffer
        self.buffer = np.concatenate((self.buffer, pcm_float))
        if len(self.buffer) > self.max_window_samples:
            self.buffer = self.buffer[-self.max_window_samples:]

        speech_duration_ms = int((self.speech_samples / self.sample_rate) * 1000)
        return round(snr_db, 2), speech_duration_ms, self.buffer, is_clipped

