# claude_v1 — Claude is the compiler

There is no Bedrock, no `human_compiler.py`, no model call inside a program. In
this folder **you (Claude) are the compiler**. The user hands you a request in
prose; you produce a project: the ideas, their levels, the code, and the map
that connects every idea to the characters of code it caused. The web app in
`web/` only *renders* what you emit — it decides nothing.

## What you emit for a request

Given a request like "insertion sort a list", create `projects/<name>/`:

```
projects/<name>/
  <name>.human            the root idea: @id, the prose, and any assert: lines
  <name>/1.human          a child idea (when the root is worth lowering)
  <name>/2.human          ...
  build/main.py           the whole program, one module, stdlib only
  build/main.map.json     the declared idea -> code map (schema below)
```

Then add `{ "name": "<name>", "request": "..." }` to `projects.json`.

## The compile, step by step

1. **Find the ideas.** Read the request as meaning, not keywords. Break it into
   atomic ideas — a node is one idea, any shape. Give each a stable short `@id`
   (4 hex chars) and a level: the root is level 0, its children level 1, and so
   on. Only lower an idea into children when the children genuinely carry
   distinct meaning; a child that would just restate the parent is noise.

2. **Write the code.** Emit `build/main.py` as one Python module, standard
   library only, no comments or docstrings (the repo rule holds here too). Build
   *something* even when the request is underspecified — pick a conventional
   default rather than refusing.

3. **Declare the map.** For every idea, record the character ranges of
   `main.py` it is responsible for. A range is `[start, end]` into the code
   string; `code[start:end]` is a region the idea owns. Ranges may overlap and
   need not be contiguous — a parent's range naturally *contains* its children's,
   and that nesting is the abstraction depth, not a mistake. Tag each region:
   - `specified` — it traces to something the user actually wrote.
   - `assumed` — you filled a gap by convention (an argument name, a `__main__`
     demo, a not-stated default). Attribute assumed regions honestly: to the
     idea that implied the gap, or to `lang/convention` when nothing did.

4. **Snap ranges to token edges.** Never emit a range that cuts a word or an
   identifier in half. Start and end on whitespace, punctuation, or line
   boundaries so the rendered highlight is legible.

## Map schema (`build/main.map.json`)

```json
{
  "program": "<name>",
  "request": "<the user's words>",
  "code_file": "main.py",
  "map": [
    { "node": "<name>",   "id": "4a1c", "level": 0, "kind": "specified",
      "text": "the idea's prose", "ranges": [[start, end]] },
    { "node": "<name>/1", "id": "9f22", "level": 1, "kind": "specified",
      "text": "the child idea's prose", "ranges": [[start, end]] },
    { "node": "<name>",   "id": "4a1c", "level": 0, "kind": "assumed",
      "text": "", "why": "why this region was invented", "ranges": [[start, end]] },
    { "node": "lang/convention", "id": "0000", "level": 0, "kind": "assumed",
      "text": "", "why": "...", "ranges": [[start, end]] }
  ]
}
```

`text` is the idea's current wording (also mirrored in the `.human` file). An
`assumed` entry carries `why` instead of user prose. Offsets index the exact
bytes of `main.py`; compute them, do not guess.

## Editing an existing project

- **Reword** — the user changes an idea's wording but not its meaning. Update
  the `.human` file and the `text` in the map. Do **not** touch `main.py` or the
  ranges. The build is unchanged by construction.
- **Revise** — the meaning changed. Rewrite only what the change forces in
  `main.py`, keeping every untouched line byte for byte, then update the ranges
  that moved. Leave the rest of the map alone.
- **Annotation** — a `note:` line in a `.human` file is for the human only. It
  never reaches the code and never causes a range.

## Ground truth

The `assert:` lines are the only real check. Whatever ideas and map you declare,
the program must satisfy every assertion in the tree. If you cannot make them
pass, say so — do not ship a map that describes code that fails its asserts.
