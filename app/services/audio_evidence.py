import asyncio
import io
import json
import wave
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import text
from app.core.config import settings
from app.services.audit import AuditService

# ponytail: one CPU inference slot for this local demo; add measured worker capacity after load testing.
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="audio-inference")
_slot = asyncio.Lock()


async def infer(fn):
    try:
        await asyncio.wait_for(_slot.acquire(), timeout=1)
    except TimeoutError:
        raise HTTPException(503, "Audio inference is busy; retry shortly.")
    future = asyncio.get_running_loop().run_in_executor(_executor, fn)
    # A timeout cannot cancel a running native inference. Keep the slot until it actually ends.
    future.add_done_callback(lambda _: _slot.release())
    return await asyncio.wait_for(asyncio.shield(future), timeout=settings.AUDIO_INFERENCE_TIMEOUT_SECONDS)


def unavailable(reason="DETECTOR_UNAVAILABLE"):
    return {"risk_state": "SERVICE_UNAVAILABLE", "spoof_score": None, "snr_db": 0.0,
            "speech_duration_ms": 0, "reason_codes": [reason], "model_version": "unavailable",
            "threshold_profile": settings.THRESHOLD_PROFILE}


def evaluate_wav(data: bytes):
    from app.services.audio_pipeline import AudioPipeline
    try:
        with wave.open(io.BytesIO(data), "rb") as audio:
            if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate(), audio.getcomptype()) != (1, 2, 16000, "NONE"):
                raise ValueError("Use uncompressed 16 kHz, mono, 16-bit WAV audio.")
            frames = audio.getnframes()
            if not 0 < frames <= 16000 * 30:
                raise ValueError("Audio must contain between 1 sample and 30 seconds.")
            pcm = audio.readframes(frames)
            if len(pcm) != frames * 2:
                raise ValueError("The WAV file is truncated.")
    except (wave.Error, EOFError) as exc:
        raise ValueError("Invalid WAV audio.") from exc
    pipeline = AudioPipeline()
    results = [pipeline.process_chunk(pcm[i:i + 6400]) for i in range(0, len(pcm), 6400)]
    # Keep an alert anywhere in the file; trailing genuine speech cannot erase an earlier attack.
    for state in ("SERVICE_UNAVAILABLE", "HIGH", "ELEVATED"):
        candidates = [item for item in results if item["risk_state"] == state]
        if candidates:
            return candidates[-1]
    return results[-1]


async def begin_audio(db, session_id, mode):
    generation = uuid4()
    await db.execute(text("""
        UPDATE sessions SET generation=:generation,status=:status,latest_evaluation_id=NULL
        WHERE session_id=:id
    """), {"generation": generation, "status": mode, "id": session_id})
    await AuditService.log_event(db, session_id, "AUDIO_START", details={"source": mode})
    await db.commit()
    return generation


async def record_evidence(db, session_id, generation, result, mode):
    session = (await db.execute(text("SELECT * FROM sessions WHERE session_id=:id FOR UPDATE"), {"id": session_id})).mappings().one()
    if session["generation"] != generation:
        raise HTTPException(409, "A newer audio input replaced this one.")
    evaluation_id = uuid4()
    await db.execute(text("""
        INSERT INTO risk_evaluations (id,session_id,timestamp,score,snr_db,speech_duration_ms,
                                     risk_state,reason_codes,model_version,threshold_profile)
        VALUES (:id,:session,clock_timestamp(),:score,:snr,:speech,:risk,CAST(:reasons AS jsonb),:model,:profile)
    """), {"id": evaluation_id, "session": session_id, "score": result["spoof_score"],
            "snr": result["snr_db"], "speech": result["speech_duration_ms"], "risk": result["risk_state"],
            "reasons": json.dumps(result["reason_codes"]), "model": result["model_version"],
            "profile": result["threshold_profile"]})
    await db.execute(text("UPDATE sessions SET latest_evaluation_id=:evaluation,status=:mode WHERE session_id=:id"),
                     {"evaluation": evaluation_id, "mode": mode, "id": session_id})
    await AuditService.log_event(db, session_id, "SPOOF_EVAL", result["risk_state"],
                                details={**result, "source": mode})
    await db.commit()


async def end_audio(db, session_id, generation, reason):
    result = await db.execute(text("""
        UPDATE sessions SET status='DISCONNECTED',latest_evaluation_id=NULL
        WHERE session_id=:id AND generation=:generation RETURNING session_id
    """), {"id": session_id, "generation": generation})
    if result.first():
        await AuditService.log_event(db, session_id, "AUDIO_UNAVAILABLE", "SERVICE_UNAVAILABLE", reason)
    await db.commit()
