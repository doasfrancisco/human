import ast
import json
import os
import sys
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

{stmts}Rules:
1. The groups cover the cells in order: the first group starts at cell 1, every group is a contiguous run of cells, each group starts one after the end of the group before it, and the last group ends at cell {n}.
2. Return fewer groups than cells. One group that holds all cells is legal when the block does one small thing. One group for one cell is legal when the block has only one cell.
3. A group of one cell is legal when a cell does not belong with a neighbor. Its text may stay the old text.
4. Every group gets one text: one simple sentence with one main verb that says what its lines do. It never copies a code line.
5. Write the text in ASD-STE100 Simplified Technical English: short, active, plain words. No summary jargon.
6. The first word of a text is the name the group defines or uses. A function name always gets parentheses, like ask() or check(). A constant name gets none. A stage of a function starts with that function's name. Never start a text with "The".
7. A prompt or template string gets a text that says what it instructs, not how it is built.
8. A group holds all of a statement or none of it. A header line or an else line may join the group on either side.
9. On the first pass, a group is one step: at most 15 non-blank lines, unless the group is one single cell. A small block gets one group. A big block gets one group per stage, cut at its inner statement boundaries. Never group the lines before a loop or branch with only a part of it.
10. A text names the concrete things its lines touch: the names, the files, the keys, the counts. It never says only what kind of thing the code is.
11. When the lines call a compiled function from the list above, the text names it with parentheses. It does not explain the inside of that function.

Texts from a good map, in the exact voice to use:
"imports bring in the tools: JSON, the environment, paths, the Bedrock client, and .env loading."
"load_dotenv() reads the credentials from the .env file next to the script."
"write_json() writes a list of rows to a file as JSON, one row per line."
"check() verifies the map: no duplicate id, no cut statement, no overlap, and full coverage."
"main() reads the file, asks the model for the tree, checks it, and writes map.json."
"main()'s first stage reads the source file and numbers its lines."

Return one JSON object only, no code fences:
{{"groups": [{{"cells": [1, 3], "text": "setup prepares the tools and the prompt."}}, {{"cells": [4, 4], "text": "load_dotenv() reads the credentials from the .env file next to the script."}}]}}"""


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


def check_pass(m, cells, stmts, blank, ess):
    groups = m.get("groups")
    assert isinstance(groups, list) and groups, "no groups"
    assert len(groups) < len(cells) or len(cells) == 1, "the group count must go down"
    at = 1
    for g in groups:
        a, b = g.get("cells") or [0, 0]
        assert a == at, f"group {a}-{b}: it must start at cell {at}"
        assert a <= b <= len(cells), f"group {a}-{b}: bad end"
        assert isinstance(g.get("text"), str) and g["text"].strip(), f"group {a}-{b}: empty text"
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


def lift(groups, cells, layer):
    out = []
    for g in groups:
        a, b = g["cells"]
        kids = cells[a - 1:b]
        if len(kids) == 1 and "text" in kids[0]:
            out.append(kids[0])
            continue
        node = {"layer": layer, "text": g["text"].strip(), "lines": merge([r for c in kids for r in c["lines"]])}
        if any("text" in c for c in kids):
            node["children"] = kids
        out.append(node)
    return out


def blocks_of(path, src, lines):
    fns = []
    if path.suffix == ".py":
        for n in ast.parse(src).body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                a = min([n.lineno] + [d.lineno for d in n.decorator_list])
                fns.append({"name": n.name, "lines": [[a, n.end_lineno]], "node": n})
    used = {x for f in fns for a, b in f["lines"] for x in range(a, b + 1)}
    spans = []
    a = None
    for i in range(1, len(lines) + 2):
        free = i <= len(lines) and i not in used
        if free and a is None:
            a = i
        if not free and a is not None:
            spans.append([a, i - 1])
            a = None
    out = []
    for a, b in spans:
        while a <= b and not lines[a - 1].strip():
            a += 1
        while b >= a and not lines[b - 1].strip():
            b -= 1
        if a <= b:
            out.append([a, b])
    blocks = fns[:]
    if out:
        blocks.append({"name": "script", "lines": out, "node": None})
    blocks.sort(key=lambda b: b["lines"][0][0])
    return blocks


def calls_of(block, body, names):
    skip = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    tops = [block["node"]] if block["node"] else [n for n in body if not isinstance(n, skip)]
    out = set()
    for t in tops:
        for x in ast.walk(t):
            if isinstance(x, ast.Name) and x.id in names and x.id != block["name"]:
                out.add(x.id)
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
        head += f'"name": {json.dumps(t["name"])}, "layer": {t["layer"]}, "calls": {json.dumps(t["calls"])}, '
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
    tree = ",\n".join(write_node(t, "    ") for t in m["map"])
    path.write_text('{\n  "file": ' + json.dumps(m["file"]) + ',\n  "links": ' + links_part
                    + ',\n  "map": [\n' + tree + '\n  ]\n}\n', encoding="utf-8")


def one_pass(cells, name, code, lines, stext, stmts, blank, ess, layer, label, span, ctx, final):
    rows = "\n".join(row_of(i, c, lines) for i, c in enumerate(cells, 1))
    base = PROMPT.format(name=name, code=code, block=label, span=span, ctx=ctx, cells=rows, n=len(cells), stmts=stext)
    if final:
        base += ("\n\nThis is the final pass. Return exactly one group that holds all cells. "
                 "Its text is the one sentence for the whole block.")
    note = ""
    errs = []
    m = None
    for attempt in range(8):
        try:
            m = ask(base + note)
            groups = check_pass(m, cells, stmts, blank, ess)
            assert not final or len(groups) == 1, "this is the final pass: return exactly one group that holds all cells"
            return lift(groups, cells, layer)
        except (AssertionError, TypeError, ValueError, KeyError) as e:
            print(f"retry {attempt + 1} [{label}]: {e}")
            errs.append(f"- {e}")
            note = (f"\n\nYour last answer:\n{json.dumps(m)}\n\n"
                    f"It broke a rule: {e}. Repair it and return the full corrected JSON.\n"
                    f"Rules your answers broke so far, do not break them again:\n" + "\n".join(errs))
    sys.exit("no valid pass after 8 tries")


def compile_block(bl, cells, name, code, lines, stmts, blank, ess, ctx):
    bstmts = [s for s in stmts if any(x <= s[1] and s[2] <= y for x, y in bl["lines"])]
    stext = ""
    if bstmts:
        stext = ("Statements as line ranges, a child indented under its parent. A group holds all of a statement or none of it:\n"
                 + "\n".join("  " * d + f"{a}-{b}" for d, a, b in bstmts) + "\n\n")
    label = bl["name"] + "()" if bl["node"] else "the top-level script code"
    span = ", ".join(f"{a}-{b}" for a, b in bl["lines"])
    layer = 0
    while len(cells) > 1 or "text" not in cells[0]:
        layer += 1
        n = len(cells)
        final = all("text" in c for c in cells)
        cells = one_pass(cells, name, code, lines, stext, bstmts, blank, ess, layer, label, span, ctx, final)
        print(f"{bl['name']} pass {layer}: {n} -> {len(cells)}")
    return cells[0]


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
    for bl in sorted(blocks, key=lambda b: (lay[b["name"]], b["lines"][0][0])):
        ctx = "".join(f'{n}() — {done[n]["text"]}\n' for n in calls[bl["name"]] if n in done)
        if ctx:
            ctx = "Functions this block calls, compiled already. Their one-line meanings:\n" + ctx + "\n"
        root = compile_block(bl, parts[bl["name"]], path.name, code, lines, stmts, blank, ess, ctx)
        root["name"] = bl["name"]
        root["layer"] = lay[bl["name"]]
        root["calls"] = calls[bl["name"]]
        root["lines"] = bl["lines"]
        done[bl["name"]] = root
    tree = sorted(done.values(), key=lambda t: t["lines"][0][0])
    number(tree)
    owner = owner_of(tree)
    m = {"file": path.name, "links": links(path, owner), "map": tree}
    out = path.parent / "map.json"
    write_map(out, m)
    print(f"{len(blocks)} blocks, {len(nodes_of(tree))} texts, {len(m['links'])} links -> {out}")


if __name__ == "__main__":
    main()
