from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

import boto3
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
LANG = ROOT / "lang"
PROGS = ROOT / "progs"
CACHE = ROOT / ".cache"
BUILD = ROOT / "build"

for _env in (ROOT / ".env", ROOT.parent / ".env", ROOT.parent / "web_editor" / "project" / "backend" / ".env"):
    if _env.exists():
        load_dotenv(_env)

REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-6")
TWIG = "\\_ "


class Node:
    def __init__(self, path: str):
        self.path = path

    @property
    def file(self) -> Path:
        return ROOT / (self.path + ".human")

    @property
    def dir(self) -> Path:
        return ROOT / self.path

    @property
    def name(self) -> str:
        return self.path.rsplit("/", 1)[-1]

    @property
    def text(self) -> str:
        return self.file.read_text(encoding="utf-8").strip() if self.file.exists() else ""

    def write(self, text: str) -> None:
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.file.write_text(text.strip() + "\n", encoding="utf-8")

    @property
    def parent(self) -> "Node | None":
        if self.path.count("/") <= 1:
            return None
        return Node(self.path.rsplit("/", 1)[0])

    @property
    def is_lang(self) -> bool:
        return self.path.startswith("lang/")

    @property
    def program(self) -> "Node":
        parts = self.path.split("/")
        return Node("/".join(parts[:2]))

    @property
    def level(self) -> int:
        return self.path.count("/") - 1

    def children(self) -> list["Node"]:
        if not self.dir.is_dir():
            return []
        kids = []
        for f in self.dir.glob("*.human"):
            kids.append(Node(f"{self.path}/{f.stem}"))
        return sorted(kids, key=lambda n: (not n.name.isdigit(), int(n.name) if n.name.isdigit() else 0, n.name))

    def ancestors(self) -> list["Node"]:
        chain, cur = [], self.parent
        while cur is not None:
            chain.append(cur)
            cur = cur.parent
        return list(reversed(chain))

    def siblings(self) -> list["Node"]:
        p = self.parent
        return [] if p is None else [n for n in p.children() if n.path != self.path]

    def subtree(self) -> list["Node"]:
        out = [self]
        for c in self.children():
            out.extend(c.subtree())
        return out

    def assertions(self) -> list[str]:
        return [m.group(1).strip() for m in re.finditer(r"^assert:\s*(.+)$", self.text, re.M)]

    def intent(self) -> str:
        return re.sub(r"^assert:\s*.+$", "", self.text, flags=re.M).strip()


def lang_text() -> str:
    parts = []
    for f in sorted(LANG.glob("*.human")):
        parts.append(f"### lang/{f.stem}\n{f.read_text(encoding='utf-8').strip()}")
    return "\n\n".join(parts)


def lang_hash() -> str:
    return hashlib.sha256(lang_text().encode()).hexdigest()[:16]


def owns(ancestor: str, path: str) -> bool:
    return path == ancestor or path.startswith(ancestor + "/")


def serialize(node: Node, exclude: str | None = None) -> str:
    lines = []
    for n in node.subtree():
        if exclude and owns(exclude, n.path):
            continue
        lines.append(f"{'  ' * (n.level - node.level)}[{n.path}] {n.intent()}")
    return "\n".join(lines)


def stage_hash(kind: str) -> str:
    return hashlib.sha256(STAGE_PROMPTS.get(kind, "").encode()).hexdigest()[:16]


def cache_file(kind: str, key_parts: list[str]) -> Path:
    parts = [kind, MODEL_ID, lang_hash(), stage_hash(kind), *key_parts]
    key = hashlib.sha256("\x1f".join(parts).encode()).hexdigest()
    return CACHE / f"{key}.json"


def cache_probe(kind: str, key_parts: list[str]) -> dict | None:
    f = cache_file(kind, key_parts)
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def cached(kind: str, key_parts: list[str], fn):
    f = cache_file(kind, key_parts)
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8")), True
    value = fn()
    CACHE.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(value, indent=2), encoding="utf-8")
    return value, False


def call(system: str, user: str, max_tokens: int = 4096) -> str:
    client = boto3.client(service_name="bedrock-runtime", region_name=REGION)
    r = client.converse(
        modelId=MODEL_ID,
        system=[{"text": system}],
        messages=[{"role": "user", "content": [{"text": user}]}],
        inferenceConfig={"temperature": 0, "maxTokens": max_tokens},
    )
    return r["output"]["message"]["content"][0]["text"]


def extract_json(raw: str) -> dict | None:
    best = None
    for start in (i for i, ch in enumerate(raw) if ch == "{"):
        depth, in_str, esc = 0, False, False
        for i in range(start, len(raw)):
            ch = raw[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(raw[start : i + 1])
                    except json.JSONDecodeError:
                        break
                    if isinstance(obj, dict) and (best is None or len(raw[start : i + 1]) > best[1]):
                        best = (obj, len(raw[start : i + 1]))
                    break
    return best[0] if best else None


def call_json(system: str, user: str, max_tokens: int = 4096) -> dict:
    system = system + "\n\nRespond with one JSON object and nothing else. Do not wrap it in a code fence."
    last = ""
    for _ in range(2):
        last = call(system, user, max_tokens).strip()
        obj = extract_json(last)
        if obj is not None:
            return obj
    raise RuntimeError(f"model did not return JSON:\n{last[:300]}")


EXPAND_SYSTEM = """You are the lowering stage of fran, a language whose source is human text.

You are given the language definition, the chain of ancestors that explains why a
node exists, the siblings that are already settled, and the node to expand.

Expand the node one level toward code, obeying the language definition exactly.
Do not write code. Write the next level of human text.

Return {"leaf": true} if expanding would only restate the node.
Otherwise return {"children": ["...", "..."]}."""


def propose(node: Node) -> list[str]:
    anc = "\n".join(f"[level {a.level}] {a.intent()}" for a in node.ancestors()) or "(none, this is the root)"
    sib = "\n".join(f"- {s.intent()}" for s in node.siblings()) or "(none)"
    user = (
        f"# The language\n{lang_text()}\n\n"
        f"# Ancestors (why this node exists)\n{anc}\n\n"
        f"# Siblings (already settled, do not restate)\n{sib}\n\n"
        f"# Node to expand (level {node.level})\n{node.intent()}"
    )
    key = [node.intent(), anc, sib, str(node.level)]
    result, _ = cached("expand", key, lambda: call_json(EXPAND_SYSTEM, user))
    if result.get("leaf"):
        return []
    return [c.strip() for c in result.get("children", []) if c.strip()]


CONTRACT_SYSTEM = """You are the contract stage of fran, a language whose source is human text.

You are given the language definition, the program root, and its units - the level-1 nodes,
in order. You do not see what is beneath them, and neither will they see each other.

The units are compiled independently. Write the contract they must all obey so that their
code fits together: the shared data representation, and the exact public signature of every
function or class. Assign each public name to exactly ONE owning unit, and identify that
unit by quoting its text verbatim. Every other unit may only call it.

Every unit must own at least one name. A unit that owns nothing cannot be compiled, because
its only way to speak would be to redefine a name another unit owns, and that is a failed
compile. If a unit's decision would otherwise live inside a function another unit owns, give
that unit its own helper function - name it, give its exact signature - and require the
owning unit to call it at the point the decision applies.

Every unit is concatenated into ONE Python module. A unit never imports a name another unit
owns - it calls that name directly, as a module-level name that is already there.

Be short and prescriptive. This is a specification the units obey, not prose. Name exact
identifiers, exact parameter names, exact return values, exact dict keys.

Return {"contract": "<the contract, as plain text>"}."""


def contract_key(root: Node) -> list[str]:
    return [root.intent(), *[u.intent() for u in root.children()]]


def contract(root: Node) -> str:
    units = root.children()
    if not units:
        return ""
    listing = "\n\n".join(f"## unit {i}\n{u.intent()}" for i, u in enumerate(units, 1))
    user = (
        f"# The language\n{lang_text()}\n\n"
        f"# Program root\n{root.intent()}\n\n"
        f"# The units, in order\n{listing}"
    )
    result, _ = cached("contract", contract_key(root), lambda: call_json(CONTRACT_SYSTEM, user))
    return result.get("contract", "").strip()


CODE_SYSTEM = """You are the code generation stage of fran, a language whose source is human text.

You are given the language definition, the program root, the contract every unit obeys, and
one unit: a node plus the whole subtree of nodes beneath it. Emit Python for that unit only.

Obey the contract exactly. Define only the public names the contract assigns to this unit.
Call the names it assigns to other units - do not define them, and do not redefine them.

Every unit is concatenated into ONE Python module. A name another unit owns is already in
scope: call it directly. Never import it. Import only from the standard library.

Every line must be caused by exactly one node in the subtree, and you must say which.

Return {"code": "<python>", "attribution": {"1": "<node path>", "2": "<node path>", ...}}
where each key is a 1-based line number of your code and each value is the path of the
node that caused it. Blank lines may be omitted from attribution."""


def codegen_serial(root_intent: str, serial: str, spec: str) -> tuple[dict, bool]:
    user = (
        f"# The language\n{lang_text()}\n\n"
        f"# Program root\n{root_intent}\n\n"
        f"# The contract (every unit obeys this)\n{spec}\n\n"
        f"# The unit and its subtree\n{serial}"
    )
    return cached("code", [root_intent, serial, spec], lambda: call_json(CODE_SYSTEM, user, max_tokens=4096))


def codegen(unit: Node) -> tuple[dict, bool]:
    root = unit.program
    return codegen_serial(root.intent(), serialize(unit), contract(root))


REDUCE_SYSTEM = """You are the code generation stage of fran, a language whose source is human text.

You have already emitted code for a unit. One node has now been removed from that unit's
node set. You are not being asked to write the unit again. You are being asked for the
smallest change to the baseline code that the new node set forces.

Emit the code the new node set implies. Preserve every line the new set still implies,
byte for byte. Change only what the removal forces you to change. Do not restyle, do not
rename, do not resign a function, do not reorder, and do not rewrite anything you were not
forced to touch. If the removed node caused no line, the code you return is the baseline
code unchanged.

Return {"code": "<python>"}."""


STAGE_PROMPTS = {
    "expand": EXPAND_SYSTEM,
    "contract": CONTRACT_SYSTEM,
    "code": CODE_SYSTEM,
    "reduce": REDUCE_SYSTEM,
}


def codegen_reduce(root_intent: str, serial: str, baseline: str, spec: str) -> tuple[dict, bool]:
    user = (
        f"# The language\n{lang_text()}\n\n"
        f"# Program root\n{root_intent}\n\n"
        f"# The contract (every unit obeys this)\n{spec}\n\n"
        f"# The baseline code (what the previous node set emitted)\n{baseline}\n\n"
        f"# The new node set (one node was removed)\n{serial}"
    )
    return cached(
        "reduce", [root_intent, serial, baseline, spec], lambda: call_json(REDUCE_SYSTEM, user, max_tokens=4096)
    )


def unit_of(node: Node) -> Node:
    parts = node.path.split("/")
    return Node("/".join(parts[:3])) if len(parts) >= 3 else node


def owner_path(value: str, unit: Node) -> str:
    m = re.search(r"(progs|lang)/[^\s\]\[]+", str(value))
    if m is None:
        return unit.path
    p = m.group(0).rstrip("/")
    return p if Node(p).file.exists() else unit.path


def attribution(result: dict, unit: Node) -> dict[int, str]:
    raw = result.get("attribution", {})
    return {int(k): owner_path(v, unit) for k, v in raw.items() if str(k).isdigit()}


def emitted(result: dict) -> list[str]:
    return [l.strip() for l in result.get("code", "").splitlines() if l.strip()]


def earned(verdict: str) -> bool:
    return verdict in ("caused", "partial")


def lower_earned(node: Node) -> tuple[int, list[Node]]:
    kept = node.children()
    texts = propose(node)
    if not texts:
        return 0, []
    node.dir.mkdir(parents=True, exist_ok=True)
    cands = []
    for i, text in enumerate(texts, len(kept) + 1):
        c = Node(f"{node.path}/{i}")
        c.write(text)
        cands.append(c)
    keepers = []
    for c in cands:
        if earned(ablate(c)["verdict"]):
            keepers.append(c)
        else:
            c.file.unlink()
    survivors = []
    for i, c in enumerate(keepers, len(kept) + 1):
        target = Node(f"{node.path}/{i}")
        if target.path != c.path:
            c.file.rename(target.file)
        survivors.append(target)
    return len(cands), survivors


def ablate(node: Node, probe: bool = False) -> dict | None:
    unit = unit_of(node)
    root = node.program
    if probe and cache_probe("contract", contract_key(root)) is None:
        return None
    spec = contract(root)
    if probe and cache_probe("code", [root.intent(), serialize(unit), spec]) is None:
        return None
    base, _ = codegen(unit)
    baseline = base.get("code", "")

    if node.path == unit.path:
        lines = emitted(base)
        return {
            "verdict": "caused" if lines else "inert",
            "owned": len(lines),
            "survived": 0,
            "collateral": 0,
            "code": "",
        }

    attrib = attribution(base, unit)
    owned, others = [], []
    for i, line in enumerate(baseline.splitlines(), start=1):
        if not line.strip():
            continue
        (owned if owns(node.path, attrib.get(i, unit.path)) else others).append(line.strip())

    serial = serialize(unit, exclude=node.path)
    if probe and cache_probe("reduce", [root.intent(), serial, baseline, spec]) is None:
        return None
    after, _ = codegen_reduce(root.intent(), serial, baseline, spec)
    after_lines = set(emitted(after))

    survived = [l for l in owned if l in after_lines]
    collateral = [l for l in others if l not in after_lines]
    if not owned and not collateral:
        verdict = "inert"
    elif not owned:
        verdict = "unattributed"
    elif not survived:
        verdict = "caused"
    elif len(survived) == len(owned):
        verdict = "DECORATIVE"
    else:
        verdict = "partial"
    return {
        "verdict": verdict,
        "owned": len(owned),
        "survived": len(survived),
        "collateral": len(collateral),
        "code": after.get("code", ""),
    }


class Collision(Exception):
    pass


def top_names(code: str) -> list[str]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    names = []
    for stmt in tree.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append(stmt.name)
        elif isinstance(stmt, ast.Assign):
            names.extend(t.id for t in stmt.targets if isinstance(t, ast.Name))
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            names.append(stmt.target.id)
    return names


def spurious_import(line: str, claimed: dict[str, str]) -> bool:
    try:
        stmt = ast.parse(line.strip()).body[0]
    except (SyntaxError, IndexError):
        return False
    if isinstance(stmt, ast.ImportFrom):
        return bool(stmt.names) and all((a.asname or a.name) in claimed for a in stmt.names)
    if isinstance(stmt, ast.Import):
        return bool(stmt.names) and all((a.asname or a.name.split(".")[0]) in claimed for a in stmt.names)
    return False


def assemble(root: Node) -> tuple[str, list[str]]:
    units = root.children() or [root]
    imports: list[str] = []
    body: list[str] = []
    owners: list[str] = []
    claimed: dict[str, str] = {}
    emitted_units = []
    for unit in units:
        result, _ = codegen(unit)
        code = result.get("code", "")
        for name in top_names(code):
            if name in claimed and claimed[name] != unit.path:
                raise Collision(
                    f"two nodes both define '{name}': {claimed[name]} and {unit.path}. "
                    f"code that two nodes claim cannot explain itself. fix the contract or the nodes."
                )
            claimed[name] = unit.path
        emitted_units.append((unit, code, result))

    for unit, code, result in emitted_units:
        attrib = attribution(result, unit)
        for i, line in enumerate(code.splitlines(), start=1):
            owner = attrib.get(i, unit.path)
            if re.match(r"^(import |from \S+ import )", line):
                if spurious_import(line, claimed):
                    continue
                if line not in imports:
                    imports.append(line)
                continue
            body.append(line)
            owners.append(owner)
        body.append("")
        owners.append(unit.path)

    out_lines: list[str] = []
    out_owners: list[str] = []
    for line in sorted(imports):
        out_lines.append(line)
        out_owners.append(root.path)
    if imports:
        out_lines.append("")
        out_owners.append(root.path)
    while body and not body[0].strip():
        body.pop(0)
        owners.pop(0)
    out_lines.extend(body)
    out_owners.extend(owners)
    return "\n".join(out_lines).rstrip() + "\n", out_owners


def build_dir(root: Node) -> Path:
    return BUILD / root.name


def build(root: Node) -> tuple[Path, list[str]]:
    code, owners = assemble(root)
    d = build_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    py = d / "main.py"
    py.write_text(code, encoding="utf-8")
    (d / "main.map.json").write_text(
        json.dumps({str(i + 1): o for i, o in enumerate(owners)}, indent=2), encoding="utf-8"
    )
    return py, owners


def raises(exc, fn, *args, **kwargs) -> bool:
    try:
        fn(*args, **kwargs)
    except exc:
        return True
    except Exception:
        return False
    return False


class Repl:
    def __init__(self):
        self.cursor: Node | None = None

    def where(self) -> str:
        return self.cursor.path if self.cursor else "/"

    def resolve(self, arg: str) -> Node | None:
        if arg.startswith("progs/") and Node(arg).file.exists():
            return Node(arg)
        cands = [Node(f"progs/{f.stem}") for f in PROGS.glob("*.human")] if self.cursor is None else self.cursor.children()
        if arg.isdigit() and 1 <= int(arg) <= len(cands):
            return cands[int(arg) - 1]
        for c in cands:
            if c.name == arg or c.intent().lower().startswith(arg.lower()):
                return c
        if Node(f"progs/{arg}").file.exists():
            return Node(f"progs/{arg}")
        return None

    def roots(self) -> list[Node]:
        progs = [Node(f"progs/{f.stem}") for f in sorted(PROGS.glob("*.human"))]
        return progs + [Node(f"lang/{f.stem}") for f in sorted(LANG.glob("*.human"))]

    def do_write(self, text: str):
        if self.cursor is None:
            slug = "_".join(re.findall(r"[a-z0-9]+", text.lower())[:3]) or "prog"
            name, i = slug, 2
            while Node(f"progs/{name}").file.exists():
                name, i = f"{slug}{i}", i + 1
            n = Node(f"progs/{name}")
            n.write(text)
            self.cursor = n
            print(f"created {n.path} - now: build")
            return
        self.cursor.write(text)
        stale = " (subtree below is stale - run: lower -r)" if self.cursor.children() else ""
        print(f"rewrote {self.cursor.path}{stale}")

    def do_ls(self, arg: str):
        if arg.strip() in ("-r", "--recursive") and self.cursor is not None:
            for n in self.cursor.subtree():
                print(f"{'  ' * (n.level - self.cursor.level)}{n.intent()[:70]}")
            return
        if self.cursor is None:
            cands = self.roots()
            if not cands:
                print("(nothing here - type what you want to build, e.g.  http server)")
            for i, c in enumerate(cands, 1):
                tag = "lang" if c.is_lang else "prog"
                print(f"  {i}. [{tag}] {c.name}  -  {c.intent()[:56]}")
            return
        print(f"  {self.cursor.intent()}\n")
        kids = self.cursor.children()
        if not kids:
            print("  (no children - type new text to rewrite this, or: lower)")
            return
        for i, c in enumerate(kids, 1):
            mark = "+" if c.children() else " "
            print(f"  {i}.{mark} {c.intent()}")

    def do_cd(self, arg: str):
        if arg in ("/", ""):
            self.cursor = None
            return
        if arg == "..":
            if self.cursor is not None:
                self.cursor = self.cursor.parent
            return
        n = self.resolve(arg)
        if n is None:
            print(f"no such node: {arg}")
            return
        self.cursor = n

    def do_edit(self, _):
        if self.cursor is None:
            print("cd into a node first")
            return
        editor = os.environ.get("EDITOR") or ("notepad" if os.name == "nt" else "vi")
        fd, tmp = tempfile.mkstemp(suffix=".human", text=True)
        os.close(fd)
        Path(tmp).write_text(self.cursor.text + "\n", encoding="utf-8")
        subprocess.call([editor, tmp])
        new = Path(tmp).read_text(encoding="utf-8").strip()
        os.unlink(tmp)
        if new and new != self.cursor.text:
            self.cursor.write(new)
            print(f"updated {self.cursor.path} (subtree below it is now stale - run: lower -r)")
        else:
            print("unchanged")

    def do_add(self, text: str):
        if self.cursor is None:
            print("cd into a node first")
            return
        if not text:
            print("+ what? give the child some text")
            return
        self.cursor.dir.mkdir(parents=True, exist_ok=True)
        child = Node(f"{self.cursor.path}/{len(self.cursor.children()) + 1}")
        child.write(text)
        print(f"added {child.path}")

    def do_lower(self, arg: str):
        if self.cursor is None:
            print("cd into a node first")
            return
        recursive = arg.strip() in ("-r", "--recursive")
        queue = [self.cursor]
        while queue:
            node = queue.pop(0)
            proposed, survivors = lower_earned(node)
            if not survivors:
                print(f"{node.path} is a leaf (nothing proposed changes the code)")
                continue
            discarded = proposed - len(survivors)
            print(
                f"lowered {node.path}: {proposed} proposed, {len(survivors)} earned, "
                f"{discarded} discarded (changed no code)"
            )
            if recursive:
                queue.extend(survivors)
        self.do_ls("")

    def chain(self, node: Node, label: str = ""):
        if label:
            print(label)
        for i, a in enumerate(node.ancestors() + [node]):
            print(f"{'  ' * i}{TWIG if i else ''}{a.intent()}   [{a.path}]")

    def do_why(self, arg: str):
        if self.cursor is None:
            print("(at /) cd into a node, or: why <line number> inside a program")
            return
        if not arg.strip():
            self.chain(self.cursor)
            return
        root = self.cursor.program
        m = build_dir(root) / "main.map.json"
        if not m.exists():
            print("nothing compiled yet - run: build")
            return
        owner = json.loads(m.read_text(encoding="utf-8")).get(arg.strip())
        if not owner:
            print(f"no provenance for line {arg.strip()}")
            return
        self.chain(Node(owner), f"line {arg.strip()} of {root.name} was caused by:\n")

    def program_or_none(self) -> Node | None:
        if self.cursor is None or self.cursor.is_lang:
            print("cd into a program first")
            return None
        return self.cursor.program

    def provenance(self, root: Node, force: bool) -> None:
        targets = [n for n in root.subtree() if n.path != root.path]
        tally: dict[str, dict[str, int]] = {"unit": {}, "deep": {}}
        unmeasured = 0
        for n in targets:
            try:
                r = ablate(n, probe=not force)
            except Exception as exc:
                print(f"  [ablate] {'error':<12} {n.path}: {exc}")
                continue
            if r is None:
                unmeasured += 1
                continue
            v = r["verdict"]
            tier = "unit" if n.path == unit_of(n).path else "deep"
            tally[tier][v] = tally[tier].get(v, 0) + 1
            if force:
                print(f"  [ablate] {v:<12} {n.path}: owned {r['owned']}, survived {r['survived']}")
                print(f"             {n.intent()[:64]}")
        units, deep = tally["unit"], tally["deep"]
        parts = []
        nu = sum(units.values())
        if nu:
            own = sum(v for k, v in units.items() if earned(k))
            parts.append(f"{own}/{nu} units own code")
        nd = sum(deep.values())
        if nd:
            won = sum(v for k, v in deep.items() if earned(k))
            bits = ", ".join(f"{k} {v}" for k, v in sorted(deep.items()))
            parts.append(f"{won}/{nd} nodes below the unit line earned ({bits})")
        else:
            parts.append("no nodes below the unit line")
        if nu or nd:
            print(f"provenance: {', '.join(parts)}")
        if unmeasured:
            print(f"provenance: {unmeasured} nodes unmeasured - run: check")

    def do_check(self, _):
        root = self.program_or_none()
        if root is None:
            return
        asserted = [(n, a) for n in root.subtree() for a in n.assertions()]
        if asserted:
            py, _ = build(root)
            ns = {"__name__": "fran_check", "raises": raises}
            exec(compile(py.read_text(encoding="utf-8"), str(py), "exec"), ns)
            passed = 0
            for n, a in asserted:
                try:
                    ok = bool(eval(a, ns))
                except Exception as exc:
                    ok, a = False, f"{a}   !! {exc}"
                passed += 1 if ok else 0
                print(f"  [test] {'pass' if ok else 'FAIL'} {n.path}: {a}")
            print(f"tests: {passed}/{len(asserted)} passed\n")
        else:
            print("no assertions in this tree (add an 'assert:' line to any node)\n")
        self.provenance(root, force=True)
        print("\n  caused       the lines it claimed vanished when it was deleted. sound.")
        print("  DECORATIVE   its lines survived its deletion. it did not cause them.")
        print("  partial      it caused some of the lines it claimed.")
        print("  unattributed it causes code, but the map credits another node.")
        print("  inert        deleting it changes nothing. the node is ceremony.")

    def do_build(self, arg: str):
        root = self.program_or_none()
        if root is None:
            return
        py, owners = build(root)
        rel = py.relative_to(ROOT)
        if arg.strip() in ("-p", "--print"):
            print(py.read_text(encoding="utf-8"))
        print(f"compiled {root.path} -> {rel}  ({len(owners)} lines, {len(set(owners))} nodes)")
        print(f"  map: {rel.with_suffix('.map.json')}   run it yourself: python {rel}")
        self.provenance(root, force=False)

    def do_help(self, _):
        print(HELP)

    def loop(self):
        print(f"fran - model {MODEL_ID} - type what you want to build, or 'help'")
        table = {
            "ls": self.do_ls, "cd": self.do_cd, "edit": self.do_edit,
            "lower": self.do_lower, "why": self.do_why, "check": self.do_check,
            "build": self.do_build, "help": self.do_help,
        }
        while True:
            try:
                line = input(f"{self.where()}> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return
            if not line:
                continue
            if line in ("quit", "exit", "q"):
                return
            try:
                if line.startswith("+"):
                    self.do_add(line[1:].strip())
                    continue
                cmd, _, args = line.partition(" ")
                fn = table.get(cmd)
                fn(args.strip()) if fn else self.do_write(line)
            except Exception as exc:
                print(f"error: {exc}")


HELP = """  <text>              write. at / it starts a program; on a node it rewrites it.
  + <text>            add a child to the cursor. your words. never auto-discarded.
  ls [-r]             the cursor's text and its children, numbered
  cd <n|path|..|/>    move the cursor
  edit                open $EDITOR on the cursor, for longer text
  lower [-r]          propose children, keep only the ones that change the code.
                      a node whose children change nothing is a leaf. -r recurses
                      into the survivors only.
  build [-p]          compile the nodes that exist to build/. it does not lower.
                      -p prints the code.
  why [<line>]        why this node exists, or what caused line <n> of the build
  check               run the assertions, then ablate every node. the honest measure.
  quit

  fran compiles. it does not launch your program - that is your shell's job.

  lang/ is nodes too. cd 6, type new text, and you have changed the compiler."""


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] in ("build", "check", "lower"):
        r = Repl()
        r.cursor = Node(args[1]) if len(args) > 1 else None
        {"build": r.do_build, "check": r.do_check, "lower": r.do_lower}[args[0]]("-r" if args[0] == "lower" else "")
    else:
        Repl().loop()
