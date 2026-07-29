from __future__ import annotations

import ast
import hashlib
import json
import os
import re
from pathlib import Path

import boto3
from botocore.config import Config
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
LANG, CACHE = ROOT / "lang", ROOT / ".cache"
PROJECTS = ROOT.parent / "projects"
PROJECTS_JSON = ROOT.parent / "projects.json"
for _env in (ROOT / ".env", ROOT.parent.parent / ".env"):
    if _env.exists():
        load_dotenv(_env)
REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-6")
FRESH = False

class Malformed(Exception):
    pass

ID_LINE = re.compile(r"^@id:\s*([0-9a-f]{4})\s*$", re.M)
LANG_SHEETS = ("python", "html")

class Node:
    def __init__(self, path: str):
        self.path = path
    def __eq__(self, other):
        return isinstance(other, Node) and other.path == self.path
    def __hash__(self):
        return hash(self.path)
    def program_name(self) -> str:
        return self.path.split("/", 1)[0]
    def file(self) -> Path:
        return PROJECTS / self.program_name() / (self.path + ".human")
    def dir(self) -> Path:
        return PROJECTS / self.program_name() / self.path
    def name(self) -> str:
        return self.path.rsplit("/", 1)[-1]
    def level(self) -> int:
        return self.path.count("/")
    def program(self) -> "Node":
        return Node(self.program_name())
    def parent(self) -> "Node | None":
        return None if "/" not in self.path else Node(self.path.rsplit("/", 1)[0])
    def raw(self) -> str:
        return self.file().read_text(encoding="utf-8") if self.file().exists() else ""
    def text(self) -> str:
        return ID_LINE.sub("", self.raw()).strip()
    def intent(self) -> str:
        return re.sub(r"^(assert|note):\s*.+$", "", self.text(), flags=re.M).strip()
    def assertions(self) -> list[str]:
        return [m.group(1).strip() for m in re.finditer(r"^assert:\s*(.+)$", self.text(), re.M)]
    def nid(self) -> str:
        m = ID_LINE.search(self.raw())
        return m.group(1) if m else ""
    def stamp(self, new: str) -> None:
        self.file().parent.mkdir(parents=True, exist_ok=True)
        self.file().write_text(f"@id: {new}\n{self.text()}\n", encoding="utf-8")
    def write(self, text: str) -> None:
        self.file().parent.mkdir(parents=True, exist_ok=True)
        head = f"@id: {self.nid()}\n" if self.nid() else ""
        self.file().write_text(f"{head}{text.strip()}\n", encoding="utf-8")
    def children(self) -> list["Node"]:
        kids = [Node(f"{self.path}/{f.stem}") for f in self.dir().glob("*.human")] if self.dir().is_dir() else []
        return sorted(kids, key=lambda n: (not n.name().isdigit(), int(n.name()) if n.name().isdigit() else 0, n.name()))
    def ancestors(self) -> list["Node"]:
        chain, cur = [], self.parent()
        while cur is not None:
            chain.append(cur)
            cur = cur.parent()
        return chain[::-1]
    def subtree(self) -> list["Node"]:
        return [self] + [d for c in self.children() for d in c.subtree()]

def mint(path: str, text: str, used: set[str]) -> str:
    seed = hashlib.sha256((path + chr(31) + text).encode()).hexdigest()
    cand, i = seed[:4], 0
    while cand in used:
        i += 1
        cand = seed[i:i + 4] if i + 4 <= len(seed) else hashlib.sha256(f"{seed}{i}".encode()).hexdigest()[:4]
    used.add(cand)
    return cand

def ensure_ids(root: Node) -> None:
    nodes = root.subtree()
    used = {n.nid() for n in nodes if n.nid()}
    for n in nodes:
        if not n.nid():
            n.stamp(mint(n.path, n.text(), used))

EXPAND_SYSTEM = """You are the lowering stage of human, a language whose source is human text.

You are given the language, the ancestors that explain why this node exists, the children it
already has, and the node to expand. Expand it one level toward code, obeying the language
exactly. Do not write code. Write the next level of human text.

Return {"leaf": true} if expanding would only restate the node.
Otherwise return {"children": ["...", "..."]}."""

CODE_SYSTEM = """You are the code generation stage of human, a language whose source is human text.

You are given the language and the entire program: every sentence with its @id and path, indented
by depth. Emit the whole program as ONE file. There is one namespace and you are its only author.

Declare, in the same answer, which sentences caused which characters of the code. Answer in two
parts and nothing else. First the whole file inside one fenced code block, LF line endings only:

```
<the whole file>
```

Then one JSON object carrying the map, declared over the exact string between the fence lines:

{"map": [{"nodes": ["<id>", ...], "kind": "specified" | "assumed",
          "why": "<only on assumed: the gap this fragment fills>",
          "quote": "<the exact substring of the code the range covers>",
          "ranges": [[start, end], ...]}, ...]}

A fragment's nodes list is its owner-set: the ids of every sentence that causes those characters,
written as bare 4-hex strings exactly as given, without the @ sign.
Several ids mean joint causation, sentences that only together force that span. kind is "specified"
when the span traces to sentences in the tree, "assumed" when you filled a gap with a convention no
sentence stated; every assumed fragment carries a why, and only an assumed fragment may have an
empty owner-set, meaning pure convention. A range is a pair of character offsets: code[start:end]
is the region. Compute offsets exactly, never guess; snap edges to token or line boundaries.
Every fragment carries quote, one entry per range in range order (a list when there are several).
For a range of at most 120 characters the entry is the exact substring the range covers, copied
character for character. For a longer range the entry is an object {"head": "...", "tail": "..."}
carrying the first 60 and last 60 characters of the covered slice, copied exactly. Omit quote only
on the root whole-file fragment; the engine fills that one.

Hard rules, verified by computation before your answer is accepted:
- the root sentence owns one fragment whose range is the whole file, [0, len(code)]
- any two ranges either nest or are disjoint, never partially overlap
- every character lies inside some range beyond that whole-file one: code no sentence causes is
  owned up to in an assumed fragment with a why, no orphans
- for each sentence, the tightest ranges of other sentences that contain its ranges form an
  antichain: none of those containers contains another
- each quote matches the code at its range: a short range's quote equals code[start:end], a long
  range's head and tail equal the first and last characters of the slice; a wrong quote is
  relocated only when it pins one exact position in the code, otherwise rejected

If the program is underspecified, build it anyway: choose a conventional default, write the code,
and tag the region "assumed" with its why. Never refuse to build. Return the fenced code block,
then the map object, and nothing else."""

REVISE_SYSTEM = """You are the code generation stage of human, a language whose source is human text.

The tree changed since the last build. You are given the baseline code as it stood before the
change and the tree as it stands now. Emit the program the tree now implies, as the smallest change
to the baseline the edit forces. Every line the tree still implies survives byte for byte: do not
rename, re-sign, reorder, restyle, or improve anything the change did not force you to touch.

Return the same two-part answer as the code stage: the whole file inside one fenced code block,
then one JSON object {"map": [...]} with the owner-set map declared over the code you return,
obeying the same hard rules, specified and assumed tagged."""

MAP_SYSTEM = """You are the map stage of human, a language whose source is human text.

The program's code is already accepted and frozen; only the causation map was rejected. You are
given the language, the program tree, the exact code, and what was wrong. Offsets index the frozen
code string exactly as shown, character for character. Return one JSON object and nothing else:

{"map": [{"nodes": ["<id>", ...], "kind": "specified" | "assumed",
          "why": "<only on assumed: the gap this fragment fills>",
          "quote": "<the exact substring of the code the range covers>",
          "ranges": [[start, end], ...]}, ...]}

Owner ids are bare 4-hex strings without the @ sign. The hard rules are unchanged: the root owns a
whole-file fragment, any two ranges nest or are disjoint, every character lies in some range beyond
the whole-file one, each sentence's tightest containing ranges form an antichain, and every
fragment carries quote, one entry per range: the exact covered substring for a range of at most 120
characters, an object {"head": "...", "tail": "..."} with the slice's first 60 and last 60
characters for a longer one (omit quote only on the whole-file fragment; the engine fills it).
Snap range edges to line boundaries: adjacent fragments tile flush, so the whitespace between two
fragments belongs inside one of them or inside an assumed fragment, never in a crack between them."""

SYSTEM = {"expand": EXPAND_SYSTEM, "code": CODE_SYSTEM, "revise": REVISE_SYSTEM}
SCOPES = {"expand": ("lower",), "code": ("code", "map"), "revise": ("code", "map", "revise")}

def lang_text(kind: str, lang: str = "") -> str:
    parts = []
    for scope in SCOPES[kind]:
        d = LANG / scope
        for f in (sorted(d.glob("*.human")) if d.is_dir() else []):
            if scope == "code" and f.stem in LANG_SHEETS and f.stem != lang:
                continue
            parts.append(f"### lang/{scope}/{f.stem}\n{f.read_text(encoding='utf-8').strip()}")
    return "\n\n".join(parts)

def cached(kind: str, lang: str, key: list[str], fn):
    seed = [kind, MODEL_ID, lang_text(kind, lang), SYSTEM[kind], *key]
    f = CACHE / f"{hashlib.sha256(chr(31).join(seed).encode()).hexdigest()}.json"
    if f.exists() and not FRESH:
        return json.loads(f.read_text(encoding="utf-8"))
    value = fn()
    CACHE.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(value, indent=2), encoding="utf-8")
    return value

def call(system: str, user: str, max_tokens: int = 4096) -> str:
    cfg = Config(read_timeout=1200, connect_timeout=30, retries={"max_attempts": 2})
    print(f"  [api] converse -> {MODEL_ID} ({len(user)} prompt chars, maxTokens {max_tokens})", flush=True)
    r = boto3.client(service_name="bedrock-runtime", region_name=REGION, config=cfg).converse(
        modelId=MODEL_ID,
        system=[{"text": system}],
        messages=[{"role": "user", "content": [{"text": user}]}],
        inferenceConfig={"temperature": 0, "maxTokens": max_tokens},
    )
    text = r["output"]["message"]["content"][0]["text"]
    usage = r.get("usage", {})
    print(f"  [api] <- {len(text)} chars ({usage.get('inputTokens', '?')} in / {usage.get('outputTokens', '?')} out tokens)", flush=True)
    return text

def lenient_loads(text: str):
    for strict in (True, False):
        try:
            return json.loads(text, strict=strict)
        except json.JSONDecodeError:
            continue
    return None

def call_json(system: str, user: str) -> dict:
    nudge = ""
    for _ in range(2):
        raw = call(system + "\n\nRespond with one JSON object and nothing else." + nudge, user)
        m = re.search(r"\{.*\}", raw, re.S)
        if m:
            val = lenient_loads(m.group(0))
            if val is not None:
                return val
        nudge = "\n\nYour previous reply was not one parseable JSON object. Emit the object alone."
    raise Malformed("the model did not return one JSON object")

def structure_errors(frags, code: str, ids: set[str]) -> list[str]:
    if not isinstance(frags, list) or not frags:
        return ["'map' must be a non-empty list of fragments"]
    errs = []
    for i, f in enumerate(frags):
        tag = f"fragment {i} ({json.dumps(f)[:100]})"
        if not isinstance(f, dict):
            errs.append(f"{tag}: not an object")
            continue
        owners, kind, why = f.get("nodes"), f.get("kind"), f.get("why")
        if not isinstance(owners, list) or not all(isinstance(x, str) for x in owners):
            errs.append(f"{tag}: 'nodes' must be a list of @id strings")
            continue
        unknown = [x for x in owners if x not in ids]
        if unknown:
            errs.append(f"{tag}: unknown node id(s) {unknown}")
        if kind not in ("specified", "assumed"):
            errs.append(f"{tag}: 'kind' must be 'specified' or 'assumed'")
            continue
        if kind == "specified" and not owners:
            errs.append(f"{tag}: an empty owner-set is allowed only on an assumed fragment")
        if kind == "assumed" and (not isinstance(why, str) or not why.strip()):
            errs.append(f"{tag}: an assumed fragment must carry a non-empty 'why'")
        if kind == "specified" and why is not None:
            errs.append(f"{tag}: 'why' belongs only on assumed fragments")
        ranges = f.get("ranges")
        if not isinstance(ranges, list) or not ranges:
            errs.append(f"{tag}: 'ranges' must be a non-empty list of [start, end] pairs")
            continue
        bad = False
        for r in ranges:
            if not isinstance(r, list) or len(r) != 2 or not all(isinstance(x, int) and not isinstance(x, bool) for x in r):
                errs.append(f"{tag}: range {r} is not a pair of integers")
                bad = True
        if bad:
            continue
        qs = f.get("quote")
        good = lambda x: (isinstance(x, str) and x) or (
            isinstance(x, dict) and isinstance(x.get("head"), str) and x["head"]
            and isinstance(x.get("tail"), str) and x["tail"])
        if not isinstance(qs, list) or not all(good(x) for x in qs):
            errs.append(f"{tag}: each quote entry must be the exact substring for a short range, or an object {{\"head\": ..., \"tail\": ...}} of non-empty strings for a long one")
        elif len(qs) != len(ranges):
            errs.append(f"{tag}: this fragment has {len(ranges)} ranges but {len(qs)} quote entries; give a list of exactly {len(ranges)}, one per range in range order")
    return errs

def crossing_errors(frags) -> list[str]:
    spans = [(a, b, i) for i, f in enumerate(frags) for a, b in f["ranges"]]
    errs = []
    for k in range(len(spans)):
        for l in range(k + 1, len(spans)):
            a, b, i = spans[k]
            c, d, j = spans[l]
            if a < c < b < d or c < a < d < b:
                errs.append(f"fragments {i} and {j}: ranges [{a}, {b}] and [{c}, {d}] cross; any two ranges must nest or be disjoint")
    return errs

def coverage_errors(frags, code: str, root_id: str) -> list[str]:
    n = len(code)
    errs = []
    if not any(root_id in f["nodes"] and any(r[0] == 0 and r[1] == n for r in f["ranges"]) for f in frags):
        errs.append(f"the root node {root_id} must own a fragment whose range is the whole file, [0, {n}]")
    inner = sorted((a, b) for f in frags for a, b in f["ranges"] if not (a == 0 and b == n))
    pos, gaps = 0, []
    for a, b in inner:
        if a > pos:
            gaps.append((pos, a))
        pos = max(pos, b)
    if pos < n:
        gaps.append((pos, n))
    for a, b in gaps:
        if code[a:b].strip():
            errs.append(f"characters {a}:{b} ({code[a:min(b, a + 60)]!r}) lie in no fragment beyond the whole-file range; attribute them to a node or to an assumed fragment with a why")
    return errs

def quote_errors(frags, code: str) -> list[str]:
    errs = []
    for i, f in enumerate(frags):
        tag = lambda: f"fragment {i} ({json.dumps(f)[:100]})"
        for k, ((a, b), q) in enumerate(zip(f["ranges"], f["quote"])):
            if isinstance(q, str):
                if code[a:b] == q:
                    continue
                hits = [m.start() for m in re.finditer(re.escape(q), code)]
                near = hits if len(hits) == 1 else [h for h in hits if abs(h - a) <= 200]
                if len(near) == 1:
                    f["ranges"][k] = [near[0], near[0] + len(q)]
                    continue
                if not hits:
                    s = code[a:a + len(q)]
                    p = next((j for j, (x, y) in enumerate(zip(q, s)) if x != y), min(len(q), len(s)))
                    errs.append(f"{tag()}: quote {q[:60]!r} occurs nowhere in the code; it first diverges at quote offset {p}, where the quote reads {q[p:p + 40]!r} but the code at {a + p} reads {code[a + p:a + p + 40]!r}; copy the quote from the code exactly")
                else:
                    errs.append(f"{tag()}: quote {q[:60]!r} occurs {len(hits)} times and range [{a}, {b}] pins none of them; give a longer quote that occurs once")
                continue
            h, t = q["head"], q["tail"]
            if b - len(t) >= 0 and code[a:a + len(h)] == h and code[b - len(t):b] == t:
                continue
            L = b - a
            starts = [m.start() for m in re.finditer(re.escape(h), code)]
            ends = [m.start() + len(t) for m in re.finditer(re.escape(t), code)]
            pairs = [(p, e) for p in starts for e in ends if e - p >= max(len(h), len(t))]
            pick = pairs[0] if len(pairs) == 1 else None
            if pick is None and len(pairs) > 1:
                close = [pe for pe in pairs if abs((pe[1] - pe[0]) - L) <= max(64, L // 8)]
                exact = [pe for pe in close if pe[1] - pe[0] == L]
                if len(exact) == 1:
                    pick = exact[0]
                elif len(close) == 1:
                    pick = close[0]
                elif len(close) > 1:
                    ranked = sorted(close, key=lambda pe: abs((pe[1] - pe[0]) - L))
                    if abs((ranked[0][1] - ranked[0][0]) - L) < abs((ranked[1][1] - ranked[1][0]) - L):
                        pick = ranked[0]
            if pick is not None:
                f["ranges"][k] = [pick[0], pick[1]]
                continue
            errs.append(f"{tag()}: capped quote does not match range [{a}, {b}]: the slice starts {code[a:a + 40]!r} and ends {code[max(a, b - 40):b]!r}, but head reads {h[:40]!r} and tail reads {t[-40:]!r}, and no span near that length starts with the head and ends with the tail at one unique position; fix head, tail, or the range")
    return errs

def layer_errors(frags, ids: list[str]) -> list[str]:
    spans = [(a, b, frozenset(f["nodes"])) for f in frags for a, b in f["ranges"]]
    errs = []
    for x in ids:
        own = [(a, b) for a, b, o in spans if x in o]
        pool = [(a, b, o) for a, b, o in spans if o and x not in o]
        containers = {}
        for a, b in own:
            cands = [(c, d, o) for c, d, o in pool if c <= a and b <= d and (c, d) != (a, b)]
            if cands:
                c, d, o = min(cands, key=lambda t: t[1] - t[0])
                containers[(c, d)] = o
        keys = sorted(containers)
        for u in keys:
            for v in keys:
                if u != v and u[0] <= v[0] and v[1] <= u[1]:
                    errs.append(f"node {x} skips a layer: its ranges hang under both [{u[0]}, {u[1]}] (owned by {sorted(containers[u])}) and [{v[0]}, {v[1]}] (owned by {sorted(containers[v])}), and the first contains the second; the tightest containers of one node must form an antichain")
    return errs

def html_errors(code: str) -> list[str]:
    if not code.strip():
        return ["the html is empty"]
    body = re.sub(r"<!--.*?-->", "", code, flags=re.S)
    stripped = re.sub(r"<(script|style)\b[^>]*>.*?</\1\s*>", "", body, flags=re.S | re.I)
    if re.search(r"<(script|style)\b[^>]*>", stripped, re.I):
        return ["an opened <script> or <style> block never closes"]
    errs = []
    for tag in ("html", "head", "body", "main", "div", "span", "section", "table", "ul", "ol", "pre"):
        opens = len(re.findall(rf"<{tag}(?=[\s>])", stripped, re.I))
        closes = len(re.findall(rf"</{tag}\s*>", stripped, re.I))
        if opens != closes:
            errs.append(f"<{tag}> opens {opens} time(s) but closes {closes} time(s)")
    return errs

def language_errors(code: str, ext: str) -> list[str]:
    if ext == "py":
        try:
            ast.parse(code)
            return []
        except SyntaxError as exc:
            return [f"the code is not a valid python module: line {exc.lineno}: {exc.msg}"]
    if ext == "html":
        return html_errors(code)
    return []

def normalized(frags, code: str) -> list[dict]:
    n = len(code)
    out = []
    for f in frags:
        e = {"nodes": list(f["nodes"]), "kind": f["kind"], "ranges": [[int(a), int(b)] for a, b in f["ranges"]]}
        if e["ranges"] != [[0, n]]:
            qs = [code[a:b] if b - a <= 120 else {"head": code[a:a + 60], "tail": code[b - 60:b]}
                  for a, b in e["ranges"]]
            e["quote"] = qs[0] if len(qs) == 1 else qs
        if f["kind"] == "assumed":
            e["why"] = f["why"].strip()
        out.append(e)
    return out

def extract_obj(raw: str):
    m = re.search(r"\{.*\}", raw, re.S)
    return lenient_loads(m.group(0)) if m else None

def extract_map(raw: str):
    obj = extract_obj(raw)
    if isinstance(obj, dict) and isinstance(obj.get("map"), list):
        return obj["map"]
    m = re.search(r"\[.*\]", raw, re.S)
    if m:
        val = lenient_loads(m.group(0))
        if isinstance(val, list):
            return val
    return None

def split_reply(raw: str):
    m = re.search(r"```[^\n]*\n(.*?)\n```", raw, re.S)
    if m:
        return m.group(1), extract_map(raw[m.end():])
    obj = extract_obj(raw)
    if isinstance(obj, dict) and isinstance(obj.get("code"), str):
        return obj["code"], obj.get("map")
    return None, None

def map_validate(frags, code: str, ids: list[str], root_id: str):
    n = len(code)
    if isinstance(frags, list):
        for f in frags:
            if not isinstance(f, dict):
                continue
            if isinstance(f.get("nodes"), list):
                f["nodes"] = [x.lstrip("@") if isinstance(x, str) else x for x in f["nodes"]]
            if isinstance(f.get("quote"), (str, dict)):
                f["quote"] = [f["quote"]]
            if isinstance(f.get("ranges"), list):
                quotes = f["quote"] if isinstance(f.get("quote"), list) and len(f["quote"]) == len(f["ranges"]) else None
                kept_r, kept_q = [], []
                for k, r in enumerate(f["ranges"]):
                    if isinstance(r, list) and len(r) == 2 and all(isinstance(x, int) and not isinstance(x, bool) for x in r):
                        a, b = max(0, min(r[0], n)), max(0, min(r[1], n))
                        if a < b:
                            kept_r.append([a, b])
                        else:
                            continue
                    else:
                        kept_r.append(r)
                    if quotes is not None:
                        kept_q.append(quotes[k])
                f["ranges"] = kept_r
                if quotes is not None:
                    f["quote"] = kept_q
            if (root_id in (f.get("nodes") or []) and f.get("quote") is None
                    and isinstance(f.get("ranges"), list) and len(f["ranges"]) == 1
                    and isinstance(f["ranges"][0], list) and len(f["ranges"][0]) == 2
                    and f["ranges"][0][0] == 0 and isinstance(f["ranges"][0][1], int)
                    and n - 8 <= f["ranges"][0][1] <= n + 8):
                f["ranges"] = [[0, n]]
            if f.get("ranges") == [[0, n]] and f.get("quote") != [code]:
                f["quote"] = [code]
        frags[:] = [f for f in frags if not (isinstance(f, dict) and f.get("ranges") == [])]
        if not any(isinstance(f, dict) and root_id in (f.get("nodes") or [])
                   and any(r == [0, n] for r in (f.get("ranges") or []))
                   for f in frags):
            frags.append({"nodes": [root_id], "kind": "specified", "ranges": [[0, n]], "quote": [code]})
    complaints = structure_errors(frags, code, set(ids))
    if not complaints:
        complaints = quote_errors(frags, code)
    if not complaints:
        complaints = crossing_errors(frags) + coverage_errors(frags, code, root_id) + layer_errors(frags, ids)
    return frags, complaints

def map_repair(kind: str, user: str, code: str, frags, ids: list[str], root_id: str) -> dict:
    frags, complaints = map_validate(frags, code, ids, root_id)
    if not complaints:
        return {"code": code, "map": normalized(frags, code)}
    for rnd in range(1, 5):
        print(f"  [map repair {rnd}] {complaints[0]}", flush=True)
        prompt = (f"{user}\n\n# The code, {len(code)} characters, accepted and frozen; offsets index this exact string\n"
                  f"```\n{code}\n```\n\n# The map was rejected\n" + "\n".join(complaints[:12])
                  + "\n\nReturn one JSON object {\"map\": [...]} and nothing else - the complete corrected map over the frozen code.")
        cand = extract_map(call(MAP_SYSTEM, prompt, 32000))
        if not isinstance(cand, list):
            complaints = ["the reply was neither one JSON object {\"map\": [...]} nor a JSON array of fragments"]
            continue
        frags, complaints = map_validate(cand, code, ids, root_id)
        if not complaints:
            return {"code": code, "map": normalized(frags, code)}
    raise Malformed(f"{kind}: map rejected after 4 map-only repairs; last complaint: {complaints[0]}")

def code_call(kind: str, user: str, ext: str, ids: list[str], root_id: str, lang: str = "", key: list[str] | None = None) -> dict:
    fz = None
    if key is not None:
        seed = ["frozen", kind, MODEL_ID, lang_text(kind, lang), SYSTEM[kind], *key]
        fz = CACHE / f"{hashlib.sha256(chr(31).join(seed).encode()).hexdigest()}.json"
        if fz.exists():
            kept = json.loads(fz.read_text(encoding="utf-8"))
            print("  [cache] frozen code reused; map repairs only", flush=True)
            return map_repair(kind, user, kept["code"], kept["map"], ids, root_id)
    prompt = user
    complaints = ["the model returned nothing"]
    for attempt in range(3):
        if attempt:
            print(f"  [repair {attempt}] {complaints[0]}", flush=True)
        code, frags = split_reply(call(SYSTEM[kind] + "\n\nRespond with the fenced code block, then the map object, and nothing else.", prompt, 32000))
        if not isinstance(code, str) or not code.strip():
            complaints = ["the reply did not open with the whole file inside one fenced code block"]
        elif "\r" in code:
            complaints = ["the code contains carriage returns; emit LF line endings only"]
        else:
            complaints = language_errors(code, ext)
            if not complaints:
                frags = frags if isinstance(frags, list) else []
                if fz is not None:
                    CACHE.mkdir(parents=True, exist_ok=True)
                    fz.write_text(json.dumps({"code": code, "map": frags}, indent=2), encoding="utf-8")
                return map_repair(kind, user, code, frags, ids, root_id)
        prompt = (f"{user}\n\n# Your previous answer was rejected\n" + "\n".join(complaints[:12])
                  + "\n\nReturn the complete corrected answer and nothing else: the whole file inside one"
                  " fenced code block, then one JSON object {\"map\": [...]} - the full code and the full map,"
                  " not an explanation of the fix, not a partial answer.")
    raise Malformed(f"{kind}: rejected after 2 repairs; last complaint: {complaints[0]}")

def serialize(root: Node) -> str:
    return "\n".join(f"{'  ' * n.level()}[@{n.nid()} {n.path}] {' '.join(n.intent().split())}" for n in root.subtree())

def tree_nodes(root: Node) -> list[dict]:
    return [{"id": n.nid(), "path": n.path, "level": n.level(), "text": n.intent()} for n in root.subtree()]

def generate(root: Node, entry: dict, baseline: str | None = None) -> dict:
    kind = "revise" if baseline is not None else "code"
    ext = entry["code_file"].rsplit(".", 1)[-1].lower()
    lang = {"py": "python"}.get(ext, ext)
    tree = serialize(root)
    ids = [n.nid() for n in root.subtree()]
    user = f"# The language\n{lang_text(kind, lang)}\n\n# The target\nOne file: {entry['code_file']}\n\n"
    if baseline is not None:
        user += f"# The baseline code (before the change)\n```\n{baseline}\n```\n\n"
    user += f"# The program\n{tree}"
    key = [entry["code_file"], tree] + ([baseline] if baseline is not None else [])
    return cached(kind, lang, key, lambda: code_call(kind, user, ext, ids, root.nid(), lang, key))

def materialize(root: Node, frags) -> None:
    nodes = root.subtree()
    used = {n.nid() for n in nodes}
    by_id = {n.nid(): n for n in nodes}
    next_idx = {}
    def free(parent: Node) -> int:
        if parent.path not in next_idx:
            taken = [int(c.name()) for c in parent.children() if c.name().isdigit()]
            next_idx[parent.path] = max(taken, default=0) + 1
        idx = next_idx[parent.path]
        next_idx[parent.path] = idx + 1
        return idx
    for i in sorted((i for i, f in enumerate(frags) if f["kind"] == "assumed"),
                    key=lambda i: -max(b - a for a, b in frags[i]["ranges"])):
        f = frags[i]
        tight = None
        for a, b in f["ranges"]:
            for g in frags:
                if g is f or not g["nodes"]:
                    continue
                for c, d in g["ranges"]:
                    if c <= a and b <= d and (tight is None or d - c < tight[0]):
                        tight = (d - c, g)
        owners = [by_id[x] for x in (tight[1]["nodes"] if tight else [root.nid()])]
        parent = max(owners, key=lambda o: o.level())
        child = Node(f"{parent.path}/{free(parent)}")
        why = f["why"].strip()
        child.write(why)
        child.stamp(mint(child.path, why, used))
        by_id[child.nid()] = child
        f["nodes"], f["kind"] = [child.nid()], "specified"
        f.pop("why", None)

def build(root: Node, entry: dict, baseline: str | None = None) -> tuple[Path, str, list[dict]]:
    result = generate(root, entry, baseline)
    code, frags = result["code"], [dict(f) for f in result["map"]]
    materialize(root, frags)
    d = PROJECTS / root.path / "build"
    d.mkdir(parents=True, exist_ok=True)
    out = d / entry["code_file"]
    out.write_text(code, encoding="utf-8", newline="\n")
    (d / "main.map.json").write_text(json.dumps({
        "program": root.path,
        "request": entry.get("request", ""),
        "code_file": entry["code_file"],
        "nodes": tree_nodes(root),
        "map": frags,
    }, indent=2), encoding="utf-8")
    return out, code, frags

def propose(node: Node) -> list[str]:
    anc = "\n".join(f"[level {a.level()}] {' '.join(a.intent().split())}" for a in node.ancestors()) or "(none, this is the root)"
    kids = "\n".join(f"- {' '.join(c.intent().split())}" for c in node.children()) or "(none)"
    user = (f"# The language\n{lang_text('expand')}\n\n# Ancestors (why this node exists)\n{anc}\n\n"
            f"# Children it already has (do not restate them)\n{kids}\n\n"
            f"# Node to expand (level {node.level()})\n{node.intent()}")
    out = cached("expand", "", [node.intent(), anc, kids], lambda: call_json(EXPAND_SYSTEM, user))
    if out.get("leaf"):
        return []
    return [c.strip() for c in out.get("children", []) if isinstance(c, str) and c.strip()]

def lower(node: Node) -> list[Node]:
    texts = propose(node)
    if not texts:
        return []
    start = len(node.children()) + 1
    made = []
    for i, text in enumerate(texts, start):
        child = Node(f"{node.path}/{i}")
        child.write(text)
        made.append(child)
    return made

def check(root: Node, code: str, path: Path) -> list[tuple]:
    ns = {"__name__": "human_check", "__file__": str(path), "raises": raises}
    exec(compile(code, str(path), "exec"), ns)
    results = []
    for n in root.subtree():
        for a in n.assertions():
            try:
                ok, err = bool(eval(a, ns)), ""
            except Exception as exc:
                ok, err = False, str(exc)
            results.append((n, a, ok, err))
    return results

def raises(exc, fn, *a, **kw) -> bool:
    try:
        fn(*a, **kw)
    except exc:
        return True
    except Exception:
        return False
    return False
