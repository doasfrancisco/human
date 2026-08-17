import argparse
import ast
import difflib
import json
import re
import subprocess
import sys
from pathlib import Path

PROMPT = """You map an explanation text onto the real lines of a code file.

The file is <code_file>. Every line has its number in front:

<numbered_code>

The blocks of the file, with their exact line spans:

<span_table>

The entries already mapped:

<existing>

The new explanation text:

---
<text>
---

Hints from the user: block = <block_hint>, within = <within_hint>.

Return one JSON object and nothing else, in this shape:

{"block": "<name of the code region the text explains>",
 "block_lines": [[start, end]],
 "within": {"explanation": <entry id>, "part": "<part name>", "instruction": "<one line of that part's text>"} or null,
 "parts": [
   {"part": "<left-column name from the text>",
    "own_lines": [[start, end]],
    "callee_lines": [{"name": "<block>", "lines": [[start, end]]}],
    "constant_lines": [{"name": "<CONSTANT>", "lines": [[start, end]]}],
    "outside_within": true,
    "note": "<where these lines belong>"}]}

The rules:
- One part per bound name of the text, in the order of the text. A name bound inside a loop line is a part too.
- own_lines are the lines inside block_lines that the part describes.
- callee_lines hold the full span of every block the part calls, copied verbatim from the block table, plus the blocks those blocks call when the part is the one that reaches them.
- constant_lines hold the module constants the part uses.
- A part whose own lines sit outside block_lines gets "outside_within": true and a note that says which entry and part those lines belong to. Only such a part carries these two keys.
- within points to the one already-mapped part whose lines contain this block. Its instruction is the exact line of that part's text that reaches this block, copied verbatim from the entry's text without its leading spaces. Use null when no mapped part contains it.
- Map only this text. Do not restate or change the entries already mapped.
"""


SYNC_PROMPT = """A code file changed. Explanation texts were written for the old version of the file. A deterministic tool already renumbered every mapped line span. Your job is only the words and the part structure.

The file is <code_file>. The unified diff of the change:

<diff>

Facts from the tool, in new-file numbering:

<facts>

The candidate entries, each with its flow text and its part names:

<candidates>

The rules:
- A text line is stale only when the change makes its words wrong. A text whose mapped lines moved but whose words still hold is not stale.
- A new bound name in the code needs a new flow line, in code order, in the style and alignment of the text, plus a part edit that adds the part with its own lines.
- A deleted bound name loses its flow line and its part.
- Rewrite a stale line with the smallest edit. Keep every other line verbatim. Keep the vocabulary, the layout, and the indentation.
- An entry whose words all still hold needs no text and no edits.

Return one JSON object and nothing else:

{"stale": [{"entry": <id>, "old": "<old line, stripped>", "new": "<new line, stripped, empty when the line dies>"}],
 "part_edits": [{"entry": <id>, "add": [{"part": "<name>", "own_lines": [[start, end]], "after_part": "<existing part name>"}], "remove": ["<part name>"]}],
 "texts": {"<entry id>": "<the full corrected text, only for an entry with a changed line>"}}
"""


def numbered(lines):
    return "\n".join(f"{i:4} {l}" for i, l in enumerate(lines, 1))


def md_spans(path, lines):
    spans = {}
    stack = []
    fence = None
    for i, l in enumerate(lines, 1):
        t = l.strip()
        if fence:
            if t.startswith(fence):
                fence = None
            continue
        if t.startswith("```") or t.startswith("~~~"):
            fence = t[:3]
            continue
        m = re.match(r"(#{1,6})\s+(.+?)\s*#*\s*$", l)
        if not m:
            continue
        level, name = len(m.group(1)), m.group(2)
        while stack and stack[-1][0] >= level:
            lv, nm, st = stack.pop()
            spans[nm] = [st, i - 1]
        if name in spans or any(nm == name for lv, nm, st in stack):
            sys.exit(f"duplicate heading {name!r} in {path.name}; "
                     f"headings must be unique to serve as block names")
        stack.append((level, name, i))
    for lv, nm, st in stack:
        spans[nm] = [st, len(lines)]
    return spans


def block_spans(path, lines):
    if path.suffix == ".md":
        return md_spans(path, lines)
    if path.suffix != ".py":
        return {}
    try:
        tree = ast.parse("\n".join(lines))
    except SyntaxError:
        return {}
    spans = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start = min([node.lineno] + [d.lineno for d in node.decorator_list])
            spans[node.name] = [start, node.end_lineno]
    return spans


def expand(span_list):
    s = set()
    for a, b in span_list:
        s.update(range(a, b + 1))
    return s


def part_lines(part):
    s = expand(part.get("own_lines", []))
    for c in part.get("callee_lines", []):
        s |= expand(c["lines"])
    for c in part.get("constant_lines", []):
        s |= expand(c["lines"])
    return s


def fmt(nums):
    nums = sorted(nums)
    out = []
    i = 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        out.append(str(nums[i]) if i == j else f"{nums[i]}-{nums[j]}")
        i = j + 1
    return ", ".join(out)


def check_spans(sp, n, label):
    assert isinstance(sp, list), f"[{label}] must be a list of [start, end] pairs"
    out = []
    for pair in sp:
        assert isinstance(pair, list) and len(pair) == 2 and all(isinstance(x, int) for x in pair), \
            f"[{label}] each span must be a [start, end] pair of integers, got {pair}"
        a, b = pair
        assert 1 <= a <= b <= n, f"[{label}] span {pair} is outside the file (1-{n})"
        out.append([a, b])
    return out


def head_token(s):
    t = s.strip()
    if t.startswith("!"):
        t = t[1:].strip()
    return t.split()[0].lower()


def chunks_of(text):
    raw, cur = [], None
    for l in text.split("\n"):
        if l.strip() and l[0] not in " \t":
            if cur:
                raw.append(cur)
            cur = []
        if cur is None:
            cur = []
        cur.append(l)
    if cur:
        raw.append(cur)
    return raw


def part_chunk(parent, part_name):
    raw = chunks_of(parent["text"])
    parts = parent["parts"]
    if len(raw) == len(parts):
        idx = next(i for i, p in enumerate(parts) if p["part"] == part_name)
        return raw[idx]
    tok = head_token(part_name)
    for c in raw:
        if head_token(c[0]) == tok:
            return c
    return [l for c in raw for l in c]


def check_entry(m, data, lines, spans):
    n = len(lines)
    block = m.get("block")
    assert isinstance(block, str) and block.strip(), "[BLOCK-NAME] block must be a non-empty name"
    block_lines = check_spans(m.get("block_lines"), n, "BLOCK-LINES")
    assert block_lines, "[BLOCK-LINES] block_lines must have at least one span"
    parts = m.get("parts")
    assert isinstance(parts, list) and parts, "[PARTS] parts must be a non-empty list"
    block_set = expand(block_lines)
    seen = set()
    clean_parts = []
    for p in parts:
        name = p.get("part")
        assert isinstance(name, str) and name.strip(), "[PART-NAME] every part needs a non-empty name"
        name = name.strip()
        assert name not in seen, f"[PART-NAME] part {name} appears twice"
        seen.add(name)
        own = check_spans(p.get("own_lines", []), n, "OWN-LINES")
        outside = bool(p.get("outside_within"))
        if not outside:
            bad = expand(own) - block_set
            assert not bad, f"[PART-BOUNDS] part {name} has own lines {fmt(bad)} outside the block; " \
                            "fix the lines, or mark the part outside_within with a note"
        callees = []
        for c in p.get("callee_lines", []):
            cname = c.get("name")
            assert isinstance(cname, str) and cname.strip(), "[CALLEE-REAL] every callee needs a name"
            cname = cname.strip()
            cl = check_spans(c.get("lines"), n, "CALLEE-LINES")
            if spans:
                assert cname in spans, f"[CALLEE-REAL] {cname} is not a block of this file"
                assert cl == [spans[cname]], \
                    f"[CALLEE-REAL] {cname} spans lines {spans[cname][0]}-{spans[cname][1]}, not {cl}"
            callees.append({"name": cname, "lines": cl})
        consts = []
        for c in p.get("constant_lines", []):
            cname = c.get("name")
            assert isinstance(cname, str) and cname.strip(), "[CONST-NAME] every constant needs a name"
            consts.append({"name": cname.strip(), "lines": check_spans(c.get("lines"), n, "CONST-LINES")})
        q = {"part": name, "own_lines": own, "callee_lines": callees, "constant_lines": consts}
        if outside:
            note = p.get("note")
            assert isinstance(note, str) and note.strip(), \
                f"[PART-BOUNDS] part {name} is outside_within, add a note that says where its lines belong"
            q["outside_within"] = True
            q["note"] = note.strip()
        elif isinstance(p.get("note"), str) and p["note"].strip():
            q["note"] = p["note"].strip()
        clean_parts.append(q)
    out = {"block": block.strip(), "block_lines": block_lines, "parts": clean_parts}
    within = m.get("within")
    if within:
        assert isinstance(within, dict), "[WITHIN-REAL] within must be an object or null"
        parent = next((e for e in data["explanations"] if e["id"] == within.get("explanation")), None)
        assert parent, f"[WITHIN-REAL] explanation {within.get('explanation')} does not exist"
        ppart = next((p for p in parent["parts"] if p["part"] == within.get("part")), None)
        assert ppart, f"[WITHIN-REAL] part {within.get('part')!r} does not exist in explanation {parent['id']}"
        bad = block_set - part_lines(ppart)
        assert not bad, f"[WITHIN-BOUNDS] lines {fmt(bad)} are outside part {ppart['part']!r} " \
                        f"of explanation {parent['id']}"
        instr = within.get("instruction")
        assert isinstance(instr, str) and instr.strip(), \
            "[WITHIN-INSTRUCTION] within needs instruction: the exact line of the parent part's text " \
            "that reaches this block"
        instr = instr.strip()
        chunk = [l.strip() for l in part_chunk(parent, ppart["part"])]
        assert instr in chunk, \
            f"[WITHIN-INSTRUCTION] {instr!r} is not a line of part {ppart['part']!r} " \
            f"in explanation {parent['id']}"
        out["within"] = {"explanation": parent["id"], "part": ppart["part"], "instruction": instr}
    return out


def recompute(data, lines):
    blank = [i for i, l in enumerate(lines, 1) if not l.strip()]
    covered = set()
    for e in data["explanations"]:
        covered |= expand(e["block_lines"])
        for p in e["parts"]:
            covered |= part_lines(p)
    missing = [i for i in range(1, len(lines) + 1) if i not in covered and i not in set(blank)]
    data["not_covered"] = {"code_lines": missing, "blank_lines": blank}
    return missing, blank


def ask_claude(prompt):
    r = subprocess.run(["claude", "-p", prompt, "--output-format", "json"],
                       capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        sys.exit(f"claude failed: {r.stderr[-500:]}")
    raw = json.loads(r.stdout)["result"]
    return json.loads(raw[raw.index("{"):raw.rindex("}") + 1])


def load_map(map_path, name):
    if map_path.exists():
        return json.loads(map_path.read_text())
    return {"code_file": name, "explanations": [], "not_covered": {"code_lines": [], "blank_lines": []}}


def parse_within(arg):
    wid, sep, wpart = arg.partition(":")
    if not sep or not wid.isdigit() or not wpart:
        sys.exit(f"--within must look like <id>:<part>, got {arg!r}")
    return {"explanation": int(wid), "part": wpart}


def cmd_map(a):
    code_path = Path(a.code_file).resolve()
    lines = code_path.read_text().splitlines()
    spans = block_spans(code_path, lines)
    map_path = code_path.parent / f"explanation_{code_path.name}.json"
    data = load_map(map_path, code_path.name)
    text = (Path(a.text).read_text() if a.text else sys.stdin.read()).strip()
    if not text:
        sys.exit("no explanation text on stdin or --text")
    within_arg = parse_within(a.within) if a.within else None
    if within_arg and a.at:
        within_arg["instruction"] = a.at.strip()
    existing = [{"id": e["id"], "block": e["block"], "block_lines": e["block_lines"],
                 "text": e["text"],
                 "parts": [{k: p[k] for k in ("part", "own_lines", "callee_lines", "constant_lines")}
                           for p in e["parts"]]}
                for e in data["explanations"]]
    span_table = "\n".join(f"{k}: {v[0]}-{v[1]}"
                           for k, v in sorted(spans.items(), key=lambda x: x[1])) or "none"
    prompt = (PROMPT.replace("<code_file>", code_path.name)
              .replace("<numbered_code>", numbered(lines))
              .replace("<span_table>", span_table)
              .replace("<existing>", json.dumps(existing) if existing else "none")
              .replace("<text>", text)
              .replace("<block_hint>", a.block or "none")
              .replace("<within_hint>", a.within or "none"))
    entry = None
    last = ""
    suffix = ""
    for _ in range(a.tries):
        try:
            m = ask_claude(prompt + suffix)
        except (ValueError, KeyError) as e:
            last = f"the answer was not one JSON object: {e}"
            suffix = "\n\nYour previous answer was not one JSON object. Return only the JSON."
            continue
        if a.block:
            m["block"] = a.block
        if within_arg:
            m["within"] = {**(m.get("within") or {}), **within_arg}
        try:
            entry = check_entry(m, data, lines, spans)
            break
        except AssertionError as e:
            last = str(e)
            suffix = f"\n\nYour previous answer:\n{json.dumps(m)}\n\n" \
                     f"It broke this rule: {last}\nReturn the full corrected JSON object."
    if entry is None:
        sys.exit(f"the mapping failed after {a.tries} tries, last error: {last}")
    eid = max((e["id"] for e in data["explanations"]), default=0) + 1
    record = {"id": eid, "block": entry["block"], "block_lines": entry["block_lines"]}
    if "within" in entry:
        record["within"] = entry["within"]
    record["text"] = text
    record["parts"] = entry["parts"]
    data["explanations"].append(record)
    missing, blank = recompute(data, lines)
    map_path.write_text(json.dumps(data, indent=2) + "\n")
    w = record.get("within")
    tail = f", within {w['explanation']}:{w['part']}" if w else ""
    if w and w.get("instruction"):
        tail += f" @ {w['instruction']}"
    print(f"entry {eid}: {record['block']}, lines {fmt(expand(record['block_lines']))}, "
          f"{len(record['parts'])} parts{tail}")
    print("parts: " + ", ".join(p["part"] for p in record["parts"]))
    total = len(lines) - len(blank)
    print(f"covered: {total - len(missing)} of {total} code lines")
    print(f"not covered: {fmt(missing) if missing else 'nothing'}")
    print(f"wrote {map_path}")


def part_line(line, name):
    if not line.startswith(name):
        return False
    rest = line[len(name):]
    return not rest or not rest[0].isalnum()


def load_existing(code_path):
    map_path = code_path.parent / f"explanation_{code_path.name}.json"
    if not map_path.exists():
        sys.exit(f"no map file at {map_path}")
    return map_path, json.loads(map_path.read_text())


def cmd_retext(a):
    code_path = Path(a.code_file).resolve()
    map_path, data = load_existing(code_path)
    entry = next((e for e in data["explanations"] if e["id"] == a.id), None)
    if entry is None:
        sys.exit(f"no entry {a.id} in {map_path.name}")
    text = (Path(a.text).read_text() if a.text else sys.stdin.read()).strip()
    if not text:
        sys.exit("no explanation text on stdin or --text")
    ls = [l.strip() for l in text.split("\n") if l.strip()]
    i = 0
    for p in entry["parts"]:
        while i < len(ls) and not part_line(ls[i], p["part"]):
            i += 1
        if i == len(ls):
            sys.exit(f"[RETEXT-PARTS] the new text must keep every part name, in order; "
                     f"no line starts with {p['part']!r}")
        i += 1
    new_lines = {l.strip() for l in text.split("\n") if l.strip()}
    for k in data["explanations"]:
        w = k.get("within") or {}
        if w.get("explanation") == a.id and w.get("instruction") and w["instruction"] not in new_lines:
            sys.exit(f"[RETEXT-INSTRUCTION] entry {k['id']} hangs on the line {w['instruction']!r}; "
                     f"the new text must keep that line")
    entry["text"] = text
    map_path.write_text(json.dumps(data, indent=2) + "\n")
    print(f"entry {a.id} ({entry['block']}): text replaced, {len(entry['parts'])} parts unchanged")
    print(f"wrote {map_path}")


def cmd_undo(a):
    code_path = Path(a.code_file).resolve()
    map_path, data = load_existing(code_path)
    if not data["explanations"]:
        sys.exit("nothing to undo")
    last = data["explanations"][-1]
    kids = [e["id"] for e in data["explanations"]
            if (e.get("within") or {}).get("explanation") == last["id"]]
    if kids:
        sys.exit(f"entry {last['id']} has children {kids}; undo them first")
    data["explanations"].pop()
    lines = code_path.read_text().splitlines()
    missing, blank = recompute(data, lines)
    map_path.write_text(json.dumps(data, indent=2) + "\n")
    w = last.get("within")
    tail = f", within {w['explanation']}:{w['part']}" if w else ""
    print(f"removed entry {last['id']}: {last['block']}, "
          f"lines {fmt(expand(last['block_lines']))}{tail}")
    total = len(lines) - len(blank)
    print(f"covered: {total - len(missing)} of {total} code lines")
    print(f"wrote {map_path}")


def cmd_show(a):
    code_path = Path(a.code_file).resolve()
    lines = code_path.read_text().splitlines()
    map_path = code_path.parent / f"explanation_{code_path.name}.json"
    if not map_path.exists():
        print(f"no map file at {map_path}")
        return
    data = json.loads(map_path.read_text())
    for e in data["explanations"]:
        w = e.get("within")
        tail = f"  within {w['explanation']}:{w['part']}" if w else ""
        print(f"{e['id']:3}  {e['block']:<20} {fmt(expand(e['block_lines'])):<18} "
              f"{len(e['parts'])} parts{tail}")
    missing, blank = recompute(data, lines)
    total = len(lines) - len(blank)
    print(f"covered: {total - len(missing)} of {total} code lines")
    print(f"not covered: {fmt(missing) if missing else 'nothing'}")


def cmd_lines(a):
    code_path = Path(a.code_file).resolve()
    print(numbered(code_path.read_text().splitlines()))


def old_lines_of(code_path, old_arg):
    if old_arg:
        return Path(old_arg).read_text().splitlines()
    r = subprocess.run(["git", "-C", str(code_path.parent), "show", f"HEAD:./{code_path.name}"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"no old version of {code_path.name}: commit the file or pass --old "
                 f"(git: {r.stderr.strip()[-200:]})")
    return r.stdout.splitlines()


def line_map(old, new):
    sm = difflib.SequenceMatcher(None, old, new, autojunk=False)
    o2n = {}
    changed = set()
    inserted = set()
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                o2n[i1 + k + 1] = j1 + k + 1
        else:
            paired = min(i2 - i1, j2 - j1)
            for k in range(paired):
                o2n[i1 + k + 1] = j1 + k + 1
            changed.update(range(i1 + 1, i2 + 1))
            inserted.update(range(j1 + paired + 1, j2 + 1))
    return o2n, changed, inserted


def shift_spans(spans, o2n, changed, n_old, n_new, hits):
    def to_new(x, side):
        if x in o2n:
            return o2n[x]
        lo = x
        while lo > 0 and lo not in o2n:
            lo -= 1
        hi = x
        while hi <= n_old and hi not in o2n:
            hi += 1
        if side == "end":
            return o2n[lo] if lo > 0 else 0
        return o2n[hi] if hi <= n_old else n_new + 1
    out = []
    for a, b in spans:
        if set(range(a, b + 1)) & changed:
            hits.append([a, b])
        na, nb = to_new(a, "start"), to_new(b, "end")
        if na <= nb:
            out.append([na, nb])
    return out


def shift_map(data, o2n, changed, inserted, n_old, n_new):
    cand = set()
    for e in data["explanations"]:
        hits = []
        e["block_lines"] = shift_spans(e["block_lines"], o2n, changed, n_old, n_new, hits)
        for p in e["parts"]:
            p["own_lines"] = shift_spans(p["own_lines"], o2n, changed, n_old, n_new, hits)
            for c in p.get("callee_lines", []):
                c["lines"] = shift_spans(c["lines"], o2n, changed, n_old, n_new, hits)
            for c in p.get("constant_lines", []):
                c["lines"] = shift_spans(c["lines"], o2n, changed, n_old, n_new, hits)
        if hits or expand(e["block_lines"]) & inserted:
            cand.add(e["id"])
    return cand


def check_sync(m, data, new_lines, cand):
    assert isinstance(m, dict), "[SYNC-SHAPE] the answer must be one JSON object"
    stale = m.get("stale") or []
    edits = m.get("part_edits") or []
    texts = m.get("texts") or {}
    assert isinstance(stale, list) and isinstance(edits, list) and isinstance(texts, dict), \
        "[SYNC-SHAPE] stale is a list, part_edits is a list, texts is an object"
    n = len(new_lines)
    need = set()
    for s in stale:
        assert isinstance(s, dict) and s.get("entry") in cand, \
            f"[SYNC-STALE] every stale record names a candidate entry, got {s}"
        assert isinstance(s.get("old"), str) and s["old"].strip(), \
            "[SYNC-STALE] a stale record needs the old line"
        assert isinstance(s.get("new"), str), \
            "[SYNC-STALE] a stale record needs the new line, empty when the line dies"
        need.add(s["entry"])
    final_names = {}
    for pe in edits:
        eid = pe.get("entry")
        assert eid in cand, f"[SYNC-EDIT] part_edits entry {eid} is not a candidate"
        e = next(x for x in data["explanations"] if x["id"] == eid)
        names = final_names.get(eid, [p["part"] for p in e["parts"]])
        block_set = expand(e["block_lines"])
        for r in pe.get("remove") or []:
            assert r in names, f"[SYNC-EDIT] cannot remove {r!r}, entry {eid} has no such part"
            kids = [k["id"] for k in data["explanations"]
                    if (k.get("within") or {}).get("explanation") == eid
                    and k["within"].get("part") == r]
            assert not kids, f"[SYNC-EDIT] part {r!r} of entry {eid} has child zooms {kids}; undo them first"
            names.remove(r)
        for adm in pe.get("add") or []:
            nm = (adm.get("part") or "").strip()
            assert nm, "[SYNC-EDIT] an added part needs a name"
            assert nm not in names, f"[SYNC-EDIT] entry {eid} already has a part {nm!r}"
            own = check_spans(adm.get("own_lines"), n, "SYNC-EDIT")
            assert own, f"[SYNC-EDIT] the added part {nm!r} needs own lines"
            bad = expand(own) - block_set
            assert not bad, f"[SYNC-EDIT] part {nm!r} has own lines {fmt(bad)} outside entry {eid}"
            adm["part"] = nm
            adm["own_lines"] = own
            after = adm.get("after_part")
            assert after in names, f"[SYNC-EDIT] after_part {after!r} is not a part of entry {eid}"
            names.insert(names.index(after) + 1, nm)
        final_names[eid] = names
        need.add(eid)
    for eid in need:
        assert str(eid) in texts, f"[SYNC-TEXTS] entry {eid} changed, texts must carry its full new text"
    updates = []
    for key, text in texts.items():
        assert str(key).isdigit() and int(key) in cand, \
            f"[SYNC-TEXTS] texts key {key} is not a candidate entry"
        eid = int(key)
        assert isinstance(text, str) and text.strip(), f"[SYNC-TEXTS] the text of entry {eid} is empty"
        e = next(x for x in data["explanations"] if x["id"] == eid)
        names = final_names.get(eid, [p["part"] for p in e["parts"]])
        ls = [l.strip() for l in text.split("\n") if l.strip()]
        i = 0
        for nm in names:
            while i < len(ls) and not part_line(ls[i], nm):
                i += 1
            assert i < len(ls), f"[SYNC-PARTS] the new text of entry {eid} must keep every part name, " \
                                f"in order; no line starts with {nm!r}"
            i += 1
        new_set = set(ls)
        for k in data["explanations"]:
            w = k.get("within") or {}
            if w.get("explanation") != eid or not w.get("instruction"):
                continue
            instr = w["instruction"]
            if instr in new_set:
                continue
            rec = next((s for s in stale if s["entry"] == eid and s["old"] == instr), None)
            assert rec and rec["new"].strip() and rec["new"].strip() in new_set, \
                f"[SYNC-INSTRUCTION] entry {k['id']} hangs on the line {instr!r}; the new text must " \
                f"keep that line, or a stale record must map it to a line of the new text"
            updates.append((k["id"], rec["new"].strip()))
    return stale, edits, texts, updates


def cmd_sync(a):
    code_path = Path(a.code_file).resolve()
    map_path, data = load_existing(code_path)
    new_lines = code_path.read_text().splitlines()
    old = old_lines_of(code_path, a.old)
    if old == new_lines:
        print("nothing changed")
        return
    o2n, changed, inserted = line_map(old, new_lines)
    cand = shift_map(data, o2n, changed, inserted, len(old), len(new_lines))
    print(f"changed old lines: {fmt(changed) if changed else 'none'}; "
          f"inserted new lines: {fmt(inserted) if inserted else 'none'}")
    if not cand:
        missing, blank = recompute(data, new_lines)
        map_path.write_text(json.dumps(data, indent=2) + "\n")
        total = len(new_lines) - len(blank)
        print("spans renumbered, no entry touches the change, no claude call")
        print(f"covered: {total - len(missing)} of {total} code lines")
        print(f"wrote {map_path}")
        return
    print(f"candidate entries: {', '.join(str(i) for i in sorted(cand))}")
    facts = [f"deleted old line {i}: {old[i - 1].strip()}" for i in sorted(changed)]
    facts += [f"inserted new line {i}: {new_lines[i - 1].strip()}" for i in sorted(inserted)]
    cands = "\n\n".join(
        f"=== entry {e['id']} (block {e['block']}), parts: {', '.join(p['part'] for p in e['parts'])} ===\n{e['text']}"
        for e in data["explanations"] if e["id"] in cand)
    diff = "\n".join(difflib.unified_diff(old, new_lines, "old", "new", lineterm=""))
    prompt = (SYNC_PROMPT.replace("<code_file>", code_path.name)
              .replace("<diff>", diff)
              .replace("<facts>", "\n".join(facts))
              .replace("<candidates>", cands))
    got = None
    last = ""
    suffix = ""
    for _ in range(a.tries):
        try:
            m = ask_claude(prompt + suffix)
        except (ValueError, KeyError) as e:
            last = f"the answer was not one JSON object: {e}"
            suffix = "\n\nYour previous answer was not one JSON object. Return only the JSON."
            continue
        try:
            got = check_sync(m, data, new_lines, cand)
            break
        except AssertionError as e:
            last = str(e)
            suffix = f"\n\nYour previous answer:\n{json.dumps(m)}\n\n" \
                     f"It broke this rule: {last}\nReturn the full corrected JSON object."
    if got is None:
        sys.exit(f"the sync failed after {a.tries} tries, last error: {last}")
    stale, edits, texts, updates = got
    for pe in edits:
        e = next(x for x in data["explanations"] if x["id"] == pe["entry"])
        for r in pe.get("remove") or []:
            e["parts"] = [p for p in e["parts"] if p["part"] != r]
            print(f"entry {pe['entry']}: part {r!r} removed")
        for adm in pe.get("add") or []:
            idx = next(i for i, p in enumerate(e["parts"]) if p["part"] == adm["after_part"]) + 1
            e["parts"].insert(idx, {"part": adm["part"], "own_lines": adm["own_lines"],
                                    "callee_lines": [], "constant_lines": []})
            print(f"entry {pe['entry']}: part {adm['part']!r} added at lines {fmt(expand(adm['own_lines']))}")
    for key, text in texts.items():
        e = next(x for x in data["explanations"] if x["id"] == int(key))
        e["text"] = text.strip()
    for kid, instr in updates:
        e = next(x for x in data["explanations"] if x["id"] == kid)
        e["within"]["instruction"] = instr
        print(f"entry {kid}: instruction moved to {instr!r}")
    for s in stale:
        print(f"entry {s['entry']}: {s['old']!r} -> {s['new']!r}" if s["new"].strip()
              else f"entry {s['entry']}: {s['old']!r} removed")
    missing, blank = recompute(data, new_lines)
    map_path.write_text(json.dumps(data, indent=2) + "\n")
    for e in data["explanations"]:
        inside = expand(e["block_lines"]) & inserted
        if not inside:
            continue
        cov = set()
        for p in e["parts"]:
            cov |= part_lines(p)
        loose = inside - cov
        if loose:
            print(f"warning: entry {e['id']} has inserted lines {fmt(loose)} in no part")
    total = len(new_lines) - len(blank)
    print(f"covered: {total - len(missing)} of {total} code lines")
    print(f"not covered: {fmt(missing) if missing else 'nothing'}")
    print(f"wrote {map_path}")


def main():
    ap = argparse.ArgumentParser(prog="dmap")
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("map")
    m.add_argument("code_file")
    m.add_argument("--block")
    m.add_argument("--within")
    m.add_argument("--at")
    m.add_argument("--text")
    m.add_argument("--tries", type=int, default=8)
    r = sub.add_parser("retext")
    r.add_argument("code_file")
    r.add_argument("id", type=int)
    r.add_argument("--text")
    u = sub.add_parser("undo")
    u.add_argument("code_file")
    s = sub.add_parser("show")
    s.add_argument("code_file")
    l = sub.add_parser("lines")
    l.add_argument("code_file")
    y = sub.add_parser("sync")
    y.add_argument("code_file")
    y.add_argument("--old")
    y.add_argument("--tries", type=int, default=4)
    a = ap.parse_args()
    {"map": cmd_map, "retext": cmd_retext, "undo": cmd_undo,
     "show": cmd_show, "lines": cmd_lines, "sync": cmd_sync}[a.cmd](a)


if __name__ == "__main__":
    main()
