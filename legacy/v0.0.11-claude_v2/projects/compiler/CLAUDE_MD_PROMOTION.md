# Promote the instruction sheet

The `compiler` project compiles into `build/CLAUDE.md.human`. That output is
also the governing sheet at `CLAUDE.md` — the spec is its own fixed point: the
sheet that compiles programs is itself a compiled program of the language.
Promotion makes the governing sheet equal to the latest build, archiving the
current one under `claude_md_legacy/`.

Run from `projects/compiler/`:

```bash
SRC=build/CLAUDE.md.human
DST=CLAUDE.md

# 1. already promoted -> stop
if diff -q <(tr -d '\r' < "$DST") <(tr -d '\r' < "$SRC") >/dev/null; then
  echo "up to date; nothing to promote"; exit 0
fi

# 2. next legacy slot
N=$(ls claude_md_legacy/CLAUDE_0_0_*.md 2>/dev/null | sed 's/.*_//;s/\.md//' | sort -n | tail -1)
N=$(( ${N:-0} + 1 ))

# 3. archive current live, then promote the build
mkdir -p claude_md_legacy
cp "$DST" "claude_md_legacy/CLAUDE_0_0_$N.md"
cp "$SRC" "$DST"
echo "archived old sheet -> claude_md_legacy/CLAUDE_0_0_$N.md ; promoted build -> $DST"
```

Idempotent: when the build already matches the governing sheet it does nothing.
