from __future__ import annotations

import difflib
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import boto3
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


def load_nearest_env() -> None:
    """Load the first .env found at or above this file."""
    here = Path(__file__).resolve()
    for directory in [here.parent, *here.parents]:
        env_path = directory / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            return


load_nearest_env()

MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-6")
REGION = os.environ.get("AWS_REGION", "us-east-1")
WORKSPACE = Path(__file__).resolve().parent / "workspace"
PROGRAM_NAME = "program"
GRAPH_VERSION = 1
DEFAULT_HUMAN = "insertion sort"

app = FastAPI(title="fran++ v0.0.5 backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SaveRequest(BaseModel):
    human: str | None = None
    context: str | None = None
    python: str | None = None


class HumanRequest(BaseModel):
    human: str
    force: bool = False


class ContextRequest(BaseModel):
    context: str
    force: bool = False


class CheckoutRequest(BaseModel):
    kind: Literal["human", "context", "python"] = "human"
    hash: str


class DeleteRequest(BaseModel):
    kind: Literal["human", "context", "python"]
    hash: str


class BundleRequest(BaseModel):
    humanHash: str


class ActiveResponse(BaseModel):
    humanHash: str | None
    contextHash: str | None
    pythonHash: str | None


class StatusResponse(BaseModel):
    hasContext: bool
    hasPython: bool


class ContextProvenanceResponse(BaseModel):
    line: int | str
    status: str
    source: str
    text: str
    previousLine: int | str | None = None


class TreePythonResponse(BaseModel):
    hash: str
    preview: str
    active: bool
    createdAt: str
    updatedAt: str


class TreeContextResponse(BaseModel):
    hash: str
    preview: str
    active: bool
    python: TreePythonResponse | None = None
    pythons: list[TreePythonResponse] = []
    createdAt: str
    updatedAt: str


class TreeHumanResponse(BaseModel):
    hash: str
    preview: str
    active: bool
    context: TreeContextResponse | None = None
    contexts: list[TreeContextResponse] = []
    createdAt: str
    updatedAt: str


class FilesResponse(BaseModel):
    human: str
    context: str
    python: str
    active: ActiveResponse
    status: StatusResponse
    contextProvenance: list[ContextProvenanceResponse] = []
    tree: list[TreeHumanResponse]


class BundleResponse(BaseModel):
    human: str
    context: str
    python: str


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def preview(text: str, max_len: int = 72) -> str:
    first = next((line.strip() for line in text.splitlines() if line.strip()), "empty")
    if len(first) > max_len:
        return first[: max_len - 1] + "…"
    return first


def workspace_path(suffix: str) -> Path:
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    return WORKSPACE / f"{PROGRAM_NAME}.{suffix}"


def graph_path() -> Path:
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    return WORKSPACE / "graph.json"


def read_legacy_file(suffix: str, default: str = "") -> str:
    path = workspace_path(suffix)
    if not path.exists():
        return default
    return path.read_text(encoding="utf-8")


def write_file(suffix: str, text: str) -> None:
    workspace_path(suffix).write_text(text, encoding="utf-8")


def empty_graph() -> dict[str, Any]:
    return {
        "version": GRAPH_VERSION,
        "humans": {},
        "contexts": {},
        "pythons": {},
        "current_human_hash": None,
    }


def newest_human_hash(graph: dict[str, Any]) -> str | None:
    humans = list(graph.get("humans", {}).values())
    if not humans:
        return None
    newest = max(humans, key=lambda node: node.get("updated_at", node.get("created_at", "")))
    return newest.get("hash")


def read_graph() -> dict[str, Any]:
    path = graph_path()
    if not path.exists():
        graph = empty_graph()
        human = read_legacy_file("human", DEFAULT_HUMAN)
        ensure_human(graph, human)
        context = read_legacy_file("context")
        python = read_legacy_file("py")
        if context:
            ensure_context(graph, context, graph["current_human_hash"])
        if python and graph["current_human_hash"]:
            context_hash = graph["humans"][graph["current_human_hash"]].get("context_hash")
            if context_hash:
                ensure_python(graph, python, context_hash)
        write_graph(graph)
        materialize_current(graph)
        return graph

    try:
        graph = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"workspace graph is invalid JSON: {exc}") from exc

    graph.setdefault("version", GRAPH_VERSION)
    graph.setdefault("humans", {})
    graph.setdefault("contexts", {})
    graph.setdefault("pythons", {})
    graph.setdefault("current_human_hash", None)
    if graph["current_human_hash"] not in graph["humans"]:
        graph["current_human_hash"] = newest_human_hash(graph)
    for context in graph["contexts"].values():
        if "provenance" not in context:
            human_text = graph["humans"].get(context.get("human_hash"), {}).get("text", DEFAULT_HUMAN)
            context["provenance"] = context_provenance_from_scratch(human_text, context.get("text", ""))
    return graph


def write_graph(graph: dict[str, Any]) -> None:
    graph_path().write_text(json.dumps(graph, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def touch(node: dict[str, Any]) -> None:
    timestamp = now_iso()
    node.setdefault("created_at", timestamp)
    node["updated_at"] = timestamp


def context_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.strip()]


def strip_refinement_connector(text: str) -> str:
    words = text.strip().split()
    while words and words[0].lower() in {"of", "for", "with", "using", "on", "to", "about"}:
        words = words[1:]
    return " ".join(words).strip()


def human_refinement_phrase(previous_human: str, new_human: str) -> str:
    previous_human = previous_human.strip()
    new_human = new_human.strip()
    if previous_human and new_human.startswith(previous_human):
        return strip_refinement_connector(new_human[len(previous_human) :]) or new_human

    previous_words = previous_human.split()
    new_words = new_human.split()
    matcher = difflib.SequenceMatcher(a=previous_words, b=new_words)
    inserted: list[str] = []
    for tag, _i1, _i2, j1, j2 in matcher.get_opcodes():
        if tag in {"insert", "replace"}:
            inserted.extend(new_words[j1:j2])
    return strip_refinement_connector(" ".join(inserted)) or new_human


def context_provenance_from_scratch(human: str, context: str) -> list[dict[str, Any]]:
    source = f'human phrase "{human.strip()}"'
    return [
        {"line": index, "status": "added", "source": source, "text": line}
        for index, line in enumerate(context_lines(context), start=1)
    ]


def closest_previous_line(line: str, previous_lines: list[str]) -> tuple[int | None, float]:
    best_index: int | None = None
    best_ratio = 0.0
    for index, previous_line in enumerate(previous_lines, start=1):
        ratio = difflib.SequenceMatcher(a=previous_line, b=line).ratio()
        if ratio > best_ratio:
            best_index = index
            best_ratio = ratio
    return best_index, best_ratio


def context_provenance_from_update(
    previous_human: str,
    previous_context_node: dict[str, Any] | None,
    new_human: str,
    updated_context: str,
) -> list[dict[str, Any]]:
    previous_context = previous_context_node.get("text", "") if previous_context_node else ""
    previous_lines = context_lines(previous_context)
    previous_provenance = previous_context_node.get("provenance", []) if previous_context_node else []
    previous_by_text = {
        entry.get("text"): entry
        for entry in previous_provenance
        if isinstance(entry, dict) and entry.get("text")
    }
    refinement = human_refinement_phrase(previous_human, new_human)
    inherited_source = f'human phrase "{previous_human.strip()}"'
    added_source = f'human phrase "{refinement}"'

    provenance: list[dict[str, Any]] = []
    for index, line in enumerate(context_lines(updated_context), start=1):
        prior = previous_by_text.get(line)
        if prior:
            prior_status = prior.get("status", "inherited")
            provenance.append(
                {
                    "line": index,
                    "status": "manual" if prior_status == "manual" else "inherited",
                    "source": prior.get("source", inherited_source),
                    "text": line,
                    "previous_line": prior.get("line"),
                }
            )
        elif line in previous_lines:
            provenance.append({"line": index, "status": "inherited", "source": inherited_source, "text": line})
        elif previous_context:
            previous_line, similarity = closest_previous_line(line, previous_lines)
            if previous_line is not None and similarity >= 0.72:
                provenance.append(
                    {
                        "line": index,
                        "status": "updated",
                        "source": f'{inherited_source} refined by {added_source}',
                        "text": line,
                        "previous_line": previous_line,
                    }
                )
            else:
                provenance.append({"line": index, "status": "added", "source": added_source, "text": line})
        else:
            provenance.append({"line": index, "status": "added", "source": f'human phrase "{new_human.strip()}"', "text": line})
    return provenance


def context_provenance_from_manual_edit(previous_context_node: dict[str, Any] | None, edited_context: str) -> list[dict[str, Any]]:
    previous_context = previous_context_node.get("text", "") if previous_context_node else ""
    previous_lines = context_lines(previous_context)
    previous_provenance = previous_context_node.get("provenance", []) if previous_context_node else []
    previous_by_text = {
        entry.get("text"): entry
        for entry in previous_provenance
        if isinstance(entry, dict) and entry.get("text")
    }

    provenance: list[dict[str, Any]] = []
    for index, line in enumerate(context_lines(edited_context), start=1):
        prior = previous_by_text.get(line)
        if prior:
            prior_status = prior.get("status", "inherited")
            provenance.append(
                {
                    "line": index,
                    "status": "manual" if prior_status == "manual" else "inherited",
                    "source": prior.get("source", "previous context"),
                    "text": line,
                    "previous_line": prior.get("line"),
                }
            )
        elif line in previous_lines:
            provenance.append({"line": index, "status": "inherited", "source": "previous context", "text": line})
        else:
            provenance.append({"line": index, "status": "manual", "source": "manual edit in .context", "text": line})
    return provenance


def ensure_human(graph: dict[str, Any], text: str) -> str:
    hash_ = content_hash(text)
    humans = graph["humans"]
    if hash_ not in humans:
        timestamp = now_iso()
        humans[hash_] = {
            "hash": hash_,
            "text": text,
            "context_hash": None,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
    else:
        touch(humans[hash_])
    graph["current_human_hash"] = hash_
    return hash_


def ensure_context(
    graph: dict[str, Any],
    text: str,
    human_hash: str | None,
    provenance: list[dict[str, Any]] | None = None,
    parent_context_hash: str | None = None,
) -> str:
    if not human_hash:
        human_hash = ensure_human(graph, DEFAULT_HUMAN)

    hash_ = content_hash(text)
    contexts = graph["contexts"]
    if hash_ not in contexts:
        timestamp = now_iso()
        contexts[hash_] = {
            "hash": hash_,
            "text": text,
            "human_hash": human_hash,
            "python_hash": None,
            "provenance": provenance or context_provenance_from_scratch(graph["humans"][human_hash]["text"], text),
            "parent_context_hash": parent_context_hash,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
    else:
        touch(contexts[hash_])
        contexts[hash_].setdefault("human_hash", human_hash)
        if provenance is not None:
            contexts[hash_]["provenance"] = provenance
        contexts[hash_].setdefault("provenance", context_provenance_from_scratch(graph["humans"][human_hash]["text"], text))
        if parent_context_hash is not None:
            contexts[hash_]["parent_context_hash"] = parent_context_hash

    human_hashes = contexts[hash_].setdefault("human_hashes", [])
    if human_hash not in human_hashes:
        human_hashes.append(human_hash)

    graph["humans"][human_hash]["context_hash"] = hash_
    touch(graph["humans"][human_hash])
    return hash_


def ensure_python(graph: dict[str, Any], text: str, context_hash: str | None) -> str:
    if not context_hash:
        raise HTTPException(status_code=400, detail="Cannot save Python before a context exists")

    hash_ = content_hash(text)
    pythons = graph["pythons"]
    if hash_ not in pythons:
        timestamp = now_iso()
        pythons[hash_] = {
            "hash": hash_,
            "text": text,
            "context_hash": context_hash,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
    else:
        touch(pythons[hash_])
        pythons[hash_].setdefault("context_hash", context_hash)

    context_hashes = pythons[hash_].setdefault("context_hashes", [])
    if context_hash not in context_hashes:
        context_hashes.append(context_hash)

    graph["contexts"][context_hash]["python_hash"] = hash_
    touch(graph["contexts"][context_hash])
    return hash_


def python_belongs_to_context(python: dict[str, Any], context_hash: str) -> bool:
    return python.get("context_hash") == context_hash or context_hash in python.get("context_hashes", [])


def context_belongs_to_human(context: dict[str, Any], human_hash: str) -> bool:
    return context.get("human_hash") == human_hash or human_hash in context.get("human_hashes", [])


def delete_python_snapshot(graph: dict[str, Any], python_hash: str) -> None:
    if python_hash not in graph["pythons"]:
        raise HTTPException(status_code=404, detail="Python snapshot not found")

    graph["pythons"].pop(python_hash, None)
    for context in graph["contexts"].values():
        if context.get("python_hash") == python_hash:
            context["python_hash"] = None
            touch(context)


def delete_context_snapshot(graph: dict[str, Any], context_hash: str) -> None:
    context = graph["contexts"].get(context_hash)
    if not context:
        raise HTTPException(status_code=404, detail="Context snapshot not found")

    python_hashes = [
        python_hash
        for python_hash, python in list(graph["pythons"].items())
        if python_belongs_to_context(python, context_hash)
    ]
    for python_hash in python_hashes:
        delete_python_snapshot(graph, python_hash)

    graph["contexts"].pop(context_hash, None)
    for human in graph["humans"].values():
        if human.get("context_hash") == context_hash:
            human["context_hash"] = None
            touch(human)


def delete_human_snapshot(graph: dict[str, Any], human_hash: str) -> None:
    if human_hash not in graph["humans"]:
        raise HTTPException(status_code=404, detail="Human snapshot not found")

    context_hashes = [
        context_hash
        for context_hash, context in list(graph["contexts"].items())
        if context_belongs_to_human(context, human_hash)
    ]
    for context_hash in context_hashes:
        delete_context_snapshot(graph, context_hash)

    graph["humans"].pop(human_hash, None)
    if graph.get("current_human_hash") == human_hash:
        graph["current_human_hash"] = newest_human_hash(graph)


def delete_snapshot(graph: dict[str, Any], kind: Literal["human", "context", "python"], hash_: str) -> None:
    if kind == "human":
        delete_human_snapshot(graph, hash_)
    elif kind == "context":
        delete_context_snapshot(graph, hash_)
    else:
        delete_python_snapshot(graph, hash_)

    if graph.get("current_human_hash") not in graph["humans"]:
        graph["current_human_hash"] = newest_human_hash(graph)


def active_hashes(graph: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    human_hash = graph.get("current_human_hash")
    context_hash = None
    python_hash = None

    if human_hash and human_hash in graph["humans"]:
        context_hash = graph["humans"][human_hash].get("context_hash")
    if context_hash and context_hash in graph["contexts"]:
        python_hash = graph["contexts"][context_hash].get("python_hash")
    return human_hash, context_hash, python_hash


def active_texts(graph: dict[str, Any]) -> tuple[str, str, str]:
    human_hash, context_hash, python_hash = active_hashes(graph)
    human = graph["humans"].get(human_hash, {}).get("text", "") if human_hash else ""
    context = graph["contexts"].get(context_hash, {}).get("text", "") if context_hash else ""
    python = graph["pythons"].get(python_hash, {}).get("text", "") if python_hash else ""
    return human, context, python


def explain_text(graph: dict[str, Any]) -> str:
    human_hash, context_hash, python_hash = active_hashes(graph)
    human = graph["humans"].get(human_hash, {}) if human_hash else {}
    context = graph["contexts"].get(context_hash, {}) if context_hash else {}
    python = graph["pythons"].get(python_hash, {}) if python_hash else {}

    lines = [
        "# program.explain",
        "",
        f"active human: {human_hash or 'none'}",
        f"active context: {context_hash or 'none'}",
        f"active python: {python_hash or 'none'}",
        "",
        "## Human",
        human.get("text", DEFAULT_HUMAN),
        "",
        "## Context line provenance",
    ]

    provenance = context.get("provenance", [])
    if provenance:
        for entry in provenance:
            line_number = entry.get("line", "?")
            status = entry.get("status", "unknown")
            source = entry.get("source", "unknown source")
            text = entry.get("text", "")
            lines.append(f"C{line_number} [{status}] from {source}: {text}")
    elif context.get("text"):
        for index, line in enumerate(context_lines(context.get("text", "")), start=1):
            lines.append(f"C{index} [unknown]: {line}")
    else:
        lines.append("No context yet.")

    lines.extend(["", "## Python", python.get("text", "No Python yet.")])
    return "\n".join(lines).rstrip() + "\n"


def materialize_current(graph: dict[str, Any]) -> None:
    human, context, python = active_texts(graph)
    write_file("human", human)
    write_file("context", context)
    write_file("py", python)
    write_file("explain", explain_text(graph))


def python_tree_response(graph: dict[str, Any], python: dict[str, Any], active_python: str | None) -> TreePythonResponse:
    return TreePythonResponse(
        hash=python["hash"],
        preview=preview(python["text"]),
        active=python["hash"] == active_python,
        createdAt=python.get("created_at", ""),
        updatedAt=python.get("updated_at", ""),
    )


def context_tree_response(graph: dict[str, Any], context: dict[str, Any], active_context: str | None, active_python: str | None) -> TreeContextResponse:
    linked_pythons = [
        python
        for python in graph["pythons"].values()
        if context["hash"] == python.get("context_hash") or context["hash"] in python.get("context_hashes", [])
    ]
    linked_pythons.sort(key=lambda node: node.get("updated_at", ""), reverse=True)

    python_responses = [python_tree_response(graph, python, active_python) for python in linked_pythons]
    current_python = next((python for python in python_responses if python.hash == context.get("python_hash")), None)

    return TreeContextResponse(
        hash=context["hash"],
        preview=preview(context["text"]),
        active=context["hash"] == active_context,
        python=current_python,
        pythons=python_responses,
        createdAt=context.get("created_at", ""),
        updatedAt=context.get("updated_at", ""),
    )


def graph_tree(graph: dict[str, Any]) -> list[TreeHumanResponse]:
    active_human, active_context, active_python = active_hashes(graph)
    humans = sorted(
        graph["humans"].values(),
        key=lambda node: node.get("updated_at", ""),
        reverse=True,
    )
    tree: list[TreeHumanResponse] = []
    for human in humans:
        linked_contexts = [
            context
            for context in graph["contexts"].values()
            if human["hash"] == context.get("human_hash") or human["hash"] in context.get("human_hashes", [])
        ]
        linked_contexts.sort(key=lambda node: node.get("updated_at", ""), reverse=True)

        context_responses = [
            context_tree_response(graph, context, active_context, active_python) for context in linked_contexts
        ]
        current_context = next((context for context in context_responses if context.hash == human.get("context_hash")), None)

        tree.append(
            TreeHumanResponse(
                hash=human["hash"],
                preview=preview(human["text"]),
                active=human["hash"] == active_human,
                context=current_context,
                contexts=context_responses,
                createdAt=human.get("created_at", ""),
                updatedAt=human.get("updated_at", ""),
            )
        )
    return tree


def files_response(graph: dict[str, Any]) -> FilesResponse:
    human_hash, context_hash, python_hash = active_hashes(graph)
    human, context, python = active_texts(graph)
    provenance = graph["contexts"].get(context_hash, {}).get("provenance", []) if context_hash else []
    return FilesResponse(
        human=human,
        context=context,
        python=python,
        active=ActiveResponse(
            humanHash=human_hash,
            contextHash=context_hash,
            pythonHash=python_hash,
        ),
        status=StatusResponse(
            hasContext=context_hash is not None,
            hasPython=python_hash is not None,
        ),
        contextProvenance=[
            ContextProvenanceResponse(
                line=entry.get("line", "?"),
                status=entry.get("status", "unknown"),
                source=entry.get("source", "unknown source"),
                text=entry.get("text", ""),
                previousLine=entry.get("previous_line"),
            )
            for entry in provenance
            if isinstance(entry, dict)
        ],
        tree=graph_tree(graph),
    )


def bundle_for_human(graph: dict[str, Any], human_hash: str) -> BundleResponse:
    human = graph["humans"].get(human_hash)
    if not human:
        raise HTTPException(status_code=404, detail="Human snapshot not found")

    context_hash = human.get("context_hash")
    context_node = graph["contexts"].get(context_hash) if context_hash else None
    python_hash = context_node.get("python_hash") if context_node else None
    python_node = graph["pythons"].get(python_hash) if python_hash else None

    return BundleResponse(
        human=human.get("text", ""),
        context=context_node.get("text", "") if context_node else "",
        python=python_node.get("text", "") if python_node else "",
    )


def strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        text = text[first_newline + 1 :] if first_newline != -1 else ""
    if text.endswith("```"):
        text = text[: text.rfind("```")]
    return text.strip()


def bedrock_client():
    return boto3.client(service_name="bedrock-runtime", region_name=REGION)


def call_bedrock(system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> str:
    try:
        response = bedrock_client().converse(
            modelId=MODEL_ID,
            system=[{"text": system_prompt}],
            messages=[{"role": "user", "content": [{"text": user_prompt}]}],
            inferenceConfig={"temperature": 0, "maxTokens": max_tokens},
        )
    except Exception as exc:  # pragma: no cover - surfaces provider setup errors to UI
        raise HTTPException(status_code=502, detail=f"Bedrock call failed: {exc}") from exc

    return response["output"]["message"]["content"][0]["text"]


HUMAN_TO_CONTEXT_SYSTEM = """You are the .human -> .context compiler stage for fran++ v0.0.5.

Input: freeform human intent.
Output: expanded implementation context as plain text.

Rules:
- Do not output JSON.
- Do not output markdown.
- Do not output code.
- Write one meaningful implementation decision per line.
- Make hidden defaults explicit.
- The context should be detailed enough that another compiler stage can generate Python from it.
- Preserve the user's intent faithfully.
"""

UPDATE_CONTEXT_SYSTEM = """You are the incremental .human -> .context compiler stage for fran++ v0.0.5.

Input: previous human intent, previous context, and new human intent.
Output: updated implementation context as plain text.

Rules:
- Do not output JSON.
- Do not output markdown.
- Do not output code.
- Write one meaningful implementation decision per line.
- Preserve existing context unless the new human text explicitly changes it.
- Add only the smallest compatible refinement required by the new human text.
- If the new human text adds a concrete input or example, add/update demo/input lines; do not turn the algorithm into a step-by-step trace unless tracing is explicitly requested.
- Preserve function names, function contracts, algorithm choices, and defaults from the previous context unless explicitly contradicted.
- Remove or replace old context lines only when they conflict with the new human intent.
"""

CONTEXT_TO_PYTHON_SYSTEM = """You are the .context -> .py compiler stage for fran++ v0.0.5.

Input: free-text implementation context.
Output: Python source code only.

Rules:
- No prose.
- No markdown fences.
- The first line must be exactly: \"\"\"Compiled from .human via .context — DO NOT EDIT.\"\"\"
- Implement the context faithfully.
- Include a small if __name__ == \"__main__\": example when appropriate.
- Keep imports minimal.
"""


def human_to_context(human: str) -> str:
    raw = call_bedrock(
        HUMAN_TO_CONTEXT_SYSTEM,
        f"Human intent:\n{human.strip()}\n\nReturn only the .context text.",
    )
    return strip_code_fences(raw) + "\n"


def update_context(previous_human: str, previous_context: str, new_human: str) -> str:
    raw = call_bedrock(
        UPDATE_CONTEXT_SYSTEM,
        "\n".join(
            [
                "Previous human intent:",
                previous_human.strip(),
                "",
                "Previous .context:",
                previous_context.strip(),
                "",
                "New human intent:",
                new_human.strip(),
                "",
                "Return only the updated .context text.",
            ]
        ),
    )
    return strip_code_fences(raw) + "\n"


def context_to_python(context: str) -> str:
    raw = call_bedrock(
        CONTEXT_TO_PYTHON_SYSTEM,
        f"Context:\n{context.strip()}\n\nReturn only the Python source.",
    )
    return strip_code_fences(raw) + "\n"


@app.get("/")
def root():
    return {"name": "fran++ v0.0.5 backend", "docs": "/docs"}


@app.get("/api/health")
def health():
    return {"ok": True, "model": MODEL_ID, "region": REGION}


@app.get("/api/files", response_model=FilesResponse)
def get_files():
    graph = read_graph()
    materialize_current(graph)
    return files_response(graph)


@app.post("/api/bundle", response_model=BundleResponse)
def get_bundle(req: BundleRequest):
    graph = read_graph()
    return bundle_for_human(graph, req.humanHash)


@app.post("/api/save", response_model=FilesResponse)
def save_files(req: SaveRequest):
    graph = read_graph()

    if req.human is not None:
        ensure_human(graph, req.human)

    if req.context is not None:
        human_hash, previous_context_hash, _ = active_hashes(graph)
        previous_context_node = graph["contexts"].get(previous_context_hash) if previous_context_hash else None
        if req.context.strip():
            provenance = context_provenance_from_manual_edit(previous_context_node, req.context)
            ensure_context(graph, req.context, human_hash, provenance=provenance, parent_context_hash=previous_context_hash)
        elif human_hash:
            graph["humans"][human_hash]["context_hash"] = None
            touch(graph["humans"][human_hash])

    if req.python is not None:
        _, context_hash, _ = active_hashes(graph)
        if req.python.strip():
            ensure_python(graph, req.python, context_hash)
        elif context_hash:
            graph["contexts"][context_hash]["python_hash"] = None
            touch(graph["contexts"][context_hash])

    write_graph(graph)
    materialize_current(graph)
    return files_response(graph)


@app.post("/api/checkout", response_model=FilesResponse)
def checkout(req: CheckoutRequest):
    graph = read_graph()

    if req.kind == "human":
        if req.hash not in graph["humans"]:
            raise HTTPException(status_code=404, detail="Human snapshot not found")
        graph["current_human_hash"] = req.hash
    elif req.kind == "context":
        context = graph["contexts"].get(req.hash)
        if not context:
            raise HTTPException(status_code=404, detail="Context snapshot not found")
        graph["current_human_hash"] = context.get("human_hash")
        if graph["current_human_hash"]:
            graph["humans"][graph["current_human_hash"]]["context_hash"] = req.hash
    elif req.kind == "python":
        python = graph["pythons"].get(req.hash)
        if not python:
            raise HTTPException(status_code=404, detail="Python snapshot not found")
        context_hash = python.get("context_hash")
        context = graph["contexts"].get(context_hash)
        if not context:
            raise HTTPException(status_code=404, detail="Parent context snapshot not found")
        human_hash = context.get("human_hash")
        graph["current_human_hash"] = human_hash
        graph["humans"][human_hash]["context_hash"] = context_hash
        graph["contexts"][context_hash]["python_hash"] = req.hash

    write_graph(graph)
    materialize_current(graph)
    return files_response(graph)


@app.post("/api/delete", response_model=FilesResponse)
def delete(req: DeleteRequest):
    graph = read_graph()
    delete_snapshot(graph, req.kind, req.hash)
    write_graph(graph)
    materialize_current(graph)
    return files_response(graph)


@app.post("/api/human-to-context", response_model=FilesResponse)
def human_to_context_endpoint(req: HumanRequest):
    graph = read_graph()
    previous_human_hash, previous_context_hash, _ = active_hashes(graph)
    previous_human = graph["humans"].get(previous_human_hash, {}).get("text", "") if previous_human_hash else ""
    previous_context_node = graph["contexts"].get(previous_context_hash) if previous_context_hash else None
    previous_context = previous_context_node.get("text", "") if previous_context_node else ""

    human_hash = ensure_human(graph, req.human)
    human = graph["humans"][human_hash]

    if not human.get("context_hash") or req.force:
        if previous_context and previous_human_hash != human_hash:
            context = update_context(previous_human, previous_context, req.human)
            provenance = context_provenance_from_update(previous_human, previous_context_node, req.human, context)
            ensure_context(graph, context, human_hash, provenance=provenance, parent_context_hash=previous_context_hash)
        else:
            context = human_to_context(req.human)
            provenance = context_provenance_from_scratch(req.human, context)
            ensure_context(graph, context, human_hash, provenance=provenance)

    write_graph(graph)
    materialize_current(graph)
    return files_response(graph)


@app.post("/api/context-to-python", response_model=FilesResponse)
def context_to_python_endpoint(req: ContextRequest):
    graph = read_graph()
    human_hash, previous_context_hash, _ = active_hashes(graph)
    previous_context_node = graph["contexts"].get(previous_context_hash) if previous_context_hash else None
    provenance = context_provenance_from_manual_edit(previous_context_node, req.context)
    context_hash = ensure_context(
        graph,
        req.context,
        human_hash,
        provenance=provenance,
        parent_context_hash=previous_context_hash,
    )
    context = graph["contexts"][context_hash]

    if not context.get("python_hash") or req.force:
        python = context_to_python(req.context)
        ensure_python(graph, python, context_hash)

    write_graph(graph)
    materialize_current(graph)
    return files_response(graph)


@app.post("/api/compile-all", response_model=FilesResponse)
def compile_all(req: HumanRequest):
    graph = read_graph()
    previous_human_hash, previous_context_hash, _ = active_hashes(graph)
    previous_human = graph["humans"].get(previous_human_hash, {}).get("text", "") if previous_human_hash else ""
    previous_context_node = graph["contexts"].get(previous_context_hash) if previous_context_hash else None
    previous_context = previous_context_node.get("text", "") if previous_context_node else ""

    human_hash = ensure_human(graph, req.human)
    human = graph["humans"][human_hash]

    if not human.get("context_hash") or req.force:
        if previous_context and previous_human_hash != human_hash:
            context = update_context(previous_human, previous_context, req.human)
            provenance = context_provenance_from_update(previous_human, previous_context_node, req.human, context)
            context_hash = ensure_context(graph, context, human_hash, provenance=provenance, parent_context_hash=previous_context_hash)
        else:
            context = human_to_context(req.human)
            provenance = context_provenance_from_scratch(req.human, context)
            context_hash = ensure_context(graph, context, human_hash, provenance=provenance)
    else:
        context_hash = human["context_hash"]
        context = graph["contexts"][context_hash]["text"]

    context_node = graph["contexts"][context_hash]
    if not context_node.get("python_hash") or req.force:
        python = context_to_python(context)
        ensure_python(graph, python, context_hash)

    write_graph(graph)
    materialize_current(graph)
    return files_response(graph)
