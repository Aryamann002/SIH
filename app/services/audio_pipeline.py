"""One synchronous pipeline shared by upload and WebSocket routes."""

from functools import lru_cache
from hashlib import sha256
import json
import numpy as np

from app.core.config import settings
from app.services.policy_engine import DeterministicPolicyEngine
from app.services.spoof_detector import SpoofDetector
from app.services.vad_worker import SileroVADWorker


class AudioPipeline:
    def __init__(self):
        self.vad = SileroVADWorker(max_window_sec=getattr(settings, "AUDIO_WINDOW_SECONDS", 2.0))
        self.detector = SpoofDetector()
        self.smoothed_score = None
        self.alpha = getattr(settings, "EMA_ALPHA", 0.3)
        if not 0 < self.alpha <= 1:
            raise ValueError("EMA_ALPHA must be in (0, 1]")
        values = {name: getattr(settings, name, default) for name, default in {
            "MIN_SNR_DB": 10.0, "MIN_SPEECH_DURATION_MS": 1500,
            "HIGH_RISK_SPOOF_THRESHOLD": 0.75, "ELEVATED_RISK_SPOOF_THRESHOLD": 0.4,
            "EMA_ALPHA": 0.3, "VAD_THRESHOLD": 0.5, "MIN_RMS": 0.003,
            "AUDIO_WINDOW_SECONDS": 2.0,
        }.items()}
        digest = sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()[:12]
        self.threshold_profile = f"{getattr(settings, 'THRESHOLD_PROFILE', 'prototype-uncalibrated-v1')}:{digest}"

    @staticmethod
    @lru_cache(maxsize=1)
    def status() -> dict:
        vad, detector = SileroVADWorker(), SpoofDetector()
        vad_available, detector_available = vad.available, detector.available
        if vad_available:
            try:
                vad.process_chunk(bytes(1024))
            except Exception:
                vad_available = False
        if detector_available:
            try:
                detector.predict(np.zeros(32000, dtype=np.float32))
            except Exception:
                detector_available = False
        return {
            "available": vad_available and detector_available,
            "vad_available": vad_available,
            "detector_available": detector_available,
            "model_version": detector.model_version,
            "vad_model_version": vad.model_version,
            "calibrated": False,
        }

    def process_chunk(self, chunk_bytes: bytes) -> dict:
        result = {
            "risk_state": "SERVICE_UNAVAILABLE", "spoof_score": None, "snr_db": 0.0,
            "speech_duration_ms": 0, "reason_codes": ["MODEL_UNAVAILABLE"],
            "model_version": self.detector.model_version,
            "threshold_profile": self.threshold_profile,
        }
        if not self.vad.available or not self.detector.available:
            return result
        try:
            snr, speech_ms, pcm, clipped = self.vad.process_chunk(chunk_bytes)
            result.update(snr_db=snr, speech_duration_ms=speech_ms)
            if self.vad.rms < getattr(settings, "MIN_RMS", 0.003):
                self.smoothed_score = None
                result.update(risk_state="POOR_QUALITY", reason_codes=["AUDIO_TOO_QUIET"])
                return result
            state, reasons = DeterministicPolicyEngine.evaluate(snr, speech_ms, 0.0, clipped)
            if state.value in {"POOR_QUALITY", "INSUFFICIENT_EVIDENCE", "SERVICE_UNAVAILABLE"}:
                self.smoothed_score = None
                result.update(risk_state=state.value, reason_codes=reasons)
                return result
            score = self.detector.predict(pcm)
            self.smoothed_score = score if self.smoothed_score is None else (
                self.alpha * score + (1 - self.alpha) * self.smoothed_score
            )
            # Escalate immediately on high raw evidence; EMA slows only recovery.
            policy_score = max(score, self.smoothed_score)
            state, reasons = DeterministicPolicyEngine.evaluate(snr, speech_ms, policy_score, clipped)
            result.update(risk_state=state.value, spoof_score=round(policy_score, 6), reason_codes=reasons)
        except ValueError:
            self.vad.reset()
            self.smoothed_score = None
            result.update(risk_state="POOR_QUALITY", reason_codes=["INVALID_PCM_ENCODING"])
        except Exception:
            self.vad.reset()
            self.smoothed_score = None
            result.update(risk_state="SERVICE_UNAVAILABLE", reason_codes=["MODEL_INFERENCE_FAILED"])
        return result
