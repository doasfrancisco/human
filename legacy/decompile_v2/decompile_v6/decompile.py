import ast
import json
import os
import re
import runpy
import sys
import types
from pathlib import Path

import boto3
import jedi
from botocore.config import Config
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

PROMPT = """You are a decompiler. You go up one layer of abstraction per call. The input is one code file, one line per number, and the cells of the current layer of one block of that file, in file order. Merge adjacent cells into fewer groups and give each group one text.

File: {name}
{code}

You are compiling the block {block}, lines {span}. Ignore all other lines.

{ctx}Cells of the current layer:
{cells}

{stmts}{seen}Rules:
1. The groups cover the cells in order: the first group starts at cell 1, every group is a contiguous run of cells, each group starts one after the end of the group before it, and the last group ends at cell {n}.
2. Return fewer groups than cells. One group that holds all cells is legal when the block does one small thing. One group for one cell is legal when the block has only one cell.
3. A group of one cell is legal when a cell does not belong with a neighbor. Its text may stay the old text.
4. Every group gets one text: pseudocode in the shapes of the code, like x = ..., for x in y: ..., if x: return .... It names the real variables its lines read and write and the real functions they call. It drops the indexes, the temporaries, and the guards a reader does not need. A text may hold more than one line, split with \\n.
5. When a group binds more than one variable, the text gives one line per variable, in code order: name = what it holds, in plain words, not the expression that computes it.
6. When the pseudocode alone is not clear, add a note. A note that tells an action becomes its own pseudocode line, like for each cell: append it to its block. A note that does not tell an action is one short clause after " — " on the same line, in ASD-STE100 Simplified Technical English: short, active, plain words. No summary jargon.
7. A text starts with its pseudocode, not with prose. A function name always gets parentheses with its arguments, like emit(node) or check(map). A constant name gets none. Never start a text with "The".
8. A prompt or template string gets a text that says what it instructs, not how it is built.
9. A group holds all of a statement or none of it. A header line or an else line may join the group on either side.
10. On the first pass, a group is one step: at most 15 non-blank lines, unless the group is one single cell. A small block gets one group. A big block gets one group per stage, cut at its inner statement boundaries. Never group the lines before a loop or branch with only a part of it.
11. A text names the concrete things its lines touch: the names, the files, the keys, the counts. It never says only what kind of thing the code is.
12. When the lines call a compiled function from the list above, the text names it with its arguments. It does not explain the inside of that function. It never names a function this block does not call.
13. When the lines compute a thing the code does not name, the text may coin one short noun phrase for it, like "non-blank run", and every text uses the same phrase for the same thing.

Texts from a good map, in the exact voice to use:
"import ast, json, boto3, jedi — the parse, file, model, and link tools."
"load_dotenv(.env) — reads the credentials next to the script."
"path = the file path from sys.argv[1]\\nsrc = the text read from path\\nlines = src split into lines\\ncode = the lines, each with its number in front — the file the model sees"
"for node in ast.parse(src).body: emit(node) — each call fills spans."
"parts = cells grouped by block\\nfor each cell: parts[the block whose line spans hold all its lines] += cell"
"if not spans: return the non-blank runs of lines as cells — the fallback for files that are not Python."
"check(map) — asserts no duplicate id, no cut statement, no overlap, and full coverage."

Return one JSON object only, no code fences:
{{"groups": [{{"cells": [1, 3], "text": "client = boto3.client(bedrock-runtime) — region and timeouts come from the environment."}}, {{"cells": [4, 4], "text": "load_dotenv(.env) — reads the credentials next to the script."}}]}}"""

FLOW = """

This is the flow pass. The cells are the compiled stages of the block. Give the flow of the block: one beat per group, so the right sides read top to bottom as one story.
Flow rules:
a. Every group text is one single line, no \\n, also for a group of one cell. Never keep a multi-line stage text.
b. The line is names = role. The role says what the thing is for in the block's work, in plain words a reader who never saw the code understands — not how it is computed, and not the list of its parts. How is the stage below.
c. The role never repeats a left name or its noun. "cells = its cells" tells nothing. "cells = the smallest pieces to describe" decodes it.
d. The left side holds at most two names: the ones the story turns on. Every other bound name lives in the stage below — the flow does not inventory them.
e. One role per line, with at most one "and". A line that needs a second "and" glues roles: split the beat or drop names.
f. Merge adjacent stages into one group when they serve one role.
g. A tail clause after " — " only when the line is not clear without it.
h. A branch beat may be an if line, a loop beat a for line.
Flow texts from a good map, in the exact voice to use, top to bottom one story:
"code = the file to be decompiled"
"cells, ess = the smallest pieces to describe, and the lines no piece may break"
"blocks, lay = what to compile, and in what order"
"parts = each block's share of the pieces"
"done = every block compiled"
"map.json = the decompilation, written\""""

TERMS = """You are a decompiler. The map of one code file is done: every block has one signature text, flow texts for its movements, and pseudocode stage texts. Some texts coin a noun phrase for a thing the code computes but never names with a function or a variable. Collect these terms and define each one.

File: {name}
{code}

Texts of the map:
{texts}

Rules:
1. A term is a short noun phrase from the texts that names a computed thing with no name of its own in the code.
2. A variable name, a function name, or a plain English phrase that explains itself is not a term.
3. Each term gets one text: one line in ASD-STE100 Simplified Technical English that defines the thing, concrete, with the real names its code touches.
4. Each term gets defs: every [start, end] line range where the code computes the thing.
5. Keep only terms a reader needs: a phrase that two or more texts use, or a phrase a reader cannot decode from the lines of its own text. Zero terms is legal.

Return one JSON object only, no code fences:
{{"terms": [{{"term": "non-blank run", "text": "a longest stretch of consecutive lines where each line has text after strip()", "defs": [[88, 97], [102, 111]]}}]}}"""


def statements(path, src):
    if path.suffix != ".py":
        return []
    rows = []

    def walk(node, depth):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.stmt):
                rows.append((depth, child.lineno, child.end_lineno))
                walk(child, depth + 1)
            else:
                walk(child, depth)

    walk(ast.parse(src), 0)
    return rows


def cells_of(path, src, lines):
    spans = []
    if path.suffix == ".py":
        def kids_of(node):
            out = []
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.stmt):
                    out.append(child)
                else:
                    out.extend(kids_of(child))
            return out

        def emit(node):
            kids = kids_of(node)
            if not kids:
                spans.append([node.lineno, node.end_lineno])
                return
            covered = set()
            for k in kids:
                covered.update(range(k.lineno, k.end_lineno + 1))
                emit(k)
            a = None
            for n in range(node.lineno, node.end_lineno + 1):
                own = n not in covered and bool(lines[n - 1].strip())
                if own and a is None:
                    a = n
                if not own and a is not None:
                    spans.append([a, n - 1])
                    a = None
            if a is not None:
                spans.append([a, node.end_lineno])

        for node in ast.parse(src).body:
            emit(node)
    if not spans:
        a = None
        for n, l in enumerate(lines, 1):
            if l.strip():
                if a is None:
                    a = n
            elif a is not None:
                spans.append([a, n - 1])
                a = None
        if a is not None:
            spans.append([a, len(lines)])
        return [{"lines": [s]} for s in spans]
    covered = {n for a, b in spans for n in range(a, b + 1)}
    extra = []
    a = None
    for n, l in enumerate(lines, 1):
        gap = bool(l.strip()) and n not in covered
        if gap and a is None:
            a = n
        if not gap and a is not None:
            extra.append([a, n - 1])
            a = None
    if a is not None:
        extra.append([a, len(lines)])
    for run in extra:
        nxt = next((s for s in spans if s[0] > run[1]), None)
        if nxt:
            nxt[0] = run[0]
        else:
            spans[-1][1] = run[1]
    return [{"lines": [s]} for s in sorted(spans)]


def merge(spans):
    out = []
    for a, b in sorted(spans):
        if out and a <= out[-1][1] + 1:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def ask(prompt):
    client = boto3.client(
        "bedrock-runtime",
        region_name=os.environ["AWS_REGION"],
        config=Config(connect_timeout=10, read_timeout=600),
    )
    r = client.converse(
        modelId=os.environ["BEDROCK_MODEL_ID"],
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 32000},
    )
    assert r["stopReason"] == "end_turn", f'reply was cut: {r["stopReason"]}'
    raw = r["output"]["message"]["content"][0]["text"]
    return json.loads(raw[raw.index("{"):raw.rindex("}") + 1])


def observe(path, run):
    ok = {str(path), os.path.realpath(path)}
    seen, last, born = {}, {}, {}

    def summary(v):
        try:
            r = repr(v)
        except Exception:
            r = "?"
        if len(r) > 60:
            r = r[:60] + "…"
        t = type(v).__name__
        try:
            return f"{t}[{len(v)}] {r}"
        except TypeError:
            return f"{t} {r}"

    def keep(k, v):
        return not (k.startswith((".", "__", "@")) or callable(v) or isinstance(v, types.ModuleType))

    def tracer(frame, event, arg):
        if frame.f_code.co_filename not in ok:
            return None
        fid = id(frame)
        if event == "call":
            b = born.setdefault(fid, {})
            for k, v in frame.f_locals.items():
                if keep(k, v):
                    b[k] = frame.f_code.co_firstlineno
                    seen.setdefault(b[k], {})[k] = summary(v)
            last[fid] = (frame.f_lineno, dict(frame.f_locals))
            return tracer
        if event in ("line", "return"):
            pline, psnap = last.get(fid, (frame.f_lineno, {}))
            snap = dict(frame.f_locals)
            for k, v in snap.items():
                if (k not in psnap or psnap[k] is not v) and keep(k, v):
                    born.setdefault(fid, {})[k] = pline
                    seen.setdefault(pline, {})[k] = summary(v)
            last[fid] = (frame.f_lineno, snap)
            if event == "return":
                for k, ln in born.get(fid, {}).items():
                    if k in snap and keep(k, snap[k]):
                        seen.setdefault(ln, {})[k] = summary(snap[k])
                last.pop(fid, None)
                born.pop(fid, None)
        return tracer

    argv = sys.argv
    sys.argv = [str(path)] + run
    sys.settrace(tracer)
    try:
        runpy.run_path(str(path), run_name="__main__")
    finally:
        sys.settrace(None)
        sys.argv = argv
    return seen


def check_pass(m, cells, stmts, blank, ess, bad, flow):
    groups = m.get("groups")
    assert isinstance(groups, list) and groups, "no groups"
    assert flow or len(groups) < len(cells) or len(cells) == 1, "the group count must go down"
    at = 1
    for g in groups:
        a, b = g.get("cells") or [0, 0]
        assert a == at, f"group {a}-{b}: it must start at cell {at}"
        assert a <= b <= len(cells), f"group {a}-{b}: bad end"
        assert isinstance(g.get("text"), str) and g["text"].strip(), f"group {a}-{b}: empty text"
        for w in re.findall(r"(?<![.\w])([A-Za-z_][A-Za-z0-9_]*)\(", g["text"]):
            assert w not in bad, f"group {a}-{b}: the text names {w}(), but this block does not call {w}"
        got = set()
        for c in cells[a - 1:b]:
            for x, y in c["lines"]:
                got.update(range(x, y + 1))
        got -= blank
        if b > a and not any("text" in c for c in cells):
            assert len(got) <= 15, (f"group {a}-{b}: {len(got)} non-blank lines is too big for one first-pass text: "
                                    f"split it into more groups at inner statement boundaries")
        got &= ess
        for _, s, e in stmts:
            span = set(range(s, e + 1)) & ess
            hit = got & span
            ins = [str(i) for i, c in enumerate(cells, 1) if all(s <= x and y <= e for x, y in c["lines"])]
            assert not hit or span <= got or got <= span, \
                (f"group {a}-{b}: it cuts the statement {s}-{e}: hold all of its lines, or only lines inside it, or none of them: "
                 f"cells {', '.join(ins)} are the cells inside it")
        at = b + 1
    assert at == len(cells) + 1, f"the last group ends at cell {at - 1}, not at cell {len(cells)}"
    return groups


def lift(groups, cells, layer, flow):
    out = []
    for g in groups:
        a, b = g["cells"]
        kids = cells[a - 1:b]
        if not flow and len(kids) == 1 and "text" in kids[0]:
            out.append(kids[0])
            continue
        node = {"layer": layer, "text": g["text"].strip(), "lines": merge([r for c in kids for r in c["lines"]])}
        if any("text" in c for c in kids):
            node["children"] = kids
        out.append(node)
    return out


def carve(a, b, minus, lines):
    used = {x for s, e in minus for x in range(s, e + 1)}
    spans = []
    run = None
    for i in range(a, b + 2):
        free = i <= b and i not in used
        if free and run is None:
            run = i
        if not free and run is not None:
            spans.append([run, i - 1])
            run = None
    out = []
    for s, e in spans:
        while s <= e and not lines[s - 1].strip():
            s += 1
        while e >= s and not lines[e - 1].strip():
            e -= 1
        if s <= e:
            out.append([s, e])
    return out


def blocks_of(path, src, lines):
    fns = []
    if path.suffix == ".py":
        def grab(node, scope):
            for n in ast.iter_child_nodes(node):
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    a = min([n.lineno] + [d.lineno for d in n.decorator_list])
                    fns.append({"name": ".".join(scope + [n.name]), "span": [a, n.end_lineno], "node": n})
                    grab(n, scope + [n.name])
                else:
                    grab(n, scope)

        grab(ast.parse(src), [])
    blocks = []
    for f in fns:
        inner = [g["span"] for g in fns
                 if g is not f and f["span"][0] <= g["span"][0] and g["span"][1] <= f["span"][1]]
        blocks.append({"name": f["name"], "lines": carve(f["span"][0], f["span"][1], inner, lines), "node": f["node"]})
    out = carve(1, len(lines), [f["span"] for f in fns], lines)
    if out:
        blocks.append({"name": "script", "lines": out, "node": None})
    blocks.sort(key=lambda b: b["lines"][0][0])
    return blocks


def calls_of(block, body, names):
    skip = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    scope = block["name"].split(".") if block["node"] else []
    out = set()

    def resolve(word):
        for k in range(len(scope), -1, -1):
            hit = ".".join(scope[:k] + [word])
            if hit in names:
                return hit
        return None

    def scan(node):
        for c in ast.iter_child_nodes(node):
            if isinstance(c, skip):
                continue
            if isinstance(c, ast.Name):
                hit = resolve(c.id)
                if hit and hit != block["name"]:
                    out.add(hit)
            scan(c)

    for t in [block["node"]] if block["node"] else [n for n in body if not isinstance(n, skip)]:
        scan(t)
    return sorted(out)


def layers_of(blocks, calls):
    idx, low, on, st, comp = {}, {}, set(), [], {}
    k = [0]

    def strong(v):
        idx[v] = low[v] = k[0]
        k[0] += 1
        st.append(v)
        on.add(v)
        for w in calls[v]:
            if w not in idx:
                strong(w)
                low[v] = min(low[v], low[w])
            elif w in on:
                low[v] = min(low[v], idx[w])
        if low[v] == idx[v]:
            while True:
                w = st.pop()
                on.discard(w)
                comp[w] = v
                if w == v:
                    break

    for b in blocks:
        if b["name"] not in idx:
            strong(b["name"])
    edges = {}
    for b in blocks:
        for w in calls[b["name"]]:
            if comp[w] != comp[b["name"]]:
                edges.setdefault(comp[b["name"]], set()).add(comp[w])
    h = {}

    def height(c):
        if c not in h:
            h[c] = 1 + max((height(d) for d in edges.get(c, ())), default=0)
        return h[c]

    return {b["name"]: height(comp[b["name"]]) for b in blocks}


def nodes_of(tree):
    out = []

    def walk(ns):
        for t in ns:
            out.append(t)
            if t.get("children"):
                walk(t["children"])

    walk(tree)
    return out


def number(tree):
    for i, t in enumerate(tree, 1):
        t["id"] = f"F{i:02d}"
        k = [0]

        def walk(ns):
            for c in ns:
                k[0] += 1
                c["id"] = f'{t["id"]}.{k[0]}'
                if c.get("children"):
                    walk(c["children"])

        walk(t.get("children") or [])


def owner_of(tree):
    owner = {}
    for t in nodes_of(tree):
        if not t.get("children"):
            for a, b in t["lines"]:
                for n in range(a, b + 1):
                    owner[n] = t["id"]
    return owner


def links(path, owner):
    if path.suffix != ".py":
        return []
    p = path.resolve()
    script = jedi.Script(path=p)
    rows = []
    for d in script.get_names():
        if any(g.module_path != p for g in d.goto()):
            continue
        src = owner.get(d.line)
        if src is None:
            continue
        used = sorted({owner[r.line] for r in script.get_references(d.line, d.column, scope="file")
                       if r.line in owner and owner[r.line] != src})
        if used:
            rows.append({"name": d.name, "def": src, "used": used})
    return rows


def row_of(i, c, lines):
    spans = ", ".join(f"{a}-{b}" for a, b in c["lines"])
    text = c.get("text")
    if text:
        return f"{i}: lines {spans} — {text}"
    return f"{i}: lines {spans} | {lines[c['lines'][0][0] - 1].strip()}"


def write_node(t, ind):
    head = f'{ind}{{"id": {json.dumps(t["id"])}, '
    if "name" in t:
        head += (f'"name": {json.dumps(t["name"])}, "layer": {t["layer"]}, "calls": {json.dumps(t["calls"])}, '
                 f'"takes": {json.dumps(t["takes"], ensure_ascii=False)}, "gives": {json.dumps(t["gives"], ensure_ascii=False)}, ')
    else:
        head += f'"layer": {t["layer"]}, '
    head += (f'"text": {json.dumps(t["text"], ensure_ascii=False)}, '
             f'"lines": {json.dumps(t["lines"])}')
    if not t.get("children"):
        return head + "}"
    kids = ",\n".join(write_node(c, ind + "  ") for c in t["children"])
    return f'{head}, "children": [\n{kids}\n{ind}]}}'


def write_map(path, m):
    rows = ",\n    ".join(json.dumps(r, ensure_ascii=False) for r in m["links"])
    links_part = f"[\n    {rows}\n  ]" if rows else "[]"
    trows = ",\n    ".join(json.dumps(r, ensure_ascii=False) for r in m["terms"])
    terms_part = f"[\n    {trows}\n  ]" if trows else "[]"
    tree = ",\n".join(write_node(t, "    ") for t in m["map"])
    path.write_text('{\n  "file": ' + json.dumps(m["file"]) + ',\n  "links": ' + links_part
                    + ',\n  "terms": ' + terms_part + ',\n  "map": [\n' + tree + '\n  ]\n}\n', encoding="utf-8")


def one_pass(cells, name, code, lines, stext, sv, stmts, blank, ess, layer, label, span, ctx, bad, flow, final):
    rows = "\n".join(row_of(i, c, lines) for i, c in enumerate(cells, 1))
    base = PROMPT.format(name=name, code=code, block=label, span=span, ctx=ctx, cells=rows, n=len(cells), stmts=stext, seen=sv)
    if flow:
        base += FLOW
    if final:
        base += ("\n\nThis is the final pass. Return exactly one group that holds all cells. "
                 "The cell texts in order are the execution flow of the block. "
                 'The group\'s text is the signature of the block: name(arguments) -> result, then one clause after " — " '
                 "that states the effect of the whole block. "
                 "When the result is a data structure, the text adds one more line: example: one small instance of "
                 "the shape with the real keys, elided with … where the shape repeats. "
                 "The top-level script block starts with the word script instead of a signature. "
                 "The text does not repeat the calls: the cell texts hold them. "
                 'The group also gets "takes" and "gives": short noun phrases that name the input and the output.\n'
                 'Example: {"groups": [{"cells": [1, 6], "takes": "a .py file path from the command line", '
                 '"gives": "map.json next to the source file", '
                 '"text": "main(path) -> map.json — one map for the whole file\\nexample: {\\"file\\": \\"x.py\\", '
                 '\\"links\\": […], \\"terms\\": […], \\"map\\": [{\\"id\\": \\"F01\\", \\"text\\": …, \\"children\\": […]}]}"}]}')
    note = ""
    errs = []
    m = None
    for attempt in range(8):
        try:
            m = ask(base + note)
            groups = check_pass(m, cells, stmts, blank, ess, bad, flow)
            if flow:
                assert len(groups) >= 2, "the flow needs at least 2 beats"
                for g in groups:
                    a, b = g["cells"]
                    t = g["text"]
                    assert "\n" not in t, f"group {a}-{b}: a flow line is one single line, no \\n"
                    if " = " not in t:
                        continue
                    left, right = t.split(" = ", 1)
                    names = re.findall(r"[A-Za-z_][\w.]*", left)
                    assert len(names) <= 2, f"group {a}-{b}: at most two names left of =: keep the ones the story turns on"
                    low = right.lower()
                    assert low.count(" and ") <= 1, f"group {a}-{b}: one role per line, at most one and: split the beat or drop names"
                    for w in names:
                        forms = {w.lower()}
                        if w.lower().endswith("s"):
                            forms.add(w.lower()[:-1])
                        for fm in forms:
                            assert not re.search(rf"\b{re.escape(fm)}\b", low), \
                                f'group {a}-{b}: the role repeats the name "{w}": say what the thing is, not its name'
            if final:
                g = groups[0]
                assert len(groups) == 1, "this is the final pass: return exactly one group that holds all cells"
                assert isinstance(g.get("takes"), str) and g["takes"].strip(), "the final group needs a takes field"
                assert isinstance(g.get("gives"), str) and g["gives"].strip(), "the final group needs a gives field"
                if label.endswith("()"):
                    assert g["text"].strip().startswith(label[:-2] + "("), \
                        f"the final text must start with the signature {label[:-2]}(...)"
                node = {"layer": layer, "text": g["text"].strip(), "takes": g["takes"].strip(),
                        "gives": g["gives"].strip(), "lines": merge([r for c in cells for r in c["lines"]])}
                if len(cells) > 1:
                    node["children"] = cells
                return [node]
            return lift(groups, cells, layer, flow)
        except (AssertionError, TypeError, ValueError, KeyError) as e:
            print(f"retry {attempt + 1} [{label}]: {e}")
            errs.append(f"- {e}")
            note = (f"\n\nYour last answer:\n{json.dumps(m)}\n\n"
                    f"It broke a rule: {e}. Repair it and return the full corrected JSON.\n"
                    f"Rules your answers broke so far, do not break them again:\n" + "\n".join(errs))
    sys.exit("no valid pass after 8 tries")


def terms_of(name, code, lines, tree):
    nodes = nodes_of(tree)
    texts = "\n".join(f'{t["id"]}: {t["text"]}' for t in nodes)
    low = [t["text"].lower() for t in nodes]
    base = TERMS.format(name=name, code=code, texts=texts)
    note = ""
    errs = []
    m = None
    for attempt in range(8):
        try:
            m = ask(base + note)
            terms = m.get("terms")
            assert isinstance(terms, list), "no terms list"
            seen = set()
            out = []
            for t in terms:
                w = t.get("term")
                assert isinstance(w, str) and w.strip(), "empty term"
                w = w.strip()
                assert w.lower() not in seen, f"duplicate term: {w}"
                seen.add(w.lower())
                assert any(w.lower() in x for x in low), f"no text uses the term: {w}"
                assert isinstance(t.get("text"), str) and t["text"].strip(), f"the term {w} has no text"
                d = t.get("defs")
                assert isinstance(d, list) and d, f"the term {w} has no defs"
                for r in d:
                    a, b = r
                    assert 1 <= a <= b <= len(lines), f"the term {w} has the bad range {r}"
                out.append({"term": w, "text": t["text"].strip(), "defs": d})
            return out
        except (AssertionError, TypeError, ValueError, KeyError) as e:
            print(f"retry {attempt + 1} [terms]: {e}")
            errs.append(f"- {e}")
            note = (f"\n\nYour last answer:\n{json.dumps(m)}\n\n"
                    f"It broke a rule: {e}. Repair it and return the full corrected JSON.\n"
                    f"Rules your answers broke so far, do not break them again:\n" + "\n".join(errs))
    sys.exit("no valid terms after 8 tries")


def compile_block(bl, cells, name, code, lines, stmts, blank, ess, ctx, bad, seen):
    bstmts = [s for s in stmts if any(x <= s[1] and s[2] <= y for x, y in bl["lines"])]
    stext = ""
    if bstmts:
        stext = ("Statements as line ranges, a child indented under its parent. A group holds all of a statement or none of it:\n"
                 + "\n".join("  " * d + f"{a}-{b}" for d, a, b in bstmts) + "\n\n")
    srows = [f'{ln}| ' + " ; ".join(f"{k} = {v}" for k, v in sorted(seen[ln].items()))
             for ln in sorted(seen) if any(x <= ln <= y for x, y in bl["lines"])]
    sv = ""
    if srows:
        sv = ("Values one real run bound, as line| name = value. Use them to say what a name holds and for the example shapes:\n"
              + "\n".join(srows) + "\n\n")
    label = bl["name"].split(".")[-1] + "()" if bl["node"] else "the top-level script code"
    span = ", ".join(f"{a}-{b}" for a, b in bl["lines"])
    layer = 0
    flowed = False
    while len(cells) > 1 or "takes" not in cells[0]:
        layer += 1
        n = len(cells)
        staged = all("text" in c for c in cells)
        flow = staged and not flowed and len(cells) >= 4
        final = staged and not flow
        cells = one_pass(cells, name, code, lines, stext, sv, bstmts, blank, ess, layer, label, span, ctx, bad, flow, final)
        flowed = flowed or flow
        print(f"{bl['name']} pass {layer}: {n} -> {len(cells)}")
    return cells[0]


def main():
    args = sys.argv[1:]
    run = []
    if "--" in args:
        at = args.index("--")
        args, run = args[:at], args[at + 1:]
    path = Path(args[0])
    seen = observe(path, run) if run else {}
    src = path.read_text(encoding="utf-8")
    lines = src.splitlines()
    assert any(l.strip() for l in lines), f"{path.name} is empty"
    code = "\n".join(f"{n}|{l}" for n, l in enumerate(lines, 1))
    cells = cells_of(path, src, lines)
    stmts = statements(path, src)
    blank = {n for n, l in enumerate(lines, 1) if not l.strip()}
    ess = set()
    for d, a, b in stmts:
        if not any(s >= a and e <= b and (s, e) != (a, b) for _, s, e in stmts):
            ess.update(range(a, b + 1))
    ess -= blank
    blocks = blocks_of(path, src, lines)
    body = ast.parse(src).body if path.suffix == ".py" else []
    names = {b["name"] for b in blocks if b["node"]}
    calls = {b["name"]: calls_of(b, body, names) for b in blocks}
    lay = layers_of(blocks, calls)
    parts = {b["name"]: [] for b in blocks}
    for c in cells:
        home = next(b["name"] for b in blocks
                    if all(any(x <= a and e <= y for x, y in b["lines"]) for a, e in c["lines"]))
        parts[home].append(c)
    done = {}
    for bl in sorted(blocks, key=lambda b: (lay[b["name"]], b["lines"][0][0])):
        ctx = "".join(f'{n.split(".")[-1]}() — takes {done[n]["takes"]}, gives {done[n]["gives"]} — {done[n]["text"]}\n'
                      for n in calls[bl["name"]] if n in done)
        if ctx:
            ctx = "Functions this block calls, compiled already. Their one-line meanings:\n" + ctx + "\n"
        bad = ({n.split(".")[-1] for n in names}
               - {c.split(".")[-1] for c in calls[bl["name"]]} - {bl["name"].split(".")[-1]})
        root = compile_block(bl, parts[bl["name"]], path.name, code, lines, stmts, blank, ess, ctx, bad, seen)
        root["name"] = bl["name"]
        root["layer"] = lay[bl["name"]]
        root["calls"] = calls[bl["name"]]
        root["lines"] = bl["lines"]
        done[bl["name"]] = root
    tree = sorted(done.values(), key=lambda t: t["lines"][0][0])
    number(tree)
    owner = owner_of(tree)
    m = {"file": path.name, "links": links(path, owner), "terms": terms_of(path.name, code, lines, tree), "map": tree}
    out = path.parent / "map.json"
    write_map(out, m)
    print(f"{len(blocks)} blocks, {len(nodes_of(tree))} texts, {len(m['links'])} links, {len(m['terms'])} terms -> {out}")


if __name__ == "__main__":
    main()
