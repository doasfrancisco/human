---
name: decompile-claude
description: Explain a code file in the flow shape, tie the words to real code with inline anchors, and register each explanation with the dmap CLI. Use when the user invokes /decompile-claude, asks for a flow-shape explanation of code, or says "map it" / "map this explanation".
---

# decompile-claude

Two operations: **explain** and **map**. The state is one JSON file per code file, `explanation_<file_name>.json`, written next to the code file. The dmap CLI owns that file — never edit it by hand; every operation you need is a dmap command (`map`, `retext`, `undo`, `show`, `lines`, `sync`). The map grows delta by delta: every map run appends one entry and never changes the entries before it.

## How the user points at things

The user pastes text — a whole entry, a fragment, or one line — instead of naming entry ids. Find what the pasted text belongs to in the map file, then act on that entry or anchor. When the paste contains an anchor, that anchor is what the user points at.

## 1. Anchors

An explanation ties itself to real things with inline anchors, written like a Markdown link:

- `[the tool checks](check_entry)` — the words point at a **block** of the code file: a function, a class, a heading of a document, a once-only tag or a named function of a web page.
- `[the checking](e1:the tool checks)` — the words point at an **anchor of an earlier explanation**: entry 1's anchor whose bracketed words are `the tool checks`.

The rules:

- Anchor the words that name the thing. The rest of the line stays plain text.
- Anchor words are unique inside one text. Two anchors cannot share the same bracketed words.
- A block target must be a real block of the file. dmap refuses a dead name.
- An `e<id>:` target must name an existing entry and existing anchor words inside it. It cannot make a circle.
- Everything else in the text is free. The layout carries no meaning: drawings, arrows, boxes, and rules between groups are all allowed, because the anchors — not the columns — carry the structure.

Layering runs one way: a plainer explanation anchors into a more detailed one with `e<id>:` targets, and holds no line numbers of its own — it inherits them through the chain. The detailed explanation anchors into the code with block targets. So the map reads: explanation → anchor → block → lines.

In the reader, the entry nothing points at stands on top. A click on an `e<id>:` anchor opens the more detailed explanation **in the place of** the plainer one, and the block header above the text is the way back. A click on a block anchor whose block has its own entry opens that entry **inline under the line**, and its header closes it. An anchor with no entry behind it shows muted and does not react.

## 2. Explain

When the user asks how a file or a block works, read the file and write the explanation in the flow shape:

```
name            = what the step binds, in simple words
```

**The first explanation of a file covers the whole file.** Its flow is the module layer, top to bottom: the imports, each module binding, one line per function or class with its role — anchor the name of the step to its block, `[the start](main) = ...` — and the entry point. Every later explanation is a zoom on one block or a plainer layer over the whole.

**Who the reader is.** Write for a reader who does not read code. The reader knows the domain of the file, not the vocabulary of programming. When the user validates a different level, keep that level for the rest of the session.

The rules of the shape:

- One line per bound name. The left column is the name, anchored to its block.
- A loop is a header line with indented step lines.
- Use the real names from the code only inside anchor targets. Do not invent names.
- Simple words, one idea per line. A dense clause after the `=` is what makes a flow hard to follow.
- A word is coined when the reader's world does not contain it. This includes the words of programming itself — parser, argument, flag, table, callback, index — not only the words this project made. Do not write a coined word in a flow line before an indented line defines it — or say what the thing does in place of its class: "the reader of what a person types", not "the argument parser".
- When a binding exists only to feed one later step, the line must say that purpose: "it exists only so X can Y". A "what" without a "for what" reads as trivia.
- Compress by dropping the fields the reader does not need yet, never by dropping the verbs. A pile of nouns is short but not simple.
- For a numbering or naming scheme, give the first two cases and "and so on" instead of the rule.
- A value that comes from outside — typed input, a file — gets one real example and what the step keeps from it.
- A dispatch from a name to a function is a header line with indented cases, not one dense line that names the data structure. Describe what the step does, not the structure that does it.
- A definition states the permission before the constraint. First what the thing may do, then the rule that binds it.
- When the user says which phrasing made them understand, build the definition from those exact words. Never paraphrase a validated phrasing away.

**The question shape.** When a block is a chain of checks — a gate, a validator — write each check as a question, with its stop error on the right, each question and its answer on one line.

**Definitions live inside the flow.** When a concept needs a definition, put it as indented lines at the point where the reader meets it. Do not create a separate entry just to hold a definition.

**The format is always the flow shape** for code, even when the user says "explain simpler" — answer with a simpler flow, not with prose. One short read-me line under the flow is fine; paragraphs are not.

**The stage shape**, for a plainer telling of a whole file. When the user says the whole-file flow is still too hard, write six to eight stages, each a head line plus two to four indented sentences. The head is an act with the one who acts in it — "the tool finds the pieces of the file" — and the head words are the anchor, targeted with `e<id>:` at the anchor of the detailed entry that does the work. Every sentence has a subject and a full stop; the subject is you, the tool, or claude. Keep one kind of file in hand and drop the rest. Say the purpose of a stage in a sentence of its own. Drawings — an arrow back for a retry loop, a rule line before the stages that are not the main run — are welcome, because the layout carries no meaning.

**A markdown file.** The blocks of a `.md` file are its headings. The first flow of a document is one line per section — a short label on the left, anchored to the real heading, the section's one job after it. For a document the label ends with a comma in place of the equals sign. Labels stay unique across the whole text.

**A web page.** A `.html` file's blocks come from two places: every tag that appears once — `head`, `style`, `body`, `main`, `script` — and every named function inside a `<script>`, nested ones too. A zoom on the look has no bound names, so the grammar shifts: one line per visual role, and say what the reader sees, never how the rule finds its target.

Run `dmap lines <code_file>` to see the file with line numbers.

**Reread before you show.** Read each line of the finished flow as a stranger who has not seen the code: does the line use a word the flow has not defined yet? Does a line use a programming word? Does a line only say "what" where the reader needs "for what"? Fix those lines before you show the flow.

**Show the explanation, then stop. Do not touch the map until the user gives the word.** This holds even when the user's message sounds like approval in advance — show the flow first, map on the next word.

## 3. Map

When the user says "map it", pipe the exact explanation text into dmap:

```bash
dmap map <code_file> --block <name> <<'EOF'
<the explanation text, verbatim>
EOF
```

- `--block` is the block the entry explains. Omit it for a whole-file entry — the default is the file itself.
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
