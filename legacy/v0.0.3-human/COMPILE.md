# Compile protocol

The protocol Claude follows when compiling a `.human` file. Any agent should be able to read this file and perform the same compilation.

## Inputs

- `<name>.human` — the user's intent. Immutable. Never edit this file.
- `<name>.context` — learned bindings. May or may not exist yet.
- `../../.context` — global context shared across programs (optional).
- [`../../silent-when-wrong.md`](../../silent-when-wrong.md) — the rule for what to ask about.

## Output

- `<name>.py` — fully runnable Python. No stubs, no TODOs.
- `<name>.context` (updated) — any new bindings learned during this compile.
- `../../.context` (maybe updated) — if a binding learned here is also referenced by a sibling `.human` file, migrate it up.

## Steps

1. **Read the intent.** Parse `<name>.human` as named blocks with key-value pairs. Block names are identifiers. Keys are semantic slots, not fixed syntax.

2. **Resolve bindings.** For every noun or phrase in the intent:
   - If it matches a block name in the same file → dynamic binding, resolve at runtime.
   - Else if it appears in `<name>.context` → use the bound value.
   - Else if it appears in the global `../../.context` → use the bound value.
   - Else it's an unresolved decision.

3. **Classify unresolved decisions.**
   - **Silent when wrong** (ask the user): wrong guess produces wrong output, not a crash. Thresholds, categories, filter criteria, action choices, routing destinations, schedule times. See [`../../silent-when-wrong.md`](../../silent-when-wrong.md).
   - **Loud when wrong** (decide yourself): wrong guess crashes visibly. Library choices, data-structure implementations, API auth, parsing strategies. Pick, note it in `.context` as a "compiler default," keep going.
   - **Cosmetic** (decide silently): whitespace, variable names, file layout. Do not ask, do not save.

4. **Ask about silent-when-wrong decisions, one at a time, in order.** Save each answer to `<name>.context` immediately under a `user decisions` section. Phrase answers as bindings: `"a list" → tasks from Notion`, `"sort by" → due_date`.

5. **Save compiler defaults.** Any loud-when-wrong decision you made yourself goes under a `compiler defaults (edit to tune)` section in `<name>.context`. The user can tune these later without re-running the interactive compile.

6. **Check for global migrations.** If a binding you just learned matches a noun that appears in a sibling `.human` file in the same directory, move the binding to `../../.context`.

7. **Generate the Python.** Write `<name>.py` top to bottom with:
   - A one-line docstring: `"""Compiled from <name>.human — DO NOT EDIT."""`.
   - Imports.
   - Helper functions.
   - A main flow that implements the intent using the resolved bindings.
   - Runnable example data or `if __name__ == "__main__":` guard so `python <name>.py` works.

8. **Do not ask again.** On the next compile, every binding already in `.context` is reused silently. No questions. Same `.human` + same `.context` → same `.py`.

## Rules

- **The `.human` file is source code.** Only the user edits it.
- **The `.py` file is disposable.** Regenerated on every compile. Never edit by hand.
- **The `.context` file is editable.** The user may tune compiler defaults there.
- **Ask only about silent-when-wrong.** Asking about library choices, loop structure, or error handling is a bug.
- **No stubs.** Generated code must run end-to-end on realistic inputs.
- **One question at a time.** Do not batch five questions in one message.

## Failure modes

- The user says "pick any you like" — that's a delegated decision. Pick, save to `compiler defaults`, continue.
- The intent requires a *policy* (e.g., "fix failing tests" — see [`v3-sketches.md`](./v3-sketches.md) program 5). The current language doesn't cover this. Stop and tell the user the intent isn't compilable by this protocol.
- External service auth missing (Gmail, Notion, WhatsApp) — generate the code anyway; document the env vars the user needs in a comment at the top of the `.py`.
