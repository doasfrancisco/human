import json
import os
import sys
from pathlib import Path

import boto3
from botocore.config import Config
from dotenv import load_dotenv

for p in (Path(__file__).parent / ".env", Path(__file__).parent.parent / "hand" / ".env"):
    load_dotenv(p)

DECISIONS_PROMPT = """You are a compiler. The source is human text. Extract the decisions.

The root is:
{root}

Rules:
1. A decision is one choice among real alternatives. It is one node with: text in the form "name: chosen, not rejected", chosen: the words of the winning option, by: who made the choice, and source: the ids of the decisions that force it.
2. by is "human" when the root text makes the choice. Then chosen is copied character for character from the root text. Do not reword it.
3. by is "compiler" when the text leaves the choice open and you make it. Name a real alternative you reject.
4. Every decision has a non-empty source. D0 is the root.
5. Together the decisions must decide the whole program. A separate compiler will see only the decisions, never the root text.

Return one JSON object only, no code fences:
{{"decisions": [{{"id": "D1", "text": "order: ascending, not descending", "chosen": "ascending", "by": "human", "source": ["D0"]}}]}}"""

CODE_PROMPT = """You are a compiler. The input is a list of decisions. Compile it to code. Assume Python or HTML.

Decisions:
{decisions}

Rules:
1. Write the smallest complete runnable program that satisfies every decision.
2. A code line has an id and a source: the ids of the decisions that caused it.
3. Return the lines in program order.
4. Return lang: the file suffix the program needs, py or html.

Return one JSON object only, no code fences:
{{"lang": "html", "code": [{{"id": "C1", "text": "<!DOCTYPE html>", "source": ["D1"]}}]}}"""


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


def write_json(path, key, rows):
    body = ",\n    ".join(json.dumps(r) for r in rows)
    path.write_text(f'{{\n  "{key}": [\n    {body}\n  ]\n}}\n', encoding="utf-8")


def validate(decisions, text):
    by_id = {d["id"]: d for d in decisions}
    assert len(by_id) == len(decisions), "duplicate decision id"
    for d in decisions[1:]:
        assert d.get("source"), f'{d["id"]}: a decision needs a source'
        assert set(d["source"]) <= by_id.keys() - {d["id"]}, f'{d["id"]}: unknown source'
        assert d.get("by") in ("human", "compiler"), f'{d["id"]}: by must be human or compiler'
        if d["by"] == "human":
            assert d.get("chosen") and d["chosen"] in text, \
                f'{d["id"]}: "{d.get("chosen")}" is not a verbatim fragment of the root'


def build_decisions(path):
    text = path.read_text(encoding="utf-8").strip()
    assert text, f"{path.name} is empty"

    root = {"id": "D0", "text": text}
    print("decisions...")
    base = DECISIONS_PROMPT.format(root=json.dumps(root))
    prompt, err = base, None
    for _ in range(3):
        decisions = [root] + ask(prompt)["decisions"]
        try:
            validate(decisions, text)
            err = None
            break
        except AssertionError as e:
            err = e
            print(f"rejected: {e}")
            prompt = f"{base}\n\nYour previous answer failed this check: {e}\nFix it and return the full corrected JSON."
    if err:
        raise err

    write_json(path.parent / "decisions.json", "decisions", decisions)
    print(f"{len(decisions)} decisions -> decisions.json")
    return decisions


def build_code(path, decisions):
    ids = {d["id"] for d in decisions}
    print("code...")
    r = ask(CODE_PROMPT.format(decisions=json.dumps(decisions)))
    code = r["code"]
    for c in code:
        if c["text"].strip():
            assert c.get("source"), f'no source: {c["text"]}'
            assert set(c["source"]) <= ids, f'unknown source: {c["text"]}'

    out = path.with_suffix("." + r["lang"])
    out.write_text("\n".join(c["text"] for c in code) + "\n", encoding="utf-8")
    write_json(path.parent / "code.json", "code", code)
    print(f"{len(code)} lines -> {out.name}")


def main():
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    path = Path(next(a for a in sys.argv[1:] if not a.startswith("--")))

    if "--code" in flags:
        decisions = json.loads((path.parent / "decisions.json").read_text(encoding="utf-8"))["decisions"]
    else:
        decisions = build_decisions(path)

    if "--decisions" not in flags:
        build_code(path, decisions)


if __name__ == "__main__":
    main()
