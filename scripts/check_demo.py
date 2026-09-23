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
import os
from pathlib import Path
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import UUID
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed
from app.api.v1.actions import complete as complete_action
from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.models.schemas import CompleteRequest

BASE = os.getenv("VIGILVOICE_BASE_URL", "http://127.0.0.1:8000/api/v1").rstrip("/")
WS_BASE = os.getenv("VIGILVOICE_WS_URL", "ws://127.0.0.1:8000/api/v1").rstrip("/")


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


class AuditFailingSession:
    def __init__(self, db):
        self.db = db

    async def execute(self, statement, params=None):
        if "INSERT INTO audit_logs" in str(statement):
            raise SQLAlchemyError("injected audit failure")
        return await self.db.execute(statement, params or {})

    def __getattr__(self, name):
        return getattr(self.db, name)


def write_private_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        json.dump(value, output)


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

        rollback = action(owner)
        rollback_approval = confirm(owner, rollback, challenge(owner, rollback))
        try:
            async with AsyncSessionLocal() as db:
                await complete_action(UUID(rollback["action_id"]), CompleteRequest(
                    approval_token=rollback_approval["approval_token"]), owner["session_token"],
                    AuditFailingSession(db))
        except SQLAlchemyError as exc:
            assert "injected audit failure" in str(exc)
        else:
            raise AssertionError("Injected audit failure did not abort completion")
        async with AsyncSessionLocal() as db:
            row = (await db.execute(text("""
                SELECT a.status,a.completed_at,p.consumed_at,
                       COUNT(l.id) FILTER (WHERE l.event_type='ACTION_COMPLETED') AS completed_events
                FROM protected_actions a JOIN approval_tokens p USING (action_id)
                LEFT JOIN audit_logs l USING (action_id)
                WHERE a.action_id=:id GROUP BY a.status,a.completed_at,p.consumed_at
            """), {"id": UUID(rollback["action_id"])})).mappings().one()
        assert row["status"] == "VERIFIED" and row["completed_at"] is None
        assert row["consumed_at"] is None and row["completed_events"] == 0
        assert complete(owner, rollback, rollback_approval)["status"] == "COMPLETED"
        passed("Injected audit failure rolls back completion and approval consumption")

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

        capacity_owner = session()
        assert upload(capacity_owner, genuine)["risk_state"] in ("LOW", "ELEVATED")
        capacity_action = action(capacity_owner)
        challenge(capacity_owner, capacity_action)
        holder = session()
        async with connect(f"{WS_BASE}/stream/ws/{holder['session_id']}") as ws:
            await ws.send(json.dumps({"session_token": holder["session_token"]}))
            assert json.loads(await ws.recv())["type"] == "ready"
            started_capacity_checks = time.perf_counter()
            for _ in range(2):
                overflow = session()
                async with connect(f"{WS_BASE}/stream/ws/{overflow['session_id']}") as rejected:
                    await rejected.send(json.dumps({"session_token": overflow["session_token"]}))
                    try:
                        await rejected.recv()
                    except ConnectionClosed as exc:
                        assert exc.code == 1013
                    else:
                        raise AssertionError("Excess audio session was admitted")
            request(f"/actions/{capacity_action['action_id']}", capacity_owner)
            request(f"/actions/{capacity_action['action_id']}/audit", capacity_owner)
            request(f"/demo/inbox/{capacity_action['action_id']}",
                    headers={"X-Demo-Verifier-Key": settings.DEMO_VERIFIER_KEY})
            assert time.perf_counter() - started_capacity_checks < 3
        assert upload(overflow, genuine)["risk_state"] in ("LOW", "ELEVATED")
        passed("One audio session admitted; sessions 2 and 3 rejected while action and verifier APIs stay responsive")

        unauthenticated = session()
        async with connect(f"{WS_BASE}/stream/ws/{unauthenticated['session_id']}") as ws:
            await ws.send(bytes(6400))
            try:
                await ws.recv()
            except ConnectionClosed as exc:
                assert exc.code == 1008
            else:
                raise AssertionError("Binary audio was accepted before authentication")

        with wave.open(io.BytesIO(genuine), "rb") as audio:
            pcm = audio.readframes(audio.getnframes())
        async with connect(f"{WS_BASE}/stream/ws/{owner['session_id']}") as ws:
            await ws.send(json.dumps({"session_token": owner["session_token"]}))
            assert json.loads(await ws.recv())["type"] == "ready"
            live_results = []
            for offset in range(0, len(pcm), 6400):
                await ws.send(pcm[offset:offset + 6400])
                live_results.append(json.loads(await ws.recv()))
                if live_results[-1]["risk_state"] in ("LOW", "ELEVATED"):
                    break
            assert len(live_results) >= 2 and live_results[-1]["risk_state"] in ("LOW", "ELEVATED"), live_results
            info = request(f"/sessions/{owner['session_id']}", owner)
            assert info["status"] == "LIVE" and info["speech_duration_ms"] > 0
            interrupted = action(owner)
            token = confirm(owner, interrupted, challenge(owner, interrupted))
        for _ in range(40):
            info = request(f"/sessions/{owner['session_id']}", owner)
            if info["status"] == "DISCONNECTED":
                break
            await asyncio.sleep(0.05)
        assert info["risk_state"] == "SERVICE_UNAVAILABLE"
        complete(owner, interrupted, token, 409)
        passed("Authenticated PCM reaches live inference; binary-first and disconnect remain fail-closed")

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


async def prepare_restart(state_path):
    genuine = Path("models/demo/genuine.wav").read_bytes()
    owner = session()
    assert upload(owner, genuine)["risk_state"] in ("LOW", "ELEVATED")

    completed = action(owner)
    completed_approval = confirm(owner, completed, challenge(owner, completed))
    assert complete(owner, completed, completed_approval)["status"] == "COMPLETED"
    events = request(f"/actions/{completed['action_id']}/audit", owner)["events"]
    assert sum(event["event_type"] == "ACTION_COMPLETED" for event in events) == 1

    expired = action(owner)
    expired_approval = confirm(owner, expired, challenge(owner, expired))
    async with AsyncSessionLocal() as db:
        await db.execute(text("""
            UPDATE approval_tokens SET expires_at=clock_timestamp()-interval '1 second'
            WHERE action_id=:id
        """), {"id": UUID(expired["action_id"])})
        await db.commit()

    orphaned = action(owner)
    issued = request(f"/actions/{orphaned['action_id']}/verification", owner, method="POST")
    delivered = request(f"/demo/inbox/{orphaned['action_id']}",
                        headers={"X-Demo-Verifier-Key": settings.DEMO_VERIFIER_KEY})
    assert delivered["action_id"] == orphaned["action_id"]
    del delivered

    with wave.open(io.BytesIO(genuine), "rb") as audio:
        pcm = audio.readframes(audio.getnframes())
    async with connect(f"{WS_BASE}/stream/ws/{owner['session_id']}") as ws:
        await ws.send(json.dumps({"session_token": owner["session_token"]}))
        assert json.loads(await ws.recv())["type"] == "ready"
        live_result = None
        for offset in range(0, len(pcm), 6400):
            await ws.send(pcm[offset:offset + 6400])
            live_result = json.loads(await ws.recv())
            if live_result["risk_state"] in ("LOW", "ELEVATED"):
                break
        assert live_result and live_result["risk_state"] in ("LOW", "ELEVATED"), live_result
        live = action(owner)
        live_approval = confirm(owner, live, challenge(owner, live))
        write_private_json(state_path, {
            "owner": owner,
            "completed": completed["action_id"],
            "completed_approval": completed_approval["approval_token"],
            "expired": expired["action_id"],
            "expired_approval": expired_approval["approval_token"],
            "orphaned": orphaned["action_id"],
            "orphaned_challenge": issued["challenge_id"],
            "live": live["action_id"],
            "live_approval": live_approval["approval_token"],
        })
        print(f"READY_FOR_RESTART: {state_path}", flush=True)
        try:
            while True:
                await ws.send(pcm[:6400])
                await ws.recv()
                await asyncio.sleep(1)
        except Exception:
            while True:
                await asyncio.sleep(60)


async def verify_restart(state_path, output):
    started = time.perf_counter()
    checks = []
    state = json.loads(state_path.read_text(encoding="utf-8"))
    owner = state["owner"]
    try:
        assert request("/system")["ready"]
        completed = request(f"/actions/{state['completed']}", owner)
        assert completed["status"] == "COMPLETED"
        complete(owner, {"action_id": state["completed"]},
                 {"approval_token": state["completed_approval"]}, 409)
        events = request(f"/actions/{state['completed']}/audit", owner)["events"]
        assert sum(event["event_type"] == "ACTION_COMPLETED" for event in events) == 1
        checks.append({"name": "Completed action and exactly-once audit survive restart", "passed": True})

        complete(owner, {"action_id": state["live"]},
                 {"approval_token": state["live_approval"]}, 409)
        session_info = request(f"/sessions/{owner['session_id']}", owner)
        live = request(f"/actions/{state['live']}", owner)
        async with AsyncSessionLocal() as db:
            restart_events = (await db.execute(text("""
                SELECT COUNT(*) FROM audit_logs
                WHERE session_id=:id AND event_type='AUDIO_UNAVAILABLE'
                  AND risk_state='SERVICE_UNAVAILABLE' AND reason_code='BACKEND_RESTART'
            """), {"id": UUID(owner["session_id"])})).scalar_one()
        assert session_info["status"] == "DISCONNECTED"
        assert live["status"] == "BLOCKED" and live["risk_state"] == "SERVICE_UNAVAILABLE"
        assert restart_events == 1
        checks.append({"name": "Restart invalidates live evidence and denies prior approval", "passed": True})

        assert upload(owner, Path("models/demo/genuine.wav").read_bytes())["risk_state"] in ("LOW", "ELEVATED")
        complete(owner, {"action_id": state["expired"]},
                 {"approval_token": state["expired_approval"]}, 409)
        assert request(f"/actions/{state['expired']}", owner)["status"] == "EXPIRED"
        checks.append({"name": "Expired approval is not revived by restart", "passed": True})

        status, lost = request(f"/actions/{state['orphaned']}/verification", owner,
                               method="POST", expected=None)
        assert status == 409 and lost["detail"] == "Verification delivery was lost; create a new action."
        request(f"/demo/inbox/{state['orphaned']}", expected=404,
                headers={"X-Demo-Verifier-Key": settings.DEMO_VERIFIER_KEY})
        assert request(f"/actions/{state['orphaned']}", owner)["status"] == "EXPIRED"
        complete(owner, {"action_id": state["orphaned"]},
                 {"approval_token": state["expired_approval"]}, 409)
        async with AsyncSessionLocal() as db:
            challenge_row = (await db.execute(text("""
                SELECT status,code_hash FROM verification_challenges WHERE challenge_id=:id
            """), {"id": UUID(state["orphaned_challenge"])})).mappings().one()
            leaked = (await db.execute(text("""
                SELECT COUNT(*) FROM audit_logs
                WHERE action_id=:id AND details::text ~ '\"otp_code\"|\"code\"[[:space:]]*:'
            """), {"id": UUID(state["orphaned"])})).scalar_one()
        assert challenge_row["status"] == "EXPIRED" and len(challenge_row["code_hash"]) == 64
        assert not challenge_row["code_hash"].isdigit() and leaked == 0
        checks.append({"name": "Lost verifier delivery expires action and stores no plaintext code", "passed": True})

        recovered = action(owner)
        recovered_approval = confirm(owner, recovered, challenge(owner, recovered))
        assert complete(owner, recovered, recovered_approval)["status"] == "COMPLETED"
        events = request(f"/actions/{recovered['action_id']}/audit", owner)["events"]
        assert sum(event["event_type"] == "ACTION_COMPLETED" for event in events) == 1
        checks.append({"name": "New action recovers after restart with fresh verification", "passed": True})
        success, error = True, None
    except Exception as exc:
        success, error = False, str(exc)
        print(f"FAIL: {error}", flush=True)
    finally:
        state_path.unlink(missing_ok=True)
        await engine.dispose()
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "passed": success,
              "elapsed_seconds": round(time.perf_counter() - started, 3), "checks": checks,
              "error": error, "scope": "Hard backend restart with isolated test records; no plaintext OTP persisted.",
              "script_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0 if success else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("/tmp/demo-checks.json"))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--restart-prepare", type=Path)
    mode.add_argument("--restart-verify", type=Path)
    args = parser.parse_args()
    if args.restart_prepare:
        raise SystemExit(asyncio.run(prepare_restart(args.restart_prepare.resolve())))
    if args.restart_verify:
        raise SystemExit(asyncio.run(verify_restart(args.restart_verify.resolve(), args.output.resolve())))
    raise SystemExit(asyncio.run(main(args.output.resolve())))
