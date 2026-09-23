import asyncio
import json
import websockets
from pathlib import Path
from urllib.request import Request, urlopen
import wave


def create_session(base_uri: str):
    request = Request(f"{base_uri}/sessions", data=b"{}", method="POST",
                      headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=5) as response:
        return json.load(response)


async def run_client_simulation(server_uri: str = "ws://localhost:8000/api/v1/stream/ws",
                                api_uri: str = "http://localhost:8000/api/v1",
                                audio_path: Path = Path("models/demo/genuine.wav")):
    session = create_session(api_uri)
    url = f"{server_uri}/{session['session_id']}"
    print(f"Connecting to VIGILVOICE Stream Gateway: {url}")
    with wave.open(str(audio_path), "rb") as audio:
        if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) != (1, 2, 16000):
            raise ValueError("Use mono 16 kHz PCM16 WAV audio.")
        pcm = audio.readframes(audio.getnframes())

    async with websockets.connect(url) as ws:
        await ws.send(json.dumps({"session_token": session["session_token"]}))
        ready = json.loads(await ws.recv())
        if ready.get("type") != "ready" or ready.get("session_id") != session["session_id"]:
            raise RuntimeError(f"Unexpected stream handshake: {ready}")

        for i, offset in enumerate(range(0, len(pcm), 6400), 1):
            await ws.send(pcm[offset:offset + 6400])
            response_json = await ws.recv()
            data = json.loads(response_json)

            print(
                f"Frame {i:02d} -> Risk State: {data['risk_state']} | "
                f"Spoof Score: {data['spoof_score']} | SNR: {data['snr_db']}dB | "
                f"Speech MS: {data['speech_duration_ms']}ms | Reasons: {data['reason_codes']}"
            )
            await asyncio.sleep(0.2)


if __name__ == "__main__":
    asyncio.run(run_client_simulation())
