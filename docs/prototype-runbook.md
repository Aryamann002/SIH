# VigilVoice prototype

This is a local, simulated-transfer demo. It does not move money and its voice score does not establish identity.

For rehearsal, use the [current presentation guide](teacher-demo-guide.md) and [saved development plan](final-development-plan.md). The older slides, silent video and exploratory evaluation predate the current streaming build; do not treat them as final evidence.

## Start

```powershell
python scripts/configure_demo.py
docker compose up -d --build
```

Open `http://127.0.0.1:8000/`. The included audio samples are in `models/demo/`.

Wait for `http://127.0.0.1:8000/readyz` to return 200. Chrome/Edge on localhost can **Start live detection**: the AudioWorklet sends authenticated, numbered 200 ms mono 16 kHz PCM16 frames over WebSocket and the risk display updates while capture continues. The **Record voice** fallback records up to 10 seconds and converts to WAV for **Analyze recording**. Upload requires [16 kHz mono signed-16-bit PCM WAV](../README.md#wav-upload-format).

The operator prepares a transfer only after fresh usable evidence. LOW or ELEVATED can request verification but never authorizes completion by itself. Open `/verify` in a separate tab, enter the local verifier key from `.env` privately, review the exact recipient and amount, and use the displayed code in the operator tab. Completion requires a fresh, single-use approval bound to the stored action. HIGH, stale/missing evidence, source change or service failure block it. The verifier is a local demo role, not a true out-of-band channel.

## Checks

```powershell
python -m pytest -q -p no:cacheprovider
node tests/ui_smoke.cjs
node tests/microphone_smoke.cjs
```

Run API/browser scripts only against an isolated test stack; see the [presentation guide](teacher-demo-guide.md). Set `RUN_MODEL_SMOKE=1` for bundled model inference checks. The detector and thresholds are uncalibrated, and the [public-clip quality probe](validation/m04-public-probe-2026-09-24.md) found synthetic misses under noise and simulated band-limiting. Do not present demo clips as accuracy evidence.

## Models

`python scripts/fetch_models.py` downloads and verifies the pinned local models when `models/` is empty. See [model-setup.md](model-setup.md) for licenses, hashes, and known limitations.

For an offline machine, use the preloaded images/models and [offline package instructions](validation/offline-package-2026-09-24.md); normal `--build` may need a package index. The existing V03 archives predate later source changes, so rebuild and rehearse the final package after source freeze.

## Stop

```powershell
docker compose down
```

Do not add `.env` or model files to source control. Existing database records are preserved by `scripts/migrate.py` and `config/migrations/001_protected_actions.sql`.
