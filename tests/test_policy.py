import pytest
from app.services.policy_engine import DeterministicPolicyEngine
from app.models.schemas import RiskState


def test_poor_quality_clipping():
    state, reasons = DeterministicPolicyEngine.evaluate(
        snr_db=20.0, speech_duration_ms=2000, spoof_score=0.10, is_clipped=True
    )
    assert state == RiskState.POOR_QUALITY
    assert "AUDIO_CLIPPING_DETECTED" in reasons


def test_poor_quality_low_snr():
    state, reasons = DeterministicPolicyEngine.evaluate(
        snr_db=5.0, speech_duration_ms=2000, spoof_score=0.10
    )
    assert state == RiskState.POOR_QUALITY
    assert "LOW_SNR_AUDIO_DEGRADED" in reasons


def test_insufficient_evidence_duration():
    state, reasons = DeterministicPolicyEngine.evaluate(
        snr_db=15.0, speech_duration_ms=800, spoof_score=0.10
    )
    assert state == RiskState.INSUFFICIENT_EVIDENCE
    assert "INSUFFICIENT_SPEECH_DURATION" in reasons


def test_high_risk_spoof():
    state, reasons = DeterministicPolicyEngine.evaluate(
        snr_db=15.0, speech_duration_ms=2000, spoof_score=0.85
    )
    assert state == RiskState.HIGH
    assert reasons == ["HIGH_SPOOF_SCORE"]


def test_elevated_risk_spoof():
    state, reasons = DeterministicPolicyEngine.evaluate(
        snr_db=15.0, speech_duration_ms=2000, spoof_score=0.55
    )
    assert state == RiskState.ELEVATED
    assert "ELEVATED_SPOOF_RISK" in reasons


def test_low_score_is_not_identity_verification():
    state, reasons = DeterministicPolicyEngine.evaluate(
        snr_db=15.0, speech_duration_ms=2000, spoof_score=0.15
    )
    assert state == RiskState.LOW
    assert reasons == ["NO_STRONG_SYNTHETIC_EVIDENCE"]
