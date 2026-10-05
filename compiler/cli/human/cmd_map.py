import json
import sys
from pathlib import Path

from . import cmd_human, compiler, helpers


def load_map(map_path, name):
    if map_path.exists():
        data = json.loads(map_path.read_text())
        compiler.guard_structure(data, map_path)
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
    return {"verbatim": {"origin": compiler.strip_pins(text)}}


def cmd_map(a):
    root = compiler.find_root(Path(a.code_file).resolve())
    map_path, sort = helpers.name_to_map(a.code_file, root)
    if sort in helpers.NO_CODE:
        cmd_human.cmd_map_project(a)
        return
    code_path = Path(a.code_file).resolve()
    if not code_path.is_file():
        sys.exit(f"{a.code_file} is not a file of the project")
    code_name = compiler.rel_name(code_path, root)
    lines = code_path.read_text().splitlines()
    spans = compiler.block_spans(code_path, lines)
    data = load_map(map_path, code_name)
    text = compiler.read_text_arg(a)
    extra = verbatim_record(a, text)
    n = len(lines)
    block = (a.block or code_name).strip()
    block_lines = entry_span(block, code_name, code_path, spans, n)
    eid = next_id(data)
    try:
        anchors = compiler.build_anchors(text, data, spans, eid, root)
        compiler.check_cycle(data, eid, anchors)
    except AssertionError as e:
        sys.exit(str(e))
    record = {"id": eid, "block": block, "block_lines": block_lines,
              "text": text, "anchors": anchors}
    record.update(extra)
    data["explanations"].append(record)
    missing, blank = compiler.recompute(data, lines)
    map_path.write_text(json.dumps(data, indent=2) + "\n")
    compiler.register_file(root, code_name)
    print(f"entry {eid}: {block}, lines {compiler.fmt(compiler.expand(block_lines))}, {compiler.anchor_counts(anchors)}")
    compiler.print_coverage(missing, blank, lines)
    print(f"wrote {map_path}")
