import difflib
import json
import os
import sys
from pathlib import Path

import boto3
from botocore.config import Config
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

IDEAS_PROMPT = """You are a decompiler. The input is code, one line per id. Understand the program, then extract the ideas behind it, layer by layer.

Code lines:
{code}

Rules:
1. An idea is a decision the programmer made. A different decision would give different code.
2. Work bottom-up. First write the low ideas straight from the code; their sources are code line ids.
3. Then abstract. When lower ideas are together one simpler decision, add a higher idea whose source is those idea ids. Keep folding until no idea can be made simpler.
4. The top ideas alone must say what the program is, in the fewest and simplest words. All the detail stays reachable below them.
5. Idea text is short: a compressed phrase, not a sentence. It may name identifiers from the code, but never copies a code line.
6. Every code line id must appear in the source of at least one idea.
7. Every idea has a non-empty source.
8. When the code behind an idea calls or reads what an other idea decides, that other idea's id also goes into the source.
{old}
Return one JSON object only, no code fences:
{{"ideas": [{{"id": "I1", "text": "ascending order", "source": ["C5"]}}]}}"""

OLD_RULES = """
Ideas from an earlier version of this code:
{ideas}

9. If an earlier idea is still true, keep its id. Reword its text only to satisfy rule 5; the meaning must not change.
10. If an earlier idea is no longer true, drop it.
11. A new idea gets an id no earlier idea used.
"""


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


def load(path, key):
    return json.loads(path.read_text(encoding="utf-8"))[key] if path.exists() else None


def snapshot(folder):
    hist = folder / "history"
    hist.mkdir(exist_ok=True)
    v = hist / str(len(list(hist.iterdir())) + 1)
    v.mkdir()
    for name in ("code.json", "ideas.json", "diff.json"):
        if (folder / name).exists():
            (v / name).write_bytes((folder / name).read_bytes())
    return v


def check(code, ideas):
    code_ids = {c["id"] for c in code}
    by_id = {i["id"]: i for i in ideas}
    assert len(by_id) == len(ideas), "duplicate idea id"
    assert not code_ids & by_id.keys(), "idea id collides with a code id"
    for i in ideas:
        assert i.get("source"), f'{i["id"]}: an idea needs a source'
        assert set(i["source"]) <= (code_ids | by_id.keys()) - {i["id"]}, f'{i["id"]}: unknown source'
    used = {s for i in ideas for s in i["source"]}
    missing = [c for c in code if c["id"] not in used]
    assert not missing, "these lines reach no idea: " + ", ".join(f'{c["id"]} {c["text"].strip()}' for c in missing)


def diff(old_code, old_ideas, code, ideas):
    sm = difflib.SequenceMatcher(None, [c["text"] for c in old_code], [c["text"] for c in code])
    idmap = {old_code[a + k]["id"]: code[b + k]["id"] for a, b, n in sm.get_matching_blocks() for k in range(n)}
    old = {i["id"]: i for i in old_ideas}
    new = {i["id"]: i for i in ideas}
    moved = [{"id": k, "from": sorted({idmap.get(s, s) for s in old[k]["source"]}), "to": sorted(set(new[k]["source"]))}
             for k in sorted(old.keys() & new.keys())
             if {idmap.get(s, s) for s in old[k]["source"]} != set(new[k]["source"])]
    return {
        "added": sorted(new.keys() - old.keys()),
        "removed": [old[k] for k in sorted(old.keys() - new.keys())],
        "moved": moved,
        "reworded": [{"id": k, "from": old[k]["text"], "to": new[k]["text"]}
                     for k in sorted(old.keys() & new.keys())
                     if old[k]["text"] != new[k]["text"]],
    }


def main():
    path = Path(sys.argv[1])
    rows, n = [], 0
    for l in path.read_text(encoding="utf-8").splitlines():
        n += 1 if l.strip() else 0
        rows.append({"id": f"C{n}", "text": l} if l.strip() else {"text": l})
    code = [r for r in rows if "id" in r]
    assert code, f"{path.name} is empty"

    old_code = load(path.parent / "code.json", "code")
    old_code = [c for c in old_code if "id" in c] if old_code else None
    old_ideas = load(path.parent / "ideas.json", "ideas")
    old = ""
    if old_ideas:
        old = OLD_RULES.format(ideas=json.dumps([{"id": i["id"], "text": i["text"]} for i in old_ideas]))

    write_json(path.parent / "code.json", "code", rows)
    print(f"{len(code)} lines -> code.json")

    print("ideas...")
    base = IDEAS_PROMPT.format(code=json.dumps(code), old=old)
    note = ""
    for attempt in range(3):
        ideas = ask(base + note)["ideas"]
        try:
            check(code, ideas)
            break
        except AssertionError as e:
            print(f"retry {attempt + 1}: {e}")
            note = (f"\n\nYour last answer:\n{json.dumps({'ideas': ideas})}\n\n"
                    f"It broke a rule: {e}. Repair it and return the full corrected JSON.")
    else:
        sys.exit("no valid ideas after 3 tries")
    write_json(path.parent / "ideas.json", "ideas", ideas)
    print(f"{len(ideas)} ideas -> ideas.json")

    if old_code and old_ideas:
        d = diff(old_code, old_ideas, code, ideas)
        (path.parent / "diff.json").write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8")
        print(f'{len(d["added"])} added, {len(d["removed"])} removed, {len(d["moved"])} moved -> diff.json')
    elif (path.parent / "diff.json").exists():
        (path.parent / "diff.json").unlink()

    v = snapshot(path.parent)
    print(f"version -> {v.relative_to(path.parent)}")


if __name__ == "__main__":
    main()
