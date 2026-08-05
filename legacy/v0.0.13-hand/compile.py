import json
import os
import sys
from pathlib import Path

import boto3
from botocore.config import Config
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

IDEAS_PROMPT = """You are compiler. The source is human text. Build the idea graph.

The root idea is:
{root}

Rules:
1. One idea is one node with a text and a source: the ids of the ideas that caused it.
2. First extract fragments: ideas whose text is copied character for character from the text of their source. Do not reword, shorten or merge the words.
3. Then expand: add the decisions a program needs, each sourced from the ideas that made it necessary.
4. Every idea has a non-empty source.
5. Together the ideas must decide the whole program. A separate compiler will see only the ideas, never the root text.

Return one JSON object only, no code fences:
{{"ideas": [{{"id": "I1", "text": "insertion sort", "source": ["I0"]}},
            {{"id": "I2", "text": "sort in ascending order", "source": ["I1"]}}]}}"""

CODE_PROMPT = """You are a compiler. The input is an idea graph. Compile it to code. Assume Python or HTML

Ideas:
{ideas}

Rules:
1. Write the smallest complete runnable program that satisfies every idea.
2. A code line is an idea whose text is one line of code. Give each one an id and a source: the idea ids that caused it.
3. Return the lines in program order.
4. Return lang: the file suffix the program needs, py or html.

Return one JSON object only, no code fences:
{{"lang": "py", "code": [{{"id": "P1", "text": "def f(items):", "source": ["I1"]}}]}}"""


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


def build_ideas(path):
    text = path.read_text(encoding="utf-8").strip()
    assert text, f"{path.name} is empty"

    root = {"id": "I0", "text": text}
    print("ideas...")
    ideas = [root] + ask(IDEAS_PROMPT.format(root=json.dumps(root)))["ideas"]
    by_id = {i["id"]: i for i in ideas}
    assert len(by_id) == len(ideas), "duplicate idea id"
    for i in ideas[1:]:
        assert i.get("source"), f'{i["id"]}: an idea needs a source'
        assert set(i["source"]) <= by_id.keys() - {i["id"]}, f'{i["id"]}: unknown source'
        if "I0" in i["source"]:
            assert i["text"] in text, f'{i["id"]}: "{i["text"]}" is not a verbatim fragment of the root'

    idea_rows = ",\n    ".join(json.dumps(i) for i in ideas)
    (path.parent / "ideas.json").write_text(f'{{\n  "ideas": [\n    {idea_rows}\n  ]\n}}\n', encoding="utf-8")
    print(f"{len(ideas)} ideas -> ideas.json")
    return ideas


def build_code(path, ideas):
    ids = {i["id"] for i in ideas}
    print("code...")
    r = ask(CODE_PROMPT.format(ideas=json.dumps(ideas)))
    code = r["code"]
    for c in code:
        if c["text"].strip():
            assert c.get("source"), f'no source: {c["text"]}'
            assert set(c["source"]) <= ids, f'unknown source: {c["text"]}'

    out = path.with_suffix("." + r["lang"])
    out.write_text("\n".join(c["text"] for c in code) + "\n", encoding="utf-8")

    code_rows = ",\n    ".join(json.dumps(c) for c in code)
    (path.parent / "code.json").write_text(f'{{\n  "code": [\n    {code_rows}\n  ]\n}}\n', encoding="utf-8")
    print(f"{len(code)} lines -> {out.name}")


def main():
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    path = Path(next(a for a in sys.argv[1:] if not a.startswith("--")))

    if "--code" in flags:
        ideas = json.loads((path.parent / "ideas.json").read_text(encoding="utf-8"))["ideas"]
    else:
        ideas = build_ideas(path)

    if "--ideas" not in flags:
        build_code(path, ideas)

if __name__ == "__main__":
    main()
