"""Check the local dashboard in headless Chrome using a fake microphone WAV.

Requires the existing websockets dependency and installed Chrome/Edge. No real
microphone is accessed. Writes a screenshot and a check receipt under docs/.
"""
import argparse
import asyncio
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import tempfile
from urllib.request import Request, urlopen
from websockets.asyncio.client import connect

ROOT = Path(__file__).resolve().parents[1]


async def check(browser, output, presentation, base_url="http://127.0.0.1:8000/", action_flow=False):
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="vigilvoice-browser-", ignore_cleanup_errors=True) as profile:
        process = subprocess.Popen([
            str(browser), "--headless=new", "--no-first-run", "--no-default-browser-check",
            "--remote-debugging-port=0", f"--user-data-dir={profile}",
            "--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream",
            f"--use-file-for-fake-audio-capture={ROOT / 'models/demo/genuine.wav'}",
            "--autoplay-policy=no-user-gesture-required", "about:blank",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
           env={key: value for key, value in os.environ.items() if key != "VIGILVOICE_TEST_VERIFIER_KEY"},
           creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        try:
            active_port = Path(profile) / "DevToolsActivePort"
            for _ in range(100):
                if active_port.exists():
                    break
                await asyncio.sleep(0.1)
            port = int(active_port.read_text().splitlines()[0])
            with urlopen(f"http://127.0.0.1:{port}/json/list", timeout=5) as response:
                page = next(item for item in json.load(response) if item["type"] == "page")
            async with connect(page["webSocketDebuggerUrl"], max_size=20_000_000) as ws:
                serial = 0
                exceptions = []

                async def command(method, **params):
                    nonlocal serial
                    serial += 1
                    await ws.send(json.dumps({"id": serial, "method": method, "params": params}))
                    while True:
                        message = json.loads(await asyncio.wait_for(ws.recv(), timeout=45))
                        if message.get("method") == "Runtime.exceptionThrown":
                            exceptions.append(message["params"])
                        if message.get("id") == serial:
                            assert "error" not in message, message
                            return message.get("result", {})

                async def js(expression):
                    result = await command("Runtime.evaluate", expression=expression, returnByValue=True,
                                           awaitPromise=True, userGesture=True)
                    assert "exceptionDetails" not in result, result
                    return result.get("result", {}).get("value")

                async def until(expression):
                    for _ in range(150):
                        if await js(expression):
                            return
                        await asyncio.sleep(0.2)
                    raise AssertionError(f"Browser condition timed out: {expression}")

                await command("Page.enable")
                await command("Runtime.enable")
                await command("Emulation.setDeviceMetricsOverride", width=1440, height=1100,
                              deviceScaleFactor=1, mobile=False)
                await command("Page.navigate", url=base_url)
                await until("document.getElementById('service-status')?.dataset.ready === 'true'")
                assert await js("MicrophoneAudio.supported()"), "Microphone browser APIs unavailable"
                assert await js("MicrophoneAudio.liveSupported()"), "AudioWorklet streaming unavailable"
                await js("document.getElementById('live-start').click()")
                await until("state.live?.capture.ready === true")
                await until("state.live?.results >= 2 && ['LOW','ELEVATED','HIGH'].includes(document.getElementById('risk-state').textContent) && parseFloat(document.getElementById('speech-duration').textContent) >= 1.5")
                live = await js("({results: state.live.results, ready: state.live.capture.ready, risk: document.getElementById('risk-state').textContent, speech: document.getElementById('speech-duration').textContent})")
                assert live["ready"] and live["results"] >= 2, live
                assert live["risk"] in ("LOW", "ELEVATED", "HIGH") and float(live["speech"].split()[0]) >= 1.5, live
                await js("document.getElementById('live-stop').click()")
                await until("state.live === null && !document.getElementById('audio-file').disabled")
                assert await js("document.getElementById('risk-state').textContent") == "SERVICE UNAVAILABLE"
                assert await js("document.getElementById('evidence-age').textContent") == "Unavailable"
                await until("(async () => { const response = await fetch('/api/v1/sessions/' + state.session.session_id, {headers: {Authorization: 'Bearer ' + state.session.session_token}}); return (await response.json()).status === 'DISCONNECTED'; })()")
                await js("document.getElementById('live-start').click()")
                await until("state.live?.capture.ready === true && state.live.results >= 2")
                await js("document.getElementById('live-stop').click()")
                await until("state.live === null && !document.getElementById('audio-file').disabled")
                await js("document.getElementById('record-start').click()")
                await until("state.microphone?.ready === true")
                await asyncio.sleep(4)
                await js("document.getElementById('record-stop').click()")
                await until("!state.busy && state.audioFile?.name === 'microphone.wav'")
                info = await js("({name: state.audioFile.name, type: state.audioFile.type, size: state.audioFile.size})")
                assert info["type"] == "audio/wav" and 64044 < info["size"] <= 320044, info
                await until("document.getElementById('audio-preview').readyState >= 2")
                await js("document.getElementById('analyze-button').click()")
                await until("!state.busy && state.session !== null")
                assert await js("document.getElementById('notice').hidden"), await js("document.getElementById('notice').textContent")
                risk = await js("document.getElementById('risk-state').textContent")
                assert risk in ("LOW", "ELEVATED", "HIGH", "POOR QUALITY", "INSUFFICIENT EVIDENCE"), risk
                age = await js("document.getElementById('evidence-age').textContent")
                assert age.endswith(" s old") if risk in ("LOW", "ELEVATED", "HIGH") else age == "Unavailable", age
                action_result = None
                if action_flow:
                    verifier_key = os.environ.get("VIGILVOICE_TEST_VERIFIER_KEY")
                    assert verifier_key, "Set VIGILVOICE_TEST_VERIFIER_KEY for isolated action-flow testing"
                    assert risk in ("LOW", "ELEVATED"), f"Genuine demo audio was not eligible: {risk}"
                    await js("document.getElementById('create-action').click()")
                    await until("state.action?.status === 'PENDING' && !state.busy")
                    await until("!document.getElementById('request-verification').disabled")
                    await js("document.getElementById('request-verification').click()")
                    await until("state.challenge?.challenge_id && !state.busy")
                    action_id = await js("state.action.action_id")
                    inbox_request = Request(base_url.rstrip("/") + f"/api/v1/demo/inbox/{action_id}",
                                            headers={"X-Demo-Verifier-Key": verifier_key})
                    with urlopen(inbox_request, timeout=10) as inbox_response:
                        delivered = json.load(inbox_response)
                    assert delivered["action_id"] == action_id
                    assert delivered["payload"] == {"recipient": "Demo beneficiary", "amount": 25000}
                    code = delivered["otp_code"]
                    assert len(code) == 6 and code.isdigit()
                    await js(f"document.getElementById('otp-code').value = {json.dumps(code)}; document.getElementById('confirm-code').click()")
                    code = None
                    await until("state.action?.status === 'VERIFIED' && state.approval && !state.busy")
                    await js("document.getElementById('complete-action').click()")
                    await until("state.action?.status === 'COMPLETED' && !state.busy")
                    assert await js("[...document.querySelectorAll('#audit-list strong')].some(node => node.textContent === 'ACTION COMPLETED')")
                    await js("document.getElementById('new-action').click()")
                    synthetic = base64.b64encode((ROOT / "models/demo/synthetic.wav").read_bytes()).decode("ascii")
                    await js("window.syntheticBytes = Uint8Array.from(atob('" + synthetic + "'), c => c.charCodeAt(0))")
                    await js("document.getElementById('live-start').click()")
                    await until("state.live?.capture.ready === true && state.live.results >= 2 && document.getElementById('risk-state').textContent === 'LOW'")
                    await js("document.getElementById('create-action').click()")
                    await until("state.action?.status === 'PENDING' && !state.busy")
                    await until("!document.getElementById('request-verification').disabled")
                    await js("document.getElementById('request-verification').click()")
                    await until("state.challenge?.challenge_id && !state.busy")
                    live_action_id = await js("state.action.action_id")
                    live_inbox_request = Request(base_url.rstrip("/") + f"/api/v1/demo/inbox/{live_action_id}",
                                                 headers={"X-Demo-Verifier-Key": verifier_key})
                    with urlopen(live_inbox_request, timeout=10) as inbox_response:
                        live_code = json.load(inbox_response)["otp_code"]
                    await js(f"document.getElementById('otp-code').value = {json.dumps(live_code)}; document.getElementById('confirm-code').click()")
                    live_code = None
                    await until("state.action?.status === 'VERIFIED' && state.approval && !state.busy")
                    # Test-only frame substitution keeps the same authenticated stream and sequence cadence.
                    await js("""window.injectSynthetic = false; window.syntheticOffset = 0;
                        const originalSend = state.live.socket.send.bind(state.live.socket);
                        state.live.socket.send = function(packet) {
                          if (!window.injectSynthetic || !(packet instanceof ArrayBuffer) || packet.byteLength !== 6404) return originalSend(packet);
                          const replacement = packet.slice(0);
                          const target = new Uint8Array(replacement, 4);
                          const source = window.syntheticBytes.subarray(44);
                          const first = Math.min(target.length, source.length - window.syntheticOffset);
                          target.set(source.subarray(window.syntheticOffset, window.syntheticOffset + first));
                          if (first < target.length) target.set(source.subarray(0, target.length - first), first);
                          window.syntheticOffset = (window.syntheticOffset + target.length) % source.length;
                          return originalSend(replacement);
                        }; window.injectSynthetic = true""")
                    await until("document.getElementById('risk-state').textContent === 'HIGH' && state.action?.status === 'BLOCKED'")
                    assert await js("document.getElementById('complete-action').disabled || document.getElementById('complete-action').hidden")
                    assert await js("[...document.querySelectorAll('#audit-list strong')].some(node => node.textContent === 'ACTION BLOCKED')")
                    denied = "(async () => { const response = await fetch('/api/v1/actions/' + state.action.action_id + '/complete', {method:'POST', headers:{Authorization:'Bearer ' + state.session.session_token, 'Content-Type':'application/json'}, body:JSON.stringify({approval_token:state.approval.approval_token})}); return response.status; })()"
                    assert await js(denied) == 409
                    await js("window.injectSynthetic = false")
                    await until("document.getElementById('risk-state').textContent === 'LOW'")
                    assert await js("state.action.status") == "BLOCKED"
                    await js("document.getElementById('live-stop').click()")
                    await until("state.live === null")
                    await until("(async () => { const response = await fetch('/api/v1/sessions/' + state.session.session_id, {headers: {Authorization: 'Bearer ' + state.session.session_token}}); return (await response.json()).status === 'DISCONNECTED'; })()")
                    await js("document.getElementById('new-action').click(); document.getElementById('analyze-button').click()")
                    await until("!state.busy && ['LOW','ELEVATED'].includes(document.getElementById('risk-state').textContent)")
                    await js("document.getElementById('create-action').click()")
                    await until("state.action?.status === 'PENDING' && !state.busy")
                    injection = "(async () => { const response = await fetch('/api/v1/sessions/' + state.session.session_id + '/audio', {method:'POST', headers:{Authorization:'Bearer ' + state.session.session_token, 'Content-Type':'audio/wav'}, body:new Blob([window.syntheticBytes], {type:'audio/wav'})}); return response.status; })()"
                    assert await js(injection) == 200
                    await until("state.action?.status === 'BLOCKED' && document.getElementById('risk-state').textContent === 'HIGH'")
                    assert await js("document.getElementById('request-verification').disabled")
                    assert await js("[...document.querySelectorAll('#audit-list strong')].some(node => node.textContent === 'ACTION BLOCKED')")
                    await js("document.getElementById('new-action').click()")
                    await js("selectAudio(new File([window.syntheticBytes], 'synthetic.wav', {type:'audio/wav'}))")
                    await js("document.getElementById('analyze-button').click()")
                    await until("!state.busy && document.getElementById('risk-state').textContent === 'HIGH'")
                    await js("document.getElementById('create-action').click()")
                    await until("state.action?.status === 'BLOCKED' && !state.busy")
                    assert await js("document.getElementById('request-verification').disabled && document.getElementById('complete-action').hidden")
                    assert await js("[...document.querySelectorAll('#audit-list strong')].some(node => node.textContent === 'ACTION CREATED')")
                    assert await js("[...document.querySelectorAll('#audit-list strong')].some(node => node.textContent === 'JEV DECISION')")
                    action_result = {"genuine": "COMPLETED after action-bound verification",
                                     "live_transition": "verified action BLOCKED by HIGH on same stream; completion denied after later LOW",
                                     "source_replacement": "pending action BLOCKED and visible in browser",
                                     "synthetic": "HIGH and BLOCKED", "unauthorized_completions": 0}
                assert not exceptions, exceptions
                # Full dashboard is the presentation fallback if the server is unavailable later.
                dimensions = (await command("Page.getLayoutMetrics"))["cssContentSize"]
                screenshot = await command("Page.captureScreenshot", captureBeyondViewport=True,
                                           clip={"x": 0, "y": 0, "width": 1440, "height": dimensions["height"], "scale": 1})
                (output / "teacher-demo.png").write_bytes(base64.b64decode(screenshot["data"]))
                await command("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=1, mobile=True)
                assert await js("document.documentElement.scrollWidth <= 390"), "Mobile page overflows"
                checks = ["Authenticated AudioWorklet stream", "Repeated live inference while capture continued",
                          "Live stop clears risk and evidence age", "Reconnect starts a new stream", "Safe live stop and WAV fallback", "Native fake microphone recording", "16 kHz PCM WAV conversion",
                          "Blob preview allowed by CSP", "Real authenticated backend upload",
                          "No JavaScript exceptions", "390px mobile layout has no horizontal overflow"]
                if action_flow:
                    checks.extend(["Action-bound genuine completion", "Verified action blocked by live HIGH despite later LOW",
                                   "Pending action blocked on source replacement", "Synthetic WAV HIGH blocks new action"])
                report = {"generated_at": datetime.now(timezone.utc).isoformat(), "passed": True,
                          "checks": checks,
                          "live": live, "recording": info, "risk_state": risk, "action_flow": action_result,
                          "limitation": "Automated fake audio device; physical microphone and OS permission interaction need manual rehearsal."}
                (output / "browser-checks.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
                print(json.dumps(report, indent=2))
                if presentation:
                    await command("Page.navigate", url=presentation.resolve().as_uri())
                    await until("document.readyState === 'complete' && document.title.includes('Presentation')")
                    pdf = await command("Page.printToPDF", printBackground=True, preferCSSPageSize=True)
                    presentation.with_suffix(".pdf").write_bytes(base64.b64decode(pdf["data"]))
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    candidates = [Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
                  Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")]
    parser.add_argument("--browser", type=Path, default=next((path for path in candidates if path.exists()), None))
    parser.add_argument("--output", type=Path, default=ROOT / "docs")
    parser.add_argument("--presentation", type=Path)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/")
    parser.add_argument("--action-flow", action="store_true", help="Run isolated browser/action test with VIGILVOICE_TEST_VERIFIER_KEY")
    args = parser.parse_args()
    if not args.browser or not args.browser.is_file():
        parser.error("Provide --browser with an installed Chrome or Edge executable")
    asyncio.run(check(args.browser.resolve(), args.output.resolve(), args.presentation, args.base_url, args.action_flow))
