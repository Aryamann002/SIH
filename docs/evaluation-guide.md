# Reproduce the exploratory audio evaluation

This evaluates the existing pretrained detector; it does not train a model, calibrate a fraud probability, or change application thresholds. Present it as an engineering prototype with measured limitations.

## Prepare the pinned corpus

From the repository directory, use a Python environment with NumPy, SoundFile and SciPy:

```powershell
python scripts/prepare_evaluation.py
```

The script downloads 40 complete English clips from [Gary Stafford's Deepfake Audio Detection Dataset v4](https://huggingface.co/datasets/garystafford/deepfake-audio-detection/tree/fcf5344bb7f82b54b6b932291326d29750ef1e82), pinned revision `fcf5344bb7f82b54b6b932291326d29750ef1e82`. Attribution: Gary Stafford; license CC BY 4.0. Files are converted to mono 16 kHz PCM16 WAV. Source SHA256 digests are verified against the pinned Hub listing; converted-file hashes and source URLs are recorded in `models/evaluation/manifest.csv`. Download limit: 100 MiB. The complete dataset card and preparation provenance are saved beside the files.

Selection is deterministic: 10 genuine and 10 spoof clips for validation, another 10 of each for test. Source-recording filename groups never cross splits; synthetic provider prefixes also stay in one split. The existing demo source recordings are excluded. This grouping does **not** verify speaker or transcript independence, or overlap with the pretrained model's training data. It is a small English-only corpus, not a representative Indian-language, replay, or telephone benchmark.

The public [Hugging Face Hub API](https://huggingface.co/docs/hub/api) supplies the pinned repository tree and source digests. No API key or paid service is required.

## Run the same inference as WAV upload

After `docker compose up -d --build`, run evaluation in the backend's Python environment. The existing models and code are mounted; no server credentials are needed:

```powershell
docker compose run --rm --no-deps --entrypoint python -v "${PWD}:/workspace" -w /workspace backend scripts/evaluate_audio.py models/evaluation/manifest.csv --output docs/evaluation-output
```

Alternatively, a compatible local Python environment with the repository dependencies can run:

```powershell
python scripts/evaluate_audio.py models/evaluation/manifest.csv --output docs/evaluation-output
python -m unittest discover -s tests -p test_evaluation.py -v
```

The evaluator calls the actual upload function `evaluate_wav`: identical WAV validation, 0.2-second chunks, VAD state, quality gates, EMA and whole-file risk retention. It captures real chunk results while preserving the default endpoint decision. Cold model loading is measured separately from file latency. Run this while the demo is idle because inference shares CPU resources.

## Read the evidence correctly

- `docs/evaluation-output/report.md`: teacher-readable results and limitations.
- `docs/evaluation-output/report.json`: confusion counts, denominators, quality/service rejection counts, model digests, source hashes, active profile and latency.
- `docs/evaluation-output/results.json`: every file, label, split, digest, default risk, maximum chunk score and elapsed time.

**FAR** here means spoof clips still eligible for independent OTP divided by scorable spoof clips. **FRR** means genuine clips blocked as HIGH divided by scorable genuine clips. Quality failures and unavailable service are shown separately and excluded from those denominators; they must never disappear into an apparent accuracy improvement. Eligible for OTP does not mean a transaction completed.

The candidate HIGH threshold is chosen on validation only: minimum balanced error over a 0.01 grid at or above the existing elevated threshold; ties favor lower FAR, then lower threshold. It is frozen before reporting test metrics. Offline replay compares the maximum chunk score with this threshold while retaining the original quality/service disposition. The default application's exact returned risk is reported independently. The candidate is **not deployed**, and small validation results do not justify deployment.

For another dataset, supply `path,label,split,group,sha256` CSV columns; paths must be relative to the CSV directory. Labels are `genuine` or `spoof`, splits `validation` or `test`; each split needs both classes. Group all recordings from the same source together and keep related augmentations in that group. The loader rejects path escapes, changed files, duplicate file/PCM contents and groups crossing splits. Perceptual near-duplicates still require dataset review.

Before making accuracy claims, expand the held-out corpus to consented Indian-language speakers, actual replay attacks, phone channels, background noise and generators absent from training. Predefine the acceptable missed-attack and false-block tradeoff; keep test data untouched during tuning. Current score values remain model outputs, not verified fraud probabilities.
