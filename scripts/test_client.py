import asyncio
import json
import uuid
import numpy as np
import websockets


async def run_client_simulation(server_uri: str = "ws://localhost:8000/api/v1/stream/ws"):
    session_id = str(uuid.uuid4())
    url = f"{server_uri}/{session_id}"
    print(f"Connecting to VIGILVOICE Stream Gateway: {url}")

    async with websockets.connect(url) as ws:
        # Simulate 10 frames of 16kHz 16-bit PCM audio (200ms per frame)
        sample_rate = 16000
        frame_duration_sec = 0.2
        samples_per_frame = int(sample_rate * frame_duration_sec)

        for i in range(10):
            # Generate speech-like synthetic sine wave audio with noise
            t = np.linspace(0, frame_duration_sec, samples_per_frame, endpoint=False)
            sine_wave = 0.3 * np.sin(2 * np.pi * 440 * t)  # 440Hz tone
            noise = 0.01 * np.random.normal(size=samples_per_frame)
            audio_signal = (sine_wave + noise).astype(np.float32)

            # Convert float32 [-1, 1] to Int16 PCM bytes
            pcm_int16 = (audio_signal * 32767).astype(np.int16)
            pcm_bytes = pcm_int16.tobytes()

            await ws.send(pcm_bytes)
            response_json = await ws.recv()
            data = json.loads(response_json)

            print(
                f"Frame {i+1:02d} -> Risk State: {data['risk_state']} | "
                f"Spoof Score: {data['spoof_score']} | SNR: {data['snr_db']}dB | "
                f"Speech MS: {data['speech_duration_ms']}ms | Reasons: {data['reason_codes']}"
            )
            await asyncio.sleep(0.1)


if __name__ == "__main__":
    asyncio.run(run_client_simulation())
