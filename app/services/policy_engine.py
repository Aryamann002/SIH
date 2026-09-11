import math
from typing import List, Tuple
from app.core.config import settings
from app.models.schemas import RiskState


class DeterministicPolicyEngine:
    """Deterministic, fail-closed policy authorization engine."""

    @staticmethod
    def evaluate(
        snr_db: float,
        speech_duration_ms: int,
        spoof_score: float | None,
        is_clipped: bool = False,
    ) -> Tuple[RiskState, List[str]]:
        try:
            reasons: List[str] = []
            if spoof_score is None or not all(math.isfinite(v) for v in (snr_db, speech_duration_ms, spoof_score)):
                return RiskState.SERVICE_UNAVAILABLE, ["INVALID_OR_UNAVAILABLE_EVIDENCE"]
            if not 0 <= spoof_score <= 1 or speech_duration_ms < 0:
                return RiskState.SERVICE_UNAVAILABLE, ["INVALID_EVIDENCE_RANGE"]

            # 1. Audio quality check
            if is_clipped:
                reasons.append("AUDIO_CLIPPING_DETECTED")
                return RiskState.POOR_QUALITY, reasons

            if snr_db < settings.MIN_SNR_DB:
                reasons.append("LOW_SNR_AUDIO_DEGRADED")
                return RiskState.POOR_QUALITY, reasons

            # 2. Evidence duration check
            if speech_duration_ms < settings.MIN_SPEECH_DURATION_MS:
                reasons.append("INSUFFICIENT_SPEECH_DURATION")
                return RiskState.INSUFFICIENT_EVIDENCE, reasons

            # 3. Spoof detection score check
            if spoof_score >= settings.HIGH_RISK_SPOOF_THRESHOLD:
                reasons.append("HIGH_SPOOF_SCORE")
                return RiskState.HIGH, reasons

            if spoof_score >= settings.ELEVATED_RISK_SPOOF_THRESHOLD:
                reasons.append("ELEVATED_SPOOF_RISK")
                return RiskState.ELEVATED, reasons

            reasons.append("NO_STRONG_SYNTHETIC_EVIDENCE")
            return RiskState.LOW, reasons

        except Exception:
            # Fail closed on any exception
            return RiskState.SERVICE_UNAVAILABLE, ["ENGINE_FAILURE_FAIL_CLOSED"]
