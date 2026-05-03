# fran++ v0.0.4 insights

## Why a JSON IR

v0.0.3 had `.context` as a list of bindings learned through Q&A. That worked when Claude was the compiler — bindings are how an LLM thinks. But it left no debuggable artifact: when the output was wrong, you couldn't tell whether the binding was wrong, the resolution was wrong, or the codegen was wrong.

v0.0.4 makes the middle stage explicit and structured:

```
text  →  JSON  →  code
```

When the output is wrong, you read the JSON. If the JSON looks right and the code looks wrong, the bug is in `context_to_python()`. If the JSON looks wrong, the bug is in `human_to_context()` or in the `.human` itself. The fault line is visible.

## The compiler is a Python script

Not Claude. Not an LLM. A deterministic function.

That sounds like a regression from v0.0.3 ("Claude is the compiler"). It is, in capability — v0.0.3 could compile programs no v0.0.4 recipe covers. But v0.0.4 has a property v0.0.3 didn't:

> Same `.human` + same compiler version → same `.py`, byte-for-byte.

Reproducibility matters once you start versioning generated code, diffing across compiles, or running CI against the output.

## Two transforms, not one

The interesting decision is putting `.context` between `.human` and `.py`. A one-shot `human_to_python()` would be shorter — but it would conflate two questions:

1. **What did the user mean?** (handled by `human_to_context`)
2. **How do we implement that?** (handled by `context_to_python`)

Splitting them lets the second one be reused. `insertion sort` and `insertion-sort` and `insertionsort` all mean the same IR, and the IR has one codegen path.

## Editing the IR

`.context` is generated, but it's not sealed. A user who wants `branching_factor: 4` instead of `5` can edit the JSON and re-run the codegen step (currently bundled into `compile_human_file`, but trivially separable).

This is the same fault line v0.0.3 drew between "user decisions" and "compiler defaults" — but expressed as JSON keys rather than Q&A history.

## Limits

- **One recipe.** Insertion sort, ascending or descending. Anything else raises.
- **No composition.** Blocks-referencing-blocks (the v0.0.3 idea) doesn't exist here yet.
- **No global context.** Each `.human` compiles in isolation.
- **No agents.** The compiler doesn't ask questions. If the text is ambiguous, it picks one branch or fails.

These are deliberate. The point of v0.0.4 is to nail the three-stage pipeline on a single example before generalizing.

## What v0.0.4 trades for what

| Property                | v0.0.3 (Claude)         | v0.0.4 (script)          |
|-------------------------|-------------------------|--------------------------|
| Coverage                | open-ended              | one recipe               |
| Determinism             | none                    | total                    |
| Debuggability           | conversation history    | inspectable JSON IR      |
| Cost per compile        | LLM call                | nanoseconds              |
| Adding a new intent     | write `.human`          | write a Python branch    |

v0.0.3 is the language people would want. v0.0.4 is the language people can actually build, version, and trust.
