# v0.0.3 — the `.human` language

No traditional compiler. **Claude is the compiler.** The human writes 1–2 lines of intent in a `.human` file. The compiler asks about decisions that are silent when wrong, saves the answers to `.context`, and writes `.py`.

## How to use it

There is no CLI. The runtime is Claude Code. The protocol lives in [`COMPILE.md`](./COMPILE.md) — point Claude at a `.human` file and tell it to compile.

```
User: compile examples/sort/sort.human
Claude: (reads sort.human, checks sort.context, asks about missing decisions,
         updates sort.context, writes sort.py)
```

## Three files per program

```
sort.human     → what you own (intent, immutable)
sort.context   → what the compiler learned (bindings)
sort.py        → what the machine runs (generated code)
```

The `.human` file never changes. The `.context` file grows as the compiler learns. The `.py` file is rewritten on every compile.

## Examples

| Folder | Intent | Size ratio |
|---|---|---|
| [`examples/sort/`](./examples/sort/) | `sort a list` | 1 line → 100+ lines of Python |
| [`examples/btree/`](./examples/btree/) | `b+ tree to sort information` | 1 line → ~100 lines |
| [`examples/morning/`](./examples/morning/) | Notion + Gmail + WhatsApp scheduled report | ~20 lines → ~140 lines |

## Design docs

- [`v3-language.md`](./v3-language.md) — the language spec (syntax, keys, block resolution).
- [`v3-insights.md`](./v3-insights.md) — design notes on how v0.0.3 evolved.
- [`v3-sketches.md`](./v3-sketches.md) — worked programs the language is designed around.

## Hypothesis tested

Humans own silent-when-wrong decisions; the LLM owns everything else. The `.context` file is where the fault line lives. See [`../../silent-when-wrong.md`](../../silent-when-wrong.md) for the principle.
