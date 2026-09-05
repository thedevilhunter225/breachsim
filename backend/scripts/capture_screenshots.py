"""Capture console screenshots for the FYP report, poster and demo slides.

Drives a headless Chrome over the DevTools Protocol. The admin session is injected into
``localStorage`` before each navigation, so authenticated pages render exactly as they do
for a signed-in administrator without scripting a login form.

Usage::

    python scripts/capture_screenshots.py
    python scripts/capture_screenshots.py --out ../docs/screenshots --theme dark
    python scripts/capture_screenshots.py --only dashboard,personas

Requires a running backend and frontend. Chrome is located automatically on Windows and
common Linux/macOS paths, or pass --chrome.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import httpx
import websockets

DEFAULT_API = "http://127.0.0.1:8000"
DEFAULT_APP = "http://localhost:3000"
SESSION_KEY = "breachsim.session"

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
]

#: (filename, path, needs_auth, settle_seconds)
PAGES = [
    ("01-login", "/login", False, 1.6),
    ("02-dashboard", "/dashboard", True, 3.2),
    ("03-scenario-studio", "/scenario-lab", True, 3.0),
    ("04-campaigns", "/campaigns", True, 3.0),
    ("05-personas", "/personas", True, 2.6),
    ("06-controls", "/policies", True, 2.4),
    ("07-analytics", "/analytics", True, 3.2),
    ("08-risk-intelligence", "/risk-intelligence", True, 3.2),
    ("09-employees", "/employees", True, 3.0),
    ("10-reports", "/reports", True, 2.6),
    ("11-audit", "/audit", True, 2.6),
    ("12-settings", "/settings", True, 2.4),
]


def find_chrome(explicit: str | None) -> str:
    if explicit:
        return explicit
    for candidate in CHROME_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    found = shutil.which("chrome") or shutil.which("google-chrome") or shutil.which("chromium")
    if found:
        return found
    raise SystemExit("Could not locate Chrome. Pass --chrome /path/to/chrome.")


def login(api_base: str, email: str, password: str) -> dict:
    response = httpx.post(
        f"{api_base.rstrip('/')}/api/v1/auth/login",
        json={"email": email, "password": password},
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()


class Chrome:
    """Minimal DevTools Protocol driver: launch, one tab per page, capture, quit."""

    def __init__(self, binary: str, port: int) -> None:
        self.binary = binary
        self.port = port
        self.profile = Path(tempfile.mkdtemp(prefix="breachsim-shots-"))
        self.process: subprocess.Popen | None = None

    def start(self) -> None:
        self.process = subprocess.Popen(
            [
                self.binary,
                "--headless=new",
                f"--remote-debugging-port={self.port}",
                f"--user-data-dir={self.profile}",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-extensions",
                "--disable-gpu",
                "--hide-scrollbars",
                "--force-color-profile=srgb",
                "--force-device-scale-factor=2",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                httpx.get(f"http://127.0.0.1:{self.port}/json/version", timeout=2.0).raise_for_status()
                return
            except Exception:  # noqa: BLE001 - Chrome is still binding the port
                time.sleep(0.4)
        raise SystemExit("Chrome did not expose its debugging port in time.")

    def new_tab(self) -> str:
        for method in ("put", "get"):
            try:
                response = getattr(httpx, method)(
                    f"http://127.0.0.1:{self.port}/json/new?about:blank", timeout=10.0
                )
                if response.status_code < 400:
                    return response.json()["webSocketDebuggerUrl"]
            except Exception:  # noqa: BLE001 - fall through to the other verb
                continue
        raise SystemExit("Could not open a Chrome tab over CDP.")

    def close_tab(self, target_id: str) -> None:
        try:
            httpx.get(f"http://127.0.0.1:{self.port}/json/close/{target_id}", timeout=5.0)
        except Exception:  # noqa: BLE001 - best effort
            pass

    def stop(self) -> None:
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
        shutil.rmtree(self.profile, ignore_errors=True)


class Session:
    def __init__(self, websocket) -> None:
        self.websocket = websocket
        self.counter = 0

    async def send(self, method: str, params: dict | None = None) -> dict:
        self.counter += 1
        message_id = self.counter
        await self.websocket.send(json.dumps({"id": message_id, "method": method, "params": params or {}}))
        while True:
            raw = await asyncio.wait_for(self.websocket.recv(), timeout=60)
            message = json.loads(raw)
            if message.get("id") == message_id:
                if "error" in message:
                    raise RuntimeError(f"{method} failed: {message['error']}")
                return message.get("result", {})


async def capture(
    chrome: Chrome,
    *,
    url: str,
    out_path: Path,
    bootstrap_script: str | None,
    width: int,
    settle: float,
) -> tuple[int, int]:
    ws_url = chrome.new_tab()
    target_id = ws_url.rstrip("/").rsplit("/", 1)[-1]

    async with websockets.connect(ws_url, max_size=80 * 1024 * 1024) as websocket:
        session = Session(websocket)
        await session.send("Page.enable")
        await session.send("Runtime.enable")
        await session.send(
            "Emulation.setDeviceMetricsOverride",
            {"width": width, "height": 900, "deviceScaleFactor": 2, "mobile": False},
        )
        if bootstrap_script:
            # Runs before any page script, so the app boots already authenticated.
            await session.send("Page.addScriptToEvaluateOnNewDocument", {"source": bootstrap_script})

        await session.send("Page.navigate", {"url": url})
        # Give the client-side data fetches time to resolve and charts time to lay out.
        await asyncio.sleep(settle)

        # Fast-forward any entrance animations to their end state. `captureBeyondViewport`
        # forces a re-layout that can restart CSS animations, which would otherwise capture
        # a staggered reveal at frame zero and look like missing content.
        await session.send(
            "Runtime.evaluate",
            {
                "expression": (
                    "document.getAnimations().forEach(a => { try { a.finish(); } catch (e) {} });"
                    "document.documentElement.classList.add('capture-static');"
                ),
                "awaitPromise": False,
            },
        )
        await asyncio.sleep(0.35)

        metrics = await session.send("Page.getLayoutMetrics")
        content = metrics.get("cssContentSize") or metrics.get("contentSize") or {}
        full_width = int(content.get("width") or width)
        full_height = int(content.get("height") or 900)
        # Guard against a runaway height blowing up the PNG.
        full_height = min(full_height, 6000)

        shot = await session.send(
            "Page.captureScreenshot",
            {
                "format": "png",
                "captureBeyondViewport": True,
                "clip": {"x": 0, "y": 0, "width": full_width, "height": full_height, "scale": 1},
            },
        )
        out_path.write_bytes(base64.b64decode(shot["data"]))

    chrome.close_tab(target_id)
    return full_width, full_height


def bootstrap(session_payload: dict, theme: str) -> str:
    return (
        f"try {{"
        f"localStorage.setItem({json.dumps(SESSION_KEY)}, {json.dumps(json.dumps(session_payload))});"
        f"localStorage.setItem('breachsim.theme', {json.dumps(theme)});"
        f"document.documentElement.setAttribute('data-theme', {json.dumps(theme)});"
        f"}} catch (e) {{}}"
    )


async def run(args: argparse.Namespace) -> int:
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        session_payload = login(args.api, args.email, args.password)
    except Exception as exc:  # noqa: BLE001
        print(f"Could not sign in against {args.api}: {exc}")
        print("Start the API first:  uvicorn app.main:app --port 8000")
        return 1

    wanted = {name.strip() for name in args.only.split(",")} if args.only else None
    pages = [
        page
        for page in PAGES
        if not wanted or page[0] in wanted or page[0].split("-", 1)[-1] in wanted
    ]
    if args.extra:
        for index, raw in enumerate(args.extra):
            label, _, path = raw.partition("=")
            pages.append((label or f"extra-{index}", path or label, False, 3.0))

    chrome = Chrome(find_chrome(args.chrome), args.port)
    print(f"Launching Chrome ({chrome.binary})")
    chrome.start()

    written: list[Path] = []
    try:
        for name, path, needs_auth, settle in pages:
            # Accept either an app-relative path or a full URL. Some shells (Git Bash on
            # Windows) rewrite a leading "/..." into a filesystem path, so passing the
            # whole URL is the reliable form for --extra.
            url = path if path.startswith("http") else f"{args.app.rstrip('/')}{path}"
            out_path = out_dir / f"{name}.png"
            script = bootstrap(session_payload, args.theme) if needs_auth else (
                f"try {{ document.documentElement.setAttribute('data-theme', {json.dumps(args.theme)}); }} catch (e) {{}}"
            )
            try:
                width, height = await capture(
                    chrome,
                    url=url,
                    out_path=out_path,
                    bootstrap_script=script,
                    width=args.width,
                    settle=settle,
                )
                size_kb = out_path.stat().st_size / 1024
                print(f"  {name:<24} {width}x{height}  {size_kb:6.0f} KB  {path}")
                written.append(out_path)
            except Exception as exc:  # noqa: BLE001 - one bad page must not abort the run
                print(f"  {name:<24} FAILED: {exc}")
    finally:
        chrome.stop()

    print(f"\n{len(written)} screenshot(s) written to {out_dir}")
    return 0 if written else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--app", default=DEFAULT_APP, help="Frontend base URL (default: %(default)s)")
    parser.add_argument("--api", default=DEFAULT_API, help="Backend base URL (default: %(default)s)")
    parser.add_argument("--out", default="../docs/screenshots", help="Output directory")
    parser.add_argument("--email", default="admin@breachsim-lab.com")
    parser.add_argument("--password", default="Admin123!")
    parser.add_argument("--theme", default="light", choices=["light", "dark"])
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--port", type=int, default=9333)
    parser.add_argument("--chrome", default=os.environ.get("CHROME_PATH"))
    parser.add_argument("--only", help="Comma-separated page names to capture")
    parser.add_argument(
        "--extra",
        nargs="*",
        help="Additional pages as label=/path or label=https://full/url",
    )
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
