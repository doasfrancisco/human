import json
import sys
from pathlib import Path

import boto3

KEY = "sessions.json"
LOCAL = Path(__file__).resolve().parent / KEY
s3 = boto3.client("s3")


def bucket_name():
    account = boto3.client("sts").get_caller_identity()["Account"]
    return f"human-training-{account}"


def read_json(bucket, key):
    try:
        return json.loads(s3.get_object(Bucket=bucket, Key=key)["Body"].read())
    except s3.exceptions.NoSuchKey:
        return None


def write_json(bucket, key, payload):
    s3.put_object(Bucket=bucket, Key=key, Body=json.dumps(payload, indent=2).encode(),
                  ContentType="application/json")


def create(bucket):
    if LOCAL.is_file():
        write_json(bucket, KEY, json.loads(LOCAL.read_text()))
        print(f"uploaded {LOCAL} to s3://{bucket}/{KEY}")
        return
    if read_json(bucket, KEY) is not None:
        print(f"s3://{bucket}/{KEY} already exists")
        return
    write_json(bucket, KEY, {"sessions": {}})
    print(f"created empty s3://{bucket}/{KEY}")


def get(bucket):
    data = read_json(bucket, KEY)
    if data is None:
        print(f"no s3://{bucket}/{KEY}")
        return
    print(json.dumps(data, indent=2))


def users_of(bucket):
    pages = s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix="sessions/", Delimiter="/")
    return [p["Prefix"].split("/")[1] for page in pages for p in page.get("CommonPrefixes", [])]


def indexes(bucket):
    for user in users_of(bucket):
        for summary in read_json(bucket, f"sessions/{user}/index.json") or []:
            yield user, summary


def pending(bucket):
    data = read_json(bucket, KEY) or {"sessions": {}}
    sessions = data["sessions"]
    for user, summary in indexes(bucket):
        sid = summary["session_id"]
        if sid in sessions or not summary.get("finished"):
            continue
        sessions[sid] = {"analyzed": False, "user": user}
    print(json.dumps(data, indent=2))


def mark(bucket, ids):
    data = read_json(bucket, KEY) or {"sessions": {}}
    for sid in ids:
        data["sessions"].setdefault(sid, {})["analyzed"] = True
    write_json(bucket, KEY, data)
    print(f"marked {len(ids)} analyzed in s3://{bucket}/{KEY}")


def main():
    args = sys.argv[1:]
    if not args or args[0] not in ("create", "get", "pending", "mark"):
        sys.exit("usage: feedback.py create | get | pending | mark <session id>...")
    bucket = bucket_name()
    if args[0] == "create":
        create(bucket)
    elif args[0] == "get":
        get(bucket)
    elif args[0] == "pending":
        pending(bucket)
    else:
        if len(args) < 2:
            sys.exit("mark takes one session id or more")
        mark(bucket, args[1:])


if __name__ == "__main__":
    main()
