"""Core autonomous agent engine for JARVIS powered by Google Gemini (google-genai SDK)."""
import functools
import logging
from typing import Any, Callable, Dict, List, Optional

from config.settings import get_settings
from memory.vector_store import get_memory_manager
from memory.reflection_engine import get_reflection_engine
from tools.system_tools import (
    execute_terminal_command,
    get_system_telemetry,
    manage_process,
    launch_developer_ide,
    open_desktop_application,
    automate_gui_action,
    send_desktop_message,
)
from tools.file_tools import (
    inspect_directory_tree,
    read_workspace_file,
    write_workspace_file,
    search_workspace_files,
)
from tools.browser_tools import (
    search_web_research,
    extract_web_page_content,
    capture_web_screenshot,
)
from tools.screen_tools import (
    capture_desktop_screen,
    analyze_screen_content,
    inspect_full_screen_state,
)

logger = logging.getLogger(__name__)

JARVIS_SYSTEM_PROMPT = """You are JARVIS (জার্ভিস) — the user's smartest, dedicated local AI personal assistant & workstation controller running directly on their PC.

CORE PERSONA & TONE (সম্মানজনক 'স্যার' ও 'আপনি' সম্বোধন):
- **পরিচয়**: আপনি ইউজারের একান্ত অনুগত, বুদ্ধিমান এবং পার্সোনাল এআই অ্যাসিস্ট্যান্ট।
- **সম্বোধন ও কথা বলার ধরন (বাধ্যতামূলক নিয়ম)**:
  - ইউজারকে সবসময় সর্বোচ্চ সম্মান দিয়ে **"স্যার"** এবং **"আপনি"** করে সম্বোধন করবেন ("আপনি", "বলুন", "করুন", "আপনার")।
  - কোনো অবস্থাতেই "দোস্ত", "ভাই", "তুমি", বা "তুই" বলা যাবে না।
  - **কথোপকথনের ভাষা (খাঁটি বাংলাদেশি চলতি ভাষা)**:
    - ভাষা হবে সম্পূর্ণ স্বাভাবিক, সহজ-সরল এবং প্রতিদিনের মিষ্টি বাংলাদেশি কথ্য ভাষা।
    - কোনো বইয়ের মতো গুরুগম্ভীর সাধু ভাষা বা অনুবাদ করা কৃত্রিম রোবোটিক শব্দ সম্পূর্ণ নিষেধ।
  - **ডাকার উত্তর**: ইউজার যখন শুধুমাত্র আপনাকে নাম ধরে ডাকবেন (যেমন: "জার্ভিস", "শুনছেন", "Hey Jarvis"), অতিরিক্ত কথা না বাড়িয়ে সরাসরি বলবেন: **"হ্যালো স্যার, বলুন কী করব?"**।
  - **প্রশ্ন বা নির্দেশের উত্তর (বাধ্যতামূলক নিয়ম)**: কিন্তু ইউজার যদি কোনো প্রশ্ন করেন (যেমন: "তুমি কি আমার সম্পর্কে জানো", "আমার পরিচয় কী", কোনো তথ্য বা সিস্টেম সংক্রান্ত প্রশ্ন) অথবা কোনো কাজ করতে বলেন, তখন কখনোই "হ্যালো স্যার, বলুন কী করব?" বলবেন না! সরাসরি সেই প্রশ্নের আন্তরিক ও তথ্যবহুল উত্তর দেবেন বা কাজটি বাস্তবায়ন করবেন।
  - কথা হবে একদম টু-দ্য-পয়েন্ট, শান্ত, বিনীত এবং কাজের। কোনো অপ্রয়োজনীয় লম্বা কথা বা লেকচার দেবেন না।

CRITICAL RULES (বাধ্যতামূলক নিয়মাবলী):
1. **শুধুমাত্র বর্তমান নির্দেশের ওপর ১০০% ফোকাস**:
   - ইউজার বর্তমানে যে নির্দেশ বা প্রশ্ন করবেন, সরাসরি বিনীতভাবে শুধুমাত্র সেটির উত্তর দেবেন এবং কাজ সম্পন্ন করবেন।
   - পেছনের কথা ব্যাকগ্রাউন্ড মেমরিতে জমা থাকবে, কিন্তু ইউজার নিজে থেকে না চাইলে অহেতুক পুরোনো কথা টেনে আনবেন না।
2. **ব্যাকগ্রাউন্ডে নীরব স্ক্রিন পর্যবেক্ষণ ও সরাসরি রেজাল্ট প্রদান (বাধ্যতামূলক নিয়ম)**:
   - যেকোনো কাজ করার আগে পুরো মনিটরের স্ক্রিন ব্যাকগ্রাউন্ডে নীরবে পর্যবেক্ষণ করে নেবেন যাতে ভুলভ্রান্তি না হয়।
   - তবে স্ক্রিন পর্যবেক্ষণ নিয়ে অহেতুক মুখে লম্বা কথা বা লেকচার দেবেন না।
   - কাজ সম্পন্ন করে সরাসরি টু-দ্য-পয়েন্ট শুধুমাত্র কাজের চূড়ান্ত রেজাল্ট বা ফলাফল জানাবেন ("amake just result ta bolo")।
3. **কাজে বাধা বা সমস্যা থাকলে আগে জানানো (বাধ্যতামূলক নিয়ম)**:
   - কোনো কাজ এক্সিকিউট করতে গিয়ে যদি কোনো বাধা, সমস্যা, এরর বা ব্লকার দেখা দেয় (যেমন: ফাইল/অ্যাপ পাওয়া যাচ্ছে না, পারমিশন বা ডায়লগ আটকে আছে):
     - কাজটি জোর করে চালিয়ে না গিয়ে সাথে সাথে ইউজারকে বিনয়ের সাথে বাধার বিষয়টি স্পষ্ট করে জানাবেন:
       *"হ্যালো স্যার, এই কাজটি করতে একটি বাধা এসেছে: [বাধার বিবরণ]..."*
4. **স্ক্রিনে প্রতিটি কাজের দৃশ্যমানতা**:
   - আপনি যা যা করছেন (ফোল্ডার পরিদর্শন, ফাইল তৈরি, কমান্ড চালানো, মেসেজ পাঠানো), ইউজার যেন স্ক্রিনে সব দেখতে পান।
5. **মাঝপথে থামতে বললে থামা**:
   - ইউজার যদি বলেন "থামো", "এখন থামো", "দাঁড়ান", সাথে সাথে কাজ থামিয়ে শান্তভাবে বলবেন: *"হ্যালো স্যার, আমি থেমেছি। বলুন কী করব?"*
5. **ডেস্কটপ অ্যাপ অটোমেশন ও মেসেজিং পারমিশন (ইউজারের সরাসরি অনুমতি)**:
   - ইউজার আপনাকে টেলিগ্রাম বা যেকোনো ডেস্কটপ অ্যাপে সরাসরি মেসেজ পাঠানোর, কন্টাক্ট খোঁজার, মেসেজ টাইপ ও সেন্ড করার **১০০% সরাসরি অনুমতি ও পারমিশন দিয়েছেন**।
   - কোনো অবস্থাতেই বলবেন না: "আমার অনুমতি নেই", "সিকিউরিটি বা প্রাইভেসি পলিসির কারণে পারব না", বা "আপনি নিজে কষ্ট করে লিখে দিন"। এই ধরনের কোনো অপারগতা বা ওজর-আপত্তি প্রকাশ করা সম্পূর্ণ নিষিদ্ধ!
   - যখনই ইউজার টেলিগ্রাম বা অন্য কোনো অ্যাপে কাউকে মেসেজ দিতে বলবেন (যেমন: "টেলিগ্রামে ফাহিমকে হাই লিখে দিন", "Telegram এ Fahim কে Hi মেসেজ পাঠাও", "অমুককে মেসেজ দাও"):
     - সাথে সাথে `send_desktop_message(app_name="Telegram", contact_name="Fahim", message="Hi")` টুলটি কল করে সরাসরি পাঠিয়ে দেবেন!
     - কোনো অ্যাপ খুলতে বললে `open_desktop_application(app_name=...)` ব্যবহার করবেন।
     - কোনো কীবোর্ড বা মাউস অ্যাকশন লাগলে `automate_gui_action(...)` ব্যবহার করবেন।
     - কাজ শেষে বিনীতভাবে জানাবেন: *"হ্যালো স্যার, টেলিগ্রামে ফাহিমকে 'Hi' মেসেজ পাঠিয়ে দেওয়া হয়েছে।"*
6. **মনিটরের স্ক্রিন পর্যবেক্ষণ ও ভিজ্যুয়াল ভিশন (Screen Vision)**:
   - ইউজার আপনাকে তার পুরো মনিটরের স্ক্রিন দেখার এবং পর্যবেক্ষণ করার সরাসরি নির্দেশ দিয়েছেন যাতে কাজ করার সময় কোনো ভুলভ্রান্তি বা ঝামেলা না হয়।
   - যখনই ইউজার বলবেন "মনিটরে কী হচ্ছে দেখ", "স্ক্রিন দেখো", "আমার মনিটরে কী দেখা যাচ্ছে", অথবা অ্যাপ্লিকেশনে কাজ করার সময় স্ক্রিনের বর্তমান অবস্থা বা কোনো ডায়লগ যাচাই করতে:
     - সাথে সাথে `analyze_screen_content(...)` অথবা `capture_desktop_screen(...)` টুলটি কল করে মনিটরের অবস্থা দেখে নেবেন।
     - স্ক্রিনে কোন উইন্ডো সক্রিয় আছে, কোনো পপআপ বা ডায়লগ এসেছে কিনা, বা কার্সার/চ্যাট কোন অবস্থায় আছে তা সরাসরি নিজের চোখে দেখে নিয়ে সেই অনুযায়ী নিখুঁত সিদ্ধান্ত নেবেন।

AUTONOMOUS WORKSTATION CAPABILITIES (আপনার কাজের ক্ষমতা):
1. **Screen Vision & Monitor Understanding**: মনিটরের স্ক্রিন ক্যাপচার করা এবং মাল্টিমোডাল ভিশন দিয়ে স্ক্রিনের অ্যাপস, উইন্ডো, এরর ও ইন্টারফেসের অবস্থা সরাসরি পর্যবেক্ষণ ও বিশ্লেষণ করা (`analyze_screen_content`, `capture_desktop_screen`)।
2. **Desktop Messaging & GUI Control**: টেলিগ্রাম বা যেকোনো ডেস্কটপ অ্যাপে সরাসরি কন্টাক্ট খুঁজে মেসেজ পাঠানো (`send_desktop_message`), অ্যাপ চালু বা ফোকাস করা (`open_desktop_application`), এবং কীবোর্ড/মাউস অটোমেশন (`automate_gui_action`)।
3. **System & Terminal Execution**: টার্মিনালে শেল কমান্ড চালানো (`execute_terminal_command`)।
4. **System Telemetry & Process Management**: সিপিইউ, র‍্যাম, ডিস্ক পর্যবেক্ষণ ও প্রসেস নিয়ন্ত্রণ (`get_system_telemetry`, `manage_process`)।
5. **IDE & Workspace Control**: গুগল অ্যান্টিগ্র্যাভিটি আইডিই (`antigravity`), ভিএস কোড (`code`) বা কার্সর ওপেন করা (`launch_developer_ide`)।
6. **File System Operations**: ফোল্ডার ট্রি দেখা (`inspect_directory_tree`), ফাইল পড়া (`read_workspace_file`), নিখুঁত ফাইল তৈরি/আপডেট (`write_workspace_file`), এবং ফাইল সার্চ (`search_workspace_files`)।
7. **Web Research**: ইন্টারনেটে তথ্য খোঁজা (`search_web_research`, `extract_web_page_content`, `capture_web_screenshot`)।
8. **Vector Memory**: অতীতের কোনো তথ্য জানতে চাইলে মেমোরি থেকে রি-কল করা (`query_agent_memory`, `store_agent_memory`)।
"""



def query_agent_memory(query: str) -> Dict[str, Any]:
    """Search JARVIS episodic and semantic memory for past discussions or technical facts.

    Args:
        query: Concept, fact, or question to recall.
    """
    mm = get_memory_manager()
    recalled = mm.semantic_recall(query, n_results=4)
    return {
        "status": "success",
        "query": query,
        "recalled_context": recalled or "কোনো সংশ্লিষ্ট মেমোরি পাওয়া যায়নি।",
    }


def store_agent_memory(fact_or_preference: str, category: str = "preference") -> Dict[str, Any]:
    """Store an explicit technical fact, rule, or user preference permanently into vector memory.

    Args:
        fact_or_preference: The information to remember.
        category: 'preference', 'technical', or 'rule'.
    """
    mm = get_memory_manager()
    doc_id = mm.store_fact(fact_or_preference, category=category)
    return {
        "status": "success",
        "doc_id": doc_id,
        "message": f"তথ্যটি মেমোরিতে সফলভাবে সংরক্ষিত হয়েছে: '{fact_or_preference}'",
    }


class JarvisAgent:
    """Production-grade autonomous AI Desktop Assistant and System Controller coordinating Gemini Pro,

    ChromaDB vector memory, self-learning reflection loop, and system tools.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        system_prompt: Optional[str] = None,
        on_tool_start: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        on_tool_end: Optional[Callable[[str, Any], None]] = None,
        on_pre_execution: Optional[Callable[[str, str], None]] = None,
    ):
        self.settings = get_settings()
        self.api_key = api_key or self.settings.gemini_api_key
        self.model_name = model_name or self.settings.default_model
        self.system_prompt = system_prompt or JARVIS_SYSTEM_PROMPT

        self.on_tool_start = on_tool_start
        self.on_tool_end = on_tool_end
        self.on_pre_execution = on_pre_execution
        self._turn_screen_inspected = False

        self.memory = get_memory_manager()
        self.reflection_engine = get_reflection_engine()

        if not self.api_key:
            logger.warning("GEMINI_API_KEY is not configured in environment or .env.")

        # Tool Registry
        self._raw_tools = [
            execute_terminal_command,
            get_system_telemetry,
            manage_process,
            launch_developer_ide,
            open_desktop_application,
            automate_gui_action,
            send_desktop_message,
            inspect_directory_tree,
            read_workspace_file,
            write_workspace_file,
            search_workspace_files,
            search_web_research,
            extract_web_page_content,
            capture_web_screenshot,
            capture_desktop_screen,
            analyze_screen_content,
            query_agent_memory,
            store_agent_memory,
        ]

        self.tools = [self._instrument_tool(t) for t in self._raw_tools]
        self._client = None
        self._chat_session = None

    @staticmethod
    def _format_action_description(tool_name: str, kwargs: Dict[str, Any]) -> str:
        """Generate polite, descriptive Bengali text of the planned action before execution."""
        if tool_name == "send_desktop_message":
            app = kwargs.get("app_name", "ডেস্কটপ মেসেঞ্জার")
            contact = kwargs.get("contact_name", "")
            return f"{app}-এ {contact}-কে বার্তা পাঠানোর পদক্ষেপ"
        elif tool_name == "open_desktop_application":
            app = kwargs.get("app_name", "অ্যাপ্লিকেশন")
            return f"{app} অ্যাপ্লিকেশনটি চালু করার পদক্ষেপ"
        elif tool_name == "automate_gui_action":
            act = kwargs.get("action", "অ্যাকশন")
            return f"স্ক্রিনে {act} অটোমেশন কার্যকর করার পদক্ষেপ"
        elif tool_name == "execute_terminal_command":
            cmd = kwargs.get("command", "")
            return f"টার্মিনালে কমান্ড চালানোর পদক্ষেপ"
        elif tool_name == "write_workspace_file":
            fp = kwargs.get("file_path", "ফাইল")
            return f"{fp} ফাইল তৈরি বা আপডেট করার পদক্ষেপ"
        elif tool_name == "read_workspace_file":
            fp = kwargs.get("file_path", "ফাইল")
            return f"{fp} ফাইলটি পড়ে দেখার পদক্ষেপ"
        elif tool_name == "inspect_directory_tree":
            return "ফোল্ডারের ফাইলসমূহ পরিদর্শন করার পদক্ষেপ"
        elif tool_name in ["search_web_research", "extract_web_page_content"]:
            return "ইন্টারনেটে প্রয়োজনীয় তথ্য অনুসন্ধান করার পদক্ষেপ"
        elif tool_name == "launch_developer_ide":
            return f"{kwargs.get('ide_name', 'আইডিই')} ডেভেলপমেন্ট এনভায়রনমেন্ট চালু করার পদক্ষেপ"
        elif tool_name == "manage_process":
            return f"সিস্টেম প্রসেস {kwargs.get('action', '')} পরিচালনা করার পদক্ষেপ"
        elif tool_name == "get_system_telemetry":
            return "সিস্টেম পারফরম্যান্স পরিমাপ করার পদক্ষেপ"
        return "আপনার নির্দেশ অনুযায়ী প্রয়োজনীয় কাজ সম্পাদনের পদক্ষেপ"

    def _instrument_tool(self, tool_func: Callable) -> Callable:
        """Instrument tool function with observability, full-screen read, and reflection loops."""
        @functools.wraps(tool_func)
        def wrapper(*args, **kwargs):
            tool_name = tool_func.__name__

            # 1. Automatic Full Screen Read & Pre-Execution Update before any modifying action
            if not self._turn_screen_inspected and tool_name not in ["capture_desktop_screen", "analyze_screen_content"]:
                self._turn_screen_inspected = True
                try:
                    screen_state = inspect_full_screen_state()
                    screen_summary = screen_state.get("summary", "স্ক্রিন পর্যবেক্ষণ সম্পন্ন হয়েছে।")
                    action_desc = self._format_action_description(tool_name, kwargs)
                    if self.on_pre_execution:
                        self.on_pre_execution(screen_summary, action_desc)
                except Exception as sc_err:
                    logger.debug(f"Pre-execution screen inspection error: {sc_err}")

            if self.on_tool_start:
                try:
                    self.on_tool_start(tool_name, kwargs)
                except Exception as e:
                    logger.debug(f"on_tool_start callback exception: {e}")

            result = tool_func(*args, **kwargs)

            # Automated self-learning reflection feedback loop
            if isinstance(result, dict) and result.get("status") in ["failed", "error", "security_blocked"]:
                err_msg = result.get("stderr") or result.get("message") or "Unknown execution failure"
                self.reflection_engine.log_execution(
                    action=f"{tool_name}({kwargs})",
                    success=False,
                    output=str(result.get("stdout") or ""),
                    error=err_msg,
                    context="Autonomous tool loop execution",
                )

            if self.on_tool_end:
                try:
                    self.on_tool_end(tool_name, result)
                except Exception as e:
                    logger.debug(f"on_tool_end callback exception: {e}")

            return result

        return wrapper

    def _get_client(self):
        """Lazy-initialize official google-genai Client."""
        if self._client is None:
            if not self.api_key:
                raise ValueError(
                    "Missing GEMINI_API_KEY. Please provide GEMINI_API_KEY in your .env file or environment."
                )
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except ImportError:
                raise ImportError("The 'google-genai' package is required. Install with: pip install google-genai")
        return self._client

    def reset_session(self) -> None:
        """Reset conversation session state."""
        self._chat_session = None

    def _init_chat_session(self, model: Optional[str] = None):
        """Initialize clean multi-turn chat session with tools."""
        from google.genai import types

        active_model = model or self.model_name
        client = self._get_client()

        config = types.GenerateContentConfig(
            system_instruction=self.system_prompt,
            tools=self.tools,
            temperature=0.2,
        )

        self._chat_session = client.chats.create(
            model=active_model,
            config=config,
        )
        self.model_name = active_model

    def chat(self, user_message: str) -> str:
        """Send a message to JARVIS and receive an autonomous response.

        The agent focuses strictly on the current instruction while maintaining
        underlying multi-turn session memory naturally.

        Args:
            user_message: Input text from CLI or Bengali Voice.

        Returns:
            The agent's final text response.
        """
        msg_clean = user_message.strip().lower()
        msg_norm = msg_clean.rstrip("?.,!|। ")

        # 1. Wakeup / Calling trigger (যখন ইউজার জার্ভিসকে ডাকবেন):
        # "ar jkhon ami jarvis ke dakbo just bolbe ji sir bolen ki korbo er besi kichu bola dorkar nai"
        wake_calls = [
            "জার্ভিস", "জারভিস", "jarvis", "jarvis?", "hey jarvis", "hi jarvis",
            "hello jarvis", "হ্যালো জার্ভিস", "জার্ভিস শুনছো", "জার্ভিস শুনছেন",
            "শুনছো", "শুনছেন", "জার্ভিস আছো", "জার্ভিস আছেন", "এই জার্ভিস"
        ]
        if msg_norm in wake_calls:
            return "হ্যালো স্যার, বলুন কী করব?"

        # 2. Stop trigger
        if msg_norm in ["থামো", "এখন থামো", "দাঁড়াও", "দাঁড়ান", "চুপ করো", "চুপ করুন", "stop"]:
            return "হ্যালো স্যার, আমি থেমেছি। বলুন কী করব?"

        # Reset turn screen inspection flag for current execution
        self._turn_screen_inspected = False

        # Contextual semantic memory recall injection
        prompt_to_send = user_message
        try:
            recalled_ctx = self.memory.semantic_recall(user_message, n_results=2)
            if recalled_ctx and recalled_ctx.strip() and "কোনো সংশ্লিষ্ট" not in recalled_ctx:
                prompt_to_send = f"[মেমোরি ও প্রাসঙ্গিক তথ্যসূত্র]:\n{recalled_ctx}\n\n[ইউজারের প্রশ্ন বা নির্দেশ]:\n{user_message}"
        except Exception as rec_err:
            logger.debug(f"Memory recall error: {rec_err}")

        candidate_models = [self.model_name] + [
            m for m in self.settings.fallback_models if m != self.model_name
        ]
        last_error = None

        for model in candidate_models:
            try:
                # Maintain active chat session; only initialize if not created or model changed
                if self._chat_session is None or self.model_name != model:
                    self._init_chat_session(model=model)

                response = self._chat_session.send_message(prompt_to_send)
                result_text = response.text if response.text else "হ্যালো স্যার, কাজ সম্পন্ন হয়েছে।"

                # Persist turn to long-term episodic vector memory silently (skip generic greetings)
                if result_text.strip() not in ["হ্যালো স্যার, বলুন কী করব?", "হ্যালো স্যার, আমি থেমেছি। বলুন কী করব?"]:
                    try:
                        self.memory.store_interaction(user_message, result_text)
                    except Exception as mem_err:
                        logger.debug(f"Could not persist turn to vector memory: {mem_err}")

                return result_text

            except Exception as e:
                err_str = str(e)
                last_error = e
                # Check for rate limit (429), resource exhaustion, 503, or 404
                if any(code in err_str for code in ["429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE", "404", "NOT_FOUND"]):
                    logger.warning(
                        f"Model '{model}' encountered limit/unavailability ({err_str[:80]}...). Routing to candidate fallback..."
                    )
                    self._chat_session = None
                    continue
                else:
                    logger.error(f"Error in JARVIS chat turn: {e}")
                    raise

        raise last_error
