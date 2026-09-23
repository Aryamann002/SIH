// Run: node tests/microphone_smoke.cjs. Native capture boundary and PCM/WAV checks.
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const audio = require("../app/static/microphone.js");

const encoded = audio.encodeWav(new Float32Array([-2, -1, 0, 1, 2]));
const bytes = Buffer.from(encoded);
assert.equal(bytes.toString("ascii", 0, 4), "RIFF");
assert.equal(bytes.toString("ascii", 8, 12), "WAVE");
assert.equal(bytes.readUInt32LE(4), bytes.length - 8);
assert.equal(bytes.readUInt16LE(20), 1); // PCM
assert.equal(bytes.readUInt16LE(22), 1); // mono
assert.equal(bytes.readUInt32LE(24), 16000);
assert.equal(bytes.readUInt16LE(34), 16);
assert.equal(bytes.readUInt32LE(40), 10);
assert.deepEqual([0, 1, 2, 3, 4].map((i) => bytes.readInt16LE(44 + i * 2)), [-32768, -32768, 0, 32767, 32767]);
assert.throws(() => audio.encodeWav(new Float32Array()), /between/);
assert.throws(() => audio.encodeWav(new Float32Array([NaN])), /invalid/);
assert.throws(() => audio.encodeWav(new Float32Array(160001)), /between/);

let Worklet, posted;
const workletContext = vm.createContext({
  AudioWorkletProcessor: class { constructor() { this.port = { postMessage: (data, transfer) => { posted = { data, transfer }; } }; } },
  registerProcessor: (name, implementation) => { assert.equal(name, "pcm16-capture"); Worklet = implementation; },
  Int16Array, Math,
});
vm.runInContext(fs.readFileSync(path.resolve(__dirname, "../app/static/pcm-worklet.js"), "utf8"), workletContext);
const processor = new Worklet();
const left = new Float32Array(3200).fill(1);
const right = new Float32Array(3200).fill(1);
left[1] = right[1] = -1;
assert.equal(processor.process([[left, right]]), true);
assert.equal(posted.data.byteLength, 6400, "Worklet must emit one 200 ms PCM16 frame");
assert.equal(new DataView(posted.data).getInt16(0, true), 32767);
assert.equal(new DataView(posted.data).getInt16(2, true), -32768);
assert.equal(posted.transfer[0], posted.data, "PCM frame must transfer without copying");

function environment() {
  let request, device, timer, stopped = 0, cleared = 0, closed = 0, outputOptions;
  const track = { stop() { stopped++; } };
  const stream = { getTracks: () => [track], getAudioTracks: () => [track] };
  class Recorder {
    constructor() { device = this; this.state = "inactive"; this.mimeType = "audio/webm"; }
    start() { this.state = "recording"; }
    stop() {
      this.state = "inactive";
      queueMicrotask(() => { this.ondataavailable({ data: new Blob(["sample"]) }); this.onstop(); });
    }
  }
  class DecodeContext {
    async decodeAudioData() { return { length: 144000, duration: 3 }; }
    async close() { closed++; }
  }
  class RenderContext {
    constructor(...args) { outputOptions = args; }
    createBufferSource() { return { connect() {}, start() {} }; }
    async startRendering() { return { getChannelData: () => new Float32Array(48000) }; }
  }
  const context = vm.createContext({
    navigator: { mediaDevices: { getUserMedia: () => new Promise((resolve, reject) => { request = { resolve, reject }; }) } },
    MediaRecorder: Recorder, AudioContext: DecodeContext, OfflineAudioContext: RenderContext,
    Blob, File, setTimeout: (callback, delay) => { assert.equal(delay, 10000); timer = callback; return 1; },
    clearTimeout: () => { cleared++; },
  });
  vm.runInContext(fs.readFileSync(path.resolve(__dirname, "../app/static/microphone.js"), "utf8"), context);
  return {
    audio: vm.runInContext("MicrophoneAudio", context),
    allow: () => request.resolve(stream), deny: () => request.reject(new Error("Permission denied")),
    timeout: () => timer(), error: () => device.onerror(), disconnect: () => track.onended(),
    stopped: () => stopped, cleared: () => cleared, closed: () => closed, outputOptions: () => outputOptions,
  };
}

function liveEnvironment(delayedResume = false) {
  let context, node, resume, connected = 0, stopped = 0, closed = 0;
  const track = { onended: null, stop() { stopped++; } };
  const stream = { getTracks: () => [track], getAudioTracks: () => [track] };
  const source = { connect() { connected++; }, disconnect() {} };
  class LiveContext {
    constructor(options) { assert.equal(options.sampleRate, 16000); this.sampleRate = 16000; this.destination = {}; context = this; }
    audioWorklet = { addModule: async (path) => assert.equal(path, "/static/pcm-worklet.js") };
    createMediaStreamSource() { return source; }
    async resume() { connected++; if (delayedResume) await new Promise((resolve) => { resume = resolve; }); }
    async close() { closed++; }
  }
  class LiveNode {
    constructor(_context, name) { assert.equal(name, "pcm16-capture"); this.port = {}; node = this; }
    connect() { connected++; }
    disconnect() {}
  }
  const contextVm = vm.createContext({
    navigator: { mediaDevices: { getUserMedia: async () => stream } },
    AudioContext: LiveContext, AudioWorkletNode: LiveNode, WebSocket: class {},
    MediaRecorder: class {}, OfflineAudioContext: class {}, Blob, File,
  });
  vm.runInContext(fs.readFileSync(path.resolve(__dirname, "../app/static/microphone.js"), "utf8"), contextVm);
  return {
    audio: vm.runInContext("MicrophoneAudio", contextVm),
    node: () => node, connected: () => connected, stopped: () => stopped,
    closed: () => closed, resume: () => resume(), track, context: () => context,
  };
}
const settle = () => new Promise(setImmediate);

(async () => {
  const successful = environment();
  let started = 0;
  const recording = successful.audio.record(() => started++);
  successful.allow(); await settle();
  assert.equal(started, 1);
  assert.equal(recording.ready, true);
  recording.stop();
  const blob = await recording.result;
  assert.equal(blob.size, 6);
  assert.equal(successful.stopped(), 1, "Successful capture must release microphone");
  const wav = await successful.audio.toWav(blob);
  assert.equal(wav.name, "microphone.wav");
  assert.equal(wav.type, "audio/wav");
  assert.equal(wav.size, 44 + 48000 * 2);
  assert.deepEqual(successful.outputOptions(), [1, 48000, 16000]);
  assert.equal(successful.closed(), 1, "Decode context must close");

  const cancelled = environment();
  const pending = cancelled.audio.record(() => assert.fail("Cancelled capture must not start"));
  pending.cancel();
  await assert.rejects(pending.result, /cancelled/);
  cancelled.allow(); await settle();
  assert.equal(cancelled.stopped(), 1, "Permission arriving after cancel must release microphone");

  const denied = environment();
  const permission = denied.audio.record(() => assert.fail("Denied capture must not start"));
  denied.deny();
  await assert.rejects(permission.result, /Permission denied/);

  for (const operation of ["timeout", "error", "disconnect"]) {
    const boundary = environment();
    const capture = boundary.audio.record(() => {});
    boundary.allow(); await settle();
    boundary[operation]();
    if (operation === "timeout") await capture.result;
    else await assert.rejects(capture.result, /failed|disconnected/);
    assert.equal(boundary.stopped(), 1, `${operation} must release microphone`);
    assert.ok(boundary.cleared() > 0);
  }

  const live = liveEnvironment();
  let frame;
  const capture = await live.audio.stream((value) => { frame = value; }, assert.fail);
  assert.equal(live.audio.liveSupported(), true);
  assert.equal(live.connected(), 0, "Capture graph must wait for authenticated ready");
  await capture.start();
  assert.equal(capture.ready, true);
  assert.equal(live.connected(), 3, "Ready capture connects source, worklet and native context");
  live.node().port.onmessage({ data: posted.data });
  assert.equal(frame, posted.data);
  capture.stop(); capture.stop();
  assert.equal(live.stopped(), 1, "Live stop must release microphone once");
  assert.equal(live.closed(), 1, "Live stop must close AudioContext once");

  const startRace = liveEnvironment(true);
  const pendingLive = await startRace.audio.stream(() => {}, () => {});
  const pendingStart = pendingLive.start();
  await settle();
  pendingLive.stop();
  startRace.resume();
  await assert.rejects(pendingStart, /disconnected/);
  assert.equal(pendingLive.ready, false, "Stopped capture cannot become ready after resume resolves");
  console.log("Microphone smoke passed: PCM WAV and 200 ms live PCM16, native 16 kHz resampling, ready gate, stop, permission/error boundaries, cleanup.");
})().catch((error) => { console.error(error); process.exitCode = 1; });
