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
from importlib import metadata
from pathlib import Path

DOWNLOADS = os.environ.get("HUMAN_DOWNLOADS", "https://downloads.doashuman.com").rstrip("/")
HOME = Path(os.environ.get("HUMAN_HOME") or Path.home() / ".human")
BIN = Path.home() / ".local" / "bin"
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
    if place() == "win32-x64":
        return HOME / "versions" / v / "human.exe"
    return HOME / "versions" / v / "human" / "human"


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
    if item["file"].endswith(".tar.gz"):
        with tempfile.TemporaryFile() as f:
            f.write(body)
            f.seek(0)
            with tarfile.open(fileobj=f, mode="r:gz") as t:
                t.extractall(tmp, filter="data")
    else:
        (tmp / "human.exe").write_bytes(body)
    shutil.rmtree(dest, ignore_errors=True)
    tmp.rename(dest)


def activate(v):
    BIN.mkdir(parents=True, exist_ok=True)
    if place() == "win32-x64":
        link = BIN / "human.exe"
        old = BIN / "human.exe.old"
        old.unlink(missing_ok=True)
        if link.exists():
            link.rename(old)
        shutil.copy2(program(v), link)
        return
    link = BIN / "human"
    tmp = BIN / ".human.new"
    tmp.unlink(missing_ok=True)
    tmp.symlink_to(program(v))
    os.replace(tmp, link)


def check():
    latest = fetch(f"{DOWNLOADS}/latest", timeout=10).decode().strip()
    if not newer(latest, STATE["ready"] or version()):
        return
    download(latest)
    activate(latest)
    subprocess.run([str(program(latest)), "skills"], capture_output=True)
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
        new = str(program(STATE["ready"]))
        args = [new, *sys.argv[1:]]
        if os.name == "nt":
            subprocess.Popen(args)
            os._exit(0)
        os.execv(new, args)

    threading.Thread(target=wait, daemon=True).start()
