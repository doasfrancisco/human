import ast
import os
import re
import sys
from pathlib import Path

import boto3
from botocore.config import Config
from dotenv import load_dotenv

HERE = Path(__file__).parent
for p in (HERE / ".env", HERE.parent / ".env", HERE.parent / "hand" / ".env"):
    if p.exists():
        load_dotenv(p)
        break

PROMPT = """You are a compiler. The language has one axiom: refine, text -> text.

The text:
<text>
{text}
</text>

Laws:
1. Conservation: every behavior the text demands, the refined text still demands. Never reverse a decision.
2. Progress: decide at least one choice the text leaves open. Move one level down: intent, then interface, then algorithm, then code.
3. Fixed point: when no choice is open, the text is one complete runnable Python program and nothing else.

Apply refine once. Return only the refined text. No fences, no commentary."""

MAX_LEVELS = 8


def ask(text):
    client = boto3.client(
        "bedrock-runtime",
        region_name=os.environ["AWS_REGION"],
        config=Config(connect_timeout=10, read_timeout=600),
    )
    r = client.converse(
        modelId=os.environ["BEDROCK_MODEL_ID"],
        messages=[{"role": "user", "content": [{"text": PROMPT.format(text=text)}]}],
        inferenceConfig={"maxTokens": 32000},
    )
    assert r["stopReason"] == "end_turn", f'reply was cut: {r["stopReason"]}'
    out = r["output"]["message"]["content"][0]["text"].strip()
    m = re.fullmatch(r"```\w*\n(.*)\n```", out, re.S)
    return m.group(1).strip() if m else out


def chain(folder):
    files = [p for p in folder.iterdir() if p.suffix in (".human", ".py") and p.stem.isdigit()]
    assert files, f"{folder} has no 0.human"
    return sorted(files, key=lambda p: int(p.stem))


def body(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    return "\n".join(l for l in lines if not l.strip().startswith("assert:")).strip()


def asserts(files):
    out = []
    for p in files:
        for l in p.read_text(encoding="utf-8").splitlines():
            if l.strip().startswith("assert:"):
                out.append((p.name, l.strip()[len("assert:"):].strip()))
    return out


def is_code(text):
    try:
        ast.parse(text)
        return True
    except SyntaxError:
        return False


def step(folder):
    last = chain(folder)[-1]
    assert last.suffix == ".human", f"{last.name} is the fixed point"
    text = body(last)
    out = ask(text)
    assert out != text, f"{last.name}: the step decided nothing"
    dst = folder / f"{int(last.stem) + 1}.{'py' if is_code(out) else 'human'}"
    dst.write_text(out + "\n", encoding="utf-8")
    print(f"{last.name} -> {dst.name}")
    return dst


def build(folder):
    while chain(folder)[-1].suffix == ".human":
        assert len(chain(folder)) < MAX_LEVELS, f"no fixed point after {MAX_LEVELS} levels"
        step(folder)
    print(f"fixed point: {chain(folder)[-1].name}")


def check(folder):
    files = chain(folder)
    for a, b in zip(files, files[1:]):
        assert body(a) != body(b), f"{b.name}: no progress over {a.name}"
    last = files[-1]
    assert last.suffix == ".py", "the chain does not end in code"
    code = last.read_text(encoding="utf-8")
    ast.parse(code)

    def raises(exc, fn, *a, **k):
        try:
            fn(*a, **k)
        except exc:
            return True
        except Exception:
            return False
        return False

    ns = {"__name__": "refine_check", "raises": raises}
    exec(compile(code, str(last), "exec"), ns)
    tests = asserts(files)
    green = 0
    for name, expr in tests:
        try:
            ok = bool(eval(expr, ns))
            print(f"{'green' if ok else 'red  '} {name}: {expr}")
        except Exception as e:
            ok = False
            print(f"red   {name}: {expr}  ({type(e).__name__}: {e})")
        green += ok
    print(f"{green}/{len(tests)} asserts green")
    assert green == len(tests), "conservation failed"


def main():
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    folder = Path(next(a for a in sys.argv[1:] if not a.startswith("--")))
    if "--step" in flags:
        step(folder)
    elif "--check" in flags:
        check(folder)
    else:
        build(folder)


if __name__ == "__main__":
    main()
