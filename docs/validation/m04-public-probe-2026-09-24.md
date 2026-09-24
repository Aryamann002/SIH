# M04 public-clip quality probe — 2026-09-24

This is a diagnostic on two already-public demo WAVs, **not** a representative accuracy estimate. `python -m scripts.check_quality --output docs/validation/m04-public-probe-2026-09-24.json` passed on host Python 3.13/CPU ONNX Runtime. The script creates deterministic in-memory transformations, feeds them through the deployed `evaluate_wav` path and writes only metadata/results. [All 17 rows](m04-public-probe-2026-09-24.json) SHA256 `52437534494ea5aad09e476330e694f0f1f84216d4a984298bd66f592bbabea1`; script SHA256 `8f41a264da13b6bd40117ba874dc5581f154e11938d87655536260445f126e3a`.

| Condition | Genuine result | Synthetic result |
|---|---|---|
| Clean full clip | ELEVATED, score 0.412686 | HIGH, score 0.756581 |
| −30 dB gain | POOR_QUALITY / `AUDIO_TOO_QUIET` | POOR_QUALITY / `AUDIO_TOO_QUIET` |
| Forced clipping | POOR_QUALITY / `AUDIO_CLIPPING_DETECTED` | POOR_QUALITY / `AUDIO_CLIPPING_DETECTED` |
| Added Gaussian noise, nominal 10 dB full-clip signal/noise ratio | LOW, score 0.169590 | **LOW, score 0.113638** |
| FFT 300–3400 Hz band limit (simulation, not a phone recording) | LOW, score 0.087089 | **LOW, score 0.135760** |
| First 0.5 / 1 s | INSUFFICIENT_EVIDENCE / INSUFFICIENT_EVIDENCE | INSUFFICIENT_EVIDENCE / INSUFFICIENT_EVIDENCE |
| First 2 s | ELEVATED, score 0.527165 | ELEVATED, score 0.704988 |
| First 4 s | ELEVATED, score 0.412686 | Not available: source is only 3.934 s; no padding/looping used |

The synthetic clip's noise and band-limit transformations produced no HIGH alert. LOW still requires action-bound verification; this is a **detector miss**, not evidence of unauthorized action completion. Do not tune the threshold using these known demo clips or call the transformed files independent trials.

The same script was then copied into the **isolated** `vv-v04-backend` (Python 3.11.16, ONNX Runtime 1.30.0, NumPy 2.4.6; `/app/models` mounted from the same local models) and run there. [Docker's 17 rows](m04-docker-probe-2026-09-24.json) SHA256 `9a7ac314cbcc619289b15559bf59a42535e21e76b795114ae9ce1bb584eb3658` had the **same risk states in all 17 conditions** as the host Python 3.13.5/ONNX Runtime 1.26.0 run, though nine exact scores differed slightly. Docker synthetic clean was HIGH 0.756676; added noise was LOW 0.113789; simulated band-limit was LOW 0.134800. This reproduces the miss in the demo runtime, but still only on one synthetic source clip and two artificial transforms. The existing presentation database was untouched.

The noisy synthetic result reported `speech_duration_ms=2000` and `snr_db=57.5`, despite the added noise. Code inspection shows the SNR estimate uses VAD-unvoiced samples as its noise reference; if VAD marks the whole window voiced, it substitutes a `0.0001` RMS floor. That likely inflates reported SNR for this condition. Clean all-voiced speech can produce the same estimator edge case, so rejecting every all-voiced window would also reject good audio. This needs representative noisy genuine/synthetic recordings and a measured quality-rule comparison before any policy change. The FFT filter is not a measured telephone channel. No model, threshold, VAD rule or action gate was changed.

Public source hashes: genuine WAV `442cf79d7c596c7417db8ce25c4ad4c0b0f388c953f82f7b6d803d199bb5e611`, synthetic WAV `08d5a81def7e7a7231bb6e42f5773acd013b074e718a3f6faadb9baa65723337`. Silero ONNX `2623a2953f6ff3d2c1e61740c6cdb7168133479b267dfef114a4cc5bdd788f`; spoof ONNX `7af799e8443c3d030bb3ef644ffc6e74f5b6fddcd6a4286ee9abe9e828cb762e`. Profile and deployed HIGH threshold remained `prototype-uncalibrated-v1:9535b80951b0`/0.75. M04 is IN_PROGRESS, not validated for noisy, phone or replay audio.
