import ast
import json
import re
import subprocess
import sys
from pathlib import Path

import jedi

PROMPT = """You are explaining one block of a code file to a person, the way you would explain it if they asked you "what does this do?". The input is the file, one line per number. Return the block's sequent — takes, gives, effects — plus one root line and one body.

File: {name}
{code}

You are explaining the block {block}, lines {span}. Ignore all other lines.

{ctx}Sequent rules:
1. takes is one plain phrase: what the block needs — its arguments and the state it reads. "nothing" is legal.
2. gives is one plain phrase: what the block returns to its caller.
3. effects is a list of short plain phrases: what the block does to the world — file writes, subprocess runs, prints, sleeps, globals it changes. A pure block returns []. An effect belongs to the block that performs it, never to its callers.

Root rules:
4. The root is the answer line: 15 words or less, counted by spaces. It names the subject and the effect. It is the answer a person keeps, not a description of the code.
5. Bad root: "compile_block builds the prompt and calls claude for one block." Good root: "One claude call turns a block into root plus body."
6. The test: a reader who reads only the roots down a call path must know how the program works without opening one body.

Body rules:
7. body is free text, the explanation one layer down from the root. Choose the shape that fits the block.
8. For a block that orchestrates — its work is mostly calling other blocks and moving their results — write a FLOW: "name = role" lines, indentation for sub-steps, plain words, and the real callee names in parentheses so they become links. A step line that performs one of the block's own effects starts with "! "; pure steps have no marker.
9. For a block that computes — its work is its own logic — write an EXAMPLE: a tiny concrete input and what the block makes of it, then at most 3 short sentences for the rules a reader would guess wrong. Use real names from this file, or plainly generic ones like f, x and small numbers; never an invented plausible name.
10. SILENCE: when the body would only restate the root — no flow worth drawing, no rule a competent programmer would guess wrong — return "" as the body. Expect this for small plain blocks. A body that paraphrases the root is worse than no body.
11. Every name you write in parentheses on its own, like (cells_of), must be the name of a block of this file. The blocks of this file: {names}. This holds even when the body speaks about parenthesized names themselves: pick every example name from the blocks of this file, never invent one.
12. When the block calls a block explained above, speak through its sequent: what it takes, gives, and does. Never re-explain its inside.

A gold flow body, written for a main() that runs a decompiler like this one; it writes map.json itself, so that step carries the mark:
code            = the file to explain, a line number in front of every line
blocks, layers  = one block per function and class plus the script (blocks_of),
                  ordered so a block comes after the blocks it calls (layers_of)

for each block, bottom up:
    one claude call -> root + body   (ask_claude)
    checked, up to 8 tries          (check_block)
    the roots of finished callees ride along as context,
    so a caller speaks about its callees at their level

links       = the name links jedi finds between blocks
! map.json  = the explanation, written beside the file

A gold example body, written for a cells_of that cuts a file into per-statement pieces:
Example: a four-line file

1  def double(n):
2      return n + n
3
4  print(double(2))

becomes three cells: [1,1] the def line, [2,2] the return, [4,4] the print. An inner statement gets its own cell; the outer one keeps only its own lines. A file that is not Python is cut at its blank lines instead.

Return one JSON object only, no code fences:
{{"takes": "...", "gives": "...", "effects": [], "root": "...", "body": "..."}}"""

VOCAB = """Below are the explanations of the blocks of one code file: per block one root line and one body, some bodies empty. Several blocks may share a piece of logic, so their texts repeat each other.

{expl}

Your job is compression through shared vocabulary:
1. Find the logic that several blocks share.
2. Invent the SMALLEST vocabulary of named concepts that shrinks the total text. Each entry is a term and a meaning. The term is a short natural phrase, like "the retry dance". The meaning is one plain line that defines the shared logic fully, so a reader who knows the term needs nothing else. Invent a term only when at least 2 blocks use it. When the blocks share nothing, an empty vocabulary with the texts unchanged is the right answer.
3. Rewrite EVERY root and body through the dictionary: where a term applies, write the term verbatim and keep only what is specific to that block. A block that shares nothing keeps its text untouched.

Hard rules:
- Every term appears verbatim in at least 2 rewritten texts; roots and bodies both count.
- Every rewritten root is 15 words or less, counted by spaces.
- A block whose body was not empty must not come back empty. A block whose body was empty stays empty unless a term truly applies.
- A name in parentheses on its own, like (cells_of), must stay the name of a block of this file. A step line that starts with "! " keeps its mark.
- A term meaning may use another term or cite a block name, but the chain must always lead down: no circle of terms, and every cited block is a real block of this file.

Return one JSON object only, no code fences:
{{"vocabulary": [{{"term": "...", "meaning": "..."}}], "rewritten": {{"block_name": {{"root": "...", "body": "..."}}}}}}"""


RULES = {
    "SEQ-FIELDS": "takes and gives are non-empty plain phrases and effects is a list of short phrases, empty for a pure block",
    "ROOT-15": "the root is 15 words or less, counted by spaces",
    "LINK-REAL": "a lone name in parentheses is the name of a block of this file",
    "EFFECT-MARK": "bang lines and the effects list agree: a bang line needs a declared effect, an effectful flow body needs a bang line",
    "BODY-KEPT": "a body that was not empty does not come back empty from the vocabulary pass",
    "TERM-USED": "every term appears verbatim in at least 2 rewritten texts",
    "TERM-GROUNDED": "a term meaning cites only real blocks of this file and no circle of terms closes",
}

BLOCK_RULES = ["SEQ-FIELDS", "ROOT-15", "LINK-REAL", "EFFECT-MARK"]


CALLS = [0]


def ask_claude(prompt):
    CALLS[0] += 1
    r = subprocess.run(["claude", "-p", prompt, "--output-format", "json"],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stderr[-500:]
    raw = json.loads(r.stdout)["result"]
    return json.loads(raw[raw.index("{"):raw.rindex("}") + 1])


NAME_REF = re.compile(r"(?<![A-Za-z0-9_])\(([A-Za-z_][A-Za-z0-9_]*)\)")
DOTTED = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+")


def check_block(m, names):
    takes = m.get("takes")
    gives = m.get("gives")
    eff = m.get("effects")
    assert isinstance(takes, str) and takes.strip(), "[SEQ-FIELDS] takes must be a non-empty phrase"
    assert isinstance(gives, str) and gives.strip(), "[SEQ-FIELDS] gives must be a non-empty phrase"
    assert isinstance(eff, list) and all(isinstance(e, str) and e.strip() for e in eff), \
        "[SEQ-FIELDS] effects must be a list of non-empty phrases, [] is legal"
    root = m.get("root")
    assert isinstance(root, str) and root.strip(), "[ROOT-15] no root"
    assert len(root.split()) <= 15, f"[ROOT-15] the root has {len(root.split())} words, the limit is 15"
    body = m.get("body")
    assert isinstance(body, str), "the body must be a string, empty is legal"
    for w in sorted(set(NAME_REF.findall(body))):
        assert w in names, f"[LINK-REAL] ({w}) is not the name of a block of this file"
    bangs = [l for l in body.splitlines() if l.lstrip().startswith("! ")]
    if bangs:
        assert eff, "[EFFECT-MARK] the body has a bang line but effects is empty"
    if eff and body.strip() and not body.lstrip().lower().startswith("example"):
        assert bangs, "[EFFECT-MARK] the block has effects and a flow body, so one step line must start with a bang"
    return {"takes": takes.strip(), "gives": gives.strip(), "effects": [e.strip() for e in eff],
            "root": root.strip(), "body": body.strip()}


def check_grounded(vocab, names):
    tnames = [t["term"].strip() for t in vocab]
    for t in vocab:
        meaning = t["meaning"]
        for w in sorted(set(NAME_REF.findall(meaning))):
            assert w in names, \
                f'[TERM-GROUNDED] the meaning of "{t["term"].strip()}" cites ({w}), which is not a block of this file'
        for tok in sorted(set(DOTTED.findall(meaning))):
            if tok.split(".")[0] in names:
                assert tok in names, \
                    f'[TERM-GROUNDED] the meaning of "{t["term"].strip()}" cites {tok}, which is not a block of this file'
    edges = {}
    for i in range(len(vocab)):
        for j in range(len(vocab)):
            if re.search(r"\b" + re.escape(tnames[j]) + r"\b", vocab[i]["meaning"], re.I):
                edges.setdefault(i, []).append(j)
    state = {}

    def walk(v, path):
        state[v] = 1
        for w in edges.get(v, ()):
            if state.get(w) == 1:
                cyc = path[path.index(w):] + [w]
                assert False, ("[TERM-GROUNDED] a circle of terms closes: "
                               + " -> ".join(f'"{tnames[x]}"' for x in cyc))
            if state.get(w) != 2:
                walk(w, path + [w])
        state[v] = 2

    for i in range(len(vocab)):
        if state.get(i) != 2:
            walk(i, [i])


def check_vocab(m, done, names):
    vocab = m.get("vocabulary")
    assert isinstance(vocab, list), "vocabulary must be a list, empty is legal"
    for t in vocab:
        assert isinstance(t, dict) and isinstance(t.get("term"), str) and t["term"].strip(), \
            "a vocabulary entry needs a term string"
        assert isinstance(t.get("meaning"), str) and t["meaning"].strip(), \
            f'the term "{t.get("term")}" needs a meaning'
    check_grounded(vocab, names)
    rew = m.get("rewritten")
    assert isinstance(rew, dict), "no rewritten object"
    out = {}
    for n, old in done.items():
        e = rew.get(n)
        assert isinstance(e, dict), f"the block {n} is missing from rewritten"
        root = e.get("root")
        body = e.get("body")
        assert isinstance(root, str) and root.strip(), f"[ROOT-15] the block {n} needs a root"
        assert len(root.split()) <= 15, \
            f"[ROOT-15] the rewritten root of {n} has {len(root.split())} words, the limit is 15"
        assert isinstance(body, str), f"the body of {n} must be a string, empty is legal"
        if old["body"]:
            assert body.strip(), f"[BODY-KEPT] the body of {n} was not empty, it must not come back empty"
        for w in sorted(set(NAME_REF.findall(body))):
            assert w in names, f"[LINK-REAL] ({w}) is not the name of a block of this file"
        out[n] = dict(old, root=root.strip(), body=body.strip())
    for t in vocab:
        used = sum(1 for e in out.values()
                   if t["term"].strip() in e["root"] or t["term"].strip() in e["body"])
        assert used >= 2, \
            f'[TERM-USED] the term "{t["term"].strip()}" appears verbatim in {used} texts, it must appear in at least 2'
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
    for attempt in range(4):
        try:
            m = ask_claude(base + note)
            rec = check_block(m, names)
            print(f"{bl['name']}: root" + (" + body" if rec["body"] else ", silent")
                  + (f", {len(rec['effects'])} effects" if rec["effects"] else ", pure"))
            return rec
        except (AssertionError, TypeError, ValueError, KeyError) as e:
            print(f"retry {attempt + 1} [{label}]: {e}")
            errs.append(f"- {e}")
            note = (f"\n\nYour last answer:\n{json.dumps(m)}\n\n"
                    f"It broke a rule: {e}. Repair it and return the full corrected JSON.\n"
                    f"Rules your answers broke so far, do not break them again:\n" + "\n".join(errs))
    sys.exit(f"no valid pass after 4 tries [{bl['name']}]")


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
        ctx = ""
        for n in calls[bl["name"]]:
            if n in done:
                d = done[n]
                ctx += f'{n.split(".")[-1]}() — takes {d["takes"]}, gives {d["gives"]}'
                ctx += f'; does: {", ".join(d["effects"])}\n' if d["effects"] else "; pure\n"
        if ctx:
            ctx = ("Blocks this block calls, each given as its sequent. Speak about a callee only "
                   "through its sequent — what it takes, gives and does. Never re-explain its inside:\n"
                   + ctx + "\n")
        done[bl["name"]] = compile_block(bl, path.name, code, ctx, ok)
    terms, done = vocab_pass(blocks, done, ok)
    ids = {bl["name"]: f"B{i:02d}" for i, bl in enumerate(blocks, 1)}
    rows = []
    for bl in blocks:
        d = done[bl["name"]]
        rows.append({"id": ids[bl["name"]], "name": bl["name"], "layer": lay[bl["name"]],
                     "lines": bl["lines"], "calls": calls[bl["name"]],
                     "takes": d["takes"], "gives": d["gives"], "effects": d["effects"],
                     "root": d["root"], "body": d["body"],
                     "premises": [ids[n] for n in calls[bl["name"]]],
                     "rules": BLOCK_RULES + (["BODY-KEPT"] if d["body"] else [])})
    owner = {}
    for r in rows:
        for a, e in r["lines"]:
            for n in range(a, e + 1):
                owner[n] = r["id"]
    m = {"file": path.name, "links": links(path, owner), "terms": terms, "rules": RULES,
         "blocks": rows}
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else path.parent / "map.json"
    out.write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    silent = sum(1 for r in rows if not r["body"])
    pure = sum(1 for r in rows if not r["effects"])
    print(f"{len(blocks)} blocks, {silent} silent, {pure} pure, {len(terms)} terms, "
          f"{len(m['links'])} links, {CALLS[0]} claude calls -> {out}")


if __name__ == "__main__":
    main()
