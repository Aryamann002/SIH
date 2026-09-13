import asyncio
from uuid import UUID
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from app.core.database import AsyncSessionLocal
from app.services.action_gate import owned_session
from app.services.audio_evidence import audio_capacity, begin_audio, end_audio, infer, record_evidence

router = APIRouter()


@router.websocket("/ws/{session_id}")
async def stream_audio_gateway(websocket: WebSocket, session_id: UUID):
    await websocket.accept()
    generation = None
    async with AsyncSessionLocal() as db:
        try:
            # Credentials are the first frame, never a URL/query string written to access logs.
            auth = await asyncio.wait_for(websocket.receive_json(), timeout=5)
            token = auth.get("session_token", "") if isinstance(auth, dict) else ""
            if not isinstance(token, str) or not 32 <= len(token) <= 128:
                raise HTTPException(401, "Session token required.")
            await owned_session(db, session_id, token, lock=True)
            generation = await begin_audio(db, session_id, "LIVE")
            async with audio_capacity():
                from app.services.audio_pipeline import AudioPipeline
                pipeline = await infer(AudioPipeline)
                await websocket.send_json({"type": "ready", "session_id": str(session_id)})
                while True:
                    data = await asyncio.wait_for(websocket.receive_bytes(), timeout=5)
                    if not data or len(data) > 16000 or len(data) % 2:
                        raise ValueError("Send 16-bit mono PCM frames up to 500 ms.")
                    result = await infer(lambda: pipeline.process_chunk(data))
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
