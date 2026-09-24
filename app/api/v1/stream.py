import asyncio
import json
import struct
import time
from uuid import UUID
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.services.action_gate import owned_session
from app.services.audio_evidence import audio_capacity, begin_audio, end_audio, infer, record_evidence

router = APIRouter()
_auth_slots = asyncio.Semaphore(8)  # ponytail: per-process cap; share admission state if workers are added.


@router.websocket("/ws/{session_id}")
async def stream_audio_gateway(websocket: WebSocket, session_id: UUID):
    await websocket.accept()
    generation = None
    async with AsyncSessionLocal() as db:
        try:
            # Credentials are the first frame, never a URL/query string written to access logs.
            if _auth_slots.locked():
                await websocket.close(code=1013)
                return
            await _auth_slots.acquire()
            try:
                message = await asyncio.wait_for(websocket.receive(), timeout=5)
                if message["type"] == "websocket.disconnect":
                    raise WebSocketDisconnect(message.get("code", 1000))
                raw = message.get("text")
                if not isinstance(raw, str) or len(raw) > 256:
                    raise ValueError("Send session credentials as the first JSON text frame.")
                try:
                    auth = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise ValueError("Send session credentials as the first JSON text frame.") from exc
                token = auth.get("session_token", "") if isinstance(auth, dict) else ""
                if not isinstance(token, str) or not 32 <= len(token) <= 128:
                    raise HTTPException(401, "Session token required.")
                if auth.get("audio_protocol") != "pcm16-seq-v1":
                    raise ValueError("Use the sequenced 200 ms PCM16 stream protocol.")
                await owned_session(db, session_id, token)
                await db.rollback()
            finally:
                _auth_slots.release()
            async with audio_capacity():
                await owned_session(db, session_id, token, lock=True)
                generation = await begin_audio(db, session_id, "LIVE")
                from app.services.audio_pipeline import AudioPipeline
                pipeline = await infer(AudioPipeline)
                started = time.monotonic()
                expected_sequence = 0
                await websocket.send_json({"type": "ready", "session_id": str(session_id),
                                           "audio_protocol": "pcm16-seq-v1"})
                while True:
                    data = await asyncio.wait_for(websocket.receive_bytes(), timeout=5)
                    received = time.monotonic()
                    if len(data) != 6404:
                        raise ValueError("Send sequenced 200 ms mono PCM16 frames.")
                    sequence = struct.unpack_from("<I", data)[0]
                    if sequence != expected_sequence:
                        raise ValueError("Duplicate, missing or out-of-order audio frame.")
                    lag = received - started - (sequence + 1) * 0.2
                    if lag > settings.STREAM_MAX_LAG_SECONDS or lag < -settings.STREAM_MAX_AHEAD_SECONDS:
                        raise ValueError("Audio frame is stale or arrived faster than capture time.")
                    expected_sequence += 1
                    result = await infer(lambda: pipeline.process_chunk(data[4:]))
                    if time.monotonic() - received >= settings.STREAM_EVIDENCE_TTL_SECONDS:
                        raise TimeoutError("Audio result exceeded the freshness window.")
                    await record_evidence(db, session_id, generation, result, "LIVE")
                    await websocket.send_json({"session_id": str(session_id), **result})
                    if result["risk_state"] == "SERVICE_UNAVAILABLE":
                        await websocket.close(code=1011)
                        break
        except WebSocketDisconnect:
            pass
        except HTTPException as exc:
            await websocket.close(code=1013 if exc.status_code == 503 else 1008)
        except ValueError:
            await websocket.close(code=1008)
        except TimeoutError:
            await websocket.close(code=1011)
        except Exception:
            await websocket.close(code=1011)
        finally:
            await db.rollback()
            if generation:
                await end_audio(db, session_id, generation, "STREAM_DISCONNECTED_OR_FAILED")
