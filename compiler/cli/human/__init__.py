import argparse
import fnmatch
import gzip
import hashlib
import ipaddress
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import timezone
from email.utils import parsedate_to_datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import cmd_map, cmd_project, cmd_store, cmd_train, cmd_watch, decompiler, helpers, updater

PKG = Path(__file__).parent
READER = ("web.html", "trees.js", "shiki.js")

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
    (h / "feed.html").unlink(missing_ok=True)
    map_path = h / "human.json"
    if map_path.exists():
        data = json.loads(map_path.read_text())
        decompiler.guard_structure(data, map_path)
    else:
        data = {"code_file": root.name, "explanations": [],
                "not_covered": {"code_lines": [], "blank_lines": []}}
    data["code_file"] = root.name
    if not data.get("project"):
        data["project"] = secrets.token_hex(4)
    found, data = write_files(root, data)
    if not cmd_project.map_path(root).exists():
        cmd_project.save(root, cmd_project.load(root))
    for p in sorted(h.glob("explanation_*.json")):
        d = read_map(p)
        name = d.get("code_file") if d else None
        if isinstance(name, str) and not (root / name).is_file():
            p.unlink()
            print(f"deleted {p.name}: {name} is not on disk")
    for bare in [cmd_project.WORD] + helpers.human_names(root):
        if (root / bare).exists():
            print(f"warning: a file named {bare} sits at the root; the bare name reaches the map with "
                  f"no code under it, the file needs a path like ./{bare}")
    hidden = len(found) - len(data["files"])
    tail = f", {hidden} ignored" if hidden else ""
    print(f"project {root.name}: {len(data['files'])} files{tail}, id {data['project']}")
    print(f"wrote {map_path}", flush=True)
    serve_away(root, a.port)


def serve_away(root, port):
    pid = cmd_store.project_id(root)
    if not hand_over(root, port):
        me = [sys.executable] if updater.frozen() else [sys.executable, "-c", "from human import main; main()"]
        log = cmd_watch.folder(root) / "serve.log"
        away = {"creationflags": 0x00000008 | 0x00000200} if os.name == "nt" else {"start_new_session": True}
        with open(log, "ab") as out:
            subprocess.Popen([*me, "serve", str(root), "--port", str(port)], cwd=str(root),
                             stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT, **away)
        for _ in range(50):
            if hand_over(root, port):
                break
            time.sleep(0.2)
        else:
            sys.exit(f"the human server did not start on port {port}; read {log}")
    print_links(pid, port)


def write_files(root, data=None):
    map_path = root / "human" / "human.json"
    if data is None:
        data = json.loads(map_path.read_text())
    patterns = data.get("ignore", [])
    found = scan_files(root)
    data["ignore"] = patterns
    data["files"] = [f for f in found if not is_ignored(f, patterns)]
    data["humans"] = helpers.human_entries(root)
    data.pop("ignored", None)
    map_path.write_text(json.dumps(data, indent=2) + "\n")
    return found, data


class Sweep:
    def __init__(self, root):
        self.root = root
        self.dirs = {}
        self.lock = threading.Lock()

    def files(self):
        with self.lock:
            out, seen = [], set()
            self.visit(self.root, out, seen)
            for d in set(self.dirs) - seen:
                del self.dirs[d]
            return out

    def visit(self, d, out, seen):
        seen.add(d)
        if d != self.root and (d / "human" / "human.json").is_file():
            return
        try:
            stamp = d.stat().st_mtime_ns
        except OSError:
            return
        held = self.dirs.get(d)
        if held is None or held[0] is None or held[0] != stamp:
            held = (stamp if time.time_ns() - stamp > 2_000_000_000 else None, *self.listing(d))
            self.dirs[d] = held
        out.extend(held[2])
        for sub in held[1]:
            self.visit(sub, out, seen)

    def listing(self, d):
        subs, names = [], []
        try:
            with os.scandir(d) as it:
                for e in it:
                    if e.is_dir():
                        if not e.is_symlink():
                            subs.append(e.name)
                    else:
                        names.append(e.name)
        except OSError:
            return [], []
        subs = [d / x for x in sorted(subs)
                if not x.startswith(".") and x not in IGNORE_DIRS
                and not (d == self.root and x == "human")]
        files = [(d / f).relative_to(self.root).as_posix() for f in sorted(names)
                 if not f.startswith(".") and Path(f).suffix.lower() in SUFFIXES]
        return subs, files


SWEEPS = {}


def fresh_map(root):
    data = json.loads((root / "human" / "human.json").read_text())
    patterns = data.get("ignore", [])
    sweep = SWEEPS.setdefault(root, Sweep(root))
    data["files"] = [f for f in sweep.files() if not is_ignored(f, patterns)]
    data["humans"] = helpers.human_entries(root)
    return data


def read_map(p):
    try:
        d = json.loads(p.read_text())
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) else None


def all_maps(root):
    h = root / "human"
    files, humans = {}, {}
    for p in sorted(h.glob("explanation_*.json")):
        d = read_map(p)
        name = d.get("code_file") if d else None
        if isinstance(name, str) and (root / name).is_file():
            files[name] = d
    for p in sorted(h.glob(f"{helpers.HUMAN_PREFIX}*.json")):
        d = read_map(p)
        if d:
            humans[p.stem[len(helpers.HUMAN_PREFIX):]] = d
    return {"files": files, "humans": humans, "project": read_map(cmd_project.map_path(root))}


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


def human_place(root, place):
    if not isinstance(place, str) or not place.strip():
        return ""
    rel = Path(place.strip().replace("\\", "/"))
    if rel.is_absolute() or ".." in rel.parts or not rel.parts:
        return ""
    if rel.parts[0] == "human" or any(part.startswith(".") or part in IGNORE_DIRS for part in rel.parts):
        return ""
    if not (root / rel).is_dir():
        return ""
    return rel.as_posix()


def new_human(root, name, place=""):
    if not isinstance(name, str) or not name.strip():
        return 400, "no name"
    bare = name.strip()
    if not helpers.is_bare(bare) or bare.startswith("."):
        return 400, f"{bare} is not a bare name; a human file takes one word, no folder and no suffix"
    if bare == cmd_project.WORD:
        return 400, f"{bare} is the word of the project map"
    p = helpers.human_map_path(root, bare)
    if p.exists():
        return 400, f"{bare} is held by another human file"
    if (root / bare).exists():
        return 400, f"{bare} is held by a file at the root"
    where = human_place(root, place)
    data = {"code_file": bare, "explanations": [],
            "not_covered": {"code_lines": [], "blank_lines": []}}
    if where:
        data["place"] = where
    p.write_text(json.dumps(data, indent=2) + "\n")
    shown = f"{where}/{bare}.human" if where else f"{bare}.human"
    return 200, {"name": f"human/{helpers.HUMAN_PREFIX}{bare}.json",
                 "output": f"{shown} made, empty; write its abstraction, with no file under it"}


DRAFTS_LOCK = threading.Lock()


def tip_path(root):
    return cmd_watch.folder(root) / "tip.json"


def read_tip(root):
    try:
        d = json.loads(tip_path(root).read_text())
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def reader_file(root, name):
    p, kind = helpers.name_to_map(name, root)
    if kind == "project":
        return p, "human/project.json"
    if helpers.no_code(name, root):
        return p, f"human/{p.name}"
    path = Path(name) if Path(name).is_absolute() else root / name
    return p, path.resolve().relative_to(root).as_posix()


def cmd_tip(a):
    root = decompiler.find_root(Path.cwd())
    if a.clear:
        tip_path(root).unlink(missing_ok=True)
        print("tip cleared")
        return
    if not a.code_file or not a.say:
        sys.exit("a tip takes a name and --say <the words the reader shows>")
    p, file = reader_file(root, a.code_file)
    if a.draft is not None:
        if not p.exists():
            if not helpers.no_code(a.code_file, root):
                sys.exit(f"{a.code_file} has no map; a draft tip goes on a human file or the project map")
            status, out = new_human(root, a.code_file)
            if status != 200:
                sys.exit(out)
            write_files(root)
        d = read_map(p)
        if d is None or d.get("explanations"):
            sys.exit(f"{a.code_file} already holds an abstraction; a draft tip goes on an empty map")
        top = json.loads((root / "human" / "human.json").read_text()).get("code_file") or root.name
        tidy_drafts(root, {f"human-draft:{top}/{file}/map": a.draft})
        tip = {"file": file, "kind": "compile", "say": a.say}
    else:
        d = read_map(p)
        if d is None:
            sys.exit(f"{a.code_file} has no map")
        e = next((x for x in d.get("explanations", []) if x.get("id") == a.entry), None)
        if e is None:
            sys.exit(f"{a.code_file} has no entry {a.entry}")
        if not a.words or not any(a.words in line for line in e["text"].split("\n")):
            sys.exit(f"--words must be found inside one line of entry {a.entry}, as it is written in the map")
        tip = {"file": file, "kind": "line", "entry": a.entry, "words": a.words, "say": a.say}
    out = tip_path(root)
    out.write_text(json.dumps(tip, indent=1) + "\n")
    print(f"tip kept in {out}; the reader shows it on its next open")


def drafts_path(root):
    return cmd_watch.folder(root) / "drafts.json"


def read_drafts(root):
    try:
        d = json.loads(drafts_path(root).read_text())
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def spent_draft(root, k, v):
    if not v:
        return True
    m = re.fullmatch(r"human-draft:[^/]*/(.+)/([^/]+)", k)
    if not m:
        return False
    rel, tail = m.groups()
    p = root / rel
    if tail == "code":
        try:
            return v == p.read_text()
        except (OSError, ValueError):
            return False
    if not tail.isdigit():
        return False
    d = read_map(p if rel.startswith("human/") else helpers.map_path_of(p, root))
    if d is None:
        return False
    texts = {e.get("id"): e.get("text") for e in d.get("explanations", [])}
    return texts.get(int(tail), v) == v


def tidy_drafts(root, changes):
    with DRAFTS_LOCK:
        d = read_drafts(root)
        d.update(changes)
        kept = {k: v for k, v in d.items() if not spent_draft(root, k, v)}
        if changes or kept != d:
            p = drafts_path(root)
            tmp = p.with_name(p.name + ".tmp")
            tmp.write_text(json.dumps(kept, indent=1) + "\n")
            tmp.replace(p)
    return kept


def keep_drafts(root, changes):
    if not isinstance(changes, dict) or not all(
            isinstance(k, str) and (v is None or isinstance(v, str)) for k, v in changes.items()):
        return 400, "a draft is a name and its text, or no text to remove it"
    return 200, {"drafts": len(tidy_drafts(root, changes))}


PROJECTS_LOCK = threading.Lock()
SERVED = {}
BUSY = [0]
BUSY_LOCK = threading.Lock()


def projects_path():
    return updater.HOME / "projects.json"


def read_projects():
    try:
        d = json.loads(projects_path().read_text())
    except (OSError, ValueError):
        return {}
    if not isinstance(d, dict):
        return {}
    return {k: Path(v) for k, v in d.items() if isinstance(k, str) and isinstance(v, str)}


def add_project(root):
    pid = cmd_store.project_id(root)
    with PROJECTS_LOCK:
        d = read_projects()
        d[pid] = root
        updater.HOME.mkdir(parents=True, exist_ok=True)
        p = projects_path()
        tmp = p.with_name(p.name + ".tmp")
        tmp.write_text(json.dumps({k: str(v) for k, v in sorted(d.items())}, indent=2) + "\n")
        tmp.replace(p)
        SERVED.update(d)
    return pid


def project_root(pid):
    root = SERVED.get(pid)
    if root is None:
        with PROJECTS_LOCK:
            SERVED.update(read_projects())
        root = SERVED.get(pid)
    if root is None or not (root / "human" / "human.json").is_file():
        return None
    return root


def deploy_reader():
    updater.HOME.mkdir(parents=True, exist_ok=True)
    for name in READER:
        src, dst = PKG / "reader" / name, updater.HOME / name
        body = src.read_bytes()
        if not dst.is_file() or dst.read_bytes() != body:
            tmp = dst.with_name(name + ".tmp")
            tmp.write_bytes(body)
            tmp.replace(dst)


def idle():
    with BUSY_LOCK:
        if BUSY[0]:
            return False
    for root in list(SERVED.values()):
        if (root / "human" / "human.json").is_file() and cmd_watch.pending(root)["pending"]:
            return False
    return True


class FreshHandler(SimpleHTTPRequestHandler):
    verbose = False
    protocol_version = "HTTP/1.1"
    timeout = 30

    def send_body(self, status, body, ctype, etag=None, modified=None):
        if etag and self.headers.get("If-None-Match") == etag:
            self.send_response(304)
            self.send_header("ETag", etag)
            self.end_headers()
            return
        zipped = len(body) > 1024 and "gzip" in (self.headers.get("Accept-Encoding") or "")
        if zipped:
            body = gzip.compress(body, 6)
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Vary", "Accept-Encoding")
        if zipped:
            self.send_header("Content-Encoding", "gzip")
        if etag:
            self.send_header("ETag", etag)
        if modified:
            self.send_header("Last-Modified", modified)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def send_json(self, status, payload, versioned=False):
        body = json.dumps(payload).encode()
        etag = f'"{hashlib.sha1(body).hexdigest()[:16]}"' if versioned else None
        self.send_body(status, body, "application/json", etag)

    def send_static(self, p):
        ctype = self.guess_type(str(p))
        if not p.is_file() or not (ctype.startswith("text/") or ctype.endswith(("javascript", "json"))):
            return super().do_GET()
        try:
            st = p.stat()
            body = p.read_bytes()
        except OSError:
            return super().do_GET()
        since = self.headers.get("If-Modified-Since")
        if since and not self.headers.get("If-None-Match"):
            try:
                t = parsedate_to_datetime(since)
                if t.tzinfo is None:
                    t = t.replace(tzinfo=timezone.utc)
                if int(st.st_mtime) <= t.timestamp():
                    self.send_response(304)
                    self.end_headers()
                    return
            except (TypeError, ValueError, IndexError, OverflowError):
                pass
        self.send_body(200, body, ctype, modified=self.date_time_string(st.st_mtime))

    def project(self):
        path = self.path.split("?")[0]
        m = re.fullmatch(r"/([^/]+)(/.*)?", path)
        root = project_root(m.group(1)) if m else None
        if root is None:
            return None, None, path
        self.directory = str(root)
        return m.group(1), root, m.group(2) or "/"

    def do_GET(self):
        if self.path.split("?")[0] == "/human/hello":
            self.send_json(200, {"human": updater.version()})
            return
        pid, root, path = self.project()
        if root is None:
            self.send_json(404, {"error": f"no project at {path}"})
            return
        if path == "/":
            self.send_response(302)
            self.send_header("Location", f"/{pid}/human/web.html")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if path in {f"/human/{n}" for n in READER}:
            self.send_static(updater.HOME / path.rsplit("/", 1)[1])
            return
        self.path = path
        if path == "/human/human.json":
            try:
                self.send_json(200, fresh_map(root), versioned=True)
            except (OSError, ValueError):
                self.send_static(Path(self.translate_path(path)))
            return
        if path == "/human/server/update":
            self.send_json(200, updater.status())
            return
        if path == "/human/maps":
            self.send_json(200, all_maps(root))
            return
        m = re.fullmatch(r"/human/training/(?:([^/]+)\.json)?", path)
        if m:
            try:
                if m.group(1):
                    out = cmd_store.get_session(m.group(1))
                    if out.get("project") != cmd_store.project_id(root):
                        raise cmd_store.Refused(404, f"no session {m.group(1)} in this project")
                else:
                    out = cmd_train.list_sessions(root)
                self.send_json(200, out)
            except cmd_store.Refused as e:
                self.send_json(e.status, {"error": e.message})
            except cmd_store.Unreachable as e:
                self.send_json(502, {"error": str(e)})
            return
        if path == "/human/server/queue":
            self.send_json(200, cmd_watch.pending(root))
            return
        if path == "/human/server/drafts":
            self.send_json(200, tidy_drafts(root, {}))
            return
        if path == "/human/server/tip":
            self.send_json(200, read_tip(root))
            return
        self.send_static(Path(self.translate_path(path)))

    def read_body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_POST(self):
        if self.path.split("?")[0] == "/human/projects":
            self.take_project()
            return
        pid, root, path = self.project()
        if root is None:
            self.send_json(404, {"error": f"no project at {path}"})
            return
        if path == "/human/server/update":
            updater.restart_when(idle, self.server.server_close)
            self.send_json(200, updater.status())
            return
        with BUSY_LOCK:
            BUSY[0] += 1
        try:
            self.write(root, path)
        finally:
            with BUSY_LOCK:
                BUSY[0] -= 1

    def take_project(self):
        if self.client_address[0] not in ("127.0.0.1", "::1"):
            self.send_json(403, {"error": "a project is given from this machine only"})
            return
        try:
            root = Path(self.read_body().get("root") or "")
            pid = add_project(root.resolve())
        except (ValueError, OSError, cmd_store.Refused) as e:
            self.send_json(400, {"error": str(e)})
            return
        self.send_json(200, {"id": pid})

    def write(self, root, path):
        m = re.fullmatch(r"/human/training/([^/]+)/(pick|close)", path)
        try:
            body = self.read_body()
            if path == "/human/compile":
                status, out = cmd_watch.compile_writing(root, body.get("name"), body.get("kind"),
                                                        body.get("id"), body.get("text"), body.get("words"))
            elif path == "/human/file":
                status, out = new_file(root, body.get("name"))
            elif path == "/human/human":
                status, out = new_human(root, body.get("name"), body.get("place"))
            elif path == "/human/server/drafts":
                status, out = keep_drafts(root, body.get("drafts"))
            elif path == "/human/server/tip":
                tip_path(root).unlink(missing_ok=True)
                status, out = 200, {}
            elif m and m.group(2) == "close":
                status, out = cmd_train.close_road(root, m.group(1))
            elif m:
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


def hand_over(root, port):
    ask = urllib.request.Request(f"http://127.0.0.1:{port}/human/projects", method="POST",
                                 data=json.dumps({"root": str(root)}).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(ask, timeout=5) as r:
            return json.loads(r.read()).get("id")
    except urllib.error.HTTPError as e:
        try:
            said = json.loads(e.read()).get("error")
        except ValueError:
            said = None
        if e.code == 400 and said:
            sys.exit(said)
        return None
    except (OSError, ValueError):
        return None


def print_links(pid, port):
    print(f"Click http://localhost:{port}/{pid}/human/web.html to read your human code!", flush=True)
    tip = tailnet_ip()
    if tip:
        print(f"This is the tailnet http://{tip}:{port}/{pid}/human/web.html in case you need it : )", flush=True)


def cmd_serve(a):
    root = decompiler.find_root(Path(a.folder).resolve())
    try:
        pid = cmd_store.project_id(root)
    except cmd_store.Refused as e:
        sys.exit(e.message)
    if hand_over(root, a.port):
        print_links(pid, a.port)
        return
    add_project(root)
    deploy_reader()
    FreshHandler.verbose = a.log
    handler = partial(FreshHandler, directory=str(root))
    try:
        srv = ThreadingHTTPServer(("0.0.0.0", a.port), handler)
    except OSError as e:
        sys.exit(f"port {a.port} is held by another program, or by a human server older than this one: {e.strerror}")
    print_links(pid, a.port)
    updater.start()
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
    shutil.copytree(PKG / "shapes", updater.HOME / "shapes", dirs_exist_ok=True)
    print(f"installed shapes -> {updater.HOME / 'shapes'}")


def main():
    ap = argparse.ArgumentParser(prog="human")
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("init")
    i.add_argument("folder", nargs="?", default=".")
    i.add_argument("--port", type=int, default=8010)
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
    y.add_argument("--for", dest="for_entry", type=int)
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
    n = sub.add_parser("tip")
    n.add_argument("code_file", nargs="?")
    n.add_argument("--entry", type=int, default=1)
    n.add_argument("--words")
    n.add_argument("--draft")
    n.add_argument("--say")
    n.add_argument("--clear", action="store_true")
    if updater.from_pypi():
        print(updater.MOVED, file=sys.stderr)
    a = ap.parse_args()
    if a.cmd in cmd_project.COMMANDS and helpers.no_code(a.code_file, decompiler.find_root(Path.cwd())):
        cmd_project.COMMANDS[a.cmd](a)
        return
    {"init": cmd_init, "serve": cmd_serve, "skills": cmd_skills, "map": cmd_map.cmd_map,
     "retext": decompiler.cmd_retext, "undo": decompiler.cmd_undo,
     "show": decompiler.cmd_show, "lines": decompiler.cmd_lines,
     "sync": decompiler.cmd_sync, "train": cmd_train.cmd_train,
     "watch": cmd_watch.cmd_watch, "ack": cmd_watch.cmd_ack,
     "login": cmd_store.cmd_login, "tip": cmd_tip}[a.cmd](a)


if __name__ == "__main__":
    main()
