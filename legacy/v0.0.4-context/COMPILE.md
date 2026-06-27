# Compile protocol

Three stages, two files generated, one source of truth.

## Stages

```
                human_to_context()         context_to_python()
   .human   ──────────────────────►   .context   ──────────────────────►   .py
   (text)         (lookup)         (JSON IR)         (template)         (Python)
```

Both functions live in [`compiler.py`](./compiler.py) and are pure: same input → same output.

## Files

- `<name>.human` — source. The user owns it. The compiler never writes here.
- `<name>.context` — IR. Generated from `.human` on every compile. Editable by humans for tuning.
- `<name>.py` — output. Generated from `.context` on every compile. Disposable.

## Steps

1. **Read** `<name>.human` as raw text.
2. **Match** the text against known recipes inside `human_to_context()`. If no match, raise.
3. **Emit IR** — write the chosen recipe as JSON to `<name>.context`.
4. **Codegen** — pass the IR through `context_to_python()` and write `<name>.py`.

## Rules

- **`.human` is text.** No keywords, no syntax. Whatever the user wrote.
- **`.context` is JSON.** Structured, inspectable, deterministic.
- **`.py` is generated.** Never edit by hand.
- **The compiler is a Python script.** Not Claude, not an LLM. Deterministic.
- **Recipes live in code.** Adding a new intent means adding a branch to `human_to_context()` and (maybe) a branch to `context_to_python()`.

## Why two stages instead of one

A single function from text to Python would be opaque. With the IR in the middle:

- You can read the `.context` to verify the compiler understood your intent.
- You can edit the `.context` to tune behavior without touching `.human`.
- The codegen step is reusable across different `.human` phrasings that map to the same IR.

## Failure modes

- **Unknown intent.** `human_to_context()` raises `ValueError`. Add a recipe.
- **IR with no codegen path.** `context_to_python()` raises. Add a branch.
- **Ambiguous text.** Pick a recipe; the user can override by editing `.context` before regenerating `.py` (or by rewriting `.human` to be unambiguous).
