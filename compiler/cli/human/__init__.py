import argparse
import fnmatch
import ipaddress
import json
import os
import shutil
import socket
import sys
import tempfile
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import cmd_map, decompiler

PKG = Path(__file__).parent

IGNORE_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv",
               "build", "dist", ".idea", ".vscode"}
SUFFIXES = {".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".htm", ".css", ".md",
            ".toml", ".json", ".yaml", ".yml", ".sh", ".rs", ".go", ".c", ".h",
            ".cpp", ".java", ".rb", ".sql"}

DESTINATIONS = {
    "claude": Path.home() / ".claude" / "skills",
    "droid": Path.home() / ".factory" / "skills",
    "shared": Path.home() / ".agents" / "skills",
}


def scan_files(root):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        d = Path(dirpath)
        if d != root and (d / "human" / "human.json").is_file():
            dirnames[:] = []
            continue
        dirnames[:] = sorted(x for x in dirnames
                             if not x.startswith(".") and x not in IGNORE_DIRS
                             and not (d == root and x == "human"))
        for f in sorted(filenames):
            if f.startswith(".") or f == "abstraction.txt":
                continue
            p = d / f
            if p.suffix.lower() in SUFFIXES:
                out.append(p.relative_to(root).as_posix())
    return out


def is_ignored(rel, patterns):
    for p in patterns:
        q = (p["path"] if isinstance(p, dict) else p).rstrip("/")
        if rel == q or rel.startswith(q + "/") or fnmatch.fnmatch(rel, q):
            return True
    return False


def cmd_init(a):
    root = Path(a.folder).resolve()
    root.mkdir(parents=True, exist_ok=True)
    h = root / "human"
    h.mkdir(exist_ok=True)
    for name in ("web.html", "trees.js"):
        shutil.copy(PKG / "reader" / name, h / name)
    map_path = h / "human.json"
    if map_path.exists():
        data = json.loads(map_path.read_text())
        decompiler.guard_structure(data, map_path)
    else:
        data = {"code_file": root.name, "explanations": [],
                "not_covered": {"code_lines": [], "blank_lines": []}}
    data["code_file"] = root.name
    patterns = data.get("ignore", [])
    found = scan_files(root)
    data["ignore"] = patterns
    data["files"] = [f for f in found if not is_ignored(f, patterns)]
    data.pop("ignored", None)
    map_path.write_text(json.dumps(data, indent=2) + "\n")
    hidden = len(found) - len(data["files"])
    tail = f", {hidden} ignored" if hidden else ""
    print(f"project {root.name}: {len(data['files'])} files{tail}")
    print(f"wrote {map_path}")
    print(f"read it with: human serve  (from {root})")


def fresh_map(root):
    data = json.loads((root / "human" / "human.json").read_text())
    patterns = data.get("ignore", [])
    data["files"] = [f for f in scan_files(root) if not is_ignored(f, patterns)]
    return data


class FreshHandler(SimpleHTTPRequestHandler):
    verbose = False

    def do_GET(self):
        if self.path.split("?")[0] == "/human/human.json":
            try:
                body = json.dumps(fresh_map(Path(self.directory))).encode()
            except (OSError, ValueError):
                super().do_GET()
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, format, *args):
        if self.verbose:
            super().log_message(format, *args)


def tailnet_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("100.100.100.100", 1))
            ip = s.getsockname()[0]
        finally:
            s.close()
    except OSError:
        return None
    if ipaddress.ip_address(ip) in ipaddress.ip_network("100.64.0.0/10"):
        return ip
    return None


def cmd_serve(a):
    root = decompiler.find_root(Path(a.folder).resolve())
    FreshHandler.verbose = a.log
    handler = partial(FreshHandler, directory=str(root))
    srv = ThreadingHTTPServer(("0.0.0.0", a.port), handler)
    print(f"serving {root}")
    print(f"http://localhost:{a.port}/human/web.html")
    tip = tailnet_ip()
    if tip:
        print(f"http://{tip}:{a.port}/human/web.html")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


def cmd_skills(a):
    dests = list(DESTINATIONS) if a.dest == "all" else [a.dest]
    skills = sorted(p.name for p in (PKG / "skills").iterdir() if p.is_dir())
    for dest in dests:
        base = DESTINATIONS[dest]
        base.mkdir(parents=True, exist_ok=True)
        for name in skills:
            dst = base / name
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(PKG / "skills" / name, dst)
            shutil.copytree(PKG / "shapes", dst / "shapes", dirs_exist_ok=True)
            print(f"installed {name} -> {dst}")


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
    i.add_argument("folder", nargs="?", default=".")
    v = sub.add_parser("serve")
    v.add_argument("folder", nargs="?", default=".")
    v.add_argument("--port", type=int, default=8010)
    v.add_argument("--log", action="store_true")
    k = sub.add_parser("skills")
    k.add_argument("--dest", choices=list(DESTINATIONS) + ["all"], default="claude")
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
    {"init": cmd_init, "serve": cmd_serve, "skills": cmd_skills, "map": cmd_map_h,
     "retext": decompiler.cmd_retext, "undo": decompiler.cmd_undo,
     "show": decompiler.cmd_show, "lines": decompiler.cmd_lines,
     "sync": decompiler.cmd_sync}[a.cmd](a)


if __name__ == "__main__":
    main()
