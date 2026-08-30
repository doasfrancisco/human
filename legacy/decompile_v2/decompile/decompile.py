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

PROMPT = """You are a decompiler. You go up one layer of abstraction per call. The input is one code file, one line per number, and the cells of the current layer in file order. Merge adjacent cells into fewer groups and give each group one text.

File: {name}
{code}

Cells of the current layer:
{cells}

{stmts}Rules:
1. The groups cover the cells in order: the first group starts at cell 1, every group is a contiguous run of cells, each group starts one after the end of the group before it, and the last group ends at cell {n}.
2. Return fewer groups than cells. Merge the cells that do one thing together.
3. A group of one cell is legal when a cell does not belong with a neighbor. Its text may stay the old text.
4. Every group gets one text: one simple sentence with one main verb that says what its lines do. It never copies a code line.
5. Write the text in ASD-STE100 Simplified Technical English: short, active, plain words. No summary jargon.
6. The first word of a text is the name the group defines or uses. A function name always gets parentheses, like ask() or check(). A constant name gets none. A stage of a function starts with that function's name. Never start a text with "The".
7. A prompt or template string gets a text that says what it instructs, not how it is built.
8. A group holds all of a statement or none of it. Never put a part of one function with a part of the next function in one group. A header line or an else line may join the group on either side.
9. On the first pass, a group is one step: at most 15 non-blank lines, unless the group is one single cell. A small function gets one group. A big function or block gets one group per stage, cut at its inner statement boundaries. Never group the lines before a block with only a part of the block.
10. A text names the concrete things its lines touch: the names, the files, the keys, the counts. It never says only what kind of thing the code is.

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
            assert len(got) <= 15, f"group {a}-{b}: {len(got)} non-blank lines is too big for one first-pass text"
        got &= ess
        for _, s, e in stmts:
            span = set(range(s, e + 1)) & ess
            hit = got & span
            assert not hit or span <= got or got <= span, \
                f"group {a}-{b}: it cuts the statement {s}-{e}: hold all of its lines, or only lines inside it, or none of them"
        at = b + 1
    assert at == len(cells) + 1, f"the last group ends at cell {at - 1}, not at cell {len(cells)}"
    return groups


def lift(groups, cells):
    out = []
    for g in groups:
        a, b = g["cells"]
        kids = cells[a - 1:b]
        node = {"text": g["text"].strip(), "lines": merge([r for c in kids for r in c["lines"]])}
        if any("text" in c for c in kids):
            node["children"] = kids
        out.append(node)
    return out


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
    k = [0]

    def walk(ns):
        for t in ns:
            k[0] += 1
            t["id"] = f"T{k[0]:02d}"
            if t.get("children"):
                walk(t["children"])

    walk(tree)


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
    head = (f'{ind}{{"id": {json.dumps(t["id"])}, '
            f'"text": {json.dumps(t["text"], ensure_ascii=False)}, '
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


def top_chunks(cells, stmts, blank):
    tops = [(a, b) for d, a, b in stmts if d == 0]
    big = {t for t in tops if len(set(range(t[0], t[1] + 1)) - blank) > 15}

    def top_of(c):
        x = c["lines"][0][0]
        for t in tops:
            if t[0] <= x <= t[1]:
                return t
        return (x, x)

    out = []
    prev = None
    for c in cells:
        t = top_of(c)
        if out and (t == prev or (t not in big and prev not in big)):
            out[-1].append(c)
        else:
            out.append([c])
        prev = t
    return out


def one_pass(cells, name, code, lines, stext, stmts, blank, ess):
    rows = "\n".join(row_of(i, c, lines) for i, c in enumerate(cells, 1))
    base = PROMPT.format(name=name, code=code, cells=rows, n=len(cells), stmts=stext)
    note = ""
    errs = []
    for attempt in range(8):
        m = ask(base + note)
        try:
            groups = check_pass(m, cells, stmts, blank, ess)
            return lift(groups, cells)
        except (AssertionError, TypeError, ValueError, KeyError) as e:
            print(f"retry {attempt + 1}: {e}")
            errs.append(f"- {e}")
            note = (f"\n\nYour last answer:\n{json.dumps(m)}\n\n"
                    f"It broke a rule: {e}. Repair it and return the full corrected JSON.\n"
                    f"Rules your answers broke so far, do not break them again:\n" + "\n".join(errs))
    sys.exit("no valid pass after 8 tries")


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
    stext = ""
    if stmts:
        stext = ("Statements as line ranges, a child indented under its parent. A group holds all of a statement or none of it:\n"
                 + "\n".join("  " * d + f"{a}-{b}" for d, a, b in stmts) + "\n\n")
    layer = 0
    while len(cells) > 1 or "text" not in cells[0]:
        layer += 1
        n = len(cells)
        if "text" not in cells[0]:
            nxt = []
            for chunk in top_chunks(cells, stmts, blank):
                nxt += one_pass(chunk, path.name, code, lines, stext, stmts, blank, ess)
            cells = nxt
        else:
            cells = one_pass(cells, path.name, code, lines, stext, stmts, blank, ess)
        print(f"pass {layer}: {n} -> {len(cells)}")
    number(cells)
    owner = owner_of(cells)
    m = {"file": path.name, "links": links(path, owner), "map": cells}
    out = path.parent / "map.json"
    write_map(out, m)
    print(f"{len(nodes_of(cells))} texts, {len(m['links'])} links -> {out}")


if __name__ == "__main__":
    main()
