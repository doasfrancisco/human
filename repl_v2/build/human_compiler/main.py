import os
import re
import sys
import json
import time
import hashlib
import textwrap
import ast
import shutil
from pathlib import Path
from collections import Counter
from typing import Optional

import boto3
from dotenv import load_dotenv

ROOT = Path(__file__).parent.resolve()
LANG = ROOT / "lang"
PROGS = ROOT / "progs"
CACHE = ROOT / ".cache"
BUILD = ROOT / ".build"

CACHE.mkdir(exist_ok=True)
BUILD.mkdir(exist_ok=True)

_env_path = ROOT / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

MODEL_ID = os.environ.get("MODEL_ID", "anthropic.claude-opus-4-5")


class Malformed(Exception):
    pass


class Node:
    def __init__(self, path: str):
        self.path = path

    def file(self) -> Path:
        return ROOT / (self.path + ".human")

    def name(self) -> str:
        return self.path.split("/")[-1]

    def level(self) -> int:
        parts = self.path.split("/")
        if len(parts) <= 2:
            return 0
        return len(parts) - 2

    def parent(self) -> Optional["Node"]:
        parts = self.path.split("/")
        if len(parts) <= 2:
            return None
        return Node("/".join(parts[:-1]))

    def program(self) -> str:
        parts = self.path.split("/")
        return "/".join(parts[:2])

    def ancestors(self) -> list:
        result = []
        current = self.parent()
        while current is not None:
            result.append(current)
            current = current.parent()
        result.reverse()
        return result

    def children(self) -> list:
        d = ROOT / self.path
        if not d.is_dir():
            return []
        kids = []
        for f in d.iterdir():
            if f.suffix == ".human":
                stem = f.stem
                try:
                    int(stem)
                    kids.append(Node(self.path + "/" + stem))
                except ValueError:
                    pass
        kids.sort(key=lambda n: int(n.name()))
        return kids

    def subtree(self) -> list:
        result = [self]
        for child in self.children():
            result.extend(child.subtree())
        return result

    def text(self) -> str:
        f = self.file()
        if f.exists():
            return f.read_text(encoding="utf-8").strip()
        return ""

    def intent(self) -> str:
        lines = self.text().splitlines()
        non_assert = [l for l in lines if not l.startswith("assert:")]
        return "\n".join(non_assert).strip()

    def assertions(self) -> list:
        lines = self.text().splitlines()
        claims = [l[len("assert:"):].strip() for l in lines if l.startswith("assert:")]
        return claims


def lang_text(sheet: str) -> str:
    p = LANG / (sheet + ".human")
    if p.exists():
        return p.read_text(encoding="utf-8").strip()
    return ""


def _make_bedrock_client():
    region = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
    kwargs = {"region_name": region}
    key = os.environ.get("AWS_ACCESS_KEY_ID")
    secret = os.environ.get("AWS_SECRET_ACCESS_KEY")
    token = os.environ.get("AWS_SESSION_TOKEN")
    if key and secret:
        kwargs["aws_access_key_id"] = key
        kwargs["aws_secret_access_key"] = secret
        if token:
            kwargs["aws_session_token"] = token
    return boto3.client("bedrock-runtime", **kwargs)


def call(system: str, user: str) -> str:
    client = _make_bedrock_client()
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 8192,
        "temperature": 0,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    })
    response = client.invoke_model(modelId=MODEL_ID, body=body)
    result = json.loads(response["body"].read())
    return result["content"][0]["text"]


def call_json(system: str, user: str) -> dict:
    def _attempt(sys_prompt, usr_prompt):
        text = call(sys_prompt, usr_prompt)
        try:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            return json.loads(text)
        except json.JSONDecodeError as e:
            return None, str(e)

    result = _attempt(system, user)
    if result is not None and not (isinstance(result, tuple) and result[0] is None):
        return result

    sharper_system = system + "\n\nYou MUST respond with valid JSON only. No prose, no markdown, just a JSON object."
    result2 = _attempt(sharper_system, user)
    if result2 is not None and not (isinstance(result2, tuple) and result2[0] is None):
        return result2

    raise Malformed("call_json: could not parse JSON from model response")


def cached(kind: str, key: str, fn):
    lang_dir = LANG / kind
    lang_content = ""
    if lang_dir.is_dir():
        parts = []
        for f in sorted(lang_dir.rglob("*.human")):
            parts.append(f.read_text(encoding="utf-8"))
        lang_content = "\n".join(parts)

    system_prompt = lang_text(kind)

    fingerprint = kind + MODEL_ID + lang_content + system_prompt + key
    h = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

    cache_file = CACHE / (h + ".json")
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))

    result = fn()
    cache_file.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return result


def serialize(root: Node, drop: Optional[str] = None) -> str:
    lines = []
    for node in root.subtree():
        if drop is not None:
            if node.path == drop or node.path.startswith(drop + "/"):
                continue
        indent = "  " * node.level()
        lines.append(f"{indent}[{node.path}] {node.intent()}")
    return "\n".join(lines)


def _extract_python(text: str) -> Optional[str]:
    lines = text.splitlines()
    fence_indices = [i for i, l in enumerate(lines) if l.strip() == "```python" or l.strip() == "```"]
    
    python_blocks = []
    i = 0
    while i < len(lines):
        if lines[i].strip() == "```python":
            start = i
            for j in range(i + 1, len(lines)):
                if lines[j].strip() == "```":
                    python_blocks.append((start, j, "\n".join(lines[i+1:j])))
                    i = j + 1
                    break
            else:
                i += 1
        else:
            i += 1

    if not python_blocks:
        return None
    return python_blocks[-1][2]


def generate(root: Node, node: Optional[Node] = None, baseline: Optional[str] = None) -> str:
    code_system = lang_text("code/code")
    tree_text = serialize(root)

    if node is None and baseline is None:
        system = code_system
        user = tree_text
    else:
        reduce_text = lang_text("code/reduce")
        drop_path = node.path if node else None
        reduced_tree = serialize(root, drop=drop_path)
        system = code_system + "\n\n" + reduce_text
        user = f"BASELINE:\n```python\n{baseline}\n```\n\nTREE WITH NODE DROPPED:\n{reduced_tree}"

    def _do_call(sys_p, usr_p):
        return call(sys_p, usr_p)

    raw = _do_call(system, user)
    code = _extract_python(raw)

    if code is None:
        retry_user = user + "\n\nYour previous response contained no fenced python block. Please respond with a fenced python block."
        raw2 = _do_call(system, retry_user)
        code = _extract_python(raw2)
        if code is None:
            retry_user2 = retry_user + "\n\nStill no fenced python block found. You must include a ```python ... ``` block."
            raw3 = _do_call(system, retry_user2)
            code = _extract_python(raw3)
            if code is None:
                raise Malformed("generate: no fenced python block in model response after 3 attempts")

    try:
        ast.parse(code)
    except SyntaxError as e:
        err_msg = str(e)
        retry_user = user + f"\n\nYour previous response had a SyntaxError: {err_msg}\nPlease fix it."
        raw2 = _do_call(system, retry_user)
        code = _extract_python(raw2)
        if code is None:
            raise Malformed(f"generate: no fenced python block after syntax error retry")
        try:
            ast.parse(code)
        except SyntaxError as e2:
            err_msg2 = str(e2)
            retry_user2 = retry_user + f"\n\nStill a SyntaxError: {err_msg2}\nPlease fix it."
            raw3 = _do_call(system, retry_user2)
            code = _extract_python(raw3)
            if code is None:
                raise Malformed(f"generate: no fenced python block after second syntax error retry")
            try:
                ast.parse(code)
            except SyntaxError as e3:
                raise Malformed(f"generate: unparseable python after 3 attempts: {e3}")

    return code


def tally(code: str) -> Counter:
    lines = code.splitlines()
    result = Counter()
    for line in lines:
        rstripped = line.rstrip()
        if rstripped:
            result[rstripped] += 1
    return result


def caused_by(root: Node, node: Node, baseline: str):
    def _regen():
        return generate(root, node, baseline)

    key = serialize(root) + "|||" + node.path + "|||" + baseline
    regenerated = cached("code", key, _regen)

    baseline_tally = tally(baseline)
    regen_tally = tally(regenerated)

    lost = baseline_tally - regen_tally
    invented = regen_tally - baseline_tally

    return lost, invented


def project(code: str, caused: dict):
    build_tally = tally(code)
    lines = code.splitlines()

    line_paths = {}
    line_ambiguous = {}

    for lineno, line in enumerate(lines, 1):
        rstripped = line.rstrip()
        if not rstripped:
            continue

        build_count = build_tally[rstripped]
        claimants = []

        for path, lost_counter in caused.items():
            if lost_counter[rstripped] >= build_count:
                claimants.append(path)

        if claimants:
            line_paths[str(lineno)] = sorted(claimants)
        else:
            partial_claimants = [path for path, lost_counter in caused.items() if lost_counter[rstripped] > 0]
            if partial_claimants:
                line_ambiguous[str(lineno)] = sorted(partial_claimants)

    return line_paths, line_ambiguous


def propose(node: Node) -> dict:
    system = lang_text("lower")
    ancestors = node.ancestors()
    siblings = []
    parent = node.parent()
    if parent is not None:
        for child in parent.children():
            if child.path != node.path:
                siblings.append(child)

    ancestor_text = "\n".join(f"[{a.path}] {a.intent()}" for a in ancestors)
    sibling_text = "\n".join(f"[{s.path}] {s.intent()}" for s in siblings)
    node_text = f"[{node.path}] {node.intent()}"

    user = f"NODE:\n{node_text}"
    if ancestor_text:
        user = f"ANCESTORS:\n{ancestor_text}\n\n" + user
    if sibling_text:
        user = user + f"\n\nSETTLED SIBLINGS:\n{sibling_text}"

    key = user
    result = cached("lower", key, lambda: call_json(system, user))
    return result


def lower(node: Node):
    node_dir = ROOT / node.path
    created_files = []

    try:
        proposal = propose(node)

        if proposal.get("leaf"):
            return 0, 0

        children_texts = proposal.get("children", [])
        if not children_texts:
            return 0, 0

        num_proposed = len(children_texts)

        node_dir.mkdir(parents=True, exist_ok=True)

        temp_nodes = []
        for i, text in enumerate(children_texts, 1):
            child_path = node.path + "/" + str(i)
            child_file = ROOT / (child_path + ".human")
            child_file.write_text(text, encoding="utf-8")
            created_files.append(child_file)
            temp_nodes.append(Node(child_path))

        root_node = Node(node.program())
        baseline_code = generate(root_node)

        survivors = []
        for child in temp_nodes:
            lost, _ = caused_by(root_node, child, baseline_code)
            if lost:
                survivors.append(child)
            else:
                child.file().unlink(missing_ok=True)
                created_files.remove(child.file()) if child.file() in created_files else None

        for i, survivor in enumerate(survivors, 1):
            old_path = survivor.path
            new_path = node.path + "/" + str(i)
            if old_path != new_path:
                old_file = ROOT / (old_path + ".human")
                new_file = ROOT / (new_path + ".human")
                if old_file.exists():
                    old_file.rename(new_file)
                    if old_file in created_files:
                        created_files.remove(old_file)
                    created_files.append(new_file)

        return num_proposed, len(survivors)

    except Exception:
        for f in created_files:
            if Path(f).exists():
                Path(f).unlink(missing_ok=True)
        if node_dir.exists() and not any(node_dir.iterdir()):
            node_dir.rmdir()
        raise


def build(root: Node):
    prog_name = root.name()
    out_dir = BUILD / prog_name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "main.py"

    key = serialize(root)
    code = cached("code", key, lambda: generate(root))

    provenance_file = out_dir / "provenance.json"
    if provenance_file.exists():
        try:
            existing = json.loads(provenance_file.read_text(encoding="utf-8"))
            if existing.get("tree") != key:
                provenance_file.unlink()
        except Exception:
            provenance_file.unlink(missing_ok=True)

    out_file.write_text(code, encoding="utf-8")
    return out_file, code


def raises(exc, fn, *args) -> bool:
    try:
        fn(*args)
        return False
    except exc:
        return True
    except Exception:
        return False


if __name__ == "__main__":
    pass