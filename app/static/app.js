"use strict";

const $ = (id) => document.getElementById(id);
const state = { session: null, action: null, challenge: null, approval: null, busy: false, audioUrl: null, audioFile: null, microphone: null, live: null, systemReady: false, verifierAvailable: false, safeEvidence: false };
const explanations = {
  LOW: ["good", "Low voice risk. Independent verification is still required before this simulated transfer can complete."],
  ELEVATED: ["warning", "The audio contains elevated spoof signals. Review the exact transfer independently before proceeding."],
  HIGH: ["danger", "High voice risk. The backend must keep the transfer unapproved."],
  POOR_QUALITY: ["warning", "The recording is too degraded for a reliable assessment. Try a clearer speech recording."],
  INSUFFICIENT_EVIDENCE: ["neutral", "There is not enough usable speech evidence. Add a longer, clearer recording."],
  SERVICE_UNAVAILABLE: ["danger", "The detector or current evidence is unavailable. Transfers remain unapproved."],
};
const label = (value) => String(value || "UNKNOWN").replaceAll("_", " ");
const number = (value, digits = 1) => typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "—";
const ended = () => ["COMPLETED", "BLOCKED", "EXPIRED", "CANCELLED", "LOCKED"].includes(state.action?.status);
const active = (item) => Boolean(item && Date.parse(item.expires_at) > Date.now());

async function api(path, options = {}) {
  const headers = { ...options.headers };
  if (state.session) headers.Authorization = `Bearer ${state.session.session_token}`;
  if (options.body && !(options.body instanceof File)) headers["Content-Type"] = "application/json";
  const response = await fetch(`/api/v1${path}`, { ...options, headers, cache: "no-store" });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail || data);
    throw new Error(`${response.status}: ${detail}`);
  }
  return data;
}

function notice(message, tone = "error") {
  $("notice").textContent = message;
  $("notice").dataset.tone = tone;
  $("notice").hidden = !message;
}

function renderControls() {
  const { busy, action, challenge, approval } = state;
  $("live-start").disabled = busy || Boolean(state.live) || Boolean(state.microphone) || !state.systemReady || !MicrophoneAudio.liveSupported();
  $("live-stop").disabled = !state.live;
  $("analyze-button").disabled = busy || Boolean(state.live) || !state.audioFile;
  $("audio-file").disabled = busy || Boolean(state.live);
  $("record-start").disabled = busy || Boolean(state.live) || !MicrophoneAudio.supported();
  $("record-stop").disabled = !state.microphone?.ready;
  $("record-cancel").disabled = !state.microphone;
  $("refresh-risk").disabled = busy || !state.session;
  $("create-action").disabled = busy || Boolean(action);
  $("transfer-fields").disabled = busy || Boolean(action);
  $("create-action").hidden = Boolean(action);
  $("new-action").disabled = busy;
  $("refresh-audit").disabled = busy || !action;
  $("request-verification").disabled = busy || action?.status !== "PENDING" || Boolean(challenge) || Boolean(approval) || !state.verifierAvailable || !state.safeEvidence;
  $("verification-form").hidden = !active(challenge) || Boolean(approval) || ended();
  $("confirm-code").disabled = busy || !active(challenge) || ended();
  $("otp-code").disabled = busy || !active(challenge) || ended();
  $("complete-action").hidden = !approval || ended();
  $("complete-action").disabled = busy || !active(approval) || !state.safeEvidence;
}

async function run(task) {
  if (state.busy) return;
  state.busy = true;
  notice("");
  renderControls();
  try { await task(); }
  catch (error) {
    notice(error.message || String(error));
    if (state.action) {
      await refreshAction().catch(() => {});
      await refreshAudit().catch(() => {});
    }
  } finally { state.busy = false; renderControls(); }
}

async function refreshAction() {
  if (!state.action) return;
  const previous = state.action.status;
  state.action = { ...state.action, ...await api(`/actions/${state.action.action_id}`) };
  renderAction();
  renderControls();
  if (previous !== state.action.status) await refreshAudit();
}

async function ensureSession() {
  if (!state.session) {
    const session = await api("/sessions", { method: "POST", body: "{}" });
    if (!session.session_id || !session.session_token) throw new Error("The server did not return a usable session.");
    state.session = session;
    $("session-label").textContent = `Session ${session.session_id.slice(0, 8)} · credentials stay in this tab`;
  }
  return state.session.session_id;
}

function openStream(session) {
  return new Promise((resolve, reject) => {
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    const socket = new WebSocket(`${protocol}//${location.host}/api/v1/stream/ws/${encodeURIComponent(session.session_id)}`);
    let settled = false;
    let timer;
    const fail = (error) => {
      if (settled) return;
      settled = true;
      window.clearTimeout(timer);
      socket.close();
      reject(error);
    };
    timer = window.setTimeout(() => fail(new Error("Live stream handshake timed out. Use a WAV upload.")), 5000);
    socket.onopen = () => socket.send(JSON.stringify({ session_token: session.session_token, audio_protocol: "pcm16-seq-v1" }));
    socket.onerror = () => fail(new Error("Live stream connection failed. Use a WAV upload."));
    socket.onclose = (event) => fail(new Error(`Live stream closed before ready (${event.code}). Use a WAV upload.`));
    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.type !== "ready" || message.session_id !== session.session_id || message.audio_protocol !== "pcm16-seq-v1") throw new Error("Unexpected stream handshake.");
        settled = true;
        window.clearTimeout(timer);
        resolve(socket);
      } catch (error) { fail(error); }
    };
  });
}

function stopLive(message = "Live detection stopped. WAV recording and upload remain available.", failed = false) {
  const live = state.live;
  state.live = null;
  live?.capture?.stop();
  if (live?.socket?.readyState < 2) live.socket.close(1000, "Stopped by operator");
  $("live-status").textContent = message;
  if (live) {
    renderRisk({ risk_state: "SERVICE_UNAVAILABLE", reason_codes: ["STREAM_STOPPED_OR_DISCONNECTED"] });
    $("evidence-age").textContent = "Unavailable";
    if (state.action) refreshAction().catch(() => {});
  }
  if (failed) notice(`${message} Current evidence is unavailable.`);
  renderControls();
}

function renderRisk(data) {
  const [tone, explanation] = explanations[data.risk_state] || ["neutral", "The server returned an unrecognized state. Review the reason codes; no approval is implied."];
  $("risk-state").textContent = label(data.risk_state);
  $("risk-explanation").textContent = explanation;
  $("risk-box").dataset.tone = tone;
  $("spoof-score").textContent = number(data.spoof_score, 3);
  $("speech-duration").textContent = Number.isFinite(data.speech_duration_ms) ? `${number(data.speech_duration_ms / 1000)} s` : "—";
  $("snr").textContent = Number.isFinite(data.snr_db) ? `${number(data.snr_db)} dB` : "—";
  $("model-version").textContent = data.model_version || "Unavailable";
  $("threshold-profile").textContent = data.threshold_profile || "—";
  if (!['LOW', 'ELEVATED'].includes(data.risk_state)) state.safeEvidence = false;
  else if (Number.isFinite(data.evidence_age_ms)) state.safeEvidence = true;
  if (Object.hasOwn(data, "evidence_age_ms")) $("evidence-age").textContent = Number.isFinite(data.evidence_age_ms)
    ? `${number(data.evidence_age_ms / 1000)} s old` : "Unavailable";
  $("reason-codes").replaceChildren();
  for (const reason of data.reason_codes || []) {
    const item = document.createElement("li");
    item.textContent = String(reason);
    $("reason-codes").append(item);
  }
  renderControls();
}

function renderAction() {
  const action = state.action;
  $("action-summary").hidden = !action;
  if (!action) return;
  $("action-id").textContent = action.action_id;
  $("action-status").textContent = label(action.status);
  $("action-message").textContent = action.status === "COMPLETED"
    ? "Simulated transfer completed. No money was moved."
    : action.message || `Transfer remains unapproved. Current voice risk: ${label(action.risk_state)}. Details are fixed to this action ID.`;
  if (ended()) $("verification-message").textContent = action.status === "COMPLETED"
    ? "Approval was consumed for this action. Review the persisted events below."
    : "This action cannot complete. Review its audit events; prepare a new transfer after resolving the cause.";
}

async function refreshRisk() {
  if (state.session) renderRisk(await api(`/sessions/${state.session.session_id}`));
}

async function refreshAudit() {
  if (!state.action) return;
  const data = await api(`/actions/${state.action.action_id}/audit`);
  $("audit-list").replaceChildren();
  $("audit-empty").hidden = Boolean(data.events?.length);
  for (const event of data.events || []) {
    const item = document.createElement("li");
    const row = document.createElement("div");
    row.className = "row";
    const title = document.createElement("strong");
    title.textContent = label(event.event_type);
    const time = document.createElement("time");
    const date = new Date(event.timestamp);
    if (!Number.isNaN(date.getTime())) {
      time.dateTime = date.toISOString();
      time.textContent = date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
      time.title = date.toLocaleString();
    }
    row.append(title, time);
    item.append(row);
    const reason = document.createElement("p");
    reason.textContent = [event.risk_state, event.reason_code].filter(Boolean).map(label).join(" · ");
    item.append(reason);
    if (event.details && Object.keys(event.details).length) {
      const details = document.createElement("details");
      const summary = document.createElement("summary");
      summary.textContent = "Event details";
      const pre = document.createElement("pre");
      pre.textContent = JSON.stringify(event.details, null, 2);
      details.append(summary, pre);
      item.append(details);
    }
    $("audit-list").append(item);
  }
}

function selectAudio(file) {
  if (state.audioUrl) URL.revokeObjectURL(state.audioUrl);
  state.audioUrl = null;
  state.audioFile = file || null;
  $("audio-preview").hidden = !file;
  if (file) {
    state.audioUrl = URL.createObjectURL(file);
    $("audio-preview").src = state.audioUrl;
    $("file-info").textContent = `${file.name} · ${(file.size / 1024).toFixed(0)} KB · ready to analyze`;
  } else {
    $("audio-preview").removeAttribute("src");
    $("file-info").textContent = "Choose a recording to start.";
  }
  renderControls();
}

$("audio-file").addEventListener("change", () => selectAudio($("audio-file").files[0]));
$("live-start").addEventListener("click", () => run(async () => {
  $("live-status").textContent = "Waiting for microphone permission…";
  const capture = await MicrophoneAudio.stream(
    (frame) => {
      const live = state.live;
      if (live?.socket.readyState !== WebSocket.OPEN) return;
      if (frame.byteLength !== 6400 || live.socket.bufferedAmount > 12808 || live.sequence > 0xffffffff) {
        stopLive("Live audio fell behind. Restart capture or use a WAV upload.", true);
        return;
      }
      const packet = new ArrayBuffer(4 + frame.byteLength);
      new DataView(packet).setUint32(0, live.sequence++, true);
      new Uint8Array(packet, 4).set(new Uint8Array(frame));
      live.socket.send(packet);
    },
    (error) => stopLive(error.message, true),
  );
  $("live-status").textContent = "Microphone ready. Authenticating live stream…";
  let socket;
  try { await ensureSession(); socket = await openStream(state.session); }
  catch (error) { capture.stop(); throw error; }
  const live = { capture, socket, results: 0, sequence: 0 };
  state.live = live;
  socket.onmessage = (event) => {
    try {
      const result = JSON.parse(event.data);
      live.results += 1;
      renderRisk(result);
      $("live-status").textContent = `Live detection active · ${live.results} risk update${live.results === 1 ? "" : "s"}`;
    } catch { stopLive("Live stream returned invalid data. Use a WAV upload.", true); }
  };
  socket.onerror = () => {};
  socket.onclose = (event) => {
    if (state.live === live) stopLive(event.code === 1000
      ? "Live detection stopped. WAV recording and upload remain available."
      : `Live stream ended (${event.code}). Use a WAV upload.`, event.code !== 1000);
  };
  try { await capture.start(); }
  catch (error) { stopLive("Live microphone could not start. Use a WAV upload.", true); throw error; }
  $("live-status").textContent = "Live detection active · listening for speech";
  renderControls();
}));
$("live-stop").addEventListener("click", () => stopLive());
$("record-start").addEventListener("click", () => run(async () => {
  if (!MicrophoneAudio.supported()) throw new Error("Microphone recording needs a supported browser on localhost or HTTPS. Use a WAV upload.");
  $("record-status").textContent = "Waiting for microphone permission…";
  state.microphone = MicrophoneAudio.record(() => {
    $("record-status").textContent = "Recording. Speak clearly for 3–10 seconds, then stop. Stops automatically at 10 seconds.";
    renderControls();
  });
  renderControls();
  try {
    const recording = await state.microphone.result;
    state.microphone = null;
    renderControls();
    $("record-status").textContent = "Preparing WAV recording…";
    const file = await MicrophoneAudio.toWav(recording);
    $("audio-file").value = "";
    selectAudio(file);
    $("record-status").textContent = "Recording ready. Preview it, then select Analyze recording to submit it.";
  } catch (error) {
    $("record-status").textContent = "Recording stopped. You can try again or upload a WAV file.";
    throw error;
  } finally { state.microphone = null; }
}));
$("record-stop").addEventListener("click", () => {
  state.microphone?.stop();
  renderControls();
});
$("record-cancel").addEventListener("click", () => state.microphone?.cancel());
window.addEventListener("pagehide", () => {
  stopLive();
  state.microphone?.cancel();
  if (state.audioUrl) URL.revokeObjectURL(state.audioUrl);
});
if (!MicrophoneAudio.supported()) $("record-status").textContent = "Microphone recording is unavailable here. Open in a supported browser on localhost or HTTPS, or upload a WAV file.";
if (!MicrophoneAudio.liveSupported()) $("live-status").textContent = "Continuous microphone detection is unavailable here. Use WAV recording or upload.";
renderControls();

$("audio-form").addEventListener("submit", (event) => {
  event.preventDefault();
  run(async () => {
    const file = state.audioFile;
    if (!file) throw new Error("Choose a WAV recording first.");
    const id = await ensureSession();
    $("analyze-button").textContent = "Analyzing recording…";
    try {
      renderRisk(await api(`/sessions/${id}/audio`, { method: "POST", headers: { "Content-Type": "audio/wav" }, body: file }));
      await refreshRisk();
      $("file-info").textContent = `${file.name} · assessment received at ${new Date().toLocaleTimeString()}`;
    } finally { $("analyze-button").textContent = "Analyze recording ↗"; }
  });
});

$("action-form").addEventListener("submit", (event) => {
  event.preventDefault();
  run(async () => {
    if (state.action) return;
    const recipient = $("recipient").value.trim();
    const amount = Number($("amount").value);
    if (!recipient || recipient.length > 120 || !Number.isInteger(amount) || amount <= 0 || amount > 10000000) throw new Error("Enter a recipient (up to 120 characters) and a whole INR amount between 1 and 10,000,000.");
    const session_id = await ensureSession();
    const action = await api("/actions", { method: "POST", body: JSON.stringify({ session_id, action_type: "fund_transfer", payload: { amount, recipient } }) });
    if (!action.action_id) throw new Error("The server did not return an action ID.");
    state.action = action;
    $("recipient").value = recipient;
    renderAction();
    if (!ended()) $("verification-message").textContent = "Details are fixed. Request verification, then share the action ID with the verifier.";
    await refreshAudit();
  });
});

$("request-verification").addEventListener("click", () => run(async () => {
  if (!state.action || ended()) return;
  const challenge = await api(`/actions/${state.action.action_id}/verification`, { method: "POST" });
  if (!challenge.challenge_id || !active(challenge)) throw new Error("The server did not return a valid verification challenge.");
  state.challenge = challenge;
  state.approval = null;
  $("otp-code").value = "";
  $("verification-message").textContent = "Code requested. Ask the independent verifier to review this action in the local inbox.";
  await refreshAudit();
  window.setTimeout(() => $("otp-code").focus(), 0);
}));

$("verification-form").addEventListener("submit", (event) => {
  event.preventDefault();
  run(async () => {
    if (!state.action || !active(state.challenge) || ended()) throw new Error("There is no active challenge. Select New transfer; codes cannot be reissued for this action.");
    const otp_code = $("otp-code").value.trim();
    if (!/^[0-9]{6}$/.test(otp_code)) throw new Error("Enter the six-digit verification code.");
    const approval = await api(`/actions/${state.action.action_id}/confirm`, { method: "POST", body: JSON.stringify({ challenge_id: state.challenge.challenge_id, otp_code }) });
    if (!approval.approval_token || !active(approval)) throw new Error("The server did not return a valid action approval.");
    state.approval = approval;
    state.action.status = "VERIFIED";
    renderAction();
    $("otp-code").value = "";
    $("verification-message").textContent = "Code verified for this action. Complete the transfer before the approval expires; the backend rechecks current evidence.";
    await refreshAudit();
  });
});

$("complete-action").addEventListener("click", () => run(async () => {
  if (!state.action || !active(state.approval) || ended()) throw new Error("Approval is missing or expired. Select New transfer.");
  const action = await api(`/actions/${state.action.action_id}/complete`, { method: "POST", body: JSON.stringify({ approval_token: state.approval.approval_token }) });
  if (action.status !== "COMPLETED" || action.allowed !== true) throw new Error(action.message || "The backend did not approve this transfer.");
  state.action = { ...state.action, ...action };
  state.approval = null;
  state.challenge = null;
  renderAction();
  notice("Simulated transfer completed after independent verification. No money was moved.", "good");
  await refreshAudit();
}));

$("new-action").addEventListener("click", () => {
  if (state.busy) return;
  state.action = null;
  state.challenge = null;
  state.approval = null;
  $("otp-code").value = "";
  $("audit-list").replaceChildren();
  $("audit-empty").hidden = false;
  $("verification-message").textContent = "Prepare a new transfer. Earlier actions and their audit events remain stored.";
  notice("");
  renderAction();
  renderControls();
  $("recipient").focus();
});
$("refresh-risk").addEventListener("click", () => run(refreshRisk));
$("refresh-audit").addEventListener("click", () => run(refreshAudit));
$("copy-action").addEventListener("click", () => run(async () => {
  if (!state.action) return;
  await navigator.clipboard.writeText(state.action.action_id);
  notice("Action ID copied. Share it with the independent verifier.", "good");
}));

let refreshing = false;
let lastRefresh = 0;
window.setInterval(() => {
  if (state.challenge) {
    const remaining = Math.max(0, Math.ceil((Date.parse(state.challenge.expires_at) - Date.now()) / 1000));
    $("challenge-expiry").textContent = remaining ? `${remaining}s remaining` : "Code expired";
    if (!remaining && !state.approval) $("verification-message").textContent = "Code expired. Select New transfer; codes cannot be reissued for this action.";
  }
  if (state.approval && !active(state.approval)) {
    state.approval = null;
    $("verification-message").textContent = "Approval expired. Select New transfer; this action cannot receive another code.";
  }
  renderControls();
  if (state.busy || refreshing || !state.session || !(state.live || state.action) || Date.now() - lastRefresh < 2000) return;
  lastRefresh = Date.now();
  refreshing = true;
  (async () => { await refreshRisk(); if (state.action && !ended()) await refreshAction(); })()
    .catch(() => {
      renderRisk({ risk_state: "SERVICE_UNAVAILABLE", reason_codes: ["STATUS_REFRESH_FAILED"] });
      $("evidence-age").textContent = "Unavailable";
      notice("Could not refresh evidence or action status. Completion remains unavailable.");
    })
    .finally(() => { refreshing = false; renderControls(); });
}, 1000);

api("/system").then((system) => {
  state.systemReady = Boolean(system.ready);
  state.verifierAvailable = Boolean(system.demo_verification_enabled);
  $("service-status").textContent = system.ready ? "System ready" : "System unavailable";
  $("service-status").dataset.ready = String(Boolean(system.ready));
  $("model-version").textContent = system.model_version || "Unavailable";
  if (!system.ready) renderRisk({ risk_state: "SERVICE_UNAVAILABLE", reason_codes: ["SERVING_PATH_UNAVAILABLE"], model_version: system.model_version });
  if (!system.demo_verification_enabled) {
    $("verifier-link").hidden = true;
    $("verification-message").textContent = "The local verifier inbox is disabled on this server.";
  }
  renderControls();
}).catch((error) => {
  $("service-status").textContent = "Backend unavailable";
  $("model-version").textContent = "Unavailable";
  notice(`Could not read server status. ${error.message}`);
});
