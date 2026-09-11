import json
import re
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from . import cmd_project, decompiler

FOLDER = "server"
KINDS = ("retext", "map", "code", "decompile", "expand", "create", "delete", "link")
TRAINED = ("decompile", "expand", "create")
WRITTEN = ("retext", "map", "code")
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
    return {"done": c["done"], "seen": c["seen"], "pending": out}


def run_cli(root, args, text):
    r = subprocess.run([sys.executable, "-c", "from human import main; main()", *args],
                       cwd=str(root), input=text, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def map_of(root, name):
    if name == cmd_project.WORD:
        p = cmd_project.map_path(root)
    else:
        p = decompiler.map_path_of(root / name, root)
    if not p.exists():
        return p, None
    return p, json.loads(p.read_text())


def pins_reaching(root, name):
    out = []
    maps = [cmd_project.map_path(root)] + sorted((root / "human").glob("explanation_*.json"))
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


def training_for(root, event):
    from . import cmd_store, cmd_train
    if event["kind"] not in TRAINED or event.get("new_text") is not None or not cmd_store.credentials():
        return
    notes = []
    try:
        session, made = cmd_train.ensure_open(root, notes)
    except (cmd_store.Refused, cmd_store.Unreachable) as e:
        event["session"] = None
        event["output"] += f"  ·  no training: {e}"
        return
    event["session"] = session["session_id"]
    event["output"] += f"  ·  training {session['session_id']}" + (" opened" if made else "")


def compile_writing(root, name, kind, eid, text, words=None):
    if kind not in KINDS or kind == "link":
        return 400, f"unknown kind {kind!r}; one of {', '.join(KINDS[:-1])}"
    if kind in WRITTEN and (not text or not text.strip()):
        return 400, "the text is empty"
    is_project = name == cmd_project.WORD
    file_path = None if is_project else (root / name).resolve()
    if not is_project and (root not in file_path.parents or not file_path.is_file()):
        return 400, f"{name} is not a file of the project"
    if not is_project and (root / "human") in file_path.parents:
        return 400, f"{name} belongs to the human folder; the maps take no writing"
    map_p, data = map_of(root, name)
    event = {"kind": kind, "name": name, "map": str(map_p), "entry": eid,
             "file": None if is_project else str(file_path)}
    if kind == "retext":
        entry = cmd_project.entry_of(data, eid) if data else None
        if entry is None:
            return 400, f"no entry {eid} in the map of {name}"
        code, out = run_cli(root, ["retext", name, str(eid), "--verbatim"], text)
        if code != 0:
            return 400, out
        event.update({"old_text": entry["text"], "new_text": text, "output": out})
    elif kind == "map":
        if data and not is_project:
            return 400, f"{name} has a map; write on its entries"
        code, out = run_cli(root, ["map", name, "--verbatim"], text)
        if code != 0:
            return 400, out
        m = ENTRY_RE.search(out)
        event.update({"entry": int(m.group(1)) if m else None, "old_text": None,
                      "new_text": text, "output": out})
    elif kind == "decompile":
        if is_project:
            return 400, "the project has no code of its own"
        if data:
            return 400, f"{name} has a map; expand or create on its entries"
        if not file_path.read_text(errors="replace").strip():
            return 400, f"{name} is empty; write its telling, and claude writes the code under it"
        event.update({"entry": None, "old_text": None, "new_text": None,
                      "output": f"decompile of {name} waits for claude"})
    elif kind == "create":
        entry = cmd_project.entry_of(data, eid) if data else None
        if entry is None:
            return 400, f"no entry {eid} in the map of {name}"
        event.update({"target": eid, "old_text": None, "new_text": None,
                      "output": f"a top abstraction over entry {eid} of {name} waits for claude"})
    elif kind == "delete":
        entry = cmd_project.entry_of(data, eid) if data else None
        if entry is None:
            return 400, f"no entry {eid} in the map of {name}"
        code, out = run_cli(root, ["undo", name, "--entry", str(eid)], None)
        if code != 0:
            return 400, out
        said = [l for l in out.splitlines() if not l.startswith("wrote ")]
        return 200, {"seq": None, "output": "  ·  ".join(said)}
    elif kind == "expand":
        entry = cmd_project.entry_of(data, eid) if data else None
        if entry is None:
            return 400, f"no entry {eid} in the map of {name}"
        if not words or not words.strip():
            return 400, "no highlighted words to expand"
        event.update({"target": eid, "words": words, "old_text": None, "new_text": None})
        if text and text.strip():
            code, out = run_cli(root, ["map", name, "--verbatim"], text)
            if code != 0:
                return 400, out
            m = ENTRY_RE.search(out)
            event.update({"entry": int(m.group(1)) if m else None, "new_text": text,
                          "output": out + f"  ·  expands entry {eid}"})
        else:
            event["output"] = f"an expansion of entry {eid} of {name} waits for claude"
    else:
        if is_project:
            return 400, "the project has no code of its own"
        if data:
            return 400, f"{name} has a map; write on its entries, not on the code"
        old = file_path.read_text()
        file_path.write_text(text if text.endswith("\n") else text + "\n")
        pins = pins_reaching(root, name)
        if not pins:
            return 200, {"seq": None, "output": f"{name} saved; no telling stands on it"}
        event.update({"map": None, "entry": None, "old_text": old, "new_text": text,
                      "pins": pins, "output": f"{name} saved; {len(pins)} pins reach it"})
    training_for(root, event)
    with LOCK:
        seq = append_event(root, event)
    return 200, {"seq": seq, "output": event["output"]}


def cmd_watch(a):
    root = decompiler.find_root(Path.cwd())
    printed = 0
    while True:
        c = read_cursor(root)
        events = [e for e in read_events(root) if e["seq"] > max(c["done"], printed)]
        for e in events:
            e["replay"] = e["seq"] <= c["seen"]
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
    root = decompiler.find_root(Path.cwd())
    c = read_cursor(root)
    last = max((e["seq"] for e in read_events(root)), default=0)
    if a.seq <= c["done"] or a.seq > last:
        sys.exit(f"nothing to ack at {a.seq}; done up to {c['done']}, last event {last}")
    c["done"] = a.seq
    c["seen"] = max(c["seen"], a.seq)
    write_cursor(root, c)
    left = last - a.seq
    print(f"event {a.seq} done; {left} waiting" if left else f"event {a.seq} done; the queue is empty")
