"""fran++ v0.0.4 compiler: .human -> .context -> .py

Both stages call Claude via Amazon Bedrock.
Stage 1 (.human    -> .context): LLM extracts a JSON IR from freeform intent.
Stage 2 (.context  -> .py):      LLM generates Python from the JSON IR.

Setup:
    pip install boto3 python-dotenv
    # .env at project root must define AWS_BEARER_TOKEN_BEDROCK
"""

import difflib
import json
import os
import sys
from pathlib import Path

import boto3
from dotenv import load_dotenv

# .env lives at the repo root: ../../.env relative to this file.
ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(ENV_PATH)

MODEL_ID = "us.anthropic.claude-sonnet-4-6"


def _bedrock_client():
    return boto3.client(
        service_name="bedrock-runtime",
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        text = text[first_newline + 1:] if first_newline != -1 else ""
    if text.endswith("```"):
        text = text[: text.rfind("```")]
    return text.strip()


# ----- Stage 1: .human -> .context (LLM via Bedrock) -----

HUMAN_TO_CONTEXT_SYSTEM = """You are the .human -> .context compiler stage of fran++ v0.0.4.

Input: freeform text describing what a user wants a program to do.
Output: a single JSON object capturing the user's intent in a structured way. NO prose, NO markdown fences.

The JSON object should include keys that make the intent unambiguous to a downstream code generator. Common keys (use what fits, add more as needed):
- "kind":   category, e.g. "algorithm", "pipeline", "rule"
- "name":   canonical snake_case identifier
- "input":  what the program takes
- "output": what it returns
- "order":  "ascending" | "descending" if relevant
- "stable": boolean if relevant
- "logic":  ordered list of plain-English steps describing the algorithm

Make decisions deterministically. If the user wrote "insertion sort", default to ascending and stable. Always emit valid JSON, nothing else.
"""


def human_to_context(human_text: str) -> dict:
    response = _bedrock_client().converse(
        modelId=MODEL_ID,
        system=[{"text": HUMAN_TO_CONTEXT_SYSTEM}],
        messages=[
            {
                "role": "user",
                "content": [{"text": f"Human intent:\n{human_text.strip()}"}],
            }
        ],
        inferenceConfig={"temperature": 0, "maxTokens": 1024},
    )
    raw = response["output"]["message"]["content"][0]["text"]
    return json.loads(_strip_code_fences(raw))


# ----- Stage 2: .context -> .py (LLM via Bedrock) -----

CONTEXT_TO_PYTHON_SYSTEM = """You are the .context -> .py compiler stage of fran++ v0.0.4.

Input: a JSON IR describing a small program.
Output: Python source code that implements it. NO prose, NO markdown fences.

Rules:
- The very first line of the file must be: \"\"\"Compiled from .human via .context — DO NOT EDIT.\"\"\"
- Match the IR exactly. If `order` is `descending`, the comparison must reflect that.
- Include an `if __name__ == \"__main__\":` block that runs the function on a small example so `python file.py` prints something visible.
- Keep imports minimal — only what the algorithm strictly requires.
"""


def context_to_python(context: dict) -> str:
    response = _bedrock_client().converse(
        modelId=MODEL_ID,
        system=[{"text": CONTEXT_TO_PYTHON_SYSTEM}],
        messages=[
            {
                "role": "user",
                "content": [
                    {"text": f"IR:\n```json\n{json.dumps(context, indent=2)}\n```\n\nReturn the Python source."}
                ],
            }
        ],
        inferenceConfig={"temperature": 0, "maxTokens": 1024},
    )
    raw = response["output"]["message"]["content"][0]["text"]
    return _strip_code_fences(raw) + "\n"


# ----- Pipeline -----

def compile_human_file(path: Path):
    human_text = path.read_text(encoding="utf-8")

    context = human_to_context(human_text)
    context_path = path.with_suffix(".context")
    python_path = path.with_suffix(".py")

    new_context_text = json.dumps(context, indent=2) + "\n"

    if context_path.exists():
        old_context_text = context_path.read_text(encoding="utf-8")
        if old_context_text == new_context_text:
            print(f"No changes to {context_path.name}.")
        else:
            print(f"--- {context_path.name} will change ---")
            diff = difflib.unified_diff(
                old_context_text.splitlines(keepends=True),
                new_context_text.splitlines(keepends=True),
                fromfile=f"{context_path.name} (old)",
                tofile=f"{context_path.name} (new)",
            )
            sys.stdout.writelines(diff)
            print()
    else:
        print(f"Creating new {context_path.name}.")

    context_path.write_text(new_context_text, encoding="utf-8")

    python_code = context_to_python(context)
    python_path.write_text(python_code, encoding="utf-8")

    print(f"Compiled {path.name}")
    print(f"Wrote {context_path.name}")
    print(f"Wrote {python_path.name}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python compiler.py file.human")
        raise SystemExit(1)

    compile_human_file(Path(sys.argv[1]))
