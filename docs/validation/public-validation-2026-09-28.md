# Public detector probes and source-lineage audit — 2026-09-28

These are exploratory regression/challenge checks, **not representative four-language validation, threshold selection or an untouched final test**. Sources, durations and selection methods differ; do not pool their class totals into EER, AUC, precision or recall. The model and safety policy were not changed to fit these results.

## Repeated public-audio checks

Existing scripts were rerun with their fixed release/offset/selection rules. All 72 clips matched the previous run's normalized input hashes, scores and risk states exactly. Input hashes were distinct within each probe. Downloaded synthetic/Monsoon audio remained in memory; the existing public OpenSLR archive was reused without extraction.

| Source and class | Clips | Scorable | HIGH | Insufficient | Quality rejection | Interpretation |
|---|---:|---:|---:|---:|---:|---|
| OpenSLR-104 genuine Hindi–English | 30 | 25 | 5 | 1 | 4 | 5/25 scorable genuine false blocks (20%); exceeds the protocol's observed <=10% bound on this challenge, not a population estimate. |
| Monsoon genuine Indian English | 15 | 11 | 0 | 4 | 0 | Genuine-only challenge; original conversation IDs missing. |
| Monsoon genuine Hindi | 15 | 11 | 0 | 2 | 2 | One ELEVATED, ten LOW; no synthetic class. |
| IndicSynth synthetic Hindi | 4 | 2 | 2 | 1 | 1 | Fixed public row positions, not a representative sample. |
| IndicSynth synthetic Marathi | 4 | 4 | 2 | 0 | 0 | Two scorable synthetic clips ELEVATED, not HIGH. |
| IndicSynth synthetic Punjabi | 4 | 3 | 2 | 0 | 1 | One scorable synthetic clip ELEVATED, not HIGH. |

IndicSynth total: 6/9 scorable clips alerted HIGH; 3/9 scorable synthetic attacks had no HIGH alert. FreeVC24: eight clips, four HIGH, three ELEVATED, one quality rejection. XTTS v2: four clips, two HIGH, one insufficient, one quality rejection. Neither generator is an independent untouched holdout here. Unscorable evidence still prevents action completion; ELEVATED/LOW may request verification but never authenticate a person.

The first Monsoon rerun stopped on a 30-second HTTPS read timeout after the Indian-English rows, before writing a report. One complete retry passed all 30 fixed selections. The failed attempt is not counted as a completed evaluation. Network/FFmpeg timing is excluded; simultaneous probes make inference timing unsuitable as a presentation-host latency benchmark.

### Short-duration and channel check

`scripts/check_quality.py` exercised 17 deterministic variants of the two bundled public English demo clips. Genuine clean was ELEVATED; synthetic clean was HIGH. Both quiet/clipped variants were quality-rejected, and both 0.5/1-second prefixes were insufficient. At two seconds the synthetic prefix was ELEVATED rather than HIGH. Added nominal 10 dB noise and simulated telephone-band filtering changed synthetic HIGH to LOW (scores 0.113638 and 0.135760). This reproduces a material robustness weakness; the current SNR estimate is not a reliable synthetic-detector guarantee for all-speech/noise audio. The synthetic source is shorter than four seconds, so there is no synthetic 4-second result in this 17-row probe. No real replay, partial-spoof span study, representative first-alert distribution or population metric was established.

## Public IndicSUPERB route and overlap

The [official repository at commit `8860e5c39c726186a0a36f2163cf30397f398e0d`](https://github.com/AI4Bharat/indicSUPERB/tree/8860e5c39c726186a0a36f2163cf30397f398e0d) links public object-store files without login/contact-sharing acceptance. Its dataset-packaging terms say CC0; that does not prove every text/reference-voice synthesis permission or clear an unrelated derivative release. The gated Hugging Face Kathbath wrapper is a separate route and was not accepted.

| Public asset | Size | This run |
|---|---:|---|
| [ASV metadata ZIP](https://objectstore.e2enetworks.net/indic-superb/meta_data.zip) | 37,610,028 bytes | Acquired, local ignored archive; SHA256 `1c2064140d199f7729880b5c5c6790d28a70fc168d3f3bc2323d2311f46f60fd`. |
| [Clean test-unknown audio TAR](https://objectstore.e2enetworks.net/indic-superb/kathbath/clean/testunk_audio.tar) | 2,207,580,160 bytes | HEAD/access check only; not acquired. |
| [Normalized transcripts TAR](https://objectstore.e2enetworks.net/indic-superb/kathbath/clean/transcripts_n2w.tar) | 208,998,400 bytes | HEAD/access check only; not acquired. |

Object-store assets are not commit-versioned and have no inspected publisher SHA256; the local hash binds this acquisition, not a verified immutable upstream release. The ZIP contains 120 files with 906,576,554 declared uncompressed bytes. An initial whole-archive 200 MB read-budget assertion correctly refused further reading. The audit then selected only 15 Hindi/Marathi/Punjabi `*_data.txt` members (each <20 MB, combined <230 MB), streamed bounded lines without extracting paths, and read the tiny corresponding speaker lists. These files are ASV pair protocols, not a complete source-recording manifest; no training inventory is present.

Twenty distinct sampled IndicSynth reference filenames had **zero exact filename matches** in those 15 members. Absence from this partial protocol is **not evidence of independence**. Speaker membership did overlap:

- Hindi: reference IDs 1102 in `test_known`; 261 and 323 in `test_known_noisy`.
- Marathi: reference ID 45 in `test_known_noisy`; 1106 and 978 in `valid`.
- Punjabi: reference IDs 180 and 850 in `test_known`; 1119, 180 and 850 in `valid`.

Namespace IDs by corpus **and language**, group both source and target voices plus all reference-derived clips, and resolve actual original recordings before splitting. The known-speaker ASV protocols are not speech-deepfake train/test isolation guarantees. IndicSynth's sampled XTTS rows still lack source references; the metadata acquisition alone cannot build paired genuine/synthetic groups or unblock D02.

Monsoon speaker/segment IDs likewise do not identify the original two-person conversations described in its [collection report](https://huggingface.co/blog/open-asr-leaderboard-global-south); conversation grouping remains unresolved. [BH-Builds/indic-audio at `235908022c0e52fecffeabe347c7eb29f77d7e4f`](https://huggingface.co/datasets/BH-Builds/indic-audio/tree/235908022c0e52fecffeabe347c7eb29f77d7e4f) remains quarantined: the `other` license and service terms do not establish a downstream grant, and designed voice personas do not supply reference-audio/voice lineage. No files or service outputs from that candidate were acquired.

## Source binding and reproduction

Detector: `wav2vec2-xlsr-int8-4b1c4a294ab6:sha256:7af799e8443c3d030bb3ef644ffc6e74f5b6fddcd6a4286ee9abe9e828cb762e`; profile: `prototype-uncalibrated-v1:9535b80951b0`. Host Python 3.13, existing local ONNX/VAD and FFmpeg. Exact source selection/rights and older reports are in the [OpenSLR](d02-openslr104-2026-09-27.md), [Monsoon](d02-monsoon-2026-09-27.md) and [IndicSynth](d02-indicsynth-2026-09-27.md) receipts.

Ignored report SHA256s:

| Filename under `docs/validation/artifacts/datasets/` | SHA256 |
|---|---|
| `openslr104-genuine-probe-2026-09-28.json` | `aa0a3fbf8baa92090a1203faf47f5fc7312b0db1ee545bf8381e9d8639f997c0` |
| `monsoon-genuine-probe-2026-09-28.json` | `8fa73b6b44638146e77d9fc5efad72a5f79107be0c0ca0cd01134560e518f547` |
| `indicsynth-synthetic-probe-2026-09-28.json` | `064be8a1e21cdd786083cab96c39f0e8f664f1345f8248437c0fac8965cd5b1c` |
| `quality-probe-2026-09-28.json` | `52437534494ea5aad09e476330e694f0f1f84216d4a984298bd66f592bbabea1` |

Scripts are unchanged: OpenSLR SHA256 `7f238adef600822e8ebcd3c761220807f722cc6b5491b21de771f83535ee2f2e`; IndicSynth `d1924f549474355bd43052fd8bdb6013752be89d32535ffa012e8805a3a13e7d`; Monsoon `89ed6b1ab1aa646c667c507424c101f7418b697b4b8d30e1acd36a680f485c0a`; quality `8f41a264da13b6bd40117ba874dc5581f154e11938d87655536260445f126e3a`.

Use new output names; the public dataset probes refuse overwrites:

```powershell
python -m scripts.probe_openslr104 docs/validation/artifacts/datasets/Hindi-English_test.tar.gz --output docs/validation/artifacts/datasets/openslr104-rerun.json
python -m scripts.probe_indicsynth --output docs/validation/artifacts/datasets/indicsynth-rerun.json
python -m scripts.probe_monsoon --output docs/validation/artifacts/datasets/monsoon-rerun.json
python -m scripts.check_quality --output docs/validation/artifacts/datasets/quality-rerun.json
```

To reproduce the metadata audit, verify the ZIP hash above, iterate the three languages' `*_data.txt` members with stdlib `zipfile.ZipFile.open`, match each tab-separated pair's path basename to the sampled IndicSynth `source_reference_audio`/`target_reference_audio`, then compare reference speaker IDs to the language-local `*_speaker_ids.txt` sets. Do not extract absolute paths or treat a failed filename join as disjointness.

## Decision

D02/M03 remain blocked: both classes with cleared rights and original-source lineage, Indian-English/Hinglish synthetic coverage, audible code-switch review, and held-out-generator isolation are missing. Existing-model robustness/false-block targets are not met on the exercised challenges. Do not weaken gates, tune on these exposed probes, synthesize unlicensed reference voices, train a replacement on leaky data or claim final test success. Keep the current model explicitly uncalibrated for the simulated demonstration and defer replacement until a defensible corpus is available.
