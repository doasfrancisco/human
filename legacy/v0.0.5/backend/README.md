# v0.0.5 backend

FastAPI backend for the `.human -> .context -> .py` pipeline.

The backend stores a content-addressed compile tree in `workspace/graph.json`. Exact `.human` text is cached, so returning to a previous `.human` restores the `.context` and `.py` generated for that snapshot.

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

- `GET /api/files`
- `POST /api/save`
- `POST /api/checkout`
- `POST /api/human-to-context`
- `POST /api/context-to-python`
- `POST /api/compile-all`
