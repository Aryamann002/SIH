# Offline demo package checkpoint — 2026-09-24

This local package is a tested checkpoint, **not** the final September 30 release. The `v03` source ZIP and backend tar below include the S03 browser and V02 upload-admission fixes; the unsuffixed source ZIP/backend tar in the same folder are superseded and must not be used as the current build. Regenerate and retest after final source freeze. The large image/model archives under `docs/validation/artifacts/` are intentionally ignored by Git; they must be copied separately. No API key, `.env`, private audio or OTP is included. The bundled demo WAVs are the two public CC-BY-4.0 examples named and attributed in `models/manifest.json`.

| Local artifact | Purpose | SHA256 |
|---|---|---|
| `offline-source-v03-2026-09-24.zip` | App, scripts, config, Compose, Dockerfile and README; 44 files, 82,405 bytes | `0e07a0cc96536161b3594c861bae9776cebaf33ed7fde7e46541f1ab39eb722e` |
| `vigilvoice-backend-v03-2026-09-24.tar` | Prebuilt Python 3.11 backend image, tag `vigilvoice:local`, image ID `sha256:136591533727ec788a0e6365adf395ceefe562c3e856637b8ec36efa0f51c2d4`; 115,606,528 bytes | `212ecb9fc6662640189ece3894921241029022e1c1955ef49f357147c5cde9fb` |
| `postgres-16-alpine-2026-09-24.tar` | Local PostgreSQL image, tag `postgres:16-alpine` | `3e0a8f06b46ffb54b8e2b54389215960043fffbc7fc56b151f24d1baba61fb24` |
| `runtime-models-2026-09-24.zip` | Two ONNX models, license/card files, manifest and public demo WAVs | `9314741498067ea09fbcc4fe1eea201c7d363769ad96ea3990d1f7c941363c77` |

On an offline Windows machine with Docker Desktop/Compose and Python 3.11 already installed, copy those four files to a local folder. Verify each hash with `Get-FileHash -Algorithm SHA256` before extraction/loading. Then, from that folder:

```powershell
Expand-Archive .\offline-source-v03-2026-09-24.zip .\VigilVoice
Expand-Archive .\runtime-models-2026-09-24.zip .\VigilVoice
docker load -i .\vigilvoice-backend-v03-2026-09-24.tar
docker load -i .\postgres-16-alpine-2026-09-24.tar
Set-Location .\VigilVoice
python scripts/configure_demo.py
docker compose up -d --no-build --pull never
```

`configure_demo.py` creates a new ignored `.env` locally; it does not ship credentials. On a machine with an existing VigilVoice database, preserve that machine's `.env` and database volume. Do not overwrite either with files from this package. Check `http://127.0.0.1:8000/readyz` for HTTP 200, then use the operator and verifier pages as described in `README.md`. Jev is optional: with no key it falls back to deterministic local policy; `JEV_MODE=disabled` can be set in `.env` to guarantee no external request attempts.

The new backend tar reloaded into the same daemon with the expected image ID. The new source ZIP extracted to 44 byte-for-byte matching staged files, with no `.env`, WAV, ONNX, PDF or tar inside. Its Compose config validated with test-only placeholder credentials; the separately unchanged model ZIP previously matched both ONNX and public WAV hashes. The exact new backend image passed 20/20 local API/action checks on a Docker `--internal` network with no Internet route (`ENETUNREACH` 101). The temporary offline test container/network were removed; the isolated test database and original demo stack were preserved. A second pristine Docker host and an exact Compose launch from these archives have **not** been tested; neither has a physical microphone rehearsal. The source ZIP contains runtime files and README, not its linked `docs/` tree; use the repository for those references. Neither model is included in Git.
