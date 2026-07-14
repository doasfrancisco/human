from __future__ import annotations

import json
import re
import sys

from engine import (BUILD, LANG, MODEL_ID, PROGS, ROOT, Malformed, Node, build, caused_by, lower,
                    project, raises)

TWIG = "\\_ "

class Repl:
    def __init__(self):
        self.cursor: Node | None = None

    def listing(self) -> list[Node]:
        if self.cursor is not None:
            return self.cursor.children()
        progs = [Node(f"progs/{f.stem}") for f in sorted(PROGS.glob("*.human"))] if PROGS.is_dir() else []
        return progs + [Node(f"lang/{f.parent.name}/{f.stem}") for f in sorted(LANG.glob("*/*.human"))]

    def root_or_none(self) -> Node | None:
        if self.cursor is None or self.cursor.path.startswith("lang/"):
            print("cd into a program first")
            return None
        return self.cursor.program()

    def chain(self, node: Node) -> None:
        for i, a in enumerate(node.ancestors() + [node]):
            print(f"{'  ' * i}{TWIG if i else ''}{a.intent()}   [{a.path}]")

    def do_write(self, text: str):
        if self.cursor is None:
            slug = "_".join(re.findall(r"[a-z0-9]+", text.lower())[:3]) or "prog"
            name, i = slug, 2
            while Node(f"progs/{name}").file().exists():
                name, i = f"{slug}{i}", i + 1
            self.cursor = Node(f"progs/{name}")
            self.cursor.write(text)
            print(f"created {self.cursor.path} - now: lower, then build")
            return
        kids = self.cursor.children()
        print(f"this replaces: {self.cursor.intent()[:70]}")
        strand = f" and strand {len(kids)} child node(s)" if kids else ""
        if input(f"overwrite {self.cursor.path}{strand}? [y/N] ").strip().lower() not in ("y", "yes"):
            print("kept")
            return
        self.cursor.write(text)
        print(f"rewrote {self.cursor.path}{' - the subtree below is stale, run: lower' if kids else ''}")

    def do_add(self, text: str):
        if self.cursor is None or not text:
            print("cd into a node first, then: + <text>")
            return
        self.cursor.dir().mkdir(parents=True, exist_ok=True)
        child = Node(f"{self.cursor.path}/{len(self.cursor.children()) + 1}")
        child.write(text)
        print(f"added {child.path} - yours, never auto-discarded, still audited by check")

    def do_ls(self, _):
        if self.cursor is not None:
            print(f"  {self.cursor.intent()}\n")
        kids = self.listing()
        if not kids:
            print("  (nothing here - type what you want to build)" if self.cursor is None else "  (leaf - or: lower)")
        for i, c in enumerate(kids, 1):
            tag = "[lang] " if self.cursor is None and c.path.startswith("lang/") else ""
            print(f"  {i}.{'+' if c.children() else ' '} {tag}{' '.join(c.intent().split())[:64]}")

    def do_cd(self, arg: str):
        if arg in ("", "/"):
            self.cursor = None
            return
        if arg == "..":
            self.cursor = self.cursor.parent() if self.cursor else None
            return
        cands = self.listing()
        if arg.isdigit() and 1 <= int(arg) <= len(cands):
            self.cursor = cands[int(arg) - 1]
            return
        hit = [c for c in cands if c.name() == arg or c.intent().lower().startswith(arg.lower())]
        if hit:
            self.cursor = hit[0]
        elif Node(arg).file().exists():
            self.cursor = Node(arg)
        else:
            print(f"no such node: {arg}")

    def do_lower(self, arg: str):
        if self.cursor is None:
            print("cd into a node first")
            return
        queue = [self.cursor]
        while queue:
            node = queue.pop(0)
            proposed, survivors = lower(node)
            if not survivors:
                print(f"{node.path} is a leaf ({proposed} proposed, none caused code)")
                continue
            print(f"lowered {node.path}: {proposed} proposed, {len(survivors)} earned, "
                  f"{proposed - len(survivors)} discarded (caused no code)")
            if arg.strip() in ("-r", "--recursive"):
                queue.extend(survivors)
        self.do_ls("")

    def do_build(self, arg: str):
        root = self.root_or_none()
        if root is None:
            return
        py, code = build(root)
        if arg.strip() in ("-p", "--print"):
            print(code)
        print(f"compiled {root.path} -> {py.relative_to(ROOT)} ({len(code.splitlines())} lines)")
        print("provenance unmeasured - it costs one call per node. run: check")

    def do_check(self, _):
        root = self.root_or_none()
        if root is None:
            return
        py, code = build(root)
        ns = {"__name__": "fran_check", "__file__": str(py), "raises": raises}
        exec(compile(code, str(py), "exec"), ns)
        asserted = [(n, a) for n in root.subtree() for a in n.assertions()]
        passed = 0
        for n, a in asserted:
            try:
                ok = bool(eval(a, ns))
            except Exception as exc:
                ok, a = False, f"{a}   !! {exc}"
            passed += 1 if ok else 0
            print(f"  [test] {'pass' if ok else 'FAIL'} {n.path}: {a}")
        print(f"tests: {passed}/{len(asserted)} passed\n" if asserted else
              "the module runs, but it asserts nothing. add an 'assert:' line to any node.\n")
        measured = {n.path: caused_by(root, n, code) for n in root.subtree() if n.path != root.path}
        caused = {p: gone for p, (gone, _) in measured.items()}
        owners, ambiguous = project(code, caused)
        (BUILD / root.name() / "main.map.json").write_text(
            json.dumps({"owners": owners, "ambiguous": ambiguous}, indent=2), encoding="utf-8")
        dead = [p for p, c in caused.items() if not sum(c.values())]
        void = sum(1 for k, v in owners.items() if not v and k not in ambiguous)
        shared = sum(1 for v in owners.values() if len(v) > 1)
        drift = {p: sum(inv.values()) for p, (_, inv) in measured.items() if sum(inv.values())}
        for p in dead:
            print(f"  [ablate] DECORATIVE {p}: deleting it changed no line")
        print(f"provenance: {len(caused) - len(dead)}/{len(caused)} nodes caused code, "
              f"{len(owners) - void - shared - len(ambiguous)}/{len(owners)} lines owned by one node, "
              f"{void} unattributed, {shared} shared, {len(ambiguous)} ambiguous. "
              f"map: build/{root.name()}/main.map.json")
        print("  unattributed   no deletable node causes it: the root's own sentence, lang/, or the model's "
              "convention. the root is never ablated, so ablation cannot tell those apart.")
        if ambiguous:
            print(f"  ambiguous      {len(ambiguous)} line(s) whose text repeats in the build. a node took some "
                  "copies with it, but ablation cannot say which copy, so none is claimed.")
        for p, n in sorted(drift.items(), key=lambda kv: -kv[1]):
            print(f"  [drift] {p}: deleting it made the model invent {n} line(s) it was not forced to write. "
                  f"each one may be a restyling that stole causation from another node.")
        if drift:
            print(f"  the counts above are inflated by at most {sum(drift.values())} line(s) of drift.")

    def do_why(self, arg: str):
        if self.cursor is None:
            return print("cd into a node, or: why <line> inside a program")
        if not arg.strip():
            return self.chain(self.cursor)
        root = self.cursor.program()
        m = BUILD / root.name() / "main.map.json"
        if not m.exists():
            return print("provenance is not measured yet - run: check")
        data, ln = json.loads(m.read_text(encoding="utf-8")), arg.strip()
        owners, ambiguous = data["owners"].get(ln), data["ambiguous"].get(ln)
        if owners is None:
            return print(f"line {ln} is blank or out of range")
        if ambiguous:
            print(f"line {ln} repeats elsewhere in the build. deleting these took some copies away, but not "
                  f"every copy, and ablation cannot say which one this is:\n")
        elif not owners:
            return print(f"line {ln} is caused by no deletable node: it is {root.path}'s own sentence, or lang/, "
                         f"or the model's convention. deleting any child leaves it standing.")
        elif len(owners) > 1:
            print(f"line {ln} is shared - deleting any one of these takes it away:\n")
        for p in owners or ambiguous:
            self.chain(Node(p))

    def loop(self):
        print(f"fran v2 - model {MODEL_ID} - type what you want to build, or 'help'")
        table = {"ls": self.do_ls, "cd": self.do_cd, "lower": self.do_lower, "build": self.do_build,
                 "check": self.do_check, "why": self.do_why, "help": lambda _: print(HELP)}
        while True:
            try:
                line = input(f"{self.cursor.path if self.cursor else '/'}> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return
            if line in ("quit", "exit", "q"):
                return
            if not line:
                continue
            try:
                if line.startswith("+"):
                    self.do_add(line[1:].strip())
                    continue
                cmd, _, args = line.partition(" ")
                fn = table.get(cmd)
                fn(args.strip()) if fn else self.do_write(line)
            except Exception as exc:
                print(f"error: {exc}")

HELP = """  <text>            write. at / it starts a program; on a node it rewrites it, and asks first.
  + <text>          add a child by hand. yours - never auto-discarded, but still audited.
  ls                the cursor's text and its children, numbered. cd takes those numbers.
  cd <n|path|..|/>  move. lang/ is nodes too: cd into it and you have changed the compiler.
  lower [-r]        propose children, keep only the ones that cause code.
  build [-p]        compile the tree to build/. one call, one module. it does not lower.
  check             run the assertions, then delete every node to see what it caused. this
                    writes the map, and it costs one model call per node.
  why [<line>]      why this node exists, or which node caused line <n> of the build.
  quit

  provenance is measured by deletion, never claimed by the model."""

if __name__ == "__main__":
    argv, r = sys.argv[1:], Repl()
    if argv and argv[0] in ("build", "check", "lower"):
        r.cursor = Node(argv[1]) if len(argv) > 1 else None
        try:
            {"build": r.do_build, "check": r.do_check, "lower": r.do_lower}[argv[0]]("-r" if argv[0] == "lower" else "")
        except Malformed as exc:
            print(f"compile failed: {exc}")
            sys.exit(1)
    else:
        r.loop()
