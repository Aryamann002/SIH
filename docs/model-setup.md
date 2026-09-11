# Local audio models

From the project directory, run `python scripts/fetch_models.py`. This downloads approximately 358 MB into `models/`, verifies pinned SHA256 digests, and saves attribution and a manifest. Requests never download weights. Missing weights or inference failures produce `SERVICE_UNAVAILABLE` with no score.

The runtime uses NumPy and ONNX Runtime on CPU; PyTorch is unnecessary. Configure `SILERO_MODEL_PATH` and `SPOOF_MODEL_PATH` when using another directory. Restart the API after changing models because inference sessions are cached.

- Voice activity: [Silero v5.1](https://github.com/snakers4/silero-vad/tree/v5.1), MIT, revision `84768cefdf5a3852400e9d8237f7315d14b64a08`.
- Spoof classifier: [Pranjal Pravesh's INT8 ONNX conversion](https://huggingface.co/pranjal-pravesh/wav2vec2-large-xlsr-deepfake-audio-classification) of [Gustking's trained Wav2Vec2 XLSR classifier](https://huggingface.co/Gustking/wav2vec2-large-xlsr-deepfake-audio-classification), Apache 2.0, revision `4b1c4a294ab68ab444dac038fec8e8da2cc1982f`.

This pretrained classifier replaces the earlier spectral heuristic. It is not the presentation's newly trained frozen WavLM head. Input is normalized mono 16 kHz PCM; output logits use index 1 for synthetic speech. The actual INT8 artifact requires an int32 attention mask, despite its model card describing int64. The adapter reads that type from the artifact.

`AudioPipeline.process_chunk(bytes)` accepts at most four seconds of little-endian PCM16. Routes validate file sample rate/channel headers and call it off the event loop. One pipeline belongs to one audio session; calls must be serialized. Silero recurrent state stays per session. Speech duration and clipping expire with the two-second evidence window. EMA slows score recovery while raw high scores escalate immediately. Audit metadata includes the actual model digest and a digest of policy settings.

## Reproducible speech smoke check

Optional sample preparation needs `soundfile` and `scipy`: `python scripts/fetch_models.py --samples`. Two English clips from [Gary Stafford's dataset](https://huggingface.co/datasets/garystafford/deepfake-audio-detection), CC BY 4.0, are downmixed/resampled to PCM16 WAV. Their original and converted digests, source revision, attribution, and modifications are in `models/manifest.json`.

Run `python -m unittest discover -s tests -p test_audio.py -v`. Set `RUN_MODEL_SMOKE=1` to include local model inference on both clips. Models must already be downloaded.

Observed with default settings and one-second chunks: genuine speech finished LOW at 0.318090, after initial ELEVATED results; synthetic speech finished HIGH at 0.911070. These two clips prove execution and demonstrate a false escalation; they do not establish accuracy. Thresholds, SNR estimation, and scores remain uncalibrated. Indian-language, noisy-channel, replay, and unseen-generator evaluation remain necessary.

The SNR estimate uses RMS of Silero-labelled speech and non-speech. All-speech windows use a minimum noise floor; this can overestimate quality and needs validation against recorded noise. Raw audio buffers remain in memory only. Use the bundled samples for demonstrations without uploading private speech.
