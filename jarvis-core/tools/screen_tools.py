"""Screen vision and desktop capture tools for JARVIS using native spectacle and Gemini Vision."""
import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional

from PIL import Image
from config.settings import get_settings

logger = logging.getLogger(__name__)


def capture_desktop_screen(
    output_path: Optional[str] = None,
    delay_ms: int = 0,
) -> Dict[str, Any]:
    """Capture a screenshot of the entire desktop monitor screen.

    Args:
        output_path: Optional file path to save the screenshot. If None, saves to a temporary PNG file.
        delay_ms: Milliseconds delay before capturing.
    """
    if not output_path:
        temp_dir = Path(tempfile.gettempdir()) / "jarvis_screens"
        temp_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(temp_dir / f"screen_{int(time.time() * 1000)}.png")

    try:
        # 1. Try spectacle on KDE Plasma / Wayland
        cmd = ["spectacle", "-b", "-n", "-f", "-o", output_path]
        if delay_ms > 0:
            cmd.extend(["-d", str(delay_ms)])

        res = subprocess.run(cmd, capture_output=True, timeout=5)
        if res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            with Image.open(output_path) as img:
                w, h = img.size
            return {
                "status": "success",
                "file_path": output_path,
                "width": w,
                "height": h,
                "message": f"স্ক্রিনশট সফলভাবে গ্রহণ করা হয়েছে ({w}x{h})।",
            }
    except Exception as e:
        logger.warning(f"Spectacle screenshot failed: {e}")

    # Fallback to PyAutoGUI / PIL if spectacle fails
    try:
        import sys
        sys.modules["mouseinfo"] = None
        import pyautogui
        shot = pyautogui.screenshot()
        shot.save(output_path)
        w, h = shot.size
        return {
            "status": "success",
            "file_path": output_path,
            "width": w,
            "height": h,
            "message": f"স্ক্রিনশট সফলভাবে গ্রহণ করা হয়েছে ({w}x{h})।",
        }
    except Exception as e2:
        logger.error(f"Fallback screenshot failed: {e2}")
        return {"status": "error", "message": f"স্ক্রিন ক্যাপচার ব্যর্থ হয়েছে: {str(e2)}"}


def analyze_screen_content(
    query: str = "মনিটরে বর্তমানে কী কী অ্যাপ্লিকেশন, উইন্ডো বা কনটেন্ট দৃশ্যমান এবং এর অবস্থা কী?",
) -> Dict[str, Any]:
    """Take a screenshot of the monitor and analyze its visual content using Gemini Vision.

    Args:
        query: Specific question or inspection goal about what is on the screen.
    """
    settings = get_settings()
    api_key = settings.gemini_api_key
    if not api_key:
        return {"status": "error", "message": "GEMINI_API_KEY কনফিগার করা নেই।"}

    shot_result = capture_desktop_screen()
    if shot_result.get("status") != "success":
        return shot_result

    img_path = shot_result["file_path"]

    try:
        from google import genai
        client = genai.Client(api_key=api_key)

        with Image.open(img_path) as img:
            # Resize image to reasonable bounds for fast high-accuracy analysis
            img_copy = img.copy()
            img_copy.thumbnail((1600, 1000))

            prompt = (
                f"You are JARVIS's visual eye inspecting the user's computer monitor screen.\n"
                f"User Question / Goal: {query}\n"
                f"Analyze the screenshot precisely. Report:\n"
                f"1. Active/focused windows and open applications.\n"
                f"2. Current UI state, dialogs, buttons, search bars, or chat conversations visible.\n"
                f"3. Any errors, notifications, or blockers visible on the screen.\n"
                f"Provide your answer in clear, polite Bengali ('স্যার' and 'আপনি' tone) directly addressing the user's inspection goal."
            )

            # Use fallback candidate models if default encounters limit
            candidate_models = [settings.default_model] + [
                m for m in settings.fallback_models if m != settings.default_model
            ]
            last_err = None
            for model_name in candidate_models:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=[prompt, img_copy],
                    )
                    analysis_text = response.text if response.text else "স্ক্রিন বিশ্লেষণ সম্পন্ন হয়েছে।"
                    return {
                        "status": "success",
                        "query": query,
                        "screenshot_path": img_path,
                        "visual_analysis": analysis_text,
                    }
                except Exception as m_err:
                    last_err = m_err
                    continue

            if last_err:
                raise last_err

        return {"status": "error", "message": "কোনো মডেল থেকে রেসপন্স পাওয়া যায়নি।"}
    except Exception as e:
        logger.error(f"Error analyzing screen content with Gemini Vision: {e}")
        return {"status": "error", "message": f"স্ক্রিন বিশ্লেষণে সমস্যা হয়েছে: {str(e)}"}


_last_screen_cache = {"timestamp": 0.0, "path": "", "summary": ""}


def inspect_full_screen_state(force_refresh: bool = False) -> Dict[str, Any]:
    """Capture and read the user's full monitor screen, returning a concise summary of current visible state.

    Used automatically before executing workstation actions.
    """
    now = time.time()
    # Cache recent screen read within 2.5 seconds to avoid redundant API hits during rapid actions
    if not force_refresh and (now - _last_screen_cache["timestamp"] < 2.5) and _last_screen_cache["summary"]:
        return {
            "status": "success",
            "cached": True,
            "screenshot_path": _last_screen_cache["path"],
            "summary": _last_screen_cache["summary"],
        }

    settings = get_settings()
    api_key = settings.gemini_api_key
    if not api_key:
        return {"status": "error", "summary": "স্ক্রিন দেখা সম্ভব হয়নি (API key অনুপস্থিত)।"}

    shot_res = capture_desktop_screen()
    if shot_res.get("status") != "success":
        return {"status": "error", "summary": "স্ক্রিন ক্যাপচার সম্পন্ন করা যায়নি।"}

    img_path = shot_res["file_path"]

    try:
        from google import genai
        client = genai.Client(api_key=api_key)

        with Image.open(img_path) as img:
            img_copy = img.copy()
            img_copy.thumbnail((1280, 720))

            prompt = (
                "You are JARVIS inspecting the user's computer monitor screen before executing an action.\n"
                "In 1 or 2 concise, polite Bengali sentences, state what application(s) and window(s) are currently "
                "open and active on the screen (e.g., 'বর্তমানে স্ক্রিনে ভিজ্যুয়াল স্টুডিও কোড এবং টার্মিনাল কনসোল খোলা রয়েছে।'). "
                "Do not use bullet points or markdown headings. Keep it short and natural for vocal reading."
            )

            candidate_models = [settings.default_model] + [
                m for m in settings.fallback_models if m != settings.default_model
            ]
            summary_text = ""
            for model_name in candidate_models:
                try:
                    res = client.models.generate_content(
                        model=model_name,
                        contents=[prompt, img_copy],
                    )
                    if res.text:
                        summary_text = res.text.strip()
                        break
                except Exception:
                    continue

            if not summary_text:
                summary_text = "মনিটরে বর্তমান অ্যাপ্লিকেশন এবং ডেস্কটপ দৃশ্যমান রয়েছে।"

            _last_screen_cache["timestamp"] = now
            _last_screen_cache["path"] = img_path
            _last_screen_cache["summary"] = summary_text

            return {
                "status": "success",
                "cached": False,
                "screenshot_path": img_path,
                "summary": summary_text,
            }

    except Exception as e:
        logger.error(f"Error inspecting full screen state: {e}")
        return {
            "status": "error",
            "summary": "ডেস্কটপ উইন্ডো ও অ্যাপ দৃশ্যমান রয়েছে।",
        }

