from __future__ import annotations

import re
from typing import Any

SPLIT_CODE_EXTENSIONS = [
    "py", "ts", "tsx", "js", "jsx", "mjs", "cjs", "css", "json",
    "html", "md", "toml", "yaml", "yml", "txt", "svg",
]
SPLIT_TARGET_EXTENSIONS = ["context", *SPLIT_CODE_EXTENSIONS]

SPLIT_TARGET_RE = re.compile(
    r"^([\w.\-/]+\.(?:" + "|".join(SPLIT_TARGET_EXTENSIONS) + r"))\s*(?:—|–|--|:)\s*(.*)$"
)
SPLIT_TARGET_SUFFIX_RE = re.compile(r"\.(?:" + "|".join(SPLIT_TARGET_EXTENSIONS) + r")$")

def numbered_context_lines(text: str) -> list[tuple[int, str, str | None]]:
    numbered: list[tuple[int, str, str | None]] = []
    target: str | None = None
    for index, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        match = SPLIT_TARGET_RE.match(stripped)
        if match:
            target = match.group(1)
        numbered.append((index, line, target))
    return numbered


def parse_split_sections(text: str) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = SPLIT_TARGET_RE.match(stripped)
        if match:
            current = {"target": match.group(1), "description": [match.group(2).strip()]}
            sections.append(current)
        elif current:
            current["description"].append(stripped)
    return sections


def split_section_headers(context: str) -> list[tuple[str, str]]:
    headers: list[tuple[str, str]] = []
    seen_targets: set[str] = set()
    for line in context.splitlines():
        stripped = line.strip()
        match = SPLIT_TARGET_RE.match(stripped) if stripped else None
        if match and match.group(1) not in seen_targets:
            seen_targets.add(match.group(1))
            headers.append((match.group(1), stripped))
    return headers
