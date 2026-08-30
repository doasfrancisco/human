# decompile_v3/test/

## Files

- `decompile.py` — the map decompiler: it turns one code file into `map.json`, a tree of simple-english texts over line ranges.
- `decompile.py.pseu` — the pseudocode for `decompile.py`.

## Execution flow

Execution starts in `decompile.py` with `main()`, which takes one file path from the command line. `main()` cuts the file into cells and blocks, then compiles each block bottom-up in call order. For each block, `compile_block()` calls `one_pass()` in a loop: `one_pass()` sends the cells to Bedrock through `ask()`, gates the answer with `check_pass()`, and lifts accepted groups into tree nodes. When every block is one node, `main()` numbers the tree, adds name links with jedi, and writes `map.json` in this folder.
