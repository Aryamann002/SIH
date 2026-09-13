import asyncio
import hmac
import secrets
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import database_status, get_db
from app.services import demo_verifier
from app.services.action_gate import bearer, digest, evidence, owned_session
from app.services.audio_evidence import begin_audio, end_audio, evaluate_wav, infer, record_evidence, unavailable
from app.services.audit import AuditService

router = APIRouter()


@router.post("/sessions", status_code=201)
async def create_session(db: AsyncSession = Depends(get_db)):
    session_id, token = uuid4(), secrets.token_urlsafe(32)
    await db.execute(text("INSERT INTO sessions (session_id,status,token_hash) VALUES (:id,'CREATED',:hash)"),
                     {"id": session_id, "hash": digest(token)})
    await AuditService.log_event(db, session_id, "SESSION_CREATED")
    await db.commit()
    return {"session_id": session_id, "session_token": token}


@router.get("/sessions/{session_id}")
async def get_session(session_id: UUID, token: str = Depends(bearer), db: AsyncSession = Depends(get_db)):
    session = await owned_session(db, session_id, token)
    risk, info = await evidence(db, session)
    return {**unavailable(), "session_id": session_id, "status": session["status"], "risk_state": risk.value,
            "spoof_score": info.get("score"), "snr_db": info.get("snr_db", 0),
            "speech_duration_ms": info.get("speech_duration_ms", 0), "reason_codes": info.get("reason_codes", []),
            "model_version": info.get("model_version", "unavailable"),
            "threshold_profile": info.get("threshold_profile", settings.THRESHOLD_PROFILE)}


@router.post("/sessions/{session_id}/audio")
async def upload_audio(session_id: UUID, request: Request, token: str = Depends(bearer), db: AsyncSession = Depends(get_db)):
    await owned_session(db, session_id, token, lock=True)
    generation = await begin_audio(db, session_id, "PROCESSING_FILE")
    try:
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > settings.MAX_AUDIO_BYTES:
                raise HTTPException(413, "Maximum audio size is 30 seconds of 16 kHz mono PCM WAV.")
        result = await infer(lambda: evaluate_wav(bytes(data)))
        await record_evidence(db, session_id, generation, result, "FILE_READY")
        return {"session_id": session_id, **result}
    except ValueError as exc:
        await db.rollback()
        await end_audio(db, session_id, generation, "INVALID_AUDIO")
        raise HTTPException(422, str(exc))
    except HTTPException:
        await db.rollback()
        await end_audio(db, session_id, generation, "AUDIO_REQUEST_FAILED")
        raise
    except Exception:
        await db.rollback()
        await end_audio(db, session_id, generation, "INFERENCE_FAILED_OR_TIMED_OUT")
        raise HTTPException(503, "Audio inference is unavailable; action remains unapproved.")


async def model_status():
    from app.services.audio_pipeline import AudioPipeline
    try:
        return await infer(AudioPipeline.status)
    except Exception:
        return {"available": False, "vad_available": False, "detector_available": False,
                "model_version": "unavailable", "vad_model_version": "unavailable", "calibrated": False}


async def readiness():
    (database_available, schema_available), info = await asyncio.gather(database_status(), model_status())
    verifier_available = bool(settings.DEMO_VERIFIER_KEY)
    ready = all((database_available, schema_available, info["vad_available"],
                 info["detector_available"], verifier_available))
    return {**info, "available": ready, "ready": ready, "database_available": database_available,
            "schema_available": schema_available, "demo_verification_enabled": verifier_available,
            "simulated_transfers": True}


@router.get("/system")
async def system():
    return await readiness()


@router.get("/demo/inbox/{action_id}")
async def verifier_inbox(action_id: UUID, x_demo_verifier_key: str = Header(default="", max_length=128)):
    if not settings.DEMO_VERIFIER_KEY or not hmac.compare_digest(x_demo_verifier_key, settings.DEMO_VERIFIER_KEY):
        raise HTTPException(403, "Independent verifier credentials required.")
    demo_verifier.prune()
    message = demo_verifier.inbox.get(action_id)
    if message is None:
        raise HTTPException(404, "No unexpired verification message for this action.")
    return message
