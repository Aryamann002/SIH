import hmac
import json
import secrets
from datetime import timedelta
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import get_db
from app.models.schemas import (ActionRequest, ActionResponse, ApprovalResponse,
                                ChallengeResponse, CompleteRequest, OTPVerifyRequest)
from app.services import demo_verifier
from app.services.action_gate import (bearer, db_now, digest, eligible, evidence,
                                     otp_digest, owned_action, owned_session)
from app.services.audit import AuditService

router = APIRouter()


def response(action) -> ActionResponse:
    return ActionResponse(**{key: action[key] for key in ("action_id", "session_id", "action_type", "payload", "status", "risk_state")},
                          allowed=action["status"] == "COMPLETED", otp_required=action["status"] == "PENDING")


async def event(db, action, name, reason=None, details=None):
    await AuditService.log_event(db, action["session_id"], name, action["risk_state"],
                                reason, details, action["action_id"])


async def reject(db, action, reason, status="BLOCKED"):
    await db.execute(text("UPDATE protected_actions SET status=:status WHERE action_id=:id"),
                     {"status": status, "id": action["action_id"]})
    await event(db, action, "ACTION_BLOCKED", reason)
    await db.commit()
    demo_verifier.inbox.pop(action["action_id"], None)
    raise HTTPException(409, reason)


@router.post("", response_model=ActionResponse, status_code=201)
@router.post("/execute", response_model=ActionResponse, status_code=201, deprecated=True)
async def create_action(req: ActionRequest, token: str = Depends(bearer), db: AsyncSession = Depends(get_db)):
    session = await owned_session(db, req.session_id, token, lock=True)
    risk, info = await evidence(db, session)
    action = {"action_id": uuid4(), "session_id": req.session_id, "action_type": req.action_type,
              "payload": req.payload.model_dump(), "status": "PENDING" if eligible(risk) else "BLOCKED",
              "risk_state": risk.value}
    await db.execute(text("""
        INSERT INTO protected_actions (action_id,session_id,action_type,payload,status,risk_state)
        VALUES (:action_id,:session_id,:action_type,CAST(:payload AS jsonb),:status,:risk_state)
    """), {**action, "payload": json.dumps(action["payload"])})
    await event(db, action, "ACTION_CREATED", details={"payload": action["payload"],
                "model_version": info.get("model_version", "unavailable"),
                "threshold_profile": info.get("threshold_profile", settings.THRESHOLD_PROFILE),
                "reason_codes": info.get("reason_codes", [])})
    await db.commit()
    return response(action)


@router.post("/verify-otp", deprecated=True)
async def legacy_verify():
    raise HTTPException(410, "Use action-bound /actions/{action_id}/confirm.")


@router.get("/{action_id}", response_model=ActionResponse)
async def get_action(action_id: UUID, token: str = Depends(bearer), db: AsyncSession = Depends(get_db)):
    action, _ = await owned_action(db, action_id, token, lock=False)
    return response(action)


@router.post("/{action_id}/verification", response_model=ChallengeResponse)
async def request_verification(action_id: UUID, token: str = Depends(bearer), db: AsyncSession = Depends(get_db)):
    action, session = await owned_action(db, action_id, token)
    if action["status"] != "PENDING":
        raise HTTPException(409, "This action is not awaiting verification.")
    risk, _ = await evidence(db, session)
    if not eligible(risk):
        await reject(db, action, "Current audio evidence does not permit verification.")
    existing = (await db.execute(text("SELECT challenge_id,expires_at,status FROM verification_challenges WHERE action_id=:id"),
                                 {"id": action_id})).mappings().first()
    if existing:
        if existing["status"] == "PENDING" and existing["expires_at"] > await db_now(db):
            return ChallengeResponse(**existing)
        await reject(db, action, "Verification expired or exhausted; create a new action.", "EXPIRED")
    if not settings.DEMO_VERIFIER_KEY:
        raise HTTPException(503, "Independent verification delivery is not configured.")
    challenge_id = uuid4()
    code = f"{secrets.randbelow(1000000):06d}"
    expires_at = await db_now(db) + timedelta(seconds=settings.OTP_TTL_SECONDS)
    await db.execute(text("""
        INSERT INTO verification_challenges (challenge_id,action_id,code_hash,status,expires_at)
        VALUES (:id,:action,:hash,'PENDING',:expires)
    """), {"id": challenge_id, "action": action_id, "hash": otp_digest(challenge_id, code), "expires": expires_at})
    await event(db, action, "OTP_CHALLENGE_ISSUED")
    await db.commit()
    demo_verifier.deliver(action_id, code, expires_at, action["payload"])
    return ChallengeResponse(challenge_id=challenge_id, expires_at=expires_at)


@router.post("/{action_id}/confirm", response_model=ApprovalResponse)
async def confirm(action_id: UUID, req: OTPVerifyRequest, token: str = Depends(bearer), db: AsyncSession = Depends(get_db)):
    action, session = await owned_action(db, action_id, token)
    if action["status"] != "PENDING":
        raise HTTPException(409, "This action is not awaiting verification.")
    risk, _ = await evidence(db, session)
    if not eligible(risk):
        await reject(db, action, "Current audio evidence does not permit verification.")
    challenge = (await db.execute(text("""
        SELECT * FROM verification_challenges WHERE action_id=:action AND challenge_id=:id FOR UPDATE
    """), {"action": action_id, "id": req.challenge_id})).mappings().first()
    if challenge is None or challenge["status"] != "PENDING":
        raise HTTPException(409, "No pending challenge for this action.")
    now = await db_now(db)
    if now >= challenge["expires_at"]:
        await db.execute(text("UPDATE verification_challenges SET status='EXPIRED' WHERE challenge_id=:id"), {"id": req.challenge_id})
        await reject(db, action, "OTP expired.", "EXPIRED")
    if challenge["attempts"] >= settings.MAX_OTP_ATTEMPTS:
        await reject(db, action, "OTP attempt limit reached.")
    if not hmac.compare_digest(challenge["code_hash"], otp_digest(req.challenge_id, req.otp_code)):
        attempts = challenge["attempts"] + 1
        locked = attempts >= settings.MAX_OTP_ATTEMPTS
        await db.execute(text("UPDATE verification_challenges SET attempts=:n,status=:status WHERE challenge_id=:id"),
                         {"n": attempts, "status": "LOCKED" if locked else "PENDING", "id": req.challenge_id})
        await event(db, action, "OTP_FAILED", "INVALID_CODE", {"attempts": attempts})
        if locked:
            await reject(db, action, "OTP attempt limit reached.")
        await db.commit()
        raise HTTPException(400, "Invalid OTP code.")
    approval = secrets.token_urlsafe(32)
    expires_at = now + timedelta(seconds=settings.APPROVAL_TTL_SECONDS)
    await db.execute(text("UPDATE verification_challenges SET status='VERIFIED' WHERE challenge_id=:id"), {"id": req.challenge_id})
    await db.execute(text("INSERT INTO approval_tokens (action_id,token_hash,expires_at) VALUES (:action,:hash,:expires)"),
                     {"action": action_id, "hash": digest(approval), "expires": expires_at})
    await db.execute(text("UPDATE protected_actions SET status='VERIFIED' WHERE action_id=:id"), {"id": action_id})
    await event(db, action, "OTP_VERIFIED")
    await db.commit()
    demo_verifier.inbox.pop(action_id, None)
    return ApprovalResponse(approval_token=approval, expires_at=expires_at)


@router.post("/{action_id}/complete", response_model=ActionResponse)
async def complete(action_id: UUID, req: CompleteRequest, token: str = Depends(bearer), db: AsyncSession = Depends(get_db)):
    action, session = await owned_action(db, action_id, token)
    if action["status"] != "VERIFIED":
        raise HTTPException(409, "An unused verified approval is required.")
    risk, info = await evidence(db, session)
    if not eligible(risk):
        await reject(db, action, "Audio evidence is stale, unavailable, or unsafe.")
    approval = (await db.execute(text("SELECT * FROM approval_tokens WHERE action_id=:id FOR UPDATE"), {"id": action_id})).mappings().first()
    if approval is None or approval["consumed_at"] is not None or not hmac.compare_digest(approval["token_hash"], digest(req.approval_token)):
        raise HTTPException(403, "Invalid approval token for this action.")
    now = await db_now(db)
    if now >= approval["expires_at"]:
        await reject(db, action, "Approval expired.", "EXPIRED")
    await db.execute(text("UPDATE approval_tokens SET consumed_at=:now WHERE action_id=:id"), {"id": action_id, "now": now})
    await db.execute(text("UPDATE protected_actions SET status='COMPLETED',completed_at=:now,risk_state=:risk WHERE action_id=:id"),
                     {"id": action_id, "now": now, "risk": risk.value})
    final = {**action, "status": "COMPLETED", "risk_state": risk.value}
    await event(db, final, "ACTION_COMPLETED", details={"simulated": True,
                "model_version": info.get("model_version"), "threshold_profile": info.get("threshold_profile")})
    await db.commit()
    return response(final)


@router.get("/{action_id}/audit")
async def audit(action_id: UUID, token: str = Depends(bearer), db: AsyncSession = Depends(get_db)):
    await owned_action(db, action_id, token, lock=False)
    rows = (await db.execute(text("""
        SELECT timestamp,event_type,risk_state,reason_code,details FROM audit_logs
        WHERE action_id=:id ORDER BY id
    """), {"id": action_id})).mappings().all()
    return {"events": [dict(row) for row in rows]}
