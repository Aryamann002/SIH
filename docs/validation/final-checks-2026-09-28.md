# Current-build checks — September 28, 2026

Status: **automated safety, browser, source-export and sustained-stream checks passed; presentation acceptance remains open**. Not multilingual detector validation or a production release.

## Exact scope

Application source was clean commit `c68bc204a9034b9337ce60c1e9d6e1a2eabdf2b2` at session start. No application, model, threshold or authorization code changed. Backend image `sha256:76da2d773d40211451876c653c044deb042cbf1e95408aabc46efeb5d8d83aa5`: all 47 runtime source/config files matched the checkout. Laya image `sha256:1cb195cc18735d9b1dcd408c99896194ec543aba89f8cd5d669f3f8f9dc0d80a`, English revision `55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851`, cached weight SHA256 `891102d372688fc2a094dac56a384bc537b87c63f21f9f3dac0be2b7cbc8d86c` (842,609,210 bytes). Laya remains shadow-only, advisory disabled, CPU/four threads, `HF_HUB_OFFLINE=1`, no published port.

Detector SHA256 `7af799e8443c3d030bb3ef644ffc6e74f5b6fddcd6a4286ee9abe9e828cb762e`, Silero SHA256 `2623a2953f6ff3d2c1e61740c6cdb7168133479b267dfef114a4a3cc5bdd788f`; profile `prototype-uncalibrated-v1:9535b80951b0` unchanged. Windows laptop: 16 logical processors, 31.71 GiB RAM. Docker 29.5.3: 16 CPUs, 16,615,931,904 bytes memory. Host Python 3.13.5; image Python 3.11.16; Node 24.14.1. These are observed resources, not minimum requirements.

Isolated backend `vv-finalcheck-0928-backend` used loopback 59116 and the existing test-only `vv-s02-db` volume. Presentation database and other projects were not restarted, paused or reset.

## Results

| Check | Actual result |
|---|---|
| `python -m pytest -q -p no:cacheprovider --tb=short` | 49 passed, 1 skipped, 26 subtests; 5.46 s |
| `node tests/ui_smoke.cjs`; `node tests/microphone_smoke.cjs` | Both passed |
| `RUN_MODEL_SMOKE=1 python -m unittest discover -s tests -p test_audio.py -v` | All seven passed, including real model execution |
| `docker compose --profile laya config --quiet`; image `python -m pip check` | Passed |
| `python -m scripts.evaluate_laya` | 20 fixtures, zero unsafe downgrades, two escalations, three injected failures/one timeout; no live labels |
| `uvx pip-audit -r requirements.txt --no-deps --disable-pip` | No known advisories; wheel-hash warning. Not an OS/image audit |
| Test image `python scripts/migrate.py` after startup migration | Additive repeat passed |
| Test image `python scripts/check_demo.py --output /tmp/final-checks-20260928.json` | 22/22, 44.073 s; zero unauthorized completions in exercised cases |
| Internal-only network external TCP probe | `ENETUNREACH` 101; internal readiness and 22 checks passed with Laya unreachable. Normal test bridge attached afterward for browser/COMMIT access |
| `python scripts/check_browser.py --base-url http://127.0.0.1:59116/ --action-flow --output <temporary-dir>/browser` | 15 checks; genuine verified completion, retained live HIGH, source replacement denial, synthetic HIGH/BLOCKED, zero JS exceptions; fake audio device |
| Real verification/confirmation/completion COMMIT pauses | All three passed; 503 in 3.50 / 3.45 / 3.45 s; consistent persisted state/audit, safe retry, triggers removed |
| Test image `python scripts/check_commit_ambiguity.py` | All three post-COMMIT timeout cases passed |
| `docker restart vv-finalcheck-0928-backend`, then restart verification | Five recovery checks passed in 3.762 s; observed readiness 4.631 s after restart command returned, not full restart/cold-start latency |
| Read-only presentation and test DB invariants | Zero COMPLETED actions at HIGH/SERVICE_UNAVAILABLE; zero top-level audit keys for OTP/API/session/approval secrets; zero leftover COMMIT test triggers |
| Test image `python scripts/test_client.py --duration-seconds 600` | 2,999 frames/600.17 s, no protocol close; response median 9.07 ms/p95 407.67 ms; first/last-minute medians 9.00/9.08 ms |
| Twelve warmed repeated-public ten-second WAV uploads | Median 5264.625 ms/p95 5321.02 ms; all ELEVATED; latency-only diagnostic, not accuracy |

COMMIT probe reused the guarded helper with only its isolated backend/port selected: `python -c "import scripts.check_commit_boundary as m; m.BACKEND='vv-finalcheck-0928-backend'; m.PORT=59116; m.BASE='http://127.0.0.1:59116/api/v1'; m.main()"`. Its allowlisted DB and runtime host/port checks remained. The verifier key was held only in a process variable, never printed; restart verification deleted its private temporary token file. Reports contain no raw/private audio or plaintext credentials.

Fifteen resource samples during the stream (08:25:04–08:32:32 Asia/Calcutta, roughly every 32 seconds) showed backend 784.5–785.1 MiB and 118.37–289.84% of one logical CPU. Laya sampled 1.914–1.942 GiB and 0.14–20.96% CPU. Sampled maxima are not continuous peaks, a capacity guarantee or physical capture-to-alert timing. The test repeated a public WAV; stable first/last-minute response medians are evidence against growing response delay in this one run, not a general backlog proof.

## Source-export check

`python scripts/package_offline.py --output <temporary-dir>/source-docs-tests.zip`: 158 files, SHA256 `435ae24eafcf2a52834005e4ff6866812a1a2a06f63ab002f728183cc5e59de7`. ZIP integrity passed; no `.env`, WAV, ONNX or safetensors entries. Extracted source passed 49 tests/one skipped/26 subtests, both Node checks and Compose configuration. Extracted `docker build -t vigilvoice-validation:final0928 .` passed; image `sha256:a48d6c922e73af6b701969b9b162575eb90e8b7c7d8ccd4a3e27ad77428fae08`, all 47 runtime files matching checkout; imports and dependency check passed with network disabled. Build used cached pinned dependencies and an available registry, not a pristine offline builder. This application checkpoint predates this receipt/plan update, excludes image/model/video archives, and is **not the final offline bundle**.

## Laya observations and failures

Initial live probe timed out at 1502.44 ms. Six subsequent probes: one safe timeout (1502.62 ms), five `STANDARD_VERIFICATION` replies (1323.39, 1389.94, 1227.15, 1335.83, 1377.46 ms). All six were asserted to remain PENDING. Repeated unlabeled states during a separate stream workload are not representative agreement/failure/calibration measurements. Keep the 1.5-second bound and advisory disabled.

The timed-out background transport emitted `Future exception was never retrieved` with a timeout exception. No secret appeared; fallback was safe. Focused background-future exception retrieval/log hygiene remains a follow-up; no runtime fix was made in this check-only session.

The command runner rejected the SIGKILL drill before execution; ordinary restart was tested instead. The generated restart report's generic “hard backend restart” label is not SIGKILL evidence. An earlier restart verification failed an exact EXPIRED assertion because test audio aged during other checks: the action was safely BLOCKED for stale evidence. A fresh prompt run passed all five without policy change. Initial host-port access on the internal-only network was refused; attaching the normal test bridge enabled it. Diagnostic path/quoting errors were corrected, and a documentation patch with mismatched context was rejected atomically; none is counted as passing evidence.

## Media and remaining gates

HyperFrames skill required CLI pin 0.8.80→0.8.81; `npm run check -- --json` passed: zero errors, 42 existing lint warnings (numeric-leading IDs/missing stable Studio IDs), one transient crossfade overlap info, 16/16 contrast checks. No motion assertion sidecars exist (zero assertions). Timeline remains 22.848 s; all five voice clips resolved. New package pin SHA256 `aeb0257f919eb96bb31263fa21e5c98b39b97caa3bd01ecdfe49e8c884bafc2e`. No MP4 rendered/published.

Seven-page deck and ten-page handbook PDFs each still contain two Jev mentions and no Laya mention; current HTML has no Jev references. Old PDFs/screenshots need regeneration/review. Current isolated HIGH/BLOCKED capture exists, but was not inserted into final media here. Representative public four-language two-class validation, independent lineage/held-out generator, defensible model/threshold selection, untouched test, labeled Laya evaluation, timed physical/offline rehearsals, final media and independent-host offline package acceptance remain open.

## Diagnostic artifacts

Source-export temporary root: `C:\Users\Aryamann Sharma\AppData\Local\Temp\vigilvoice-finalchecks-61c1c0b5d4a14362a72b16ff3dc0f925`. Sanitized [API](final-checks-2026-09-28/api-checks.json), [restart](final-checks-2026-09-28/restart-checks.json), [browser](final-checks-2026-09-28/browser-checks.json), [HIGH/BLOCKED capture](final-checks-2026-09-28/teacher-demo.png) and [performance](final-checks-2026-09-28/performance.json) evidence are retained alongside this receipt; not a release bundle. Performance JSON records the exact repeated-WAV construction and raw timing samples.

| File | SHA256 |
|---|---|
| `api-checks.json` | `f93a6a2aab355cfc26459b0df7e4da9787331cbc140be6360cccb3cbb086a454` |
| `restart-checks.json` | `847f0781309d2efc01a29120b8a30a3abc9b893953ab35cbbd19b21e03f01514` |
| `browser-checks.json` | `e08796e8d8a25814ca4fccf477369017bba94e51b72fbee782350761defd11ca` |
| `teacher-demo.png` | `752053596a14fcb716ea4b43fdf6e11aa9f2961763486d03414ba897e28f2b59` |

Cleanup at 08:38 Asia/Calcutta: isolated backend and test database stopped, database volumes preserved and no test triggers left. Presentation `/readyz` remained 200; presentation backend, DB and cached Laya sidecar remained running. No commit, push, release, external audio upload or advisory promotion occurred. Ruflo memory/policy ledger and local HyperFrames history were updated; generated history files were preserved.
