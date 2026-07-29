import json
import os
import sys
from pathlib import Path

import boto3
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

IDEAS_PROMPT = """You are the front end of a compiler. The source is human text. Build the idea graph.

The root idea is:
{root}

Rules:
1. One idea is one node with a text and a source: the ids of the ideas that caused it.
2. First extract fragments: ideas whose text is copied verbatim from the text of their source.
3. Then expand: add the decisions a program needs, each sourced from the ideas that made it necessary.
4. Every idea has a non-empty source.
5. Together the ideas must decide the whole program. A separate compiler will see only the ideas, never the root text.

Return one JSON object only, no code fences:
{{"ideas": [{{"id": "I1", "text": "insertion sort", "source": ["I0"]}},
            {{"id": "I2", "text": "sort in ascending order", "source": ["I1"]}}]}}"""

CODE_PROMPT = """You are the back end of a compiler. The input is an idea graph. Compile it to Python.

Ideas:
{ideas}

Rules:
1. Write the smallest complete runnable Python program that satisfies every idea.
2. A code line is an idea whose text is one line of Python. Give each one an id and a source: the idea ids that caused it.
3. Return the lines in program order.

Return one JSON object only, no code fences:
{{"code": [{{"id": "P1", "text": "def f(items):", "source": ["I1"]}}]}}"""


def ask(prompt):
    client = boto3.client("bedrock-runtime", region_name=os.environ["AWS_REGION"])
    r = client.converse(
        modelId=os.environ["BEDROCK_MODEL_ID"],
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 8192},
    )
    assert r["stopReason"] == "end_turn", f'reply was cut: {r["stopReason"]}'
    raw = r["output"]["message"]["content"][0]["text"]
    return json.loads(raw[raw.index("{"):raw.rindex("}") + 1])


def main():
    path = Path(sys.argv[1])
    text = path.read_text().strip()
    assert text, f"{path.name} is empty"

    root = {"id": "I0", "text": text}
    ideas = [root] + ask(IDEAS_PROMPT.format(root=json.dumps(root)))["ideas"]
    by_id = {i["id"]: i for i in ideas}
    assert len(by_id) == len(ideas), "duplicate idea id"
    for i in ideas[1:]:
        assert i.get("source"), f'{i["id"]}: an idea needs a source'
        assert set(i["source"]) <= by_id.keys() - {i["id"]}, f'{i["id"]}: unknown source'
        if "I0" in i["source"]:
            assert i["text"] in text, f'{i["id"]}: "{i["text"]}" is not a verbatim fragment of the root'

    code = ask(CODE_PROMPT.format(ideas=json.dumps(ideas)))["code"]
    for c in code:
        if c["text"].strip():
            assert c.get("source"), f'no source: {c["text"]}'
            assert set(c["source"]) <= by_id.keys(), f'unknown source: {c["text"]}'

    path.with_suffix(".py").write_text("\n".join(c["text"] for c in code) + "\n")

    idea_rows = ",\n    ".join(json.dumps(i) for i in ideas)
    code_rows = ",\n    ".join(json.dumps(c) for c in code)
    path.with_suffix(".json").write_text(
        f'{{\n  "ideas": [\n    {idea_rows}\n  ],\n'
        f'  "code": [\n    {code_rows}\n  ]\n}}\n'
    )

    print(path.with_suffix(".py").name)
    for i in ideas[1:]:
        if "I0" not in i["source"]:
            print(f'{i["id"]}: {i["text"]}  <- {", ".join(i["source"])}')


if __name__ == "__main__":
    main()
