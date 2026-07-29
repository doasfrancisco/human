import json
import os
import sys
from pathlib import Path

import boto3
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

PROMPT = """You are a compiler. The source is human text. Compile it to Python.

Source text:
{text}

Rules:
1. Extract ideas. One idea is one decision.
2. An idea the source states has an anchor: the exact words that caused it.
3. An idea the source does not state is a decision you make. It has no anchor. It has causes instead: the idea ids that made the decision necessary.
4. Every idea has an anchor or causes, never both, never neither.
5. Write the smallest complete runnable Python program. Every non-empty line lists its causes: idea ids.

Return one JSON object only, no code fences:
{{"ideas": [{{"id": "I1", "text": "sort the items", "anchor": "insertion sort"}},
            {{"id": "I2", "text": "sort in ascending order", "causes": ["I1"]}}],
 "code": [{{"line": "def f(items):", "causes": ["I1"]}}]}}"""


def main():
    path = Path(sys.argv[1])
    text = path.read_text().strip()
    assert text, f"{path.name} is empty"
    client = boto3.client("bedrock-runtime", region_name=os.environ["AWS_REGION"])
    r = client.converse(
        modelId=os.environ["BEDROCK_MODEL_ID"],
        messages=[{"role": "user", "content": [{"text": PROMPT.format(text=text)}]}],
        inferenceConfig={"maxTokens": 8192},
    )
    assert r["stopReason"] == "end_turn", f'reply was cut: {r["stopReason"]}'
    raw = r["output"]["message"]["content"][0]["text"]
    result = json.loads(raw[raw.index("{"):raw.rindex("}") + 1])

    ids = {i["id"] for i in result["ideas"]}
    for i in result["ideas"]:
        anchored, caused = "anchor" in i, bool(i.get("causes"))
        assert anchored != caused, f'{i["id"]}: an idea needs an anchor or causes, not both, not neither'
        if anchored:
            assert i["anchor"] in text, f'{i["id"]}: anchor "{i["anchor"]}" is not in the source'
        else:
            assert set(i["causes"]) <= ids - {i["id"]}, f'{i["id"]}: unknown cause'
    for c in result["code"]:
        if c["line"].strip():
            assert c.get("causes"), f'no cause: {c["line"]}'
            assert set(c["causes"]) <= ids, f'unknown cause: {c["line"]}'

    path.with_suffix(".py").write_text("\n".join(c["line"] for c in result["code"]) + "\n")

    ideas = ",\n    ".join(json.dumps(i) for i in result["ideas"])
    code = ",\n    ".join(json.dumps(c) for c in result["code"])
    path.with_suffix(".json").write_text(
        f'{{\n  "root": {json.dumps(text)},\n'
        f'  "ideas": [\n    {ideas}\n  ],\n'
        f'  "code": [\n    {code}\n  ]\n}}\n'
    )

    print(path.with_suffix(".py").name)
    for i in result["ideas"]:
        if "anchor" not in i:
            print(f'{i["id"]}: {i["text"]}  <- {", ".join(i["causes"])}')


if __name__ == "__main__":
    main()
