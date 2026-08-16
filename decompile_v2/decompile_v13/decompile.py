import ast
import json
import re
import subprocess
import sys
from pathlib import Path

import jedi

PROMPT = """You are explaining one block of a code file to a person, the way you would explain it if they asked you "what does this do?". The input is the file, one line per number. Return one root line for the whole block and one body, the explanation one layer down.

File: {name}
{code}

You are explaining the block {block}, lines {span}. Ignore all other lines.

{ctx}Root rules:
1. The root is the answer line: 12 words or less, counted by spaces. It names the subject and the effect. It is the answer a person keeps, not a description of the code.
2. Bad root: "compile_block builds the prompt and calls claude for one block." Good root: "One claude call turns a block into root plus body."
3. The test: a reader who reads only the roots down a call path must know how the program works without opening one body.

Body rules:
4. body is free text, the explanation one layer down from the root. Choose the shape that fits the block.
5. For a block that orchestrates — its work is mostly calling other blocks and moving their results — write a FLOW: "name = role" lines, indentation for sub-steps, plain words, and the real callee names in parentheses so they become links.
6. For a block that computes — its work is its own logic — write an EXAMPLE: a tiny concrete input and what the block makes of it, then at most 3 short sentences for the rules a reader would guess wrong. Use real names from this file, or plainly generic ones like f, x and small numbers; never an invented plausible name.
7. SILENCE: when the body would only restate the root — no flow worth drawing, no rule a competent programmer would guess wrong — return "" as the body. Expect this for small plain blocks. A body that paraphrases the root is worse than no body.
8. Every name you write in parentheses on its own, like (cells_of), must be the name of a block of this file. The blocks of this file: {names}. This holds even when the body speaks about parenthesized names themselves: pick every example name from the blocks of this file, never invent one.
9. When the block calls a block explained above, speak at its level: use its one-line meaning, do not re-explain its inside.

A gold flow body, written for a main() that runs a decompiler like this one:
code            = the file to explain, a line number in front of every line
blocks, layers  = one block per function and class plus the script (blocks_of),
                  ordered so a block comes after the blocks it calls (layers_of)

for each block, bottom up:
    one claude call -> root + body   (ask_claude)
    checked, up to 8 tries          (check_block)
    the roots of finished callees ride along as context,
    so a caller speaks about its callees at their level

links     = the name links jedi finds between blocks
map.json  = the explanation, written beside the file

A gold example body, written for a cells_of that cuts a file into per-statement pieces:
Example: a four-line file

1  def double(n):
2      return n + n
3
4  print(double(2))

becomes three cells: [1,1] the def line, [2,2] the return, [4,4] the print. An inner statement gets its own cell; the outer one keeps only its own lines. A file that is not Python is cut at its blank lines instead.

Return one JSON object only, no code fences:
{{"root": "...", "body": "..."}}"""

VOCAB = """Below are the explanations of the blocks of one code file: per block one root line and one body, some bodies empty. Several blocks may share a piece of logic, so their texts repeat each other.

{expl}

Your job is compression through shared vocabulary:
1. Find the logic that several blocks share.
2. Invent the SMALLEST vocabulary of named concepts that shrinks the total text. Each entry is a term and a meaning. The term is a short natural phrase, like "the retry dance". The meaning is one plain line that defines the shared logic fully, so a reader who knows the term needs nothing else. Invent a term only when at least 2 blocks use it. When the blocks share nothing, an empty vocabulary with the texts unchanged is the right answer.
3. Rewrite EVERY root and body through the dictionary: where a term applies, write the term verbatim and keep only what is specific to that block. A block that shares nothing keeps its text untouched.

Hard rules:
- Every term appears verbatim in at least 2 rewritten texts; roots and bodies both count.
- Every rewritten root is 12 words or less, counted by spaces.
- A block whose body was not empty must not come back empty. A block whose body was empty stays empty unless a term truly applies.
- A name in parentheses on its own, like (cells_of), must stay the name of a block of this file.

Return one JSON object only, no code fences:
{{"vocabulary": [{{"term": "...", "meaning": "..."}}], "rewritten": {{"block_name": {{"root": "...", "body": "..."}}}}}}"""


CALLS = [0]


def ask_claude(prompt):
    CALLS[0] += 1
    r = subprocess.run(["claude", "-p", prompt, "--output-format", "json"],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stderr[-500:]
    raw = json.loads(r.stdout)["result"]
    return json.loads(raw[raw.index("{"):raw.rindex("}") + 1])


NAME_REF = re.compile(r"(?<![A-Za-z0-9_])\(([A-Za-z_][A-Za-z0-9_]*)\)")


def check_block(m, names):
    root = m.get("root")
    assert isinstance(root, str) and root.strip(), "no root"
    assert len(root.split()) <= 12, f"the root has {len(root.split())} words, the limit is 12"
    body = m.get("body")
    assert isinstance(body, str), "the body must be a string, empty is legal"
    for w in sorted(set(NAME_REF.findall(body))):
        assert w in names, f"({w}) is not the name of a block of this file"
    return root.strip(), body.strip()


def check_vocab(m, done, names):
    vocab = m.get("vocabulary")
    assert isinstance(vocab, list), "vocabulary must be a list, empty is legal"
    for t in vocab:
        assert isinstance(t, dict) and isinstance(t.get("term"), str) and t["term"].strip(), \
            "a vocabulary entry needs a term string"
        assert isinstance(t.get("meaning"), str) and t["meaning"].strip(), \
            f'the term "{t.get("term")}" needs a meaning'
    rew = m.get("rewritten")
    assert isinstance(rew, dict), "no rewritten object"
    out = {}
    for n, old in done.items():
        e = rew.get(n)
        assert isinstance(e, dict), f"the block {n} is missing from rewritten"
        root = e.get("root")
        body = e.get("body")
        assert isinstance(root, str) and root.strip(), f"the block {n} needs a root"
        assert len(root.split()) <= 12, \
            f"the rewritten root of {n} has {len(root.split())} words, the limit is 12"
        assert isinstance(body, str), f"the body of {n} must be a string, empty is legal"
        if old["body"]:
            assert body.strip(), f"the body of {n} was not empty, it must not come back empty"
        for w in sorted(set(NAME_REF.findall(body))):
            assert w in names, f"({w}) is not the name of a block of this file"
        out[n] = {"root": root.strip(), "body": body.strip()}
    for t in vocab:
        used = sum(1 for e in out.values()
                   if t["term"].strip() in e["root"] or t["term"].strip() in e["body"])
        assert used >= 2, \
            f'the term "{t["term"].strip()}" appears verbatim in {used} texts, it must appear in at least 2'
    return [{"term": t["term"].strip(), "meaning": t["meaning"].strip()} for t in vocab], out


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


def compile_block(bl, name, code, ctx, names):
    label = bl["name"].split(".")[-1] + "()" if bl["node"] else "the top-level script code"
    span = ", ".join(f"{a}-{b}" for a, b in bl["lines"])
    short = ", ".join(sorted({n.split(".")[-1] for n in names}))
    base = PROMPT.format(name=name, code=code, block=label, span=span, ctx=ctx, names=short)
    note = ""
    errs = []
    m = None
    for attempt in range(8):
        try:
            m = ask_claude(base + note)
            root, body = check_block(m, names)
            print(f"{bl['name']}: root" + (" + body" if body else ", silent"))
            return root, body
        except (AssertionError, TypeError, ValueError, KeyError) as e:
            print(f"retry {attempt + 1} [{label}]: {e}")
            errs.append(f"- {e}")
            note = (f"\n\nYour last answer:\n{json.dumps(m)}\n\n"
                    f"It broke a rule: {e}. Repair it and return the full corrected JSON.\n"
                    f"Rules your answers broke so far, do not break them again:\n" + "\n".join(errs))
    sys.exit(f"no valid pass after 8 tries [{bl['name']}]")


def vocab_pass(blocks, done, names):
    expl = "\n\n".join((f'{bl["name"]}\nroot: {done[bl["name"]]["root"]}\n'
                        f'body:\n{done[bl["name"]]["body"]}').rstrip() for bl in blocks)
    base = VOCAB.format(expl=expl)
    note = ""
    errs = []
    m = None
    for attempt in range(4):
        try:
            m = ask_claude(base + note)
            terms, rewritten = check_vocab(m, done, names)
            print(f"vocabulary: {len(terms)} terms")
            return terms, rewritten
        except (AssertionError, TypeError, ValueError, KeyError) as e:
            print(f"vocab retry {attempt + 1}: {e}")
            errs.append(f"- {e}")
            note = (f"\n\nYour last answer:\n{json.dumps(m)}\n\n"
                    f"It broke a rule: {e}. Repair it and return the full corrected JSON.\n"
                    f"Rules your answers broke so far, do not break them again:\n" + "\n".join(errs))
    sys.exit("no valid vocabulary pass after 4 tries")


def main():
    path = Path(sys.argv[1])
    src = path.read_text(encoding="utf-8")
    lines = src.splitlines()
    assert any(l.strip() for l in lines), f"{path.name} is empty"
    code = "\n".join(f"{n}|{l}" for n, l in enumerate(lines, 1))
    blocks = blocks_of(path, src, lines)
    body = ast.parse(src).body if path.suffix == ".py" else []
    names = {b["name"] for b in blocks if b["node"]}
    calls = {b["name"]: calls_of(b, body, names) for b in blocks}
    lay = layers_of(blocks, calls)
    ok = {b["name"] for b in blocks} | {b["name"].split(".")[-1] for b in blocks}
    done = {}
    for bl in sorted(blocks, key=lambda b: (lay[b["name"]], b["lines"][0][0])):
        ctx = "".join(f'{n.split(".")[-1]}() — {done[n]["root"]}\n'
                      for n in calls[bl["name"]] if n in done)
        if ctx:
            ctx = "Blocks this block calls, explained already. Their root lines:\n" + ctx + "\n"
        root, btext = compile_block(bl, path.name, code, ctx, ok)
        done[bl["name"]] = {"root": root, "body": btext}
    terms, done = vocab_pass(blocks, done, ok)
    rows = []
    for i, bl in enumerate(blocks, 1):
        rows.append({"id": f"B{i:02d}", "name": bl["name"], "layer": lay[bl["name"]],
                     "lines": bl["lines"], "calls": calls[bl["name"]],
                     "root": done[bl["name"]]["root"], "body": done[bl["name"]]["body"]})
    owner = {}
    for r in rows:
        for a, e in r["lines"]:
            for n in range(a, e + 1):
                owner[n] = r["id"]
    m = {"file": path.name, "links": links(path, owner), "terms": terms, "blocks": rows}
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else path.parent / "map.json"
    out.write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    silent = sum(1 for r in rows if not r["body"])
    print(f"{len(blocks)} blocks, {silent} silent, {len(terms)} terms, {len(m['links'])} links, "
          f"{CALLS[0]} claude calls -> {out}")


if __name__ == "__main__":
    main()
