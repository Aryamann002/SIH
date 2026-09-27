# Reviewed local assets

- `capture/assets/image_001.png`: isolated September 25 fake-device/public-WAV operator screenshot, 1440 × 1740 pixels. It visibly shows the native VigilVoice interface, HIGH risk, BLOCKED simulated transfer, and audit trail. It contains a synthetic action ID/session ID but no OTP, key, private audio or real payment. Source SHA256 `822b67d7fe6121166ec82a315bd7030100e9594c21fa3464afaadf961abe9adb`. It is a historical test capture, not final-source live footage.
- `capture/assets/image_002.png`: isolated September 25 fake-device/public-WAV operator screenshot, 1440 × 1680 pixels. It shows LOW risk and the statement that separate verification is still required. Source SHA256 `55a65304d3a65051c8554685fd53304907f9bf71ac4e7a4f9bcbee3cbc22849c`. The asset was ingested locally; the media CLI later exited with a Windows async assertion, so verify asset/manifest again before final render.
- `../../docs/validation/artifacts/r02-kokoro-narration-preview.wav`: locally generated English Kokoro draft, 24.55 seconds; use only if it matches the final script. No music, third-party stock footage, or cloud assets are necessary.

No website was captured. The app CSS in the current checkout supplied the brand tokens; the screenshot is the sole visual source.
