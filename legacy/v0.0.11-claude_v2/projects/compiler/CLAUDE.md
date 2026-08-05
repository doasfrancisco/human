# claude_v2 — Claude is the compiler

There is no model call inside a program. In this folder **you (Claude) are the
compiler**. The user hands you human code in prose; you produce the sentences, the code,
the map that connects every sentence to the characters it caused, and the registry.
The web app in `web/` only *renders* what you emit — it decides nothing.

## What you emit for a program

```
projects/<name>/
  <word><nnn>.human              the root sentence
  <word><nnn>/<word><nnn>.human  a child sentence
  build/main.py                  the "compiled" code file (name the file in code_file)
  build/main.map.json            the causation map (schema below)
  build/concepts.json            the concept registry file
```

Every `.human` file's name is a short word that describes its node plus a
3-digit combination. Children appear only when lowering adds real meaning.

Then add `{ "name": "<name>", "human_code": "..." }` to `projects.json`.

## Two relations, kept apart

The folder tree is **only the authoring tree**: it records which sentence
refines which sentence, nothing else. Causation lives exclusively in the map,
keyed by each sentence's stable `@id` (4 hex chars). The two relations may
disagree — a child may cause code far outside anything its parent caused — and
that disagreement is information, not an error.

## Map schema (`build/main.map.json`)

```json
{
  "program": "<name>",
  "human_code": "<the user's words>",
  "code_file": "main.py",
  "nodes": [
    { "id": "4a1c", "path": "<name>",   "level": 0, "text": "the root prose" },
    { "id": "9f22", "path": "<name>/1", "level": 1, "text": "a child's prose" }
  ],
  "map": [
    { "nodes": ["4a1c"],         "kind": "specified", "ranges": [[0, 900]] },
    { "nodes": ["9f22"],         "kind": "specified", "ranges": [[120, 300]] },
    { "nodes": ["4a1c", "9f22"], "kind": "specified", "ranges": [[420, 460]] },
    { "nodes": ["9f22"], "kind": "assumed", "why": "gap this sentence implied",
      "ranges": [[40, 80]] },
    { "nodes": [], "kind": "assumed", "why": "pure convention, nobody asked",
      "ranges": [[0, 40]] }
  ]
}
```

`nodes` on a fragment is its **owner-set**. Usually a singleton; several ids
mean joint causation — sentences that only together force that span (e.g.
"keep the list sorted" + "insert items" → `bisect.insort`). The renderer lights
every owner's prose when the fragment is hovered. An empty owner-set on an
`assumed` fragment means pure convention. Every `assumed` fragment carries
`why` instead of user prose.

## No crossing — hard rule

Any two ranges in a map must either **nest or be disjoint**. Partially
overlapping (crossing) ranges are a compile error. A contribution that would
straddle another fragment's range must be emitted as several split ranges
instead. Containment is then a valid poset, so the deepest cover of any
character is well defined wherever owners are singletons.

## Full coverage — hard rule

A node's range must be completely tiled by deeper fragments: every character
inside it must also lie inside a fragment of some other node or inside an
`assumed` fragment. In particular the root's `[0, len]` leaves no orphan
characters — code that no child sentence causes is not the parent's leftover,
it is either attributed to the sentence that forces it or owned up to in an
`assumed` fragment with a `why`. A gap is a compile error. Verify coverage by
computation before emitting the map, exactly like the no-crossing check.

## No layer skipping — hard rule

For every node, take each of its ranges and find the tightest range owned by
some *other* node that contains it. Those container ranges are where the node
hangs, and they must form an antichain: none of them may contain another.
A node whose code hangs partly under a parent and partly under that parent's
ancestor is straddling layers — either split the shallow part into its own
sentence at its true depth, or write the parent sentence that owns it. Levels
of abstraction are never declared anywhere; they fall out of containment, and
this rule is what keeps them honest. Verify by computation before emitting the
map, like the other invariants.

## Concept registry

The compiler keeps a concept registry: each concept gets one id, and each
node points to the ids of its concepts. The registry file is readable and
diffable. When a concept changes, every node that points to it recompiles.

The LLM reads one node and lists its concepts, each with a name, a type, and
a signature; the list is rebuilt only when the node changes. The compiler
then finds candidate pairs without the LLM — near names, near embeddings, or
equal signatures — and removes pairs with different types.

The LLM examines one candidate pair at a time. Do not ask if the two
concepts are the same — the LLM says yes too often. Ask for one example
where the two concepts cause different results: an example means different,
no example means same.

The compiler writes the decision and the example in the registry, and the
match is tested by ablation: change the concept, recompile — the code of
each connected node must change, and a match that moves no code goes back to
examination. Matches are never chained: a matching b and b matching c does
not make a match c; each new concept is compared with all members of the
group.

## Rules carried from v1

- Offsets index the LF-normalized code string exactly — compute them, never
  guess. Snap range edges to token or line boundaries.
- `specified` traces to the user's words; `assumed` fills a gap by convention.
- A `note:` line in a `.human` file is for the human only: never compiled,
  never a cause of any range.
- **Reword** — wording changed, meaning didn't: update the `.human` file and
  the map `text`; touch nothing else. **Revise** — meaning changed: a revise
  reads the registry first; rewrite only what the change forces, keep
  untouched code byte for byte, update only the ranges that moved; a changed
  concept recompiles every node that points to it.
- `assert:` lines are the only ground truth. If the program cannot satisfy
  them, say so — never ship a map describing code that fails its asserts.
