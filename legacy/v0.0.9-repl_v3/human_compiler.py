from __future__ import annotations

import ast
import hashlib
import json
import os
import re
from pathlib import Path

import boto3
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
LANG, PROGS, CACHE, BUILD = ROOT / "lang", ROOT / "progs", ROOT / ".cache", ROOT / "build"
for _env in (ROOT / ".env", ROOT.parent / ".env"):
    if _env.exists():
        load_dotenv(_env)
REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-6")

class Malformed(Exception):
    pass

ID_LINE = re.compile(r"^@id:\s*([0-9a-f]+)\s*$", re.M)

class Node:
    def __init__(self, path: str):
        self.path = path
    def __eq__(self, other):
        return isinstance(other, Node) and other.path == self.path
    def __hash__(self):
        return hash(self.path)
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
    def raw(self) -> str:
        return self.file().read_text(encoding="utf-8") if self.file().exists() else ""
    def text(self) -> str:
        return ID_LINE.sub("", self.raw()).strip()
    def intent(self) -> str:
        return re.sub(r"^assert:\s*.+$", "", self.text(), flags=re.M).strip()
    def assertions(self) -> list[str]:
        return [m.group(1).strip() for m in re.finditer(r"^assert:\s*(.+)$", self.text(), re.M)]
    def nid(self) -> str:
        m = ID_LINE.search(self.raw())
        if m:
            return m.group(1)
        new = hashlib.sha256((self.path + self.text()).encode()).hexdigest()[:8]
        self.file().parent.mkdir(parents=True, exist_ok=True)
        self.file().write_text(f"@id: {new}\n{self.text()}\n", encoding="utf-8")
        return new
    def write(self, text: str) -> None:
        self.file().parent.mkdir(parents=True, exist_ok=True)
        m = ID_LINE.search(self.raw())
        head = f"@id: {m.group(1)}\n" if m else ""
        self.file().write_text(f"{head}{text.strip()}\n", encoding="utf-8")
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

You are given the language and the entire program: every node with its path, indented by depth.
Emit the whole program as ONE python module. There is one namespace and you are its only author.
Standard library only.

Declare, in the same answer, which node caused which characters of the code. Return one JSON object:

{"code": "<the whole module as a string>",
 "map": [{"node": "<path>", "kind": "specified" | "assumed", "ranges": [[start, end], ...]}, ...]}

A range is a pair of character offsets into code: code[start:end] is a region that node owns. Ranges
may overlap and need not be contiguous; a node may own scattered regions and a region may belong to
more than one node. kind is "specified" when the region traces to a sentence in the tree, "assumed"
when you filled a gap with a convention no node stated.

If the program is underspecified, build it anyway: choose a conventional default, write the code, and
tag the region you invented "assumed". Never refuse to build. Return the JSON object and nothing else."""

REVISE_SYSTEM = """You are the code generation stage of human, a language whose source is human text.

One node's meaning changed. You are given the baseline code as it stood before the edit and the tree
as it stands after it. Emit the program the edited tree now implies, as the smallest change to the
baseline the edit forces. Every line the edited tree still implies survives byte for byte: do not
rename, re-sign, reorder, restyle, or improve anything the edit did not force you to touch.

Return the same JSON object as the code stage: {"code": ..., "map": [...]} with the declared
node->character map over the code you return, specified and assumed tagged."""

FOLD_SYSTEM = """You are the folding stage of human, a language whose source is human text.

You are given a node and its children. Return one sentence, in the imperative, that summarizes the
node together with what its children decide - the sentence you would view and edit this idea at one
level higher. Return {"sentence": "..."}."""

EQUIV_SYSTEM = """You are the edit classifier of human, a language whose source is human text.

You are given two renderings of one idea: the wording the current build was compiled from, and a new
wording. Decide whether they mean the same thing for the code they imply - whether a compiler would
emit the same program from each. Return {"equivalent": true} or {"equivalent": false}."""

SYSTEM = {"expand": EXPAND_SYSTEM, "code": CODE_SYSTEM, "revise": REVISE_SYSTEM,
          "fold": FOLD_SYSTEM, "equiv": EQUIV_SYSTEM}
SCOPES = {"expand": ("lower",), "code": ("code",), "revise": ("code", "revise"), "fold": (), "equiv": ()}

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
    raise Malformed("the model did not return one JSON object")

def clamp(mp, code: str) -> list[dict]:
    n, out = len(code), []
    for e in mp if isinstance(mp, list) else []:
        if not isinstance(e, dict) or not isinstance(e.get("node"), str):
            continue
        ranges = []
        for r in e.get("ranges") or []:
            if isinstance(r, list) and len(r) == 2 and all(isinstance(x, int) for x in r):
                a, b = max(0, min(r[0], n)), max(0, min(r[1], n))
                if a <= b:
                    ranges.append([a, b])
        out.append({"node": e["node"], "kind": "assumed" if e.get("kind") == "assumed" else "specified",
                    "ranges": ranges})
    return out

def code_call(kind: str, user: str) -> dict:
    prompt = user
    for _ in range(3):
        raw = call(SYSTEM[kind] + "\n\nRespond with one JSON object and nothing else.", prompt, 8192)
        m = re.search(r"\{.*\}", raw, re.S)
        obj = None
        if m:
            try:
                obj = json.loads(m.group(0))
            except json.JSONDecodeError:
                obj = None
        code = obj.get("code", "") if isinstance(obj, dict) else ""
        if isinstance(code, str) and code.strip():
            try:
                ast.parse(code)
                return {"code": code, "map": clamp(obj.get("map", []), code)}
            except SyntaxError as exc:
                said = f"line {exc.lineno}: {exc.msg}"
        else:
            said = "the reply was not one JSON object carrying a non-empty 'code' string"
        prompt = (f"{user}\n\n# Your previous answer was rejected\n{said}\n\n"
                  "Return one JSON object {\"code\": ..., \"map\": [...]} whose code is a valid python module.")
    raise Malformed(f"{kind}: no parseable module after 2 repairs")

def serialize(root: Node) -> str:
    return "\n".join(f"{'  ' * (n.level() - root.level())}[{n.path}] {n.intent()}" for n in root.subtree())

def generate(root: Node, baseline: str | None = None) -> dict:
    kind = "revise" if baseline is not None else "code"
    tree = serialize(root)
    user = f"# The language\n{lang_text(kind)}\n\n"
    if baseline is not None:
        user += f"# The baseline code (before the edit)\n```python\n{baseline}\n```\n\n"
    user += f"# The program\n{tree}"
    key = [tree] + ([baseline] if baseline is not None else [])
    return cached(kind, key, lambda: code_call(kind, user))

def build(root: Node, baseline: str | None = None) -> tuple[Path, str, list[dict]]:
    result = generate(root, baseline)
    code = result["code"]
    d = BUILD / root.name()
    d.mkdir(parents=True, exist_ok=True)
    py = d / "main.py"
    py.write_text(code, encoding="utf-8")
    renderings = {n.path: n.intent() for n in root.subtree()}
    (d / "main.map.json").write_text(
        json.dumps({"map": result["map"], "renderings": renderings}, indent=2), encoding="utf-8")
    return py, code, result["map"]

def compiled_rendering(node: Node) -> str | None:
    m = BUILD / node.program().name() / "main.map.json"
    if not m.exists():
        return None
    return json.loads(m.read_text(encoding="utf-8")).get("renderings", {}).get(node.path)

def equivalent(old: str, new: str) -> bool:
    if old.strip() == new.strip():
        return True
    user = f"# Wording the build was compiled from\n{old}\n\n# New wording\n{new}"
    return bool(cached("equiv", [old, new], lambda: call_json(EQUIV_SYSTEM, user)).get("equivalent"))

def revise(node: Node, new_text: str) -> tuple[Path, str, list[dict]]:
    root = node.program()
    baseline = (BUILD / root.name() / "main.py").read_text(encoding="utf-8")
    node.write(new_text)
    return build(root, baseline)

def owns(root: Node, node_path: str) -> list[dict] | None:
    m = BUILD / root.name() / "main.map.json"
    if not m.exists():
        return None
    return [e for e in json.loads(m.read_text(encoding="utf-8"))["map"] if e["node"] == node_path]

def decorative(root: Node) -> list[str]:
    m = BUILD / root.name() / "main.map.json"
    if not m.exists():
        return []
    owned = {e["node"] for e in json.loads(m.read_text(encoding="utf-8"))["map"]
             if e["kind"] == "specified" and e["ranges"]}
    return [n.path for n in root.subtree() if n.path != root.path and n.path not in owned]

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
    made = []
    for i, text in enumerate(texts, start):
        child = Node(f"{node.path}/{i}")
        child.write(text)
        made.append(child)
    return len(texts), made

def fold(node: Node) -> str:
    kids = "\n".join(f"- {c.intent()}" for c in node.children()) or "(none)"
    user = f"# The node\n{node.intent()}\n\n# Its children\n{kids}"
    return cached("fold", [node.intent(), kids], lambda: call_json(FOLD_SYSTEM, user)).get("sentence", "").strip()

def check(root: Node) -> tuple[list[tuple], str, list[dict]]:
    py, code, cmap = build(root)
    ns = {"__name__": "human_check", "__file__": str(py), "raises": raises}
    exec(compile(code, str(py), "exec"), ns)
    results = []
    for n in root.subtree():
        for a in n.assertions():
            try:
                ok, err = bool(eval(a, ns)), ""
            except Exception as exc:
                ok, err = False, str(exc)
            results.append((n, a, ok, err))
    return results, code, cmap

def raises(exc, fn, *a, **kw) -> bool:
    try:
        fn(*a, **kw)
    except exc:
        return True
    except Exception:
        return False
    return False
