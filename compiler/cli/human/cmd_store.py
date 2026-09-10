import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

URL = "https://gtfaf35mzbskdlynb3aysviyoy0aokpp.lambda-url.us-east-1.on.aws"
HEADER = "x-human-key"
LOGIN = "no key on this machine; log in first with human login <key>"


class Refused(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


class Unreachable(Exception):
    pass


def store_url():
    return (os.environ.get("HUMAN_STORE") or URL).rstrip("/")


def credentials_path():
    return Path(os.environ.get("HUMAN_CREDENTIALS") or Path.home() / ".config" / "human" / "credentials.json")


def credentials():
    p = credentials_path()
    if not p.is_file():
        return None
    return json.loads(p.read_text())


def call(method, path, key, payload=None):
    body = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(store_url() + path, data=body, method=method,
                                 headers={HEADER: key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            out = json.loads(e.read())
        except ValueError:
            out = e.reason
        return e.code, out
    except (urllib.error.URLError, OSError) as e:
        raise Unreachable(f"the training store does not answer: {getattr(e, 'reason', e)}")


def ask(method, path, payload=None):
    c = credentials()
    if not c:
        raise Refused(401, LOGIN)
    status, out = call(method, path, c["key"], payload)
    if status != 200:
        raise Refused(status, out if isinstance(out, str) else json.dumps(out))
    return out


def list_sessions():
    return ask("GET", "/sessions")


def get_session(sid):
    return ask("GET", f"/sessions/{sid}")


def put_session(data):
    return ask("PUT", f"/sessions/{data['session_id']}", data)


def open_session():
    for s in list_sessions():
        if not s["finished"]:
            return get_session(s["session_id"])
    return None


def login(key):
    status, out = call("POST", "/login", key)
    if status != 200:
        raise Refused(status, out if isinstance(out, str) else json.dumps(out))
    p = credentials_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"user": out["user"], "key": key}, indent=2) + "\n")
    p.chmod(0o600)
    return out["user"], p


def cmd_login(a):
    try:
        user, p = login(a.key.strip())
    except (Refused, Unreachable) as e:
        sys.exit(str(e))
    print(f"logged in as user {user}")
    print(f"wrote {p}")
