import asyncio
import time

from app.core.config import settings
from app.services import jev


def test_jev_modes_validation_timeout_and_redaction(monkeypatch):
    async def checks():
        state = jev.build_state({"risk_state": "ELEVATED", "speech_duration_ms": 2100,
                                 "threshold_profile": "policy-v1", "model_version": "model-v1"},
                                {"status": "LIVE"})
        assert "otp" not in str(state).lower() and "audio" not in str(state).lower()
        monkeypatch.setattr(settings, "JEV_MODE", "disabled")
        monkeypatch.setattr(settings, "JEV_API_KEY", "")
        assert (await jev.advise(state))["fallback_reason"] == "disabled"
        monkeypatch.setattr(settings, "JEV_MODE", "shadow")
        assert (await jev.advise(state))["fallback_reason"] == "missing_key"

        monkeypatch.setattr(settings, "JEV_API_KEY", "fake-test-secret")
        payload = {"model": settings.JEV_MODEL, "answers": {jev.QUESTION: {
            "type": "choice", "choice": "STANDARD_VERIFICATION", "confidence": .7,
            "probabilities": {name: (.7 if name == "STANDARD_VERIFICATION" else .1)
                              for name in jev.CHOICES},
        }}}
        monkeypatch.setattr(jev, "_request", lambda *_: payload)
        answer = await jev.advise(state)
        assert answer["choice"] == "STANDARD_VERIFICATION"
        assert answer["fallback_reason"] is None and answer["latency_ms"] is not None
        assert "fake-test-secret" not in str(answer)

        monkeypatch.setattr(jev, "_request", lambda *_: {"model": settings.JEV_MODEL,
            "answers": {jev.QUESTION: {"type": "choice", "choice": "ALLOW_TRANSFER"}}})
        assert (await jev.advise(state))["fallback_reason"] == "malformed_response"

        def bad_request(*_):
            raise RuntimeError("fake-test-secret must not leak")

        monkeypatch.setattr(jev, "_request", bad_request)
        assert "fake-test-secret" not in str(await jev.advise(state))
        monkeypatch.setattr(settings, "JEV_TIMEOUT_SECONDS", .01)
        monkeypatch.setattr(jev, "_request", lambda *_: time.sleep(.05))
        assert (await jev.advise(state))["fallback_reason"] == "timeout"
        await asyncio.sleep(.06)  # Allow the bounded worker to release its slot.
        assert (await jev.advise(state))["fallback_reason"] == "circuit_open"

    monkeypatch.setattr(jev, "_failures", 0)
    monkeypatch.setattr(jev, "_open_until", 0.0)
    asyncio.run(checks())


def test_advice_only_escalates_an_eligible_action():
    for mode in ("disabled", "shadow", "advisory"):
        for choice in jev.CHOICES:
            advice = {"mode": mode, "choice": choice, "fallback_reason": None}
            assert jev.final_action_status("BLOCKED", advice) == "BLOCKED"
            expected = ("BLOCKED" if mode == "advisory" and choice in
                        ("ENHANCED_REVIEW", "BLOCK_RECOMMENDED") else "PENDING")
            assert jev.final_action_status("PENDING", advice) == expected
    assert jev.final_action_status("PENDING", {"mode": "advisory", "choice": "BLOCK_RECOMMENDED",
                                                 "fallback_reason": "timeout"}) == "PENDING"
