# fran++ v0.0.4 — the language

## The shape

```
.human   →   .context   →   .py
```

Three files per program. Two transforms. One source of truth.

## `.human`

Free text. Whatever you want to write. No syntax, no keywords.

```
insertion sort
```

```
insertion sort descending
```

The compiler matches the text against known recipes. Variants that mean the same thing collapse to the same IR.

## `.context`

A JSON object — the intermediate representation.

```json
{
  "kind": "algorithm",
  "name": "insertion_sort",
  "input": "list",
  "output": "sorted_list",
  "order": "ascending",
  "stable": true,
  "logic": [
    "start from index 1",
    "store current item as key",
    "move larger previous items one position right",
    "insert key into correct position"
  ]
}
```

Keys aren't a fixed schema. They're whatever the recipe needs. But patterns emerge:

| Key      | What it decides                        |
|----------|----------------------------------------|
| `kind`   | category of program (algorithm, pipeline, rule) |
| `name`   | the canonical algorithm or routine     |
| `input`  | what comes in                          |
| `output` | what goes out                          |
| `order`  | direction (ascending, descending)      |
| `logic`  | the recipe in plain steps              |

## `.py`

Whatever Python the codegen writes. Always runnable. Always regenerable.

```python
def insertion_sort(items):
    items = list(items)

    for i in range(1, len(items)):
        key = items[i]
        j = i - 1

        while j >= 0 and items[j] > key:
            items[j + 1] = items[j]
            j -= 1

        items[j + 1] = key

    return items
```

## How a change propagates

```
.human (you edit)
   │
   │ human_to_context()  — recipe lookup
   ▼
.context (regenerated)
   │
   │ context_to_python() — template fill
   ▼
.py (regenerated)
```

Edit `.human` from `insertion sort` to `insertion sort descending`:
- `order` flips from `"ascending"` to `"descending"` in the IR.
- The comparison in the generated loop flips from `items[j] > key` to `items[j] < key`.

Same input → same output. The whole thing is a pure function.

## Composition (planned)

v0.0.4 ships with a single recipe (insertion sort). Future recipes are added by extending `human_to_context()` and `context_to_python()`. References between programs (the v0.0.3 idea) are not yet in the language.

## What this ISN'T

- **Not v0.0.3.** v0.0.3 made Claude the compiler — interactive Q&A produced bindings. v0.0.4 is a deterministic script with a JSON IR.
- **Not a DSL with a grammar.** There is no parser. The "language" is whatever phrases the recipe table happens to recognize.
- **Not magic.** If the text doesn't match a recipe, the compiler raises. Adding intents means writing recipes.
