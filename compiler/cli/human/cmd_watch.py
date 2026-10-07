import json
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from . import cmd_human, compiler, helpers

FOLDER = "server"
KINDS = ("retext", "map", "code", "expand", "create", "delete")
WRITTEN = ("retext", "map", "code", "expand", "create")
LOCK = threading.Lock()
ENTRY_RE = re.compile(r"^entry (\d+)", re.M)


def folder(root):
    p = root / "human" / FOLDER
    p.mkdir(parents=True, exist_ok=True)
    return p


def events_path(root):
    return folder(root) / "events.jsonl"


def cursor_path(root):
    return folder(root) / "cursor.json"


def read_events(root):
    p = events_path(root)
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def read_cursor(root):
    p = cursor_path(root)
    if not p.exists():
        return {"done": 0, "seen": 0}
    return json.loads(p.read_text())


def write_cursor(root, c):
    cursor_path(root).write_text(json.dumps(c) + "\n")


def append_event(root, event):
    events = read_events(root)
    event["seq"] = (events[-1]["seq"] if events else 0) + 1
    event["time"] = datetime.now().astimezone().isoformat(timespec="seconds")
    with events_path(root).open("a") as f:
        f.write(json.dumps(event) + "\n")
    return event["seq"]


def pending(root):
    c = read_cursor(root)
    out = [{"seq": e["seq"], "kind": e["kind"], "name": e["name"], "entry": e.get("entry")}
           for e in read_events(root) if e["seq"] > c["done"]]
    saved = [{"name": m["name"], "kind": m["kind"], "entry": m["entry"], "seq": m.get("seq")}
             for m in read_marks(root)]
    return {"done": c["done"], "seen": c["seen"], "pending": out, "not_compiled": saved}


def run_cli(root, args, text):
    me = [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, "-c", "from human import main; main()"]
    r = subprocess.run([*me, *args],
                       cwd=str(root), input=text, capture_output=True, text=True,
                       creationflags=0x08000000 if os.name == "nt" else 0)
    return r.returncode, (r.stdout + r.stderr).strip()


def map_of(root, name):
    p = helpers.name_to_map(name, root)[0]
    if not p.exists():
        return p, None
    return p, json.loads(p.read_text())


def pins_reaching(root, name):
    out = []
    maps = [mp for _, mp in helpers.no_code_maps(root)]
    maps += sorted((root / "human").glob(f"{helpers.MAP_PREFIX}*.json"))
    for mp in maps:
        if not mp.exists():
            continue
        data = json.loads(mp.read_text())
        for e in data.get("explanations", []):
            for x in e.get("anchors", []):
                if x.get("file") == name:
                    pin = {"map": str(mp), "entry": e["id"], "words": x["words"]}
                    for k in ("block", "anchor", "lines"):
                        if k in x:
                            pin[k] = x[k]
                    out.append(pin)
    return out


def marks_path(root):
    return folder(root) / "not_compiled.json"


def read_marks(root):
    try:
        d = json.loads(marks_path(root).read_text())
    except (OSError, ValueError):
        return []
    return d if isinstance(d, list) else []


def write_marks(root, marks):
    p = marks_path(root)
    tmp = p.with_name(f"{p.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(marks, indent=1) + "\n")
    tmp.replace(p)


def slot(m):
    return m["name"], m["kind"] == "code", m["entry"]


def mark(root, m):
    with LOCK:
        marks = read_marks(root)
        if any(slot(x) == slot(m) for x in marks if not x.get("seq")):
            return
        marks.append(m)
        write_marks(root, marks)


def unmark(root, name, eid):
    with LOCK:
        marks = read_marks(root)
        kept = [x for x in marks if x.get("seq") or x["name"] != name or x["entry"] != eid]
        if kept != marks:
            write_marks(root, kept)


def save_writing(root, name, kind, eid, text, words=None):
    if kind not in KINDS:
        return 400, f"unknown kind {kind!r}; one of {', '.join(KINDS)}"
    if kind in WRITTEN and (not text or not text.strip()):
        return 400, "the text is empty"
    no_code = helpers.no_code(name, root)
    file_path = None if no_code else (root / name).resolve()
    if not no_code and (root not in file_path.parents or not file_path.is_file()):
        return 400, f"{name} is not a file of the project"
    if not no_code and (root / "human") in file_path.parents:
        return 400, f"{name} belongs to the human folder; the maps take no writing"
    map_p, data = map_of(root, name)
    held = bool(data and data.get("explanations"))
    m = {"kind": kind, "name": name, "entry": eid, "old_text": None}
    if kind == "retext":
        entry = cmd_human.entry_of(data, eid) if data else None
        if entry is None:
            return 400, f"no entry {eid} in the map of {name}"
        code, out = run_cli(root, ["retext", name, str(eid), "--verbatim"], text)
        if code != 0:
            return 400, out
        m["old_text"] = entry["text"]
    elif kind == "map":
        if held and not no_code:
            return 400, f"{name} has a map; write on its entries"
        code, out = run_cli(root, ["map", name, "--verbatim"], text)
        if code != 0:
            return 400, out
        found = ENTRY_RE.search(out)
        m["entry"] = int(found.group(1)) if found else None
    elif kind in ("expand", "create"):
        entry = cmd_human.entry_of(data, eid) if data else None
        if entry is None:
            return 400, f"no entry {eid} in the map of {name}"
        if kind == "expand" and (not words or not words.strip()):
            return 400, "no highlighted words to expand"
        code, out = run_cli(root, ["map", name, "--verbatim"], text)
        if code != 0:
            return 400, out
        found = ENTRY_RE.search(out)
        said = f"expands entry {eid}" if kind == "expand" else f"stands over entry {eid}"
        m.update({"entry": int(found.group(1)) if found else None, "target": eid})
        out += f"  ·  {said}"
        if kind == "expand":
            m["words"] = words
    elif kind == "delete":
        entry = cmd_human.entry_of(data, eid) if data else None
        if entry is None:
            return 400, f"no entry {eid} in the map of {name}"
        code, out = run_cli(root, ["undo", name, "--entry", str(eid)], None)
        if code != 0:
            return 400, out
        unmark(root, name, eid)
        said = [l for l in out.splitlines() if not l.startswith("wrote ")]
        return 200, {"output": "  ·  ".join(said)}
    else:
        if no_code:
            return 400, f"{name} has no code under it"
        if held:
            return 400, f"{name} has a map; write on its entries, not on the code"
        m["old_text"] = file_path.read_text()
        file_path.write_text(text if text.endswith("\n") else text + "\n")
        if not pins_reaching(root, name):
            return 200, {"output": f"{name} saved; no telling stands on it"}
        out = f"{name} saved"
    mark(root, m)
    return 200, {"entry": m["entry"], "output": out}


def event_of(root, m):
    name = m["name"]
    no_code = helpers.no_code(name, root)
    map_p, data = map_of(root, name)
    file_path = None if no_code else (root / name).resolve()
    event = {"kind": m["kind"], "name": name, "map": str(map_p), "entry": m["entry"],
             "file": None if no_code else str(file_path), "old_text": m["old_text"]}
    if m["kind"] == "code":
        pins = pins_reaching(root, name)
        if not pins or not file_path.is_file():
            return None
        event.update({"map": None, "new_text": file_path.read_text(), "pins": pins})
        return event
    entry = cmd_human.entry_of(data, m["entry"]) if data else None
    if entry is None or entry["text"] == m["old_text"]:
        return None
    event["new_text"] = entry["text"]
    for k in ("target", "words"):
        if k in m:
            event[k] = m[k]
    return event


def compile_saved(root, name):
    with LOCK:
        kept, seqs = [], []
        for m in read_marks(root):
            if m["name"] == name and not m.get("seq"):
                event = event_of(root, m)
                if event is None:
                    continue
                m["seq"] = append_event(root, event)
                seqs.append(m["seq"])
            kept.append(m)
        write_marks(root, kept)
    if not seqs:
        return 200, {"seqs": [], "output": f"{name}: nothing saved waits for a compile"}
    return 200, {"seqs": seqs, "output": f"{name}: {len(seqs)} sent to the ai harness"}


def cmd_watch(a):
    root = compiler.find_root(Path.cwd())
    printed = 0
    print("read human watch with no pipe after it: a filter can hold back the last event", file=sys.stderr, flush=True)
    while True:
        c = read_cursor(root)
        events = [e for e in read_events(root) if e["seq"] > max(c["done"], printed)]
        for e in events:
            e["maybe_started"] = e["seq"] <= c["seen"]
            print(json.dumps(e), flush=True)
            printed = e["seq"]
        if events:
            c = read_cursor(root)
            c["seen"] = max(c["seen"], printed)
            write_cursor(root, c)
        if a.once:
            return
        time.sleep(1)


def cmd_ack(a):
    root = compiler.find_root(Path.cwd())
    c = read_cursor(root)
    last = max((e["seq"] for e in read_events(root)), default=0)
    if a.seq <= c["done"] or a.seq > last:
        sys.exit(f"nothing to ack at {a.seq}; done up to {c['done']}, last event {last}")
    c["done"] = a.seq
    c["seen"] = max(c["seen"], a.seq)
    write_cursor(root, c)
    marks = read_marks(root)
    kept = [m for m in marks if not m.get("seq") or m["seq"] > a.seq]
    if kept != marks:
        write_marks(root, kept)
    left = last - a.seq
    print(f"event {a.seq} done; {left} waiting" if left else f"event {a.seq} done; the queue is empty")
