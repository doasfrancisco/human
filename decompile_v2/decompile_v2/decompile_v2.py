import json
import os
import sys
from pathlib import Path

import boto3
from botocore.config import Config
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

PROMPT = """You are a decompiler. The input is one code file, one line per number. Describe what the code does, block by block.

File: {name}
{code}

Rules:
1. Split the file into a few sections. A section has a short lowercase name that says what kind of code it holds.
2. Split each section into blocks. A block is a run of lines that does one thing. One function is usually one block. A long function that does several things gets one block per stage.
3. Each block gets one text: one simple sentence that says what the block does. It never copies a code line.
4. Write the text in ASD-STE100 Simplified Technical English: short, active, plain words. No summary jargon.
5. The first word of a text is the name the block defines or uses, like the function name, the constant name, or the selector. A stage of a function starts with that function's name. Never start a text with "The".
6. A prompt or template string gets a text that says what it instructs, not how it is built.
7. "lines" holds [start, end] ranges, 1-based, both ends included. A block may hold more than one range.
8. Every non-blank line of the file belongs to exactly one block. No line belongs to two blocks. Blank lines belong to no block.
9. Ids are T01, T02, ... in file order.

Texts from a good map, in the exact voice to use:
"imports bring in the tools: text diffing, JSON, the environment, paths, the Bedrock client, and .env loading."
"load_dotenv reads the credentials from the .env file next to the script."
"write_json writes a list of rows to a file as JSON, one row per line."
"check verifies the ideas: no duplicate id, no collision with a code id, every source exists, and every code line reaches at least one idea."
"main's first stage reads the source file and gives each non-blank line an id like C7."
"main's fourth stage asks the model for ideas, checks the answer, and on a broken rule sends the answer and the error back for repair, up to three tries."

Return one JSON object only, no code fences. The keys are "file" and then one key per section, in file order:
{{"file": "{name}", "<section>": [{{"id": "T01", "text": "imports bring in the tools.", "lines": [[1, 9]]}}]}}"""


def ask(prompt):
    client = boto3.client(
        "bedrock-runtime",
        region_name=os.environ["AWS_REGION"],
        config=Config(connect_timeout=10, read_timeout=600),
    )
    r = client.converse(
        modelId=os.environ["BEDROCK_MODEL_ID"],
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 32000},
    )
    assert r["stopReason"] == "end_turn", f'reply was cut: {r["stopReason"]}'
    raw = r["output"]["message"]["content"][0]["text"]
    return json.loads(raw[raw.index("{"):raw.rindex("}") + 1])


def check(lines, m):
    secs = [k for k in m if k != "file"]
    assert secs, "no sections"
    texts = [t for k in secs for t in m[k]]
    ids = [t["id"] for t in texts]
    assert len(set(ids)) == len(ids), "duplicate text id"
    owner = {}
    for t in texts:
        assert t.get("text", "").strip(), f'{t["id"]}: empty text'
        assert t.get("lines"), f'{t["id"]}: a text needs lines'
        for a, b in t["lines"]:
            assert 1 <= a <= b <= len(lines), f'{t["id"]}: bad range {a}-{b}'
            for n in range(a, b + 1):
                assert n not in owner, f'line {n} belongs to {owner[n]} and {t["id"]}'
                owner[n] = t["id"]
    missing = [n for n in range(1, len(lines) + 1) if n not in owner and lines[n - 1].strip()]
    assert not missing, "these lines reach no text: " + ", ".join(map(str, missing))


def write_map(path, m):
    parts = [f'  "file": {json.dumps(m["file"])}']
    for k in m:
        if k == "file":
            continue
        rows = ",\n    ".join(json.dumps(t, ensure_ascii=False) for t in m[k])
        parts.append(f'  {json.dumps(k)}: [\n    {rows}\n  ]')
    path.write_text("{\n" + ",\n".join(parts) + "\n}\n", encoding="utf-8")


def main():
    path = Path(sys.argv[1])
    lines = path.read_text(encoding="utf-8").splitlines()
    assert any(l.strip() for l in lines), f"{path.name} is empty"
    code = "\n".join(f"{n}|{l}" for n, l in enumerate(lines, 1))
    base = PROMPT.format(name=path.name, code=code)
    note = ""
    for attempt in range(3):
        m = ask(base + note)
        m["file"] = path.name
        try:
            check(lines, m)
            break
        except (AssertionError, TypeError, ValueError, KeyError) as e:
            print(f"retry {attempt + 1}: {e}")
            note = (f"\n\nYour last answer:\n{json.dumps(m)}\n\n"
                    f"It broke a rule: {e}. Repair it and return the full corrected JSON.")
    else:
        sys.exit("no valid map after 3 tries")
    out = path.parent / "map.json"
    write_map(out, m)
    print(f"{sum(len(v) for k, v in m.items() if k != 'file')} texts -> {out}")


if __name__ == "__main__":
    main()
