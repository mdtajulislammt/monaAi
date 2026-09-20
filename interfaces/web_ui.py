"""Modern Web-based Desktop UI Server powered by Starlette and Uvicorn."""
import asyncio
import json
import logging
from pathlib import Path
from typing import Optional
import re
import webbrowser

import os
import shutil
import subprocess

from starlette.applications import Starlette
from starlette.responses import FileResponse, HTMLResponse, Response
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect
import uvicorn
try:
    import edge_tts
except ImportError:
    edge_tts = None

from config.settings import get_settings
from core.agent import DesktopAgent

logger = logging.getLogger(__name__)

UI_FILE = Path(__file__).resolve().parent.parent / "ui" / "index.html"
ICON_FILE = Path(__file__).resolve().parent.parent / "ui" / "icon.png"


async def homepage(request):
    """Serve the single-page voice & text UI."""
    if not UI_FILE.exists():
        return HTMLResponse("<h1>UI File not found</h1>", status_code=404)
    with open(UI_FILE, "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(html_content)


async def icon_endpoint(request):
    """Serve the monaAi app icon."""
    if ICON_FILE.exists():
        return FileResponse(ICON_FILE, media_type="image/png")
    return Response(b"", status_code=404)


async def tts_endpoint(request):
    """Generate authentic Bangladeshi Bengali Neural Voice Audio (edge-tts)."""
    if not edge_tts:
        return Response(b"", status_code=501)

    try:
        data = await request.json()
        raw_text = data.get("text", "")
        # Clean markdown, code blocks and symbols for clean speech synthesis
        clean = re.sub(r'```[\s\S]*?```', 'কোড নিচে দিয়ে দিয়েছি জান।', raw_text)
        clean = re.sub(r'`([^`]+)`', r'\1', clean)
        clean = re.sub(r'[*#_\[\]()•\->]', ' ', clean)
        clean = " ".join(clean.split()).strip()[:450]

        if not clean:
            return Response(b"", status_code=204)

        voice = data.get("voice", "bn-BD-NabanitaNeural")
        # Default to sweet, soft, feminine pitch & gentle romantic pacing for girlfriend persona
        if "Nabanita" in voice:
            pitch = data.get("pitch", "+5Hz")
            rate = data.get("rate", "-2%")
        else:
            pitch = data.get("pitch", "+0Hz")
            rate = data.get("rate", "+0%")

        communicate = edge_tts.Communicate(clean, voice, pitch=pitch, rate=rate)
        chunks = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])

        audio_bytes = b"".join(chunks)
        return Response(audio_bytes, media_type="audio/mpeg")
    except Exception as e:
        logger.error(f"TTS endpoint error: {e}")
        return Response(b"", status_code=500)


class AgentWebSocketHandler:
    """Manages WebSocket communication between the browser UI and DesktopAgent."""

    def __init__(self):
        self.settings = get_settings()
        self.active_websocket: Optional[WebSocket] = None
        self.lock = asyncio.Lock()

    async def handle_ws(self, websocket: WebSocket):
        await websocket.accept()
        loop = asyncio.get_running_loop()

        # Enforce single active client to prevent multiple windows talking at the same time
        async with self.lock:
            if self.active_websocket is not None and self.active_websocket != websocket:
                logger.info("Superseding previous WebSocket client to prevent double voice.")
                try:
                    await self.active_websocket.close(code=1000, reason="Superseded by new client")
                except Exception:
                    pass
            self.active_websocket = websocket

        # Callbacks that push events over WebSocket
        def on_tool_start(tool_name: str, args: dict):
            future = asyncio.run_coroutine_threadsafe(
                websocket.send_text(json.dumps({
                    "type": "tool_start",
                    "tool_name": tool_name,
                    "args": args,
                }, default=str)),
                loop,
            )
            future.result(timeout=5)

        def on_tool_end(tool_name: str, result: any):
            future = asyncio.run_coroutine_threadsafe(
                websocket.send_text(json.dumps({
                    "type": "tool_end",
                    "tool_name": tool_name,
                    "result": result,
                }, default=str)),
                loop,
            )
            future.result(timeout=5)

        # Create session agent
        agent = DesktopAgent(
            on_tool_start=on_tool_start,
            on_tool_end=on_tool_end,
        )

        try:
            while True:
                raw_data = await websocket.receive_text()
                message = json.loads(raw_data)
                action = message.get("action")

                if action == "reset":
                    agent.reset_session()
                    await websocket.send_text(json.dumps({"type": "reset_done"}))
                    continue

                if action == "chat":
                    user_text = message.get("text", "").strip()
                    if not user_text:
                        continue

                    try:
                        # Run synchronous Gemini agent chat in background thread
                        response = await asyncio.to_thread(agent.chat, user_text)
                        await websocket.send_text(json.dumps({
                            "type": "response",
                            "text": response,
                        }))
                    except Exception as e:
                        logger.error(f"Error in UI agent loop: {e}")
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "message": str(e),
                        }))

        except WebSocketDisconnect:
            logger.info("Browser client disconnected.")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            async with self.lock:
                if self.active_websocket == websocket:
                    self.active_websocket = None


handler = AgentWebSocketHandler()

routes = [
    Route("/", homepage),
    Route("/icon.png", icon_endpoint),
    Route("/tts", tts_endpoint, methods=["POST"]),
    WebSocketRoute("/ws", handler.handle_ws),
]

app = Starlette(routes=routes)


def find_browser_app_binary() -> Optional[str]:
    """Find installed Chrome/Chromium binary capable of standalone desktop app mode."""
    candidates = [
        "/opt/google/chrome/google-chrome",
        "/opt/google/chrome/chrome",
        shutil.which("google-chrome"),
        shutil.which("google-chrome-stable"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        shutil.which("brave-browser"),
        shutil.which("microsoft-edge"),
    ]
    for path in candidates:
        if path and Path(path).is_file() and os.access(path, os.X_OK):
            return str(Path(path).resolve())
    return None


def launch_desktop_window(url: str):
    """Launch monaAi as a dedicated standalone Desktop Application Window without browser tabs or address bar."""
    binary = find_browser_app_binary()
    if binary:
        profile_dir = Path(__file__).resolve().parent.parent / ".app_profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        # Clear stale singleton lock files
        for lock in profile_dir.glob("Singleton*"):
            try:
                lock.unlink()
            except Exception:
                pass

        cmd = [
            binary,
            f"--app={url}",
            f"--user-data-dir={str(profile_dir)}",
            "--class=monaAi",
            "--name=monaAi",
            "--window-size=1180,860",
            "--no-first-run",
            "--no-default-browser-check",
            "--autoplay-policy=no-user-gesture-required",
        ]
        try:
            logger.info(f"Launching standalone desktop window: {' '.join(cmd)}")
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return
        except Exception as e:
            logger.warning(f"Failed to launch standalone app window: {e}")

    # Fallback to default browser if no app-mode binary is found
    webbrowser.open(url)


def run_web_ui(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True):
    """Start local web backend and launch standalone desktop application window."""
    url = f"http://{host}:{port}"
    print(f"\n✨ Starting monaAi Desktop App at {url}")

    if open_browser:
        # Launch dedicated desktop app window in background thread after server starts
        async def open_app():
            await asyncio.sleep(0.9)
            launch_desktop_window(url)

        import threading
        threading.Thread(target=lambda: asyncio.run(open_app()), daemon=True).start()

    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    run_web_ui()
