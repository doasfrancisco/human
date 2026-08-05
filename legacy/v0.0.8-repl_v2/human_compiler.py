from __future__ import annotations

import ast
import hashlib
import json
import os
import re
from collections import Counter
from pathlib import Path

import boto3
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
LANG, PROGS, CACHE, BUILD = ROOT / "lang", ROOT / "progs", ROOT / ".cache", ROOT / "build"
for _env in (ROOT / ".env", ROOT.parent / ".env", ROOT.parent / "web_editor" / "project" / "backend" / ".env"):
    if _env.exists():
        load_dotenv(_env)
REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-6")

class Malformed(Exception):
    pass

class Node:
    def __init__(self, path: str):
        self.path = path
    def file(self) -> Path:
        return ROOT / (self.path + ".human")
    def dir(self) -> Path:
        return ROOT / self.path
    def name(self) -> str:
        return self.path.rsplit("/", 1)[-1]
    def level(self) -> int:
        return self.path.count("/") - 1
    def program(self) -> "Node":
        return Node("/".join(self.path.split("/")[:2]))
    def parent(self) -> "Node | None":
        return None if self.path.count("/") <= 1 else Node(self.path.rsplit("/", 1)[0])
    def text(self) -> str:
        return self.file().read_text(encoding="utf-8").strip() if self.file().exists() else ""
    def intent(self) -> str:
        return re.sub(r"^assert:\s*.+$", "", self.text(), flags=re.M).strip()
    def assertions(self) -> list[str]:
        return [m.group(1).strip() for m in re.finditer(r"^assert:\s*(.+)$", self.text(), re.M)]
    def write(self, text: str) -> None:
        self.file().parent.mkdir(parents=True, exist_ok=True)
        self.file().write_text(text.strip() + "\n", encoding="utf-8")
    def children(self) -> list["Node"]:
        kids = [Node(f"{self.path}/{f.stem}") for f in self.dir().glob("*.human")] if self.dir().is_dir() else []
        return sorted(kids, key=lambda n: (not n.name().isdigit(), int(n.name()) if n.name().isdigit() else 0))
    def ancestors(self) -> list["Node"]:
        chain, cur = [], self.parent()
        while cur is not None:
            chain.append(cur)
            cur = cur.parent()
        return chain[::-1]
    def subtree(self) -> list["Node"]:
        return [self] + [d for c in self.children() for d in c.subtree()]

EXPAND_SYSTEM = """You are the lowering stage of human, a language whose source is human text.

You are given the language, the ancestors that explain why this node exists, the children it
already has, and the node to expand. Expand it one level toward code, obeying the language
exactly. Do not write code. Write the next level of human text.

Return {"leaf": true} if expanding would only restate the node.
Otherwise return {"children": ["...", "..."]}."""

CODE_SYSTEM = """You are the code generation stage of human, a language whose source is human text.

You are given the language and the entire program: every node, indented by depth. Emit the whole
program as ONE python module, in ONE answer. There is one namespace and you are its only author.
Standard library only.

Return the module as a single fenced python block. No prose, no JSON."""

REDUCE_SYSTEM = """You are the code generation stage of human, a language whose source is human text.

One node has been deleted. You are given the baseline code as it stood before the deletion, and the
tree as it stands after it. Emit the program the remaining tree implies.

The deleted node is gone, and the code it caused goes with it. Keep a baseline line only if a node
that still exists still implies it. Never keep a line because it is in the baseline: the baseline is
what you are correcting.

Make the smallest change the deletion forces. Every line the remaining tree still implies must
survive byte for byte - do not restyle, rename, resign, reorder, or rewrite anything the deletion
did not force you to touch.

Return the module as a single fenced python block. No prose, no JSON."""

SYSTEM = {"expand": EXPAND_SYSTEM, "code": CODE_SYSTEM, "reduce": REDUCE_SYSTEM}
SCOPES = {"expand": ("lower",), "code": ("code",), "reduce": ("code", "reduce")}
FENCE = re.compile(r"(?ms)^[ \t]*```(?:python)?[ \t]*\n(.*?)^[ \t]*```[ \t]*$")

def lang_text(kind: str) -> str:
    return "\n\n".join(
        f"### lang/{scope}/{f.stem}\n{f.read_text(encoding='utf-8').strip()}"
        for scope in SCOPES[kind]
        for f in (sorted((LANG / scope).glob("*.human")) if (LANG / scope).is_dir() else [])
    )

def cached(kind: str, key: list[str], fn):
    seed = [kind, MODEL_ID, lang_text(kind), SYSTEM[kind], *key]
    f = CACHE / f"{hashlib.sha256(chr(31).join(seed).encode()).hexdigest()}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    value = fn()
    CACHE.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(value, indent=2), encoding="utf-8")
    return value

def call(system: str, user: str, max_tokens: int = 4096) -> str:
    r = boto3.client(service_name="bedrock-runtime", region_name=REGION).converse(
        modelId=MODEL_ID,
        system=[{"text": system}],
        messages=[{"role": "user", "content": [{"text": user}]}],
        inferenceConfig={"temperature": 0, "maxTokens": max_tokens},
    )
    return r["output"]["message"]["content"][0]["text"]

def call_json(system: str, user: str) -> dict:
    nudge = ""
    for _ in range(2):
        raw = call(system + "\n\nRespond with one JSON object and nothing else." + nudge, user)
        m = re.search(r"\{.*\}", raw, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        nudge = "\n\nYour previous reply was not one parseable JSON object. Emit the object alone."
    raise Malformed("expand did not return JSON")

def serialize(root: Node, drop: str | None = None) -> str:
    return "\n".join(
        f"{'  ' * (n.level() - root.level())}[{n.path}] {n.intent()}"
        for n in root.subtree()
        if not (drop and (n.path == drop or n.path.startswith(drop + "/")))
    )

def generate(root: Node, drop: Node | None = None, baseline: str | None = None) -> str:
    kind = "reduce" if drop else "code"
    tree = serialize(root, drop.path if drop else None)
    user = f"# The language\n{lang_text(kind)}\n\n"
    if drop:
        user += f"# The baseline code (the program before the deletion)\n```python\n{baseline}\n```\n\n"
    user += f"# The tree after the deletion\n{tree}" if drop else f"# The program\n{tree}"

    def run() -> dict:
        prompt = user
        for _ in range(3):
            blocks = FENCE.findall(call(SYSTEM[kind], prompt, 8192))
            code = (blocks[-1] if blocks else "").strip()
            try:
                ast.parse(code)
                if code:
                    return {"code": code}
                said = "the answer carried no fenced python block at all"
            except SyntaxError as exc:
                said = f"line {exc.lineno}: {exc.msg}"
            prompt = (f"{user}\n\n# Your previous answer is not valid python\n```python\n{code}\n```\n\n"
                      f"# The parser said\n{said}\n\n"
                      "Fix that error. Return the whole corrected program as one fenced python block.")
        raise Malformed(f"{root.path}{' minus ' + drop.path if drop else ''}: no parseable python after 2 repairs")

    return cached(kind, [tree] + ([baseline] if drop else []), run)["code"]

def tally(code: str) -> Counter:
    return Counter(l.rstrip() for l in code.splitlines() if l.strip())

def caused_by(root: Node, node: Node, baseline: str) -> tuple[Counter, Counter]:
    before, after = tally(baseline), tally(generate(root, node, baseline))
    return before - after, after - before

def project(code: str, caused: dict[str, Counter]) -> tuple[dict, dict]:
    occ = tally(code)
    owners, ambiguous = {}, {}
    for i, line in enumerate(code.splitlines(), 1):
        if not line.strip():
            continue
        t = line.rstrip()
        owners[str(i)] = sorted(p for p, c in caused.items() if c[t] >= occ[t])
        some = sorted(p for p, c in caused.items() if 0 < c[t] < occ[t])
        if some and not owners[str(i)]:
            ambiguous[str(i)] = some
    return owners, ambiguous

def propose(node: Node) -> list[str]:
    anc = "\n".join(f"[level {a.level()}] {a.intent()}" for a in node.ancestors()) or "(none, this is the root)"
    kids = "\n".join(f"- {c.intent()}" for c in node.children()) or "(none)"
    user = (f"# The language\n{lang_text('expand')}\n\n# Ancestors (why this node exists)\n{anc}\n\n"
            f"# Children it already has (do not restate them)\n{kids}\n\n"
            f"# Node to expand (level {node.level()})\n{node.intent()}")
    out = cached("expand", [node.intent(), anc, kids], lambda: call_json(EXPAND_SYSTEM, user))
    if out.get("leaf"):
        return []
    return [c.strip() for c in out.get("children", []) if isinstance(c, str) and c.strip()]

def lower(node: Node) -> tuple[int, list[Node]]:
    texts = propose(node)
    if not texts:
        return 0, []
    start = len(node.children()) + 1
    node.dir().mkdir(parents=True, exist_ok=True)
    cands: list[Node] = []
    try:
        for i, text in enumerate(texts, start):
            cands.append(Node(f"{node.path}/{i}"))
            cands[-1].write(text)
        root = node.program()
        baseline = generate(root)
        keep = [c for c in cands if sum(caused_by(root, c, baseline)[0].values())]
    except BaseException:
        for c in cands:
            c.file().unlink(missing_ok=True)
        raise
    for c in cands:
        if c not in keep:
            c.file().unlink()
    survivors = []
    for i, c in enumerate(keep, start):
        target = Node(f"{node.path}/{i}")
        if target.path != c.path:
            c.file().rename(target.file())
        survivors.append(target)
    return len(cands), survivors

def build(root: Node) -> tuple[Path, str]:
    code = generate(root)
    d = BUILD / root.name()
    d.mkdir(parents=True, exist_ok=True)
    py, m = d / "main.py", d / "main.map.json"
    if m.exists() and (not py.exists() or py.read_text(encoding="utf-8") != code):
        m.unlink()
    py.write_text(code, encoding="utf-8")
    return py, code

def raises(exc, fn, *a, **kw) -> bool:
    try:
        fn(*a, **kw)
    except exc:
        return True
    except Exception:
        return False
    return False
