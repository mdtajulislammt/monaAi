"""Rich terminal UI presentation and interactive command-line loop."""
import json
from typing import Any, Dict, Optional

try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.rule import Rule
    from rich.table import Table
    from rich.theme import Theme

    custom_theme = Theme({
        "info": "cyan",
        "warning": "yellow",
        "danger": "bold red",
        "success": "bold green",
        "tool": "bold magenta",
    })
except ImportError:
    Console = None
    Markdown = None
    Panel = None
    Rule = None
    Table = None
    Theme = None
    custom_theme = None

from config.settings import get_settings


class CLIInterface:
    """Rich terminal user interface for the Desktop AI Agent."""

    def __init__(self):
        self.settings = get_settings()
        self.console = Console(theme=custom_theme) if Console else None

    def display_banner(self, voice_active: bool = False) -> None:
        """Render a banner showing agent status and configurations."""
        if not self.console:
            print("=== monaAi Desktop Agent ===")
            print(f"Model: {self.settings.default_model} | Safety: {self.settings.safety_mode}")
            return

        mode_badge = "[bold green]VOICE ACTIVE[/bold green]" if voice_active else "[bold cyan]CLI INTERACTIVE[/bold cyan]"
        content = (
            f"[bold white]Workstation Desktop AI Agent[/bold white] | [italic]Google Gemini Pro[/italic]\n"
            f"• [bold]Model:[/bold] {self.settings.default_model}\n"
            f"• [bold]Safety Mode:[/bold] [{ 'red' if self.settings.safety_mode == 'STRICT' else 'yellow'}]{self.settings.safety_mode}[/]\n"
            f"• [bold]Workspace:[/bold] [dim]{self.settings.workspace_root}[/dim]\n"
            f"• [bold]Mode:[/bold] {mode_badge}\n"
            f"• [bold]Commands:[/bold] Type 'exit' to quit, 'reset' to clear context, 'voice' to toggle voice."
        )
        self.console.print(Panel(content, title="🚀 monaAi System Agent", border_style="cyan", padding=(1, 2)))

    def display_tool_start(self, tool_name: str, args: Dict[str, Any]) -> None:
        """Render tool invocation card."""
        if not self.console:
            print(f"⚙️ Running tool: {tool_name}({args})")
            return

        pretty_args = json.dumps(args, indent=2, default=str)
        self.console.print(
            Panel(
                f"[tool]{pretty_args}[/tool]",
                title=f"⚡ Tool Call: [bold yellow]{tool_name}[/bold yellow]",
                border_style="magenta",
                padding=(0, 1),
            )
        )

    def display_tool_end(self, tool_name: str, result: Any) -> None:
        """Render tool execution summary."""
        if not self.console:
            print(f"✔ Tool {tool_name} returned.")
            return

        status = "success"
        if isinstance(result, dict):
            status = result.get("status", "success")

        border = "green" if status == "success" else "red"
        preview = str(result)
        if len(preview) > 500:
            preview = preview[:500] + "... [dim](output truncated)[/dim]"

        self.console.print(
            Panel(
                preview,
                title=f"✔ Result [{tool_name}] - status: {status}",
                border_style=border,
                padding=(0, 1),
            )
        )

    def display_response(self, text: str) -> None:
        """Render markdown AI response to console."""
        if not self.console:
            print(f"\nAI: {text}\n")
            return

        self.console.print()
        self.console.print(Rule(style="dim cyan"))
        self.console.print(Markdown(text))
        self.console.print(Rule(style="dim cyan"))
        self.console.print()

    def display_error(self, message: str) -> None:
        """Render error message."""
        if not self.console:
            print(f"ERROR: {message}")
            return

        self.console.print(f"[bold red]✖ Error:[/bold red] {message}")

    def prompt_user(self, prompt_text: str = "monaAi > ") -> str:
        """Prompt user for input text."""
        try:
            from prompt_toolkit import prompt as pt_prompt
            return pt_prompt(prompt_text).strip()
        except ImportError:
            return input(prompt_text).strip()
