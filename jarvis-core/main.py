"""JARVIS - Unified CLI & Natural Bengali Voice Entrypoint.

Local Autonomous AI Desktop Assistant & Workstation Controller.
"""
import argparse
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure jarvis-core directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.settings import get_settings
from core.agent import JarvisAgent
from interfaces.voice_engine import get_voice_engine
from memory.vector_store import get_memory_manager
from memory.reflection_engine import get_reflection_engine
from tools.system_tools import get_system_telemetry

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown

console = Console()
logger = logging.getLogger("jarvis")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)


def handle_shutdown_signal(sig, frame):
    """Handle termination signals gracefully."""
    console.print("\n[bold red]বিদায় স্যার। JARVIS সিস্টেম শাটডাউন সম্পন্ন হচ্ছে...[/bold red]")
    try:
        ve = get_voice_engine()
        ve.shutdown()
    except Exception:
        pass
    sys.exit(0)


signal.signal(signal.SIGINT, handle_shutdown_signal)
signal.signal(signal.SIGTERM, handle_shutdown_signal)


def print_banner(voice_active: bool = False):
    """Display rich welcome banner."""
    settings = get_settings()
    banner_text = f"""
[bold cyan]  ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗[/bold cyan]
[bold cyan]  ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝[/bold cyan]
[bold cyan]  ██║███████║██████╔╝██║   ██║██║███████╗[/bold cyan]
[bold cyan]  ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║[/bold cyan]
[bold cyan]████║██║  ██║██║  ██║ ╚████╔╝ ██║███████║[/bold cyan]
[bold cyan]╚═══╝╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝[/bold cyan]

[bold white]Autonomous Desktop AI Assistant & Workstation Controller[/bold white]
[yellow]• Model:[/yellow] [green]{settings.default_model}[/green]
[yellow]• Bengali Voice:[/yellow] [green]{settings.voice_name} ({'ACTIVE 🎤' if voice_active else 'STANDBY'})[/green]
[yellow]• Vector Memory:[/yellow] [green]ChromaDB Active 🧠[/green]
[yellow]• Self-Learning Loop:[/yellow] [green]Reflection Engine Active 🔄[/green]
[yellow]• Safety Mode:[/yellow] [green]{settings.safety_mode} 🛡️[/green]
"""
    console.print(Panel(banner_text.strip(), title="[bold cyan]SYSTEM ONLINE[/bold cyan]", border_style="cyan"))


def display_telemetry_table():
    """Render system telemetry in a styled Rich table."""
    telem = get_system_telemetry()
    table = Table(title="Workstation Telemetry", border_style="cyan")
    table.add_column("Resource", style="bold cyan")
    table.add_column("Details", style="white")

    if "error" in telem:
        table.add_row("Error", telem["error"])
        console.print(table)
        return

    table.add_row("CPU Usage", f"{telem['cpu']['usage_percent']}% ({telem['cpu']['cores']} Cores)")
    table.add_row("RAM Total / Used", f"{telem['ram']['total_gb']} GB / {telem['ram']['used_gb']} GB ({telem['ram']['usage_percent']}%)")
    table.add_row("RAM Available", f"{telem['ram']['free_gb']} GB")
    table.add_row("Root Disk", f"{telem['disk_root']['total_gb']} GB (Free: {telem['disk_root']['free_gb']} GB)")

    procs_summary = ", ".join([f"{p['name']} ({p['memory_pct']}%)" for p in telem.get("top_processes", [])[:3]])
    table.add_row("Top Memory Processes", procs_summary or "N/A")

    console.print(table)


def on_tool_start_visual(tool_name: str, kwargs: Dict[str, Any]) -> None:
    """Display real-time visual indicator on screen when tools execute."""
    if tool_name == "send_desktop_message":
        app = kwargs.get("app_name", "App")
        contact = kwargs.get("contact_name", "")
        msg = kwargs.get("message", "")
        console.print(f"📱 [bold cyan]ডেস্কটপ মেসেজ পাঠানো হচ্ছে:[/bold cyan] অ্যাপ: [yellow]{app}[/yellow], প্রাপক: [green]{contact}[/green], বার্তা: [white]{msg}[/white]")
    elif tool_name == "open_desktop_application":
        console.print(f"🖥️ [bold cyan]অ্যাপ্লিকেশন ওপেন করা হচ্ছে:[/bold cyan] [green]{kwargs.get('app_name')}[/green]")
    elif tool_name == "automate_gui_action":
        act = kwargs.get("action", "")
        tgt = kwargs.get("text") or kwargs.get("key") or kwargs.get("hotkey") or ""
        console.print(f"🖱️ [bold cyan]GUI অটোমেশন কার্যকর হচ্ছে:[/bold cyan] [yellow]{act}[/yellow] ({tgt})")
    elif tool_name == "execute_terminal_command":
        console.print(f"💻 [bold cyan]টার্মিনালে নির্দেশ সম্পন্ন হচ্ছে:[/bold cyan] [yellow]{kwargs.get('command')}[/yellow]")
    elif tool_name == "write_workspace_file":
        console.print(f"📄 [bold yellow]ফাইল তৈরি/আপডেট করা হচ্ছে:[/bold yellow] [green]{kwargs.get('file_path')}[/green]")
    elif tool_name == "read_workspace_file":
        console.print(f"📖 [bold magenta]ফাইল খোলা ও পড়া হচ্ছে:[/bold magenta] [cyan]{kwargs.get('file_path')}[/cyan]")
    elif tool_name == "inspect_directory_tree":
        console.print(f"📂 [bold blue]ফোল্ডারে প্রবেশ ও পরিদর্শন করা হচ্ছে:[/bold blue] [cyan]{kwargs.get('path', '.')}[/cyan]")
    elif tool_name in ["search_web_research", "extract_web_page_content"]:
        target = kwargs.get("query") or kwargs.get("url") or ""
        console.print(f"🌐 [bold magenta]ইন্টারনেটে তথ্য অনুসন্ধান ও ব্রাউজিং করা হচ্ছে:[/bold magenta] [cyan]{target}[/cyan]")
    elif tool_name == "launch_developer_ide":
        console.print(f"🚀 [bold green]আইডিই লঞ্চ করা হচ্ছে:[/bold green] [cyan]{kwargs.get('ide_name')}[/cyan]")
    elif tool_name in ["capture_desktop_screen", "analyze_screen_content"]:
        console.print("👁️ [bold cyan]মনিটরের স্ক্রিন পর্যবেক্ষণ ও বিশ্লেষণ করা হচ্ছে...[/bold cyan]")
    elif tool_name == "get_system_telemetry":
        console.print("📊 [bold cyan]সিস্টেমের হার্ডওয়্যার পারফরম্যান্স পরিমাপ করা হচ্ছে...[/bold cyan]")
    elif tool_name == "manage_process":
        console.print(f"⚙️ [bold yellow]প্রসেস পর্যবেক্ষণ ও পরিচালনা করা হচ্ছে:[/bold yellow] [cyan]{kwargs.get('action')}[/cyan]")
    else:
        console.print(f"🔧 [bold cyan]টুল কার্যকর হচ্ছে:[/bold cyan] [dim]{tool_name}[/dim]")


_voice_active = [False]


def on_pre_execution_visual(screen_summary: str, action_desc: str) -> None:
    """Read full screen quietly in background without speaking out loud."""
    console.print(f"👁️ [dim cyan]স্ক্রিন পর্যবেক্ষণ (ব্যাকগ্রাউন্ড):[/dim cyan] [dim]{screen_summary}[/dim]")


def on_tool_end_visual(tool_name: str, result: Any) -> None:
    """Display visual completion state or obstacle alert for tool execution."""
    if isinstance(result, dict) and result.get("status") in ["failed", "error", "security_blocked"]:
        obstacle_msg = result.get('message') or result.get('stderr') or 'অজ্ঞাত বাধা'
        console.print(f"   [bold red]⚠️ কাজে বাধা/ত্রুটি সনাক্ত হয়েছে:[/bold red] [yellow]{obstacle_msg}[/yellow]")
    else:
        console.print(f"   [bold green]✔ কাজ সফলভাবে সম্পন্ন হয়েছে[/bold green]")


def run_single_prompt(agent: JarvisAgent, prompt: str, voice_enabled: bool = False):
    """Execute a single query and exit."""
    _voice_active[0] = voice_enabled
    ve = get_voice_engine()
    with console.status("[bold cyan]JARVIS চিন্তা করছে ও কাজ সম্পাদন করছে...[/bold cyan]"):
        response = agent.chat(prompt)

    console.print(Panel(Markdown(response), title="[bold green]JARVIS[/bold green]", border_style="green"))
    if voice_enabled:
        ve.speak(response, blocking=True)


def interactive_text_loop(agent: JarvisAgent, voice_enabled: bool = False):
    """Run interactive CLI terminal REPL."""
    _voice_active[0] = voice_enabled
    print_banner(voice_active=voice_enabled)
    ve = get_voice_engine()

    console.print("[dim]টাইপ করুন 'exit' বা 'quit' প্রস্থান করতে, 'telemetry' সিস্টেম স্ট্যাটাস দেখতে, 'reset' মেমোরি ক্লিয়ার করতে।[/dim]\n")

    while True:
        try:
            user_input = console.input("[bold cyan]USER > [/bold cyan]").strip()
            if not user_input:
                continue

            cmd_lower = user_input.lower()
            if cmd_lower in ["exit", "quit", "q"]:
                console.print("[bold cyan]বিদায় স্যার। ভালো থাকবেন।[/bold cyan]")
                break
            elif cmd_lower in ["reset", "clear"]:
                agent.reset_session()
                console.print("[green]সেশন মেমোরি রিসেট করা হয়েছে স্যার।[/green]")
                continue
            elif cmd_lower in ["telemetry", "status"]:
                display_telemetry_table()
                continue
            elif cmd_lower == "voice on":
                voice_enabled = True
                _voice_active[0] = True
                console.print("[green]বাংলা ভয়েস আউটপুট চালু করা হয়েছে।[/green]")
                continue
            elif cmd_lower == "voice off":
                voice_enabled = False
                _voice_active[0] = False
                console.print("[yellow]বাংলা ভয়েস আউটপুট বন্ধ করা হয়েছে।[/yellow]")
                continue

            with console.status("[bold cyan]JARVIS কাজ করছে...[/bold cyan]"):
                response = agent.chat(user_input)

            console.print(Panel(Markdown(response), title="[bold green]JARVIS[/bold green]", border_style="green"))

            if voice_enabled:
                ve.speak(response, blocking=True)

        except (KeyboardInterrupt, EOFError):
            handle_shutdown_signal(None, None)
        except Exception as e:
            console.print(f"[bold red]ত্রুটি:[/bold red] {e}")


def interactive_voice_loop(agent: JarvisAgent):
    """Run continuous hands-free Bengali voice interaction loop with serialized audio and zero echo."""
    _voice_active[0] = True
    print_banner(voice_active=True)
    ve = get_voice_engine()

    if not ve.is_stt_ready:
        console.print("[bold red]মাইক্রোফোন বা STT ডিভাইস সনাক্ত করা যায়নি। CLI টেক্সট মোডে সুইচ করা হচ্ছে...[/bold red]")
        interactive_text_loop(agent, voice_enabled=True)
        return

    console.print("[bold green]🎤 বাংলা ভয়েস মোড সক্রিয়। স্পষ্ট বাংলায় আপনার নির্দেশ দিন...[/bold green]")
    console.print("[dim](কথোপকথন থামাতে 'বিদায়' বা 'exit' বলুন, অথবা Ctrl+C চাপুন)[/dim]\n")

    # Initial greeting played to 100% completion before opening microphone
    greeting = "জ্বি স্যার, বলুন কী করব?"
    console.print(f"[bold green]JARVIS:[/bold green] {greeting}")
    ve.speak(greeting, blocking=True)

    while True:
        try:
            console.print("\n[bold cyan]🎤 শুনছি... (ধীরে-সুস্থে কথা বলুন)[/bold cyan]")
            speech_text = ve.listen(timeout=10, phrase_time_limit=35)

            if not speech_text or not speech_text.strip():
                continue

            console.print(f"[bold yellow]🗣️ আপনি বলেছেন:[/bold yellow] {speech_text}")

            if any(term in speech_text.lower() for term in ["বিদায়", "exit", "quit", "বন্ধ করো", "bye"]):
                farewell = "জ্বি স্যার, বিদায়। ভালো থাকবেন।"
                console.print(f"[bold green]JARVIS:[/bold green] {farewell}")
                ve.speak(farewell, blocking=True)
                break

            with console.status("[bold cyan]JARVIS কাজ করছে...[/bold cyan]"):
                response = agent.chat(speech_text)

            console.print(Panel(Markdown(response), title="[bold green]JARVIS[/bold green]", border_style="green"))

            # Play response cleanly to completion (blocking=True) so microphone never picks up the speaker output
            ve.speak(response, blocking=True)

        except (KeyboardInterrupt, EOFError):
            handle_shutdown_signal(None, None)
        except Exception as e:
            console.print(f"[bold red]ত্রুটি:[/bold red] {e}")


def main():
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(description="JARVIS - Local Autonomous AI Desktop Assistant & System Controller")
    parser.add_argument("--voice", action="store_true", help="Start in natural Bengali voice conversation mode")
    parser.add_argument("--text", action="store_true", help="Start in interactive terminal CLI REPL mode")
    parser.add_argument("--prompt", type=str, help="Execute a single command or question and exit")
    parser.add_argument("--mcp", action="store_true", help="Launch FastMCP stdio server for IDE integration")
    parser.add_argument("--model", type=str, help="Override default Gemini model")

    args = parser.parse_args()

    # FastMCP mode
    if args.mcp:
        from mcp_server import run_server
        run_server()
        return

    # Initialize Agent with visual screen feedback and pre-execution full-screen inspect hooks
    agent = JarvisAgent(
        model_name=args.model,
        on_tool_start=on_tool_start_visual,
        on_tool_end=on_tool_end_visual,
        on_pre_execution=on_pre_execution_visual,
    )

    # One-shot prompt mode
    if args.prompt:
        run_single_prompt(agent, args.prompt, voice_enabled=args.voice)
        return

    # Voice loop mode
    if args.voice:
        interactive_voice_loop(agent)
        return

    # Default to text interactive mode
    interactive_text_loop(agent, voice_enabled=False)


if __name__ == "__main__":
    main()
