import hashlib
import json
import os
import platform
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
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


def program(v):
    return HOME / "versions" / v / "human" / ("human.exe" if os.name == "nt" else "human")


def download(v):
    manifest = json.loads(fetch(f"{DOWNLOADS}/{v}/manifest.json"))
    item = manifest["platforms"][place()]
    body = fetch(f"{DOWNLOADS}/{v}/{item['file']}", timeout=600)
    if hashlib.sha256(body).hexdigest() != item["checksum"]:
        raise ValueError(f"the checksum of {item['file']} does not match")
    dest = HOME / "versions" / v
    tmp = dest.with_name(v + ".tmp")
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
    shutil.rmtree(dest, ignore_errors=True)
    tmp.rename(dest)


def activate(v):
    BIN.mkdir(parents=True, exist_ok=True)
    link = BIN / "human"
    tmp = BIN / ".human.new"
    tmp.unlink(missing_ok=True)
    tmp.symlink_to(program(v))
    os.replace(tmp, link)


def sweep():
    for d in (HOME / "old").glob("*"):
        try:
            (d / "human.exe").unlink(missing_ok=True)
        except OSError:
            continue
        shutil.rmtree(d, ignore_errors=True)


def switch(v):
    sweep()
    away = HOME / "old" / str(time.time_ns())
    if CURRENT.exists():
        for f in [f for f in CURRENT.rglob("*") if f.is_file()]:
            to = away / f.relative_to(CURRENT)
            to.parent.mkdir(parents=True, exist_ok=True)
            os.replace(f, to)
        shutil.rmtree(CURRENT, ignore_errors=True)
    shutil.copytree(program(v).parent, CURRENT, dirs_exist_ok=True)


def remove():
    if os.name == "nt":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0,
                                winreg.KEY_READ | winreg.KEY_WRITE) as k:
                path, kind = winreg.QueryValueEx(k, "Path")
                keep = [d for d in path.split(";") if d and Path(d) != CURRENT]
                winreg.SetValueEx(k, "Path", 0, kind, ";".join(keep))
        except OSError:
            pass
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
    if os.name != "nt":
        activate(latest)
    subprocess.run([str(program(latest)), "skills"], capture_output=True,
                   creationflags=0x08000000 if os.name == "nt" else 0)
    with LOCK:
        STATE["ready"] = latest
        STATE["error"] = None


def watch():
    while True:
        try:
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
            switch(STATE["ready"])
            subprocess.Popen([str(CURRENT / "human.exe"), *sys.argv[1:]], creationflags=0x08000000)
            os._exit(0)
        new = str(program(STATE["ready"]))
        os.execv(new, [new, *sys.argv[1:]])

    threading.Thread(target=wait, daemon=True).start()
