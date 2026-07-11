# v0.0.5 backend

FastAPI backend for the `.human -> .context -> .py` pipeline.

The backend holds multiple named projects. Each project has its own content-addressed compile graph in `workspace/projects/<project_id>/graph.json`, and `workspace/projects.json` is the index with the active-project pointer. Exact `.human` text is cached per project, so returning to a previous `.human` restores the `.context` and `.py` generated for that snapshot. If no project exists, the first graph access auto-creates an empty project named `untitled`.

## Run with uv

```bash
uv sync
uv run fastapi run main.py --host 0.0.0.0 --port 8000
```

For development reload, use:

```bash
uv run fastapi dev main.py --port 8000
```

The backend loads the nearest `.env` above this folder. The repo root `.env` should define `AWS_BEARER_TOKEN_BEDROCK`.

## Endpoints

Projects (each returns the project list unless noted):

- `GET /api/projects`
- `POST /api/projects` `{ "name" }` — create an empty project and make it active
- `POST /api/projects/select` `{ "id" }` — set the active project, returns the `Files` shape
- `POST /api/projects/rename` `{ "id", "name" }`
- `POST /api/projects/delete` `{ "id" }` — if it was active, another project (or none) becomes active
- `POST /api/projects/wipe` — delete all projects and reset the index

Active-project compile graph:

- `GET /api/files`
- `POST /api/save`
- `POST /api/checkout`
- `POST /api/delete`
- `POST /api/bundle`
- `POST /api/human-to-context` — adaptive, auto-decides leaf vs split, stops at `.context`
- `POST /api/human-to-split`
- `POST /api/context-to-python`
- `POST /api/compile` `{ "human", "force" }` — primary compile: triages direct vs context, always produces `.py`; on the direct path the `Files` response carries `pythonProvenance` mapping human phrases to `.py` lines (empty for leaf/split)
- `POST /api/compile-all` — legacy non-adaptive pipeline, kept for back-compat
