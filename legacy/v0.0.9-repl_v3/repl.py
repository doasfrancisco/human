from __future__ import annotations

import re
import sys

from human_compiler import (BUILD, LANG, MODEL_ID, PROGS, ROOT, Malformed, Node, build, check,
                            compiled_rendering, decorative, equivalent, fold, lower, owns, raises, revise)

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
        old = compiled_rendering(self.cursor)
        print(f"this replaces: {self.cursor.intent()[:70]}")
        if input(f"overwrite {self.cursor.path}? [y/N] ").strip().lower() not in ("y", "yes"):
            print("kept")
            return
        if old is None:
            self.cursor.write(text)
            print(f"rewrote {self.cursor.path}{' - subtree is stale, run: lower' if kids else ' - now: build'}")
            return
        new_intent = re.sub(r"^assert:\s*.+$", "", text, flags=re.M).strip()
        if equivalent(old, new_intent):
            self.cursor.write(text)
            print(f"reword {self.cursor.path} - same meaning, build kept, no rebuild")
            return
        print(f"revise {self.cursor.path} - meaning changed, minimal-diff rebuild...")
        py, code, _ = revise(self.cursor, text)
        print(f"rebuilt -> {py.relative_to(ROOT)} ({len(code.splitlines())} lines)"
              f"{' - subtree is stale, run: lower' if kids else ''}")

    def do_add(self, text: str):
        if self.cursor is None or not text:
            print("cd into a node first, then: + <text>")
            return
        self.cursor.dir().mkdir(parents=True, exist_ok=True)
        child = Node(f"{self.cursor.path}/{len(self.cursor.children()) + 1}")
        child.write(text)
        print(f"added {child.path} - yours, never folded away, still audited by check")

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
            proposed, made = lower(node)
            if not made:
                print(f"{node.path} is a leaf ({proposed} proposed, none)")
                continue
            print(f"lowered {node.path}: {len(made)} child node(s) written")
            if arg.strip() in ("-r", "--recursive"):
                queue.extend(made)
        self.do_ls("")

    def do_fold(self, _):
        if self.cursor is None:
            print("cd into a node first")
            return
        if not self.cursor.children():
            print("leaf - nothing to fold")
            return
        sentence = fold(self.cursor)
        print(f"fold {self.cursor.path}:\n  {sentence}\n")
        if input("adopt as this node's text (strands its children)? [y/N] ").strip().lower() in ("y", "yes"):
            self.cursor.write(sentence)
            print("adopted - the children below are now stale")
        else:
            print("kept - fold was a view only")

    def do_build(self, arg: str):
        root = self.root_or_none()
        if root is None:
            return
        py, code, cmap = build(root)
        if arg.strip() in ("-p", "--print"):
            print(code)
        spec = sum(1 for e in cmap if e["kind"] == "specified" and e["ranges"])
        assumed = sum(1 for e in cmap if e["kind"] == "assumed" and e["ranges"])
        print(f"compiled {root.path} -> {py.relative_to(ROOT)} ({len(code.splitlines())} lines)")
        print(f"provenance declared: {spec} specified, {assumed} assumed region-set(s). run: why | check")
        for p in decorative(root):
            print(f"  [decorative] {p}: the build declares no region to it")

    def do_check(self, _):
        root = self.root_or_none()
        if root is None:
            return
        results, _, cmap = check(root)
        passed = 0
        for n, a, ok, err in results:
            passed += ok
            shown = f"{a}   !! {err}" if err else a
            print(f"  [test] {'pass' if ok else 'FAIL'} {n.path}: {shown}")
        print(f"tests: {passed}/{len(results)} passed" if results else
              "the module runs, but it asserts nothing. add an 'assert:' line to any node.")
        for e in cmap:
            if e["kind"] == "assumed" and e["ranges"]:
                print(f"  [assumed] {e['node']}: {len(e['ranges'])} region(s) the model filled by convention")
        for p in decorative(root):
            print(f"  [decorative] {p}: the build declares no region to it")

    def do_why(self, arg: str):
        node = self.cursor
        if arg.strip():
            cands = self.listing()
            if arg.strip().isdigit() and 1 <= int(arg) <= len(cands):
                node = cands[int(arg) - 1]
            elif Node(arg.strip()).file().exists():
                node = Node(arg.strip())
        if node is None:
            print("cd into a node, or: why <n|path>")
            return
        root = node.program()
        entries = owns(root, node.path)
        if entries is None:
            print("no build yet - run: build")
            return
        code = (BUILD / root.name() / "main.py").read_text(encoding="utf-8")
        self.chain(node)
        shown = 0
        for e in entries:
            for a, b in e["ranges"]:
                shown += 1
                print(f"\n  [{e['kind']}] chars {a}:{b}")
                for line in (code[a:b].splitlines() or [code[a:b]]):
                    print(f"    {line}")
        if not shown:
            print(f"\n  {node.path} owns no declared region - decorative, or the root's own sentence / a convention.")

    def loop(self):
        print(f"human v3 - model {MODEL_ID} - type what you want to build, or 'help'")
        table = {"ls": self.do_ls, "cd": self.do_cd, "lower": self.do_lower, "fold": self.do_fold,
                 "build": self.do_build, "check": self.do_check, "why": self.do_why,
                 "help": lambda _: print(HELP)}
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

HELP = """  <text>            write. at / it starts a program; on a built node it classifies the edit.
  + <text>          add a child by hand. yours - never folded away, but still audited.
  ls                the cursor's text and its children, numbered. cd takes those numbers.
  cd <n|path|..|/>  move. lang/ is nodes too: cd into it and you have changed the compiler.
  lower [-r]        one idea -> its child ideas. provenance is declared, so none are ablated.
  fold              inverse of lower: read the children, view one summarizing sentence up.
  build [-p]        compile the tree to build/. one call returns {code, map}, declared.
  check             run the assertions - the only ground truth - and surface assumed regions.
  why [<n|path>]    the idea<->code map at this node: the regions it owns, specified vs assumed.
  quit

  meaning is declared at generation, never measured by deletion. asserts are the check."""

if __name__ == "__main__":
    argv, r = sys.argv[1:], Repl()
    if argv and argv[0] in ("build", "check", "lower", "fold"):
        r.cursor = Node(argv[1]) if len(argv) > 1 else None
        try:
            {"build": r.do_build, "check": r.do_check, "lower": r.do_lower, "fold": r.do_fold}[argv[0]](
                "-r" if argv[0] == "lower" else "")
        except Malformed as exc:
            print(f"compile failed: {exc}")
            sys.exit(1)
    else:
        r.loop()
