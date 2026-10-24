import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import urllib.request
import zipfile
from importlib import metadata
from pathlib import Path

DOWNLOADS = os.environ.get("HUMAN_DOWNLOADS", "https://downloads.doashuman.com").rstrip("/")
HOME = Path(os.environ.get("HUMAN_HOME") or Path.home() / ".human")
BIN = Path.home() / ".local" / "bin"
CURRENT = HOME / "current"
SHIMS = HOME / "bin"
EVERY = int(os.environ.get("HUMAN_UPDATE_EVERY") or 3600)
MOVED = "human moved: curl -fsSL https://doashuman.com/install.sh | bash"
STATE = {"ready": None, "restart": False, "error": None}
LOCK = threading.Lock()


def version():
    try:
        return metadata.version("humanlang")
    except metadata.PackageNotFoundError:
        return "0.0.0"


def frozen():
    return bool(getattr(sys, "frozen", False))


def from_pypi():
    if frozen():
        return False
    try:
        return metadata.distribution("humanlang").read_text("direct_url.json") is None
    except metadata.PackageNotFoundError:
        return False


def place():
    system = {"Linux": "linux", "Darwin": "darwin", "Windows": "win32"}.get(platform.system())
    machine = platform.machine().lower()
    arch = {"x86_64": "x64", "amd64": "x64", "arm64": "arm64", "aarch64": "arm64"}.get(machine)
    return f"{system}-{arch}" if system and arch else None


def newer(a, b):
    def parts(v):
        return tuple(int(x) for x in v.strip().lstrip("v").split("."))
    try:
        return parts(a) > parts(b)
    except ValueError:
        return False


def fetch(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": f"human/{version()}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def program(v):
    return HOME / "versions" / v / "human" / ("human.exe" if os.name == "nt" else "human")


def says(exe):
    try:
        r = subprocess.run([str(exe), "--version"], capture_output=True, text=True, timeout=60,
                           creationflags=0x08000000 if os.name == "nt" else 0)
    except (OSError, subprocess.SubprocessError):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def download(v):
    dest = HOME / "versions" / v
    if program(v).is_file():
        return
    manifest = json.loads(fetch(f"{DOWNLOADS}/{v}/manifest.json"))
    item = manifest["platforms"][place()]
    body = fetch(f"{DOWNLOADS}/{v}/{item['file']}", timeout=600)
    if hashlib.sha256(body).hexdigest() != item["checksum"]:
        raise ValueError(f"the checksum of {item['file']} does not match")
    tmp = dest.with_name(f"{v}.staging-{os.getpid()}")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    with tempfile.TemporaryFile() as f:
        f.write(body)
        f.seek(0)
        if item["file"].endswith(".zip"):
            with zipfile.ZipFile(f) as z:
                z.extractall(tmp)
        else:
            with tarfile.open(fileobj=f, mode="r:gz") as t:
                t.extractall(tmp, filter="data")
    if os.name == "nt":
        said = says(tmp / "human" / "human.exe")
        if said != f"human {v}":
            shutil.rmtree(tmp, ignore_errors=True)
            raise ValueError(f"the new human {v} does not start here (it said {said!r}); the old version stays")
    shutil.rmtree(dest, ignore_errors=True)
    tmp.rename(dest)


def activate(v):
    BIN.mkdir(parents=True, exist_ok=True)
    link = BIN / "human"
    tmp = BIN / ".human.new"
    tmp.unlink(missing_ok=True)
    tmp.symlink_to(program(v))
    os.replace(tmp, link)


def write(path, text):
    tmp = path.with_name(path.name + ".new")
    tmp.write_bytes(text.encode())
    os.replace(tmp, path)


def point(v):
    SHIMS.mkdir(parents=True, exist_ok=True)
    exe = str(program(v))
    write(SHIMS / "human.cmd", f'@"{exe}" %* & call exit /b %%errorlevel%%\r\n')
    write(SHIMS / "human", f'#!/bin/sh\nexec "{exe.replace(chr(92), "/")}" "$@"\n')


def pointed():
    try:
        m = re.search(r"versions[\\/]([^\\/]+)[\\/]human", (SHIMS / "human.cmd").read_text("utf-8", "replace"))
    except OSError:
        return None
    return m.group(1) if m else None


def user_path(add=None):
    import ctypes
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0,
                            winreg.KEY_READ | winreg.KEY_WRITE) as k:
            try:
                path, kind = winreg.QueryValueEx(k, "Path")
            except FileNotFoundError:
                path, kind = "", winreg.REG_EXPAND_SZ
            drop = {str(CURRENT).lower(), str(SHIMS).lower()}
            keep = [d for d in path.split(";") if d and d.rstrip("\\").lower() not in drop]
            new = ";".join(([str(add)] if add else []) + keep)
            if new == path:
                return
            winreg.SetValueEx(k, "Path", 0, kind, new)
    except OSError:
        return
    ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x1A, 0, "Environment", 0x2, 5000, None)


def settle():
    if not (os.name == "nt" and frozen()):
        return
    if not pointed() and program(version()).is_file():
        point(version())
    if pointed():
        user_path(add=SHIMS)


def prune():
    if not (os.name == "nt" and frozen()):
        return
    keep = {version(), pointed(), STATE["ready"]}
    old = [d for d in (HOME / "versions").glob("*") if d.is_dir() and d.name not in keep]
    for d in old + [CURRENT, HOME / "old"]:
        if not d.exists():
            continue
        if d.name.startswith(".delete-"):
            shutil.rmtree(d, ignore_errors=True)
            continue
        if ".staging-" in d.name and time.time() - d.stat().st_mtime < 3600:
            continue
        away = d.with_name(f".delete-{d.name}-{os.getpid()}")
        try:
            d.rename(away)
        except OSError:
            print(f"warning: {d} is in use by a running human; the next update tries again to delete it",
                  file=sys.stderr)
            continue
        shutil.rmtree(away, ignore_errors=True)


def remove():
    if os.name == "nt":
        user_path()
        subprocess.Popen(f'cmd /c ping 127.0.0.1 -n 3 > nul & rmdir /s /q "{HOME}"',
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=0x00000008 | 0x00000200)
        return
    link = BIN / "human"
    if link.is_symlink():
        link.unlink()
    shutil.rmtree(HOME, ignore_errors=True)


def check():
    latest = fetch(f"{DOWNLOADS}/latest", timeout=10).decode().strip()
    if not newer(latest, STATE["ready"] or version()):
        return
    download(latest)
    if os.name == "nt":
        point(latest)
    else:
        activate(latest)
    subprocess.run([str(program(latest)), "skills"], capture_output=True,
                   creationflags=0x08000000 if os.name == "nt" else 0)
    with LOCK:
        STATE["ready"] = latest
        STATE["error"] = None


def watch():
    try:
        settle()
    except Exception as e:
        STATE["error"] = str(e)
    time.sleep(10)
    while True:
        try:
            prune()
            check()
        except Exception as e:
            STATE["error"] = str(e)
        time.sleep(EVERY)


def start():
    if frozen() and place():
        threading.Thread(target=watch, daemon=True).start()


def status():
    with LOCK:
        return {"version": version(), "ready": STATE["ready"], "restart": STATE["restart"]}


def restart_when(idle, close):
    with LOCK:
        if not STATE["ready"] or STATE["restart"]:
            return
        STATE["restart"] = True

    def wait():
        while not idle():
            time.sleep(1)
        close()
        if os.name == "nt":
            subprocess.Popen([str(program(STATE["ready"])), *sys.argv[1:]], creationflags=0x08000000)
            os._exit(0)
        new = str(program(STATE["ready"]))
        os.execv(new, [new, *sys.argv[1:]])

    threading.Thread(target=wait, daemon=True).start()
