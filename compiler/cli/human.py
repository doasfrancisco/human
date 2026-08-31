import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

import cmd_map
import decompiler

SKIP = {"projects.json", "web.html", "trees.js", "human.json", "abstraction.txt"}


def cmd_init(a):
    folder = Path(a.folder).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    files = sorted(p.name for p in folder.iterdir()
                   if p.is_file() and p.name not in SKIP
                   and not p.name.startswith("explanation_"))
    if not files:
        sys.exit(f"no code files in {folder}; write the code first, then init")
    reg_path = folder.parent / "projects.json"
    reg = json.loads(reg_path.read_text()) if reg_path.exists() else {"projects": []}
    for p in reg["projects"]:
        if p.get("name") == folder.name:
            p.pop("file", None)
            p["files"] = files
            break
    else:
        reg["projects"].append({"name": folder.name, "files": files})
    reg_path.write_text(json.dumps(reg) + "\n")
    print(f"project {folder.name}: {len(files)} files ({', '.join(files)})")
    print(f"wrote {reg_path}")


def cmd_map_h(a):
    if not a.verbatim:
        cmd_map.cmd_map(a)
        return
    want = Path(a.verbatim).read_text().strip()
    text = decompiler.read_text_arg(a)
    got = decompiler.ANCHOR_RE.sub(lambda m: m.group(1), text)
    if got != want:
        sys.exit("with the pins stripped the text is not the abstraction word for word; "
                 "pins may go in, the words may not change")
    fd, tmp = tempfile.mkstemp(suffix=".txt")
    try:
        os.write(fd, text.encode())
        os.close(fd)
        a.text = tmp
        cmd_map.cmd_map(a)
    finally:
        os.unlink(tmp)


def main():
    ap = argparse.ArgumentParser(prog="human")
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("init")
    i.add_argument("folder")
    m = sub.add_parser("map")
    m.add_argument("code_file")
    m.add_argument("--block")
    m.add_argument("--text")
    m.add_argument("--verbatim")
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
    y.add_argument("--stale", type=int)
    y.add_argument("--tries", type=int, default=4)
    a = ap.parse_args()
    {"init": cmd_init, "map": cmd_map_h, "retext": decompiler.cmd_retext,
     "undo": decompiler.cmd_undo, "show": decompiler.cmd_show,
     "lines": decompiler.cmd_lines, "sync": decompiler.cmd_sync}[a.cmd](a)


if __name__ == "__main__":
    main()
