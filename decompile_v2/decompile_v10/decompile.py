import ast
import json
import re
import subprocess
import sys
from pathlib import Path

import jedi

PROMPT = """You are explaining one block of a code file to a person, the way you would explain it if they asked you "what does this do?". The input is the file, one line per number, and the cells of one block of that file, in file order. Return one root line for the whole block and the beats of its story.

File: {name}
{code}

You are explaining the block {block}, lines {span}. Ignore all other lines.

{ctx}Cells of the block:
{cells}

{stmts}Beat rules:
1. The beats cover the cells in order: the first beat starts at cell 1, every beat is a contiguous run of cells, each beat starts one after the end of the beat before it, and the last beat ends at cell {n}.
2. Each beat is one step of the explanation: what this part does and why the block needs it, in plain words a reader who never saw the code understands. Use the real names of variables and functions when they help the reader. One line is usually enough; add lines (split with \\n) when one line cannot carry the step.
3. When a beat lists several parallel things — imports, tools, fields, options — do not weave them into one sentence. Write a headline line that ends with ":", then one thing per line: its name, then what it is for. A blank line (\\n\\n) may separate the headline or a group that stands apart.
4. When a beat sets one name, shape it as: name = what it holds, in plain words. Put any extra clause that says why on its own line below the first, not woven into it.
5. When the beat's lines call a function or class that is defined in this file, write its exact name (like cells_of) somewhere in the beat text, so the reader can follow that name into the block's own story one layer down.
6. Top beat to bottom beat reads as one story: the block's work from its input to its result. Merge adjacent cells into one beat when they serve one step; split where the story turns.
7. A beat holds all of a statement or none of it. Never cut a loop or a branch in the middle.
8. A small helper deserves an honest explanation of what it is for, not a mechanical restatement of its lines.
9. When the lines call a compiled function from the list above, speak at its level: use its one-line meaning, do not re-explain its inside.

Root rules:
10. root.text is the signature of the block: name(arguments) -> result, then one clause after " — " that says what the whole block does for its caller. The top-level script block starts with the word script instead of a signature.
11. root.takes and root.gives are short noun phrases that name the input and the output.

Story rules:
12. story is the explanation a person reads; the beats are only the bridge to the code. The reader sees root.text directly above the story, so the story never restates it. Its shape, in this order: one small worked example — a tiny concrete input and what the block makes of it, with real values that stay consistent — then at most 3 short sentences for rules and edge cases the example does not show. Shorter is better.
13. Choose the example so it shows the one rule a reader would guess wrong without it. An example that shows only the obvious case teaches nothing.
14. The example is one or two short lines: the input, then the result. Never a formatted dump. Its names are real names from this file, or plainly generic ones like f, x and small numbers. Never a plausible name that does not exist in this file.
15. Story sentences have 20 words or fewer, one idea per sentence, active voice. No metaphors: never words like carve, glue, promise.
16. Every technical term the story uses is a name from the code, or is defined: in the story at first use, or in terms with a plain one-line meaning.
17. terms lists those defined words as {{"term": ..., "meaning": ...}}. Each term appears verbatim in the story. An empty list is legal.

A gold story, for a function digits(text) that collects the digit characters of a string as ints. Imitate this shape — example first, then short rules:
Example: digits("ab12c3") gives [1, 2, 3].
Letters and spaces are dropped. When text has no digits, the result is an empty list.

Return one JSON object only, no code fences:
{{"root": {{"text": "digits(text) -> list of ints — collects every digit character in the text as a number", "takes": "a string", "gives": "the digit values in order"}}, "story": "Example: digits(\\"ab12c3\\") gives [1, 2, 3].\\nLetters and spaces are dropped. When text has no digits, the result is an empty list.", "terms": [], "beats": [{{"cells": [1, 2], "text": "walk the characters and keep only the digits"}}, {{"cells": [3, 3], "text": "hand the collected digits back"}}]}}"""


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


CALLS = [0]


def ask_claude(prompt):
    CALLS[0] += 1
    r = subprocess.run(["claude", "-p", prompt, "--output-format", "json"],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stderr[-500:]
    raw = json.loads(r.stdout)["result"]
    return json.loads(raw[raw.index("{"):raw.rindex("}") + 1])


def check_block(m, cells, stmts, ess, label):
    root = m.get("root")
    assert isinstance(root, dict), "no root object"
    for k in ("text", "takes", "gives"):
        assert isinstance(root.get(k), str) and root[k].strip(), f"the root needs a {k} field"
    if label.endswith("()"):
        assert root["text"].strip().startswith(label[:-2] + "("), \
            f"the root text must start with the signature {label[:-2]}(...)"
    story = m.get("story")
    assert isinstance(story, str) and story.strip(), "no story"
    terms = m.get("terms")
    assert isinstance(terms, list), "terms must be a list, empty is legal"
    for t in terms:
        assert isinstance(t, dict) and isinstance(t.get("term"), str) and t["term"].strip(), "a term needs a term string"
        assert isinstance(t.get("meaning"), str) and t["meaning"].strip(), f'the term {t.get("term")} needs a meaning'
        assert t["term"].strip() in story, f'the term "{t["term"].strip()}" does not appear verbatim in the story'
    beats = m.get("beats")
    assert isinstance(beats, list) and beats, "no beats"
    at = 1
    for g in beats:
        a, b = g.get("cells") or [0, 0]
        assert a == at, f"beat {a}-{b}: it must start at cell {at}"
        assert a <= b <= len(cells), f"beat {a}-{b}: bad end"
        assert isinstance(g.get("text"), str) and g["text"].strip(), f"beat {a}-{b}: empty text"
        got = set()
        for c in cells[a - 1:b]:
            for x, y in c["lines"]:
                got.update(range(x, y + 1))
        got &= ess
        for _, s, e in stmts:
            span = set(range(s, e + 1)) & ess
            hit = got & span
            ins = [str(i) for i, c in enumerate(cells, 1) if all(s <= x and y <= e for x, y in c["lines"])]
            assert not hit or span <= got or got <= span, \
                (f"beat {a}-{b}: it cuts the statement {s}-{e}: hold all of its lines, or only lines inside it, or none of them: "
                 f"cells {', '.join(ins)} are the cells inside it")
        at = b + 1
    assert at == len(cells) + 1, f"the last beat ends at cell {at - 1}, not at cell {len(cells)}"
    return root, story, terms, beats


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
    return f"{i}: lines {spans} | {lines[c['lines'][0][0] - 1].strip()}"


def write_node(t, ind):
    head = f'{ind}{{"id": {json.dumps(t["id"])}, '
    if "name" in t:
        head += (f'"name": {json.dumps(t["name"])}, "layer": {t["layer"]}, "calls": {json.dumps(t["calls"])}, '
                 f'"takes": {json.dumps(t["takes"], ensure_ascii=False)}, "gives": {json.dumps(t["gives"], ensure_ascii=False)}, ')
        if "story" in t:
            head += f'"story": {json.dumps(t["story"], ensure_ascii=False)}, '
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


def compile_block(bl, cells, name, code, lines, stmts, ess, ctx):
    bstmts = [s for s in stmts if any(x <= s[1] and s[2] <= y for x, y in bl["lines"])]
    stext = ""
    if bstmts:
        stext = ("Statements as line ranges, a child indented under its parent. A beat holds all of a statement or none of it:\n"
                 + "\n".join("  " * d + f"{a}-{b}" for d, a, b in bstmts) + "\n\n")
    label = bl["name"].split(".")[-1] + "()" if bl["node"] else "the top-level script code"
    span = ", ".join(f"{a}-{b}" for a, b in bl["lines"])
    rows = "\n".join(row_of(i, c, lines) for i, c in enumerate(cells, 1))
    base = PROMPT.format(name=name, code=code, block=label, span=span, ctx=ctx, cells=rows, n=len(cells), stmts=stext)
    note = ""
    errs = []
    m = None
    for attempt in range(8):
        try:
            m = ask_claude(base + note)
            root, story, terms, beats = check_block(m, cells, bstmts, ess, label)
            node = {"text": root["text"].strip(), "takes": root["takes"].strip(), "gives": root["gives"].strip(),
                    "story": story.strip(), "lines": merge([r for c in cells for r in c["lines"]])}
            if len(cells) > 1:
                node["children"] = [{"layer": 1, "text": g["text"].strip(),
                                     "lines": merge([r for c in cells[g["cells"][0] - 1:g["cells"][1]] for r in c["lines"]])}
                                    for g in beats]
            print(f"{bl['name']}: {len(cells)} cells -> {len(beats)} beats, {len(terms)} terms")
            return node, [{"term": t["term"].strip(), "meaning": t["meaning"].strip()} for t in terms]
        except (AssertionError, TypeError, ValueError, KeyError) as e:
            print(f"retry {attempt + 1} [{label}]: {e}")
            errs.append(f"- {e}")
            note = (f"\n\nYour last answer:\n{json.dumps(m)}\n\n"
                    f"It broke a rule: {e}. Repair it and return the full corrected JSON.\n"
                    f"Rules your answers broke so far, do not break them again:\n" + "\n".join(errs))
    sys.exit(f"no valid pass after 8 tries [{bl['name']}]")


def main():
    path = Path(sys.argv[1])
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
    tout = []
    tseen = set()
    for bl in sorted(blocks, key=lambda b: (lay[b["name"]], b["lines"][0][0])):
        ctx = "".join(f'{n.split(".")[-1]}() — takes {done[n]["takes"]}, gives {done[n]["gives"]} — {done[n]["text"]}\n'
                      for n in calls[bl["name"]] if n in done)
        if ctx:
            ctx = "Functions this block calls, explained already. Their one-line meanings:\n" + ctx + "\n"
        root, bterms = compile_block(bl, parts[bl["name"]], path.name, code, lines, stmts, ess, ctx)
        for t in bterms:
            if t["term"] not in tseen:
                tseen.add(t["term"])
                tout.append({"term": t["term"], "meaning": t["meaning"], "block": bl["name"]})
        root["name"] = bl["name"]
        root["layer"] = lay[bl["name"]]
        root["calls"] = calls[bl["name"]]
        root["lines"] = bl["lines"]
        done[bl["name"]] = root
    tree = sorted(done.values(), key=lambda t: t["lines"][0][0])
    number(tree)
    owner = owner_of(tree)
    m = {"file": path.name, "links": links(path, owner), "terms": tout, "map": tree}
    out = path.parent / "map.json"
    write_map(out, m)
    print(f"{len(blocks)} blocks, {len(nodes_of(tree))} texts, {len(m['links'])} links, "
          f"{len(tout)} terms, {CALLS[0]} claude calls -> {out}")


if __name__ == "__main__":
    main()
