"""Exercise post-COMMIT timeout ambiguity on the isolated test database only."""
import asyncio
import os
from pathlib import Path
import sys
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import make_url

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.v1.actions import (complete as complete_action, confirm as confirm_action,
                                request_verification)
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.schemas import CompleteRequest, OTPVerifyRequest
from scripts.check_demo import action, challenge, complete, confirm, request, session, upload


class CommittedTimeoutSession:
    def __init__(self, db):
        self.db = db

    async def commit(self):
        await self.db.commit()
        raise TimeoutError("injected timeout after committed transaction")

    def __getattr__(self, name):
        return getattr(self.db, name)


async def after_commit(operation):
    try:
        async with AsyncSessionLocal() as db:
            await operation(CommittedTimeoutSession(db))
    except TimeoutError:
        return
    raise AssertionError("Post-COMMIT timeout was not observed")


async def stored(action_id):
    async with AsyncSessionLocal() as db:
        return (await db.execute(text("""
            SELECT a.status,
                   (SELECT count(*) FROM verification_challenges WHERE action_id=a.action_id) challenges,
                   (SELECT count(*) FROM approval_tokens WHERE action_id=a.action_id) approvals,
                   (SELECT count(*) FROM approval_tokens WHERE action_id=a.action_id AND consumed_at IS NOT NULL) consumed,
                   (SELECT count(*) FROM audit_logs WHERE action_id=a.action_id AND event_type='OTP_CHALLENGE_ISSUED') issued,
                   (SELECT count(*) FROM audit_logs WHERE action_id=a.action_id AND event_type='OTP_VERIFIED') verified,
                   (SELECT count(*) FROM audit_logs WHERE action_id=a.action_id AND event_type='ACTION_COMPLETED') completed
            FROM protected_actions a WHERE action_id=:id
        """), {"id": UUID(action_id)})).mappings().one()


async def main():
    if os.getenv("VIGILVOICE_ISOLATED_TEST_DB") != "1" or make_url(settings.DATABASE_URL).host != "vv-s02-db":
        raise SystemExit("Refusing to run outside the isolated vv-s02-db test backend")
    owner = session()
    result = upload(owner, Path("models/demo/genuine.wav").read_bytes())
    assert result["risk_state"] in {"LOW", "ELEVATED"}

    pending = action(owner)
    assert pending["status"] == "PENDING"
    await after_commit(lambda db: request_verification(UUID(pending["action_id"]), owner["session_token"], db))
    row = await stored(pending["action_id"])
    assert (row["status"], row["challenges"], row["issued"], row["completed"]) == ("PENDING", 1, 1, 0)
    request(f"/actions/{pending['action_id']}/verification", owner, method="POST", expected=409)
    row = await stored(pending["action_id"])
    assert row["status"] == "EXPIRED" and row["completed"] == 0
    print("PASS: committed challenge without delivery cannot be retried or complete", flush=True)

    verifying = action(owner)
    code = challenge(owner, verifying)
    await after_commit(lambda db: confirm_action(UUID(verifying["action_id"]),
                      OTPVerifyRequest(**code), owner["session_token"], db))
    row = await stored(verifying["action_id"])
    assert (row["status"], row["approvals"], row["verified"], row["completed"]) == ("VERIFIED", 1, 1, 0)
    request(f"/actions/{verifying['action_id']}/confirm", owner, code, "POST", 409)
    complete(owner, verifying, {"approval_token": "x" * 40}, 403)
    print("PASS: committed approval without returned token cannot be reused or complete", flush=True)

    finishing = action(owner)
    approval = confirm(owner, finishing, challenge(owner, finishing))
    await after_commit(lambda db: complete_action(UUID(finishing["action_id"]),
                      CompleteRequest(approval_token=approval["approval_token"]), owner["session_token"], db))
    row = await stored(finishing["action_id"])
    assert (row["status"], row["consumed"], row["completed"]) == ("COMPLETED", 1, 1)
    complete(owner, finishing, approval, 409)
    assert request(f"/actions/{finishing['action_id']}", owner)["status"] == "COMPLETED"
    print("PASS: committed completion is visible, audited once, and non-replayable", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
