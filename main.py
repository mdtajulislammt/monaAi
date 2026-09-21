"""Main entry point for monaAi Desktop Automation Agent."""
import argparse
import os
import sys
from typing import Optional

from config.settings import get_settings
from core.agent import DesktopAgent
from interfaces.cli import CLIInterface
from interfaces.voice import VoiceInterface


def run_single_prompt(agent: DesktopAgent, cli: CLIInterface, prompt: str, voice: Optional[VoiceInterface] = None) -> None:
    """Execute a single prompt and exit."""
    try:
        response = agent.chat(prompt)
        cli.display_response(response)
        if voice and voice.is_tts_available():
            voice.speak(response)
    except Exception as e:
        cli.display_error(str(e))


def interactive_loop(agent: DesktopAgent, cli: CLIInterface, voice: VoiceInterface, voice_mode: bool = False) -> None:
    """Run continuous interactive agent loop supporting CLI text and voice."""
    cli.display_banner(voice_active=voice_mode)

    while True:
        try:
            user_input = ""

            if voice_mode:
                if not voice.is_stt_available():
                    cli.display_error("Microphone/STT is not available. Falling back to text input.")
                    voice_mode = False
                else:
                    print("\n🎤 Listening... (speak your command)")
                    user_input = voice.listen() or ""
                    if user_input:
                        print(f"🗣️ You said: {user_input}")

            if not voice_mode or not user_input:
                if voice_mode and not user_input:
                    # User was silent during voice mode, prompt if they want to switch to text or continue
                    continue
                user_input = cli.prompt_user("monaAi > ")

            if not user_input or not user_input.strip():
                continue

            cmd_lower = user_input.strip().lower()

            # Handle session meta-commands
            if cmd_lower in ["exit", "quit", "q"]:
                print("👋 Goodbye!")
                break

            if cmd_lower in ["reset", "clear"]:
                agent.reset_session()
                print("🔄 Conversation memory reset.")
                continue

            if cmd_lower in ["voice", "toggle-voice"]:
                voice_mode = not voice_mode
                status = "ENABLED" if voice_mode else "DISABLED"
                print(f"🎙️ Voice mode {status}.")
                continue

            # Send prompt to DesktopAgent
            response = agent.chat(user_input)
            cli.display_response(response)

            if voice_mode and voice.is_tts_available():
                voice.speak(response)

        except KeyboardInterrupt:
            print("\nInterrupted by user. Exiting...")
            break
        except Exception as e:
            cli.display_error(f"Error: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="monaAi - Production-Grade Local Desktop AI Agent powered by Gemini Pro"
    )
    parser.add_argument(
        "-p", "--prompt",
        type=str,
        help="Execute a single command or prompt directly and exit.",
    )
    parser.add_argument(
        "-v", "--voice",
        action="store_true",
        help="Start in Voice-interactive mode (Speech-to-Text & Text-to-Speech).",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Override default Gemini model (e.g., gemini-2.5-pro, gemini-1.5-pro).",
    )
    parser.add_argument(
        "--safety",
        type=str,
        choices=["STRICT", "MODERATE", "PERMISSIVE"],
        default=None,
        help="Override security safety level.",
    )
    parser.add_argument(
        "--ui",
        action="store_true",
        help="Start the Desktop Voice & Text Web UI (opens in browser).",
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Force Terminal CLI interactive mode.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port for Desktop Web UI (default: 8765).",
    )
    parser.add_argument(
        "--mcp",
        action="store_true",
        help="Start in Model Context Protocol (MCP) server mode for Antigravity IDE.",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not automatically launch desktop browser window.",
    )
    args = parser.parse_args()

    # Route to MCP server if requested
    if args.mcp:
        from mcp_server import main as mcp_main
        mcp_main()
        return

    # Apply setting overrides
    settings = get_settings()
    if args.safety:
        settings.safety_mode = args.safety

    # If one-shot prompt is requested
    if args.prompt:
        cli = CLIInterface()
        voice = VoiceInterface()
        agent = DesktopAgent(
            model_name=args.model,
            on_tool_start=cli.display_tool_start,
            on_tool_end=cli.display_tool_end,
        )
        run_single_prompt(agent, cli, args.prompt, voice if args.voice else None)
        return

    # If terminal CLI or voice CLI is explicitly requested
    if args.cli or args.voice:
        cli = CLIInterface()
        voice = VoiceInterface()
        agent = DesktopAgent(
            model_name=args.model,
            on_tool_start=cli.display_tool_start,
            on_tool_end=cli.display_tool_end,
        )
        interactive_loop(agent, cli, voice, voice_mode=args.voice)
        return

    # Default action: Launch Desktop Voice & Text Web UI
    from interfaces.web_ui import run_web_ui
    run_web_ui(port=args.port, open_browser=not args.no_browser)


if __name__ == "__main__":
    main()
