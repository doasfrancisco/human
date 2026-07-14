# fran v2

A REPL over the DAG. The filesystem is the DAG, `lang/` is the compiler, the cache is
what makes it a compiler instead of a prompt pipeline — and **provenance is measured,
never claimed.**

```
repl_v2/
  lang/
    lower/     rules that govern proposing children   <- editing this changes the compiler
    code/      rules that govern emitting python
    reduce/    rules that govern anchored regeneration
  progs/       programs, in .human
  .cache/      content-addressed model calls
  build/       generated .py + the measured line->node map
  fran.py      the engine
```

## Run it

```
uv run fran.py                 # repl
uv run fran.py lower progs/x   # one-shot, recursive
uv run fran.py build progs/x   # compile to build/x/main.py
uv run fran.py check progs/x   # run the assertions, then ablate every node
```

`fran` is a compiler. It compiles to `build/<name>/main.py` and stops. Running the
program is your shell's job: `python build/x/main.py`.

Credentials come from `repl_v2/.env`, the repo root `.env`, or
`web_editor/project/backend/.env`, in that order. Needs `AWS_BEARER_TOKEN_BEDROCK`,
`AWS_REGION`, and optionally `BEDROCK_MODEL_ID`.

## Primitives

There are three, and there will not be a fourth.

**node** — text plus a link to the node above it. A node is a file: `progs/sort.human`
is the root, its children are `progs/sort/1.human`, `progs/sort/2.human`. The parent is
the directory you are in. No node table, no database; the tree on disk is the tree in
memory.

**lower** — `node -> [node]`. Proposes children, then throws away the ones that do not
cause code.

**check** — `(parent, child) -> bool`. Two tiers, both mechanical. A node carrying an
`assert:` line is evaluated against the compiled program: that is *sound*. Every other
node is *ablated*. There is no model-judged tier — asking the model whether it agrees
with itself is not a check.

## What v2 deleted, and what it cost

v1 generated code one *unit* at a time — a unit being a child of the root — and needed a
**contract** stage to stop the units colliding in the shared namespace. That bought
locality: a deep edit regenerated one unit and the rest came back from cache.

It also made the only number this project produces unfalsifiable. The contract is a
downstream artifact, and it was held **fixed** while ablation deleted the node that
caused it, so any node whose content reached the contract could never be shown to cause
anything. Two more failures followed from the same root: codegen shipped a whole program
as an escaped string inside JSON (on a B-tree it gave up, returned prose, and the parse
crashed), and the model *claimed* the line→node map that nothing checked.

So v2 emits **one program, in one call, into one namespace.** The model cannot collide
with itself, which deletes the contract stage, the name-collision check, the cross-unit
import stripping, and the rule that every unit must own a name. None of it was ported.

**The price is locality, and it is paid deliberately.** A deep edit now costs one
whole-program call instead of a cache hit plus one unit. Locality was a cache
optimization; its price was the soundness of the measurement. The measurement wins.

## Provenance is measured

There is no attribution stage. The model is never asked which node caused which line,
because an answer to that question is a claim, and this compiler exists to not take
claims. The map falls out of ablation:

```
baseline = code(whole tree)
for each node n other than the root:
    variant  = reduce(baseline, tree without n)
    caused(n) = lines(baseline) - lines(variant)
```

Lines are compared with a `Counter` over `rstrip`-ed lines — not a set, not `.strip()`.
Indentation is meaning, and N copies of a line must survive N times. v1 compared
stripped lines as a set, so a duplicated line always looked like it survived its own
node's deletion, and the audit could condemn a node that really did cause its line.

Four things fall out of the measurement, and the last three are **findings, not bugs**:

```
owned       exactly one node caused the line
default     zero nodes caused it. the model's convention, or lang/. no human
            sentence asked for it. report the count.
shared      more than one node caused it. report it.
DECORATIVE  the node caused no line at all.
```

`build` writes the program and says provenance is **unmeasured**. `check` writes
`build/<name>/main.map.json` from the ablation. `why` reads that map, and if it does not
exist it says so and tells you to run `check`. **The map does not exist until you have
paid for it.**

## Lowering is earned, and it is the same function as the audit

A proposed child has to earn its existence: generate the program with it, regenerate
anchored without it, and if the code does not change, it never caused anything. Discard
it. That is exactly what `check` does after the fact — one function, called from both
places. A node that could not get past `lower` is the same node `check` would call
DECORATIVE.

`lang/lower/levels.human` states the rule — *a node is a leaf until proven otherwise* —
and `discipline.human` names the trap: a name you already know ("insertion sort",
"binary search") determines its own steps, so decomposing it yields nodes that
*describe* the code instead of *causing* it. **Zero children is a common and correct
answer.** Depth is not a virtue.

The naive version of the test does not work. Regenerating from scratch without a node
changes the code for reasons that have nothing to do with the node — the model re-signs
a function, inverts a branch — and the gate reads that drift as causation. It happens at
temperature 0, so it is not sampling noise. The fix is **anchored regeneration**: the
without-node prompt carries the baseline and is told to make only the change the removal
forces. That biases hard toward *keeping* lines, which makes `caused` harder to earn —
the direction an honest measure should lean. `lang/reduce/` is that instruction, and
`drift.human` tells the model why: what it returns is not read as a program, it is read
as a measurement, so a line it moves for a reason of its own is a lie about a human
being.

`+ <text>` is the escape hatch. A child you write yourself is never auto-discarded. The
gate prunes the model's proposals and audits your decisions.

## Assertions are invisible to codegen

A node line beginning `assert:` is a Python expression evaluated by `check` against the
compiled module, imported with `__name__` set to `fran_check` so the `__main__` demo
block does not fire. **Codegen and reduce never see assertion lines.** They are stripped
from every prompt.

This is the whole point. If an assertion fails because the `.human` text never said
which exception to raise, or never named the function, that is a **true finding**: the
text is underspecified and the compiler just proved it. The wrong fix is to show the
assertion to codegen. That is teaching to the test.

It follows that **the interface is part of the intent.** With no contract stage, nothing
fixes the names but the human sentence, so a root that wants to be tested has to say
what its entry points are called. `progs/lru_cache.human` says *"exposed as a class
LRU(capacity) with get(key) ... and put(key, value)"* — that is specification, not
teaching to the test. A root that names no interface and asserts against one is asserting
against a program nobody wrote, and it deserves the `NameError` it gets.

## The corpus

A language with two programs has never been measured. Six roots, spanning small to
large and pure to stateful. Each is a **root only** — a single sentence of intent, plus
assertions. The children are the compiler's job to earn, and none of them exist yet.

```
progs/insertion_sort.human        small,  pure       the one v1 could not compile
progs/json_pretty_printer.human   medium, pure       exact whitespace is the test
progs/tokenizer.human             medium, pure       multi-char runs, and a hard error
progs/lru_cache.human             medium, stateful   eviction order: an fifo fails it
progs/url_shortener.human         medium, stateful   aliases, ttl expiry, hit counts
progs/b_tree.human                large,  stateful   the one that crashed v1's transport
```

The assertions are written to be **falsifiable**: an in-place `sort` fails insertion
sort's non-mutation claim, a FIFO cache fails the LRU's eviction claim, a b-tree that
loses a key on split fails `keys() == sorted(...)`, and a pretty-printer that reaches
for `repr` fails on `true` and `null`. An assertion that passes on a broken program is
not an assertion. Whether these hold is settled by the first real `check`, not here.

## The parse-repair loop

`code` and `reduce` return **a fenced ```python block, not JSON.** The transport was a
bug: asked for a whole program as an escaped JSON string plus a line map, the model gave
up on the B-tree and returned prose, and the compiler crashed on the parse.

Both stages run their output through `ast.parse`. On `SyntaxError`, fran calls again
with the broken code and the exact error appended, and asks for a fix — up to two rounds,
then a hard failure naming the program. A retry with an identical prompt at temperature 0
is a wasted call; if you retry, the prompt must change. v1 retried byte-identical
prompts twice and could only ever fail twice as slowly.

Nothing in v2 swallows a parse error. v1 did, in two places, and one of them turned a
malformed program into a build on disk. `lang/code/code.human` now also states outright
that the module must parse and that indentation is four spaces per level — v1 never said
so anywhere, and the model emitted a one-space-indented function body at temperature 0
and insertion sort stopped compiling.

## The cache

`hash(kind, model id, lang hash for that kind, stage prompt hash, key parts) -> output`.
The load-bearing piece: it is what makes an untouched program recompile byte-identical
and an edit invalidate exactly the nodes it should. Each stage mixes in the hash of only
the `lang/` folder it reads and of its *own* system prompt, so editing the codegen sheet
does not invalidate lowering. `lower` is idempotent: the expand key includes the children
that already exist, so lowering twice does not grow a second set of twins.

## Self-hosting

`lang/` is nodes like anything else, and `cd` reaches it from `/`. Change
`lang/lower/defaults.human` from "sorts ascend" to "sorts descend", lower a fresh
program, and the tree comes back with the descending default as an exposed node. You
changed the language using the language, and no Python was edited.

The engine is meant to stay **under 250 lines of Python**. That is not an aesthetic. One
model call emits about 300 lines, and a compiler bigger than the largest program it can
emit can never compile itself. Every line saved is a line closer to `progs/fran.human`.

## Where it stands

Nothing has been measured yet. This table is the shape of the answer, not the answer;
every dash is a number nobody has run.

```
program              nodes   lines   tests   owned   default   shared   DECORATIVE
insertion_sort         -       -      -/-      -        -         -          -
json_pretty_printer    -       -      -/-      -        -         -          -
tokenizer              -       -      -/-      -        -         -          -
lru_cache              -       -      -/-      -        -         -          -
url_shortener          -       -      -/-      -        -         -          -
b_tree                 -       -      -/-      -        -         -          -
```

Fill it in from a real `check`, and from nothing else. v1's README reported that all
five of its units owned code — a number produced by a code path that returned `caused`
without deleting anything or regenerating anything — while the program it described did
not compile. **A README that reports a number nobody measured is the exact bug this
compiler exists to detect.**

## The recurring bug

Five separate times in v1 the bug was **a check too weak to fail**: an import-only smoke
test, a gate that read model drift as causation, a collision check that switched itself
off exactly when the code was malformed enough to need it, an ablation that never ablated
the nodes it graded, a reduce prompt that fed the answer back to itself.

For every check here, ask what would make it fail — and make it fail on purpose before
trusting it green.

## What is deliberately missing

`raise` (code -> intent). It doubles the core and makes "what is the source of truth"
unanswerable. The arrow points one way: edit at the level you mean, and lower again.
