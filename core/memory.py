"""Persistent Long-term Memory and Time Context Engine for monaAi."""
import datetime
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MEMORY_FILE = DATA_DIR / "memory.json"

BENGALI_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
BENGALI_DAYS = {
    "Monday": "সোমবার",
    "Tuesday": "মঙ্গলবার",
    "Wednesday": "বুধবার",
    "Thursday": "বৃহস্পতিবার",
    "Friday": "শুক্রবার",
    "Saturday": "শনিবার",
    "Sunday": "রবিবার",
}
BENGALI_MONTHS = {
    1: "জানুয়ারি",
    2: "ফেব্রুয়ারি",
    3: "মার্চ",
    4: "এপ্রিল",
    5: "মে",
    6: "জুন",
    7: "জুলাই",
    8: "আগস্ট",
    9: "সেপ্টেম্বর",
    10: "অক্টোবর",
    11: "নভেম্বর",
    12: "ডিসেম্বর",
}


def to_bengali_digits(number: int | str) -> str:
    """Convert western digits to Bengali digits."""
    return str(number).translate(BENGALI_DIGITS)


def get_bengali_time_context(dt: Optional[datetime.datetime] = None) -> Dict[str, str]:
    """Get rich Bengali localized time, date, period of day, and formatted string."""
    now = dt or datetime.datetime.now()
    hour = now.hour
    minute = now.minute

    # Period of the day in Bengali
    if 4 <= hour < 6:
        period = "ভোর"
    elif 6 <= hour < 12:
        period = "সকাল"
    elif 12 <= hour < 15:
        period = "দুপুর"
    elif 15 <= hour < 18:
        period = "বিকাল"
    elif 18 <= hour < 20:
        period = "সন্ধ্যা"
    else:
        period = "রাত"

    # 12-hour format display
    display_hour = hour % 12
    if display_hour == 0:
        display_hour = 12

    hour_bn = to_bengali_digits(display_hour)
    minute_bn = to_bengali_digits(f"{minute:02d}")
    day_bn = BENGALI_DAYS.get(now.strftime("%A"), now.strftime("%A"))
    month_bn = BENGALI_MONTHS.get(now.month, str(now.month))
    date_bn = to_bengali_digits(now.day)
    year_bn = to_bengali_digits(now.year)

    time_str = f"{period} {hour_bn}:{minute_bn}"
    full_str = f"{day_bn}, {date_bn} {month_bn} {year_bn}, {time_str}"

    return {
        "iso": now.isoformat(),
        "period": period,
        "time": time_str,
        "day": day_bn,
        "date": f"{date_bn} {month_bn} {year_bn}",
        "full": full_str,
    }


class MemoryManager:
    """Manages persistent conversational memory, user facts, and contextual recall."""

    def __init__(self, memory_file: Optional[Path] = None):
        self.memory_file = memory_file or MEMORY_FILE
        self._ensure_storage()
        self._data = self._load()

    def _ensure_storage(self):
        """Ensure storage directory and initial file exist."""
        self.memory_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.memory_file.exists():
            default_data = {
                "user_facts": [],
                "history": [],
                "summary": "",
            }
            self._save_raw(default_data)

    def _load(self) -> Dict[str, Any]:
        """Load memory from disk safely."""
        try:
            with open(self.memory_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    data = {}
                data.setdefault("user_facts", [])
                data.setdefault("history", [])
                data.setdefault("summary", "")
                return data
        except Exception as e:
            logger.warning(f"Failed to load memory file, initializing fresh: {e}")
            return {"user_facts": [], "history": [], "summary": ""}

    def _save_raw(self, data: Dict[str, Any]):
        """Persist data to disk safely."""
        try:
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving memory file: {e}")

    def save(self):
        """Save in-memory state to disk."""
        self._save_raw(self._data)

    def save_turn(self, role: str, text: str):
        """Record a conversation turn with timestamp.
        
        Args:
            role: 'user' or 'model'
            text: Message text
        """
        now_ctx = get_bengali_time_context()
        turn = {
            "role": "user" if role == "user" else "model",
            "text": text.strip(),
            "timestamp": now_ctx["iso"],
            "time_bn": now_ctx["full"],
        }
        self._data["history"].append(turn)
        # Keep last 100 turns in persistent history to avoid unbounded file growth
        if len(self._data["history"]) > 100:
            self._data["history"] = self._data["history"][-100:]
        self.save()

    def add_fact(self, fact: str) -> bool:
        """Store a permanent fact about the user or preferences."""
        fact = fact.strip()
        if fact and fact not in self._data["user_facts"]:
            self._data["user_facts"].append(fact)
            self.save()
            return True
        return False

    def get_facts(self) -> List[str]:
        """Get all stored facts about the user."""
        return list(self._data.get("user_facts", []))

    def get_history_for_gemini(self, max_turns: int = 16) -> List[Dict[str, Any]]:
        """Format recent history into Gemini SDK chat history format."""
        history = self._data.get("history", [])
        recent = history[-max_turns:] if len(history) > max_turns else history
        gemini_history = []
        for h in recent:
            role = "user" if h.get("role") == "user" else "model"
            text = h.get("text", "")
            if text:
                gemini_history.append({
                    "role": role,
                    "parts": [{"text": text}],
                })
        return gemini_history

    def get_context_prompt_injection(self) -> str:
        """Build dynamic context block to inject into the system prompt."""
        time_info = get_bengali_time_context()
        facts = self.get_facts()

        lines = [
            f"- **বর্তমান সময় ও তারিখ (Time Awareness)**: {time_info['full']}",
            f"- **সময়ের পর্ব**: {time_info['period']}বেলা। ইউজার সময় বা তারিখ জিজ্ঞেস করলে এই তথ্য অনুযায়ী নিখুঁত উত্তর দেবে।",
            "- **পূর্ববর্তী কথোপকথন ও স্মৃতি (Memory & Continuity)**: ইউজারের সাথে তোমার আগের কথোপকথনের ইতিহাস তোমার মনে আছে। আগের কথার প্রাসঙ্গিকতা বজায় রেখে মিষ্টি সুরে উত্তর দেবে।",
        ]

        if facts:
            lines.append("- **ইউজারের সম্পর্কে তোমার মনে রাখা তথ্যগুলো (Remembered Facts)**:")
            for fact in facts:
                lines.append(f"  • {fact}")

        return "\n".join(lines)

    def clear_history(self):
        """Clear chat history while preserving learned facts."""
        self._data["history"] = []
        self.save()

    def clear_all(self):
        """Clear all memory completely."""
        self._data = {"user_facts": [], "history": [], "summary": ""}
        self.save()


# Global default instance
_global_memory: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """Get or create singleton MemoryManager."""
    global _global_memory
    if _global_memory is None:
        _global_memory = MemoryManager()
    return _global_memory


# -------------------------------------------------------------------------
# Tool Functions for Gemini Agent to call autonomously
# -------------------------------------------------------------------------

def remember_fact(fact: str) -> Dict[str, Any]:
    """Use this tool when the user asks you to remember something important (e.g. name, work, meeting, preference, birthday).

    Args:
        fact: The specific information or fact to remember for future conversations.
    """
    manager = get_memory_manager()
    added = manager.add_fact(fact)
    return {
        "status": "success",
        "fact_saved": fact,
        "message": "তথ্যটি সফলভাবে স্থায়ী মেমোরিতে সংরক্ষণ করা হয়েছে।" if added else "তথ্যটি আগেই মেমোরিতে ছিল।",
    }


def get_current_time() -> Dict[str, Any]:
    """Use this tool when the user asks what time it is, what date today is, or what day of the week it is."""
    ctx = get_bengali_time_context()
    return {
        "status": "success",
        "time_bengali": ctx["full"],
        "period": ctx["period"],
        "date": ctx["date"],
        "day": ctx["day"],
    }
