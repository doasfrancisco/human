#!/usr/bin/env bash
set -euo pipefail

DOWNLOADS="${HUMAN_DOWNLOADS:-https://downloads.doashuman.com}"
HUMAN_HOME="${HUMAN_HOME:-$HOME/.human}"
BIN="$HOME/.local/bin"

fail() { echo "human: $*" >&2; exit 1; }

case "$(uname -s)" in
  Linux) os=linux ;;
  Darwin) os=darwin ;;
  *) fail "$(uname -s) is not supported; on windows run: irm https://doashuman.com/install.ps1 | iex" ;;
esac
case "$(uname -m)" in
  x86_64|amd64) arch=x64 ;;
  arm64|aarch64) arch=arm64 ;;
  *) fail "$(uname -m) is not supported" ;;
esac
if [ "$os" = darwin ] && [ "$arch" = x64 ] && [ "$(sysctl -n sysctl.proc_translated 2>/dev/null)" = 1 ]; then
  arch=arm64
fi
place="$os-$arch"

command -v curl >/dev/null || fail "curl is needed"
command -v tar >/dev/null || fail "tar is needed"
if command -v sha256sum >/dev/null; then
  sum() { sha256sum "$1" | cut -d' ' -f1; }
elif command -v shasum >/dev/null; then
  sum() { shasum -a 256 "$1" | cut -d' ' -f1; }
else
  fail "sha256sum or shasum is needed"
fi

version="$(curl -fsSL "$DOWNLOADS/latest" | tr -d '[:space:]')"
[ -n "$version" ] || fail "no version at $DOWNLOADS/latest"
line="$(curl -fsSL "$DOWNLOADS/$version/manifest.json" | grep "\"$place\"")" || fail "no program for $place in human $version"
file="$(printf '%s' "$line" | sed -E 's/.*"file": *"([^"]+)".*/\1/')"
checksum="$(printf '%s' "$line" | sed -E 's/.*"checksum": *"([0-9a-f]{64})".*/\1/')"

tmp="$(mktemp -d "$HOME/human-install.XXXXXX")"
trap 'rm -rf "$tmp"' EXIT
echo "downloading human $version for $place"
curl -fSL --progress-bar -o "$tmp/$file" "$DOWNLOADS/$version/$file"
[ "$(sum "$tmp/$file")" = "$checksum" ] || fail "the checksum of $file does not match; nothing was installed"

dest="$HUMAN_HOME/versions/$version"
rm -rf "$dest.tmp"
mkdir -p "$dest.tmp"
tar -xzf "$tmp/$file" -C "$dest.tmp"
rm -rf "$dest"
mv "$dest.tmp" "$dest"
mkdir -p "$BIN"
ln -sfn "$dest/human/human" "$BIN/human"

"$BIN/human" skills

echo "human $version installed at $BIN/human"
case ":$PATH:" in
  *":$BIN:"*) ;;
  *) echo "add $BIN to your PATH, for example: echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc" ;;
esac
