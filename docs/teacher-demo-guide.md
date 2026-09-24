# Presenting VigilVoice

This is a rehearsal guide for the current local prototype, not a claim that the final October 3 presentation build is frozen. Open `http://127.0.0.1:8000/` for the operator and `/verify` for the local verifier. The [older slides](teacher-presentation.pdf) and [silent walkthrough](vigilvoice-teacher-walkthrough.mp4) predate continuous streaming; do not present them as current-build proof. Refresh both under R02 after the final source is frozen.

## What to say first

“VigilVoice is a working local prototype that combines a pretrained voice-spoof detector with an action approval policy. Voice evidence alone never authorizes a transfer. A separate verification step must approve the exact recipient and amount. The transfer and delivery channel are simulated.”

The local pipeline uses pretrained Silero VAD and an INT8 Wav2Vec2/XLS-R classifier. We did not train those models. The demonstrated contribution is continuous monitoring joined to a guarded, action-bound verification and audit workflow. The detector is not a speaker-identity check.

## Before presenting

From the project folder, with Docker Desktop running:

```powershell
python scripts/configure_demo.py
docker compose up -d --build
```

If weights are missing, first follow [model-setup.md](model-setup.md). Model download needs internet; the running detector does not. For the offline handoff, use preloaded images/models and the [offline package instructions](validation/offline-package-2026-09-24.md) with `docker compose up -d --no-build --pull never`. Those archives are a V03 checkpoint, not the final V04+ source. Keep both public demo WAVs available. Check `http://127.0.0.1:8000/readyz` returns 200 before opening the app; `/healthz` alone does not prove DB/model readiness.

Use Chrome or Edge on localhost. **Start live detection** sends authenticated, sequenced 200 ms mono PCM16 frames to the backend and refreshes risk as speech arrives. **Stop live detection** makes the current stream evidence unavailable; do not try to complete an old action from it. **Record voice** still makes a compatible WAV of up to 10 seconds for record-then-analyze fallback. Upload accepts only the [specified PCM WAV format](../README.md#wav-upload-format).

Open the verifier at `http://127.0.0.1:8000/verify` before projecting. Give the verifier the `DEMO_VERIFIER_KEY` from your local `.env` privately. Do not display or share the `.env` file. A second person can play the verifier role on the same laptop; this illustrates the workflow but does not create a real independent authentication channel.

If you are presenting alone, the local verifier helper avoids copying the long verifier key:

```powershell
python scripts/demo_inbox.py <action-id>
```

It displays the simulated recipient, amount, and code. Explain that this is demo delivery.

## Six-case rehearsal script

Keep the operator and verifier on separate screens. Cases 1–3 are the live audience path; cases 4–6 are safety/limitation checkpoints. Rehearse the timing and record actual results on the presentation laptop. Never replace an unexpected result with a claim that the model was correct.

1. **Live microphone:** Start live detection and speak clearly for several seconds. Point to the updating risk, speech duration, reason codes and evidence age. State the observed risk, not a promised LOW result. If microphone access fails, say so and use WAV fallback; the fake-device browser test is not a physical-mic rehearsal.
2. **Eligible speech still needs verification:** Stop the stream, upload `models/demo/genuine.wav`, and analyze. It was ELEVATED in the September 24 public-clip probe, which remains eligible for verification but is not an identity verdict. Prepare a small simulated transfer. The local verifier reviews the exact recipient, amount and action ID; request the code, enter it, complete once and show the `ACTION_COMPLETED` audit event. File evidence lasts up to 120 seconds, and code/approval each last 60 seconds, so rehearse this sequence before presenting.
3. **Synthetic HIGH blocks:** Select **New transfer**, upload `models/demo/synthetic.wav`, and analyze. The clean public clip scored HIGH in the September 24 probe. If it is HIGH now, prepare a transfer and show BLOCKED and its audit trail; a verifier code cannot override it. If it is not HIGH, report the miss rather than claiming a block. This demonstrates one known clip, not accuracy across generators or languages.
4. **HIGH retention:** Explain that later LOW audio cannot revive an already blocked action. The [tested browser/action receipt](validation/s03-2026-09-24.md) includes a genuine → synthetic HIGH → genuine transition and a direct completion denial after later LOW. Show that evidence if a controlled source-switch rehearsal is unavailable; do not claim a physical-mic transition test.
5. **Unsafe or missing evidence:** Stop/disconnect a live stream or use a too-short recording. The UI should make evidence unavailable or insufficient and completion should remain blocked. Use **New transfer** and fresh evidence for recovery; never bypass the backend or reuse an old code.
6. **Offline and limits:** With local models and database available, explain that the action path works without Jev or internet. For a deliberately offline rehearsal, set `JEV_MODE=disabled` in the local configuration and restart the backend; this avoids a shadow-mode network attempt if a key is present. Show the [V03 timing checkpoint](validation/v03-2026-09-24.md) and [Stage 0 English regression](validation/stage0-2026-09-24.md), including misses and false blocks. The [M04 probe](validation/m04-public-probe-2026-09-24.md) found that noise and simulated band-limiting turned the known synthetic clip LOW; this is an unresolved detection weakness, not a completed unsafe transfer. Do not claim a physically disconnected-internet rehearsal until it has been run on the final build.

## If something fails live

| What you see | What to do |
|---|---|
| Microphone unavailable or denied | Allow access in browser settings or use the bundled WAVs. |
| Poor quality / insufficient evidence | Record clear uninterrupted speech, or use the known WAV for the workflow demo. |
| Expired evidence | Analyze audio again. If the action was blocked/expired, choose New transfer. |
| Expired OTP / approval | Create a new transfer and request verification again. Reissuing cannot reset a used/expired challenge. |
| Backend/model unavailable | Check `docker compose ps` and `/readyz`. Use the older slides/video only as a labeled historical fallback; they do not prove current streaming or HIGH/BLOCKED. |
| Personal speech marked HIGH | Explain that this is a measured limitation of the uncalibrated detector; do not bypass the block to make the demo look successful. |

## Answers to likely questions

**Did you train the AI?** No. We integrated third-party pretrained models and built/evaluated the workflow around them.

**What does the score mean?** A synthetic-speech model output used by a threshold policy. It is not a calibrated fraud probability or an identity check.

**How accurate is it?** The [Stage 0 English regression](validation/stage0-2026-09-24.md) uses only 40 historical clips and misses its frozen target. Its source overlap with the pretrained model is unknown. There is no defensible Hindi, Hinglish, Marathi, replay, telephone or unseen-generator accuracy claim yet. Noise and simulated band-limiting also made the known synthetic demo clip score LOW; see [M04](validation/m04-public-probe-2026-09-24.md).

**What does “accepted synthetic” mean in the report?** It means the voice gate did not block that synthetic clip. Independent verification is still required; it does not mean a fraudulent transaction succeeded.

**Why show imperfect results?** They identify where quality handling, threshold selection, and target-domain data need improvement. A teacher should be able to distinguish working engineering from unproven ML claims.

**Does it scale?** The current single-worker demo admits one active audio session and rejects additional audio sessions. A repeated-public-clip 10-minute stream held a bounded response backlog, but it was not a multi-user or physical-microphone trial. The local verifier inbox is in memory and is not a trusted out-of-band channel.

**Is Jev making the decision?** No. Local VAD/detector evidence and deterministic action/OTP checks govern completion. Jev is optional metadata-only shadow by default and has not been validated with a live key; no raw audio or code is sent to it. Advisory escalation is not approved.

**What comes next?** Obtain rights-cleared, source/speaker/generator-disjoint four-language audio; validate the deployed detector before model selection; rehearse a real microphone and offline final build; then freeze and test the exact source, model and policy. Trusted delivery, production accounts and payment integration are out of scope for this presentation.

## Reproduce the checks

```powershell
python -m pytest -q -p no:cacheprovider
node tests/ui_smoke.cjs
node tests/microphone_smoke.cjs
```

For API/browser integration evidence, use the isolated setup and commands in the [S03/V01 receipt](validation/s03-2026-09-24.md); do not point `scripts/check_demo.py` at the presentation/demo database. It creates simulated sessions/actions and manipulates expiry only for its own test rows. Browser checks use a fake microphone device. Rehearse with the laptop's real microphone and verifier before claiming the final workflow. Dataset reproduction is in [evaluation-guide.md](evaluation-guide.md).

## Presentation boundaries relative to the SIH PDF

Demonstrated in automated checks: sequenced continuous browser streaming with a fake device, WAV input, local pretrained inference, quality gate, deterministic policy, local-verifier simulation, action-bound one-time approval, HIGH retention, restart safety and audit/dashboard.

Pending: physical-microphone and disconnected-internet final-build rehearsal, representative four-language and phone/replay/partial-spoof evaluation, defensible model/policy freeze, live Jev shadow evaluation, current narrated backup video and final slides. A trained SSL head is conditional, not a requirement. Real SMS/payment integration and production hosting are out of scope. Do not repeat the old slides' “already evaluated” language for pending work.
