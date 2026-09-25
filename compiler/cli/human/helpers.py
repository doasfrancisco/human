import sys
from pathlib import Path

WORD = "project"
HUMAN_PREFIX = "human_"
SORTS = ("file", "folder", "project", "human file")
NO_CODE = ("project", "human file")


def find_root(path):
    d = path if path.is_dir() else path.parent
    while True:
        if (d / "human" / "human.json").is_file():
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
    if code_path.is_dir():
        return root / "human" / "human.json"
    rel = code_path.relative_to(root).as_posix()
    return root / "human" / f"explanation_{rel.replace('/', '__')}.json"


def human_map_path(root, name):
    return Path(root) / "human" / f"{HUMAN_PREFIX}{name}.json"


def human_names(root):
    folder = Path(root) / "human"
    if not folder.is_dir():
        return []
    return sorted(p.name[len(HUMAN_PREFIX):-len(".json")]
                  for p in folder.glob(f"{HUMAN_PREFIX}*.json"))


def is_bare(name):
    return "/" not in name and "\\" not in name and not Path(name).suffix


def name_to_map(name, project_root):
    root = Path(project_root)
    if name == WORD:
        return root / "human" / f"{WORD}.json", "project"
    path = Path(name)
    if not path.is_absolute():
        path = root / name
    if path.is_dir():
        return root / "human" / "human.json", "folder"
    if path.is_file() or not is_bare(name):
        return map_path_of(path, root), "file"
    return human_map_path(root, name), "human file"


def no_code(name, project_root):
    return name_to_map(name, project_root)[1] in NO_CODE


def no_code_maps(root, skip=None):
    root = Path(root)
    out = []
    p = root / "human" / f"{WORD}.json"
    if p.exists():
        out.append((WORD, p))
    for name in human_names(root):
        out.append((name, human_map_path(root, name)))
    return [(n, p) for n, p in out if n != skip]
