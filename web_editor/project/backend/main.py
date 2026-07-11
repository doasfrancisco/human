from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import boto3
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from attribution import (
    SPLIT_CODE_EXTENSIONS,
    numbered_context_lines,
    parse_split_sections,
    split_section_headers,
)


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
NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_\-. ]*")
GRAPH_VERSION = 1
PROJECTS_VERSION = 1
DEFAULT_HUMAN = "insertion sort"
DEFAULT_PROJECT_NAME = "untitled"
LANGUAGES = {
    "python": "py",
    "typescript": "ts",
    "tsx": "tsx",
    "javascript": "js",
    "jsx": "jsx",
    "css": "css",
    "json": "json",
    "html": "html",
    "markdown": "md",
    "toml": "toml",
    "yaml": "yaml",
    "text": "txt",
    "svg": "svg",
}
LANGUAGE_LABELS = {
    "python": "Python",
    "typescript": "TypeScript",
    "tsx": "TSX",
    "javascript": "JavaScript",
    "jsx": "JSX",
    "css": "CSS",
    "json": "JSON",
    "html": "HTML",
    "markdown": "Markdown",
    "toml": "TOML",
    "yaml": "YAML",
    "text": "plain text",
    "svg": "SVG",
}
EXTENSION_LANGUAGES = {extension: language for language, extension in LANGUAGES.items()} | {
    "mjs": "javascript",
    "cjs": "javascript",
    "yml": "yaml",
}
REPO_ROOT = Path(__file__).resolve().parents[2]
FS_TREE_MAX_DEPTH = 12
FS_SKIP_DIRS = {
    "node_modules",
    ".venv",
    ".git",
    "__pycache__",
    ".next",
    ".playwright-mcp",
    ".mypy_cache",
    ".pytest_cache",
    "dist",
    "build",
    ".turbo",
}
FOLDER_PICK_TIMEOUT_SECONDS = 300
FOLDER_PICK_SCRIPT = (
    "Add-Type -AssemblyName System.Windows.Forms; "
    "$owner = New-Object System.Windows.Forms.Form; "
    "$owner.TopMost = $true; "
    "$dialog = New-Object System.Windows.Forms.FolderBrowserDialog; "
    "$dialog.Description = 'Select a folder to open in fran++'; "
    "if ($dialog.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK) "
    "{ [Console]::Out.Write($dialog.SelectedPath) }"
)

app = FastAPI(title="fran++ v0.0.5 backend")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SaveRequest(BaseModel):
    human: str | None = None
    context: str | None = None
    python: str | None = None
    name: str = PROGRAM_NAME


class SaveUnitRequest(BaseModel):
    target: str
    code: str
    name: str = PROGRAM_NAME


class AdoptRequest(BaseModel):
    name: str = PROGRAM_NAME


class HumanRequest(BaseModel):
    human: str
    force: bool = False
    name: str = PROGRAM_NAME
    language: str = "python"


class ContextRequest(BaseModel):
    context: str
    force: bool = False
    name: str = PROGRAM_NAME
    language: str = "python"


class RewordRequest(BaseModel):
    human: str
    name: str = PROGRAM_NAME
    oldPhrase: str | None = None
    newPhrase: str | None = None


class CheckoutRequest(BaseModel):
    kind: Literal["human", "context", "python"] = "human"
    hash: str
    name: str = PROGRAM_NAME


class DeleteRequest(BaseModel):
    kind: Literal["human", "context", "python"]
    hash: str
    name: str = PROGRAM_NAME


class BundleRequest(BaseModel):
    humanHash: str
    name: str = PROGRAM_NAME


class ProjectCreateRequest(BaseModel):
    name: str


class ProjectSelectRequest(BaseModel):
    id: str
    name: str = PROGRAM_NAME


class ProjectRenameRequest(BaseModel):
    id: str
    name: str


class ProjectResponse(BaseModel):
    id: str
    name: str
    created_at: str
    updated_at: str
    active: bool


class ProjectsResponse(BaseModel):
    projects: list[ProjectResponse]


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
    target: str | None = None
    contextLine: int | str | None = None
    phraseId: str | None = None


class PhraseResponse(BaseModel):
    text: str
    line: int


class TreePythonResponse(BaseModel):
    hash: str
    preview: str
    active: bool
    target: str | None = None
    createdAt: str
    updatedAt: str


class TreeContextResponse(BaseModel):
    hash: str
    preview: str
    active: bool
    role: Literal["leaf", "split", "direct"] = "leaf"
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


class UnitResponse(BaseModel):
    target: str
    python: str
    hash: str


class FilesResponse(BaseModel):
    name: str
    human: str
    context: str
    python: str
    active: ActiveResponse
    status: StatusResponse
    contextRole: Literal["leaf", "split", "direct"] | None = None
    contextProvenance: list[ContextProvenanceResponse] = []
    pythonProvenance: list[ContextProvenanceResponse] = []
    units: list[UnitResponse] = []
    phrases: dict[str, PhraseResponse] = {}
    tree: list[TreeHumanResponse]
    seeded: bool = False


class BundleResponse(BaseModel):
    human: str
    context: str
    python: str


class FsNodeResponse(BaseModel):
    name: str
    path: str
    type: Literal["dir", "file"]
    children: list[FsNodeResponse] = []


class PickFolderResponse(BaseModel):
    path: str | None


class FsReadResponse(BaseModel):
    path: str
    name: str
    content: str


class FsWriteRequest(BaseModel):
    path: str
    content: str


class FsWriteResponse(BaseModel):
    ok: bool
    path: str


class FsCreateRequest(BaseModel):
    parent: str
    name: str
    kind: Literal["file", "dir"]


class FsCreateResponse(BaseModel):
    name: str
    path: str
    type: Literal["dir", "file"]


class FsDeleteRequest(BaseModel):
    path: str


class FsDeleteResponse(BaseModel):
    ok: bool


def normalize_name(name: str | None) -> str:
    name = (name or "").strip()
    if not name:
        return PROGRAM_NAME
    if "\\" in name or any(segment == ".." or not NAME_RE.fullmatch(segment) for segment in name.split("/")):
        raise HTTPException(status_code=400, detail=f"Invalid program name: {name!r}")
    return name


def normalize_language(language: str | None) -> str:
    language = (language or "").strip().lower()
    if not language:
        return "python"
    if language in LANGUAGES:
        return language
    if language in EXTENSION_LANGUAGES:
        return EXTENSION_LANGUAGES[language]
    raise HTTPException(status_code=400, detail=f"Unsupported language: {language!r}")


def language_label(language: str) -> str:
    return LANGUAGE_LABELS.get(language, language)


def language_extension(language: str) -> str:
    return LANGUAGES.get(language, "py")


def target_extension(target: str) -> str | None:
    leaf = target.rsplit("/", 1)[-1]
    if "." not in leaf:
        return None
    return leaf.rsplit(".", 1)[1].lower()


def target_language(target: str) -> str:
    return EXTENSION_LANGUAGES.get(target_extension(target) or "", "python")


def node_language(node: dict[str, Any] | None) -> str:
    language = (node or {}).get("language")
    return language if language in LANGUAGES else "python"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def preview(text: str, max_len: int = 72) -> str:
    first = next((line.strip() for line in text.splitlines() if line.strip()), "empty")
    if len(first) > max_len:
        return first[: max_len - 1] + "…"
    return first


def projects_index_path() -> Path:
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    return WORKSPACE / "projects.json"


def project_dir(project_id: str) -> Path:
    return WORKSPACE / "projects" / project_id


def empty_projects_index() -> dict[str, Any]:
    return {"version": PROJECTS_VERSION, "active_id": None, "projects": []}


def write_projects_index(index: dict[str, Any]) -> None:
    projects_index_path().write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_projects_index() -> dict[str, Any]:
    path = projects_index_path()
    if not path.exists():
        index = empty_projects_index()
        write_projects_index(index)
        return index

    try:
        index = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"projects index is invalid JSON: {exc}") from exc

    index.setdefault("version", PROJECTS_VERSION)
    index.setdefault("projects", [])
    index.setdefault("active_id", None)
    ids = {project["id"] for project in index["projects"]}
    if index["active_id"] not in ids:
        index["active_id"] = index["projects"][0]["id"] if index["projects"] else None
        write_projects_index(index)
    return index


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "project"


def new_project_id(index: dict[str, Any], name: str) -> str:
    base = f"{slugify(name)}-{content_hash(name)[:8]}"
    existing = {project["id"] for project in index["projects"]}
    if base not in existing:
        return base
    counter = 2
    while f"{base}-{counter}" in existing:
        counter += 1
    return f"{base}-{counter}"


def create_project(index: dict[str, Any], name: str) -> dict[str, Any]:
    project_id = new_project_id(index, name)
    timestamp = now_iso()
    project = {
        "id": project_id,
        "name": name.strip() or DEFAULT_PROJECT_NAME,
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    index["projects"].append(project)
    index["active_id"] = project_id
    directory = project_dir(project_id)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "graph.json").write_text(
        json.dumps(empty_graph(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    write_projects_index(index)
    return project


def active_project_id() -> str:
    index = read_projects_index()
    if index["active_id"] is None:
        return create_project(index, DEFAULT_PROJECT_NAME)["id"]
    return index["active_id"]


def touch_active_project() -> None:
    index = read_projects_index()
    for project in index["projects"]:
        if project["id"] == index["active_id"]:
            project["updated_at"] = now_iso()
            write_projects_index(index)
            return


def projects_response(index: dict[str, Any]) -> ProjectsResponse:
    return ProjectsResponse(
        projects=[
            ProjectResponse(
                id=project["id"],
                name=project["name"],
                created_at=project.get("created_at", ""),
                updated_at=project.get("updated_at", ""),
                active=project["id"] == index["active_id"],
            )
            for project in index["projects"]
        ]
    )


def active_workspace() -> Path:
    directory = project_dir(active_project_id())
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def workspace_path(name: str, suffix: str) -> Path:
    return active_workspace() / f"{name}.{suffix}"


def graph_path(name: str) -> Path:
    if name == PROGRAM_NAME:
        return active_workspace() / "graph.json"
    return active_workspace() / f"graph-{name.replace('/', '__')}.json"


def write_file(name: str, suffix: str, text: str) -> None:
    path = workspace_path(name, suffix)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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


def read_graph(name: str) -> dict[str, Any]:
    path = graph_path(name)
    if not path.exists():
        return empty_graph()

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
        if "role" not in context:
            context["role"] = "leaf"
        if context.get("role") == "direct" and context.get("python_hash"):
            python = graph["pythons"].get(context["python_hash"])
            if python is not None and "provenance" not in python:
                human_text = graph["humans"].get(context.get("human_hash"), {}).get("text", "")
                python["provenance"] = python_provenance_fallback(human_text, python.get("text", ""), name, node_language(python))
    return graph


def write_graph(name: str, graph: dict[str, Any]) -> None:
    graph_path(name).write_text(json.dumps(graph, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    touch_active_project()


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


def word_kind(word: str) -> str:
    return "number" if re.fullmatch(r"[-+]?\d+(?:\.\d+)?", word) else "word"


def word_groups(words: list[str]) -> list[tuple[int, int]]:
    groups: list[tuple[int, int]] = []
    start = 0
    for index in range(1, len(words) + 1):
        if index == len(words) or word_kind(words[index]) != word_kind(words[start]):
            groups.append((start, index))
            start = index
    return groups


def find_word_span(words: list[str], phrase_words: list[str]) -> tuple[int, int] | None:
    size = len(phrase_words)
    for start in range(len(words) - size + 1):
        if words[start : start + size] == phrase_words:
            return start, start + size
    return None


def snap_span_to_groups(words: list[str], start: int, end: int) -> tuple[int, int]:
    groups = word_groups(words)
    left = next(group for group in groups if group[0] <= start < group[1])
    right = next(group for group in groups if group[0] < end <= group[1])
    snapped_start = start
    snapped_end = end
    if start != left[0] and word_kind(words[start]) == "number":
        snapped_start = left[1]
    if end != right[1] and word_kind(words[end - 1]) == "number":
        snapped_end = right[0]
    if snapped_start < snapped_end:
        return snapped_start, snapped_end
    return left[0], right[1]


def snap_phrase_to_human(human: str, phrase: str) -> str | None:
    phrase_words = phrase.split()
    if not phrase_words:
        return None
    if phrase_words == human.split():
        return " ".join(phrase_words)
    for line in human.splitlines():
        words = line.split()
        span = find_word_span(words, phrase_words)
        if span is None:
            continue
        start, end = snap_span_to_groups(words, span[0], span[1])
        return " ".join(words[start:end])
    return None


def phrase_memo(graph: dict[str, Any]) -> dict[str, list[str]]:
    return graph.setdefault("phrase_memo", {})


def remap_phrase_to_memo(graph: dict[str, Any], human: str, phrase: str) -> str:
    for line in human.splitlines():
        words = line.split()
        span = find_word_span(words, phrase.split())
        if span is None:
            continue
        stored = phrase_memo(graph).get(" ".join(words), [])
        if not stored or phrase in stored:
            return phrase
        best = phrase
        best_score = 0.0
        for candidate in stored:
            candidate_span = find_word_span(words, candidate.split())
            if candidate_span is None:
                continue
            overlap = min(span[1], candidate_span[1]) - max(span[0], candidate_span[0])
            if overlap <= 0:
                continue
            score = 2 * overlap / ((span[1] - span[0]) + (candidate_span[1] - candidate_span[0]))
            if score > best_score:
                best = candidate
                best_score = score
        return best
    return phrase


def update_phrase_memo(graph: dict[str, Any], human: str, phrases: list[str]) -> None:
    memo = phrase_memo(graph)
    for line in human.splitlines():
        words = line.split()
        if not words:
            continue
        key = " ".join(words)
        if key in memo:
            continue
        line_phrases = [
            phrase
            for index, phrase in enumerate(phrases)
            if phrase not in phrases[:index] and find_word_span(words, phrase.split()) is not None
        ]
        if line_phrases:
            memo[key] = line_phrases


def phrase_line_in_human(human: str, text: str) -> int:
    words = text.split()
    if words:
        for index, line in enumerate(human.splitlines(), start=1):
            if find_word_span(line.split(), words) is not None:
                return index
    return 1


def phrase_registry(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return graph.setdefault("phrases", {})


def ensure_phrase(graph: dict[str, Any], human: str, text: str) -> str:
    text = text.strip()
    registry = phrase_registry(graph)
    for phrase_id, entry in registry.items():
        if isinstance(entry, dict) and entry.get("text") == text:
            entry["line"] = phrase_line_in_human(human, text)
            return phrase_id
    graph["phrase_seq"] = int(graph.get("phrase_seq", 0)) + 1
    phrase_id = f"p{graph['phrase_seq']}"
    registry[phrase_id] = {"text": text, "line": phrase_line_in_human(human, text)}
    return phrase_id


def context_provenance_from_scratch(human: str, context: str) -> list[dict[str, Any]]:
    source = f'human phrase "{human.strip()}"'
    return [
        {"line": index, "status": "added", "source": source, "text": line, "target": target}
        for index, line, target in numbered_context_lines(context)
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
    refinement = snap_phrase_to_human(new_human, refinement) or new_human.strip()
    inherited_source = f'human phrase "{previous_human.strip()}"'
    added_source = f'human phrase "{refinement}"'

    provenance: list[dict[str, Any]] = []
    for index, line, target in numbered_context_lines(updated_context):
        prior = previous_by_text.get(line) or previous_by_text.get(line.strip())
        if prior:
            prior_status = prior.get("status", "inherited")
            provenance.append(
                {
                    "line": index,
                    "status": "manual" if prior_status == "manual" else "inherited",
                    "source": prior.get("source", inherited_source),
                    "text": line,
                    "previous_line": prior.get("line"),
                    "target": target,
                }
            )
        elif line in previous_lines:
            provenance.append({"line": index, "status": "inherited", "source": inherited_source, "text": line, "target": target})
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
                        "target": target,
                    }
                )
            else:
                provenance.append({"line": index, "status": "added", "source": added_source, "text": line, "target": target})
        else:
            provenance.append({"line": index, "status": "added", "source": f'human phrase "{new_human.strip()}"', "text": line, "target": target})
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
    for index, line, target in numbered_context_lines(edited_context):
        prior = previous_by_text.get(line) or previous_by_text.get(line.strip())
        if prior:
            prior_status = prior.get("status", "inherited")
            provenance.append(
                {
                    "line": index,
                    "status": "manual" if prior_status == "manual" else "inherited",
                    "source": prior.get("source", "previous context"),
                    "text": line,
                    "previous_line": prior.get("line"),
                    "target": target,
                }
            )
        elif line in previous_lines:
            provenance.append({"line": index, "status": "inherited", "source": "previous context", "text": line, "target": target})
        else:
            provenance.append({"line": index, "status": "manual", "source": "manual edit in .context", "text": line, "target": target})
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
    role: Literal["leaf", "split", "direct"] | None = None,
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
            "role": role or "leaf",
            "provenance": provenance or context_provenance_from_scratch(graph["humans"][human_hash]["text"], text),
            "parent_context_hash": parent_context_hash,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
    else:
        touch(contexts[hash_])
        contexts[hash_].setdefault("human_hash", human_hash)
        if role is not None:
            contexts[hash_]["role"] = role
        contexts[hash_].setdefault("role", "leaf")
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


def ensure_python(graph: dict[str, Any], text: str, context_hash: str | None, language: str = "python") -> str:
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
            "language": language,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
    else:
        touch(pythons[hash_])
        pythons[hash_].setdefault("context_hash", context_hash)
        pythons[hash_].setdefault("language", language)

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


def resolve_checkout_context_hash(graph: dict[str, Any], python: dict[str, Any]) -> str | None:
    _, active_context_hash, _ = active_hashes(graph)
    if active_context_hash and python_belongs_to_context(python, active_context_hash):
        return active_context_hash
    linked = [
        hash_
        for hash_ in [*python.get("context_hashes", []), python.get("context_hash")]
        if hash_ and hash_ in graph["contexts"]
    ]
    if not linked:
        return None
    return max(linked, key=lambda hash_: graph["contexts"][hash_].get("updated_at", ""))


def resolve_checkout_human_hash(graph: dict[str, Any], context: dict[str, Any]) -> str | None:
    current = graph.get("current_human_hash")
    if current and current in graph["humans"] and context_belongs_to_human(context, current):
        return current
    linked = [
        hash_
        for hash_ in [*context.get("human_hashes", []), context.get("human_hash")]
        if hash_ and hash_ in graph["humans"]
    ]
    if not linked:
        return None
    return max(linked, key=lambda hash_: graph["humans"][hash_].get("updated_at", ""))


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


def explain_text(graph: dict[str, Any], name: str) -> str:
    human_hash, context_hash, python_hash = active_hashes(graph)
    human = graph["humans"].get(human_hash, {}) if human_hash else {}
    context = graph["contexts"].get(context_hash, {}) if context_hash else {}
    python = graph["pythons"].get(python_hash, {}) if python_hash else {}

    lines = [
        f"# {name}.explain",
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


def active_context_role(graph: dict[str, Any]) -> str | None:
    _, context_hash, _ = active_hashes(graph)
    if not context_hash:
        return None
    return graph["contexts"].get(context_hash, {}).get("role", "leaf")


def valid_split_target(target: str) -> bool:
    if not target or "\\" in target or target.startswith("/") or target.endswith("/"):
        return False
    if any(not segment or segment == ".." for segment in target.split("/")):
        return False
    return target_extension(target) in SPLIT_CODE_EXTENSIONS


def split_unit_nodes_for(graph: dict[str, Any], context_hash: str) -> dict[str, tuple[str, dict[str, Any]]]:
    units: dict[str, tuple[str, dict[str, Any]]] = {}
    for hash_, python in sorted(graph["pythons"].items(), key=lambda item: item[1].get("updated_at", "")):
        if not python_belongs_to_context(python, context_hash):
            continue
        target = python.get("target")
        if not target or not valid_split_target(target):
            continue
        units[target] = (hash_, python)
    return units


def split_unit_nodes(graph: dict[str, Any]) -> dict[str, tuple[str, dict[str, Any]]]:
    _, context_hash, _ = active_hashes(graph)
    if not context_hash:
        return {}
    return split_unit_nodes_for(graph, context_hash)


def split_unit_files(graph: dict[str, Any]) -> dict[str, str]:
    return {target: node["text"] for target, (_, node) in split_unit_nodes(graph).items()}


def materialize_current(name: str, graph: dict[str, Any]) -> None:
    human, context, python = active_texts(graph)
    _, _, python_hash = active_hashes(graph)
    python_node = graph["pythons"].get(python_hash) if python_hash else None
    extension = language_extension(node_language(python_node))
    write_file(name, "human", human)
    write_file(name, "context", context)
    for stale in sorted(set(LANGUAGES.values()) - {extension}):
        workspace_path(name, stale).unlink(missing_ok=True)
    write_file(name, extension, python)
    write_file(name, "explain", explain_text(graph, name))
    role = active_context_role(graph)
    units = split_unit_files(graph) if role == "split" else None
    materialize_repo_files(name, human, context, python, role, units, extension)


def program_unit_dir(name: str) -> Path:
    if "/" in name:
        return REPO_ROOT / "project" / name.rsplit("/", 1)[0]
    return REPO_ROOT / "project"


def write_repo_text(path: Path, text: str) -> None:
    try:
        if path.is_file() and path.read_text(encoding="utf-8") == text:
            return
    except (OSError, UnicodeDecodeError):
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def materialize_repo_files(
    name: str,
    human: str,
    context: str,
    python: str,
    context_role: str | None = None,
    units: dict[str, str] | None = None,
    extension: str = "py",
) -> None:
    if not human.strip() and not context.strip() and not python.strip():
        return
    repo_human_dir = REPO_ROOT / "human"
    repo_project_dir = REPO_ROOT / "project"
    repo_human_dir.mkdir(parents=True, exist_ok=True)
    repo_project_dir.mkdir(parents=True, exist_ok=True)
    write_repo_text(repo_human_dir / f"{name}.human", human)
    repo_context = repo_human_dir / f"{name}.context"
    if context_role is None or context_role == "direct":
        repo_context.unlink(missing_ok=True)
    else:
        write_repo_text(repo_context, context)
    if context_role == "split" and units:
        for stale in sorted(set(LANGUAGES.values())):
            (repo_project_dir / f"{name}.{stale}").unlink(missing_ok=True)
        unit_dir = program_unit_dir(name)
        for target, text in units.items():
            write_repo_text(unit_dir / target, text)
    else:
        for stale in sorted(set(LANGUAGES.values()) - {extension}):
            (repo_project_dir / f"{name}.{stale}").unlink(missing_ok=True)
        write_repo_text(repo_project_dir / f"{name}.{extension}", python)


def python_tree_response(graph: dict[str, Any], python: dict[str, Any], active_python: str | None) -> TreePythonResponse:
    return TreePythonResponse(
        hash=python["hash"],
        preview=preview(python["text"]),
        active=python["hash"] == active_python,
        target=python.get("target"),
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
        role=context.get("role", "leaf"),
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


def hydrated_source(entry: dict[str, Any], phrases: dict[str, Any] | None) -> str:
    phrase_id = entry.get("phraseId")
    if phrases and phrase_id in phrases and isinstance(phrases[phrase_id], dict):
        return f'human phrase "{phrases[phrase_id].get("text", "")}"'
    return entry.get("source", "unknown source")


def provenance_response(entries: list[Any], phrases: dict[str, Any] | None = None) -> list[ContextProvenanceResponse]:
    return [
        ContextProvenanceResponse(
            line=entry.get("line", "?"),
            status=entry.get("status", "unknown"),
            source=hydrated_source(entry, phrases),
            text=entry.get("text", ""),
            previousLine=entry.get("previous_line"),
            target=entry.get("target"),
            contextLine=entry.get("context_line"),
            phraseId=entry.get("phraseId"),
        )
        for entry in entries
        if isinstance(entry, dict)
    ]


def seeded_disk_texts(name: str) -> tuple[str, str] | None:
    human_path = REPO_ROOT / "human" / f"{name}.human"
    if not human_path.is_file():
        return None
    context_path = REPO_ROOT / "human" / f"{name}.context"
    context = context_path.read_text(encoding="utf-8") if context_path.is_file() else ""
    return human_path.read_text(encoding="utf-8"), context


def files_response(name: str, graph: dict[str, Any]) -> FilesResponse:
    registry = graph.get("phrases") or {}
    human_hash, context_hash, python_hash = active_hashes(graph)
    human, context, python = active_texts(graph)
    context_node = graph["contexts"].get(context_hash, {}) if context_hash else {}
    seeded = seeded_disk_texts(name) if human_hash is None else None
    if seeded is not None:
        human, context = seeded
    if context_hash:
        context_role = context_node.get("role", "leaf")
    elif seeded is not None and context.strip():
        context_role = "leaf"
    else:
        context_role = None
    if python_hash and context_node.get("role") == "direct":
        python_provenance = graph["pythons"].get(python_hash, {}).get("provenance", [])
    elif context_hash and context_node.get("role") == "split":
        python_provenance = [
            entry
            for _target, (_hash, node) in sorted(split_unit_nodes(graph).items())
            for entry in node.get("provenance", [])
        ]
    else:
        python_provenance = []
    units = (
        [
            UnitResponse(target=target, python=node["text"], hash=hash_)
            for target, (hash_, node) in sorted(split_unit_nodes(graph).items())
        ]
        if context_hash and context_node.get("role") == "split"
        else []
    )
    return FilesResponse(
        name=name,
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
        contextRole=context_role,
        contextProvenance=provenance_response(context_node.get("provenance", []), registry),
        pythonProvenance=provenance_response(python_provenance, registry),
        units=units,
        phrases={
            phrase_id: PhraseResponse(text=entry.get("text", ""), line=entry.get("line", 1))
            for phrase_id, entry in registry.items()
            if isinstance(entry, dict)
        },
        tree=graph_tree(graph),
        seeded=seeded is not None,
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

HUMAN_TO_SPLIT_SYSTEM = """You are the .human -> .context split compiler stage for fran++ v0.0.5.

Input: freeform human intent.
Output: a readable decomposition of the intent into units, as plain-text sections.

Rules:
- Do not output JSON.
- Do not output markdown.
- Do not output code.
- One section per unit, sections separated by exactly one blank line.
- Every section starts with a line of exactly this form: <target> — <description>
- <target> is the file the unit compiles to, ending in .py, or an inner context ending in .context for a unit that needs its own decomposition later.
- <description> is a plain-English sentence or short paragraph (it may continue on the following lines of the section) saying what the unit does, what it takes in, what it produces, and which other units it uses.
- Example: serve.py — Bind to the host and port, accept connections, and dispatch each request to the handler.
- Exactly one unit targets main.py and its description says how it orchestrates the other units.
- Decompose the intent into the smallest set of cohesive units that covers it completely.
- Each unit's description must be precise enough to compile that unit to Python in isolation.
"""

CONTEXT_SHAPE_SYSTEM = """You are the .context shape triage stage for fran++ v0.0.5.

Input: freeform human intent.
Output: exactly one word: leaf or split.

Rules:
- Answer split only when the intent clearly decomposes into several cohesive units (a pipeline, multiple components, distinct responsibilities) that deserve separate files.
- Answer leaf when the intent is a single cohesive unit, even if it needs many implementation decisions.
- When unsure, answer leaf.
- Output the single word and nothing else.
"""

COMPILE_TRIAGE_SYSTEM = """You are the compile triage stage for fran++ v0.0.5.

Input: freeform human intent.
Output: exactly one word: direct or context.

Rules:
- Answer direct when a competent programmer could write the Python immediately with no design notes in between.
- direct covers: named textbook algorithms (insertion sort, binary search, fizzbuzz, reverse a string, fibonacci), one-liner utilities, tiny single-file scripts, and an algorithm or task name optionally followed by sample input values.
- Terse intents are fine for direct: "insertion sort 1 3 2" means implement insertion sort and demo it on 1 3 2, so it is direct.
- Answer context only when the intent has multiple distinct components, needs architectural decisions, or is so under-specified that sensible defaults cannot settle it.
- If the intent is a single small self-contained script and you are torn, answer direct.
- Output the single word and nothing else.
"""

HUMAN_TO_PYTHON_SYSTEM = """You are the direct .human -> .py compiler stage for fran++ v0.0.5.

Input: freeform human intent.
Output: Python source code only.

Rules:
- No prose.
- No markdown fences.
- The first line must be exactly: \"\"\"Compiled directly from .human — DO NOT EDIT.\"\"\"
- Implement the intent faithfully with sensible defaults.
- Include a small if __name__ == \"__main__\": example when appropriate.
- Keep imports minimal.
"""

PYTHON_PROVENANCE_SYSTEM = """You are the .human -> .py provenance mapping stage for fran++ v0.0.5.

Input: a human intent and the numbered lines of the Python compiled directly from it.
Output: a JSON array only.

Rules:
- Each array element is an object with exactly two keys: "line" (an integer line number from the numbered Python) and "source" (the human phrase that motivates that line, quoted verbatim from the intent).
- Cover every non-blank Python line; skip blank lines.
- Prefer the shortest human phrase that explains the line; when a line is general boilerplate implied by the whole intent, use the entire intent as the phrase.
- Each "source" must be a contiguous span of a single line of the intent, starting and ending on whole words — never cut a word in half.
- Never split a tight group such as a run of consecutive numbers: a phrase includes the whole run or none of it. For "insertion sort 1 2 3" the valid phrases are "insertion sort" and "1 2 3", never "insertion sort 1" or "2 3".
- Distinct phrases must not partially overlap; reuse the identical phrase for every line motivated by the same part of the intent.
- Do not invent phrases that are not in the human intent.
- Output the JSON array and nothing else.
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


def human_to_context_system(language: str) -> str:
    if language == "python":
        return HUMAN_TO_CONTEXT_SYSTEM
    return HUMAN_TO_CONTEXT_SYSTEM.replace(
        "can generate Python from it", f"can generate {language_label(language)} from it"
    )


def human_to_split_system(language: str) -> str:
    if language == "python":
        return HUMAN_TO_SPLIT_SYSTEM
    extension = language_extension(language)
    system = HUMAN_TO_SPLIT_SYSTEM.replace(
        "- Example: serve.py — Bind to the host and port, accept connections, and dispatch each request to the handler.",
        f"- Example: helpers.{extension} — Implement the shared helper unit that the other units build on.",
    )
    return system.replace(".py", f".{extension}").replace("Python", language_label(language))


def human_to_code_system(language: str) -> str:
    if language == "python":
        return HUMAN_TO_PYTHON_SYSTEM
    extension = language_extension(language)
    label = language_label(language)
    return f"""You are the direct .human -> .{extension} compiler stage for fran++ v0.0.5.

Input: freeform human intent.
Output: {label} source code only.

Rules:
- No prose.
- No markdown fences.
- Implement the intent faithfully with sensible defaults.
- Keep the output a single self-contained .{extension} file.
"""


def context_to_code_system(language: str) -> str:
    if language == "python":
        return CONTEXT_TO_PYTHON_SYSTEM
    extension = language_extension(language)
    label = language_label(language)
    return f"""You are the .context -> .{extension} compiler stage for fran++ v0.0.5.

Input: free-text implementation context.
Output: {label} source code only.

Rules:
- No prose.
- No markdown fences.
- Implement the context faithfully.
- Keep the output a single self-contained .{extension} file.
"""


def code_provenance_system(language: str) -> str:
    if language == "python":
        return PYTHON_PROVENANCE_SYSTEM
    return PYTHON_PROVENANCE_SYSTEM.replace(".py", f".{language_extension(language)}").replace(
        "Python", language_label(language)
    )


def unit_reference_rule(language: str) -> str:
    if language == "python":
        return "When the description says this unit uses another unit, import that unit by its module name."
    return "When the description says this unit uses another unit, reference it by its relative path."


def human_to_context(human: str, language: str = "python") -> str:
    raw = call_bedrock(
        human_to_context_system(language),
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


def human_to_split(human: str, language: str = "python") -> str:
    raw = call_bedrock(
        human_to_split_system(language),
        f"Human intent:\n{human.strip()}\n\nReturn only the split .context rows.",
    )
    return strip_code_fences(raw) + "\n"


def context_to_code(context: str, language: str = "python") -> str:
    raw = call_bedrock(
        context_to_code_system(language),
        f"Context:\n{context.strip()}\n\nReturn only the {language_label(language)} source.",
    )
    return strip_code_fences(raw) + "\n"


def human_to_code(human: str, language: str = "python") -> str:
    raw = call_bedrock(
        human_to_code_system(language),
        f"Human intent:\n{human.strip()}\n\nReturn only the {language_label(language)} source.",
    )
    return strip_code_fences(raw) + "\n"


def decide_word(system_prompt: str, human: str, options: set[str], default: str) -> str:
    raw = call_bedrock(system_prompt, f"Human intent:\n{human.strip()}\n\nAnswer with one word.", max_tokens=16)
    for token in raw.strip().lower().split():
        word = token.strip(".,:;!\"'")
        if word in options:
            return word
    return default


def decide_context_shape(human: str) -> Literal["leaf", "split"]:
    return decide_word(CONTEXT_SHAPE_SYSTEM, human, {"leaf", "split"}, "leaf")


def decide_compile_route(human: str) -> Literal["direct", "context"]:
    return decide_word(COMPILE_TRIAGE_SYSTEM, human, {"direct", "context"}, "context")


SPLIT_ATTRIBUTION_SYSTEM = """You are the split-section attribution stage for fran++ v0.0.5.

Input: numbered human phrases and numbered section headers from a split .context.
Output: a JSON array assigning every section exactly one phrase, like [{"section": 1, "phrase": 1}, {"section": 2, "phrase": 2}].

Rules:
- Return only the JSON array, no prose, no markdown, no code fences.
- Include exactly one entry per section, covering every section.
- "section" and "phrase" are 1-based indices into the input lists.
- Assign each section the phrase that motivated it.
- A section that no phrase mentions directly (an orchestrator, entry point, or glue file) must still get the closest related phrase.
"""


def split_attribution_from_llm(human: str, context: str) -> dict[str, str] | None:
    phrases = [line.strip() for line in human.splitlines() if line.strip()]
    headers = split_section_headers(context)
    if len(phrases) < 2 or not headers:
        return None
    numbered_phrases = "\n".join(f"{index}: {phrase}" for index, phrase in enumerate(phrases, start=1))
    numbered_sections = "\n".join(f"{index}: {header}" for index, (_target, header) in enumerate(headers, start=1))
    raw = call_bedrock(
        SPLIT_ATTRIBUTION_SYSTEM,
        f"Numbered human phrases:\n{numbered_phrases}\n\nNumbered section headers:\n{numbered_sections}\n\nReturn only the JSON array.",
    )
    try:
        entries = json.loads(strip_code_fences(raw))
    except json.JSONDecodeError:
        return None
    if not isinstance(entries, list):
        return None

    assigned: dict[int, int] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            return None
        section = entry.get("section")
        phrase = entry.get("phrase")
        if not isinstance(section, int) or section < 1 or section > len(headers) or section in assigned:
            return None
        if not isinstance(phrase, int) or phrase < 1 or phrase > len(phrases):
            return None
        assigned[section] = phrase
    if len(assigned) != len(headers):
        return None
    return {headers[section - 1][0]: phrases[phrase - 1] for section, phrase in assigned.items()}


def split_section_sources_for_compile(human: str, context: str) -> dict[str, str]:
    phrases = [line.strip() for line in human.splitlines() if line.strip()]
    if len(phrases) < 2 or not split_section_headers(context):
        return {}
    for _attempt in range(2):
        try:
            mapped = split_attribution_from_llm(human, context)
        except HTTPException:
            mapped = None
        if mapped is not None:
            return mapped
    raise HTTPException(status_code=502, detail="llm attribution failed: section sources")


SPLIT_LINE_ATTRIBUTION_SYSTEM = """You are the split-line attribution stage for fran++ v0.0.5.

Input: numbered human phrases and numbered non-blank lines from a split .context.
Output: a JSON array assigning every context line exactly one phrase, like [{"line": 1, "phrase": 1}, {"line": 2, "phrase": 2}].

Rules:
- Return only the JSON array, no prose, no markdown, no code fences.
- Include exactly one entry per context line, covering every context line.
- "line" and "phrase" are 1-based indices into the input lists.
- Assign each context line the phrase that motivated it.
- A section header line gets the phrase that motivated its unit as a whole.
- A line that no phrase mentions directly must still get the closest related phrase.
"""


def split_line_attribution_from_llm(human: str, context: str) -> dict[int, str] | None:
    phrases = [line.strip() for line in human.splitlines() if line.strip()]
    numbered = numbered_context_lines(context)
    if len(phrases) < 2 or not numbered:
        return None
    numbered_phrases = "\n".join(f"{index}: {phrase}" for index, phrase in enumerate(phrases, start=1))
    numbered_lines = "\n".join(
        f"{index}: {line.strip()}" for index, (_line_number, line, _target) in enumerate(numbered, start=1)
    )
    raw = call_bedrock(
        SPLIT_LINE_ATTRIBUTION_SYSTEM,
        f"Numbered human phrases:\n{numbered_phrases}\n\nNumbered context lines:\n{numbered_lines}\n\nReturn only the JSON array.",
    )
    try:
        entries = json.loads(strip_code_fences(raw))
    except json.JSONDecodeError:
        return None
    if not isinstance(entries, list):
        return None

    assigned: dict[int, int] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            return None
        line = entry.get("line")
        phrase = entry.get("phrase")
        if not isinstance(line, int) or line < 1 or line > len(numbered) or line in assigned:
            return None
        if not isinstance(phrase, int) or phrase < 1 or phrase > len(phrases):
            return None
        assigned[line] = phrase
    if len(assigned) != len(numbered):
        return None
    return {numbered[line - 1][0]: phrases[phrase - 1] for line, phrase in assigned.items()}


HUMAN_PHRASE_SOURCE_RE = re.compile(r'human phrase "([^"]+)"')


def stored_section_sources(provenance: list[Any]) -> dict[str, str]:
    sources: dict[str, str] = {}
    for entry in provenance:
        if not isinstance(entry, dict):
            continue
        target = entry.get("target")
        if not target or target in sources:
            continue
        match = HUMAN_PHRASE_SOURCE_RE.search(entry.get("source", ""))
        if match:
            sources[target] = match.group(1)
    return sources


def split_provenance(
    graph: dict[str, Any],
    human: str,
    context: str,
    section_sources: dict[str, str],
    line_sources: dict[int, str],
) -> list[dict[str, Any]]:
    full_source = f'human phrase "{human.strip()}"'
    provenance: list[dict[str, Any]] = []
    for line_number, line, target in numbered_context_lines(context):
        phrase = line_sources.get(line_number) or (section_sources.get(target) if target else None)
        source = f'human phrase "{phrase}"' if phrase else full_source
        provenance.append(
            {
                "line": line_number,
                "status": "added",
                "source": source,
                "text": line.strip(),
                "target": target,
                "phraseId": ensure_phrase(graph, human, phrase or human.strip()),
            }
        )
    return provenance


def llm_split_line_attribution(human: str, context: str, stage: str) -> dict[int, str]:
    phrases = [line.strip() for line in human.splitlines() if line.strip()]
    if len(phrases) < 2 or not numbered_context_lines(context):
        return {}
    for _attempt in range(2):
        try:
            mapped = split_line_attribution_from_llm(human, context)
        except HTTPException:
            mapped = None
        if mapped is not None:
            return mapped
    raise HTTPException(status_code=502, detail=f"llm attribution failed: {stage}")


def split_context_attribution(graph: dict[str, Any], human: str, context: str) -> list[dict[str, Any]]:
    section_sources = split_section_sources_for_compile(human, context)
    line_sources = llm_split_line_attribution(human, context, "context lines")
    return split_provenance(graph, human, context, section_sources, line_sources)


def ensure_split_context(graph: dict[str, Any], context: str, human_hash: str, human: str) -> str:
    provenance = split_context_attribution(graph, human, context)
    context_hash = ensure_context(graph, context, human_hash, provenance=provenance, role="split")
    graph["contexts"][context_hash]["line_attribution"] = "llm"
    return context_hash


def split_line_mapping(previous_context: str, edited_context: str) -> dict[int, int]:
    previous_by_text: dict[str, list[int]] = {}
    for line_number, line, _target in numbered_context_lines(previous_context):
        previous_by_text.setdefault(line.strip(), []).append(line_number)
    mapping: dict[int, int] = {}
    for line_number, line, _target in numbered_context_lines(edited_context):
        candidates = previous_by_text.get(line.strip())
        if candidates:
            mapping[candidates.pop(0)] = line_number
    return mapping


def split_provenance_from_manual_edit(
    graph: dict[str, Any], previous_context_node: dict[str, Any], edited_context: str, human: str
) -> list[dict[str, Any]]:
    previous_provenance = previous_context_node.get("provenance", []) or []
    previous_by_text: dict[str, list[dict[str, Any]]] = {}
    for entry in previous_provenance:
        if isinstance(entry, dict) and isinstance(entry.get("text"), str) and entry["text"].strip():
            previous_by_text.setdefault(entry["text"].strip(), []).append(entry)
    section_sources = stored_section_sources(previous_provenance)
    line_sources: dict[int, str] | None = None
    full_source = f'human phrase "{human.strip()}"'
    provenance: list[dict[str, Any]] = []
    for line_number, line, target in numbered_context_lines(edited_context):
        candidates = previous_by_text.get(line.strip())
        if candidates:
            prior = candidates.pop(0)
            carried = {
                "line": line_number,
                "status": prior.get("status", "added"),
                "source": prior.get("source", full_source),
                "text": line.strip(),
                "target": target,
            }
            if "phraseId" in prior:
                carried["phraseId"] = prior["phraseId"]
            provenance.append(carried)
            continue
        if line_sources is None:
            line_sources = llm_split_line_attribution(human, edited_context, "manual context lines")
        phrase = line_sources.get(line_number) or (section_sources.get(target) if target else None)
        source = f'human phrase "{phrase}"' if phrase else full_source
        provenance.append(
            {
                "line": line_number,
                "status": "manual",
                "source": source,
                "text": line.strip(),
                "target": target,
                "phraseId": ensure_phrase(graph, human, phrase or human.strip()),
            }
        )
    return provenance


def remap_unit_provenance(
    entries: list[Any],
    mapping: dict[int, int],
    new_by_line: dict[int, dict[str, Any]],
    header_by_target: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    remapped: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        entry = dict(entry)
        new_line = mapping.get(entry.get("context_line"))
        replacement = new_by_line.get(new_line) if new_line is not None else header_by_target.get(entry.get("target"))
        if replacement is not None:
            entry["context_line"] = replacement.get("line")
            entry["source"] = replacement.get("source", entry.get("source"))
            if "phraseId" in replacement:
                entry["phraseId"] = replacement["phraseId"]
        remapped.append(entry)
    return remapped


def save_split_context(
    graph: dict[str, Any], edited_context: str, human_hash: str | None, previous_context_hash: str
) -> str:
    previous_context_node = graph["contexts"][previous_context_hash]
    previous_context = previous_context_node.get("text", "")
    human = graph["humans"].get(human_hash, {}).get("text", "") if human_hash else ""
    provenance = split_provenance_from_manual_edit(graph, previous_context_node, edited_context, human)
    context_hash = ensure_context(
        graph, edited_context, human_hash, provenance=provenance, parent_context_hash=previous_context_hash, role="split"
    )
    graph["contexts"][context_hash]["line_attribution"] = "llm"
    if context_hash == previous_context_hash:
        return context_hash
    mapping = split_line_mapping(previous_context, edited_context)
    new_by_line = {entry["line"]: entry for entry in provenance}
    header_by_target: dict[str, dict[str, Any]] = {}
    for entry in provenance:
        target = entry.get("target")
        if target and target not in header_by_target:
            header_by_target[target] = entry
    for target, (_hash, node) in split_unit_nodes_for(graph, previous_context_hash).items():
        code_hash = ensure_python(graph, node.get("text", ""), context_hash, language=node.get("language", "python"))
        unit = graph["pythons"][code_hash]
        unit["target"] = target
        unit["provenance"] = remap_unit_provenance(unit.get("provenance", []) or [], mapping, new_by_line, header_by_target)
    return context_hash


def direct_context_text(human_hash: str) -> str:
    return f"compiled directly from .human {human_hash[:12]}; no intermediate .context\n"


def python_provenance_fallback(human: str, python: str, name: str, language: str = "python") -> list[dict[str, Any]]:
    source = f'human phrase "{human.strip()}"'
    return [
        {"line": index, "status": "added", "source": source, "text": line, "target": f"{name}.{language_extension(language)}"}
        for index, line in enumerate(python.splitlines(), start=1)
        if line.strip()
    ]


def python_provenance_from_llm(graph: dict[str, Any], human: str, python: str, name: str, language: str = "python") -> list[dict[str, Any]] | None:
    lines = python.splitlines()
    numbered = "\n".join(f"{index}: {line}" for index, line in enumerate(lines, start=1))
    raw = call_bedrock(
        code_provenance_system(language),
        f"Human intent:\n{human.strip()}\n\nNumbered {language_label(language)}:\n{numbered}\n\nReturn only the JSON array.",
    )
    try:
        entries = json.loads(strip_code_fences(raw))
    except json.JSONDecodeError:
        return None
    if not isinstance(entries, list):
        return None

    provenance: list[dict[str, Any]] = []
    used_phrases: list[str] = []
    seen: set[int] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        line = entry.get("line")
        source = entry.get("source")
        if not isinstance(line, int) or line < 1 or line > len(lines) or line in seen:
            continue
        if not isinstance(source, str):
            continue
        snapped = snap_phrase_to_human(human, source.strip())
        if not snapped:
            continue
        snapped = remap_phrase_to_memo(graph, human, snapped)
        text = lines[line - 1]
        if not text.strip():
            continue
        seen.add(line)
        used_phrases.append(snapped)
        provenance.append(
            {
                "line": line,
                "status": "added",
                "source": f'human phrase "{snapped}"',
                "text": text,
                "target": f"{name}.{language_extension(language)}",
            }
        )
    if not provenance:
        return None
    update_phrase_memo(graph, human, used_phrases)
    return provenance


def python_provenance_for_direct(graph: dict[str, Any], human: str, python: str, name: str, language: str = "python") -> list[dict[str, Any]]:
    if not python.strip():
        return []
    try:
        mapped = python_provenance_from_llm(graph, human, python, name, language)
    except HTTPException:
        mapped = None
    return mapped or python_provenance_fallback(human, python, name, language)


UNIT_PROVENANCE_SYSTEM = """You are the split-unit code provenance stage for fran++ v0.0.5.

Input: the numbered non-blank .context lines for one split unit and the numbered lines of the code compiled for that unit.
Output: a JSON array of ranges like [{"start": 1, "end": 12, "context": 1}].

Rules:
- Return only the JSON array, no prose, no markdown, no code fences.
- "start" and "end" are inclusive 1-based code line numbers; "context" is a 1-based index into the numbered context lines.
- Ranges must not overlap and together must cover every non-blank code line.
- Assign each range the context line that motivated its code.
- Code implied by the unit as a whole belongs to the unit's header context line.
"""


def split_section_entries(provenance: list[Any], target: str) -> list[dict[str, Any]]:
    return [
        entry
        for entry in provenance
        if isinstance(entry, dict) and entry.get("target") == target and entry.get("text")
    ]


def unit_provenance_entry(line_number: int, text: str, target: str, section_entry: dict[str, Any]) -> dict[str, Any]:
    entry = {
        "line": line_number,
        "status": "added",
        "source": section_entry.get("source", "unknown source"),
        "text": text,
        "target": target,
        "context_line": section_entry.get("line"),
    }
    if "phraseId" in section_entry:
        entry["phraseId"] = section_entry["phraseId"]
    return entry


def unit_provenance_from_llm(section_entries: list[dict[str, Any]], code: str, target: str) -> list[dict[str, Any]] | None:
    lines = code.splitlines()
    numbered_context = "\n".join(f"{index}: {entry['text']}" for index, entry in enumerate(section_entries, start=1))
    numbered_code = "\n".join(f"{index}: {line}" for index, line in enumerate(lines, start=1))
    raw = call_bedrock(
        UNIT_PROVENANCE_SYSTEM,
        f"Numbered context lines for {target}:\n{numbered_context}\n\nNumbered code lines:\n{numbered_code}\n\nReturn only the JSON array.",
    )
    try:
        ranges = json.loads(strip_code_fences(raw))
    except json.JSONDecodeError:
        return None
    if not isinstance(ranges, list):
        return None

    assigned: dict[int, dict[str, Any]] = {}
    for entry in ranges:
        if not isinstance(entry, dict):
            return None
        start = entry.get("start")
        end = entry.get("end")
        context_index = entry.get("context")
        if not isinstance(start, int) or not isinstance(end, int) or not isinstance(context_index, int):
            return None
        if start < 1 or end > len(lines) or start > end or context_index < 1 or context_index > len(section_entries):
            return None
        for line_number in range(start, end + 1):
            if line_number in assigned:
                return None
            assigned[line_number] = section_entries[context_index - 1]

    provenance: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        section_entry = assigned.get(line_number)
        if section_entry is None:
            return None
        provenance.append(unit_provenance_entry(line_number, line, target, section_entry))
    return provenance or None


def unit_provenance_for_split(context_provenance: list[Any], target: str, code: str) -> list[dict[str, Any]]:
    if not code.strip():
        return []
    section_entries = split_section_entries(context_provenance, target)
    if not section_entries:
        return []
    for _attempt in range(2):
        try:
            mapped = unit_provenance_from_llm(section_entries, code, target)
        except HTTPException:
            mapped = None
        if mapped is not None:
            return mapped
    raise HTTPException(status_code=502, detail="llm attribution failed: unit code lines")


def resolve_adaptive_context(graph: dict[str, Any], req: HumanRequest, language: str = "python") -> str:
    previous_human_hash, previous_context_hash, _ = active_hashes(graph)
    previous_human = graph["humans"].get(previous_human_hash, {}).get("text", "") if previous_human_hash else ""
    previous_context_node = graph["contexts"].get(previous_context_hash) if previous_context_hash else None
    previous_context = previous_context_node.get("text", "") if previous_context_node else ""

    human_hash = ensure_human(graph, req.human)
    human = graph["humans"][human_hash]

    if human.get("context_hash") and not req.force:
        return human["context_hash"]

    shape = decide_context_shape(req.human)
    if shape == "split":
        context = human_to_split(req.human, language)
        return ensure_split_context(graph, context, human_hash, req.human)

    if previous_context and previous_human_hash != human_hash and previous_context_node.get("role", "leaf") == "leaf":
        context = update_context(previous_human, previous_context, req.human)
        provenance = context_provenance_from_update(previous_human, previous_context_node, req.human, context)
        return ensure_context(graph, context, human_hash, provenance=provenance, parent_context_hash=previous_context_hash, role="leaf")

    context = human_to_context(req.human, language)
    provenance = context_provenance_from_scratch(req.human, context)
    return ensure_context(graph, context, human_hash, provenance=provenance, role="leaf")


def compile_split_children(graph: dict[str, Any], context_hash: str) -> None:
    context_node = graph["contexts"][context_hash]
    sections = parse_split_sections(context_node["text"])
    targets = [section["target"] for section in sections]
    for section in sections:
        if section["target"].endswith(".context") or not valid_split_target(section["target"]):
            continue
        section_language = target_language(section["target"])
        unit_context = "\n".join(
            [
                f"Compile only the unit that targets {section['target']}.",
                f"The full program is split into these units: {', '.join(targets)}.",
                unit_reference_rule(section_language),
                "Unit description:",
                *section["description"],
            ]
        )
        code = context_to_code(unit_context, section_language)
        code_hash = ensure_python(graph, code, context_hash, language=section_language)
        graph["pythons"][code_hash]["target"] = section["target"]
        graph["pythons"][code_hash]["provenance"] = unit_provenance_for_split(
            context_node.get("provenance", []), section["target"], code
        )


def adopt_split_children(graph: dict[str, Any], context_hash: str, name: str) -> None:
    context_node = graph["contexts"][context_hash]
    unit_dir = program_unit_dir(name)
    for section in parse_split_sections(context_node["text"]):
        if section["target"].endswith(".context") or not valid_split_target(section["target"]):
            continue
        section_language = target_language(section["target"])
        source = unit_dir / section["target"]
        code = source.read_text(encoding="utf-8") if source.is_file() else ""
        code_hash = ensure_python(graph, code, context_hash, language=section_language)
        graph["pythons"][code_hash]["target"] = section["target"]
        graph["pythons"][code_hash]["provenance"] = unit_provenance_for_split(
            context_node.get("provenance", []), section["target"], code
        )


def adopt_leaf_code(graph: dict[str, Any], context_hash: str, name: str) -> None:
    for language, extension in sorted(LANGUAGES.items()):
        source = REPO_ROOT / "project" / f"{name}.{extension}"
        if source.is_file():
            ensure_python(graph, source.read_text(encoding="utf-8"), context_hash, language=language)
            return


def complete_python(graph: dict[str, Any], context_hash: str, human: str, name: str, force: bool = False, language: str = "python") -> None:
    context_node = graph["contexts"][context_hash]
    if context_node.get("python_hash") and not force:
        return
    role = context_node.get("role", "leaf")
    if role == "split":
        compile_split_children(graph, context_hash)
    elif role == "direct":
        code_text = human_to_code(human, language)
        code_hash = ensure_python(graph, code_text, context_hash, language=language)
        graph["pythons"][code_hash]["provenance"] = python_provenance_for_direct(graph, human, code_text, name, language)
    else:
        ensure_python(graph, context_to_code(context_node["text"], language), context_hash, language=language)


@app.get("/")
def root():
    return {"name": "fran++ v0.0.5 backend", "docs": "/docs"}


@app.get("/api/health")
def health():
    return {"ok": True, "model": MODEL_ID, "region": REGION}


def fs_tree_node(directory: Path, depth: int, max_depth: int) -> FsNodeResponse:
    children: list[FsNodeResponse] = []
    if depth < max_depth:
        try:
            entries = list(directory.iterdir())
        except OSError:
            entries = []
        subdirs: list[Path] = []
        files: list[Path] = []
        for entry in entries:
            try:
                is_dir = entry.is_dir()
            except OSError:
                continue
            if is_dir:
                if entry.name not in FS_SKIP_DIRS:
                    subdirs.append(entry)
            else:
                files.append(entry)
        subdirs.sort(key=lambda item: item.name.lower())
        files.sort(key=lambda item: item.name.lower())
        children = [fs_tree_node(subdir, depth + 1, max_depth) for subdir in subdirs] + [
            FsNodeResponse(name=item.name, path=str(item), type="file") for item in files
        ]
    return FsNodeResponse(name=directory.name or str(directory), path=str(directory), type="dir", children=children)


@app.get("/api/fs/tree", response_model=FsNodeResponse)
def get_fs_tree(path: str | None = None, depth: int = FS_TREE_MAX_DEPTH):
    target = Path(path).expanduser() if path else REPO_ROOT
    try:
        target = target.resolve()
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"Cannot resolve path: {path}") from exc
    if not target.exists():
        raise HTTPException(status_code=400, detail=f"Path does not exist: {target}")
    if not target.is_dir():
        raise HTTPException(status_code=400, detail=f"Path is not a directory: {target}")
    return fs_tree_node(target, 0, max(1, min(depth, FS_TREE_MAX_DEPTH)))


@app.post("/api/fs/pick-folder", response_model=PickFolderResponse)
def pick_folder():
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-STA", "-Command", FOLDER_PICK_SCRIPT],
            capture_output=True,
            text=True,
            timeout=FOLDER_PICK_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return PickFolderResponse(path=None)
    if completed.returncode != 0:
        return PickFolderResponse(path=None)
    selected = completed.stdout.strip()
    if not selected or not Path(selected).is_dir():
        return PickFolderResponse(path=None)
    return PickFolderResponse(path=selected)


FS_NAME_BAD_CHARS = set('<>:"|?*')


def resolve_fs_path(raw: str) -> Path:
    try:
        return Path(raw).expanduser().resolve()
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"Cannot resolve path: {raw}") from exc


def validate_fs_name(name: str) -> str:
    name = name.strip()
    if not name or name in {".", ".."} or "/" in name or "\\" in name:
        raise HTTPException(status_code=400, detail=f"Invalid name: {name!r}")
    if any(ch in FS_NAME_BAD_CHARS for ch in name):
        raise HTTPException(status_code=400, detail=f"Invalid name: {name!r}")
    return name


@app.get("/api/fs/read", response_model=FsReadResponse)
def fs_read(path: str):
    target = resolve_fs_path(path)
    if not target.exists():
        raise HTTPException(status_code=400, detail=f"Path does not exist: {target}")
    if target.is_dir():
        raise HTTPException(status_code=400, detail=f"Path is a directory: {target}")
    try:
        content = target.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"Cannot read file: {target}") from exc
    return FsReadResponse(path=str(target), name=target.name, content=content)


@app.post("/api/fs/write", response_model=FsWriteResponse)
def fs_write(req: FsWriteRequest):
    target = resolve_fs_path(req.path)
    if not target.parent.is_dir():
        raise HTTPException(status_code=400, detail=f"Parent directory does not exist: {target.parent}")
    if target.is_dir():
        raise HTTPException(status_code=400, detail=f"Path is a directory: {target}")
    try:
        target.write_text(req.content, encoding="utf-8")
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"Cannot write file: {target}") from exc
    return FsWriteResponse(ok=True, path=str(target))


@app.post("/api/fs/create", response_model=FsCreateResponse)
def fs_create(req: FsCreateRequest):
    parent = resolve_fs_path(req.parent)
    if not parent.is_dir():
        raise HTTPException(status_code=400, detail=f"Parent is not an existing directory: {parent}")
    name = validate_fs_name(req.name)
    target = parent / name
    if target.exists():
        raise HTTPException(status_code=409, detail=f"Already exists: {target}")
    try:
        if req.kind == "dir":
            target.mkdir()
        else:
            target.touch(exist_ok=False)
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"Cannot create: {target}") from exc
    return FsCreateResponse(name=target.name, path=str(target), type=req.kind)


@app.post("/api/fs/delete", response_model=FsDeleteResponse)
def fs_delete(req: FsDeleteRequest):
    target = resolve_fs_path(req.path)
    if target.parent == target:
        raise HTTPException(status_code=400, detail=f"Refusing to delete filesystem root: {target}")
    if not target.exists():
        raise HTTPException(status_code=400, detail=f"Path does not exist: {target}")
    try:
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"Cannot delete: {target}") from exc
    return FsDeleteResponse(ok=True)


@app.get("/api/projects", response_model=ProjectsResponse)
def list_projects():
    return projects_response(read_projects_index())


@app.post("/api/projects", response_model=ProjectsResponse)
def create_project_endpoint(req: ProjectCreateRequest):
    index = read_projects_index()
    create_project(index, req.name)
    return projects_response(index)


@app.post("/api/projects/select", response_model=FilesResponse)
def select_project(req: ProjectSelectRequest):
    index = read_projects_index()
    if req.id not in {project["id"] for project in index["projects"]}:
        raise HTTPException(status_code=404, detail="Project not found")
    index["active_id"] = req.id
    write_projects_index(index)
    name = normalize_name(req.name)
    graph = read_graph(name)
    return files_response(name, graph)


@app.post("/api/projects/rename", response_model=ProjectsResponse)
def rename_project(req: ProjectRenameRequest):
    index = read_projects_index()
    for project in index["projects"]:
        if project["id"] == req.id:
            project["name"] = req.name.strip() or project["name"]
            project["updated_at"] = now_iso()
            write_projects_index(index)
            return projects_response(index)
    raise HTTPException(status_code=404, detail="Project not found")


@app.post("/api/projects/delete", response_model=ProjectsResponse)
def delete_project(req: ProjectSelectRequest):
    index = read_projects_index()
    if req.id not in {project["id"] for project in index["projects"]}:
        raise HTTPException(status_code=404, detail="Project not found")
    shutil.rmtree(project_dir(req.id), ignore_errors=True)
    index["projects"] = [project for project in index["projects"] if project["id"] != req.id]
    if index["active_id"] == req.id:
        index["active_id"] = index["projects"][0]["id"] if index["projects"] else None
    write_projects_index(index)
    return projects_response(index)


@app.post("/api/projects/wipe", response_model=ProjectsResponse)
def wipe_projects():
    shutil.rmtree(WORKSPACE / "projects", ignore_errors=True)
    for suffix in ["human", "context", "explain", *sorted(set(LANGUAGES.values()))]:
        for stale in WORKSPACE.glob(f"*.{suffix}"):
            stale.unlink(missing_ok=True)
    for stale in WORKSPACE.glob("graph*.json"):
        stale.unlink(missing_ok=True)
    index = empty_projects_index()
    write_projects_index(index)
    return projects_response(index)


@app.get("/api/files", response_model=FilesResponse)
def get_files(name: str = PROGRAM_NAME):
    name = normalize_name(name)
    graph = read_graph(name)
    return files_response(name, graph)


@app.post("/api/bundle", response_model=BundleResponse)
def get_bundle(req: BundleRequest):
    graph = read_graph(normalize_name(req.name))
    return bundle_for_human(graph, req.humanHash)


@app.post("/api/save", response_model=FilesResponse)
def save_files(req: SaveRequest):
    name = normalize_name(req.name)
    graph = read_graph(name)

    if req.human is not None:
        ensure_human(graph, req.human)

    if req.context is not None:
        human_hash, previous_context_hash, _ = active_hashes(graph)
        previous_context_node = graph["contexts"].get(previous_context_hash) if previous_context_hash else None
        if req.context.strip():
            if previous_context_node is not None and previous_context_node.get("role") == "split":
                save_split_context(graph, req.context, human_hash, previous_context_hash)
            else:
                provenance = None
                if content_hash(req.context) not in graph["contexts"]:
                    provenance = context_provenance_from_manual_edit(previous_context_node, req.context)
                ensure_context(graph, req.context, human_hash, provenance=provenance, parent_context_hash=previous_context_hash)
        elif human_hash:
            graph["humans"][human_hash]["context_hash"] = None
            touch(graph["humans"][human_hash])

    if req.python is not None:
        _, context_hash, python_hash = active_hashes(graph)
        if req.python.strip():
            previous_python = graph["pythons"].get(python_hash) if python_hash else None
            ensure_python(graph, req.python, context_hash, language=node_language(previous_python))
        elif context_hash:
            graph["contexts"][context_hash]["python_hash"] = None
            touch(graph["contexts"][context_hash])

    write_graph(name, graph)
    materialize_current(name, graph)
    return files_response(name, graph)


@app.post("/api/save-unit", response_model=FilesResponse)
def save_unit(req: SaveUnitRequest):
    name = normalize_name(req.name)
    graph = read_graph(name)
    _, context_hash, _ = active_hashes(graph)
    context_node = graph["contexts"].get(context_hash) if context_hash else None
    if not context_node or context_node.get("role") != "split":
        raise HTTPException(status_code=400, detail="Active context is not a split context")
    targets = {section["target"] for section in parse_split_sections(context_node["text"])}
    if req.target not in targets or req.target.endswith(".context") or not valid_split_target(req.target):
        raise HTTPException(status_code=400, detail=f"Target {req.target} is not a unit of the active split context")
    code_hash = ensure_python(graph, req.code, context_hash, language=target_language(req.target))
    graph["pythons"][code_hash]["target"] = req.target
    graph["pythons"][code_hash]["provenance"] = unit_provenance_for_split(
        context_node.get("provenance", []), req.target, req.code
    )
    write_graph(name, graph)
    materialize_current(name, graph)
    return files_response(name, graph)


def reword_split_sources(graph: dict[str, Any], human: str, old_phrase: str, new_phrase: str) -> None:
    old_phrase = old_phrase.strip()
    new_phrase = new_phrase.strip()
    if not old_phrase or not new_phrase or old_phrase == new_phrase:
        return
    for entry in (graph.get("phrases") or {}).values():
        if isinstance(entry, dict) and entry.get("text") == old_phrase:
            entry["text"] = new_phrase
            entry["line"] = phrase_line_in_human(human, new_phrase)
    memo = phrase_memo(graph)
    stored = next((phrases for phrases in memo.values() if old_phrase in phrases), None)
    if stored is None:
        return
    for line in human.splitlines():
        words = line.split()
        if not words or find_word_span(words, new_phrase.split()) is None:
            continue
        key = " ".join(words)
        memo[key] = [new_phrase if phrase == old_phrase else phrase for phrase in memo.get(key, stored)]
        return


@app.post("/api/reword", response_model=FilesResponse)
def reword(req: RewordRequest):
    name = normalize_name(req.name)
    graph = read_graph(name)
    _, context_hash, python_hash = active_hashes(graph)
    if not context_hash or not python_hash:
        raise HTTPException(status_code=400, detail="nothing compiled to rebind")

    human_hash = ensure_human(graph, req.human)
    human = graph["humans"][human_hash]
    human["context_hash"] = context_hash
    touch(human)

    context = graph["contexts"][context_hash]
    human_hashes = context.setdefault("human_hashes", [])
    if human_hash not in human_hashes:
        human_hashes.append(human_hash)
    context["python_hash"] = python_hash

    role = context.get("role", "leaf")
    if role == "direct":
        python = graph["pythons"][python_hash]
        python["provenance"] = python_provenance_for_direct(graph, req.human, python["text"], name, node_language(python))
        context["provenance"] = [
            {
                "line": 1,
                "status": "added",
                "source": f'human phrase "{req.human.strip()}"',
                "text": context["text"].strip(),
            }
        ]
    elif role == "split":
        if req.oldPhrase is not None and req.newPhrase is not None:
            reword_split_sources(graph, req.human, req.oldPhrase, req.newPhrase)
    else:
        context["provenance"] = context_provenance_from_scratch(req.human, context["text"])
    touch(context)

    write_graph(name, graph)
    materialize_current(name, graph)
    return files_response(name, graph)


@app.post("/api/checkout", response_model=FilesResponse)
def checkout(req: CheckoutRequest):
    name = normalize_name(req.name)
    graph = read_graph(name)

    if req.kind == "human":
        if req.hash not in graph["humans"]:
            raise HTTPException(status_code=404, detail="Human snapshot not found")
        graph["current_human_hash"] = req.hash
    elif req.kind == "context":
        context = graph["contexts"].get(req.hash)
        if not context:
            raise HTTPException(status_code=404, detail="Context snapshot not found")
        human_hash = resolve_checkout_human_hash(graph, context)
        if not human_hash:
            raise HTTPException(status_code=404, detail="Parent human snapshot not found")
        graph["current_human_hash"] = human_hash
        graph["humans"][human_hash]["context_hash"] = req.hash
    elif req.kind == "python":
        python = graph["pythons"].get(req.hash)
        if not python:
            raise HTTPException(status_code=404, detail="Python snapshot not found")
        context_hash = resolve_checkout_context_hash(graph, python)
        context = graph["contexts"].get(context_hash) if context_hash else None
        if not context:
            raise HTTPException(status_code=404, detail="Parent context snapshot not found")
        human_hash = resolve_checkout_human_hash(graph, context)
        if not human_hash:
            raise HTTPException(status_code=404, detail="Parent human snapshot not found")
        graph["current_human_hash"] = human_hash
        graph["humans"][human_hash]["context_hash"] = context_hash
        graph["contexts"][context_hash]["python_hash"] = req.hash

    write_graph(name, graph)
    materialize_current(name, graph)
    return files_response(name, graph)


@app.post("/api/delete", response_model=FilesResponse)
def delete(req: DeleteRequest):
    name = normalize_name(req.name)
    graph = read_graph(name)
    delete_snapshot(graph, req.kind, req.hash)
    write_graph(name, graph)
    materialize_current(name, graph)
    return files_response(name, graph)


@app.post("/api/human-to-context", response_model=FilesResponse)
def human_to_context_endpoint(req: HumanRequest):
    name = normalize_name(req.name)
    language = normalize_language(req.language)
    graph = read_graph(name)
    resolve_adaptive_context(graph, req, language)
    write_graph(name, graph)
    materialize_current(name, graph)
    return files_response(name, graph)


@app.post("/api/human-to-split", response_model=FilesResponse)
def human_to_split_endpoint(req: HumanRequest):
    name = normalize_name(req.name)
    language = normalize_language(req.language)
    graph = read_graph(name)
    human_hash = ensure_human(graph, req.human)
    human = graph["humans"][human_hash]
    current_context = graph["contexts"].get(human.get("context_hash")) if human.get("context_hash") else None

    if not current_context or current_context.get("role") != "split" or req.force:
        context = human_to_split(req.human, language)
        ensure_split_context(graph, context, human_hash, req.human)

    write_graph(name, graph)
    materialize_current(name, graph)
    return files_response(name, graph)


@app.post("/api/context-to-python", response_model=FilesResponse)
def context_to_python_endpoint(req: ContextRequest):
    name = normalize_name(req.name)
    language = normalize_language(req.language)
    graph = read_graph(name)
    human_hash, previous_context_hash, _ = active_hashes(graph)
    previous_context_node = graph["contexts"].get(previous_context_hash) if previous_context_hash else None
    provenance = None
    if content_hash(req.context) not in graph["contexts"]:
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
        code = context_to_code(req.context, language)
        ensure_python(graph, code, context_hash, language=language)

    write_graph(name, graph)
    materialize_current(name, graph)
    return files_response(name, graph)


@app.post("/api/compile-all", response_model=FilesResponse)
def compile_all(req: HumanRequest):
    name = normalize_name(req.name)
    language = normalize_language(req.language)
    graph = read_graph(name)
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
        code = context_to_code(context, language)
        ensure_python(graph, code, context_hash, language=language)

    write_graph(name, graph)
    materialize_current(name, graph)
    return files_response(name, graph)


@app.post("/api/compile", response_model=FilesResponse)
def compile_endpoint(req: HumanRequest):
    name = normalize_name(req.name)
    language = normalize_language(req.language)
    graph = read_graph(name)
    cached = graph["humans"].get(content_hash(req.human))

    if cached and cached.get("context_hash") and not req.force:
        ensure_human(graph, req.human)
        complete_python(graph, cached["context_hash"], req.human, name, language=language)
        write_graph(name, graph)
        materialize_current(name, graph)
        return files_response(name, graph)

    route = decide_compile_route(req.human)
    if route == "direct":
        human_hash = ensure_human(graph, req.human)
        marker = direct_context_text(human_hash)
        provenance = [
            {
                "line": 1,
                "status": "added",
                "source": f'human phrase "{req.human.strip()}"',
                "text": marker.strip(),
            }
        ]
        context_hash = ensure_context(graph, marker, human_hash, provenance=provenance, role="direct")
        code_text = human_to_code(req.human, language)
        code_hash = ensure_python(graph, code_text, context_hash, language=language)
        graph["pythons"][code_hash]["provenance"] = python_provenance_for_direct(graph, req.human, code_text, name, language)
    else:
        context_hash = resolve_adaptive_context(graph, req, language)
        complete_python(graph, context_hash, req.human, name, force=req.force, language=language)

    write_graph(name, graph)
    materialize_current(name, graph)
    return files_response(name, graph)


@app.post("/api/adopt", response_model=FilesResponse)
def adopt(req: AdoptRequest):
    name = normalize_name(req.name)
    graph = read_graph(name)
    if graph.get("current_human_hash"):
        return files_response(name, graph)
    seeded = seeded_disk_texts(name)
    if seeded is None:
        return files_response(name, graph)
    human, context = seeded

    human_hash = ensure_human(graph, human)
    if context.strip():
        sections = parse_split_sections(context)
        if sections:
            context_hash = ensure_split_context(graph, context, human_hash, human)
            adopt_split_children(graph, context_hash, name)
        else:
            provenance = context_provenance_from_scratch(human, context)
            context_hash = ensure_context(graph, context, human_hash, provenance=provenance, role="leaf")
            adopt_leaf_code(graph, context_hash, name)

    write_graph(name, graph)
    materialize_current(name, graph)
    return files_response(name, graph)
