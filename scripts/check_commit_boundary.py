"""Pause only an allowlisted isolated test PostgreSQL container during COMMIT.

Default target: vv-s02-db/vv-v02-final-backend on 59114. Set
VIGILVOICE_COMMIT_TARGET=sep26 for vv-sep26-db/vv-sep26-backend on 59115.
Uses the bundled public genuine WAV. Never targets the presentation database.
"""

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
TARGETS = {"legacy": ("vv-s02-db", "vv-v02-final-backend", 59114),
           "sep26": ("vv-sep26-db", "vv-sep26-backend", 59115)}
DB, BACKEND, PORT = TARGETS[os.getenv("VIGILVOICE_COMMIT_TARGET", "legacy")]
BASE = f"http://127.0.0.1:{PORT}/api/v1"
TRIGGER = "vv_commit_boundary_20260926"


def docker(*args, timeout=25):
    return subprocess.run(["docker", *args], check=True, capture_output=True,
                          text=True, timeout=timeout).stdout.strip()


def psql(sql):
    return docker("exec", DB, "psql", "-U", "vigilvoice", "-d", "vigilvoice",
                  "-X", "-q", "-t", "-A", "-v", "ON_ERROR_STOP=1", "-c", sql)


def api(path, body=None, token=None, content_type="application/json"):
    headers = {"Content-Type": content_type}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload = body if isinstance(body, bytes) else json.dumps(body or {}).encode()
    request = Request(BASE + path, data=payload, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=15) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


def ready():
    if docker("inspect", DB, "--format", "{{.State.Running}} {{.State.Paused}}") != "true false":
        raise RuntimeError("The isolated test database must be running and unpaused")
    if docker("inspect", BACKEND, "--format", "{{.State.Running}}") != "true":
        raise RuntimeError("The isolated test backend must be running")
    if docker("port", BACKEND, "8000/tcp") != f"127.0.0.1:{PORT}":
        raise RuntimeError("Refusing to send requests to an unexpected backend port")
    host = docker("exec", BACKEND, "python", "-c",
                  "from app.core.config import settings; from sqlalchemy.engine import make_url; "
                  "print(make_url(settings.DATABASE_URL).host)")
    if host != DB:
        raise RuntimeError("Backend is not connected to the isolated test database")


def install_trigger(stage):
    table, event = {"verification": ("verification_challenges", "INSERT"),
                    "confirmation": ("approval_tokens", "INSERT"),
                    "completion": ("approval_tokens", "UPDATE")}[stage]
    psql(f"""
        CREATE FUNCTION {TRIGGER}() RETURNS trigger LANGUAGE plpgsql AS
        $body$ BEGIN PERFORM pg_sleep(6); RETURN NEW; END $body$;
        CREATE CONSTRAINT TRIGGER {TRIGGER} AFTER {event} ON {table}
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION {TRIGGER}();
    """)


def remove_trigger(stage):
    table = {"verification": "verification_challenges", "confirmation": "approval_tokens",
             "completion": "approval_tokens"}[stage]
    psql(f"DROP TRIGGER IF EXISTS {TRIGGER} ON {table}; "
         f"DROP FUNCTION IF EXISTS {TRIGGER}();")


def in_commit():
    return psql("""
        SELECT count(*) FROM pg_stat_activity
        WHERE datname=current_database() AND query LIKE 'COMMIT%'
          AND wait_event='PgSleep'
    """) != "0"


def stored(action_id):
    action_id = UUID(action_id)
    row = psql(f"""
        SELECT a.status,
          (SELECT count(*) FROM verification_challenges WHERE action_id=a.action_id),
          (SELECT count(*) FROM audit_logs WHERE action_id=a.action_id
             AND event_type='OTP_CHALLENGE_ISSUED'),
          (SELECT count(*) FROM approval_tokens WHERE action_id=a.action_id
             AND consumed_at IS NOT NULL),
          (SELECT count(*) FROM audit_logs WHERE action_id=a.action_id
             AND event_type='ACTION_COMPLETED')
        FROM protected_actions a WHERE action_id='{action_id}'
    """)
    status, challenges, issued, consumed, completed = row.split("|")
    return status, int(challenges), int(issued), int(consumed), int(completed)


def stored_confirmation(action_id):
    action_id = UUID(action_id)
    row = psql(f"""
        SELECT a.status,
          (SELECT count(*) FROM approval_tokens WHERE action_id=a.action_id),
          (SELECT count(*) FROM audit_logs WHERE action_id=a.action_id
             AND event_type='OTP_VERIFIED'),
          (SELECT count(*) FROM audit_logs WHERE action_id=a.action_id
             AND event_type='ACTION_COMPLETED')
        FROM protected_actions a WHERE action_id='{action_id}'
    """)
    status, approvals, verified, completed = row.split("|")
    return status, int(approvals), int(verified), int(completed)


def pause_during_commit(stage, path, token, body=None):
    try:
        install_trigger(stage)
        with ThreadPoolExecutor(max_workers=1) as pool:
            started = time.perf_counter()
            pending = pool.submit(api, path, body, token)
            while not in_commit():
                if pending.done() or time.perf_counter() - started > 3:
                    raise AssertionError(f"{stage} did not reach deferred COMMIT")
                time.sleep(0.05)
            docker("pause", DB)
            time.sleep(3)
            docker("unpause", DB)
            status, _ = pending.result(timeout=12)
            elapsed = time.perf_counter() - started
            assert status == 503, f"Expected redacted 503, got {status}"
            assert elapsed < 12, f"Unbounded COMMIT response: {elapsed:.2f}s"
        deadline = time.perf_counter() + 12
        while in_commit() and time.perf_counter() < deadline:
            time.sleep(0.2)
        assert not in_commit(), "COMMIT still active after recovery"
        return elapsed
    finally:
        try:
            if docker("inspect", DB, "--format", "{{.State.Paused}}") == "true":
                docker("unpause", DB)
        finally:
            remove_trigger(stage)


def verifier_code(action_id):
    key = docker("exec", BACKEND, "python", "-c",
                 "from app.core.config import settings; print(settings.DEMO_VERIFIER_KEY)")
    request = Request(BASE + f"/demo/inbox/{UUID(action_id)}",
                      headers={"X-Demo-Verifier-Key": key})
    with urlopen(request, timeout=10) as response:
        return json.load(response)["otp_code"]


def main():
    ready()
    status, owner = api("/sessions")
    assert status == 201
    wav = (ROOT / "models/demo/genuine.wav").read_bytes()
    status, result = api(f"/sessions/{owner['session_id']}/audio", wav,
                         owner["session_token"], "audio/wav")
    assert status == 200 and result["risk_state"] in {"LOW", "ELEVATED"}
    status, action = api("/actions", {"session_id": owner["session_id"],
                          "action_type": "fund_transfer",
                          "payload": {"amount": 100, "recipient": "Isolated COMMIT test"}},
                         owner["session_token"])
    assert status == 201 and action["status"] == "PENDING"

    elapsed = pause_during_commit("verification",
                                  f"/actions/{action['action_id']}/verification",
                                  owner["session_token"])
    state = stored(action["action_id"])
    assert state[0] in {"PENDING", "EXPIRED"}
    assert state[1] <= 1 and state[1] == state[2] and state[3:] == (0, 0), state
    if state[1]:
        retry_status, _ = api(f"/actions/{action['action_id']}/verification",
                              None, owner["session_token"])
        assert retry_status == 409
        assert stored(action["action_id"]) == ("EXPIRED", 1, 1, 0, 0)
    print(f"PASS: verification COMMIT returned 503 in {elapsed:.2f}s; "
          f"challenge/audit count {state[1]}; zero completions; safe retry")

    status, confirming = api("/actions", {"session_id": owner["session_id"],
                               "action_type": "fund_transfer",
                               "payload": {"amount": 100, "recipient": "Isolated COMMIT test"}},
                             owner["session_token"])
    assert status == 201 and confirming["status"] == "PENDING"
    status, challenge = api(f"/actions/{confirming['action_id']}/verification",
                            None, owner["session_token"])
    assert status == 200
    code = verifier_code(confirming["action_id"])
    elapsed = pause_during_commit("confirmation",
                                  f"/actions/{confirming['action_id']}/confirm",
                                  owner["session_token"],
                                  {"challenge_id": challenge["challenge_id"], "otp_code": code})
    state = stored_confirmation(confirming["action_id"])
    assert state in {("PENDING", 0, 0, 0), ("VERIFIED", 1, 1, 0)}, state
    if state[0] == "VERIFIED":
        retry_status, _ = api(f"/actions/{confirming['action_id']}/confirm",
                              {"challenge_id": challenge["challenge_id"], "otp_code": code},
                              owner["session_token"])
        assert retry_status == 409
        guessed_status, _ = api(f"/actions/{confirming['action_id']}/complete",
                                {"approval_token": "x" * 40}, owner["session_token"])
        assert guessed_status == 403 and stored_confirmation(confirming["action_id"]) == state
    print(f"PASS: confirmation COMMIT returned 503 in {elapsed:.2f}s; "
          f"persisted {state[0]}; approval/audit {state[1]}/{state[2]}; zero completions")

    status, finishing = api("/actions", {"session_id": owner["session_id"],
                              "action_type": "fund_transfer",
                              "payload": {"amount": 100, "recipient": "Isolated COMMIT test"}},
                            owner["session_token"])
    assert status == 201 and finishing["status"] == "PENDING"
    status, challenge = api(f"/actions/{finishing['action_id']}/verification",
                            None, owner["session_token"])
    assert status == 200
    code = verifier_code(finishing["action_id"])
    status, approval = api(f"/actions/{finishing['action_id']}/confirm",
                           {"challenge_id": challenge["challenge_id"], "otp_code": code},
                           owner["session_token"])
    assert status == 200
    elapsed = pause_during_commit("completion",
                                  f"/actions/{finishing['action_id']}/complete",
                                  owner["session_token"],
                                  {"approval_token": approval["approval_token"]})
    state = stored(finishing["action_id"])
    assert (state[0], state[3], state[4]) in {("VERIFIED", 0, 0), ("COMPLETED", 1, 1)}, state
    if state[0] == "COMPLETED":
        retry_status, _ = api(f"/actions/{finishing['action_id']}/complete",
                              {"approval_token": approval["approval_token"]},
                              owner["session_token"])
        assert retry_status == 409 and stored(finishing["action_id"]) == state
    print(f"PASS: completion COMMIT returned 503 in {elapsed:.2f}s; "
          f"persisted {state[0]}; consumed/audit {state[3]}/{state[4]}; safe retry")


if __name__ == "__main__":
    main()
