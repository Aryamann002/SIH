import asyncio
import gc
import json
import threading
import time

from app.core.config import settings
from app.services import laya


def test_late_timeout_exception_is_retrieved_and_worker_slot_recovers(monkeypatch):
    release_worker = threading.Event()

    def late_failure(*_):
        assert release_worker.wait(2)
        raise TimeoutError("private late transport detail")

    async def checks():
        loop = asyncio.get_running_loop()
        errors = []
        loop.set_exception_handler(lambda _, context: errors.append(context))
        monkeypatch.setattr(laya, "_slot", asyncio.Lock())
        monkeypatch.setattr(laya, "_failures", 0)
        monkeypatch.setattr(laya, "_open_until", 0.0)
        monkeypatch.setattr(settings, "LAYA_MODE", "shadow")
        monkeypatch.setattr(settings, "LAYA_ENABLED", True)
        monkeypatch.setattr(settings, "LAYA_TIMEOUT_SECONDS", .01)
        monkeypatch.setattr(laya, "_request", late_failure)
        try:
            result = await laya.advise({"detector_score_bucket": "ELEVATED"})
            assert result["fallback_reason"] == "timeout" and result["choice"] is None
            assert laya.final_action_status("PENDING", result) == "PENDING"
            assert laya._slot.locked()  # Timeout must not admit another worker.
            assert (await laya.advise({}))["fallback_reason"] == "busy"
        finally:
            release_worker.set()
        async with asyncio.timeout(1):
            while laya._slot.locked():
                await asyncio.sleep(.001)
        gc.collect()
        await asyncio.sleep(0)
        assert errors == [], errors
        monkeypatch.setattr(laya, "_request", lambda *_: {
            "model": "laya-rl-agent", "routing": {"model": "english"},
            "answers": {laya.QUESTION: {"type": "choice", "choice": "STANDARD_VERIFICATION"}},
        })
        assert (await laya.advise({}))["choice"] == "STANDARD_VERIFICATION"

    asyncio.run(checks())


def test_laya_modes_validation_timeout_and_redaction(monkeypatch):
    async def checks():
        state = laya.build_state({"risk_state": "ELEVATED", "speech_duration_ms": 2100,
                                 "threshold_profile": "policy-v1", "model_version": "model-v1"},
                                {"status": "LIVE"})
        assert "otp" not in str(state).lower() and "audio" not in str(state).lower()
        monkeypatch.setattr(settings, "LAYA_MODE", "disabled")
        monkeypatch.setattr(settings, "LAYA_ENABLED", False)
        assert (await laya.advise(state))["fallback_reason"] == "disabled"
        monkeypatch.setattr(settings, "LAYA_MODE", "shadow")
        assert (await laya.advise(state))["fallback_reason"] == "not_configured"

        monkeypatch.setattr(settings, "LAYA_ENABLED", True)
        payload = {"model": "laya-rl-agent", "routing": {"model": laya.MODEL, "detection": None},
                   "answers": {laya.QUESTION: {
            "type": "choice", "choice": "STANDARD_VERIFICATION", "confidence": .7,
            "probabilities": {name: (.7 if name == "STANDARD_VERIFICATION" else .1)
                              for name in laya.CHOICES},
        }}}
        monkeypatch.setattr(laya, "_request", lambda *_: payload)
        answer = await laya.advise(state)
        assert answer["choice"] == "STANDARD_VERIFICATION"
        assert answer["fallback_reason"] is None and answer["latency_ms"] is not None
        assert answer["provider"] == "laya"

        monkeypatch.setattr(laya, "_request", lambda *_: {**payload,
            "answers": {laya.QUESTION: {"type": "choice", "choice": "ALLOW_TRANSFER"}}})
        assert (await laya.advise(state))["fallback_reason"] == "malformed_response"
        monkeypatch.setattr(laya, "_request", lambda *_: {**payload, "routing": {"model": "multilingual"}})
        assert (await laya.advise(state))["fallback_reason"] == "malformed_response"

        def bad_request(*_):
            raise RuntimeError("private transport detail must not leak")

        monkeypatch.setattr(laya, "_request", bad_request)
        assert "private transport detail" not in str(await laya.advise(state))
        monkeypatch.setattr(laya, "_failures", 2)
        monkeypatch.setattr(laya, "_open_until", 0.0)
        monkeypatch.setattr(settings, "LAYA_TIMEOUT_SECONDS", .01)
        monkeypatch.setattr(laya, "_request", lambda *_: time.sleep(.05))
        assert (await laya.advise(state))["fallback_reason"] == "timeout"
        await asyncio.sleep(.06)  # Allow the bounded worker to release its slot.
        assert (await laya.advise(state))["fallback_reason"] == "circuit_open"

    monkeypatch.setattr(laya, "_failures", 0)
    monkeypatch.setattr(laya, "_open_until", 0.0)
    asyncio.run(checks())


def test_advice_only_escalates_an_eligible_action():
    for mode in ("disabled", "shadow", "advisory"):
        for choice in laya.CHOICES:
            advice = {"mode": mode, "choice": choice, "fallback_reason": None}
            assert laya.final_action_status("BLOCKED", advice) == "BLOCKED"
            expected = ("BLOCKED" if mode == "advisory" and choice in
                        ("ENHANCED_REVIEW", "BLOCK_RECOMMENDED") else "PENDING")
            assert laya.final_action_status("PENDING", advice) == expected
    assert laya.final_action_status("PENDING", {"mode": "advisory", "choice": "BLOCK_RECOMMENDED",
                                                 "fallback_reason": "timeout"}) == "PENDING"


def test_request_uses_only_internal_laya_service(monkeypatch):
    calls = {"requests": []}
    revision = laya.MODEL_REVISION

    class Connection:
        def __init__(self, host, port, timeout):
            calls.update(host=host, port=port, timeout=timeout)

        def request(self, method, path, body=None, headers=None):
            calls["requests"].append((method, path, json.loads(body) if body else None, headers))

        def getresponse(self):
            class Response:
                status = 200

                def read(self, _):
                    if len(calls["requests"]) == 1:
                        return json.dumps({"status": "ok", "revisions": {"english": revision}}).encode()
                    return b'{}'
            return Response()

        def close(self):
            pass

    monkeypatch.setattr(laya.http.client, "HTTPConnection", Connection)
    laya._request({"detector_score_bucket": "ELEVATED"}, .75)
    assert calls["host"] == "laya" and calls["port"] == 8000
    assert calls["requests"][0][:2] == ("GET", "/health")
    method, path, body, headers = calls["requests"][1]
    assert (method, path) == ("POST", "/v1/systemone")
    assert body["model"] == "english"
    assert "Authorization" not in headers
    revision = "wrong-revision"
    calls["requests"].clear()
    try:
        laya._request({"detector_score_bucket": "ELEVATED"}, .75)
    except ValueError as exc:
        assert str(exc) == "model_unavailable"
    else:
        raise AssertionError("Wrong Laya checkpoint must fail closed")
    assert len(calls["requests"]) == 1
