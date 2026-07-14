# EXPLAIN

Two parts. Part 1 is how fran works. Part 2 is what is broken in it.

---

# Part 1 — How it works

You write English. fran writes Python. Every line of the Python can name the
English sentence that caused it. That is the whole pitch. Here is the machinery.

## 1. A node is a file. The folder tree is the graph.

A **node** is one `.human` file holding one sentence. Its children live in a
folder with the same name. That is it. There is no database, no node table, no
graph format. The directory tree on disk *is* the graph.

The url shortener in this repo:

```
progs/an_in_memory.human      <- the root
progs/an_in_memory/1.human    <- its children
progs/an_in_memory/2.human
progs/an_in_memory/3.human
progs/an_in_memory/3/1.human  <- a child of 3
progs/an_in_memory/4.human
progs/an_in_memory/5.human
```

`progs/an_in_memory.human` contains one line:

> an in-memory url shortener that refuses a custom alias if it is already taken,
> expires links after a configurable ttl, and returns the number of times each
> link was followed

`progs/an_in_memory/1.human` contains:

> store mappings in a dict keyed by short code, with creation timestamp, ttl, and
> hit count per entry

The parent of a node is the directory it sits in. `progs/an_in_memory/3/1.human`
is a child of `progs/an_in_memory/3.human` because it is inside the folder named
`3`. `mv` a file and you have edited the graph. Seven files, seven nodes.

A node can also carry an `assert:` line. That is a test, and it is the only thing
in the tree that is not prose. More on it in section 4.

## 2. Lowering: propose children, then throw most of them away

**Lowering** takes one node and asks the model for children — the next level of
English, not code. Then it does the part that matters: it **deletes the children
that do not change the generated Python**.

The test for each proposed child is mechanical:

1. Generate the code with the child in the tree.
2. Delete the child. Generate the code again, handing the model the first version
   and telling it to change only what the deletion forces.
3. If the lines the child claimed are still there, the child never caused them.
   Discard it.

So a node that has nothing to add stays a leaf. `lang/levels.human` states the
rule: *"A node is a leaf until proven otherwise."* `lang/discipline.human` names
the trap: *"A name you know - 'insertion sort', 'binary search', 'reverse a
string' - determines its own steps, and decomposing it yields nodes that describe
the code instead of causing it."*

This is a reversal. The first version of the language told the model to expand
every node into two to six children, and the model obeyed. Insertion sort came out
as **23 nodes over 20 lines of Python, 12 of them provably decorative**. The tree
was mostly furniture.

Today `progs/insertion_sort_a` is **3 nodes**: the root and two children.

```
progs/insertion_sort_a.human    insertion sort a list of numbers, and demonstrate it on an example
progs/insertion_sort_a/1.human  sort the list in place using insertion sort
progs/insertion_sort_a/2.human  demonstrate the sort on an example list and print the result
```

Both children are leaves. `lower` reported `2 proposed, 2 earned, 0 discarded`.
The build is 14 lines. Nothing was lost by dropping the other 20 nodes, because
those 20 nodes were never causing anything.

You can always add a child yourself with `+ <text>`. A child you wrote by hand is
never auto-discarded. The gate prunes the model's guesses, not your decisions.

## 3. Units, and the contract that stops them colliding

A **unit** is a child of the program root — a level-1 node. A unit is the chunk of
code that actually gets generated. Everything below a unit is *detail about that
unit*, not separate code.

The url shortener has five units: `progs/an_in_memory/1` through `5`. Five
codegen calls, five slabs of Python, concatenated into one file.

The point of units is locality. Edit a node three levels down and only its unit is
regenerated. The other four come back byte-identical from the cache.

The problem is that each unit is generated **blind**. Unit 3 does not see unit 1's
code. So the first time this ran, unit 2 and unit 3 both wrote a `def resolve`,
with different signatures, over three different entry schemas. `assemble()` just
concatenates, so the second `def` silently won and the program did not run.

The **contract stage** fixes that. Before any code is generated, one model call
looks at the root and the five unit sentences — and nothing else — and writes down
the shared vocabulary: the exact shape of the stored entry, and the exact
signature of every public function, each one assigned to exactly one owning unit.
Every unit is then handed the same contract. A unit may define only the names the
contract gave it, and must call the others directly, without importing them.

Two mechanical rules back it up, in `assemble()`:

- If two units define the same top-level name, the build **fails** with a
  `Collision` naming both nodes. Code that two nodes both claim cannot explain
  itself.
- Cross-unit imports are stripped. Units become one module, so
  `from unit3 import ...` is a file that will never exist.

You can read the contract's effect in `build/an_in_memory/main.py`. Unit 1 owns
`store` and `shorten`. Unit 3 owns `is_expired` and `check_and_increment`. Unit 5
owns `generate_code`. `shorten` calls `validate_alias` and `generate_code` without
defining or importing either, and `resolve` is a one-liner that calls
`check_and_increment`. Nobody redefines anybody.

## 4. check: run the asserts, then delete every node

`check` does two separate things.

**First, the assertions.** Any node can carry an `assert:` line. It is a Python
expression evaluated against the compiled program. `progs/an_in_memory/4.human`
is:

> on shorten with a custom alias, reject the alias if it is already present and
> unexpired
>
> `assert: shorten('https://a.example', 60, 'dup') == 'dup' and raises(ValueError, shorten, 'https://b.example', 60, 'dup')`

There are five such assertions across the shortener's tree. All five pass. This is
the sound tier: a claim about behaviour, settled by running the code.

**Second, ablation.** Every node in the tree gets deleted, one at a time. The unit
is regenerated without it. Then fran compares the lines the node *claimed* — from
the line→node map — against the lines that are still there. Five verdicts:

```
caused        the lines it claimed vanished when it was deleted. sound.
DECORATIVE    its lines survived its deletion. it did not cause them.
partial       it caused some of the lines it claimed.
unattributed  it causes code, but the map credits another node.
inert         deleting it changes nothing. the node is ceremony.
```

This is the same test `lower` uses as a gate. The gate and the audit are one
function.

**And here is the punchline.** A node can visibly change the code and still be
decorative.

`progs/an_in_memory/3/1.human` says:

> treat a ttl of zero as never expiring, so the link is always resolvable
>
> `assert: shorten('https://e.example', 0, 'forever') == 'forever' and time.sleep(0.05) is None and resolve('forever') == 'https://e.example'`

Its assertion passes. It owns a real line —
`build/an_in_memory/main.map.json` credits line 32 of the build to it:

```python
def is_expired(entry: dict) -> bool:
    return entry["ttl"] > 0 and time.time() - entry["created"] > entry["ttl"]
```

The `ttl > 0` guard is exactly what the node asked for. And ablation still calls
it **DECORATIVE**, because when you delete the node and regenerate, that line does
not move. Its parent — *"on resolve, reject expired entries"* — over a root that
already says *"a configurable ttl"* implies the same guard on its own. The node
described a line that was going to exist anyway.

The whole tree's verdict:
`provenance: 5/5 units own code, 0/1 nodes below the unit line earned (DECORATIVE 1)`.

*Changing the output* and *causing a line* are different questions. Only the second
one is provenance, and only ablation can tell them apart. (Note: `README.md` tells
this same story with a differently-worded ttl node — *"a negative ttl is also
treated as never expiring"* — which is not the sentence on disk. The node in the
tree today is the zero-ttl one quoted above.)

## 5. The cache is what makes this a compiler

Strip the cache out and fran is a prompt script: you would run it twice and get
two different programs.

Every model call is content-addressed. The key is a hash of: the stage (`expand`,
`contract`, `code`, `reduce`), the model id, a hash of the whole `lang/` folder, a
hash of *that stage's own system prompt*, and the inputs to that call. The result
lands in `.cache/<hash>.json`. There are **418** of them on disk right now.

That buys three things.

1. **A rebuild of an untouched program costs zero model calls and is
   byte-identical.** That is what "compiler" means. Same source, same binary.
2. **An edit invalidates exactly what depended on it, and nothing else.** Edit a
   leaf: its unit's key changes, that unit is regenerated, the other four units
   come straight from cache. The contract's key is built only from the root and
   the unit sentences, so a deep edit does not disturb it. Adding a node three
   levels down and rebuilding costs **one model call**.
3. **Editing the language is a real edit.** The `lang/` hash is in every key, so
   changing `lang/defaults.human` invalidates everything downstream of it — and
   because each stage also hashes its own prompt, rewriting the codegen prompt does
   not invalidate lowering.

## The url shortener, end to end

You type one sentence at the `/` prompt:

> an in-memory url shortener that refuses a custom alias if it is already taken,
> expires links after a configurable ttl, and returns the number of times each link
> was followed

fran writes `progs/an_in_memory.human` and puts the cursor there.

**`lower -r`.** The model proposes children for the root. Each proposal is written
to disk, then tested: generate the code with it, generate again without it, see if
its lines vanish. Five survive. They become `progs/an_in_memory/1.human` through
`5.human` — the dict-with-timestamp-ttl-and-hits, the four operations, the
expiry-and-hit-count rule, the alias rejection, the random code generator. Then
fran recurses into each survivor. Almost all of them come back leaves: the sentence
already determines the code, so there is nothing left to decide. Only one child
survives anywhere below the unit line, `3/1`, the ttl-zero node. Seven nodes total.

**`build`.** One contract call fixes the shared names: the entry is a dict with
keys `url`, `created`, `ttl`, `hits`; `shorten` belongs to unit 1, `is_expired` to
unit 3, `generate_code` to unit 5, and so on. Then five codegen calls, one per
unit, each seeing its own subtree and the contract. `assemble()` checks that no
two units defined the same top-level name, hoists and dedupes the imports, and
writes:

- `build/an_in_memory/main.py` — 54 lines of Python.
- `build/an_in_memory/main.map.json` — 54 entries, one per line, each naming the
  node that caused it.

**`why 32`** reads that map and walks up the tree:

```
an in-memory url shortener that refuses a custom alias...   [progs/an_in_memory]
  \_ on resolve, reject expired entries and increment...    [progs/an_in_memory/3]
    \_ treat a ttl of zero as never expiring...             [progs/an_in_memory/3/1]
```

**`check`.** Runs the five assertions against the compiled module: `5/5 passed`.
Then ablates all six non-root nodes. Five units own code. The one node below the
unit line — `3/1` — comes back DECORATIVE, for the reason in section 4.

fran stops there. It does not run your program; `python build/an_in_memory/main.py`
is your shell's job.

---

# Part 2 — Bugs

Every item below points at a line. Nothing here is speculation.

**1. Every stage prompt contains the codegen instruction sheet.**
`lang_text()` (`fran.py:107`) globs *all five* `lang/*.human` files and pastes them
into a single blob, and every stage — `propose` (`fran.py:225`), `contract`
(`fran.py:272`), `codegen_serial` (`fran.py:300`) — opens its user prompt with that
blob. So the lowering prompt, whose system message says *"Do not write code. Write
the next level of human text"* (`fran.py:216`), also contains `lang/code.human`
telling the model to emit a Python module. On the node `b tree` the model obeyed
`lang/code.human` instead of `EXPAND_SYSTEM` and returned Python, so `extract_json`
found no object and `call_json` raised `model did not return JSON` (`fran.py:206`).
The tell is that its output began `# Unit 1` — and the word *unit* appears nowhere
in the tree except `lang/code.human`.

**2. The retry cannot help.**
`call_json` (`fran.py:198`) loops twice (`fran.py:201`) and calls `call()` with the
byte-identical system and user prompt both times, at `temperature: 0`
(`fran.py:162`). A deterministic call given the same input returns the same output,
so the second attempt re-derives the same non-JSON and the same failure. It cannot
change the outcome; it only doubles the latency and the token cost of failing.

**3. A typo at the prompt silently rewrites your program.**
The REPL treats any line that is not in the command table as *text*
(`fran.py:821`), and only the exact strings `quit`, `exit`, `q` quit
(`fran.py:813`). Mistype `exit` as `exi` and it is written: at `/` it silently
creates a new program root, named by slugging the text (`fran.py:590`); on a node
it silently overwrites that node's text (`fran.py:599`), with no confirmation and
no undo. `progs/http_server.human` is now literally the text `exi` — and since a
root created from the word "exi" would have been named `progs/exi.human`, that file
was created as `http server` and then destroyed by the typo in place.

**4. The `__main__` guard does not make assembly order safe.**
`lang/code.human:12` promises that a unit which demonstrates the program puts its
statements under `if __name__ == "__main__":` *"so that assembly order never
changes behavior."* That is false. `assemble()` concatenates units in child order
(`fran.py:507`), and a `__main__` block in an earlier unit executes at that point in
the module — before the later units are defined. `build/http_server/main.py` calls
`run()` at line 7, which references `HelloHandler`, which unit 2 defines at line 10;
running it raises `NameError: name 'HelloHandler' is not defined`. Nothing in
`build()` (`fran.py:542`) checks that the module it just wrote can even be imported.

**5. `ls` at `/` numbers nine nodes; `cd` can only reach four of them.**
`roots()` (`fran.py:584`) lists programs *and* the five `lang/` nodes, and `do_ls`
numbers all nine. But `resolve()` (`fran.py:574`) builds its candidate list from
`PROGS` only, so a numeric argument is bounds-checked against four candidates and
`cd 5` through `cd 9` fall through to `no such node`. The help text's closing line
(`fran.py:842`) — *"lang/ is nodes too. cd 6, type new text, and you have changed
the compiler"* — is therefore a documented command that cannot work. (The two lists
also disagree on ordering: `roots()` sorts the glob, `resolve()` does not.)

**6. Ungated nodes are left on disk when lowering crashes.**
`lower_earned` writes every proposed child to disk *before* judging it
(`fran.py:382-385`), and only unlinks it if the ablation returns a losing verdict
(`fran.py:391`). If anything in between raises — `ablate` calls `contract`,
`codegen`, and `codegen_reduce`, any of which can hit the `model did not return
JSON` in bug 1 — the exception unwinds to `loop()`'s catch-all (`fran.py:822`) and
the candidate files stay. They are now indistinguishable from earned nodes, and
`build` will happily compile them. That is what `progs/b_tree/1.human` is: a node
that never passed the gate, with a 68-line `build/b_tree/main.py` generated from it.

**7. Ablation compares stripped lines as a set, so duplicate lines always "survive".**
`emitted()` strips each line and `ablate` turns the result into a `set`
(`fran.py:368`, `fran.py:433`), then asks whether each claimed line is still in it
(`fran.py:435`). Indentation is gone, so a line that survives in a *different scope*
counts as surviving; and identical lines collapse, so if a node's only claimed line
is a common one — `i += 1` appears three times in `build/b_tree/main.py` alone — any
other copy anywhere in the unit keeps it "alive" after deletion. Both errors push
the verdict toward DECORATIVE, which means the audit can condemn a node that really
did cause its line.

**8. A unit that does not parse silently loses collision checking.**
`top_names` returns `[]` on `SyntaxError` (`fran.py:463-464`). `assemble` uses that
list as its only source of claimed names (`fran.py:498`), so a unit whose Python is
malformed claims nothing, cannot collide with anything, and sails through the
`Collision` check — and its broken text is still concatenated into `main.py` and
written to disk (`fran.py:547`).

**9. Units are never actually ablated, but they are reported as if they were.**
When the node being ablated *is* the unit, `ablate` returns early
(`fran.py:412-420`): it emits the verdict `caused` if the unit's code has any lines
at all, without deleting anything or regenerating anything. So `5/5 units own code`
means only "all five units emitted at least one line". `check` then prints it under
a legend that defines `caused` as *"the lines it claimed vanished when it was
deleted"* (`fran.py:777`) — a test that was never run on those five nodes.

**10. Imports are attributed to the root, not to the node that caused them.**
`assemble` pulls every `import` line out of its unit's body (`fran.py:511-516`),
discarding that unit's attribution for it, and re-emits the hoisted imports with
`root.path` as the owner (`fran.py:523-526`). `import random` in
`build/an_in_memory/main.py` is caused by unit 5, the random-code-generator node,
but `main.map.json` credits line 1 to `progs/an_in_memory`. `why 1` therefore
answers with the whole program instead of the node that forced the import.

**11. `lower` is not idempotent.**
The `expand` cache key is `[node.intent(), ancestors, siblings, level]`
(`fran.py:230`) — it does not include the children the node already has. Run
`lower` twice on the same node and the second run gets the identical proposals back
from cache, writes them to disk again as new siblings alongside the originals
(`fran.py:382`), and then pays a fresh, uncached ablation per duplicate to discover
that deleting a twin changes nothing. The tree usually survives, since the
duplicates are discarded — but the wasted model calls are real, and the duplicates
exist on disk while the gate is running.
