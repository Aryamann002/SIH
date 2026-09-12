"use strict";

const $ = (id) => document.getElementById(id);
const state = { session: null, action: null, challenge: null, approval: null, busy: false, audioUrl: null, audioFile: null, microphone: null };
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
  $("analyze-button").disabled = busy || !state.audioFile;
  $("audio-file").disabled = busy;
  $("record-start").disabled = busy || !MicrophoneAudio.supported();
  $("record-stop").disabled = !state.microphone?.ready;
  $("record-cancel").disabled = !state.microphone;
  $("refresh-risk").disabled = busy || !state.session;
  $("create-action").disabled = busy || Boolean(action);
  $("transfer-fields").disabled = busy || Boolean(action);
  $("create-action").hidden = Boolean(action);
  $("new-action").disabled = busy;
  $("refresh-audit").disabled = busy || !action;
  $("request-verification").disabled = busy || !action || ended() || active(challenge) || active(approval);
  $("verification-form").hidden = !challenge || Boolean(approval) || ended();
  $("confirm-code").disabled = busy || !active(challenge) || ended();
  $("otp-code").disabled = busy || !active(challenge) || ended();
  $("complete-action").hidden = !approval || ended();
  $("complete-action").disabled = busy || !active(approval);
}

async function run(task) {
  if (state.busy) return;
  state.busy = true;
  notice("");
  renderControls();
  try { await task(); }
  catch (error) {
    notice(error.message || String(error));
    if (state.action) await refreshAudit().catch(() => {});
  } finally { state.busy = false; renderControls(); }
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
  $("reason-codes").replaceChildren();
  for (const reason of data.reason_codes || []) {
    const item = document.createElement("li");
    item.textContent = String(reason);
    $("reason-codes").append(item);
  }
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
  state.microphone?.cancel();
  if (state.audioUrl) URL.revokeObjectURL(state.audioUrl);
});
if (!MicrophoneAudio.supported()) $("record-status").textContent = "Microphone recording is unavailable here. Open in a supported browser on localhost or HTTPS, or upload a WAV file.";
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
    if (!state.action || !active(state.challenge) || ended()) throw new Error("There is no active challenge. Request a new code.");
    const otp_code = $("otp-code").value.trim();
    if (!/^[0-9]{6}$/.test(otp_code)) throw new Error("Enter the six-digit verification code.");
    const approval = await api(`/actions/${state.action.action_id}/confirm`, { method: "POST", body: JSON.stringify({ challenge_id: state.challenge.challenge_id, otp_code }) });
    if (!approval.approval_token || !active(approval)) throw new Error("The server did not return a valid action approval.");
    state.approval = approval;
    $("otp-code").value = "";
    $("verification-message").textContent = "Code verified for this action. Complete the transfer before the approval expires; the backend rechecks current evidence.";
    await refreshAudit();
  });
});

$("complete-action").addEventListener("click", () => run(async () => {
  if (!state.action || !active(state.approval) || ended()) throw new Error("Approval is missing or expired. Request verification again.");
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

window.setInterval(() => {
  if (state.challenge) {
    const remaining = Math.max(0, Math.ceil((Date.parse(state.challenge.expires_at) - Date.now()) / 1000));
    $("challenge-expiry").textContent = remaining ? `${remaining}s remaining` : "Code expired";
  }
  if (state.approval && !active(state.approval)) {
    state.approval = null;
    state.challenge = null;
    $("verification-message").textContent = "Approval expired. Request verification again; the transfer is still unapproved.";
  }
  renderControls();
}, 1000);

api("/system").then((system) => {
  $("service-status").textContent = system.detector_available ? "Detector available" : "Detector unavailable";
  $("service-status").dataset.ready = String(Boolean(system.detector_available));
  $("model-version").textContent = system.model_version || "Unavailable";
  if (!system.detector_available) renderRisk({ risk_state: "SERVICE_UNAVAILABLE", reason_codes: ["MODEL_UNAVAILABLE"], model_version: system.model_version });
  if (!system.demo_verification_enabled) {
    $("verifier-link").hidden = true;
    $("verification-message").textContent = "The local verifier inbox is disabled on this server.";
  }
}).catch((error) => {
  $("service-status").textContent = "Backend unavailable";
  $("model-version").textContent = "Unavailable";
  notice(`Could not read server status. ${error.message}`);
});
