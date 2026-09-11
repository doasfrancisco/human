import argparse
import ast
import difflib
import json
import re
import subprocess
import sys
from pathlib import Path

from . import cmd_map, cmd_project

ANCHOR_RE = re.compile(r"\[([^\[\]]+)\]\(([^()]+)\)")

SYNC_PROMPT = """A code file changed. Explanation texts were written for the old version of the file. Mend the words the change made wrong, and add a sentence for each behaviour the change added.

The file is <code_file>. Read the whole file at <path> before you answer; the diff below shows only the changed lines, not the blocks around them. The unified diff of the change:

<diff>

<touched>

The blocks of the new file, with their exact line spans:

<span_table>

The candidate entries, each with its full text:

<candidates>

Anchors look like [words](block) or [words](e1:anchor words). The rules:
- A text line is stale only when the change makes its words wrong. A line whose code moved but whose words still hold is not stale.
- Rewrite a stale line with the smallest edit. Keep every line the change does not touch verbatim. Keep the vocabulary, the layout, and the indentation.
- Keep every anchor. When a block was renamed, keep the anchor words and update the target to the new block name.
- These anchor words are pointed at by other entries and must survive unchanged:
<needed>
- A new bound name in the code needs a new line, in code order, in the style of the text. A dead name loses its line.
- When the change adds a behaviour the reader would ask about — a new option, a new step, a new case — add a sentence for it where the reader meets it, in the style of the text. The reader does not read code: say what the thing does, not its class.
- An entry whose words all still hold, and whose block gained no behaviour, gets no key in the answer.
- An entry marked as the user's own words gets the smallest edit, in the user's voice, and no sentence the change does not force.
- When an entry's own block was renamed, put its new name in blocks.

Return one JSON object and nothing else:

{"texts": {"<entry id>": "<the full corrected text>"},
 "blocks": {"<entry id>": "<the new name of the entry's block, only when it was renamed>"}}
"""

STALE_PROMPT = """An explanation depends on other explanations through anchors. One or more of them changed. Mend the words the changes made wrong, and carry the new facts down.

The changed explanations, each with its old text, its new text, and the diff between the two:

<parents>

The dependent text to repair:

---
<child>
---

Anchors look like [words](block), [words](path/of/file), or a pin at an anchor of a changed explanation in the form shown beside it. The rules:
- Rewrite a line only when a change upstairs makes its words wrong. Keep every line the changes do not touch verbatim. Keep the vocabulary, the layout, and the indentation.
- When a changed explanation gained a sentence about a new behaviour, add a sentence for it in the dependent text, at the dependent's own level of detail — a plainer layer says less, never nothing. Pin it at the new sentence's anchor when it has one.
- Keep every anchor.
- These anchor words are pointed at by other entries and must survive unchanged: <needed>
<verbatim>
Return one JSON object and nothing else:

{"text": "<the full corrected dependent text>"}
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


def tag_spans(lines):
    first, count = {}, {}
    for i, l in enumerate(lines, 1):
        m = re.match(r"\s*<([a-zA-Z][\w-]*)", l)
        if not m:
            continue
        name = m.group(1)
        count[name] = count.get(name, 0) + 1
        first.setdefault(name, i)
    spans = {}
    for name, i in first.items():
        if count[name] != 1:
            continue
        if re.search(rf"</{name}\s*>", lines[i - 1]):
            spans[name] = [i, i]
            continue
        for j in range(i + 1, len(lines) + 1):
            if re.match(rf"\s*</{name}\s*>", lines[j - 1]):
                spans[name] = [i, j]
                break
    return spans


def brace_delta(line):
    depth, quote, i = 0, None, 0
    while i < len(line):
        c = line[i]
        if quote:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                quote = None
        elif c in "\"'`":
            quote = c
        elif c == "/" and line[i:i + 2] == "//":
            break
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        i += 1
    return depth


def script_regions(lines):
    regions, start = [], None
    for i, l in enumerate(lines, 1):
        if start is None and re.search(r"<script\b", l):
            start = i
            if re.search(r"</script\s*>", l):
                regions.append((i, i))
                start = None
            continue
        if start is not None and re.search(r"</script\s*>", l):
            regions.append((start, i))
            start = None
    if start is not None:
        regions.append((start, len(lines)))
    return regions


def js_spans(path, lines, regions):
    spans = {}
    for lo, hi in regions:
        depth, stack = 0, []
        for i in range(lo, hi + 1):
            line = lines[i - 1]
            m = re.match(r"\s*function\s+([A-Za-z_$][\w$]*)\s*\(", line)
            if m:
                stack.append((m.group(1), i, depth))
            depth += brace_delta(line)
            while stack and depth <= stack[-1][2]:
                name, start, _ = stack.pop()
                if name in spans:
                    sys.exit(f"duplicate function {name!r} in {path.name}; "
                             f"names must be unique to serve as block names")
                spans[name] = [start, i]
        for name, start, _ in stack:
            if name not in spans:
                spans[name] = [start, hi]
    return spans


def html_spans(path, lines):
    spans = tag_spans(lines)
    for name, span in js_spans(path, lines, script_regions(lines)).items():
        if name in spans:
            sys.exit(f"the function {name!r} in {path.name} has the name of a tag; "
                     f"names must be unique to serve as block names")
        spans[name] = span
    return spans


def block_spans(path, lines):
    if path.suffix == ".md":
        return md_spans(path, lines)
    if path.suffix in (".html", ".htm"):
        return html_spans(path, lines)
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


def import_names(lines):
    try:
        tree = ast.parse("\n".join(lines))
    except SyntaxError:
        return set()
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(n.name.split(".")[0] for n in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level <= 1:
            if node.module:
                names.add(node.module.split(".")[0])
            elif node.level == 1:
                names.update(n.name for n in node.names)
    return names


PAGE_IMPORT_RE = re.compile(r"""(?:from\s+|<script[^>]*\bsrc=)["']\./?([^"']+)["']""")


def sibling_imports(code_path, lines, root):
    if code_path.suffix == ".py":
        cands = [f"{nm}.py" for nm in import_names(lines)]
    elif code_path.suffix in (".html", ".htm"):
        cands = [m.group(1) for l in lines for m in PAGE_IMPORT_RE.finditer(l)]
    else:
        return set()
    out = set()
    for c in cands:
        sib = code_path.parent / c
        if sib.is_file() and root in sib.resolve().parents:
            out.add(rel_name(sib.resolve(), root))
    return out


def blocks_of(lines, spans, code_name):
    names = []
    for i in sorted(lines):
        holders = [(hi - lo, nm) for nm, (lo, hi) in spans.items() if lo <= i <= hi]
        nm = min(holders)[1] if holders else code_name
        if nm not in names:
            names.append(nm)
    return ", ".join(names)


def touched_note(code_path, old, new, root):
    was = sibling_imports(code_path, old, root)
    now = sibling_imports(code_path, new, root)
    if not was and not now:
        return ""
    names = [", ".join(sorted(s)) or "none" for s in (now, now - was, was - now)]
    return (f"The file imports these files of the project: {names[0]} — added by this change: "
            f"{names[1]} — removed: {names[2]}. Their paths start at {root}. "
            f"Read the ones a new sentence needs; do not read the rest of the project.")


def norm_dup(line):
    line = ANCHOR_RE.sub(lambda m: m.group(1), line)
    return " ".join(re.findall(r"[0-9a-z']+", line.lower()))


def dup_warnings(root):
    h = root / "human"
    paths = sorted(h.glob("explanation_*.json"))
    if (h / "human.json").exists():
        paths.append(h / "human.json")
    seen = {}
    out = []
    for mp in paths:
        data = json.loads(mp.read_text())
        fname = "human.json" if mp.name == "human.json" else data.get("code_file", mp.name)
        for e in data["explanations"]:
            for raw in e["text"].splitlines():
                key = norm_dup(raw)
                if len(key) < 30:
                    continue
                first = seen.setdefault(key, (fname, e["id"]))
                if first[0] != fname:
                    shown = raw.strip().lstrip("│●○·─ ").strip()
                    out.append(f'the line "{shown[:60]}" is in {first[0]} entry {first[1]} '
                               f"and in {fname} entry {e['id']} — one telling, one home")
    return out


def expand(span_list):
    s = set()
    for a, b in span_list:
        s.update(range(a, b + 1))
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


def parse_target(raw):
    m = re.match(r"e(\d+):(.+)$", raw.strip())
    if m:
        return {"explanation": int(m.group(1)), "anchor": m.group(2).strip()}
    return {"block": raw.strip()}


def resolve_code_target(words, raw, spans, folder):
    if raw in spans:
        return {"words": words, "block": raw, "lines": [list(spans[raw])]}
    if ":" in raw:
        fname, bname = (s.strip() for s in raw.split(":", 1))
        fp = folder / fname
        assert fp.is_file(), \
            f"[ANCHOR-TARGET] the anchor {words!r} names {fname!r}, which is not a file of the folder"
        fspans = block_spans(fp, fp.read_text().splitlines())
        assert bname in fspans, \
            f"[ANCHOR-TARGET] the anchor {words!r} names {bname!r}, which is not a block of {fname}"
        return {"words": words, "file": fname, "block": bname, "lines": [list(fspans[bname])]}
    if (folder / raw).is_file():
        return {"words": words, "file": raw}
    raise AssertionError(f"[ANCHOR-TARGET] {raw!r} is not a block of this file "
                         f"and not a file of the folder")


def project_pins(anchors):
    bad = [x["words"] for x in anchors if "file" not in x]
    assert not bad, f"[PROJECT-PIN] a project pin points at a file or a block of a file; " \
                    f"{', '.join(repr(w) for w in bad)} does not"


def build_anchors(text, data, spans, self_id, folder):
    seen = set()
    out = []
    for m in ANCHOR_RE.finditer(text):
        words = m.group(1).strip()
        assert words, "[ANCHOR-WORDS] an anchor needs words inside the brackets"
        assert words not in seen, \
            f"[ANCHOR-WORDS] the anchor {words!r} appears twice; anchor words are unique in one text"
        seen.add(words)
        tgt = parse_target(m.group(2))
        if "block" in tgt:
            b = tgt["block"]
            assert b, f"[ANCHOR-TARGET] the anchor {words!r} needs a target"
            out.append(resolve_code_target(words, b, spans, folder))
        else:
            pid = tgt["explanation"]
            assert pid != self_id, f"[ANCHOR-TARGET] the anchor {words!r} points at its own entry"
            parent = next((e for e in data["explanations"] if e["id"] == pid), None)
            assert parent, f"[ANCHOR-TARGET] explanation {pid} does not exist"
            names = {x["words"] for x in parent.get("anchors", [])}
            assert tgt["anchor"] in names, \
                f"[ANCHOR-TARGET] explanation {pid} has no anchor {tgt['anchor']!r}"
            out.append({"words": words, "explanation": pid, "anchor": tgt["anchor"]})
    return out


def check_cycle(data, self_id, anchors):
    frontier = [a["explanation"] for a in anchors if "explanation" in a]
    seen = set()
    while frontier:
        pid = frontier.pop()
        assert pid != self_id, \
            f"[ANCHOR-CYCLE] explanation {self_id} reaches itself through its anchors"
        if pid in seen:
            continue
        seen.add(pid)
        e = next((x for x in data["explanations"] if x["id"] == pid), None)
        if e:
            frontier += [a["explanation"] for a in e.get("anchors", []) if "explanation" in a]


def children_of(data, eid):
    return [e for e in data["explanations"]
            if any(a.get("explanation") == eid for a in e.get("anchors", []))]


def needed_words(data, eid):
    return {a["anchor"] for e in data["explanations"]
            for a in e.get("anchors", []) if a.get("explanation") == eid}


def stale_notes(e):
    st = e.get("stale")
    if not st:
        return []
    return st if isinstance(st, list) else [st]


def add_note(e, note):
    notes = stale_notes(e)
    if not any(n["parent"] == note["parent"] and n.get("file") == note.get("file") for n in notes):
        e["stale"] = notes + [note]


def mark_children(data, eid, old_text):
    kids = []
    for c in children_of(data, eid):
        add_note(c, {"parent": eid, "old_text": old_text})
        kids.append(c["id"])
    return kids


def stale_tail(e, same="explanation"):
    parts = [f"{n['file']} entry {n['parent']}" if n.get("file") else f"{same} {n['parent']}"
             for n in stale_notes(e)]
    return f"  stale ({', '.join(parts)} changed)" if parts else ""


def strip_pins(text):
    return ANCHOR_RE.sub(lambda m: m.group(1), text)


def origin_of(e):
    v = e.get("verbatim")
    if isinstance(v, dict):
        return v.get("origin")
    return strip_pins(e["text"]) if v else None


def reworded(e):
    origin = origin_of(e)
    return origin is not None and strip_pins(e["text"]) != origin


def verbatim_tail(e):
    if origin_of(e) is None:
        return ""
    return "  your words, reworded since they were mapped" if reworded(e) else "  your words"


def verbatim_hint(e, name):
    if reworded(e):
        return [f"entry {e['id']} holds your words, reworded since they were mapped; bring them back with "
                f"human retext {name} {e['id']} --verbatim and the origin text kept in the map"]
    return []


def verbatim_gate(entry, text, flag):
    if flag:
        entry["verbatim"] = {"origin": strip_pins(text)}
        return
    if origin_of(entry) is not None and strip_pins(text) != strip_pins(entry["text"]):
        sys.exit(f"entry {entry['id']} holds the user's words; pins may go in, the words may not change — "
                 f"to change the words say --verbatim")


def verbatim_mark(e):
    return " — the user's own words" if origin_of(e) is not None else ""


def verbatim_rule(e):
    if origin_of(e) is None:
        return ""
    return "- This entry holds the user's own words: the smallest edit, in the user's voice, " \
           "and no sentence the change does not force.\n"


def warn_reworded(e, before_text, text, by):
    if origin_of(e) is not None and strip_pins(before_text) != strip_pins(text):
        print(f"warning: entry {e['id']} holds your words; the {by} changed them")


def parent_note(pid, form, old, new):
    diff = "\n".join(difflib.unified_diff(old.splitlines(), new.splitlines(), "old", "new", lineterm=""))
    return (f"=== explanation {pid} — a pin at one of its anchors reads {form} ===\n\n"
            f"The old text:\n\n---\n{old}\n---\n\nThe new text:\n\n---\n{new}\n---\n\n"
            f"The unified diff between the two:\n\n{diff}")


def recompute(data, lines):
    blank = [i for i, l in enumerate(lines, 1) if not l.strip()]
    covered = set()
    for e in data["explanations"]:
        covered |= expand(e["block_lines"])
        for a in e.get("anchors", []):
            if "lines" in a and "file" not in a:
                covered |= expand(a["lines"])
    missing = [i for i in range(1, len(lines) + 1) if i not in covered and i not in set(blank)]
    data["not_covered"] = {"code_lines": missing, "blank_lines": blank}
    return missing, blank


def ask_claude(prompt, root):
    r = subprocess.run(["claude", "-p", "--output-format", "json"], input=prompt,
                       capture_output=True, text=True, timeout=600, cwd=str(root))
    if r.returncode != 0:
        sys.exit(f"claude failed: {r.stderr[-500:]}")
    raw = json.loads(r.stdout)["result"]
    return json.loads(raw[raw.index("{"):raw.rindex("}") + 1])


def guard_structure(data, map_path):
    if any("parts" in e for e in data.get("explanations", [])):
        sys.exit(f"{map_path.name} carries the old part structure; "
                 f"this human reads anchors — rebuild the map with human map")
    for e in data.get("explanations", []):
        if isinstance(e.get("stale"), dict):
            e["stale"] = [e["stale"]]


def find_root(path):
    d = path if path.is_dir() else path.parent
    while True:
        if (d / "human" / "human.json").is_file():
            return d
        if d.parent == d:
            sys.exit(f"no human/ folder at or above {path}; run human init at the project root")
        d = d.parent


def rel_name(code_path, root=None):
    root = root or find_root(code_path)
    if code_path == root:
        return root.name
    return code_path.relative_to(root).as_posix()


def map_path_of(code_path, root=None):
    root = root or find_root(code_path)
    if code_path.is_dir():
        return root / "human" / "human.json"
    rel = code_path.relative_to(root).as_posix()
    return root / "human" / f"explanation_{rel.replace('/', '__')}.json"


def register_file(root, rel):
    map_path = root / "human" / "human.json"
    data = json.loads(map_path.read_text())
    files = data.setdefault("files", [])
    if rel not in files:
        files.append(rel)
        files.sort()
        map_path.write_text(json.dumps(data, indent=2) + "\n")


def load_existing(code_path):
    map_path = map_path_of(code_path)
    if not map_path.exists():
        sys.exit(f"no map file at {map_path}")
    data = json.loads(map_path.read_text())
    guard_structure(data, map_path)
    return map_path, data


def read_text_arg(a):
    text = (Path(a.text).read_text() if a.text else sys.stdin.read()).strip()
    if not text:
        sys.exit("no explanation text on stdin or --text")
    return text


def anchor_counts(anchors):
    code = sum(1 for x in anchors if "block" in x and "file" not in x)
    cross = sum(1 for x in anchors if "file" in x)
    up = len(anchors) - code - cross
    parts = [f"{code} into the code"]
    if cross:
        parts.append(f"{cross} into other files")
    parts.append(f"{up} into earlier explanations")
    return f"{len(anchors)} anchors ({', '.join(parts)})"


def print_coverage(missing, blank, lines):
    total = len(lines) - len(blank)
    print(f"covered: {total - len(missing)} of {total} code lines")
    print(f"not covered: {fmt(missing) if missing else 'nothing'}")


def report_text_diff(eid, old, new):
    ol, nl = old.split("\n"), new.split("\n")
    sm = difflib.SequenceMatcher(None, ol, nl, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        for l in ol[i1:i2]:
            print(f"entry {eid}: - {l.strip()}")
        for l in nl[j1:j2]:
            print(f"entry {eid}: + {l.strip()}")


def report_project_stale(ids):
    if ids:
        print(f"entries {', '.join(map(str, ids))} of the project map depend on the changed entry and "
              f"are marked stale; repair each with human sync project --stale <id>")


def cmd_retext(a):
    code_path = Path(a.code_file).resolve()
    root = find_root(code_path)
    map_path, data = load_existing(code_path)
    folder = root
    if code_path.is_dir():
        lines, spans = [], {}
    else:
        lines = code_path.read_text().splitlines()
        spans = block_spans(code_path, lines)
    entry = next((e for e in data["explanations"] if e["id"] == a.id), None)
    if entry is None:
        sys.exit(f"no entry {a.id} in {map_path.name}")
    text = read_text_arg(a)
    code_name = rel_name(code_path, root)
    need = needed_words(data, a.id) | cmd_project.pins_into(root, code_name, a.id)
    try:
        anchors = build_anchors(text, data, spans, a.id, folder)
        if code_path.is_dir():
            project_pins(anchors)
        gone = need - {x["words"] for x in anchors}
        assert not gone, f"[RETEXT-ANCHORS] other entries point at the anchors {sorted(gone)}; " \
                         "the new text must keep them"
        check_cycle(data, a.id, anchors)
    except AssertionError as e:
        sys.exit(str(e))
    verbatim_gate(entry, text, getattr(a, "verbatim", False))
    old_text = entry["text"]
    entry["text"] = text
    entry["anchors"] = anchors
    changed = strip_pins(text) != strip_pins(old_text)
    kids = mark_children(data, a.id, old_text) if changed else []
    missing, blank = recompute(data, lines)
    map_path.write_text(json.dumps(data, indent=2) + "\n")
    print(f"entry {a.id} ({entry['block']}): text replaced, {anchor_counts(anchors)}")
    if not changed and text != old_text:
        print(f"entry {a.id}: pins changed, no word changed")
    if kids:
        print(f"entries {', '.join(map(str, kids))} depend on entry {a.id} and are marked stale; "
              f"repair each with human sync {code_name} --stale <id>")
    report_project_stale(cmd_project.mark_stale(root, code_name, a.id, old_text) if changed else [])
    from . import cmd_train
    cmd_train.refresh_row(root, code_name, a.id, old_text, text)
    if stale_notes(entry):
        print(f"entry {a.id} stays stale; repair it with human sync {code_name} --stale {a.id}")
    print(f"wrote {map_path}")


def undo_target(data, eid):
    if eid is None:
        return data["explanations"][-1]
    entry = cmd_project.entry_of(data, eid)
    if entry is None:
        sys.exit(f"no entry {eid} in the map")
    return entry


def undo_gate(root, data, name, entry):
    kids = [e["id"] for e in children_of(data, entry["id"])]
    if kids:
        sys.exit(f"entries {kids} point at entry {entry['id']} through anchors; undo them first")
    if name != cmd_project.WORD and cmd_project.pins_into(root, name, entry["id"]):
        sys.exit(f"the project map points at entry {entry['id']} through anchors; retext it first")
    from . import cmd_store
    if not cmd_store.credentials():
        return
    try:
        session = cmd_store.open_session(cmd_store.project_id(root))
    except (cmd_store.Refused, cmd_store.Unreachable) as e:
        sys.exit(f"the undo cannot check the open training session: {e}")
    rows = [i for i, r in enumerate(session["rows"])
            if r["file"] == name and r["entry"] == entry["id"] and not r["applied"]] if session else []
    if rows:
        sys.exit(f"the open training session holds row {rows[0]} on entry {entry['id']}; close it first")


def cmd_undo(a):
    code_path = Path(a.code_file).resolve()
    map_path, data = load_existing(code_path)
    if not data["explanations"]:
        sys.exit("nothing to undo")
    root = find_root(code_path)
    gone = undo_target(data, a.entry)
    undo_gate(root, data, rel_name(code_path, root), gone)
    data["explanations"].remove(gone)
    lines = [] if code_path.is_dir() else code_path.read_text().splitlines()
    missing, blank = recompute(data, lines)
    map_path.write_text(json.dumps(data, indent=2) + "\n")
    tail = "" if code_path.is_dir() else f", lines {fmt(expand(gone['block_lines']))}"
    print(f"removed entry {gone['id']}: {gone['block']}{tail}")
    if not code_path.is_dir():
        print_coverage(missing, blank, lines)
    print(f"wrote {map_path}")


def cmd_show(a):
    code_path = Path(a.code_file).resolve()
    root = find_root(code_path)
    map_path = map_path_of(code_path, root)
    if not map_path.exists():
        print(f"no map file at {map_path}")
        if code_path.is_dir():
            for w in dup_warnings(root):
                print(f"warning: {w}")
        return
    data = json.loads(map_path.read_text())
    guard_structure(data, map_path)
    is_dir = code_path.is_dir()
    lines = [] if is_dir else code_path.read_text().splitlines()
    spans = {} if is_dir else block_spans(code_path, lines)
    folder = root
    code_name = rel_name(code_path, root)
    warnings = []
    for e in data["explanations"]:
        tail = stale_tail(e) + verbatim_tail(e)
        where = fmt(expand(e["block_lines"])) or "-"
        print(f"{e['id']:3}  {e['block']:<24} {where:<14} "
              f"{len(e.get('anchors', []))} anchors{tail}")
        warnings += verbatim_hint(e, code_name)
        derived = [m.group(1).strip() for m in ANCHOR_RE.finditer(e["text"])]
        stored = [x["words"] for x in e.get("anchors", [])]
        if derived != stored:
            warnings.append(f"entry {e['id']}: the anchors in the text do not match the stored anchors; "
                            f"rebuild the entry with human retext")
        for x in e.get("anchors", []):
            if "file" in x:
                fp = folder / x["file"]
                if not fp.is_file():
                    warnings.append(f"entry {e['id']}: the anchor {x['words']!r} names the file "
                                    f"{x['file']!r}, which is not in the folder")
                elif "block" in x:
                    fspans = block_spans(fp, fp.read_text().splitlines())
                    if x["block"] not in fspans:
                        warnings.append(f"entry {e['id']}: the anchor {x['words']!r} names the block "
                                        f"{x['block']!r}, which is not in {x['file']}; run human sync")
                    elif x.get("lines") != [list(fspans[x["block"]])]:
                        warnings.append(f"entry {e['id']}: the anchor {x['words']!r} holds old lines "
                                        f"for {x['file']}:{x['block']}; run human sync")
            elif "block" in x:
                if x["block"] not in spans:
                    warnings.append(f"entry {e['id']}: the anchor {x['words']!r} names the block "
                                    f"{x['block']!r}, which is not in the file; run human sync")
                elif x.get("lines") != [list(spans[x["block"]])]:
                    warnings.append(f"entry {e['id']}: the anchor {x['words']!r} holds old lines "
                                    f"for {x['block']!r}; run human sync")
            else:
                parent = next((p for p in data["explanations"] if p["id"] == x["explanation"]), None)
                if not parent or x["anchor"] not in {y["words"] for y in parent.get("anchors", [])}:
                    warnings.append(f"entry {e['id']}: the anchor {x['words']!r} points at "
                                    f"e{x['explanation']}:{x['anchor']}, which does not exist")
        if not is_dir and e["block"] != code_name and e["block"] not in spans:
            warnings.append(f"entry {e['id']}: the block {e['block']!r} is not in the file; run human sync")
    if not is_dir and code_path.suffix == ".py":
        whole = next((e for e in data["explanations"] if e["block"] == code_name), None)
        if whole:
            pinned = {x.get("file") for x in whole.get("anchors", [])}
            for rel in sorted(sibling_imports(code_path, lines, root)):
                if map_path_of(root / rel, root).exists() and rel not in pinned:
                    warnings.append(f"{code_name} imports {rel} but entry {whole['id']} "
                                    f"has no pin to it")
    if is_dir:
        warnings += dup_warnings(root)
    for w in warnings:
        print(f"warning: {w}")
    if not is_dir:
        missing, blank = recompute(data, lines)
        print_coverage(missing, blank, lines)


def cmd_lines(a):
    code_path = Path(a.code_file).resolve()
    if code_path.is_dir():
        sys.exit("a folder has no lines")
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


def entry_lines_set(e):
    s = expand(e["block_lines"])
    for x in e.get("anchors", []):
        if "lines" in x:
            s |= expand(x["lines"])
    return s


def rewordable(e, code_name):
    return e["block"] != code_name or any("block" in x and "file" not in x for x in e.get("anchors", []))


def refresh_file_anchor(x, eid, folder):
    fp = folder / x["file"]
    if not fp.is_file():
        return [(eid, x["file"])]
    if "block" in x:
        fspans = block_spans(fp, fp.read_text().splitlines())
        if x["block"] not in fspans:
            return [(eid, f"{x['file']}:{x['block']}")]
        x["lines"] = [list(fspans[x["block"]])]
    return []


def re_resolve(data, code_name, spans, n, folder):
    broken = []
    for e in data["explanations"]:
        if e["block"] == code_name:
            if n:
                e["block_lines"] = [[1, n]]
        elif e["block"] in spans:
            e["block_lines"] = [list(spans[e["block"]])]
        else:
            broken.append((e["id"], e["block"]))
        for x in e.get("anchors", []):
            if "file" in x:
                broken += refresh_file_anchor(x, e["id"], folder)
            elif "block" in x:
                if x["block"] in spans:
                    x["lines"] = [list(spans[x["block"]])]
                else:
                    broken.append((e["id"], x["block"]))
    return broken


def rebuild_all(trial, code_name, spans, n, folder, texts, blocks, cand):
    for e in sorted(trial["explanations"], key=lambda x: x["id"]):
        newb = blocks.get(str(e["id"]))
        if newb is not None:
            assert e["id"] in cand, f"[SYNC-BLOCKS] entry {e['id']} is not a candidate"
            e["block"] = newb.strip()
        assert e["block"] == code_name or e["block"] in spans, \
            f"[SYNC-BLOCK] entry {e['id']} explains the block {e['block']!r}, which is not in the " \
            f"new file; name its new block in blocks"
        e["block_lines"] = [[1, n]] if e["block"] == code_name else [list(spans[e["block"]])]
        newt = texts.get(str(e["id"]))
        if newt is not None:
            assert e["id"] in cand, f"[SYNC-TEXTS] entry {e['id']} is not a candidate"
            assert newt.strip(), f"[SYNC-TEXTS] the text of entry {e['id']} is empty"
            e["text"] = newt.strip()
        try:
            anchors = build_anchors(e["text"], trial, spans, e["id"], folder)
        except AssertionError as err:
            raise AssertionError(f"in the text of entry {e['id']}: {err}") from None
        need = needed_words(trial, e["id"]) | cmd_project.pins_into(folder, code_name, e["id"])
        gone = need - {x["words"] for x in anchors}
        assert not gone, f"[SYNC-ANCHORS] other entries point at the anchors {sorted(gone)} of " \
                         f"entry {e['id']}; the new text must keep them"
        e["anchors"] = anchors
    for e in trial["explanations"]:
        for x in e.get("anchors", []):
            if "explanation" not in x:
                continue
            parent = next(p for p in trial["explanations"] if p["id"] == x["explanation"])
            assert x["anchor"] in {y["words"] for y in parent["anchors"]}, \
                f"[SYNC-ANCHORS] entry {e['id']} points at e{x['explanation']}:{x['anchor']}, " \
                f"which the new text of entry {x['explanation']} dropped"


def repair_stale(a, code_path, root, map_path, data, lines, spans):
    entry = next((e for e in data["explanations"] if e["id"] == a.stale), None)
    if entry is None:
        sys.exit(f"no entry {a.stale} in {map_path.name}")
    notes = stale_notes(entry)
    if not notes:
        sys.exit(f"entry {a.stale} is not stale")
    parents = []
    for st in notes:
        parent = next((e for e in data["explanations"] if e["id"] == st["parent"]), None)
        if parent is None:
            sys.exit(f"explanation {st['parent']} no longer exists; retext entry {a.stale} instead")
        parents.append(parent_note(parent["id"], f"[words](e{parent['id']}:anchor words)",
                                   st["old_text"], parent["text"]))
    code_name = rel_name(code_path, root)
    need = needed_words(data, entry["id"]) | cmd_project.pins_into(root, code_name, entry["id"])
    prompt = (STALE_PROMPT.replace("<parents>", "\n\n".join(parents))
              .replace("<child>", entry["text"])
              .replace("<needed>", ", ".join(sorted(need)) or "none")
              .replace("<verbatim>\n", verbatim_rule(entry)))
    text = None
    last = ""
    suffix = ""
    for _ in range(a.tries):
        try:
            m = ask_claude(prompt + suffix, root)
        except (ValueError, KeyError) as e:
            last = f"the answer was not one JSON object: {e}"
            suffix = "\n\nYour previous answer was not one JSON object. Return only the JSON."
            continue
        t = (m.get("text") or "").strip()
        try:
            assert t, "[STALE-TEXT] the answer needs the full dependent text"
            anchors = build_anchors(t, data, spans, entry["id"], root)
            gone = need - {x["words"] for x in anchors}
            assert not gone, f"[STALE-ANCHORS] other entries point at the anchors {sorted(gone)}; " \
                             "the text must keep them"
            check_cycle(data, entry["id"], anchors)
            text = t
            entry_anchors = anchors
            break
        except AssertionError as e:
            last = str(e)
            suffix = f"\n\nYour previous answer:\n{json.dumps(m)}\n\n" \
                     f"It broke this rule: {last}\nReturn the full corrected JSON object."
    if text is None:
        sys.exit(f"the repair failed after {a.tries} tries, last error: {last}")
    old_text = entry["text"]
    entry["text"] = text
    entry["anchors"] = entry_anchors
    entry.pop("stale")
    warn_reworded(entry, old_text, text, "repair")
    report_text_diff(entry["id"], old_text, text)
    if text == old_text:
        print(f"entry {entry['id']}: no word changed")
    changed = strip_pins(text) != strip_pins(old_text)
    kids = mark_children(data, entry["id"], old_text) if changed else []
    if kids:
        print(f"entries {', '.join(map(str, kids))} depend on entry {entry['id']} and are marked stale")
    report_project_stale(cmd_project.mark_stale(root, code_name, entry["id"], old_text) if changed else [])
    missing, blank = recompute(data, lines)
    map_path.write_text(json.dumps(data, indent=2) + "\n")
    print_coverage(missing, blank, lines)
    print(f"wrote {map_path}")


def cmd_sync(a):
    code_path = Path(a.code_file).resolve()
    root = find_root(code_path)
    map_path, data = load_existing(code_path)
    if code_path.is_dir():
        if a.stale is not None:
            sys.exit("a project map has no stale entries")
        broken = re_resolve(data, root.name, {}, 0, root)
        map_path.write_text(json.dumps(data, indent=2) + "\n")
        for eid, name in broken:
            print(f"entry {eid}: {name!r} is gone; retext the entry")
        if not broken:
            print("every pin re-resolved, no claude call")
        print(f"wrote {map_path}")
        return
    code_name = rel_name(code_path, root)
    new_lines = code_path.read_text().splitlines()
    spans = block_spans(code_path, new_lines)
    n = len(new_lines)
    if a.stale is not None:
        repair_stale(a, code_path, root, map_path, data, new_lines, spans)
        return
    old = old_lines_of(code_path, a.old)
    if old == new_lines:
        broken = re_resolve(data, code_name, spans, n, root)
        map_path.write_text(json.dumps(data, indent=2) + "\n")
        for eid, name in broken:
            print(f"entry {eid}: {name!r} is gone; retext the entry")
        print("the file did not change; cross-file pins re-resolved, no claude call")
        print(f"wrote {map_path}")
        return
    o2n, changed, inserted = line_map(old, new_lines)
    print(f"changed old lines: {fmt(changed) if changed else 'none'}; "
          f"inserted new lines: {fmt(inserted) if inserted else 'none'}")
    cand = {e["id"] for e in data["explanations"] if entry_lines_set(e) & changed}
    broken = re_resolve(data, code_name, spans, n, root)
    broken_ids = {eid for eid, name in broken}
    cand |= broken_ids
    for e in data["explanations"]:
        if e["id"] not in broken_ids and expand(e["block_lines"]) & inserted:
            cand.add(e["id"])
    cand = {i for i in cand if i in broken_ids
            or rewordable(next(e for e in data["explanations"] if e["id"] == i), code_name)}
    if not cand:
        missing, blank = recompute(data, new_lines)
        map_path.write_text(json.dumps(data, indent=2) + "\n")
        print("spans renumbered, no entry touches the change, no claude call")
        print_coverage(missing, blank, new_lines)
        print(f"wrote {map_path}")
        return
    print(f"candidate entries: {', '.join(str(i) for i in sorted(cand))}")
    span_table = "\n".join(f"{k}: {v[0]}-{v[1]}"
                           for k, v in sorted(spans.items(), key=lambda x: x[1])) or "none"
    cands = "\n\n".join(f"=== entry {e['id']} (block {e['block']}){verbatim_mark(e)} ===\n{e['text']}"
                        for e in data["explanations"] if e["id"] in cand)
    needed = "\n".join(f"entry {i}: {', '.join(sorted(needed_words(data, i)))}"
                       for i in sorted(cand) if needed_words(data, i)) or "none"
    diff = "\n".join(difflib.unified_diff(old, new_lines, "old", "new", lineterm=""))
    prompt = (SYNC_PROMPT.replace("<code_file>", code_name)
              .replace("<path>", str(code_path))
              .replace("<diff>", diff)
              .replace("<touched>", touched_note(code_path, old, new_lines, root))
              .replace("<span_table>", span_table)
              .replace("<candidates>", cands)
              .replace("<needed>", needed))
    trial = None
    last = ""
    suffix = ""
    for _ in range(a.tries):
        try:
            m = ask_claude(prompt + suffix, root)
        except (ValueError, KeyError) as e:
            last = f"the answer was not one JSON object: {e}"
            suffix = "\n\nYour previous answer was not one JSON object. Return only the JSON."
            continue
        texts = m.get("texts") or {}
        blocks = m.get("blocks") or {}
        t = json.loads(json.dumps(data))
        try:
            assert isinstance(texts, dict) and isinstance(blocks, dict), \
                "[SYNC-SHAPE] texts and blocks are objects keyed by entry id"
            rebuild_all(t, code_name, spans, n, root, texts, blocks, cand)
            trial = t
            break
        except AssertionError as e:
            last = str(e)
            suffix = f"\n\nYour previous answer:\n{json.dumps(m)}\n\n" \
                     f"It broke this rule: {last}\nReturn the full corrected JSON object."
    if trial is None:
        sys.exit(f"the sync failed after {a.tries} tries, last error: {last}")
    stale_kids = set()
    project_kids = []
    for e in trial["explanations"]:
        before = next(x for x in data["explanations"] if x["id"] == e["id"])
        if e["block"] != before["block"]:
            print(f"entry {e['id']}: block renamed {before['block']!r} -> {e['block']!r}")
        if e["text"] != before["text"]:
            warn_reworded(e, before["text"], e["text"], "sync")
            report_text_diff(e["id"], before["text"], e["text"])
            if strip_pins(e["text"]) != strip_pins(before["text"]):
                stale_kids.update(mark_children(trial, e["id"], before["text"]))
                project_kids += cmd_project.mark_stale(root, code_name, e["id"], before["text"])
        elif e["id"] in cand:
            fresh = expand(e["block_lines"]) & inserted
            if fresh:
                print(f"warning: entry {e['id']}: {len(fresh)} new lines in "
                      f"{blocks_of(fresh, spans, code_name)}, no word changed")
    if stale_kids:
        print(f"entries {', '.join(map(str, sorted(stale_kids)))} depend on a changed entry and are "
              f"marked stale; repair each with human sync {code_name} --stale <id>")
    report_project_stale(sorted(set(project_kids)))
    missing, blank = recompute(trial, new_lines)
    map_path.write_text(json.dumps(trial, indent=2) + "\n")
    print_coverage(missing, blank, new_lines)
    print(f"wrote {map_path}")
