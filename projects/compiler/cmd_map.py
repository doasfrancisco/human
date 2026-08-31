import json
import sys
from pathlib import Path

import decompiler


def load_map(map_path, name):
    if map_path.exists():
        data = json.loads(map_path.read_text())
        decompiler.guard_structure(data, map_path)
        return data
    return {"code_file": name, "explanations": [], "not_covered": {"code_lines": [], "blank_lines": []}}


def entry_span(name, code_path, spans, n):
    if name == code_path.name:
        return [[1, n]]
    if name in spans:
        return [list(spans[name])]
    sys.exit(f"{name!r} is not a block of {code_path.name}")


def next_id(data):
    return max((e["id"] for e in data["explanations"]), default=0) + 1


def map_project(a, folder):
    if a.block:
        sys.exit("a project map has no blocks of its own; drop --block")
    map_path = folder / "human.json"
    data = load_map(map_path, folder.name)
    text = decompiler.read_text_arg(a)
    eid = next_id(data)
    try:
        anchors = decompiler.build_anchors(text, data, {}, eid, folder)
        decompiler.project_pins(anchors)
    except AssertionError as e:
        sys.exit(str(e))
    record = {"id": eid, "block": folder.name, "block_lines": [],
              "text": text, "anchors": anchors}
    data["explanations"].append(record)
    map_path.write_text(json.dumps(data, indent=2) + "\n")
    files = sorted({x["file"] for x in anchors})
    print(f"entry {eid}: {folder.name}, {len(anchors)} pins into {len(files)} files ({', '.join(files)})")
    print(f"wrote {map_path}")


def cmd_map(a):
    code_path = Path(a.code_file).resolve()
    if code_path.is_dir():
        map_project(a, code_path)
        return
    lines = code_path.read_text().splitlines()
    spans = decompiler.block_spans(code_path, lines)
    map_path = decompiler.map_path_of(code_path)
    data = load_map(map_path, code_path.name)
    text = decompiler.read_text_arg(a)
    n = len(lines)
    block = (a.block or code_path.name).strip()
    block_lines = entry_span(block, code_path, spans, n)
    eid = next_id(data)
    try:
        anchors = decompiler.build_anchors(text, data, spans, eid, code_path.parent)
        decompiler.check_cycle(data, eid, anchors)
    except AssertionError as e:
        sys.exit(str(e))
    record = {"id": eid, "block": block, "block_lines": block_lines,
              "text": text, "anchors": anchors}
    data["explanations"].append(record)
    missing, blank = decompiler.recompute(data, lines)
    map_path.write_text(json.dumps(data, indent=2) + "\n")
    print(f"entry {eid}: {block}, lines {decompiler.fmt(decompiler.expand(block_lines))}, {decompiler.anchor_counts(anchors)}")
    decompiler.print_coverage(missing, blank, lines)
    print(f"wrote {map_path}")
