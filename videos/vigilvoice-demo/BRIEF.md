---
workflow: product-launch-video
flow: automation
storyboard: no
message: "Voice risk informs a fail-closed simulated transfer; it never authorizes one"
destination: presentation-projector
aspect: 1920x1080
language: en
audience: SIH judges and presenters
length: 23s
angle: show-it-as-is product walkthrough
narration: yes
voice: bf_emma
style_preset: broadside
---

## Intent

A short, factual offline backup for the live VigilVoice demonstration. Show the actual operator interface, the HIGH/BLOCKED checkpoint, and the separate action-bound verifier step. Do not imply production banking, speaker authentication, or validated four-language detection accuracy.

## Assets

- `../../docs/validation/r02-browser-2026-09-25/teacher-demo.png` — isolated fake-device/public-WAV LOW screen; no private audio or OTP.
- `../../docs/validation/r02-action-browser-2026-09-25/teacher-demo.png` — isolated fake-device/public-WAV HIGH/BLOCKED screen; no private audio or OTP.
- `../../docs/validation/r02-narration-draft-2026-09-27.txt` — approved-scope factual narration draft.
- `../../docs/validation/artifacts/r02-kokoro-narration-preview.wav` — offline Kokoro voice draft; preview only.

## Notes

- Use existing public demo evidence. Do not capture the presentation database, verifier key, one-time code, private recordings, or third-party media.
- The screen asset is an isolated September 25 test capture, not a final frozen-build screenshot. Relabel or replace it after source freeze before final delivery.
- No Internet or Jev required for playback or the primary demo. No real money moves.
