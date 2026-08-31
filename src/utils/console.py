# -*- coding: utf-8 -*-
"""Terminal UI layer built on Rich.

All output funnels through :func:`_emit`, which applies one policy: on an
interactive terminal the Rich renderable is shown; when stdout is piped,
redirected, or captured, the plain-text equivalent (sourced from
:class:`MessageFormatter`) is printed instead, so scripts and redirection
see stable output. Helpers only describe *what* to show, never how the
terminal decision is made.
"""

from __future__ import annotations

import json
from typing import Callable

from rich.console import Console, Group, RenderableType
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


def _emit(plain: str, renderable: RenderableType | Callable[[], RenderableType]) -> None:
    """Print the Rich renderable on a terminal, the plain text otherwise.

    ``renderable`` may be a zero-argument callable so expensive rendering
    (e.g. markdown parsing) only happens when it will actually be shown.
    """
    if stdout_console.is_terminal:
        stdout_console.print(renderable() if callable(renderable) else renderable)
    else:
        print(plain)


def print_welcome(follow_up_help: str = "") -> None:
    """Print the interactive-mode welcome banner."""
    plain = MessageFormatter.welcome_message()
    if follow_up_help:
        plain += f"\n\nSession follow-ups (after your first query):\n{follow_up_help}\n"

    usage = Table.grid(padding=(0, 1))
    usage.add_row("•", "Enter your research query when prompted")
    usage.add_row("•", "Type [accent]exit[/accent] or [accent]quit[/accent] to end your session")
    usage.add_row("•", "Press [accent]Ctrl+C[/accent] to exit at any time")

    body: list[RenderableType] = [usage]
    if follow_up_help:
        body.extend(
            (
                Text(),
                Text("Session follow-ups (after your first query):", style="bold"),
                Text(follow_up_help.rstrip(), style="muted"),
            )
        )

    _emit(
        plain,
        Panel(
            Group(*body),
            title="[brand]AI Research Assistant[/brand]",
            subtitle="[muted]local-first literature review[/muted]",
            border_style="accent",
            padding=(1, 2),
        ),
    )


def print_farewell() -> None:
    """Print the session farewell message."""
    farewell = MessageFormatter.farewell_message()
    _emit(farewell, Text(farewell.strip(), style="success"))


def print_result_separator() -> None:
    """Print the separator between query results."""
    _emit(MessageFormatter.result_separator(), Rule(style="muted"))


def print_error(message: str) -> None:
    """Print an error message."""
    _emit(message, Text(message, style="danger"))


def print_notice(message: str) -> None:
    """Print an informational notice (tips, saved-file confirmations)."""
    _emit(message, Text(message, style="muted"))


def print_report(rendered: str, output_format: str = "markdown") -> None:
    """Print a rendered report, formatting it for human readability on a TTY.

    Markdown is rendered with headings, bullets, and emphasis; JSON is
    syntax-highlighted. Piped output always receives the raw text so
    redirection to files and other tools keeps working.
    """
    _emit(rendered, lambda: _report_renderable(rendered, output_format))


def _report_renderable(rendered: str, output_format: str) -> RenderableType:
    fmt = output_format.lower()
    if fmt == "markdown":
        return Markdown(rendered)
    if fmt == "json":
        try:
            pretty = json.dumps(json.loads(rendered), indent=2, ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            pretty = rendered
        return Syntax(pretty, "json", word_wrap=True, background_color="default")
    return Text(rendered)


def print_citation_export(fmt: str, content: str) -> None:
    """Print one citation export block."""
    _emit(
        f"\n--- {fmt.upper()} Export ---\n{content}",
        Panel(
            Text(content.rstrip()),
            title=f"[accent]{fmt.upper()} export[/accent]",
            border_style="muted",
            padding=(0, 1),
        ),
    )
