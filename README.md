# VigilVoice

VigilVoice is a local prototype for checking speech during a call before an operator completes a sensitive action. It runs voice activity detection and a synthetic-speech classifier, shows the resulting risk, and requires separate verification for a simulated INR transfer. A voice score never establishes identity or authorizes a transfer by itself.

The application uses FastAPI, PostgreSQL, ONNX Runtime, Silero VAD, a pretrained INT8 Wav2Vec2 classifier, and browser JavaScript. Transfers and verifier delivery are simulated; the model inference, action checks, and audit records are real.

## Run locally

You need Python 3.11, Docker with Compose, and Chrome or Edge for microphone input. Downloading the model files requires internet access once. From the repository root:

```powershell
python scripts/fetch_models.py
python scripts/configure_demo.py
docker compose up -d --build
```

`configure_demo.py` creates an ignored `.env` with local credentials and preserves an existing one. `fetch_models.py` downloads the pinned ONNX files into the ignored `models/` directory and verifies their SHA-256 hashes. The backend applies its database migration at startup. Check `http://127.0.0.1:8000/readyz` before using the app; `/healthz` only checks that the process responds.

For an offline machine, use the prebuilt backend and PostgreSQL image archives plus the model archive from the local handoff. Load both images, extract the models into `models/`, create local `.env` credentials with `configure_demo.py`, and start with `docker compose up -d --no-build --pull never`. Do not copy another machine's `.env` or database volume.

Open `http://127.0.0.1:8000/` for the operator screen and `http://127.0.0.1:8000/verify` for the verifier. Keep the `DEMO_VERIFIER_KEY` from `.env` private and enter it only on the verifier screen. Both screens run locally; the verifier is a separate demo role, not an independent delivery channel.

## Try the workflow

1. Start live detection and allow microphone access. The browser sends numbered 200 ms mono PCM frames over an authenticated WebSocket and updates the risk display. You can also record up to 10 seconds and analyze the WAV, or upload a 16 kHz mono, 16-bit PCM WAV file.
2. Prepare a simulated transfer with a recipient and amount. If the audio evidence is usable and the risk is LOW or ELEVATED, request verification. HIGH risk, stale or missing evidence, and service failure block completion.
3. On `/verify`, review the exact recipient and amount using the action ID. Enter the six-digit code on the operator screen and complete the transfer. The code expires after 60 seconds, permits at most three attempts, and can authorize the bound action only once. The audit trail appears below the action.

If a challenge expires, HIGH evidence appears, the audio source changes or disconnects, or verifier delivery is lost after a restart, create a new transfer. To stop the stack without deleting its database volume, run `docker compose down`.

Jev is optional. The default `JEV_MODE=shadow` records a metadata-only recommendation when `JEV_API_KEY` is set; without a key, the deterministic local workflow continues and records the fallback. `JEV_MODE=disabled` never calls Jev. Advisory escalation is gated off pending live shadow evaluation. Jev never receives audio or codes and never completes a transfer.

### WAV upload format

Choose an actual uncompressed **RIFF/WAVE PCM** file with **one channel (mono), 16,000 samples per second (16 kHz), and signed 16-bit samples**. The upload limit is **960,044 bytes including the WAV header**, enough for 30 seconds only with a standard 44-byte header; files with extra metadata need to be slightly shorter. A stereo, 44.1/48 kHz, 24-bit, floating-point, or compressed WAV will be rejected; renaming an MP3 to `.wav` does not convert it.

For a useful result, record about **3–10 seconds of clear, continuous speech** at a normal volume. The detector needs at least **1.5 seconds of speech within its current 2-second evidence window**. Silence, very quiet audio, heavy noise, or clipping can return insufficient or poor-quality evidence even when the file format is valid.

If you have FFmpeg installed, convert an existing recording with:

```powershell
ffmpeg -i input.mp3 -ac 1 -ar 16000 -c:a pcm_s16le output.wav
```

The app's **Record voice** button makes a compatible WAV automatically. Files uploaded through **Choose a voice recording** must already have the required format.

## Checks

With the Python dependencies and `pytest` installed locally, run:

```powershell
python -m pytest -q
node tests/ui_smoke.cjs
node tests/microphone_smoke.cjs
```

The optional model smoke check uses the downloaded ONNX files. See [model setup](docs/model-setup.md) and the [prototype runbook](docs/prototype-runbook.md) for setup and test details. The API docs are at `http://127.0.0.1:8000/docs`.

## Current limits

Session creation is limited to 60 per minute and only eight WebSockets may wait to authenticate, per backend process. These are local admission limits, not distributed DoS protection. PostgreSQL has no automated retention policy for actions and audit records. The [V04 security review](docs/validation/v04-2026-09-24.md) records the checks and remaining limits.

This is a presentation prototype, not a banking or authentication service. It admits one active audio session per backend worker. The current classifier and thresholds are uncalibrated. The current 40-clip English regression set includes missed synthetic speech and false HIGH blocks; it does not establish accuracy for Hindi, Hinglish, Marathi, phone audio, or replay. Sequenced streaming, bounded browser buffering and server receipt checks passed automated tests. The V03 image completed a 10-minute stream using repeated public WAV audio; the newer V04 image passed a fake-device browser-to-action check. Neither is a physical-microphone trial. Representative evaluation and live Jev measurements remain pending. Runtime numbers and limits are in the [V03 checkpoint](docs/validation/v03-2026-09-24.md).

The [development plan and task ledger](docs/final-development-plan.md) records completed checks, open work, and the October 3, 2026 presentation target. The [evaluation protocol](docs/evaluation-protocol.md), [dataset acquisition review](docs/dataset-acquisition.md), and [source assessment](docs/validation/current-state-and-research-2026-09-24.md) state what has been checked. The [exploratory results](docs/evaluation-report.md) are historical; the September 24 Stage 0 run is in the ignored local `docs/evaluation-output/stage0-2026-09-24/` directory.
