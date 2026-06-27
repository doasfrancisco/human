# v0.0.4 — `.human` → `.context` → `.py`

A toy compiler with three explicit stages and a deterministic intermediate representation.

```
.human   →   .context   →   .py
 (text)      (JSON IR)     (Python)
```

Where v0.0.3 made Claude the compiler, v0.0.4 is a real Python program. The `.context` file is no longer a bag of bindings learned through Q&A — it's a structured JSON IR. Edit the IR and the generated code changes accordingly.

## How to use it

```powershell
python .\compiler.py .\examples\sort\sort.human
python .\examples\sort\sort.py
```

Output:

```
[1, 2, 3, 4, 5, 6]
```

## Three files per program

```
sort.human     → what you write (free text intent)
sort.context   → what the compiler understood (JSON IR)
sort.py        → what the machine runs (generated code)
```

The `.human` file is yours. The `.context` is derived but inspectable and editable. The `.py` is regenerated on every compile.

## The key idea

`.human` text changes → `.context` changes → `.py` logic changes.

```
insertion sort
```

becomes:

```json
{ "name": "insertion_sort", "order": "ascending", ... }
```

But:

```
insertion sort descending
```

becomes:

```json
{ "name": "insertion_sort", "order": "descending", ... }
```

The text drives the IR, the IR drives the codegen. Same `.human` + same compiler → same `.py`, byte-for-byte.

## Examples

| Folder | Intent | Output |
|---|---|---|
| [`examples/sort/`](./examples/sort/) | `insertion sort` | `def insertion_sort(items): ...` |

## Design docs

- [`COMPILE.md`](./COMPILE.md) — the compile protocol (stages, files, rules).
- [`v4-language.md`](./v4-language.md) — what `.human` looks like, what `.context` looks like.
- [`v4-insights.md`](./v4-insights.md) — why `.context` is JSON, not bindings.

## Hypothesis tested

A deterministic IR sitting between intent and code is enough to make the system debuggable: when the output is wrong, you read the `.context` to see what the compiler understood. The fault line moves from "is the LLM hallucinating?" to "did the IR match my intent?"
