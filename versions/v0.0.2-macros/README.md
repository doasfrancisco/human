# v0.0.2 — macros + English-like specs

Compile `.fpp` (fran++) files to Python with BFS search. Adds Lisp-style macros that unroll into state machines at compile time.

## Run

```bash
python fran.py examples/coins.fpp                  # compile to coins.py
python fran.py examples/coins.fpp -o out.py        # custom output path
python fran.py examples/coins.fpp --run            # compile and run
python fran.py examples/coins.fpp --ast            # show AST
python fran.py examples/coin_change_macro.fpp --expand  # show macro-expanded source
```

## Input

`.fpp` files with English-flavored keywords: `module`, `variables`, `action`, `when`, `set`, `constraint`, `goal`, `for`, `between`, `macro`.

Two flavors of input:
- Direct state-machine specs (`water_jugs.fpp`, `coins.fpp`).
- Macro calls that unroll into specs at compile time (`coin_change_macro.fpp`).

## Output

Python programs that BFS the state space and print the first solution path.

## Files

| File | Role |
|---|---|
| `fran.py` | CLI entry point |
| `lexer.py` | `.fpp` tokenizer |
| `parser.py` | Tokens → AST |
| `macros.py` | Pre-parse text-level macro expansion |
| `codegen.py` | AST → Python with BFS |
| `v2-macros.md` | Macro design notes |
| `v2-session.html` | Archived Claude design conversation |
| `examples/` | `.fpp` inputs |

## Hypothesis tested

Macros can compress specs without handing logic to an LLM. It works for problems with regular structure (one action per denomination) but a macro is still a programmer writing a program — the LLM can write the macro too. The unsolved question became "what does the human write that the LLM can't?" — which v0.0.3 takes up directly.
