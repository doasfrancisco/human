# v0.0.1 — TLA+ → Python

Compile a TLA+ subset directly to executable Python classes.

## Run

```bash
python fran.py examples/fizzbuzz.tla            # compile to fizzbuzz.py
python fran.py examples/fizzbuzz.tla -o out.py  # custom output path
python fran.py examples/fizzbuzz.tla --run      # compile and run
python fran.py examples/fizzbuzz.tla --ast      # show parsed AST
```

## Input

TLA+ specifications with a relaxed subset of the language. See [`v1-tla.md`](./v1-tla.md) for the syntax differences from standard TLA+ (mainly `and`/`or` aliases for `/\`/`\/`).

Modules expose `VARIABLES`, `Init`, named actions, and `Next`. An optional `TypeInvariant` is compiled into runtime asserts.

## Output

A Python class with:
- Instance variables initialized from `Init`
- One `do_<action>()` method per action
- A `step()` method that picks an enabled action via `random.choice`
- Optional `check_invariant()` from `TypeInvariant`

## Files

| File | Role |
|---|---|
| `fran.py` | CLI entry point |
| `lexer.py` | TLA+ tokenizer |
| `tla_parser.py` | Tokens → AST |
| `codegen.py` | AST → Python |
| `v1-tla.md` | Syntax notes |
| `examples/` | `.tla` inputs |

## Hypothesis tested

A formal spec language can compile to runnable code. It works — but forces state machines onto problems that don't need them (pure expressions, simple transformations). See [`../../CHANGELOG.md`](../../CHANGELOG.md) for what this taught v0.0.2.
