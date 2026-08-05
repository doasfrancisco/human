# refine

One axiom: `refine, text -> text`. A program is a chain of texts. Each text
decides more than the text above it. The chain ends when the text is code.

```
refine/
  refine.py        the compiler, one file
  progs/x/0.human  the human text, plus assert: lines
  progs/x/1.human  more decided
  progs/x/N.py     the fixed point
```

## Laws

1. Conservation. A step never reverses a decision. The asserts check this law.
2. Progress. A step must decide at least one open choice. A step that returns
   the same text is an error.
3. Fixed point. A text that parses as Python is code. The chain stops there.

## Run it

```
uv run refine.py progs/sort            # refine until the fixed point
uv run refine.py progs/sort --step     # one refinement step
uv run refine.py progs/sort --check    # progress diffs + parse + asserts
```

Credentials come from `refine/.env`, the repo root `.env`, or `hand/.env`.
Needs `AWS_REGION` and `BEDROCK_MODEL_ID`.

## Rules of the file format

- A line that starts with `assert:` is a Python expression. `check` evaluates
  it against the compiled module. The refiner never sees these lines.
- Asserts can enter at any level. Once green, they must stay green below.
- Edit any level by hand, delete the levels below it, and build again.

## What is deliberately missing

The cache, the provenance map, and anchored revision. They are implementation,
not axioms. They return when the corpus proves the core works.
