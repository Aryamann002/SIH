# Public IndicSynth synthetic-only probe — 2026-09-27

This is a 12-clip **exploratory development check**, not representative four-language validation, a threshold-selection set or an untouched final test. The [publisher card](https://huggingface.co/datasets/vdivyasharma/IndicSynth) declares CC BY-NC 4.0 and says its genuine source/target references come from [IndicSUPERB](https://github.com/AI4Bharat/indicSUPERB), whose published dataset-packaging terms are CC0. No audio or generated result is cleared here for redistribution or commercial use; upstream raw-text and voice-use rights were not independently audited. Only public ungated viewer rows were used. No gated terms, private voices or voice-generation service were used.

`scripts/probe_indicsynth.py` pins Hugging Face revision `c0a10386b723717aff682f757bd67f72983f269f`, checks the release is still public/ungated, requires each asset URL to contain that revision and the expected language/row, and limits each fetch to 10 MB. Four offsets per language were fixed from metadata **before scoring**: Hindi `0,67959,135918,195640`; Marathi `0,42949,85898,123641`; Punjabi `0,81956,163912,235935`. These are evenly spread *positions*, not a random, speaker-balanced or source-recording-disjoint selection. They include FreeVC24 and XTTS v2, but no independent held-out generator. FreeVC rows expose source and target reference filenames/speaker IDs; XTTS rows in this sample lack source speaker/reference fields. Cross-dataset/pretraining overlap remains unverified.

One inspection WAV was temporarily downloaded: 210,284 bytes, SHA256 `4e3db7f7327627c935ac31c4077844b6440749f943482bc5bedfb65204c604b0`, mono 24 kHz PCM16, 4.38 s. It was deleted after format inspection. The probe itself holds source audio in memory, accepts bounded mono PCM16 or IEEE-float WAV (the first run failed on a float WAV before producing a report), converts with local FFmpeg to mono 16 kHz PCM16 in memory, and calls the unchanged `evaluate_wav` upload path. It writes no audio, signed asset URL, transcript, OTP or private data. Its ignored metadata-only JSON is `docs/validation/artifacts/datasets/indicsynth-synthetic-probe-2026-09-27.json`, SHA256 `26ea7dfda754f8dca7a09e0e4a0428a5e2c1a4b6b98091b6653a917ac603ba87`; script SHA256 `d1924f549474355bd43052fd8bdb6013752be89d32535ffa012e8805a3a13e7d`. All 12 source and normalized-audio hashes are distinct. Run environment: Windows host, Python 3.13.5, FFmpeg 8.1, local ONNX model `wav2vec2-xlsr-int8-4b1c4a294ab6:sha256:7af799e8443c3d030bb3ef644ffc6e74f5b6fddcd6a4286ee9abe9e828cb762e`, profile `prototype-uncalibrated-v1:9535b80951b0`.

| Language | HIGH | ELEVATED | Insufficient evidence | Poor quality |
|---|---:|---:|---:|---:|
| Hindi | 2 | 0 | 1 | 1 |
| Marathi | 2 | 2 | 0 | 0 |
| Punjabi | 2 | 1 | 0 | 1 |
| **Total** | **6** | **3** | **1** | **2** |

Nine of twelve clips were scorable (LOW/ELEVATED/HIGH), and **6/9** had a HIGH alert. The other **3/9 scorable synthetic clips were ELEVATED**, not HIGH. The three unscorable clips remain fail-closed under the backend policy: Hindi XTTS row 135918 lacked sufficient speech, Hindi XTTS row 195640 had low SNR, and Punjabi FreeVC row 81956 triggered clipping. All sources were 24 kHz and 4.38–12.39 s long; the probe normalized them before the 16 kHz upload path. The 12 warm-host upload-path latencies ranged **2.783–10.124 s** (mean 7.177 s); source download and FFmpeg time are excluded. These figures cannot be directly combined with the exact four-second OpenSLR-104 genuine probe: source, duration, content, channel and selection differ. They do not establish precision, recall by language, held-out-generator performance or a safe threshold.

Reproduce from the exact public release while it remains available, with local models and FFmpeg installed; use a **new** ignored output filename because the command refuses overwrite:

```powershell
python -m pytest -q -p no:cacheprovider tests/test_probe_indicsynth.py
python -m scripts.probe_indicsynth --output docs/validation/artifacts/datasets/indicsynth-synthetic-probe-rerun.json
```

Focused tests first failed on the missing module, then passed 2/2. The first network run stopped after roughly two minutes on IEEE-float WAV format code 3 and wrote no report. A float-WAV regression test failed on the old converter, then passed with a bounded RIFF parser plus FFmpeg normalization. No backend, model weights, threshold, quality gate, audit path, presentation database or Jev mode changed. Next: inspect source/target ancestry and rights at a pinned revision; source/speaker-disjoint selection and independent public genuine/synthetic data for Indian English and Hinglish are still required before D02/M03 can advance.

After the boundary tests were added, the full checkout passed **45 Python tests, 1 skipped, 26 subtests**, both Node UI/microphone smoke suites, and `git diff --check`; the running demo's `/readyz` returned 200. These are code/regression checks, not representative detector-accuracy evidence. The report and source WAVs are excluded from Git by `docs/validation/artifacts/.gitignore`.
