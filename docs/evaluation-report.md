# VigilVoice: exploratory evaluation for the teacher demo

**The workflow is demonstrable; detector reliability still needs broader validation.** We evaluated the existing pretrained detector on 40 public English clips. This is neither new model training nor a representative accuracy certification.

## Data and method

The corpus has 20 genuine and 20 synthetic clips: 10 of each for validation and another 10 of each for test. The two original demonstration sources were excluded. Source-recording filename groups and synthetic provider prefixes are separated between partitions; speaker/transcript independence and overlap with pretrained training data remain unverified.

Source: [Gary Stafford's Deepfake Audio Detection Dataset v4](https://huggingface.co/datasets/garystafford/deepfake-audio-detection/tree/fcf5344bb7f82b54b6b932291326d29750ef1e82), CC BY 4.0. Revision: `fcf5344bb7f82b54b6b932291326d29750ef1e82`. Modification: full clips downmixed/resampled to 16 kHz mono PCM16 WAV. Each source and converted file has a SHA256 digest in `models/evaluation/manifest.csv`.

Evaluation calls the same `evaluate_wav` decoder, 0.2-second chunks, VAD/quality gates, smoothing, and whole-file decision used by uploads. It runs offline without the HTTP timeout/database wrapper. A lower HIGH threshold was selected using validation balanced error only, then frozen for test. It is an offline sensitivity experiment and **has not changed the running app**.

## Results

“Spoof eligible” means the voice gate permits proceeding to independent verification. It does not mean a transaction succeeded. Quality rejections and unavailable results are excluded from the two scorable denominators and listed separately.

| Setting | Scorable / total | Spoof eligible / scorable spoof | Genuine HIGH false blocks / scorable genuine | Quality rejected | Service unavailable |
|---|---:|---:|---:|---:|---:|
| Default 0.75 — validation | 17 / 20 | 4 / 10 (40.0%) | 1 / 7 (14.3%) | 3 / 20 | 0 |
| Default 0.75 — test | 18 / 20 | 1 / 9 (11.1%) | 1 / 9 (11.1%) | 2 / 20 | 0 |
| Candidate 0.58 — validation | 17 / 20 | 1 / 10 (10.0%) | 2 / 7 (28.6%) | 3 / 20 | 0 |
| Frozen candidate 0.58 — test | 18 / 20 | 0 / 9 (0.0%) | 3 / 9 (33.3%) | 2 / 20 | 0 |

For the default test partition, 8 of 10 genuine files could proceed to verification; 1 was blocked as HIGH and 1 rejected for quality. Of 10 synthetic files, 8 were blocked as HIGH, 1 rejected for quality, and 1 could proceed to verification. These are small counts; **0/9 on the candidate is not evidence of a zero real-world miss rate**.

The candidate catches more synthetic examples at the cost of more genuine false blocks. The application keeps its default HIGH threshold of 0.75. Neither threshold is validated for production, and the model score is not a calibrated fraud probability.

## Timing and engineering checks

Offline inference over the 40 full files: median **3.06 seconds**, p95 **7.79 seconds**, model loading **7.07 seconds**. This is CPU file inference on the local machine, excludes HTTP/database overhead, and does not establish first-alert streaming latency. The live API has a 10-second inference timeout; use short rehearsed clips for class.

The running backend passed **13 check groups**, including real-model availability, session isolation, exact action binding, concurrent single-use completion, OTP lockout/expiry, approval expiry, stale evidence, high-risk replacement, invalid audio, silence/clipping, and WebSocket disconnect. Expiry tests adjust only records created by that check. These tests establish those behaviors, not comprehensive security certification. See [demo-checks.json](demo-checks.json).

The browser check uses a fake microphone WAV through native Chrome recording, conversion, preview and actual backend upload; it also checks JavaScript errors and mobile overflow. See [browser-checks.json](browser-checks.json). A physical microphone and user permission prompts still require manual rehearsal.

## What remains unproven

- Indian-language speech, actual replay recordings, telephone channels, and added background noise.
- Speaker/transcript independence and generators absent from the pretrained model's training data.
- Calibrated probabilities and thresholds chosen against a target operational error cost.
- Physical microphone performance, multi-user throughput, streaming alert latency, field performance, and real delivery/payment integration.

## Reproduction and provenance

Use [evaluation-guide.md](evaluation-guide.md). The complete generated [report](evaluation-output/report.json) and [per-clip results](evaluation-output/results.json) are retained locally. The report hashes bind the evaluation worker's isolated snapshot, models, policy profile and manifest; final integration includes unrelated browser/action changes. Compare hashes for the inference modules to verify they match the evaluated implementation. The final teacher-build receipt records the integrated source separately.

Model sources and licenses are in [model-setup.md](model-setup.md). No private voice recordings, API keys or paid services were used to prepare this public sample corpus.
