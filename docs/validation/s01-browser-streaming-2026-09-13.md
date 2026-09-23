# S01 continuous browser streaming receipt

Date: 2026-09-13 23:12 Asia/Calcutta

Result: **PASS**. Chrome captured the fake microphone through a native 16 kHz AudioWorklet, authenticated a same-origin WebSocket before sending audio, received eight risk updates while capture remained active, reached 1.5 seconds of speech and LOW detector output, stopped safely, then completed the existing recorded-WAV fallback.

## Source and runtime

- Baseline commit: `b84593ec32b10d774bee266a3d09ea2434096b92` (`B05 DONE`); S01 remains an uncommitted reviewable patch.
- Backend image: `sha256:f636ae6f920d3c8ac27cd26c1868d3c65fc6247298bff08390ce670c41207aef`.
- Runtime: Python 3.11.16, FastAPI 0.141.1, SQLAlchemy 2.0.52, asyncpg 0.31.0 and ONNX Runtime 1.30.0. Browser: Chrome 152.0.7977.83. Hardware: 13th Gen Intel Core i5-13450HX with 34,053,414,912 bytes RAM.
- Models/profile: `wav2vec2-xlsr-int8-4b1c4a294ab6` SHA256 `7af799e8443c3d030bb3ef644ffc6e74f5b6fddcd6a4286ee9abe9e828cb762e`; `silero-v5.1` SHA256 `2623a2953f6ff3d2c1e61740c6cdb7168133479b267dfef114a4a3cc5bdd788f`; `prototype-uncalibrated-v1`.
- Exact source SHA256: `pcm-worklet.js` `06fffddb280e586b2e4a35e23edf6a35cb80aacadb49747ceded977320231327`; `microphone.js` `b74a367a846b056c2510b04370a89cb24ae0f4280309db3a820a13887e93b45f`; `app.js` `551c382420d098b0f930a3810f501d15303f3db7f918fbeedbc10eb8fb35227a`; `index.html` `c4e1a0ed0e693043d80357f3a9362a3a09e669cdd4e35705216bf7c5b9ed1619`; `stream.py` `ccefd0cdf0a31dfa5b08c6178854047ddf982e39fddd370f08cc68968f875f89`; `test_client.py` `f66749923034c1d40f92564ca5af146749b5b80b4d692ea3f69af7cd1ba4839b`; `check_demo.py` `c23e8bda7b494a0c569a2247f625b371456b25b39c925d879e217a53bfc04f93`; `check_browser.py` `5684ee8ba1c090885e5a6ac74c5e63f8ad8bbcd315a860f8c28cb0e143020858`; `microphone_smoke.cjs` `cff404bb37319c58f9a039d5f14c760668ee8ca711e2db9f80a24bf59ab3622b`; `ui_smoke.cjs` `aa86618745397f97f884d6fc0d7258b86a39181672808b7ba46c738bfe2fcb78`.

## Implemented contract

- Browser requests raw mono microphone input and `AudioContext({sampleRate: 16000})`; it rejects a browser that cannot supply the requested native rate.
- AudioWorklet downmixes channels and emits one transferable 6,400-byte PCM16 frame per 3,200 samples, a 200 ms cadence.
- Microphone permission and capture graph setup finish before opening the WebSocket. The session token is the first JSON text frame. Capture starts only after the server returns the matching `ready` frame.
- Stream results reuse the existing risk renderer while capture continues. Stop, device loss, socket loss, startup error and page exit release tracks, worklet nodes, AudioContext and WebSocket. WAV recording/upload remains available as fallback.
- Backend now rejects binary or malformed first frames with policy close 1008 instead of reporting an internal failure. The repaired manual client creates a registered session, authenticates, awaits `ready`, and streams a real WAV in 200 ms frames.

## Checks

- `python -m pytest -q -p no:cacheprovider`: 23 passed, 1 optional model smoke skipped, 26 subtests passed; one third-party `python_multipart` pending-deprecation warning.
- `node tests/microphone_smoke.cjs`: passed PCM/WAV plus AudioWorklet 6,400-byte framing, native-rate request, ready gate and idempotent cleanup.
- `node tests/ui_smoke.cjs`: passed token-first/ready-before-PCM wiring, live result rendering during capture, safe stop and unchanged protected-action/WAV contracts.
- Rebuilt-stack `scripts/check_demo.py`: 15/15 groups passed. Real WAV PCM reached live inference; binary-first auth failed with WebSocket 1008; disconnect invalidated evidence. [Machine receipt](s01-demo-checks-2026-09-13.json), SHA256 `ba9d8961959552852e3b0b19b1730095c280a8e6246dd21169f8b8aed8097a6e`.
- `python scripts/test_client.py`: 24 authenticated 200 ms frames completed; first scorable detector result arrived at frame 9 and the stream ended LOW with 2,000 ms speech evidence.
- Headless Chrome fake-device check: eight live updates while capture stayed ready, LOW at 1.5 seconds speech, safe stop, WAV recording/upload LOW, no JavaScript exceptions and no 390 px overflow. [Browser receipt](s01-browser/browser-checks.json), SHA256 `64710cd94ac539813d6ff4d79301f70383dff6ca90a50e047bf3e0985c22c9a1`; [screenshot](s01-browser/teacher-demo.png), SHA256 `bc36559ed8f28d79ab45f4b315d9331f935e2a8b5831d964b1725a1e8e382afa`.
- `python -m compileall -q app scripts tests`, `git diff --check`, visual screenshot inspection and final `/readyz`: passed. Existing PostgreSQL data and volume were preserved.

## Scope

S01 proves capture, authentication, framing and live inference. It intentionally adds no reconnect queue, sequence protocol or backpressure policy. S02 must bound browser/server backlog, distinguish capture time from processing time and prevent delayed or replayed frames from refreshing evidence. Physical microphone and OS permission interaction remain V03/R03 rehearsal work.
