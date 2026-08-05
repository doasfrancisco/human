# fran

A REPL over the DAG. The filesystem is the DAG, `lang/` is the compiler, and the
cache is what makes it a compiler instead of a prompt pipeline.

```
repl/
  lang/      the language, in .human   <- editing this changes the compiler
  progs/     programs, in .human
  .cache/    content-addressed model calls
  build/     generated .py + line->node provenance map
  fran.py    the engine
```

## Run it

```
uv run fran.py                 # repl
uv run fran.py lower progs/x   # one-shot, recursive
uv run fran.py build progs/x   # compile to build/x/main.py
uv run fran.py check progs/x
```

`fran` is a compiler. It compiles to `build/<name>/main.py` and stops. Running the
program is your shell's job, not the language's: `python build/x/main.py`.

`uv` resolves the environment on first run; there is nothing to activate.

Credentials are read from `repl/.env`, the repo root `.env`, or
`web_editor/project/backend/.env`, in that order. Needs `AWS_BEARER_TOKEN_BEDROCK`,
`AWS_REGION`, and optionally `BEDROCK_MODEL_ID`.

## Primitives

**node** — text plus a link to the node above it. A node is a file:
`progs/sort.human` is the root, its children are `progs/sort/1.human`,
`progs/sort/2.human`, and so on. The parent is the directory you are in. There is
no node table and no database; the tree on disk is the tree in memory.

**lower** — `node -> [node]`. Proposes children for one node, in the context of its
ancestors (why it exists) and its siblings (what is already covered), and then
**throws away the ones that do not change the code**. See below — this is the whole
design.

**check** — `(parent, child) -> bool`. Two tiers, both mechanical. A node carrying
an `assert:` line is evaluated against the compiled program: that is *sound*. Every
other node is *ablated*. There is no model-judged tier — asking the model whether it
agrees with itself is not a check.

**cache** — `hash(kind, model id, lang hash, prompt hash, key parts) -> output`. The
load-bearing piece. It is what makes an untouched program recompile byte-identical
and an edit invalidate exactly the nodes it should. Each stage mixes in the hash of
its *own* system prompt, so editing the codegen prompt does not invalidate lowering.
Without this the language rewrites itself while you are not looking.

## Lowering is earned, not mandated

The first version of `lang/` told the model to expand every node into two to six
children. It obeyed. Insertion sort came out as a 23-node tree over 20 lines of
Python, and 12 of those nodes were provably decorative. The branching floor was a
bug **in the language**, not in the Python.

Now a proposed child has to earn its existence:

> generate the unit's code with the child, then regenerate it without the child. If
> the lines the child claimed survive its deletion, it never caused them. Discard it.

`lang/levels.human` states the rule in one line — *a node is a leaf until proven
otherwise* — and `discipline.human` names the trap: a name you already know
("insertion sort", "binary search") determines its own steps, so decomposing it
yields nodes that *describe* the code instead of *causing* it. **Zero children is a
common and correct answer.** Depth is not a virtue.

The naive version of this test does not work, and the failure is instructive.
Regenerating from scratch without the node changes the code for reasons that have
nothing to do with the node — the model re-signs a function, inverts a branch — and
the gate reads that drift as causation. It happens at temperature 0, from cache, so
it is not sampling noise. The fix is **anchored regeneration**: the without-node
prompt carries the baseline code and is told to preserve every line the remaining
nodes still imply, changing only what the removal forces. That biases hard toward
*keeping* lines, which makes `caused` harder to earn — which is the direction an
honest measure should lean.

`+ <text>` is the escape hatch. A child you write yourself is never auto-discarded.
The gate prunes the model's proposals, not your decisions.

## Ablation

The same predicate, run after the fact, is what makes provenance non-decorative.
Delete a node, regenerate its unit anchored, and compare the lines it *claimed*
against the lines that survived.

```
caused        the lines it claimed vanished when it was deleted. sound.
DECORATIVE    its lines survived its deletion. it never caused them.
partial       it caused some of the lines it claimed.
unattributed  it causes code, but the map credits another node.
inert         deleting it changes nothing. the node is ceremony.
```

The gate and the audit are one function. A node that could not get past `lower` is
the same node `check` would call DECORATIVE.

**The sharpest thing this found:** a node can visibly change the code and still be
DECORATIVE. In the shortener, *"a negative ttl is also treated as never expiring"*
rewrites `ttl == 0` into `ttl <= 0` — a real, visible diff. Ablation calls it
DECORATIVE anyway, because under anchored regeneration that line **survives the
node's deletion**: the parent's ttl-zero decision already implies it. *Changing the
output* and *causing a line* are different questions, and only the second one is
provenance.

## Units and the contract

Code is generated one *unit* at a time, where a unit is a child of the program root.
The subtree under a unit is its detail, not separate code. That is what buys
locality: editing a node three levels down regenerates one unit and leaves every
other unit byte-identical, straight from the cache.

But a unit that only sees its own subtree cannot know what the other units named.
The first shortener compiled and did not run: two `def resolve` with different
signatures, three different entry schemas, a stray `ttl_map`. `assemble()`
concatenates, and the later `def` silently wins.

So there is a **contract** stage: one model call, before codegen, that fixes the
shared names and the shape of the shared state. It is cached at *unit-text* grain —
it only depends on the root and the unit sentences — so a deep edit still hits the
cache and locality survives. Two mechanical rules back it up:

- **A name defined by two units is a compile error**, naming both nodes. This is
  what caught the first bug, and it immediately caught a second: the contract had
  left one unit owning *no* name at all, so its only way to speak was to redefine
  someone else's. Every unit must now own at least one name.
- **Cross-unit imports are stripped.** Units are concatenated into one module; a
  unit that writes `from unit3 import ...` has hallucinated a file that will never
  exist.

## The invariant

Every node except the root has a parent, and every generated line is caused by
exactly one node. Code that runs but cannot say which human phrase caused it is a
failed compile. `why <n>` is that claim, made answerable — and every owner in
`main.map.json` is a path that exists on disk, not a plausible-looking string.

## Commands

There are three primitives, so there are almost no commands. Typing text *is* the
language; the rest is just moving a cursor.

```
<text>              write. at / it starts a program; on a node it rewrites it.
+ <text>            add a child to the cursor. your words. never auto-discarded.
ls [-r]             the cursor's text and its children, numbered
cd <n|path|..|/>    move the cursor
edit                open $EDITOR on the cursor, for longer text
lower [-r]          propose children, keep only the ones that change the code.
                    a node whose children change nothing is a leaf. -r recurses
                    into the survivors only.
build [-p]          compile the nodes that exist to build/. it does not lower.
                    -p prints the code.
why [<line>]        why this node exists, or what caused line <n> of the build
check               run the assertions, then ablate every node. the honest measure.
quit
```

`build` compiles what is there and does not lower behind your back — a build that
silently expanded the tree would hide the one decision you came to make. It prints
the provenance ratio from the cache without spending a model call; if the tree has
never been ablated it says so and tells you to run `check`.

**`build` does not execute your program.** It writes `build/<name>/main.py` and the
line→node map, and tells you the path. Launching the artifact is the shell's job.
The only thing that ever executes generated code is `check`, and only because an
assertion is a claim about behaviour and there is no other way to settle it — it
imports the module with `__name__` set to `fran_check`, so the `__main__` demo block
does not fire, then evaluates each `assert:` expression against it.

There is no `new`: type what you want and it exists. There is no `ablate`: it is
what `check` does. There is no model-judged tier: ablation supersedes it, so the
"ask the model whether it agrees with itself" stage was deleted rather than kept as
decoration.

## Where it stands

**insertion sort** — 3 nodes, 2 units, both leaves. `2 proposed, 2 earned, 0
discarded`. 14 lines of Python. `provenance: 2/2 units own code, no nodes below the
unit line`. Under the old mandated-branching language this was 23 nodes, 12 of them
DECORATIVE.

**an in-memory url shortener** (refuses a taken alias, expires links after a
configurable ttl, counts follows) — 7 nodes, 5 units. 54 lines. No name collisions.
`tests: 5/5 passed`. `provenance: 5/5 units own code, 0/1 nodes below the unit line
earned (DECORATIVE 1)` — that one being the ttl node described above.

**Zero DECORATIVE verdicts survive lowering anymore.** They can only appear on nodes
you added by hand with `+`, which is exactly as intended: the gate prunes the
model's guesses and audits yours.

**Locality holds.** Adding a child three levels down and rebuilding: contract
`cache=HIT`, four of five units byte-identical from cache, one unit regenerated —
**one model call for the whole rebuild.** Shallow edits are global, deep edits are
local, and that is the property the whole unit/contract split exists to protect.

The assertions were checked against deliberately broken copies of the generated
program — hits that never increment, an `is_expired` that always returns False, a
dropped `ttl > 0` guard — and each assertion fails under exactly the mutation aimed
at it and no other. A test suite that passes on broken code is not a test suite.

## Self-hosting

`lang/` is nodes like anything else. Change `lang/defaults.human` from "sorts ascend"
to "sorts descend", lower a fresh program, and the tree comes back with `default:
sort descends unless the caller specifies otherwise` as an exposed node. You changed
the language using the language. No Python was edited, no compiler was bootstrapped.

The `lang` hash is in every cache key, so a language edit invalidates exactly the
nodes that depended on it and nothing else drifts. The stage prompts inside `fran.py`
are compiler too, so each one hashes itself into its own kind's key.

## What is deliberately missing

`raise` (code -> intent). It doubles the core and makes "what is the source of truth"
unanswerable. The arrow points one way: edit at the level you mean, and lower again.
