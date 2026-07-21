# human v3

A REPL over the DAG. The filesystem is the DAG, `lang/` is the compiler, the cache is
what makes it a compiler instead of a prompt pipeline — and **meaning is declared at
generation, never measured by deletion.**

```
repl_v3/
  lang/
    lower/     rules that govern proposing children   <- editing this changes the compiler
    code/      rules that govern emitting python + the declared node->char map
    revise/    rules that govern the minimal-diff rebuild after an edit
  progs/       programs, in .human
  .cache/      content-addressed model calls
  build/       generated .py + the declared char-range map
  human_compiler.py  the compiler
  repl.py            the repl that imports it
```

## Run it

```
uv run repl.py                    # repl
uv run repl.py lower progs/fizzbuzz   # one-shot, recursive
uv run repl.py build progs/fizzbuzz   # compile to build/fizzbuzz/main.py + map
uv run repl.py check progs/fizzbuzz   # build, then run the assertions
uv run repl.py fold  progs/fizzbuzz   # view one sentence up from the children
```

`human` compiles to `build/<name>/main.py` and stops. Running the program is your
shell's job: `python build/fizzbuzz/main.py`. Credentials come from `repl_v3/.env` or the
repo root `.env`: `AWS_BEARER_TOKEN_BEDROCK`, `AWS_REGION`, optional `BEDROCK_MODEL_ID`.

## The five things v3 does that v2 did not

**1. Provenance is declared, not ablated.** v2 discovered which node caused which line by
deleting the node, regenerating, and diffing whole lines — so a node had to be a set of
whole lines. v3's single code call returns `{code, map}` in one act. The map is a list of
`{node, kind, ranges}`, where a range is a `[start, end]` pair of **character offsets** into
the source. Ranges may overlap and need not be contiguous, so a node can own any shape, not
a line. No node is ever deleted to find out what it did.

**2. Identity is separate from wording.** A node's `@id:` line is its stable identity; the
human text is its current rendering. Reword the text and the id is untouched. The build
records, per node, the rendering it was compiled from, so an edit can be compared against
what the build currently assumes.

**3. Edits are classified: reword vs revise.** Rewrite a built node and the compiler asks
whether the new wording means the same thing for the code it implies. **reword** — same
meaning — updates the text and keeps the build bytes, no rebuild. **revise** — meaning
changed — rebuilds as the *smallest change* the edit forces, reusing v2's anchoring so
untouched lines survive byte for byte.

**4. The abstraction dial.** Work at whatever altitude you choose. **lower** takes one idea
to its child ideas — and because provenance is now declared, none are ablated; a child the
map attributes no region to is flagged *decorative*, not deleted. **fold** is the inverse:
read the children, view one summarizing sentence up. **why** reads the declared map for the
node you are on and prints the code regions it owns, marking specified vs assumed.

**5. Underspecification is tolerated.** If the tree underspecifies the program, the code
stage builds it anyway, fills the gap with a convention, and tags that region `assumed`.
`why` and `check` surface the assumed regions so you can drill in and override them. The
compiler never refuses to build for lack of detail.

## Ground truth is the asserts

Because meaning is now the model's *declaration* rather than a *measurement*, the only real
safety net is assertions. A node line beginning `assert:` is a Python expression evaluated
by `check` against the compiled module, imported with `__name__` set to `human_check` so the
`__main__` demo does not fire. `raises(exc, fn, *a)` is in the eval namespace. **Codegen
never sees the assertion lines.** The invariant is: touch a node, rebuild, the asserts stay
green.

## The transport

`code` and `revise` return one JSON object `{code, map}`. Both run the code through
`ast.parse`; on a `SyntaxError` or a missing/empty `code` string the compiler calls again
with the exact complaint appended and asks for a fix — up to two rounds, then a hard
`Malformed`. A retry at temperature 0 must change the prompt or it only fails twice as slowly.

## The cache

`hash(kind, model id, lang hash for that kind, stage prompt hash, key parts) -> output`.
Each stage mixes in the hash of only the `lang/` folder it reads and of its own system
prompt, so editing the codegen sheet does not invalidate lowering. An untouched program
recompiles byte-identical; an edit invalidates exactly the nodes it should.

## What is deliberately missing

`raise` (code -> intent). The arrow points one way: edit at the level you mean, lower or
fold to change altitude, and rebuild. The engine stays small on purpose — a compiler bigger
than the largest program it can emit could never compile itself.
