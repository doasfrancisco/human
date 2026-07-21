import os
import json
import hashlib
import pathlib
import re
import subprocess
import sys
import textwrap
from typing import Any

ROOT = pathlib.Path(__file__).parent.resolve()
LANG = ROOT / "lang"
PROGS = ROOT / "progs"
CACHE = ROOT / ".cache"
BUILD = CACHE / "build"
MODEL_ID = "o3"

CACHE.mkdir(parents=True, exist_ok=True)
BUILD.mkdir(parents=True, exist_ok=True)


class Malformed(Exception):
    pass


class Node:
    def __init__(self, tag: str, text: str, depth: int, children: list):
        self.tag = tag
        self.text = text
        self.depth = depth
        self.children = children

    def __repr__(self):
        return f"Node({self.tag!r}, {self.text!r}, children={len(self.children)})"


def lang_text(name: str) -> str:
    path = LANG / name
    if not path.exists():
        raise Malformed(f"lang file not found: {path}")
    return path.read_text(encoding="utf-8")


def _hash(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def cached(key: str, produce) -> str:
    digest = _hash(key)
    cache_file = CACHE / digest
    if cache_file.exists():
        return cache_file.read_text(encoding="utf-8")
    result = produce()
    cache_file.write_text(result, encoding="utf-8")
    return result


def call(prompt: str) -> str:
    import urllib.request
    key = os.environ.get("OPENAI_API_KEY", "")
    payload = json.dumps({
        "model": MODEL_ID,
        "input": prompt,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    for item in body.get("output", []):
        if item.get("type") == "message":
            for part in item.get("content", []):
                if part.get("type") == "output_text":
                    return part["text"]
    raise Malformed(f"unexpected response shape: {body}")


def call_json(prompt: str) -> Any:
    raw = call(prompt)
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if match:
        text = match.group(1)
    else:
        text = raw
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError as exc:
        raise Malformed(f"model did not return valid JSON: {exc}\n{raw}") from exc


def _parse_tree(text: str) -> list:
    nodes = []
    stack = []
    for line in text.splitlines():
        if not line.strip():
            continue
        stripped = line.lstrip()
        depth = (len(line) - len(stripped)) // 4
        stripped = stripped.rstrip()
        if stripped.startswith("[") and "]" in stripped:
            bracket_end = stripped.index("]")
            tag = stripped[1:bracket_end]
            rest = stripped[bracket_end + 1:].strip()
        else:
            tag = ""
            rest = stripped
        node = Node(tag=tag, text=rest, depth=depth, children=[])
        while stack and stack[-1].depth >= depth:
            stack.pop()
        if stack:
            stack[-1].children.append(node)
        else:
            nodes.append(node)
        stack.append(node)
    return nodes


def serialize(nodes: list) -> str:
    lines = []

    def _emit(node: Node):
        indent = "    " * node.depth
        if node.tag:
            lines.append(f"{indent}[{node.tag}] {node.text}".rstrip())
        else:
            lines.append(f"{indent}{node.text}".rstrip())
        for child in node.children:
            _emit(child)

    for node in nodes:
        _emit(node)
    return "\n".join(lines)


def generate(prog_name: str) -> str:
    prog_path = PROGS / prog_name
    if not prog_path.exists():
        raise Malformed(f"program not found: {prog_path}")
    prog_text = prog_path.read_text(encoding="utf-8")

    lang_parts = []
    for lang_file in sorted(LANG.iterdir()):
        if lang_file.is_file():
            lang_parts.append(f"### {lang_file.name}\n{lang_file.read_text(encoding='utf-8')}")
    lang_combined = "\n\n".join(lang_parts)

    prompt = f"{lang_combined}\n\n# The program\n{prog_text}"

    def produce():
        return call(prompt)

    return cached(prompt, produce)


def tally(source: str) -> dict:
    counts = {}
    for line in source.splitlines():
        stripped = line.lstrip()
        depth = (len(line) - len(stripped)) // 4
        if stripped.startswith("[") and "]" in stripped:
            bracket_end = stripped.index("]")
            tag = stripped[1:bracket_end]
            counts[tag] = counts.get(tag, 0) + 1
    return counts


def caused_by(source: str, node_tag: str) -> list:
    nodes = _parse_tree(source)
    results = []

    def _find(node: Node):
        if node.tag == node_tag:
            results.append(node)
        for child in node.children:
            _find(child)

    for node in nodes:
        _find(node)
    return results


def project(source: str, tags: list) -> list:
    tag_set = set(tags)
    nodes = _parse_tree(source)
    results = []

    def _find(node: Node):
        if node.tag in tag_set:
            results.append(node)
        for child in node.children:
            _find(child)

    for node in nodes:
        _find(node)
    return results


def propose(source: str, instruction: str) -> str:
    prompt = (
        f"You are editing a human-language program tree.\n"
        f"Instruction: {instruction}\n\n"
        f"Current tree:\n{source}\n\n"
        f"Return the full updated tree and nothing else."
    )

    def produce():
        return call(prompt)

    return cached(prompt, produce)


def lower(source: str) -> str:
    lang_parts = []
    for lang_file in sorted(LANG.iterdir()):
        if lang_file.is_file():
            lang_parts.append(f"### {lang_file.name}\n{lang_file.read_text(encoding='utf-8')}")
    lang_combined = "\n\n".join(lang_parts)

    prompt = (
        f"{lang_combined}\n\n"
        f"# The program\n{source}"
    )

    def produce():
        return call(prompt)

    return cached(prompt, produce)


def build(prog_name: str) -> pathlib.Path:
    source = generate(prog_name)
    match = re.search(r"```(?:python)?\s*([\s\S]*?)```", source)
    if match:
        code = match.group(1)
    else:
        code = source

    out_path = BUILD / f"{prog_name.replace('/', '_')}.py"
    out_path.write_text(code, encoding="utf-8")
    return out_path


def raises(func, *args, exception=Exception, **kwargs) -> bool:
    try:
        func(*args, **kwargs)
        return False
    except exception:
        return True


if __name__ == "__main__":
    pass