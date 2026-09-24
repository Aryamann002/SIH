import asyncio
import argparse
import json
import struct
import statistics
import time
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
                                audio_path: Path = Path("models/demo/genuine.wav"),
                                duration_seconds: float = 0):
    session = create_session(api_uri)
    url = f"{server_uri}/{session['session_id']}"
    print(f"Connecting to VIGILVOICE Stream Gateway: {url}")
    with wave.open(str(audio_path), "rb") as audio:
        if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) != (1, 2, 16000):
            raise ValueError("Use mono 16 kHz PCM16 WAV audio.")
        pcm = audio.readframes(audio.getnframes())

    async with websockets.connect(url) as ws:
        await ws.send(json.dumps({"session_token": session["session_token"], "audio_protocol": "pcm16-seq-v1"}))
        ready = json.loads(await ws.recv())
        if (ready.get("type") != "ready" or ready.get("session_id") != session["session_id"]
                or ready.get("audio_protocol") != "pcm16-seq-v1"):
            raise RuntimeError(f"Unexpected stream handshake: {ready}")

        frames = [pcm[offset:offset + 6400] for offset in range(0, len(pcm) - 6399, 6400)]
        if not frames:
            raise ValueError("Stream test needs at least one 200 ms frame.")
        started = time.perf_counter()
        latencies = []
        sequence = 0
        while True:
            if not duration_seconds and sequence >= len(frames):
                break
            await asyncio.sleep(max(0, started + (sequence + 1) * .2 - time.perf_counter()))
            sent = time.perf_counter()
            await ws.send(struct.pack("<I", sequence) + frames[sequence % len(frames)])
            response_json = await ws.recv()
            data = json.loads(response_json)
            latencies.append(time.perf_counter() - sent)

            if not duration_seconds:
                print(
                    f"Frame {sequence + 1:02d} -> Risk State: {data['risk_state']} | "
                    f"Spoof Score: {data['spoof_score']} | SNR: {data['snr_db']}dB | "
                    f"Speech MS: {data['speech_duration_ms']}ms | Reasons: {data['reason_codes']}"
                )
            sequence += 1
            if duration_seconds and sequence % 300 == 0:
                print(f"Stream progress: {sequence} frames, {time.perf_counter() - started:.1f}s", flush=True)
            if duration_seconds and time.perf_counter() - started >= duration_seconds:
                break
        if duration_seconds:
            ordered = sorted(latencies)
            print(json.dumps({"frames": sequence, "elapsed_seconds": round(time.perf_counter() - started, 2),
                              "median_response_ms": round(statistics.median(latencies) * 1000, 2),
                              "p95_response_ms": round(ordered[max(0, int(.95 * len(ordered)) - 1)] * 1000, 2),
                              "first_60_response_ms": round(statistics.median(latencies[:300]) * 1000, 2),
                              "last_60_response_ms": round(statistics.median(latencies[-300:]) * 1000, 2)},
                             indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Exercise authenticated sequenced PCM streaming")
    parser.add_argument("--server-uri", default="ws://localhost:8000/api/v1/stream/ws")
    parser.add_argument("--api-uri", default="http://localhost:8000/api/v1")
    parser.add_argument("--audio-path", type=Path, default=Path("models/demo/genuine.wav"))
    parser.add_argument("--duration-seconds", type=float, default=0)
    args = parser.parse_args()
    if args.duration_seconds < 0:
        parser.error("--duration-seconds must be nonnegative")
    asyncio.run(run_client_simulation(args.server_uri, args.api_uri, args.audio_path, args.duration_seconds))
