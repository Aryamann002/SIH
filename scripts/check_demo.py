"""Exercise the running LOCAL demo with real models and fresh simulated actions.

Run inside backend: python scripts/check_demo.py --output /tmp/demo-checks.json
Expiry checks age only rows created by this run; existing records are preserved.
"""
import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
import io
import json
from pathlib import Path
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import UUID
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import text
from websockets.asyncio.client import connect
from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine

BASE = "http://127.0.0.1:8000/api/v1"


def request(path, session=None, body=None, method="GET", expected=200, headers=None):
    headers = dict(headers or {})
    if session:
        headers["Authorization"] = f"Bearer {session['session_token']}"
    if body is not None and not isinstance(body, bytes):
        body = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = Request(BASE + path, data=body, headers=headers, method=method)
    try:
        with urlopen(req, timeout=30) as response:
            status, result = response.status, json.load(response)
    except HTTPError as exc:
        status, result = exc.code, json.load(exc)
    if expected is not None:
        assert status == expected, f"{method} {path}: expected {expected}, got {status}: {result}"
    return (status, result) if expected is None else result


def session():
    return request("/sessions", body={}, method="POST", expected=201)


def upload(owner, data, expected=200):
    return request(f"/sessions/{owner['session_id']}/audio", owner, data, "POST", expected,
                   {"Content-Type": "audio/wav"})


def action(owner):
    return request("/actions", owner, {"session_id": owner["session_id"],
                   "action_type": "fund_transfer", "payload": {"amount": 100, "recipient": "Automated demo check"}},
                   "POST", 201)


def challenge(owner, item):
    path = f"/actions/{item['action_id']}"
    issued = request(path + "/verification", owner, method="POST")
    delivered = request(f"/demo/inbox/{item['action_id']}",
                        headers={"X-Demo-Verifier-Key": settings.DEMO_VERIFIER_KEY})
    return {"challenge_id": issued["challenge_id"], "otp_code": delivered["otp_code"]}


def confirm(owner, item, code):
    return request(f"/actions/{item['action_id']}/confirm", owner, code, "POST")


def complete(owner, item, approval, expected=200):
    return request(f"/actions/{item['action_id']}/complete", owner,
                   {"approval_token": approval["approval_token"]}, "POST", expected)


def wav(pcm, rate=16000):
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        audio.writeframes(pcm)
    return output.getvalue()


async def main(output):
    started = time.perf_counter()
    checks = []

    def passed(name):
        checks.append({"name": name, "passed": True})
        print(f"PASS: {name}", flush=True)

    try:
        system = request("/system")
        assert system.get("ready") and all(system[key] for key in (
            "database_available", "schema_available", "vad_available",
            "detector_available", "demo_verification_enabled"
        )), system
        passed("Database schema, local models and demo verifier ready")
        genuine = Path("models/demo/genuine.wav").read_bytes()
        synthetic = Path("models/demo/synthetic.wav").read_bytes()
        owner, stranger = session(), session()
        request(f"/sessions/{owner['session_id']}", expected=401)
        request(f"/sessions/{owner['session_id']}", stranger, expected=404)
        empty = action(owner)
        assert empty["status"] == "BLOCKED" and not empty["allowed"]
        passed("Missing evidence blocks; session credentials isolate access")

        result = upload(owner, genuine)
        assert result["risk_state"] in ("LOW", "ELEVATED"), result
        first, second = action(owner), action(owner)
        assert first["status"] == "PENDING" and first["otp_required"] and not first["allowed"]
        request(f"/actions/{first['action_id']}", stranger, expected=404)
        request(f"/actions/{first['action_id']}/audit", stranger, expected=404)
        request(f"/demo/inbox/{first['action_id']}", owner, expected=403)
        code = challenge(owner, first)
        request(f"/actions/{second['action_id']}/confirm", owner, code, "POST", 409)
        approval = confirm(owner, first, code)
        second_approval = confirm(owner, second, challenge(owner, second))
        complete(owner, second, approval, 403)
        complete(stranger, first, approval, 404)
        request(f"/actions/{first['action_id']}/complete", owner,
                {"approval_token": approval["approval_token"], "payload": {"amount": 1}}, "POST", 422)
        passed("OTP and approval are bound to exact action; verifier and payload boundaries enforced")

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: complete(owner, first, approval, None), range(2)))
        assert sorted(status for status, _ in results) == [200, 409], results
        assert next(data for status, data in results if status == 200)["allowed"] is True
        complete(owner, first, approval, 409)
        audit = request(f"/actions/{first['action_id']}/audit", owner)["events"]
        assert sum(row["event_type"] == "ACTION_COMPLETED" for row in audit) == 1
        assert complete(owner, second, second_approval)["status"] == "COMPLETED"
        passed("Concurrent completion succeeds exactly once with a persisted audit event")

        locked = action(owner)
        correct = challenge(owner, locked)
        wrong = {**correct, "otp_code": "000000" if correct["otp_code"] != "000000" else "000001"}
        for status in (400, 400, 409):
            request(f"/actions/{locked['action_id']}/confirm", owner, wrong, "POST", status)
        request(f"/actions/{locked['action_id']}/verification", owner, method="POST", expected=409)
        request(f"/actions/{locked['action_id']}/confirm", owner, correct, "POST", 409)
        passed("Three incorrect OTPs block action and cannot be reset")

        expired = action(owner)
        expired_code = challenge(owner, expired)
        async with AsyncSessionLocal() as db:
            await db.execute(text("UPDATE verification_challenges SET expires_at=clock_timestamp()-interval '1 second' WHERE challenge_id=:id"),
                             {"id": UUID(expired_code["challenge_id"])})
            await db.commit()
        request(f"/actions/{expired['action_id']}/confirm", owner, expired_code, "POST", 409)
        assert request(f"/actions/{expired['action_id']}", owner)["status"] == "EXPIRED"
        passed("Expired OTP cannot approve (test-owned expiry shifted in database)")

        expired_approval = action(owner)
        token = confirm(owner, expired_approval, challenge(owner, expired_approval))
        async with AsyncSessionLocal() as db:
            await db.execute(text("UPDATE approval_tokens SET expires_at=clock_timestamp()-interval '1 second' WHERE action_id=:id"),
                             {"id": UUID(expired_approval["action_id"])})
            await db.commit()
        complete(owner, expired_approval, token, 409)
        passed("Expired approval cannot complete (test-owned expiry shifted in database)")

        stale = action(owner)
        token = confirm(owner, stale, challenge(owner, stale))
        async with AsyncSessionLocal() as db:
            await db.execute(text("UPDATE risk_evaluations SET timestamp=clock_timestamp()-(:seconds * interval '1 second') WHERE session_id=:id"),
                             {"id": UUID(owner["session_id"]), "seconds": settings.FILE_EVIDENCE_TTL_SECONDS + 1})
            await db.commit()
        complete(owner, stale, token, 409)
        stored = request(f"/actions/{stale['action_id']}", owner)
        assert stored["status"] == "BLOCKED" and stored["risk_state"] == "SERVICE_UNAVAILABLE"
        audit = request(f"/actions/{stale['action_id']}/audit", owner)["events"]
        assert audit[-1]["risk_state"] == "SERVICE_UNAVAILABLE"
        passed("Stale evidence blocks completion; stored action and audit show current unsafe risk")

        upload(owner, genuine)
        raised = action(owner)
        token = confirm(owner, raised, challenge(owner, raised))
        result = upload(owner, synthetic)
        assert result["risk_state"] == "HIGH", result
        complete(owner, raised, token, 409)
        assert request(f"/actions/{raised['action_id']}", owner)["risk_state"] == "HIGH"
        assert action(owner)["status"] == "BLOCKED"
        passed("Synthetic demo clip blocks new action and previously verified completion")

        for name, data, status in (
            ("invalid", b"not a wav", 422), ("truncated", genuine[:-100], 422),
            ("wrong sample rate", wav(bytes(16000), 8000), 422),
            ("oversized", bytes(settings.MAX_AUDIO_BYTES + 1), 413),
        ):
            upload(owner, data, status)
            info = request(f"/sessions/{owner['session_id']}", owner)
            assert info["risk_state"] == "SERVICE_UNAVAILABLE", name
            assert action(owner)["status"] == "BLOCKED", name
        passed("Malformed, truncated, wrong-rate and oversized audio fail closed")

        for data in (wav(bytes(96000)), wav(b'\xff\x7f' * 48000), wav(bytes(32))):
            result = upload(owner, data)
            assert result["risk_state"] in ("POOR_QUALITY", "INSUFFICIENT_EVIDENCE"), result
            assert result["spoof_score"] is None
            assert action(owner)["status"] == "BLOCKED"
        passed("Silence, clipping and too-short audio never fabricate a safe score")

        upload(owner, genuine)
        interrupted = action(owner)
        token = confirm(owner, interrupted, challenge(owner, interrupted))
        async with connect(f"ws://127.0.0.1:8000/api/v1/stream/ws/{owner['session_id']}") as ws:
            await ws.send(json.dumps({"session_token": owner["session_token"]}))
            assert json.loads(await ws.recv())["type"] == "ready"
        for _ in range(40):
            info = request(f"/sessions/{owner['session_id']}", owner)
            if info["status"] == "DISCONNECTED":
                break
            await asyncio.sleep(0.05)
        assert info["risk_state"] == "SERVICE_UNAVAILABLE"
        complete(owner, interrupted, token, 409)
        passed("WebSocket replacement and disconnect invalidate earlier file evidence")

        from app.services.audio_pipeline import AudioPipeline
        old = settings.SPOOF_MODEL_PATH
        try:
            settings.SPOOF_MODEL_PATH = str(Path("/tmp") / f"missing-model-{owner['session_id']}.onnx")
            result = AudioPipeline().process_chunk(bytes(6400))
            assert result["risk_state"] == "SERVICE_UNAVAILABLE" and result["spoof_score"] is None
        finally:
            settings.SPOOF_MODEL_PATH = old
        passed("Missing-model pipeline returns unavailable with no score (isolated process setting)")
        success = True
        error = None
    except Exception as exc:
        success, error = False, str(exc)
        print(f"FAIL: {error}", flush=True)
    finally:
        await engine.dispose()
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "passed": success,
              "elapsed_seconds": round(time.perf_counter() - started, 3), "checks": checks, "error": error,
              "scope": "Local simulated transactions; real pretrained inference. Not accuracy or production security certification.",
              "script_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0 if success else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("/tmp/demo-checks.json"))
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.output.resolve())))
