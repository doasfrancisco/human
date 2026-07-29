import json
import os
import sys
from pathlib import Path

import boto3
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

IDEAS_PROMPT = """You are the front end of a compiler. The source is human text. Extract the ideas a program needs.

Source text:
{text}

Rules:
1. One idea is one decision.
2. An idea the source states has an anchor: the exact words that caused it.
3. An idea the source does not state is a decision you make. It has no anchor. It has a source instead: the idea ids that made the decision necessary.
4. Every idea has an anchor or a source, never both, never neither.
5. Together the ideas must decide the whole program. A separate compiler will see only the ideas, never the source text.

Return one JSON object only, no code fences:
{{"ideas": [{{"id": "I1", "text": "sort the items", "anchor": "insertion sort"}},
            {{"id": "I2", "text": "sort in ascending order", "source": ["I1"]}}]}}"""

CODE_PROMPT = """You are the back end of a compiler. The input is a list of ideas. Compile them to Python.

Ideas:
{ideas}

Rules:
1. Write the smallest complete runnable Python program that satisfies every idea.
2. Every non-empty line lists its source: idea ids.

Return one JSON object only, no code fences:
{{"code": [{{"line": "def f(items):", "source": ["I1"]}}]}}"""


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

    ideas = ask(IDEAS_PROMPT.format(text=text))["ideas"]
    ids = {i["id"] for i in ideas}
    for i in ideas:
        anchored, sourced = "anchor" in i, bool(i.get("source"))
        assert anchored != sourced, f'{i["id"]}: an idea needs an anchor or a source, not both, not neither'
        if anchored:
            assert i["anchor"] in text, f'{i["id"]}: anchor "{i["anchor"]}" is not in the source'
        else:
            assert set(i["source"]) <= ids - {i["id"]}, f'{i["id"]}: unknown source'

    code = ask(CODE_PROMPT.format(ideas=json.dumps(ideas)))["code"]
    for c in code:
        if c["line"].strip():
            assert c.get("source"), f'no source: {c["line"]}'
            assert set(c["source"]) <= ids, f'unknown source: {c["line"]}'

    path.with_suffix(".py").write_text("\n".join(c["line"] for c in code) + "\n")

    idea_rows = ",\n    ".join(json.dumps(i) for i in ideas)
    code_rows = ",\n    ".join(json.dumps(c) for c in code)
    path.with_suffix(".json").write_text(
        f'{{\n  "root": {json.dumps(text)},\n'
        f'  "ideas": [\n    {idea_rows}\n  ],\n'
        f'  "code": [\n    {code_rows}\n  ]\n}}\n'
    )

    print(path.with_suffix(".py").name)
    for i in ideas:
        if "anchor" not in i:
            print(f'{i["id"]}: {i["text"]}  <- {", ".join(i["source"])}')


if __name__ == "__main__":
    main()
