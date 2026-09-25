import json
import sys
from pathlib import Path

from . import cmd_project, decompiler, helpers


def load_map(map_path, name):
    if map_path.exists():
        data = json.loads(map_path.read_text())
        decompiler.guard_structure(data, map_path)
        return data
    return {"code_file": name, "explanations": [], "not_covered": {"code_lines": [], "blank_lines": []}}


def entry_span(name, code_name, code_path, spans, n):
    if name == code_name:
        return [[1, n]]
    if name in spans:
        return [list(spans[name])]
    sys.exit(f"{name!r} is not a block of {code_name}")


def next_id(data):
    return max((e["id"] for e in data["explanations"]), default=0) + 1


def verbatim_record(a, text):
    if not getattr(a, "verbatim", False):
        return {}
    if decompiler.ANCHOR_RE.search(text):
        sys.exit("the user's words go in plain; the pins come after, with human retext")
    return {"verbatim": {"origin": text}}


def map_project(a, root):
    if a.block:
        sys.exit("a project map has no blocks of its own; drop --block")
    map_path = root / "human" / "human.json"
    data = load_map(map_path, root.name)
    text = decompiler.read_text_arg(a)
    eid = next_id(data)
    try:
        anchors = decompiler.build_anchors(text, data, {}, eid, root)
        decompiler.project_pins(anchors)
    except AssertionError as e:
        sys.exit(str(e))
    record = {"id": eid, "block": root.name, "block_lines": [],
              "text": text, "anchors": anchors}
    data["explanations"].append(record)
    map_path.write_text(json.dumps(data, indent=2) + "\n")
    files = sorted({x["file"] for x in anchors})
    print(f"entry {eid}: {root.name}, {len(anchors)} pins into {len(files)} files ({', '.join(files)})")
    print(f"wrote {map_path}")


def cmd_map(a):
    root = decompiler.find_root(Path(a.code_file).resolve())
    map_path, sort = helpers.name_to_map(a.code_file, root)
    if sort in helpers.NO_CODE:
        cmd_project.cmd_map_project(a)
        return
    if sort == "folder":
        map_project(a, root)
        return
    code_path = Path(a.code_file).resolve()
    if not code_path.is_file():
        sys.exit(f"{a.code_file} is not a file of the project")
    code_name = decompiler.rel_name(code_path, root)
    lines = code_path.read_text().splitlines()
    spans = decompiler.block_spans(code_path, lines)
    data = load_map(map_path, code_name)
    text = decompiler.read_text_arg(a)
    extra = verbatim_record(a, text)
    n = len(lines)
    block = (a.block or code_name).strip()
    block_lines = entry_span(block, code_name, code_path, spans, n)
    eid = next_id(data)
    try:
        anchors = decompiler.build_anchors(text, data, spans, eid, root)
        decompiler.check_cycle(data, eid, anchors)
    except AssertionError as e:
        sys.exit(str(e))
    record = {"id": eid, "block": block, "block_lines": block_lines,
              "text": text, "anchors": anchors}
    record.update(extra)
    data["explanations"].append(record)
    missing, blank = decompiler.recompute(data, lines)
    map_path.write_text(json.dumps(data, indent=2) + "\n")
    decompiler.register_file(root, code_name)
    print(f"entry {eid}: {block}, lines {decompiler.fmt(decompiler.expand(block_lines))}, {decompiler.anchor_counts(anchors)}")
    decompiler.print_coverage(missing, blank, lines)
    print(f"wrote {map_path}")
