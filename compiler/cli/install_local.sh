#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
version="$(grep -m1 '^version' pyproject.toml | cut -d'"' -f2)"
HUMAN_HOME="${HUMAN_HOME:-$HOME/.human}"
BIN="$HOME/.local/bin"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
uv venv --quiet --python 3.12 "$work/venv"
uv pip install --quiet --python "$work/venv" pyinstaller .
echo "from human import main; main()" > "$work/entry.py"
"$work/venv/bin/pyinstaller" --noconfirm --log-level WARN --name human --collect-data human --copy-metadata humanlang \
  --distpath "$work/dist" --workpath "$work/build" --specpath "$work" "$work/entry.py"
"$work/dist/human/human" --help > /dev/null

dest="$HUMAN_HOME/versions/$version"
rm -rf "$dest"
mkdir -p "$dest" "$BIN"
mv "$work/dist/human" "$dest/human"
ln -sfn "$dest/human/human" "$BIN/human"

"$BIN/human" skills
echo "human $version built here and installed at $BIN/human"
