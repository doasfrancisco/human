import argparse
import ast
import json
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
 "within": {"explanation": <entry id>, "part": "<part name>"} or null,
 "parts": [
   {"part": "<left-column name from the text>",
    "own_lines": [[start, end]],
    "callee_lines": [{"name": "<block>", "lines": [[start, end]]}],
    "constant_lines": [{"name": "<CONSTANT>", "lines": [[start, end]]}],
    "outside_within": true,
    "note": "<where these lines belong>"}]}

The rules:
- One part per left-column name of the text, in the order of the text.
- own_lines are the lines inside block_lines that the part describes.
- callee_lines hold the full span of every block the part calls, copied verbatim from the block table, plus the blocks those blocks call when the part is the one that reaches them.
- constant_lines hold the module constants the part uses.
- A part whose own lines sit outside block_lines gets "outside_within": true and a note that says which entry and part those lines belong to. Only such a part carries these two keys.
- within points to the one already-mapped part whose lines contain this block. Use null when no mapped part contains it.
- Map only this text. Do not restate or change the entries already mapped.
"""


def numbered(lines):
    return "\n".join(f"{i:4} {l}" for i, l in enumerate(lines, 1))


def block_spans(path, lines):
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
        out["within"] = {"explanation": parent["id"], "part": ppart["part"]}
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
    existing = [{"id": e["id"], "block": e["block"], "block_lines": e["block_lines"],
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
            m["within"] = within_arg
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
    print(f"entry {eid}: {record['block']}, lines {fmt(expand(record['block_lines']))}, "
          f"{len(record['parts'])} parts{tail}")
    print("parts: " + ", ".join(p["part"] for p in record["parts"]))
    total = len(lines) - len(blank)
    print(f"covered: {total - len(missing)} of {total} code lines")
    print(f"not covered: {fmt(missing) if missing else 'nothing'}")
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


def main():
    ap = argparse.ArgumentParser(prog="dmap")
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("map")
    m.add_argument("code_file")
    m.add_argument("--block")
    m.add_argument("--within")
    m.add_argument("--text")
    m.add_argument("--tries", type=int, default=8)
    s = sub.add_parser("show")
    s.add_argument("code_file")
    l = sub.add_parser("lines")
    l.add_argument("code_file")
    a = ap.parse_args()
    {"map": cmd_map, "show": cmd_show, "lines": cmd_lines}[a.cmd](a)


if __name__ == "__main__":
    main()
