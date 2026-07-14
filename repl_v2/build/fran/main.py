import os
import sys
import json
import re
import ast
import shutil
import hashlib
import boto3
from pathlib import Path
from collections import Counter
from dotenv import load_dotenv

ROOT = Path(__file__).parent.resolve()
LANG = ROOT / "lang"
PROGS = ROOT / "progs"
CACHE = ROOT / "cache"
BUILD = ROOT / "build"

_env_path = ROOT / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

MODEL_ID = os.environ.get("MODEL_ID", "anthropic.claude-opus-4-5")


class Malformed(Exception):
    pass


class Node:
    def __init__(self, path):
        if isinstance(path, Path):
            path = str(path)
        self._path = path.strip("/")

    def __repr__(self):
        return f"Node({self._path!r})"

    def __eq__(self, other):
        return isinstance(other, Node) and self._path == other._path

    def __hash__(self):
        return hash(self._path)

    def path(self):
        return self._path

    def file(self):
        return ROOT / (self._path + ".human")

    def name(self):
        return self._path.split("/")[-1]

    def level(self):
        parts = self._path.split("/")
        return len(parts) - 2

    def parent(self):
        parts = self._path.split("/")
        if len(parts) <= 2:
            return None
        return Node("/".join(parts[:-1]))

    def program(self):
        parts = self._path.split("/")
        return "/".join(parts[:2])

    def ancestors(self):
        parts = self._path.split("/")
        result = []
        for i in range(2, len(parts)):
            result.append(Node("/".join(parts[:i])))
        return result

    def children(self):
        dir_path = ROOT / self._path
        if not dir_path.exists() or not dir_path.is_dir():
            return []
        kids = []
        for f in dir_path.iterdir():
            if f.suffix == ".human":
                stem = f.stem
                try:
                    int(stem)
                    kids.append((int(stem), Node(self._path + "/" + stem)))
                except ValueError:
                    pass
        kids.sort(key=lambda x: x[0])
        return [n for _, n in kids]

    def subtree(self):
        result = [self]
        for child in self.children():
            result.extend(child.subtree())
        return result

    def text(self):
        f = self.file()
        if f.exists():
            return f.read_text(encoding="utf-8").strip()
        return ""

    def intent(self):
        t = self.text()
        lines = t.splitlines()
        non_assert = [l for l in lines if not l.startswith("assert:")]
        return "\n".join(non_assert).strip()

    def assertions(self):
        t = self.text()
        lines = t.splitlines()
        return [l[len("assert:"):].strip() for l in lines if l.startswith("assert:")]


def _read_lang(folder):
    p = LANG / folder
    if not p.exists():
        return ""
    parts = []
    for f in sorted(p.iterdir()):
        if f.is_file():
            parts.append(f.read_text(encoding="utf-8").strip())
    return "\n\n".join(parts)


def call(system, user):
    region = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
    client = boto3.client(
        "bedrock-runtime",
        region_name=region,
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        aws_session_token=os.environ.get("AWS_SESSION_TOKEN"),
    )
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 8192,
        "temperature": 0,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    response = client.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps(body),
        contentType="application/json",
        accept="application/json",
    )
    result = json.loads(response["body"].read())
    return result["content"][0]["text"]


def call_json(system, user):
    def _try(sys_prompt, usr_prompt):
        text = call(sys_prompt, usr_prompt)
        try:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            return json.loads(text)
        except json.JSONDecodeError as e:
            return None, str(e)

    result = _try(system, user)
    if isinstance(result, tuple) and result[0] is None:
        sharper = system + "\n\nYou MUST respond with valid JSON only, no other text."
        result = _try(sharper, user)
        if isinstance(result, tuple) and result[0] is None:
            raise Malformed(f"Model did not return valid JSON: {result[1]}")
    return result


def cached(kind, key, fn):
    CACHE.mkdir(parents=True, exist_ok=True)
    lang_folder = LANG / kind
    lang_content = ""
    if lang_folder.exists():
        parts = []
        for f in sorted(lang_folder.iterdir()):
            if f.is_file():
                parts.append(f.read_text(encoding="utf-8").strip())
        lang_content = "\n\n".join(parts)

    system_prompt = _get_system_prompt(kind)

    hash_input = kind + MODEL_ID + lang_content + system_prompt + key
    h = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()
    cache_file = CACHE / (h + ".json")
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))
    result = fn()
    cache_file.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return result


def _get_system_prompt(kind):
    if kind == "code":
        return _read_lang("code")
    elif kind == "reduce":
        return _read_lang("code") + "\n\n" + _read_lang("reduce")
    elif kind == "lower":
        return _read_lang("lower")
    return ""


def serialize(root, drop=None):
    drop_node = Node(drop) if drop and isinstance(drop, str) else drop
    drop_path = drop_node.path() if drop_node else None

    def _should_drop(node):
        if drop_path is None:
            return False
        p = node.path()
        return p == drop_path or p.startswith(drop_path + "/")

    lines = []
    root_level = root.level()

    def _walk(node):
        if _should_drop(node):
            return
        indent = "  " * (node.level() - root_level)
        lines.append(f"{indent}{node.path()} {node.intent()}")
        for child in node.children():
            _walk(child)

    _walk(root)
    return "\n".join(lines)


def _extract_python(text):
    lines = text.splitlines()
    blocks = []
    in_block = False
    current = []
    for line in lines:
        if line.strip() == "```python" and not in_block:
            in_block = True
            current = []
        elif line.strip() == "```" and in_block:
            in_block = False
            blocks.append("\n".join(current))
        elif in_block:
            current.append(line)
    if not blocks:
        return None
    return blocks[-1]


def _parse_check(code, response_text, system, user, attempt=0):
    try:
        ast.parse(code)
        return code
    except SyntaxError as e:
        if attempt >= 2:
            raise Malformed(f"Model returned unparseable Python after retries: {e}")
        new_user = user + f"\n\nThe previous answer had a syntax error: {e}\nPlease fix it."
        new_response = call(system, new_user)
        new_code = _extract_python(new_response)
        if new_code is None:
            raise Malformed("Model returned no Python block after retry")
        return _parse_check(new_code, new_response, system, new_user, attempt + 1)


def generate(root, node=None, baseline=None):
    lang_code = _read_lang("code")

    if node is None:
        kind = "code"
        system = lang_code
        tree_text = serialize(root)
        user = tree_text

        def fn():
            response = call(system, user)
            code = _extract_python(response)
            if code is None:
                raise Malformed("Model returned no Python block")
            code = _parse_check(code, response, system, user)
            return code

        return cached(kind, user, fn)
    else:
        lang_reduce = _read_lang("reduce")
        kind = "reduce"
        system = lang_code + "\n\n" + lang_reduce
        tree_text = serialize(root, drop=node)
        user = tree_text + "\n\n# Baseline\n```python\n" + baseline + "\n```"

        def fn():
            response = call(system, user)
            code = _extract_python(response)
            if code is None:
                raise Malformed("Model returned no Python block")
            code = _parse_check(code, response, system, user)
            return code

        return cached(kind, user, fn)


def tally(code):
    lines = code.splitlines()
    result = Counter()
    for line in lines:
        rstripped = line.rstrip()
        if rstripped:
            result[rstripped] += 1
    return result


def caused_by(root, node, baseline):
    baseline_tally = tally(baseline)
    reduced = generate(root, node, baseline)
    reduced_tally = tally(reduced)
    lost = baseline_tally - reduced_tally
    invented = reduced_tally - baseline_tally
    return lost, invented


def project(code, caused):
    build_tally = tally(code)
    lines = code.splitlines()

    claimed = {}
    ambiguous = {}

    for lineno, line in enumerate(lines, 1):
        rstripped = line.rstrip()
        if not rstripped:
            continue
        key = str(lineno)
        build_count = build_tally[rstripped]

        claimants = []
        partial = []
        for path, multiset in caused.items():
            if multiset[rstripped] >= build_count:
                claimants.append(path)
            elif multiset[rstripped] > 0:
                partial.append(path)

        if claimants:
            claimed[key] = sorted(claimants)
        elif partial:
            ambiguous[key] = sorted(partial)

    return claimed, ambiguous


def propose(node):
    lang_lower = _read_lang("lower")
    system = lang_lower

    ancestors = node.ancestors()
    siblings = []
    parent = node.parent()
    if parent is not None:
        for child in parent.children():
            if child.path() != node.path():
                siblings.append(child)

    context_parts = []
    for anc in ancestors:
        context_parts.append(f"{anc.path()}: {anc.intent()}")
    for sib in siblings:
        context_parts.append(f"{sib.path()}: {sib.intent()}")

    context = "\n".join(context_parts)
    node_text = f"{node.path()}: {node.intent()}"
    user = context + "\n\n" + node_text if context else node_text

    def fn():
        return call_json(system, user)

    result = cached("lower", user, fn)
    return result


def lower(node):
    result = propose(node)

    if result == "leaf" or result == {"type": "leaf"} or (isinstance(result, dict) and result.get("type") == "leaf"):
        return 0, 0

    if isinstance(result, dict) and "children" in result:
        children_texts = result["children"]
    elif isinstance(result, list):
        children_texts = result
    else:
        raise Malformed(f"Unexpected propose result: {result}")

    node_dir = ROOT / node.path()
    created_files = []

    try:
        node_dir.mkdir(parents=True, exist_ok=True)

        proposed_count = len(children_texts)
        child_nodes = []

        for i, text in enumerate(children_texts, 1):
            child_path = node.path() + "/" + str(i)
            child_node = Node(child_path)
            child_file = child_node.file()
            child_file.write_text(text, encoding="utf-8")
            created_files.append(child_file)
            child_nodes.append(child_node)

        baseline_code = generate(Node(node.program()))

        survivors = []
        for child_node in child_nodes:
            lost, _ = caused_by(Node(node.program()), child_node, baseline_code)
            if lost:
                survivors.append(child_node)

        for child_node in child_nodes:
            if child_node not in survivors:
                f = child_node.file()
                if f.exists():
                    f.unlink()
                d = ROOT / child_node.path()
                if d.exists():
                    shutil.rmtree(d)

        for i, survivor in enumerate(survivors, 1):
            old_path = survivor.path()
            new_path = node.path() + "/" + str(i)
            if old_path != new_path:
                old_file = ROOT / (old_path + ".human")
                new_file = ROOT / (new_path + ".human")
                if old_file.exists():
                    old_file.rename(new_file)
                old_dir = ROOT / old_path
                new_dir = ROOT / new_path
                if old_dir.exists():
                    old_dir.rename(new_dir)

        return proposed_count, len(survivors)

    except Exception:
        for f in created_files:
            if f.exists():
                f.unlink()
        if node_dir.exists() and not any(node_dir.iterdir()):
            node_dir.rmdir()
        raise


def build(root):
    code = generate(root)
    name = root.name()
    build_dir = BUILD / name
    build_dir.mkdir(parents=True, exist_ok=True)
    out_path = build_dir / "main.py"
    out_path.write_text(code, encoding="utf-8")

    prov_path = build_dir / "provenance.json"
    if prov_path.exists():
        try:
            existing = json.loads(prov_path.read_text(encoding="utf-8"))
            if existing.get("build_hash") != hashlib.sha256(code.encode()).hexdigest():
                prov_path.unlink()
        except Exception:
            prov_path.unlink()

    return out_path, code


def raises(exc, fn, *args):
    try:
        fn(*args)
        return False
    except exc:
        return True
    except Exception:
        return False


if __name__ == "__main__":
    pass