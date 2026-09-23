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
from urllib.request import urlopen
from websockets.asyncio.client import connect

ROOT = Path(__file__).resolve().parents[1]


async def check(browser, output, presentation):
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="vigilvoice-browser-", ignore_cleanup_errors=True) as profile:
        process = subprocess.Popen([
            str(browser), "--headless=new", "--no-first-run", "--no-default-browser-check",
            "--remote-debugging-port=0", f"--user-data-dir={profile}",
            "--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream",
            f"--use-file-for-fake-audio-capture={ROOT / 'models/demo/genuine.wav'}",
            "--autoplay-policy=no-user-gesture-required", "about:blank",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
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
                await command("Page.navigate", url="http://127.0.0.1:8000/")
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
                assert not exceptions, exceptions
                # Full dashboard is the presentation fallback if the server is unavailable later.
                dimensions = (await command("Page.getLayoutMetrics"))["cssContentSize"]
                screenshot = await command("Page.captureScreenshot", captureBeyondViewport=True,
                                           clip={"x": 0, "y": 0, "width": 1440, "height": dimensions["height"], "scale": 1})
                (output / "teacher-demo.png").write_bytes(base64.b64decode(screenshot["data"]))
                await command("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=1, mobile=True)
                assert await js("document.documentElement.scrollWidth <= 390"), "Mobile page overflows"
                report = {"generated_at": datetime.now(timezone.utc).isoformat(), "passed": True,
                          "checks": ["Authenticated AudioWorklet stream", "Repeated live inference while capture continued",
                                     "Safe live stop and WAV fallback", "Native fake microphone recording", "16 kHz PCM WAV conversion",
                                     "Blob preview allowed by CSP", "Real authenticated backend upload",
                                     "No JavaScript exceptions", "390px mobile layout has no horizontal overflow"],
                          "live": live, "recording": info, "risk_state": risk,
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
    args = parser.parse_args()
    if not args.browser or not args.browser.is_file():
        parser.error("Provide --browser with an installed Chrome or Edge executable")
    asyncio.run(check(args.browser.resolve(), args.output.resolve(), args.presentation))
