"use strict";

const MicrophoneAudio = {
  supported() {
    return Boolean(globalThis.navigator?.mediaDevices?.getUserMedia && globalThis.MediaRecorder && globalThis.AudioContext && globalThis.OfflineAudioContext);
  },

  record(onStarted) {
    let recorder, stream, timer, finished = false, resolve, reject;
    const chunks = [];
    const result = new Promise((yes, no) => { resolve = yes; reject = no; });
    function finish(error) {
      if (finished) return;
      finished = true;
      clearTimeout(timer);
      if (recorder?.state === "recording") recorder.stop();
      stream?.getTracks().forEach((track) => track.stop());
      if (error) reject(error);
      else resolve(new Blob(chunks, { type: recorder.mimeType }));
    }
    const capture = {
      result, ready: false,
      stop() { if (recorder?.state === "recording") { capture.ready = false; recorder.stop(); } },
      cancel() { finish(new Error("Recording cancelled. No audio was submitted.")); },
    };
    navigator.mediaDevices.getUserMedia({ audio: true }).then((value) => {
      stream = value;
      if (finished) { stream.getTracks().forEach((track) => track.stop()); return; }
      recorder = new MediaRecorder(stream);
      recorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data); };
      recorder.onerror = () => finish(new Error("Microphone recording failed. Try a WAV upload."));
      recorder.onstop = () => finish(chunks.length ? null : new Error("No audio was recorded. Try again."));
      stream.getAudioTracks().forEach((track) => {
        track.onended = () => finish(new Error("Microphone disconnected. Try recording again."));
      });
      recorder.start();
      capture.ready = true;
      timer = setTimeout(() => capture.stop(), 10000);
      onStarted();
    }).catch((error) => finish(new Error(`Microphone unavailable: ${error.message}. Allow microphone access or choose a WAV file.`)));
    return capture;
  },

  async toWav(blob) {
    const context = new AudioContext();
    let decoded;
    try { decoded = await context.decodeAudioData(await blob.arrayBuffer()); }
    finally { await context.close(); }
    if (!decoded.length || !Number.isFinite(decoded.duration)) throw new Error("The recording is empty.");
    // Native resampling/downmixing avoids a custom resampler and its aliasing errors.
    const output = new OfflineAudioContext(1, Math.min(160000, Math.ceil(decoded.duration * 16000)), 16000);
    const source = output.createBufferSource();
    source.buffer = decoded;
    source.connect(output.destination);
    source.start();
    const rendered = await output.startRendering();
    return new File([MicrophoneAudio.encodeWav(rendered.getChannelData(0))], "microphone.wav", { type: "audio/wav" });
  },

  encodeWav(samples) {
    if (!samples.length || samples.length > 160000) throw new Error("Record between 1 sample and 10 seconds of audio.");
    const buffer = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(buffer);
    const text = (offset, value) => { for (let i = 0; i < value.length; i++) view.setUint8(offset + i, value.charCodeAt(i)); };
    text(0, "RIFF"); view.setUint32(4, buffer.byteLength - 8, true); text(8, "WAVE");
    text(12, "fmt "); view.setUint32(16, 16, true); view.setUint16(20, 1, true);
    view.setUint16(22, 1, true); view.setUint32(24, 16000, true); view.setUint32(28, 32000, true);
    view.setUint16(32, 2, true); view.setUint16(34, 16, true); text(36, "data"); view.setUint32(40, samples.length * 2, true);
    samples.forEach((sample, i) => {
      if (!Number.isFinite(sample)) throw new Error("The recording contains invalid audio samples.");
      const clipped = Math.max(-1, Math.min(1, sample));
      view.setInt16(44 + i * 2, Math.round(clipped * (clipped < 0 ? 32768 : 32767)), true);
    });
    return buffer;
  },
};

if (typeof module !== "undefined") module.exports = MicrophoneAudio;
