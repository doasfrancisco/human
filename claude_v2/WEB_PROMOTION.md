# Promote the web

The `web` project compiles into `projects/web/build/index.html`. That output is
also the live app at `web/index.html`. Promotion makes the live app equal to the
latest build, archiving the current live one under `web_legacy/`.

Run from `claude_v2/`:

```bash
SRC=projects/web/build/index.html
DST=web/index.html

# 1. already promoted -> stop
if diff -q <(tr -d '\r' < "$DST") <(tr -d '\r' < "$SRC") >/dev/null; then
  echo "up to date; nothing to promote"; exit 0
fi

# 2. next legacy slot
N=$(ls -d web_legacy/web_0_0_* 2>/dev/null | sed 's/.*_//' | sort -n | tail -1)
N=$(( ${N:-0} + 1 ))

# 3. archive current live, then promote the build
mkdir -p web_legacy
mv web "web_legacy/web_0_0_$N"
mkdir -p web
cp "$SRC" "$DST"
echo "archived old live -> web_legacy/web_0_0_$N ; promoted build -> web"
```

Idempotent: when the build already matches the live app it does nothing.
