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
2. An idea with origin "user" comes from the source. Its anchor is the exact words that caused it.
3. An idea with origin "compiler" is a decision the program needs but the source does not make. You make it. It has no anchor.
4. Write the smallest complete runnable Python program. Every non-empty line lists its sources: idea ids.

Return one JSON object only, no code fences:
{{"ideas": [{{"id": "I1", "text": "sort the items", "anchor": "insertion sort", "origin": "user"}},
            {{"id": "I2", "text": "sort in ascending order", "origin": "compiler"}}],
 "code": [{{"line": "def f(items):", "sources": ["I1"]}}]}}"""


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
        if i["origin"] == "user":
            assert i.get("anchor") in text, f'{i["id"]}: anchor is not in the source'
        else:
            assert not i.get("anchor"), f'{i["id"]}: a compiler idea must not have an anchor'
    for c in result["code"]:
        if c["line"].strip():
            assert c["sources"], f'no source: {c["line"]}'
            assert set(c["sources"]) <= ids, f'unknown source: {c["line"]}'

    path.with_suffix(".py").write_text("\n".join(c["line"] for c in result["code"]) + "\n")

    tree = [f'root: "{text}"']
    for i in result["ideas"]:
        origin = f'<- "{i["anchor"]}"' if i["origin"] == "user" else "(compiler)"
        tree.append(f'{i["id"]}: {i["text"]}  {origin}')
    for c in result["code"]:
        if c["line"].strip():
            tree.append(f'{c["line"]}  <- {", ".join(c["sources"])}')
    path.with_suffix(".ideas").write_text("\n".join(tree) + "\n")

    print(path.with_suffix(".py").name)
    for i in result["ideas"]:
        if i["origin"] == "compiler":
            print(f'{i["id"]}: {i["text"]}  (compiler)')


if __name__ == "__main__":
    main()
