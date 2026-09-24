// Run: node tests/ui_smoke.cjs. Tests browser workflow contracts without dependencies.
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

class Element {
  constructor() { this.value = ""; this.textContent = ""; this.hidden = false; this.disabled = false; this.dataset = {}; this.children = []; this.handlers = {}; this.files = []; }
  addEventListener(event, handler) { this.handlers[event] = handler; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  removeAttribute(name) { delete this[name]; }
  focus() {}
  set innerHTML(_) { throw new Error("HTML interpolation is not permitted for API data."); }
}

function load(page, fetch, globals = {}) {
  const root = path.resolve(__dirname, "../app/static");
  const html = fs.readFileSync(path.join(root, `${page === "app" ? "index" : "verify"}.html`), "utf8");
  const elements = Object.fromEntries([...html.matchAll(/\bid="([^"]+)"/g)].map((match) => [match[1], new Element()]));
  const intervals = [];
  const events = {};
  const window = { setInterval: (callback) => intervals.push(callback), setTimeout: (callback, delay) => { if (delay !== 5000) callback(); return 1; }, clearTimeout() {}, addEventListener: (name, callback) => { events[name] = callback; } };
  const context = vm.createContext({
    document: { getElementById: (id) => { assert.ok(elements[id], `Missing element: ${id}`); return elements[id]; }, createElement: () => new Element() },
    window, fetch, File: class File { constructor(_bits = [], name = "fixture.wav") { this.name = name; this.size = 32044; } }, URL: { createObjectURL: () => "blob:test", revokeObjectURL() {} },
    navigator: { clipboard: { writeText: async () => {} } }, console, ...globals,
  });
  if (page === "app") vm.runInContext(fs.readFileSync(path.join(root, "microphone.js"), "utf8"), context);
  vm.runInContext(fs.readFileSync(path.join(root, `${page}.js`), "utf8"), context);
  return { elements, intervals, events, context };
}

async function settle() { for (let i = 0; i < 8; i++) await new Promise(setImmediate); }
async function fire(ui, id, event = "click") { await ui.elements[id].handlers[event]({ preventDefault() {} }); await settle(); }
const response = (data, status = 200) => ({ ok: status < 400, status, json: async () => data });
const future = () => new Date(Date.now() + 60000).toISOString();
const actionId = "ec6f9fc0-bd58-4b61-86a3-a6f951691dc8";

(async () => {
  const calls = [];
  let failComplete = true;
  let blockNext = false;
  const ui = load("app", async (url, options = {}) => {
    calls.push({ url, ...options });
    if (url.endsWith("/system")) return response({ ready: false, detector_available: true, model_version: "test-model", demo_verification_enabled: true });
    if (url.endsWith("/sessions")) return response({ session_id: "session-id", session_token: "session-secret" });
    assert.equal(options.headers.Authorization, "Bearer session-secret", "Every session-owned request must carry its bearer token");
    if (url.endsWith("/sessions/session-id")) return response({ risk_state: "LOW", spoof_score: 0.1, snr_db: 23, speech_duration_ms: 2100, evidence_age_ms: 100, reason_codes: ["<img src=x onerror=alert(1)>"], model_version: "test-model", threshold_profile: "test-policy" });
    if (url.endsWith("/audio")) return response({ risk_state: "LOW", spoof_score: 0.1, snr_db: 23, speech_duration_ms: 2100, reason_codes: ["<img src=x onerror=alert(1)>"], model_version: "test-model", threshold_profile: "test-policy" });
    if (url.endsWith("/actions")) return response({ action_id: actionId, status: blockNext ? "BLOCKED" : "PENDING", risk_state: blockNext ? "HIGH" : "LOW", allowed: false });
    if (url.endsWith("/audit")) return response({ events: [{ timestamp: new Date().toISOString(), event_type: "ACTION_CREATED", risk_state: "LOW", details: { recipient: "<script>unsafe</script>" } }] });
    if (url.endsWith("/verification")) return response({ challenge_id: "challenge-id", expires_at: future() });
    if (url.endsWith("/confirm")) return response({ approval_token: "approval-secret", expires_at: future() });
    if (url.endsWith("/complete")) return failComplete ? response({ detail: "Evidence is stale" }, 409) : response({ action_id: actionId, status: "COMPLETED", risk_state: "LOW", allowed: true });
    if (url.endsWith(actionId)) return response({ action_id: actionId, status: "VERIFIED", risk_state: "LOW", allowed: false });
    throw new Error(`Unexpected URL: ${url}`);
  });
  await settle();
  assert.equal(ui.elements["risk-state"].textContent, "SERVICE UNAVAILABLE");
  assert.equal(ui.elements["spoof-score"].textContent, "—");
  ui.elements["audio-file"].files = [vm.runInContext("new File()", ui.context)];
  await fire(ui, "audio-file", "change");
  await fire(ui, "audio-form", "submit");
  assert.equal(ui.elements["risk-state"].textContent, "LOW");
  assert.equal(ui.elements["evidence-age"].textContent, "0.1 s old");
  assert.equal(ui.elements["reason-codes"].children[0].textContent, "<img src=x onerror=alert(1)>");
  assert.equal(calls.find((call) => call.url.endsWith("/audio")).headers["Content-Type"], "audio/wav");
  assert.equal(ui.elements["record-start"].disabled, true, "Unsupported microphone must leave WAV upload available");
  vm.runInContext(`
    MicrophoneAudio.supported = () => true;
    MicrophoneAudio.record = () => ({ result: Promise.resolve({}), ready: false });
    MicrophoneAudio.toWav = async () => new File([], "microphone.wav");
  `, ui.context);
  await fire(ui, "record-start");
  assert.match(ui.elements["record-status"].textContent, /Recording ready/);
  assert.equal(ui.elements["analyze-button"].disabled, false);
  assert.equal(calls.filter((call) => call.url.endsWith("/audio")).length, 1, "Recording must wait for explicit analysis before uploading");
  await fire(ui, "audio-form", "submit");
  assert.equal(calls.filter((call) => call.url.endsWith("/audio")).at(-1).body.name, "microphone.wav", "Recorded WAV must reuse authenticated upload flow");

  ui.elements.recipient.value = "Demo beneficiary";
  ui.elements.amount.value = "25000.50";
  await fire(ui, "action-form", "submit");
  assert.match(ui.elements.notice.textContent, /whole INR/);
  assert.equal(calls.filter((call) => call.url.endsWith("/actions")).length, 0);
  ui.elements.amount.value = "25000";
  await fire(ui, "action-form", "submit");
  assert.equal(ui.elements["transfer-fields"].disabled, true, "Created action details must stay immutable");
  assert.equal(ui.elements["request-verification"].disabled, false, "LOW risk still requires verification");
  assert.equal(ui.elements["complete-action"].hidden, true);
  assert.deepEqual(JSON.parse(calls.find((call) => call.url.endsWith("/actions")).body).payload, { amount: 25000, recipient: "Demo beneficiary" });
  assert.equal(ui.elements["audit-list"].children[0].children[2].children[1].textContent, '{\n  "recipient": "<script>unsafe</script>"\n}');
  await fire(ui, "request-verification");
  assert.equal(ui.elements["verification-form"].hidden, false);
  ui.elements["otp-code"].value = "654321";
  await fire(ui, "verification-form", "submit");
  assert.equal(ui.elements["complete-action"].hidden, false);
  assert.equal(ui.elements["action-status"].textContent, "VERIFIED");
  assert.equal(ui.elements["request-verification"].disabled, true, "Verified actions cannot request another code");
  assert.deepEqual(JSON.parse(calls.find((call) => call.url.endsWith("/confirm")).body), { challenge_id: "challenge-id", otp_code: "654321" });
  await fire(ui, "complete-action");
  assert.match(ui.elements.notice.textContent, /409: Evidence is stale/);
  assert.notEqual(ui.elements["action-status"].textContent, "COMPLETED", "Denied completion must never appear successful");
  failComplete = false;
  await fire(ui, "complete-action");
  assert.equal(ui.elements["action-status"].textContent, "COMPLETED");
  assert.equal(ui.elements["complete-action"].hidden, true);

  const expired = load("app", async (url) => url.endsWith("/system")
    ? response({ ready: true, demo_verification_enabled: true })
    : response({ action_id: actionId, status: "EXPIRED", risk_state: "LOW", allowed: false }));
  await settle();
  vm.runInContext(`
    state.action = { action_id: "${actionId}", status: "PENDING", risk_state: "LOW" };
    state.challenge = { challenge_id: "challenge-id", expires_at: new Date(Date.now() - 1).toISOString() };
    renderAction(); renderControls();
  `, expired.context);
  expired.intervals[0]();
  assert.equal(expired.elements["request-verification"].disabled, true, "Expired codes cannot be reissued for the same action");
  assert.equal(expired.elements["verification-form"].hidden, true);
  assert.match(expired.elements["verification-message"].textContent, /New transfer/);
  assert.deepEqual(JSON.parse(calls.find((call) => call.url.endsWith("/complete")).body), { approval_token: "approval-secret" });
  assert.ok(calls.every((call) => !call.url.includes("/demo/inbox")), "The operator must never fetch verifier codes");
  await fire(ui, "new-action");
  blockNext = true;
  await fire(ui, "action-form", "submit");
  assert.equal(ui.elements["request-verification"].disabled, true, "Blocked actions must not offer verification");
  assert.equal(ui.elements["complete-action"].hidden, true);

  const verifierCalls = [];
  const verifier = load("verify", async (url, options) => {
    verifierCalls.push({ url, options });
    return response({ action_id: actionId, otp_code: "654321", expires_at: future(), payload: { recipient: "<img src=x>", amount: 25000 } });
  });
  verifier.elements["verifier-key"].value = "verifier-secret";
  verifier.elements["action-id"].value = actionId;
  await fire(verifier, "inbox-form", "submit");
  assert.equal(verifierCalls[0].options.headers["X-Demo-Verifier-Key"], "verifier-secret");
  assert.equal(verifier.elements["verifier-key"].value, "", "Verifier keys must clear after use");
  assert.equal(verifier.elements["review-recipient"].textContent, "<img src=x>");
  assert.equal(verifier.elements["review-code"].textContent, "654321");
  assert.equal(verifier.elements["inbox-result"].hidden, false);
  vm.runInContext("expiresAt = Date.now() - 1", verifier.context);
  verifier.intervals[0]();
  assert.equal(verifier.elements["review-code"].textContent, "Expired");
  assert.match(verifier.elements["review-expiry"].textContent, /select New transfer/);

  const lostVerifier = load("verify", async () => response({ detail: "No unexpired verification message for this action." }, 404));
  lostVerifier.elements["verifier-key"].value = "verifier-secret";
  lostVerifier.elements["action-id"].value = actionId;
  await fire(lostVerifier, "inbox-form", "submit");
  assert.match(lostVerifier.elements.notice.textContent, /backend restart/);
  assert.match(lostVerifier.elements.notice.textContent, /New transfer/);
  assert.equal(lostVerifier.elements["verifier-key"].value, "");

  const sockets = [];
  class TestSocket {
    static OPEN = 1;
    constructor(url) {
      this.url = url; this.readyState = 0; this.bufferedAmount = 0; this.sent = []; sockets.push(this);
      queueMicrotask(() => { this.readyState = TestSocket.OPEN; this.onopen(); });
    }
    send(data) {
      this.sent.push(data);
      if (typeof data === "string") {
        assert.equal(this.sent.length, 1, "No PCM may precede authentication and ready");
        queueMicrotask(() => this.onmessage({ data: JSON.stringify({ type: "ready", session_id: "live-session", audio_protocol: "pcm16-seq-v1" }) }));
      }
    }
    close(code = 1000) { this.readyState = 3; queueMicrotask(() => this.onclose?.({ code })); }
  }
  const liveUi = load("app", async (url) => {
    if (url.endsWith("/system")) return response({ ready: true, model_version: "test-model", demo_verification_enabled: true });
    if (url.endsWith("/sessions")) return response({ session_id: "live-session", session_token: "live-secret" });
    throw new Error(`Unexpected live URL: ${url}`);
  }, { WebSocket: TestSocket, location: { protocol: "http:", host: "localhost:8000" } });
  await settle();
  vm.runInContext(`
    globalThis.captureStops = 0;
    MicrophoneAudio.liveSupported = () => true;
    MicrophoneAudio.stream = async (onFrame) => ({
      ready: false,
      async start() { this.ready = true; globalThis.liveFrame = onFrame; onFrame(new ArrayBuffer(6400)); },
      stop() { this.ready = false; captureStops += 1; },
    });
    renderControls();
  `, liveUi.context);
  await fire(liveUi, "live-start");
  assert.equal(sockets[0].url, "ws://localhost:8000/api/v1/stream/ws/live-session");
  assert.deepEqual(JSON.parse(sockets[0].sent[0]), { session_token: "live-secret", audio_protocol: "pcm16-seq-v1" }, "Credentials must be first WebSocket frame");
  assert.equal(sockets[0].sent[1].byteLength, 6404, "Sequenced PCM must start only after ready");
  assert.equal(new DataView(sockets[0].sent[1]).getUint32(0, true), 0);
  sockets[0].onmessage({ data: JSON.stringify({ risk_state: "LOW", spoof_score: 0.2, snr_db: 20, speech_duration_ms: 1800, reason_codes: ["NO_STRONG_SYNTHETIC_EVIDENCE"], model_version: "test-model", threshold_profile: "test" }) });
  assert.equal(liveUi.elements["risk-state"].textContent, "LOW");
  assert.equal(vm.runInContext("state.live.capture.ready", liveUi.context), true, "Risk must update while capture continues");
  await fire(liveUi, "live-stop");
  assert.equal(vm.runInContext("state.live", liveUi.context), null);
  assert.equal(vm.runInContext("captureStops", liveUi.context), 1);
  assert.equal(liveUi.elements["risk-state"].textContent, "SERVICE UNAVAILABLE", "Stopped stream must not leave LOW on screen");
  assert.equal(liveUi.elements["evidence-age"].textContent, "Unavailable");
  assert.equal(liveUi.elements["audio-file"].disabled, false, "WAV fallback must return after live stop");
  await fire(liveUi, "live-start");
  sockets[1].bufferedAmount = 12809;
  vm.runInContext("liveFrame(new ArrayBuffer(6400))", liveUi.context);
  assert.equal(vm.runInContext("state.live", liveUi.context), null, "Backlogged socket must stop capture");
  assert.equal(vm.runInContext("captureStops", liveUi.context), 2);
  await fire(liveUi, "live-start");
  liveUi.events.pagehide();
  assert.equal(vm.runInContext("state.live", liveUi.context), null);
  assert.equal(vm.runInContext("captureStops", liveUi.context), 3, "Page navigation must release live capture");

  const polled = load("app", async (url) => {
    if (url.endsWith("/system")) return response({ ready: true, demo_verification_enabled: true });
    if (url.endsWith("/sessions/poll-session")) return response({ risk_state: "SERVICE_UNAVAILABLE", evidence_age_ms: null, reason_codes: ["STREAM_OR_FILE_UNAVAILABLE"] });
    if (url.endsWith(actionId)) return response({ action_id: actionId, status: "BLOCKED", risk_state: "SERVICE_UNAVAILABLE", allowed: false });
    if (url.endsWith("/audit")) return response({ events: [{ timestamp: new Date().toISOString(), event_type: "ACTION_BLOCKED" }] });
    throw new Error(`Unexpected poll URL: ${url}`);
  });
  await settle();
  vm.runInContext(`
    state.session = { session_id: "poll-session", session_token: "poll-secret" };
    state.action = { action_id: "${actionId}", status: "PENDING", risk_state: "LOW" };
    renderRisk({ risk_state: "LOW", evidence_age_ms: 100, reason_codes: [] });
    renderAction();
  `, polled.context);
  assert.equal(polled.elements["request-verification"].disabled, false);
  polled.intervals[0]();
  await settle();
  assert.equal(polled.elements["risk-state"].textContent, "SERVICE UNAVAILABLE");
  assert.equal(polled.elements["action-status"].textContent, "BLOCKED");
  assert.equal(polled.elements["request-verification"].disabled, true);
  assert.equal(polled.elements["audit-list"].children.length, 1);
  console.log("UI smoke passed: authenticated live/WAV flows, immutable action, independent verification, denied completion, audit rendering, and expiry.");
})().catch((error) => { console.error(error); process.exitCode = 1; });
