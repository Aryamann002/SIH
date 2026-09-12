# VigilVoice prototype

This is a local, simulated-transfer demo. It does not move money and its voice score does not establish identity.

For a classroom presentation, start with [teacher-demo-guide.md](teacher-demo-guide.md), [the slides](teacher-presentation.pdf), and [the measured evaluation](evaluation-report.md).

## Start

```powershell
python scripts/configure_demo.py
docker compose up -d --build
```

Open `http://127.0.0.1:8000/`. The included audio samples are in `models/demo/`.

Chrome/Edge can record up to 10 seconds from the microphone, preview the converted WAV, and submit it with **Analyze recording**. Use localhost or HTTPS; allow microphone access. This is record-then-analyze input. WAV upload remains available.

The operator creates a session, uploads a 16 kHz mono 16-bit WAV file, prepares a transfer, and requests independent verification. Open `/verify` in a separate tab, enter the local verifier key from `.env`, and use the displayed code in the operator tab. Completion requires the one-time approval token and the exact stored transfer details.

## Checks

```powershell
python -m unittest discover -s tests -p test_audio.py -v
python -m pytest -q
node tests/ui_smoke.cjs
```

Set `RUN_MODEL_SMOKE=1` to run the bundled model inference checks. The detector and thresholds are uncalibrated; do not present the demo clips as accuracy evidence.

## Models

`python scripts/fetch_models.py` downloads and verifies the pinned local models when `models/` is empty. See [model-setup.md](model-setup.md) for licenses, hashes, and known limitations.

## Stop

```powershell
docker compose down
```

Do not add `.env` or model files to source control. Existing database records are preserved by `scripts/migrate.py` and `config/migrations/001_protected_actions.sql`.
