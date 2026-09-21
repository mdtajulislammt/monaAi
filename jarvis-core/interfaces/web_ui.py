"""Modern Web-based Desktop UI Server powered by Starlette and Uvicorn for JARVIS."""
import asyncio
import importlib.util
import json
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Optional
import webbrowser

from starlette.applications import Starlette
from starlette.responses import FileResponse, HTMLResponse, Response
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect
import uvicorn
try:
    import edge_tts
except ImportError:
    edge_tts = None

# Ensure jarvis-core directory is in sys.path
JARVIS_DIR = Path(__file__).resolve().parent.parent
if str(JARVIS_DIR) not in sys.path:
    sys.path.insert(0, str(JARVIS_DIR))

from config.settings import get_settings
from core.agent import JarvisAgent
from tools.system_tools import get_system_telemetry

logger = logging.getLogger("jarvis.web_ui")

PROJECT_ROOT = JARVIS_DIR.parent
UI_FILE = PROJECT_ROOT / "ui" / "index.html"
ICON_FILE = PROJECT_ROOT / "ui" / "icon.png"


async def homepage(request):
    """Serve the single-page voice & text UI."""
    if not UI_FILE.exists():
        return HTMLResponse("<h1>UI File not found</h1>", status_code=404)
    with open(UI_FILE, "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(html_content)


async def icon_endpoint(request):
    """Serve the JARVIS app icon."""
    if ICON_FILE.exists():
        return FileResponse(ICON_FILE, media_type="image/png")
    return Response(b"", status_code=404)


async def tts_endpoint(request):
    """Generate Bengali Voice Audio using ElevenLabs (with automatic edge-tts fallback)."""
    settings = get_settings()

    try:
        data = await request.json()
        raw_text = data.get("text", "")
        # Clean markdown, code blocks and symbols for clean speech synthesis
        clean = re.sub(r'```[\s\S]*?```', 'কোড নিচে স্ক্রিনে দিয়ে দিয়েছি স্যার।', raw_text)
        clean = re.sub(r'`([^`]+)`', r'\1', clean)
        # Phonetic transliterations for natural Bengali audio
        clean = re.sub(r'\b(VS Code|vscode)\b', 'ভিএস কোড', clean, flags=re.IGNORECASE)
        clean = re.sub(r'\bTerminal\b', 'টার্মিনাল', clean, flags=re.IGNORECASE)
        clean = re.sub(r'\bChrome\b', 'ক্রোম', clean, flags=re.IGNORECASE)
        clean = re.sub(r'\bTelegram\b', 'টেলিগ্রাম', clean, flags=re.IGNORECASE)
        clean = re.sub(r'\bRAM\b', 'র‍্যাম', clean, flags=re.IGNORECASE)
        clean = re.sub(r'\bCPU\b', 'সিপিইউ', clean, flags=re.IGNORECASE)
        clean = re.sub(r'\bJARVIS\b', 'জার্ভিস', clean, flags=re.IGNORECASE)
        clean = re.sub(r'[*#_\[\]()•\->]', ' ', clean)
        clean = " ".join(clean.split()).strip()[:450]

        if not clean:
            return Response(b"", status_code=204)

        # Attempt 1: ElevenLabs AI Voice (Ultra-realistic Bengali Girl Voice)
        if settings.tts_provider == "elevenlabs" and settings.elevenlabs_api_key:
            try:
                import httpx
                voice_id = settings.elevenlabs_voice_id or "EXAVITQu4vr4xnSDxMaL"
                model_id = settings.elevenlabs_model_id or "eleven_multilingual_v2"
                url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
                headers = {
                    "xi-api-key": settings.elevenlabs_api_key,
                    "Content-Type": "application/json",
                }
                payload = {
                    "text": clean,
                    "model_id": model_id,
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.8,
                    }
                }
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(url, headers=headers, json=payload)
                    if resp.status_code == 200 and len(resp.content) > 100:
                        return Response(resp.content, media_type="audio/mpeg")
                    else:
                        logger.warning(f"ElevenLabs TTS status {resp.status_code}. Falling back to edge-tts.")
            except Exception as e:
                logger.warning(f"ElevenLabs TTS failed ({e}). Falling back to edge-tts.")

        # Attempt 2: Microsoft edge-tts (Authentic local Bangladeshi voice, unlimited)
        if edge_tts:
            voice = data.get("voice", settings.voice_name or "bn-BD-NabanitaNeural")
            pitch = data.get("pitch", "+0Hz")
            rate = data.get("rate", "+0%")

            communicate = edge_tts.Communicate(clean, voice, pitch=pitch, rate=rate)
            chunks = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    chunks.append(chunk["data"])

            audio_bytes = b"".join(chunks)
            return Response(audio_bytes, media_type="audio/mpeg")

        return Response(b"", status_code=501)
    except Exception as e:
        logger.error(f"TTS endpoint error: {e}")
        return Response(b"", status_code=500)


class AgentWebSocketHandler:
    """Manages WebSocket communication between the browser UI and JarvisAgent."""

    def __init__(self):
        self.settings = get_settings()
        self.active_websocket: Optional[WebSocket] = None
        self.lock = asyncio.Lock()

    async def handle_ws(self, websocket: WebSocket):
        await websocket.accept()
        loop = asyncio.get_running_loop()

        # Enforce single active client to prevent duplicate audio
        async with self.lock:
            if self.active_websocket is not None and self.active_websocket != websocket:
                logger.info("Superseding previous WebSocket client.")
                try:
                    await self.active_websocket.close(code=1000, reason="Superseded by new client")
                except Exception:
                    pass
            self.active_websocket = websocket

        # Callbacks that push events over WebSocket
        def on_tool_start(tool_name: str, args: dict):
            try:
                future = asyncio.run_coroutine_threadsafe(
                    websocket.send_text(json.dumps({
                        "type": "tool_start",
                        "tool_name": tool_name,
                        "args": args,
                    }, default=str)),
                    loop,
                )
                future.result(timeout=5)
            except Exception:
                pass

        def on_pre_execution(screen_summary: str, action_desc: str):
            try:
                future = asyncio.run_coroutine_threadsafe(
                    websocket.send_text(json.dumps({
                        "type": "pre_execution",
                        "screen_summary": screen_summary,
                        "action_desc": action_desc,
                    }, default=str)),
                    loop,
                )
                future.result(timeout=5)
            except Exception:
                pass

        def on_tool_end(tool_name: str, result: any):
            try:
                is_obstacle = False
                obstacle_msg = ""
                if isinstance(result, dict) and result.get("status") in ["failed", "error", "security_blocked"]:
                    is_obstacle = True
                    obstacle_msg = result.get('message') or result.get('stderr') or 'কাজে বাধা সনাক্ত হয়েছে'

                future = asyncio.run_coroutine_threadsafe(
                    websocket.send_text(json.dumps({
                        "type": "tool_end",
                        "tool_name": tool_name,
                        "result": result,
                        "is_obstacle": is_obstacle,
                        "obstacle_msg": obstacle_msg,
                    }, default=str)),
                    loop,
                )
                future.result(timeout=5)
            except Exception:
                pass

        # Create session agent using JarvisAgent from jarvis-core
        agent = JarvisAgent(
            on_tool_start=on_tool_start,
            on_tool_end=on_tool_end,
            on_pre_execution=on_pre_execution,
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

                    # Instant response for wake word / greeting
                    normalized = user_text.strip().lower()
                    wake_words = [
                        "জার্ভিস", "জারভিস", "jarvis", "hey jarvis", "hi jarvis", "hello jarvis",
                        "শুনছেন", "শুনছো", "হ্যালো", "হাই", "hello", "hi"
                    ]
                    if normalized in wake_words:
                        await websocket.send_text(json.dumps({
                            "type": "response",
                            "text": "হ্যালো স্যার, বলুন কী করব?",
                        }))
                        continue

                    try:
                        # Send verbal acknowledgment when analysis/processing takes time:
                        # "ok ami dekhteci ami ektu somoy dew ETA SUDU MATRO jokhon answer dite somoy lagbe tokhon eta use korbe"
                        await websocket.send_text(json.dumps({
                            "type": "ack",
                            "text": "ঠিক আছে স্যার, আমি দেখছি, আমাকে একটু সময় দিন...",
                        }))

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


async def telemetry_endpoint(request):
    """Serve real-time system hardware telemetry for the J.A.R.V.I.S. HUD."""
    import psutil
    cpu_pct = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    net = psutil.net_io_counters()

    temps = {"cpu": 42.4, "gpu": 39.2, "disk": 41.5}
    try:
        t = psutil.sensors_temperatures()
        if t:
            for k, entries in t.items():
                if entries:
                    if "coretemp" in k.lower() or "cpu" in k.lower() or "k10temp" in k.lower():
                        temps["cpu"] = round(entries[0].current, 1)
                    elif "gpu" in k.lower() or "amdgpu" in k.lower() or "nvme" in k.lower():
                        temps["gpu"] = round(entries[0].current, 1)
    except Exception:
        pass

    data = {
        "cpu_pct": cpu_pct,
        "ram_pct": mem.percent,
        "ram_used_gb": round(mem.used / (1024**3), 1),
        "ram_total_gb": round(mem.total / (1024**3), 1),
        "ram_free_gb": round(mem.available / (1024**3), 1),
        "disk_pct": disk.percent,
        "disk_used_gb": round(disk.used / (1024**3), 1),
        "disk_total_gb": round(disk.total / (1024**3), 1),
        "net_bytes_sent": net.bytes_sent,
        "net_bytes_recv": net.bytes_recv,
        "procs_count": len(psutil.pids()),
        "temperatures": temps,
    }
    return Response(json.dumps(data), media_type="application/json")


handler = AgentWebSocketHandler()

_http_agent = None

async def chat_http_endpoint(request):
    """Handle chat requests via HTTP POST as fail-safe fallback."""
    global _http_agent
    try:
        data = await request.json()
        user_text = data.get("text", "").strip()
        if not user_text:
            return Response(json.dumps({"error": "Empty prompt"}), status_code=400, media_type="application/json")

        normalized = user_text.strip().lower()
        wake_words = [
            "জার্ভিস", "জারভিস", "jarvis", "hey jarvis", "hi jarvis", "hello jarvis",
            "শুনছেন", "শুনছো", "হ্যালো", "হাই", "hello", "hi"
        ]
        if normalized in wake_words:
            return Response(json.dumps({"response": "হ্যালো স্যার, বলুন কী করব?"}), media_type="application/json")

        if _http_agent is None:
            _http_agent = JarvisAgent()
        response = await asyncio.to_thread(_http_agent.chat, user_text)
        return Response(json.dumps({"response": response}), media_type="application/json")
    except Exception as e:
        logger.error(f"HTTP chat error: {e}")
        return Response(json.dumps({"error": str(e)}), status_code=500, media_type="application/json")


routes = [
    Route("/", homepage),
    Route("/icon.png", icon_endpoint),
    Route("/tts", tts_endpoint, methods=["POST"]),
    Route("/api/telemetry", telemetry_endpoint),
    Route("/api/chat", chat_http_endpoint, methods=["POST"]),
    WebSocketRoute("/ws", handler.handle_ws),
]

app = Starlette(routes=routes)


def find_browser_app_binary() -> Optional[str]:
    """Find installed Chrome/Chromium binary capable of standalone desktop app mode."""
    candidates = [
        "/usr/bin/google-chrome-stable",
        "/usr/bin/google-chrome",
        "/opt/google/chrome/google-chrome",
        "/opt/google/chrome/chrome",
        shutil.which("google-chrome-stable"),
        shutil.which("google-chrome"),
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
    """Launch J.A.R.V.I.S. as a dedicated standalone Desktop Application Window without browser tabs or address bar."""
    binary = find_browser_app_binary()
    if binary:
        profile_dir = PROJECT_ROOT / ".jarvis_app_profile"
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
            "--class=JARVIS_Desktop",
            "--name=JARVIS",
            "--window-size=1600,960",
            "--window-position=center",
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

    # Fallback to Firefox in new window if chrome app-mode binary is not found
    firefox = shutil.which("firefox")
    if firefox:
        try:
            subprocess.Popen(
                [firefox, "--new-window", url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return
        except Exception:
            pass

    # Fallback to default browser
    webbrowser.open(url)


def free_port_if_in_use(port: int = 8765):
    """Gracefully terminate any lingering instances bound to the port to avoid Errno 98."""
    current_pid = os.getpid()
    try:
        import psutil
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                for conn in proc.connections(kind='inet'):
                    if conn.laddr.port == port:
                        if proc.pid != current_pid:
                            logger.info(f"Closing lingering process on port {port} (PID: {proc.pid})")
                            proc.terminate()
                            try:
                                proc.wait(timeout=2)
                            except Exception:
                                proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
    except Exception:
        pass

    # Secondary fallback with fuser if available
    try:
        subprocess.run(["fuser", "-k", f"{port}/tcp"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
    except Exception:
        pass


def run_web_ui(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True):
    """Start local web backend and launch standalone desktop application window."""
    free_port_if_in_use(port)
    url = f"http://{host}:{port}"
    print(f"\n✨ Starting J.A.R.V.I.S. Desktop App at {url}")

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
