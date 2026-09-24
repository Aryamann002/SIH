"""Optional, metadata-only Jev advice. This module never authorizes an action."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import http.client
import json
import time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.config import settings


QUESTION = "vigilvoice_route_v1"
CHOICES = ("CONTINUE_MONITORING", "STANDARD_VERIFICATION", "ENHANCED_REVIEW", "BLOCK_RECOMMENDED")
Choice = Literal["CONTINUE_MONITORING", "STANDARD_VERIFICATION", "ENHANCED_REVIEW", "BLOCK_RECOMMENDED"]
CRITERIA = {
    "CONTINUE_MONITORING": "The structured evidence is incomplete for a soft recommendation; maintain deterministic checks.",
    "STANDARD_VERIFICATION": "Eligible evidence supports the usual independent action-bound verification.",
    "ENHANCED_REVIEW": "Ambiguity warrants extra review; do not complete the action.",
    "BLOCK_RECOMMENDED": "The structured soft-risk pattern warrants blocking the action.",
}
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="jev-advice")
_slot = asyncio.Lock()
_failures = 0
_open_until = 0.0


class Answer(BaseModel):
    model_config = ConfigDict(extra="ignore", allow_inf_nan=False)
    type: Literal["choice"]
    choice: Choice
    probabilities: dict[Choice, float] | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)


class Reply(BaseModel):
    model_config = ConfigDict(extra="ignore")
    model: str
    answers: dict[str, Answer]


def _request(state, key, model, timeout):
    body = json.dumps({"model": model, "state": state, "questions": {QUESTION: {
        "type": "choice",
        "instructions": "Recommend only from the supplied structured metadata. Never authorize, verify identity, validate a code, or explain acoustic causes.",
        "criteria": CRITERIA,
    }}}, separators=(",", ":"), allow_nan=False)
    connection = http.client.HTTPSConnection("api.typesafe.ai", timeout=timeout)
    try:
        connection.request("POST", "/v1/systemone", body=body.encode(), headers={
            "Authorization": f"Bearer {key}", "Content-Type": "application/json",
            "Accept": "application/json",
        })
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError("authentication" if response.status in (401, 403) else "http_error")
        payload = response.read(8193)
        if len(payload) > 8192:
            raise ValueError("oversized_response")
        return json.loads(payload)
    finally:
        connection.close()


def _validate(payload, model):
    reply = Reply.model_validate(payload)
    if reply.model != model or set(reply.answers) != {QUESTION}:
        raise ValueError("malformed_response")
    answer = reply.answers[QUESTION]
    if answer.probabilities is not None:
        probabilities = answer.probabilities
        if (set(probabilities) != set(CHOICES) or any(not 0 <= value <= 1 for value in probabilities.values())
                or abs(sum(probabilities.values()) - 1) > 0.01
                or probabilities[answer.choice] < max(probabilities.values()) - 0.01):
            raise ValueError("malformed_response")
    return answer


def build_state(info, session):
    speech = info["speech_duration_ms"]
    return {
        "detector_score_bucket": info["risk_state"],
        "quality_state": "SUPPORTED", "evidence_freshness": "FRESH",
        "speech_duration_bucket": "UNDER_2_SECONDS" if speech < 2000 else "2_TO_4_SECONDS" if speech < 4000 else "OVER_4_SECONDS",
        "channel_type": "MICROPHONE" if session["status"] == "LIVE" else "WAV_UPLOAD",
        "replay_indicator": "UNKNOWN", "risk_trend": "UNKNOWN",
        "action_type": "SIMULATED_TRANSFER", "action_sensitivity": "HIGH",
        "verification_state": "NOT_STARTED", "detector_service": "AVAILABLE",
        "policy_version": info["threshold_profile"], "model_version": info["model_version"],
    }


def state_digest(state):
    return sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()


def final_action_status(deterministic, advice):
    if deterministic != "PENDING":
        return "BLOCKED"
    if (advice["mode"] == "advisory" and advice["fallback_reason"] is None
            and advice["choice"] in ("ENHANCED_REVIEW", "BLOCK_RECOMMENDED")):
        return "BLOCKED"  # No enhanced-review executor exists; require a new action.
    return "PENDING"


async def advise(state):
    global _failures, _open_until
    mode = settings.JEV_MODE
    record = {"mode": mode, "state_hash": state_digest(state),
              "question_version": QUESTION, "jev_model_version": settings.JEV_MODEL,
              "choice": None, "probabilities": None, "confidence": None,
              "latency_ms": None, "fallback_reason": None}
    if mode == "disabled":
        record["fallback_reason"] = "disabled"
        return record
    if not settings.JEV_API_KEY:
        record["fallback_reason"] = "missing_key"
        return record
    if time.monotonic() < _open_until:
        record["fallback_reason"] = "circuit_open"
        return record
    try:
        await asyncio.wait_for(_slot.acquire(), timeout=0.05)
    except TimeoutError:
        record["fallback_reason"] = "busy"
        return record
    started = time.perf_counter()
    submitted = False
    try:
        future = asyncio.get_running_loop().run_in_executor(
            _executor, _request, state, settings.JEV_API_KEY, settings.JEV_MODEL,
            settings.JEV_TIMEOUT_SECONDS)
        submitted = True
        future.add_done_callback(lambda _: _slot.release())
        payload = await asyncio.wait_for(asyncio.shield(future), timeout=settings.JEV_TIMEOUT_SECONDS)
        answer = _validate(payload, settings.JEV_MODEL)
        record.update(choice=answer.choice, probabilities=answer.probabilities,
                      confidence=answer.confidence)
        _failures = 0
    except Exception as exc:
        if isinstance(exc, TimeoutError):
            reason = "timeout"
        elif isinstance(exc, ValueError) and str(exc) in {"authentication", "http_error", "oversized_response", "malformed_response"}:
            reason = str(exc)
        elif isinstance(exc, (ValidationError, ValueError, TypeError, KeyError, json.JSONDecodeError)):
            reason = "malformed_response"
        else:
            reason = "transport_error"
        record["fallback_reason"] = reason
        _failures += 1
        if _failures >= 3:
            _open_until = time.monotonic() + 60
            _failures = 0
    finally:
        if not submitted:
            _slot.release()
        record["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
    return record
