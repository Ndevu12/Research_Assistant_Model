#!/usr/bin/env python3
"""Docs policy checks for CI: scaffold placeholders, contributing pointer, deduplication."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
MKDOCS = ROOT / "mkdocs.yml"
CONTRIBUTING_POINTER = DOCS / "contributing.md"

FENCED_BLOCK_RE = re.compile(r"^```[^\n]*\n(.*?)```", re.MULTILINE | re.DOTALL)
SRC_CMD_LINE_RE = re.compile(r"python -m src\b")

CANONICAL_MARKERS: dict[str, str] = {
    "setup-system/index.md": "<!-- canonical: setup-commands -->",
    "user-guide/cli.md": "<!-- canonical: cli-commands -->",
    "user-guide/output-formats.md": "<!-- canonical: output-formats -->",
    "development/testing.md": "<!-- canonical: pytest -->",
    "operations/logging-and-debug.md": "<!-- canonical: debug-mode -->",
    "reference/canonical-sources.md": "<!-- canonical: registry -->",
}

SETUP_COMMAND_ALLOWLIST = {"setup-system/index.md"}
MKDOCS_SERVE_ALLOWLIST = {"development/publishing.md"}
PYTEST_ALLOWLIST = {
    "development/testing.md",
    "quality/known-issues.md",
    "development/extensibility.md",
    "api/index.md",
}
SRC_CHEAT_SHEET_ALLOWLIST = {
    "user-guide/cli.md",
    "operations/logging-and-debug.md",
    "operations/progress-streaming.md",
    "user-guide/configuration-cookbook.md",
    "quality/known-issues.md",
    "user-guide/interactive-sessions.md",
    "user-guide/cli-vs-api.md",
    "api/index.md",
}
MIN_SRC_CMD_LINES_PER_BLOCK = 3

SCAFFOLD_MARKERS = (
    "<!-- docs-scaffold -->",
    "<!-- docs-scaffold",
    "<!-- SCAFFOLD",
    "Content pending",
    "This page is a scaffold",
    "This page is a placeholder",
    "TODO: write this page",
    "TODO: document this",
)

MIN_NAV_PAGE_LINES = 25
MIN_LINES_EXCEPTIONS = {
    "contributing.md",
    "research-quality-known-issues.md",
}


def nav_paths_from_mkdocs(text: str) -> list[Path]:
    """Collect markdown paths referenced in mkdocs.yml nav entries."""
    paths: list[Path] = []
    for match in re.finditer(r"^\s*-?\s*(?:[\w\s]+:\s*)?([\w./-]+\.md)\s*$", text, re.MULTILINE):
        rel = match.group(1)
        if rel.startswith("http"):
            continue
        paths.append(DOCS / rel)
    return paths


def check_scaffold_markers(paths: list[Path]) -> list[str]:
    errors: list[str] = []
    for path in paths:
        if not path.exists():
            errors.append(f"missing nav page: {path.relative_to(ROOT)}")
            continue
        text = path.read_text(encoding="utf-8")
        for marker in SCAFFOLD_MARKERS:
            if marker in text:
                errors.append(
                    f"{path.relative_to(ROOT)}: scaffold marker {marker!r} — "
                    "replace with code-backed content before merging"
                )
        if path.name not in MIN_LINES_EXCEPTIONS:
            line_count = len(text.strip().splitlines())
            if line_count < MIN_NAV_PAGE_LINES:
                errors.append(
                    f"{path.relative_to(ROOT)}: only {line_count} lines "
                    f"(minimum {MIN_NAV_PAGE_LINES} for nav pages)"
                )
    return errors


def check_contributing_pointer() -> list[str]:
    """docs/contributing.md must point to root contributing.md, not duplicate it."""
    errors: list[str] = []
    if not CONTRIBUTING_POINTER.exists():
        errors.append("docs/contributing.md is missing")
        return errors

    text = CONTRIBUTING_POINTER.read_text(encoding="utf-8")
    root_link_patterns = (
        r"contributing\.md",
        r"/blob/main/contributing\.md",
    )
    if not any(re.search(pattern, text) for pattern in root_link_patterns):
        errors.append(
            "docs/contributing.md must link to root contributing.md "
            "(canonical GitHub contributor entry)"
        )

    duplicate_signals = (
        "## Local preview",
        "## Conventions",
        "pipenv run mkdocs serve",
        "Single source of truth",
    )
    hits = sum(1 for signal in duplicate_signals if signal in text)
    if hits >= 2:
        errors.append(
            "docs/contributing.md duplicates root contributing.md — "
            "keep it as a short pointer only"
        )

    if len(text.strip().splitlines()) > 20:
        errors.append(
            "docs/contributing.md should be a brief pointer (< 20 lines), "
            f"got {len(text.strip().splitlines())} lines"
        )

    return errors


def iter_fenced_blocks(text: str) -> list[str]:
    """Return inner text of each fenced code block (language tag excluded)."""
    return [match.group(1) for match in FENCED_BLOCK_RE.finditer(text)]


def rel_doc_path(path: Path) -> str:
    return path.relative_to(DOCS).as_posix()


def check_canonical_markers() -> list[str]:
    """Hub pages must declare their canonical role via HTML comment markers."""
    errors: list[str] = []
    for rel_path, marker in CANONICAL_MARKERS.items():
        path = DOCS / rel_path
        if not path.exists():
            errors.append(f"missing canonical hub page: docs/{rel_path}")
            continue
        text = path.read_text(encoding="utf-8")
        if marker not in text:
            errors.append(
                f"docs/{rel_path}: missing canonical marker {marker!r} "
                "(see docs/reference/canonical-sources.md)"
            )
    return errors


def check_duplicate_commands(paths: list[Path]) -> list[str]:
    """Reject copy-paste command blocks duplicated outside their canonical hubs."""
    errors: list[str] = []

    for path in paths:
        rel = rel_doc_path(path)
        text = path.read_text(encoding="utf-8")

        for block in iter_fenced_blocks(text):
            if rel not in SETUP_COMMAND_ALLOWLIST:
                if "pipenv run python -m setups.health_check" in block:
                    errors.append(
                        f"docs/{rel}: duplicate setup health_check command — "
                        "link to setup-system/index.md instead"
                    )
                if re.search(r"pipenv run python -m setups\.manager\b", block):
                    errors.append(
                        f"docs/{rel}: duplicate setups.manager command — "
                        "link to setup-system/index.md instead"
                    )

            if rel not in MKDOCS_SERVE_ALLOWLIST and "pipenv run mkdocs serve" in block:
                errors.append(
                    f"docs/{rel}: duplicate mkdocs serve command — "
                    "link to development/publishing.md instead"
                )

            if rel not in PYTEST_ALLOWLIST and "pipenv run pytest" in block:
                errors.append(
                    f"docs/{rel}: duplicate pytest command — "
                    "link to development/testing.md instead"
                )

            src_cmd_lines = len(SRC_CMD_LINE_RE.findall(block))
            if src_cmd_lines >= MIN_SRC_CMD_LINES_PER_BLOCK and rel not in SRC_CHEAT_SHEET_ALLOWLIST:
                errors.append(
                    f"docs/{rel}: {src_cmd_lines} `python -m src` lines in one code block — "
                    "link to user-guide/cli.md or README Usage instead"
                )

    return errors


def main() -> int:
    if not MKDOCS.exists():
        print(f"error: {MKDOCS} not found", file=sys.stderr)
        return 1

    nav_paths = nav_paths_from_mkdocs(MKDOCS.read_text(encoding="utf-8"))
    errors: list[str] = []
    errors.extend(check_scaffold_markers(nav_paths))
    errors.extend(check_contributing_pointer())
    errors.extend(check_canonical_markers())
    errors.extend(check_duplicate_commands(nav_paths))

    if errors:
        print("Docs policy check failed:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print(
        f"Docs policy OK ({len(nav_paths)} nav pages, "
        f"{len(CANONICAL_MARKERS)} canonical hubs checked)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
