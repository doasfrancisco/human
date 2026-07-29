from __future__ import annotations

import json
import sys

import compiler
from compiler import Malformed, Node

def projects() -> list[dict]:
    if not compiler.PROJECTS_JSON.exists():
        return []
    return json.loads(compiler.PROJECTS_JSON.read_text(encoding="utf-8")).get("projects", [])

def entry_for(name: str) -> dict | None:
    return next((e for e in projects() if e.get("name") == name), None)

def build_paths(entry: dict):
    d = compiler.PROJECTS / entry["name"] / "build"
    return d / entry["code_file"], d / "main.map.json"

def changed(root: Node, entry: dict) -> bool:
    _, mapf = build_paths(entry)
    if not mapf.exists():
        return True
    return json.loads(mapf.read_text(encoding="utf-8")).get("nodes") != compiler.tree_nodes(root)

def status(entry: dict) -> str:
    root = Node(entry["name"])
    if not root.file().exists():
        return "no source"
    codef, mapf = build_paths(entry)
    if not codef.exists() or not mapf.exists():
        return "unbuilt"
    return "stale" if changed(root, entry) else "built"

def do_list() -> None:
    entries = projects()
    if not entries:
        print("no projects: add one to projects.json")
        return
    for e in entries:
        req = " ".join(e.get("request", "").split())
        print(f"  {e['name']:<12} [{status(e)}] {e.get('code_file', 'main.py')} - {req[:80]}")

def do_compile(name: str) -> None:
    entry = entry_for(name)
    if entry is None:
        print(f"no project named {name} in projects.json")
        sys.exit(1)
    root = Node(name)
    if not root.file().exists():
        print(f"missing root sentence: {root.file()}")
        sys.exit(1)
    compiler.ensure_ids(root)
    if not root.children():
        queue = [root]
        while queue:
            node = queue.pop(0)
            made = compiler.lower(node)
            if made:
                print(f"lowered {node.path}: {len(made)} child node(s)")
            queue.extend(made)
        compiler.ensure_ids(root)
    codef, _ = build_paths(entry)
    baseline = None
    if codef.exists():
        if not changed(root, entry) and not compiler.FRESH:
            print(f"{name} is up to date: {codef}")
            return
        baseline = codef.read_text(encoding="utf-8").replace("\r\n", "\n")
    out, code, frags = compiler.build(root, entry, baseline)
    spec = sum(1 for f in frags if f["kind"] == "specified")
    asm = sum(1 for f in frags if f["kind"] == "assumed")
    print(f"compiled {name} -> {out} ({len(code.splitlines())} lines, {spec} specified + {asm} assumed fragments)")
    if entry["code_file"].endswith(".py"):
        results = compiler.check(root, code, out)
        passed = 0
        for n, a, ok, err in results:
            passed += ok
            print(f"  [test] {'pass' if ok else 'FAIL'} {n.path}: {a}{f'   !! {err}' if err else ''}")
        print(f"tests: {passed}/{len(results)} passed" if results else
              "the module runs, but it asserts nothing: add an 'assert:' line to any node")

def do_why(name: str, target: str) -> None:
    entry = entry_for(name)
    if entry is None:
        print(f"no project named {name} in projects.json")
        sys.exit(1)
    codef, mapf = build_paths(entry)
    if not mapf.exists() or not codef.exists():
        print(f"no build for {name}: run python human.py {name}")
        sys.exit(1)
    mp = json.loads(mapf.read_text(encoding="utf-8"))
    node = next((nd for nd in mp.get("nodes", []) if nd["id"] == target or nd["path"] == target), None)
    if node is None:
        print(f"no node {target} in the map for {name}")
        sys.exit(1)
    code = codef.read_text(encoding="utf-8").replace("\r\n", "\n")
    print(f"[@{node['id']} {node['path']}] {' '.join(node['text'].split())}")
    shown = 0
    for f in mp.get("map", []):
        if node["id"] not in f.get("nodes", []):
            continue
        others = [x for x in f["nodes"] if x != node["id"]]
        joint = f" with @{', @'.join(others)}" if others else ""
        head = f"[assumed] {f.get('why', '')}" if f["kind"] == "assumed" else "[specified]"
        for a, b in f["ranges"]:
            shown += 1
            print(f"\n  {head}{joint} chars {a}:{b}")
            lines = code[a:b].splitlines() or [code[a:b]]
            for line in lines[:20]:
                print(f"    {line}")
            if len(lines) > 20:
                print(f"    ... {len(lines) - 20} more line(s)")
    if not shown:
        print(f"\n  {node['path']} owns no declared region")

def main() -> None:
    argv = sys.argv[1:]
    if "--fresh" in argv:
        argv.remove("--fresh")
        compiler.FRESH = True
    if not argv:
        print("usage: python human.py --list | NAME [--fresh] | NAME --why ID_OR_PATH")
        return
    if argv[0] == "--list":
        do_list()
        return
    name = argv[0]
    if "--why" in argv:
        i = argv.index("--why")
        if len(argv) <= i + 1:
            print("usage: python human.py NAME --why ID_OR_PATH")
            sys.exit(2)
        do_why(name, argv[i + 1])
        return
    try:
        do_compile(name)
    except Malformed as exc:
        print(f"compile failed: {exc}")
        sys.exit(1)

if __name__ == "__main__":
    main()
