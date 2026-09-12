# Presenting VigilVoice to teachers

Open [teacher-presentation.pdf](teacher-presentation.pdf) for the slides and `http://127.0.0.1:8000/` for the live app. Keep [vigilvoice-teacher-walkthrough.mp4](vigilvoice-teacher-walkthrough.mp4) as the silent 30-second fallback walkthrough.

## What to say first

“VigilVoice is a working local prototype that combines a pretrained voice-spoof detector with an action approval policy. Voice evidence alone never authorizes a transfer. A separate verification step must approve the exact recipient and amount. The transfer and delivery channel are simulated.”

We integrated existing pretrained Silero VAD and Wav2Vec2 XLSR models. We did not train those models. The contribution demonstrated here is the guarded workflow, quality handling, action binding, expiry, and audit trail.

## Before class

From the project folder, with Docker Desktop running:

```powershell
python scripts/configure_demo.py
docker compose up -d --build
```

If weights are missing, first follow [model-setup.md](model-setup.md). Model download needs internet; the running detector does not download weights. Keep both `models/demo/genuine.wav` and `models/demo/synthetic.wav` available.

Use Chrome or Edge at `http://127.0.0.1:8000/`. Allow microphone access when prompted. The microphone records up to 10 seconds, converts to WAV, and waits for you to click **Analyze recording**. This is recorded-audio analysis, not continuous live detection. WAV upload is the rehearsal fallback.

Open the verifier at `http://127.0.0.1:8000/verify` before projecting. Give the verifier the `DEMO_VERIFIER_KEY` from your local `.env` privately. Do not display or share the `.env` file. A second person can play the verifier role on the same laptop; this illustrates the workflow but does not create a real independent authentication channel.

If you are presenting alone, the local verifier helper avoids copying the long verifier key:

```powershell
python scripts/demo_inbox.py <action-id>
```

It displays the simulated recipient, amount, and code. Explain that this is demo delivery.

## Five-minute demonstration

1. **Problem (30 seconds):** “A familiar-sounding voice can influence an operator. We separate the audio signal from permission to act.”
2. **Recorded speech (45 seconds):** Upload `genuine.wav` and analyze. Explain the score, speech duration, quality checks, and reason codes. LOW or ELEVATED still requires verification. The supplied genuine example can be ELEVATED; that is a useful limitation to show honestly.
3. **Protected action (90 seconds):** Prepare a small simulated transfer, request its verification code, share the action ID with the verifier, review the recipient and amount, enter the code, and complete. Show the persisted audit events. No money moves. Complete promptly: file evidence lasts 120 seconds; code and approval each last 60 seconds.
4. **Attack example (45 seconds):** Choose **New transfer**, upload `synthetic.wav`, and analyze. It should produce HIGH under the current model/settings. Prepare another transfer and show BLOCKED. A score is not proof of malicious intent or speaker identity.
5. **Your microphone (30 seconds):** Record 3–10 seconds of clear speech, stop, preview, and analyze. Accept whatever result appears; do not label a false alarm as correct detection. Poor quality should ask for better evidence.
6. **Evidence and limits (60 seconds):** Show the evaluation slide and [evaluation report](evaluation-report.md). Explain the sample counts, quality rejections, missed synthetic clips, and false blocks. Show [backend check results](demo-checks.json) if asked about prevention behavior.

## If something fails during class

| What you see | What to do |
|---|---|
| Microphone unavailable or denied | Allow access in browser settings or use the bundled WAVs. |
| Poor quality / insufficient evidence | Record clear uninterrupted speech, or use the known WAV for the workflow demo. |
| Expired evidence | Analyze audio again. If the action was blocked/expired, choose New transfer. |
| Expired OTP / approval | Create a new transfer and request verification again. Reissuing cannot reset a used/expired challenge. |
| Backend/model unavailable | Check `docker compose ps` and the model setup. Use the PDF, walkthrough video, and `teacher-demo.png` if startup cannot be recovered. |
| Personal speech marked HIGH | Explain that this is a measured limitation of the uncalibrated detector; do not bypass the block to make the demo look successful. |

## Answers to likely questions

**Did you train the AI?** No. We integrated third-party pretrained models and built/evaluated the workflow around them.

**What does the score mean?** A synthetic-speech model output used by a threshold policy. It is not a calibrated fraud probability or an identity check.

**How accurate is it?** Use the attached exploratory report with its denominators. The public 40-clip corpus is small, and overlap with the pretrained model's training data is unknown. It does not establish Indian-language, replay, telephone, or real-world accuracy.

**What does “accepted synthetic” mean in the report?** It means the voice gate did not block that synthetic clip. Independent verification is still required; it does not mean a fraudulent transaction succeeded.

**Why show imperfect results?** They identify where quality handling, threshold selection, and target-domain data need improvement. A teacher should be able to distinguish working engineering from unproven ML claims.

**Does it scale?** The API/database separation and recorded model/policy versions support further development. The current single CPU inference slot and in-memory verifier have explicit limits; multi-user capacity has not been validated.

**What comes next?** Collect consented Indian-language and phone/replay recordings, evaluate with speaker/source-separated splits, calibrate thresholds, improve or fine-tune the detector if justified, then add trusted delivery, accounts, HTTPS hosting, and measured concurrency.

## Reproduce the checks

```powershell
python -m pytest -q
node tests/ui_smoke.cjs
node tests/microphone_smoke.cjs
docker compose exec -T backend python scripts/check_demo.py --output /tmp/demo-checks.json
docker cp vigilvoice_backend:/tmp/demo-checks.json docs/demo-checks.json
python scripts/check_browser.py
```

The API check creates fresh simulated sessions/actions, shifts expiry only for its own test rows, and preserves existing records. Browser checks use a fake microphone device; rehearse once with the laptop's real microphone. Reproduce the dataset experiment using [evaluation-guide.md](evaluation-guide.md).

## Presentation boundaries relative to the SIH PDF

Demonstrated: audio input, real pretrained inference, quality gate, threshold policy, independent-verifier simulation, action-bound one-time approval, fail-closed behavior, and audit/dashboard.

Pending: team-trained frozen SSL head, representative Indian-language validation, calibrated production thresholds/probabilities, real SMS/payment integration, continuous browser streaming, dedicated replay robustness, field trials, and load testing. Do not repeat the original slides' “already evaluated” language for these pending items.
