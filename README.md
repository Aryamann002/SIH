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

Open `http://127.0.0.1:8000/` for the operator screen and `http://127.0.0.1:8000/verify` for the verifier. Keep the `DEMO_VERIFIER_KEY` from `.env` private and enter it only on the verifier screen. Both screens run locally; the verifier is a separate demo role, not an independent delivery channel.

## Try the workflow

1. Start live detection and allow microphone access. The browser sends 200 ms mono PCM frames over an authenticated WebSocket and updates the risk display. You can also record up to 10 seconds and analyze the WAV, or upload a 16 kHz mono, 16-bit PCM WAV file.
2. Prepare a simulated transfer with a recipient and amount. If the audio evidence is usable and the risk is LOW or ELEVATED, request verification. HIGH risk, stale or missing evidence, and service failure block completion.
3. On `/verify`, review the exact recipient and amount using the action ID. Enter the six-digit code on the operator screen and complete the transfer. The code expires after 60 seconds, permits at most three attempts, and can authorize the bound action only once. The audit trail appears below the action.

If a challenge expires or verifier delivery is lost after a restart, create a new transfer. To stop the stack without deleting its database volume, run `docker compose down`.

## Checks

With the Python dependencies and `pytest` installed locally, run:

```powershell
python -m pytest -q
node tests/ui_smoke.cjs
node tests/microphone_smoke.cjs
```

The optional model smoke check uses the downloaded ONNX files. See [model setup](docs/model-setup.md) and the [prototype runbook](docs/prototype-runbook.md) for setup and test details. The API docs are at `http://127.0.0.1:8000/docs`.

## Current limits

This is a presentation prototype, not a banking or authentication service. It admits one active audio session per backend worker. The current classifier and thresholds are uncalibrated. A small English-only exploratory evaluation found both missed synthetic speech and false HIGH blocks; it does not establish accuracy for Hindi, Hinglish, Marathi, phone audio, or replay. Live streaming works in a fake-device browser check, but backlog and freshness controls, physical microphone trials, and full end-to-end presentation checks are still pending.

The [development plan and task ledger](docs/final-development-plan.md) records completed checks, open work, and the October 3, 2026 presentation target. The [evaluation protocol](docs/evaluation-protocol.md) defines the planned dataset and acceptance criteria; the [exploratory results](docs/evaluation-report.md) report what has actually been measured.
