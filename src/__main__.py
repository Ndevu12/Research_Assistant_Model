# -*- coding: utf-8 -*-
"""AI Research Assistant - Main Entry Point

Run with:
    python -m src
    python -m src "your query"
    python -m src --format json "your query"
    python -m src --export bibtex,apa "your query"
    python -m src --help
"""

import argparse
import asyncio
import sys
from pathlib import Path

from .memory.session import InteractiveResearchSession, follow_up_help_text
from .retrieval.orchestrator import run_research_helper
from .utils.input_handler import get_user_query
from .utils.message_formatter import MessageFormatter
from .utils.logging_system import logger


def ensure_setup() -> bool:
    """Ensure all setup requirements are met before running the application.

    Returns:
        bool: True if setup is complete and successful, False otherwise
    """
    import os

    if os.environ.get("RA_SKIP_SETUP_CHECK", "").strip().lower() in {"1", "true", "yes"}:
        logger.info("RA_SKIP_SETUP_CHECK is set; skipping environment setup checks.")
        return True

    if os.environ.get("PIPENV_ACTIVE") != "1":
        logger.warning(
            "Not running inside Pipenv. Use: pipenv run python -m src ... "
            "to ensure all dependencies (sentence-transformers, etc.) are available."
        )

    from .config.settings import get_settings

    llm_provider = get_settings().llm.provider.strip().lower()
    if llm_provider != "ollama":
        logger.info(
            "Using remote LLM provider '%s'; skipping local Ollama setup checks.",
            llm_provider,
        )
        return True

    cwd = Path(os.getcwd())
    setups_path = cwd / "setups"

    if not setups_path.exists():
        logger.error(f"Setup directory not found at {setups_path}")
        return False

    if str(setups_path) not in sys.path:
        sys.path.insert(0, str(setups_path))

    try:
        import health_check
        import manager
    except ImportError as e:
        logger.error(f"Failed to import setup modules: {e}")
        return False

    logger.info("Checking setup status...")
    ollama_ok, ollama_message = health_check.check_ollama_running()
    model_ok, model_message = health_check.check_model_available()

    if ollama_ok and model_ok:
        logger.info("Setup is complete and ready to use")
        logger.info(model_message)
        return True

    if not ollama_ok:
        logger.warning(f"Setup incomplete: {ollama_message}")
    if not model_ok:
        logger.warning(f"Setup incomplete: {model_message}")

    logger.warning("Running automatic setup...")
    health_check.print_report()

    if not manager.run_setup():
        logger.error("Automatic setup failed. Please run setup manually: python -m setups.manager")
        return False

    logger.info("Setup completed successfully!")
    return True


def _parse_export_formats(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [part.strip().lower() for part in value.split(",") if part.strip()]


async def _initialize_session(session: InteractiveResearchSession) -> None:
    await session.initialize()


async def _handle_follow_up(
    session: InteractiveResearchSession,
    text: str,
    *,
    output_format: str,
    export_formats: list[str] | None,
) -> str | None:
    return await session.handle_follow_up(
        text,
        output_format=output_format,
        export_formats=export_formats,
    )


async def _run_session_query(
    session: InteractiveResearchSession,
    query: str,
    *,
    output_format: str,
    export_formats: list[str] | None,
    stream_progress: bool = True,
) -> str:
    return await session.run_full_query(
        query,
        output_format=output_format,
        export_formats=export_formats,
        stream_progress=stream_progress,
    )


def run_interactive_mode(
    output_format: str = "markdown",
    export_formats: list[str] | None = None,
    stream_progress: bool = True,
) -> None:
    """Run the research assistant in interactive mode with session support."""
    print(MessageFormatter.welcome_message())
    print(
        "\nSession follow-ups (after your first query):\n"
        f"{follow_up_help_text()}\n"
    )

    session = InteractiveResearchSession()
    asyncio.run(_initialize_session(session))

    try:
        while True:
            query = get_user_query()
            if query is None:
                break

            follow_up = asyncio.run(
                _handle_follow_up(
                    session,
                    query,
                    output_format=output_format,
                    export_formats=export_formats,
                )
            )
            if follow_up is not None:
                print(follow_up)
                print(MessageFormatter.result_separator())
                continue

            rendered = asyncio.run(
                _run_session_query(
                    session,
                    query,
                    output_format=output_format,
                    export_formats=export_formats,
                    stream_progress=stream_progress,
                )
            )
            print(rendered)
            print(MessageFormatter.result_separator())

    except KeyboardInterrupt:
        print()

    finally:
        print(MessageFormatter.farewell_message())


def main() -> None:
    """Main entry point for the CLI."""
    if not ensure_setup():
        logger.error("Cannot proceed without completing setup")
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="AI Research Assistant - Retrieve and analyze academic papers",
    )
    parser.add_argument(
        "query",
        nargs="?",
        help="Research query. If omitted, enters interactive mode.",
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "json", "html", "pdf"],
        default="markdown",
        help="Report output format (default: markdown; pdf = print-ready HTML)",
    )
    parser.add_argument(
        "--export",
        dest="export_formats",
        metavar="FORMATS",
        help="Comma-separated citation exports: bibtex, apa, mla, chicago",
    )
    parser.add_argument(
        "--session",
        action="store_true",
        help="Enable SQLite session memory in batch mode",
    )
    parser.add_argument(
        "--output",
        "-o",
        metavar="FILE",
        help="Write report to FILE (recommended for --format html or pdf)",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable live progress streaming on stderr",
    )
    args = parser.parse_args()

    export_formats = _parse_export_formats(getattr(args, "export_formats", None))
    output_format = getattr(args, "format", "markdown")
    stream_progress = not getattr(args, "no_progress", False)

    if args.query:
        asyncio.run(
            run_research_helper(
                args.query,
                return_report=False,
                output_format=output_format,
                export_formats=export_formats,
                output_path=getattr(args, "output", None),
                stream_progress=stream_progress,
            )
        )
    else:
        run_interactive_mode(
            output_format=output_format,
            export_formats=export_formats,
            stream_progress=stream_progress,
        )


if __name__ == "__main__":
    main()
