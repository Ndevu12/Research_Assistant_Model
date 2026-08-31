# -*- coding: utf-8 -*-
"""Terminal UI layer built on Rich.

Every helper degrades gracefully: on an interactive terminal output is
rendered with Rich (panels, rules, formatted markdown); when stdout is piped,
redirected, or captured, the exact plain-text strings from
:class:`MessageFormatter` are printed instead, so scripts and tests see
stable output.
"""

from __future__ import annotations

import json

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

from .message_formatter import MessageFormatter

_THEME = Theme(
    {
        "brand": "bold cyan",
        "accent": "cyan",
        "muted": "dim",
        "success": "bold green",
        "warning": "yellow",
        "danger": "bold red",
    }
)

stdout_console = Console(highlight=False, theme=_THEME)
stderr_console = Console(stderr=True, highlight=False, theme=_THEME)


def is_interactive_terminal() -> bool:
    """True when stdout is a real terminal (not piped or captured)."""
    return stdout_console.is_terminal


def print_welcome(follow_up_help: str = "") -> None:
    """Print the interactive-mode welcome banner."""
    if not is_interactive_terminal():
        print(MessageFormatter.welcome_message())
        if follow_up_help:
            print(f"\nSession follow-ups (after your first query):\n{follow_up_help}\n")
        return

    usage = Table.grid(padding=(0, 1))
    usage.add_row("•", "Enter your research query when prompted")
    usage.add_row("•", "Type [accent]exit[/accent] or [accent]quit[/accent] to end your session")
    usage.add_row("•", "Press [accent]Ctrl+C[/accent] to exit at any time")

    body: list[object] = [usage]
    if follow_up_help:
        body.append(Text())
        body.append(Text("Session follow-ups (after your first query):", style="bold"))
        body.append(Text(follow_up_help.rstrip(), style="muted"))

    from rich.console import Group

    stdout_console.print(
        Panel(
            Group(*body),
            title="[brand]AI Research Assistant[/brand]",
            subtitle="[muted]local-first literature review[/muted]",
            border_style="accent",
            padding=(1, 2),
        )
    )


def print_farewell() -> None:
    """Print the session farewell message."""
    if not is_interactive_terminal():
        print(MessageFormatter.farewell_message())
        return
    stdout_console.print(
        "\n[success]Thank you for using the AI Research Assistant. Goodbye![/success]"
    )


def print_result_separator() -> None:
    """Print the separator between query results."""
    if not is_interactive_terminal():
        print(MessageFormatter.result_separator())
        return
    stdout_console.print(Rule(style="muted"))


def print_error(message: str) -> None:
    """Print an error message."""
    if not is_interactive_terminal():
        print(message)
        return
    stdout_console.print(Text(message, style="danger"))


def print_notice(message: str) -> None:
    """Print an informational notice (tips, saved-file confirmations)."""
    if not is_interactive_terminal():
        print(message)
        return
    stdout_console.print(Text(message, style="muted"))


def print_report(rendered: str, output_format: str = "markdown") -> None:
    """Print a rendered report, formatting it for human readability on a TTY.

    Markdown is rendered with headings, bullets, and emphasis; JSON is
    syntax-highlighted. Piped output always receives the raw text so
    redirection to files and other tools keeps working.
    """
    if not is_interactive_terminal():
        print(rendered)
        return

    fmt = output_format.lower()
    if fmt == "markdown":
        stdout_console.print(Markdown(rendered))
    elif fmt == "json":
        try:
            pretty = json.dumps(json.loads(rendered), indent=2, ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            pretty = rendered
        stdout_console.print(Syntax(pretty, "json", word_wrap=True, background_color="default"))
    else:
        print(rendered)


def print_citation_export(fmt: str, content: str) -> None:
    """Print one citation export block."""
    if not is_interactive_terminal():
        print(f"\n--- {fmt.upper()} Export ---\n{content}")
        return
    stdout_console.print(
        Panel(
            Text(content.rstrip()),
            title=f"[accent]{fmt.upper()} export[/accent]",
            border_style="muted",
            padding=(0, 1),
        )
    )
