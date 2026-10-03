import json
import re
import sys
from pathlib import Path

HUMAN_PREFIX = "human_"
MAP_PREFIX = "abstraction_"
OLD_MAP_PREFIX = "explanation_"
NO_CODE = ("human file",)


def find_root(path):
    d = path if path.is_dir() else path.parent
    while True:
        if (d / "human" / "human.json").is_file():
            migrate(d)
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
    rel = code_path.relative_to(root).as_posix()
    return root / "human" / f"{MAP_PREFIX}{rel.replace('/', '__')}.json"


def project_id(root):
    try:
        pid = json.loads((Path(root) / "human" / "human.json").read_text()).get("project")
    except (OSError, ValueError):
        pid = None
    if not isinstance(pid, str) or not pid:
        raise ValueError("no project id in human/human.json; run human init once at the root")
    return pid


def human_map_path(root, name):
    return Path(root) / "human" / f"{HUMAN_PREFIX}{name}.json"


def human_names(root):
    folder = Path(root) / "human"
    if not folder.is_dir():
        return []
    return sorted(p.name[len(HUMAN_PREFIX):-len(".json")]
                  for p in folder.glob(f"{HUMAN_PREFIX}*.json"))


def human_place(root, name):
    path = human_map_path(root, name)
    try:
        return json.loads(path.read_text()).get("place") or ""
    except Exception:
        return ""


def human_entries(root):
    return [{"name": n, "place": human_place(root, n)} for n in human_names(root)]


def is_bare(name):
    return "/" not in name and "\\" not in name and not Path(name).suffix


def name_to_map(name, project_root):
    root = Path(project_root)
    path = Path(name)
    if not path.is_absolute():
        path = root / name
    if path.is_dir():
        return map_path_of(path, root), "folder"
    if path.is_file() or not is_bare(name):
        return map_path_of(path, root), "file"
    return human_map_path(root, name), "human file"


def no_code(name, project_root):
    return name_to_map(name, project_root)[1] in NO_CODE


def no_code_maps(root, skip=None):
    return [(n, human_map_path(root, n)) for n in human_names(root) if n != skip]


def first_human_name(root):
    root = Path(root)
    name = re.sub(r"[^\w-]", "_", root.name).strip("_") or "project"
    if (root / name).exists():
        name = f"top_{name}"
    return name


def rename_pins(root, old, new):
    pat = re.compile(r"\]\(" + re.escape(old) + r"(?=[):])")
    for p in sorted((root / "human").glob("*.json")):
        try:
            data = json.loads(p.read_text())
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict) or not isinstance(data.get("explanations"), list):
            continue
        hit = False
        for e in data["explanations"]:
            text = pat.sub("](" + new, e.get("text", ""))
            if text != e.get("text"):
                e["text"] = text
                hit = True
            for x in e.get("anchors", []):
                if x.get("file") == old:
                    x["file"] = new
                    hit = True
        if hit:
            p.write_text(json.dumps(data, indent=2) + "\n")


def migrate(root):
    h = Path(root) / "human"
    for p in sorted(h.glob(f"{OLD_MAP_PREFIX}*.json")):
        q = h / (MAP_PREFIX + p.name[len(OLD_MAP_PREFIX):])
        if q.exists():
            continue
        p.rename(q)
    old = h / "project.json"
    if not old.exists():
        return
    try:
        data = json.loads(old.read_text())
    except (OSError, ValueError):
        return
    if not data.get("explanations"):
        old.unlink()
        return
    name = first_human_name(root)
    new = human_map_path(root, name)
    if new.exists():
        return
    data["code_file"] = name
    new.write_text(json.dumps(data, indent=2) + "\n")
    old.unlink()
    rename_pins(Path(root), "project", name)
