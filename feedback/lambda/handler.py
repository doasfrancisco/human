import base64
import json
import os

import boto3

BUCKET = os.environ["BUCKET"]
HEADER = "x-human-key"
s3 = boto3.client("s3")


def answer(status, payload):
    return {"statusCode": status, "headers": {"Content-Type": "application/json"},
            "body": json.dumps(payload)}


def read(key):
    try:
        return json.loads(s3.get_object(Bucket=BUCKET, Key=key)["Body"].read())
    except s3.exceptions.NoSuchKey:
        return None


def write(key, payload):
    s3.put_object(Bucket=BUCKET, Key=key, Body=json.dumps(payload, indent=2).encode(),
                  ContentType="application/json")


def summary(data):
    rows = data.get("rows", [])
    return {"session_id": data["session_id"], "project": data.get("project"), "created": data.get("created"),
            "edited": data.get("edited"), "finished": data.get("finished"),
            "rows": len(rows), "picked": sum(1 for r in rows if r.get("picked")),
            "applied": sum(1 for r in rows if r.get("applied"))}


def body_of(event):
    body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode()
    return json.loads(body)


def handler(event, context):
    key = (event.get("headers") or {}).get(HEADER)
    if not key:
        return answer(401, "no key; log in with human login <key>")
    who = read(f"keys/{key}")
    if not who:
        return answer(401, "unknown key")
    user = who["user"]
    method = event["requestContext"]["http"]["method"]
    path = event.get("rawPath", "/")
    if method == "POST" and path == "/login":
        return answer(200, {"user": user})
    prefix = f"sessions/{user}/"
    if method == "GET" and path == "/sessions":
        index = read(prefix + "index.json") or []
        project = (event.get("queryStringParameters") or {}).get("project")
        if project:
            index = [s for s in index if s.get("project") == project]
        return answer(200, index)
    if not path.startswith("/sessions/"):
        return answer(404, "not found")
    sid = path[len("/sessions/"):]
    if not sid or "/" in sid:
        return answer(404, "not found")
    if method == "GET":
        data = read(f"{prefix}{sid}.json")
        return answer(200, data) if data else answer(404, f"no session {sid}")
    if method != "PUT":
        return answer(404, "not found")
    try:
        data = body_of(event)
    except ValueError:
        return answer(400, "the body is not JSON")
    if not isinstance(data, dict) or data.get("session_id") != sid:
        return answer(400, f"the body must be the session {sid}")
    write(f"{prefix}{sid}.json", data)
    index = [s for s in (read(prefix + "index.json") or []) if s["session_id"] != sid]
    index.append(summary(data))
    index.sort(key=lambda s: s["session_id"], reverse=True)
    write(prefix + "index.json", index)
    return answer(200, summary(data))
