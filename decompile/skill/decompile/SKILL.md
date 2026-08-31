---
name: decompile
description: Explain a code file in the rail shape, tie the words to real code with inline anchors, and register each explanation with the dmap CLI. Use when the user invokes /decompile, asks for a rail-shape or flow-shape explanation of code, or says "map it" / "map this explanation".
---

# decompile

Two operations: **explain** and **map**. The state is one JSON file per code file, `explanation_<file_name>.json`, written next to the code file. A project of many files also carries one map of its own, `human.json`, written inside the project folder: one entry whose pins point at the files, so a reader who opens the project has a top. The dmap CLI owns that file — never edit it by hand; every operation you need is a dmap command (`map`, `retext`, `undo`, `show`, `lines`, `sync`). The map grows delta by delta: every map run appends one entry and never changes the entries before it.

## How the user points at things

The user pastes text — a whole entry, a fragment, or one line — instead of naming entry ids. Find what the pasted text belongs to in the map file, then act on that entry or anchor. When the paste contains an anchor, that anchor is what the user points at.

## 1. Anchors

An explanation ties itself to real things with inline anchors, written like a Markdown link:

- `[the tool checks](check_entry)` — the words point at a **block** of the code file: a function, a class, a heading of a document, a once-only tag or a named function of a web page.
- `[the checking](e1:the tool checks)` — the words point at an **anchor of an earlier explanation**: entry 1's anchor whose bracketed words are `the tool checks`.
- `[the map command](cmd_map.py)` — the words point at **another file of the folder**. In the reader the pin leads to that file's whole-file entry, the front door of the file.
- `[the check of the pins](cmd_map.py:parse_target)` — the words point at **one block of another file**, for the precise case where the sentence names one exact thing that lives elsewhere.

The rules:

- Anchor the words that name the thing. The rest of the line stays plain text.
- Anchor words are unique inside one text. Two anchors cannot share the same bracketed words.
- A block target must be a real block of the file. dmap refuses a dead name.
- An `e<id>:` target must name an existing entry and existing anchor words inside it. It cannot make a circle. It never crosses a file border — a plainer telling stays inside its file, so a change in one file makes only that file's map stale.
- A file target must name a real file of the folder; a `file:block` target must also name a real block of that file. A block name of the own file wins over a file name when both exist.
- The pins of `human.json` are file and `file:block` pins only. dmap refuses the rest.
- `dmap show` warns when a `.py` file imports another mapped file of the folder and the whole-file entry has no pin to it. It is a warning, not an error — the code holds a connection the map does not show.
- When code moves to another file, its telling moves with it. The old entry keeps one short stage with a pin to the new file — never the sentences. A sentence lives in one file's map only; every other map points at it. `dmap show <folder>` warns when the same line stands in the maps of two files.
- Everything else in the text is free. The layout carries no meaning: drawings, arrows, boxes, and rules between groups are all allowed, because the anchors — not the columns — carry the structure.

Layering runs one way: a plainer explanation anchors into a more detailed one with `e<id>:` targets, and holds no line numbers of its own — it inherits them through the chain. The detailed explanation anchors into the code with block targets. So the map reads: explanation → anchor → block → lines.

In the reader, every explanation of a file is one folded header in a single list, the most detailed first and the entry nothing points at last — a zoom on a block sits above the whole-file entry, and a plainer telling that points into the whole-file entry sits below it. A click on a header folds or unfolds that entry. A click on an anchor whose target has an entry jumps to that entry and unfolds it. An anchor with no entry behind it shows muted and does not react. `human.json` shows as a file in the file tree and opens first. A click on a cross-file pin switches to that file and jumps — to its whole-file entry for a file pin, to the block's entry for a `file:block` pin. A `file:block` pin whose block has no entry yet shows muted with the block name after the words, and does not react. When the target file has no map, a file pin still switches and shows the raw lines under "no map for this file yet".

## 2. Explain

When the user asks how a file or a block works, read the file and write the explanation. The shape follows what the explanation covers: the whole file takes the **rail**, a zoom on one block takes the **flow**.

**Who the reader is.** Write for a reader who does not read code. The reader knows the domain of the file, not the vocabulary of programming. When the user validates a different level, keep that level for the rest of the session.

**The first explanation of a code file covers the whole file, and its shape is the rail.** Write six to eight stages down a rail: the main run of the file, from the first thing the user does to the last thing the tool writes. Every later explanation is a zoom on one block or a plainer layer over the whole; a plainer layer is a rail too, and its heads point with `e<id>:` at the anchors of the entry below it.

```
●  you ask for something                              ([the start](main))
  │     You type one line and press enter.
  │     The tool keeps the two things it needs from that line:
  │     what you want done, and which file to do it to.
  │
  ●  the tool reads the file                       ([the reading](read_file))
  │     It opens the file and holds every line of it.
  │     It does this for one reason only: so the next stage
  │     works without going back to the disk.
  │
  ●  the tool writes the answer beside the file     ([the answer](write_out))
        It puts a new file next to the old one.
        The old file is never touched.

──────────────────────────────────────────────────────────────
  when a check fails                                   ([the stop](refuse))
     The tool says which check failed and stops there.
     Nothing is written, so you can correct the line and ask again.
```

The rules of the rail:

- A head is an act with the one who acts in it, in plain words — "the tool finds the pieces of the file", never a bare name and never a noun on its own.
- The pin sits on the right of the head, in parentheses, like `([the start](main))`. The head words stay plain, so the reader reads the act first and the pin second.
- Under each head stand two to four full sentences, indented. Every sentence has a subject — you, the tool, or claude — and a full stop. A fragment is not a stage sentence.
- Keep the lines short. Break a sentence over two lines rather than let it run off the screen.
- Say the purpose of a stage in a sentence of its own. A stage that says only what happens reads as trivia.
- A rule line sets apart the stages that are not the main run: what happens when the file changes, what else the user may ask for. Below the rule the rail drops away and each stage stands on its own.
- Keep one kind of file in hand through the whole rail and drop the rest. One real example of what the user types beats a description of what the user may type.
- Drawings are welcome — an arrow back for a retry loop, an indented block that shows what a line looks like — because the layout carries no meaning. The pins, not the columns, carry the structure.

**A zoom on one block: the flow shape.** For a reader who already walked the rail and asks about one block, write the flow — one line per bound name:

```
name            = what the step binds, in simple words
```

- One line per bound name. The left column is the name, anchored to its block.
- A loop is a header line with indented step lines.
- A dispatch from a name to a function is a header line with indented cases, not one dense line that names the data structure. Describe what the step does, not the structure that does it.
- The flow is the shape of a zoom only. When the user asks about the whole file again, go back to the rail.

**The question shape.** When a block is a chain of checks — a gate, a validator — write each check as a question, with its stop error on the right, each question and its answer on one line.

The wording rules hold for both shapes:

- Use the real names from the code only inside anchor targets. Do not invent names.
- Simple words, one idea per line. A dense clause is what makes an explanation hard to follow.
- A word is coined when the reader's world does not contain it. This includes the words of programming itself — parser, argument, flag, table, callback, index — not only the words this project made. Do not write a coined word before a line defines it — or say what the thing does in place of its class: "the reader of what a person types", not "the argument parser".
- When a binding exists only to feed one later step, the line must say that purpose: "it exists only so X can Y". A "what" without a "for what" reads as trivia.
- Compress by dropping the fields the reader does not need yet, never by dropping the verbs. A pile of nouns is short but not simple.
- For a numbering or naming scheme, give the first two cases and "and so on" instead of the rule.
- A value that comes from outside — typed input, a file — gets one real example and what the step keeps from it.
- A definition states the permission before the constraint. First what the thing may do, then the rule that binds it.
- When the user says which phrasing made them understand, build the definition from those exact words. Never paraphrase a validated phrasing away.

**Definitions live in place.** When a concept needs a definition, put it at the point where the reader meets it — indented lines under the stage or the flow line. Do not create a separate entry just to hold a definition.

**The answer is never prose.** Even when the user says "explain simpler", answer with a simpler rail, not with paragraphs. One short read-me line under the text is fine.

**A markdown file.** The blocks of a `.md` file are its headings. The first flow of a document is one line per section — a short label on the left, anchored to the real heading, the section's one job after it. For a document the label ends with a comma in place of the equals sign. Labels stay unique across the whole text.

**A web page.** A `.html` file's blocks come from two places: every tag that appears once — `head`, `style`, `body`, `main`, `script` — and every named function inside a `<script>`, nested ones too. A zoom on the look has no bound names, so the grammar shifts: one line per visual role, and say what the reader sees, never how the rule finds its target.

Run `dmap lines <code_file>` to see the file with line numbers.

**Reread before you show.** Read each line of the finished text as a stranger who has not seen the code: does the line use a word the text has not defined yet? Does a line use a programming word? Does a line only say "what" where the reader needs "for what"? Fix those lines before you show the explanation.

**Show the explanation, then stop. Do not touch the map until the user gives the word.** This holds even when the user's message sounds like approval in advance — show the explanation first, map on the next word.

## 3. Map

When the user says "map it", pipe the exact explanation text into dmap:

```bash
dmap map <code_file> --block <name> <<'EOF'
<the explanation text, verbatim>
EOF
```

- `--block` is the block the entry explains. Omit it for a whole-file entry — the default is the file itself.
- `dmap map <folder>` maps the project itself: the entry goes into `<folder>/human.json`, takes no `--block`, and its pins are file and `file:block` pins only. Write one line per file — what the file does, the file name as the pin.
- The run is deterministic and instant: dmap parses the anchors out of the text, checks every target, refuses duplicates, dead names, and circles, resolves each block anchor to its exact lines, and appends one entry. There is no claude call.
- Order matters once: an `e<id>:` target must name an entry that already exists, so map the detailed entry before the plainer one that points into it.

## 4. Rewrite and rollback

When the user approves a clearer wording for an entry that is already mapped, replace the text in place:

```bash
dmap retext <code_file> <id> <<'EOF'
<the new text, verbatim>
EOF
```

The new text may change anything except the anchors other entries point at — dmap refuses a text that drops one. All other anchors may be added, removed, or reworded, and are revalidated. When the text changed and other entries point into this one, dmap marks them **stale**; repair each with `dmap sync <code_file> --stale <id>` when the user gives the word.

When the user says "rollback" or "undo": `dmap undo <code_file>` removes the last entry. An entry that other entries point into cannot be undone before them.

## 5. Sync after a change

When the **code file** changed:

```bash
dmap sync <code_file>
```

- The old version comes from git `HEAD`; pass `--old <file>` when it lives elsewhere. Commit the code file together with its map, so `HEAD` is always the last synced state. Run sync exactly once per code change — a second run against the same `--old` re-applies the diff and corrupts the spans; use `dmap show` to look.
- A deterministic pass re-resolves every block anchor and entry span from the new code. A change that only moves lines ends here — no claude call.
- One claude call then repairs the words of the entries the change touches: it rewrites only the stale lines, keeps every anchor, retargets an anchor whose block was renamed, and renames an entry's block when the code renamed it. Gates check every anchor and retry up to `--tries` (default 4).
- Entries that point into a repaired entry are marked stale.

`dmap sync <folder>` re-resolves the pins of `human.json` against the folder — no claude call. A pin whose file is gone is reported; repair it with `dmap retext`.

When an **explanation** changed and its dependents are stale:

```bash
dmap sync <code_file> --stale <id>
```

One claude call reads the old and new text of the changed parent and repairs only the words of the dependent that went wrong, keeping every anchor. Repairs run one layer at a time, downward only, on the user's word — never recursively in one breath.

## 6. Report

After a map run, report to the user in this order:

1. The new entry: id, block, lines, and its anchors — how many into the code, how many into earlier explanations.
2. Coverage: covered code lines out of total code lines.
3. Any warnings from `dmap show`, and any entries marked stale.
4. Offer to take the next explanation.

After a retext, an undo, or a sync, report what changed and confirm with `dmap show <code_file>`.
