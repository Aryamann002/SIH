"""Silero v5 ONNX streaming inference with window-local speech evidence."""

import numpy as np

from app.core.config import settings
from app.services.spoof_detector import ModelUnavailable, load_onnx


class SileroVADWorker:
    def __init__(self, sample_rate: int = 16000, max_window_sec: float = 2.0):
        if sample_rate != 16000 or not 0 < max_window_sec <= 4:
            raise ValueError("Expected 16 kHz PCM with an evidence window up to 4 seconds")
        self.sample_rate = sample_rate
        self.max_window_samples = int(sample_rate * max_window_sec)
        self.session = None
        self.model_version = "unavailable"
        self.reset()
        try:
            self.session, digest = load_onnx(
                getattr(settings, "SILERO_MODEL_PATH", "models/silero_vad.onnx")
            )
            self.model_version = f"silero-v5.1:sha256:{digest}"
        except ModelUnavailable:
            pass

    @property
    def available(self) -> bool:
        return self.session is not None

    def reset(self):
        self.state = np.zeros((2, 1, 128), dtype=np.float32)
        self.context = np.zeros((1, 64), dtype=np.float32)
        self.pending = np.empty(0, dtype=np.float32)
        self.buffer = np.empty(0, dtype=np.float32)
        self.voiced = np.empty(0, dtype=bool)
        self.rms = 0.0

    def process_chunk(self, chunk_bytes: bytes) -> tuple[float, int, np.ndarray, bool]:
        """Accept PCM16LE; retain incomplete 512-sample frames until the next call."""
        if not isinstance(chunk_bytes, bytes) or not chunk_bytes or len(chunk_bytes) % 2:
            raise ValueError("PCM must be nonempty 16-bit little-endian samples")
        if len(chunk_bytes) > 128000:
            raise ValueError("PCM chunk exceeds four seconds")
        if self.session is None:
            raise ModelUnavailable("Silero model is unavailable")
        samples = np.frombuffer(chunk_bytes, dtype="<i2").astype(np.float32) / 32768.0
        self.pending = np.concatenate((self.pending, samples))
        frame_count = len(self.pending) // 512
        if frame_count == 0:
            return 0.0, 0, np.empty(0, dtype=np.float32), bool(np.any(np.abs(self.pending) >= 0.99))
        new_voice = []
        try:
            for offset in range(0, frame_count * 512, 512):
                frame = self.pending[offset:offset + 512].reshape(1, -1)
                values = np.concatenate((self.context, frame), axis=1)
                output, state = self.session.run(None, {
                    "input": values, "state": self.state,
                    "sr": np.array(16000, dtype=np.int64),
                })
                probability = float(np.asarray(output).item())
                if not np.isfinite(probability) or not 0 <= probability <= 1 or not np.isfinite(state).all():
                    raise ModelUnavailable("Invalid Silero output")
                self.state = state
                self.context = frame[:, -64:]
                new_voice.extend([probability >= getattr(settings, "VAD_THRESHOLD", 0.5)] * 512)
        except Exception as exc:
            self.reset()
            raise ModelUnavailable("Silero inference failed") from exc
        self.buffer = np.concatenate((self.buffer, self.pending[:frame_count * 512]))[-self.max_window_samples:]
        self.voiced = np.concatenate((self.voiced, np.asarray(new_voice, dtype=bool)))[-self.max_window_samples:]
        self.pending = self.pending[frame_count * 512:]
        if not len(self.buffer):
            return 0.0, 0, self.buffer, False
        self.rms = float(np.sqrt(np.mean(self.buffer ** 2)))
        noise = self.buffer[~self.voiced]
        # ponytail: VAD-separated RMS estimates SNR; validate against recorded noise before deployment.
        noise_rms = max(float(np.sqrt(np.mean(noise ** 2))) if len(noise) else 0.0001, 0.0001)
        speech = self.buffer[self.voiced]
        speech_rms = float(np.sqrt(np.mean(speech ** 2))) if len(speech) else 0.0
        snr_db = float(20 * np.log10(max(speech_rms, 1e-9) / noise_rms))
        speech_ms = int(np.count_nonzero(self.voiced) * 1000 / self.sample_rate)
        clipped = bool(np.any(np.abs(self.buffer) >= 0.99) or np.any(np.abs(self.pending) >= 0.99))
        return round(snr_db, 2), speech_ms, self.buffer, clipped
