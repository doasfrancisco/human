import argparse
import fnmatch
import ipaddress
import json
import os
import re
import shutil
import socket
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import cmd_map, cmd_project, cmd_store, cmd_train, cmd_watch, decompiler

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
            if f.startswith("."):
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
    (h / "feed.html").unlink(missing_ok=True)
    map_path = h / "human.json"
    if map_path.exists():
        data = json.loads(map_path.read_text())
        decompiler.guard_structure(data, map_path)
    else:
        data = {"code_file": root.name, "explanations": [],
                "not_covered": {"code_lines": [], "blank_lines": []}}
    data["code_file"] = root.name
    found, data = write_files(root, data)
    if not cmd_project.map_path(root).exists():
        cmd_project.save(root, cmd_project.load(root))
    if (root / cmd_project.WORD).exists():
        print(f"warning: a file named {cmd_project.WORD} sits at the root; the word reaches the project "
              f"map, the file needs a path like ./{cmd_project.WORD}")
    hidden = len(found) - len(data["files"])
    tail = f", {hidden} ignored" if hidden else ""
    print(f"project {root.name}: {len(data['files'])} files{tail}")
    print(f"wrote {map_path}")
    print(f"read it with: human serve  (from {root})")


def write_files(root, data=None):
    map_path = root / "human" / "human.json"
    if data is None:
        data = json.loads(map_path.read_text())
    patterns = data.get("ignore", [])
    found = scan_files(root)
    data["ignore"] = patterns
    data["files"] = [f for f in found if not is_ignored(f, patterns)]
    data.pop("ignored", None)
    map_path.write_text(json.dumps(data, indent=2) + "\n")
    return found, data


def fresh_map(root):
    data = json.loads((root / "human" / "human.json").read_text())
    patterns = data.get("ignore", [])
    data["files"] = [f for f in scan_files(root) if not is_ignored(f, patterns)]
    return data


def new_file(root, name):
    if not isinstance(name, str) or not name.strip():
        return 400, "no file name"
    rel = Path(name.strip().replace("\\", "/"))
    if rel.is_absolute() or ".." in rel.parts or not rel.parts:
        return 400, f"{name} leaves the project; name a path from the root, like src/app.py"
    shown = rel.as_posix()
    if rel.parts[0] == "human":
        return 400, f"{shown} is in the human folder; the maps take no file"
    for part in rel.parts[:-1]:
        if part.startswith(".") or part in IGNORE_DIRS:
            return 400, f"{shown} is in {part}, a folder the file tree skips"
    if rel.name.startswith("."):
        return 400, f"{shown} starts with a dot; the file tree skips it"
    for i in range(1, len(rel.parts)):
        d = root.joinpath(*rel.parts[:i])
        if (d / "human" / "human.json").is_file():
            return 400, f"{shown} is in {d.relative_to(root).as_posix()}, a project of its own"
    if rel.suffix.lower() not in SUFFIXES:
        return 400, f"{shown} has no suffix the file tree knows; one of {', '.join(sorted(SUFFIXES))}"
    data = json.loads((root / "human" / "human.json").read_text())
    if is_ignored(shown, data.get("ignore", [])):
        return 400, f"{shown} is ignored by human/human.json"
    p = root / rel
    if p.exists():
        return 400, f"{shown} exists"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.touch()
    write_files(root, data)
    return 200, {"name": shown, "output": f"{shown} made, empty; write its telling"}


class FreshHandler(SimpleHTTPRequestHandler):
    verbose = False

    def send_json(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        root = Path(self.directory)
        if path == "/human/human.json":
            try:
                self.send_json(200, fresh_map(root))
            except (OSError, ValueError):
                super().do_GET()
            return
        m = re.fullmatch(r"/human/training/(?:([^/]+)\.json)?", path)
        if m:
            try:
                out = cmd_store.get_session(m.group(1)) if m.group(1) else cmd_train.list_sessions()
                self.send_json(200, out)
            except cmd_store.Refused as e:
                self.send_json(e.status, {"error": e.message})
            except cmd_store.Unreachable as e:
                self.send_json(502, {"error": str(e)})
            return
        if path == "/human/server/queue":
            self.send_json(200, cmd_watch.pending(root))
            return
        super().do_GET()

    def read_body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_POST(self):
        path = self.path.split("?")[0]
        root = Path(self.directory)
        m = re.fullmatch(r"/human/training/([^/]+)/(pick|close)", path)
        try:
            if path == "/human/compile":
                body = self.read_body()
                status, out = cmd_watch.compile_writing(root, body.get("name"), body.get("kind"),
                                                        body.get("id"), body.get("text"), body.get("words"))
            elif path == "/human/file":
                status, out = new_file(root, self.read_body().get("name"))
            elif m and m.group(2) == "close":
                status, out = cmd_train.close_road(root, m.group(1))
            elif m:
                body = self.read_body()
                status, out = cmd_train.pick(root, m.group(1),
                                             body.get("row"), body.get("picked"), body.get("comment"))
            else:
                status, out = 404, "not found"
        except (ValueError, OSError) as e:
            status, out = 400, str(e)
        self.send_json(status, out if status == 200 else {"error": out})

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
    print("an open training session shows as a layer over the reader")
    print("a new file from the reader lands next to the others, empty, ready for its telling")
    print("a writing in the reader lands in human/server/; read it with: human watch")
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
    m.add_argument("--verbatim", action="store_true")
    r = sub.add_parser("retext")
    r.add_argument("code_file")
    r.add_argument("id", type=int)
    r.add_argument("--text")
    r.add_argument("--verbatim", action="store_true")
    u = sub.add_parser("undo")
    u.add_argument("code_file")
    u.add_argument("--entry", type=int)
    s = sub.add_parser("show")
    s.add_argument("code_file")
    l = sub.add_parser("lines")
    l.add_argument("code_file")
    y = sub.add_parser("sync")
    y.add_argument("code_file")
    y.add_argument("--old")
    y.add_argument("--stale", type=int)
    y.add_argument("--tries", type=int, default=4)
    t = sub.add_parser("train")
    t.add_argument("code_file", nargs="?")
    t.add_argument("--open", action="store_true")
    t.add_argument("--close", action="store_true")
    t.add_argument("--as", dest="slot", choices=cmd_train.SLOTS)
    t.add_argument("--shape")
    t.add_argument("--kind", choices=("create", "sync"), default="create")
    t.add_argument("--entry", type=int)
    t.add_argument("--block")
    t.add_argument("--target", type=int)
    t.add_argument("--words")
    t.add_argument("--text")
    w = sub.add_parser("watch")
    w.add_argument("--once", action="store_true")
    c = sub.add_parser("ack")
    c.add_argument("seq", type=int)
    g = sub.add_parser("login")
    g.add_argument("key")
    a = ap.parse_args()
    if a.cmd in cmd_project.COMMANDS and a.code_file == cmd_project.WORD:
        cmd_project.COMMANDS[a.cmd](a)
        return
    {"init": cmd_init, "serve": cmd_serve, "skills": cmd_skills, "map": cmd_map.cmd_map,
     "retext": decompiler.cmd_retext, "undo": decompiler.cmd_undo,
     "show": decompiler.cmd_show, "lines": decompiler.cmd_lines,
     "sync": decompiler.cmd_sync, "train": cmd_train.cmd_train,
     "watch": cmd_watch.cmd_watch, "ack": cmd_watch.cmd_ack,
     "login": cmd_store.cmd_login}[a.cmd](a)


if __name__ == "__main__":
    main()
