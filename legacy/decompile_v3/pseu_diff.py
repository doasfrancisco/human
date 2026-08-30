import difflib
import sys
from pathlib import Path

NAMES = {"insert": "ADDITION", "delete": "DELETION", "replace": "REPLACEMENT"}


def show(tag, lines, a, b):
    print(tag)
    for l in lines[a:b]:
        print(f"    {l}")


def main():
    if len(sys.argv) == 2:
        new = Path(sys.argv[1])
        old = new.parent / f".{new.name}"
    elif len(sys.argv) == 3:
        old, new = Path(sys.argv[1]), Path(sys.argv[2])
    else:
        sys.exit("usage: pseu_diff.py file.pseu | pseu_diff.py old new")
    if not old.exists():
        sys.exit(f"no backup: {old}")
    a = old.read_text(encoding="utf-8").splitlines()
    b = new.read_text(encoding="utf-8").splitlines()
    ops = [op for op in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes() if op[0] != "equal"]
    if not ops:
        print("NO CHANGES")
        return
    for tag, i1, i2, j1, j2 in ops:
        if tag == "insert":
            where = f"after old line {i1}, new lines {j1 + 1}-{j2}"
        elif tag == "delete":
            where = f"old lines {i1 + 1}-{i2}, after new line {j1}"
        else:
            where = f"old lines {i1 + 1}-{i2}, new lines {j1 + 1}-{j2}"
        print(f"{NAMES[tag]} {where}")
        show("  context before:", b, max(0, j1 - 3), j1)
        if tag != "insert":
            show("  old:", a, i1, i2)
        if tag != "delete":
            show("  new:", b, j1, j2)
        show("  context after:", b, j2, min(len(b), j2 + 3))
        print()


if __name__ == "__main__":
    main()
