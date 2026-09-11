"use strict";

const $ = (id) => document.getElementById(id);
let expiresAt = null;

$("inbox-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const actionId = $("action-id").value.trim();
  const verifierKey = $("verifier-key").value;
  $("notice").hidden = true;
  $("inbox-result").hidden = true;
  $("review-code").textContent = "";
  expiresAt = null;
  $("open-inbox").disabled = true;
  try {
    if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(actionId)) throw new Error("Enter a valid action ID.");
    const response = await fetch(`/api/v1/demo/inbox/${encodeURIComponent(actionId)}`, { headers: { "X-Demo-Verifier-Key": verifierKey }, cache: "no-store" });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(`${response.status}: ${typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail || data)}`);
    if (data.action_id !== actionId || !/^[0-9]{6}$/.test(data.otp_code) || !(Date.parse(data.expires_at) > Date.now())) throw new Error("The server did not return a valid code for this action.");
    $("review-recipient").textContent = String(data.payload?.recipient || "Not provided");
    const amount = Number(data.payload?.amount);
    $("review-amount").textContent = Number.isFinite(amount) ? new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" }).format(amount) : "Not provided";
    $("review-action").textContent = data.action_id;
    $("review-code").textContent = data.otp_code;
    $("inbox-result").hidden = false;
    expiresAt = Date.parse(data.expires_at);
    updateExpiry();
  } catch (error) {
    $("notice").textContent = error.message || String(error);
    $("notice").hidden = false;
  } finally {
    $("verifier-key").value = "";
    $("open-inbox").disabled = false;
  }
});

function updateExpiry() {
  if (!expiresAt) return;
  const remaining = Math.max(0, Math.ceil((expiresAt - Date.now()) / 1000));
  $("review-expiry").textContent = remaining ? `Expires in ${remaining} seconds. Single-use, and bound to this action.` : "Code expired. Ask the operator to request verification again.";
  if (!remaining) $("review-code").textContent = "Expired";
}
window.setInterval(updateExpiry, 1000);
window.addEventListener("pagehide", () => {
  $("verifier-key").value = "";
  $("review-code").textContent = "";
  expiresAt = null;
});
