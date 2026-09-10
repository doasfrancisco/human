---
name: decompile
description: Explain a code file in the rail shape, tie the words to real code with inline anchors, and register each explanation with the human CLI. Use when the user invokes /decompile, asks for a rail-shape explanation of code, or says "map it" / "map this explanation".
---

# decompile

Two operations: **explain** and **map**. The state is one `human/` folder at the project root, created once with `human init`: one JSON map per code file, `explanation_<path>.json` with the `/` of the path written as `__`, and one map for the project itself, `human/human.json` — one entry whose pins point at the files, so a reader who opens the project has a top, plus the list of the project's files. A file is named by its path from the root, like `src/app.py`. The human CLI owns the `human/` folder — never edit a map by hand; every operation you need is a human command (`init`, `map`, `retext`, `undo`, `show`, `lines`, `sync`, `serve`, `train`). The map grows delta by delta: every map run appends one entry and never changes the entries before it. When a training session is open, the explain step writes three versions instead of one — see §7.

## How the user points at things

The user pastes text — a whole entry, a fragment, or one line — instead of naming entry ids. Find what the pasted text belongs to in the map file, then act on that entry or anchor. When the paste contains an anchor, that anchor is what the user points at.

## 1. Anchors

An explanation ties itself to real things with inline anchors, written like a Markdown link:

- `[the tool checks](check_entry)` — the words point at a **block** of the code file: a function, a class, a heading of a document, a once-only tag or a named function of a web page.
- `[the checking](e1:the tool checks)` — the words point at an **anchor of an earlier explanation**: entry 1's anchor whose bracketed words are `the tool checks`.
- `[the map command](src/cmd_map.py)` — the words point at **another file of the project**, named by its path from the root. In the reader the pin leads to that file's whole-file entry, the front door of the file.
- `[the check of the pins](src/cmd_map.py:parse_target)` — the words point at **one block of another file**, for the precise case where the sentence names one exact thing that lives elsewhere.
- `[the gates](src/cmd_map.py:e1:the checking)` — the words point at **an anchor of an entry of another file's map**: entry 1 of `src/cmd_map.py`, its anchor `the checking`. This pin lives in the project map only (§8).

The rules:

- Anchor the words that name the thing. The rest of the line stays plain text.
- Anchor words are unique inside one text. Two anchors cannot share the same bracketed words.
- A block target must be a real block of the file. human refuses a dead name.
- An `e<id>:` target must name an existing entry and existing anchor words inside it. It cannot make a circle. It never crosses a file border — a plainer telling stays inside its file, so a change in one file makes only that file's map and the project map stale.
- A file target must name a real file of the project by its path from the root; a `file:block` target must also name a real block of that file. A block name of the own file wins over a file name when both exist.
- The pins of `human/human.json` are file and `file:block` pins only. human refuses the rest. The pins of `human/project.json` are file, `file:block`, `file:e<id>:words`, and `e<id>:` into its own entries.
- `human show` warns when a `.py` file imports another mapped file and the whole-file entry has no pin to it. It is a warning, not an error — the code holds a connection the map does not show.
- When code moves to another file, its telling moves with it. The old entry keeps one short stage with a pin to the new file — never the sentences. A sentence lives in one file's map only; every other map points at it. `human show .` at the root warns when the same line stands in the maps of two files.
- Everything else in the text is free. The layout carries no meaning: drawings, arrows, boxes, and rules between groups are all allowed, because the anchors — not the columns — carry the structure.

Layering runs one way: a plainer explanation anchors into a more detailed one with `e<id>:` targets, and holds no line numbers of its own — it inherits them through the chain. The detailed explanation anchors into the code with block targets. So the map reads: explanation → anchor → block → lines.

In the reader, every explanation of a file is one folded header in a single list, the most detailed first and the entry nothing points at last — a zoom on a block sits above the whole-file entry, and a plainer telling that points into the whole-file entry sits below it. A click on a header folds or unfolds that entry. A click on an anchor whose target has an entry jumps to that entry and unfolds it. An anchor with no entry behind it shows muted and does not react. `human.json` shows as a file in the file tree and opens first. The reader runs with `human serve` from anywhere in the project. A click on a cross-file pin switches to that file and jumps — to its whole-file entry for a file pin, to the block's entry for a `file:block` pin. A `file:block` pin whose block has no entry yet shows muted with the block name after the words, and does not react. When the target file has no map, a file pin still switches and shows the raw lines with "no abstraction for this file yet" on its head line. `project.json` shows as a file under `human.json`; a click on one of its `file:e<id>:words` pins switches to that file, unfolds the entry, and lights the anchor.

## 2. Explain

When the user asks how a file or a block works, read the file and write the explanation. The folder `shapes/` next to this file is the catalog of validated shapes, each with its rules and one example. The shape follows the kind of file:

- a file with one real run — a web page, a script that runs top to bottom — takes the **rail** (`shapes/rail.md`, below);
- a code file that is a set of functions takes the **sections** (`shapes/sections.md`): one head per block in story order, the inputs in the head, full sentences under it, the small helpers below a rule;
- a file that only reads what the user types and hands it on takes the **desk** (`shapes/desk.md`): one head per command;
- a rulebook — a skill, a procedure — takes the **dialogue** (`shapes/dialogue.md`): who says what, turn by turn;
- a zoom on one block takes the rail.

Read the shape file before you write. When the user has validated another shape for a project — like the skeleton, the file's own structure in plain words — that shape takes the whole-file place there.

**Who the reader is.** Write for a reader who does not read code. The reader knows the domain of the file, not the vocabulary of programming. When the user validates a different level, keep that level for the rest of the session.

**The first explanation of a code file covers the whole file.** Every later explanation is a zoom on one block or a plainer layer over the whole. A zoom is a rail — its stages walk the block's own run, and its pins reach the block and the names inside it. A plainer layer is a rail whose heads point with `e<id>:` at the anchors of the entry below it.

**The rail** is six to eight stages down a rail: the main run of the file, from the first thing the user does to the last thing the tool writes.

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

**The question shape.** When a block is a chain of checks — a gate, a validator — write each check as a question, with its stop error on the right, each question and its answer on one line.

The wording rules hold for every shape:

- Use the real names from the code only inside anchor targets. Do not invent names.
- Simple words, one idea per line. A dense clause is what makes an explanation hard to follow.
- A word is coined when the reader's world does not contain it. This includes the words of programming itself — parser, argument, flag, table, callback, index — not only the words this project made. Do not write a coined word before a line defines it — or say what the thing does in place of its class: "the reader of what a person types", not "the argument parser".
- When a binding exists only to feed one later step, the line must say that purpose: "it exists only so X can Y". A "what" without a "for what" reads as trivia.
- Compress by dropping the fields the reader does not need yet, never by dropping the verbs. A pile of nouns is short but not simple.
- For a numbering or naming scheme, give the first two cases and "and so on" instead of the rule.
- A value that comes from outside — typed input, a file — gets one real example and what the step keeps from it.
- A definition states the permission before the constraint. First what the thing may do, then the rule that binds it.
- When the user says which phrasing made them understand, build the definition from those exact words. Never paraphrase a validated phrasing away.

**Definitions live in place.** When a concept needs a definition, put it at the point where the reader meets it — indented lines under the stage. Do not create a separate entry just to hold a definition.

**The answer is never prose.** Even when the user says "explain simpler", answer with a simpler text in the same shape, not with paragraphs. One short read-me line under the text is fine.

**A markdown file.** The blocks of a `.md` file are its headings. A document that tells a procedure takes the dialogue. Any other document takes the rail like a code file: one stage per section, the head an act in plain words, the pin at the real heading on the right.

**A web page.** A `.html` file's blocks come from two places: every tag that appears once — `head`, `style`, `body`, `main`, `script` — and every named function inside a `<script>`, nested ones too. A zoom on the look takes one line per visual role — say what the reader sees, never how the rule finds its target.

Run `human lines <code_file>` to see the file with line numbers.

**Reread before you show.** Read each line of the finished text as a stranger who has not seen the code: does the line use a word the text has not defined yet? Does a line use a programming word? Does a line only say "what" where the reader needs "for what"? Fix those lines before you show the explanation.

**Show the explanation, then stop. Do not touch the map until the user gives the word.** This holds even when the user's message sounds like approval in advance — show the explanation first, map on the next word.

## 3. Map

When the user says "map it", pipe the exact explanation text into human:

```bash
human map <code_file> --block <name> <<'EOF'
<the explanation text, verbatim>
EOF
```

- `--block` is the block the entry explains. Omit it for a whole-file entry — the default is the file itself.
- The project needs its `human/` folder first: run `human init` at the project root once.
- `human map .` at the root maps the project itself: the entry goes into `human/human.json`, takes no `--block`, and its pins are file and `file:block` pins only. Write one line per file — what the file does, the file's path as the pin.
- `human map project` maps the project telling of §8: the entry goes into `human/project.json`, takes no `--block`, and its pins may be file, `file:block`, `file:e<id>:words`, and `e<id>:` into an earlier entry of the same map.
- `--verbatim` on a map says the text is the user's own words: it goes in plain — a pin in it is refused, because the words come before the things they point at — the entry is flagged, and the text is kept as its origin. The pins come later with `human retext`. The human skill uses this for the abstraction; here it is for any words the user wrote and wants kept.
- The run is deterministic and instant: human parses the anchors out of the text, checks every target, refuses duplicates, dead names, and circles, resolves each block anchor to its exact lines, and appends one entry. There is no claude call.
- Order matters once: an `e<id>:` target must name an entry that already exists, so map the detailed entry before the plainer one that points into it.

## 4. Rewrite and rollback

When the user approves a clearer wording for an entry that is already mapped, replace the text in place:

```bash
human retext <code_file> <id> <<'EOF'
<the new text, verbatim>
EOF
```

The new text may change anything except the anchors other entries point at — human refuses a text that drops one. All other anchors may be added, removed, or reworded, and are revalidated. When a word changed and other entries point into this one, human marks them **stale**; repair each with `human sync <code_file> --stale <id>` when the user gives the word. A retext that only adds or moves pins marks nothing.

A retext never removes a stale mark from the entry itself — only `--stale` does, so the tool knows the repair was made and not guessed. When the entry is stale, the retext says so and names the repair.

On an entry flagged as the user's words, a plain retext is pins only: the tool strips the pins and compares the words with the words it holds, character for character; one changed character is refused. `human retext <code_file> <id> --verbatim` is the road for new words on the user's word — the text with its pins goes in as it is, and the origin is reset. On an entry with no flag, `--verbatim` with the entry's own text puts the flag on and records the origin — the road for words mapped before the flag existed, when the user says the entry is theirs.

When the user says "rollback" or "undo": `human undo <code_file>` removes the last entry. An entry that other entries point into cannot be undone before them.

## 5. Sync after a change

When the **code file** changed:

```bash
human sync <code_file>
```

- The old version comes from git `HEAD`; pass `--old <file>` when it lives elsewhere. Commit the code file together with its map, so `HEAD` is always the last synced state. Run sync exactly once per code change — a second run against the same `--old` re-applies the diff and corrupts the spans; use `human show` to look.
- A deterministic pass re-resolves every block anchor and entry span from the new code. A change that only moves lines ends here — no claude call.
- One claude call then repairs the words of the entries the change touches: it mends the stale lines, adds a sentence for each behaviour the change added — a new option, a new step, a new case — keeps every anchor, retargets an anchor whose block was renamed, and renames an entry's block when the code renamed it. The call runs at the project root and reads the whole file, plus the project files the file imports when a new sentence needs them. Gates check every anchor and retry up to `--tries` (default 4). When new lines land inside an entry and its text did not change, sync warns: those lines got no sentence.
- Entries that point into a repaired entry are marked stale — in the file's map, and in the project map when one of its entries pins the repaired entry.
- A whole-file layer with no pin of its own into the code is never a sync candidate — the sync has nothing to compare it to. It receives a new fact through `--stale`, one layer down.
- An entry flagged as the user's words is reworded by a sync like any other, because the map must follow the code; the letter asks for the smallest edit, in the user's voice, and no sentence the change does not force. The tool then prints a warning that names the entry and the changed lines. The origin stays in the map: `human show` says "your words, reworded since they were mapped" and names the `retext --verbatim` that brings them back. Tell the user when this happened.

`human sync project` when the code changed: the old state is git `HEAD`, no `--old`. A deterministic pass re-resolves every file, block, and `file:e<id>:words` pin; a gone target is reported. One claude call then mends the entries that pin a changed file: it gets the root, the changed files with their paths — it reads them —, their diff, and the pins whose target is gone with the anchors that entry holds now. The same rules and gates as a file sync. `human sync project --stale <id>` repairs a project entry that file entries made stale: each note names its file, the parent text comes from that file's map, and a carried fact is pinned `file:e<id>:words`. A close of a training session marks the project entry once per changed parent; the notes wait for this repair.

`human sync .` at the root re-resolves the pins of `human/human.json` against the project — no claude call. A pin whose file is gone is reported; repair it with `human retext`.

When an **explanation** changed and its dependents are stale:

```bash
human sync <code_file> --stale <id>
```

The stale mark is a list: one note per changed parent, each with the parent's text as it was when the dependent last matched it. A parent that changes twice before a repair keeps its first old text — the versions between are the base of nothing. One claude call reads every note — the old text, the parent as it is now, the diff of each — mends the words of the dependent that went wrong, and carries a new fact of a parent down at the dependent's own level — pinned at the parent's new anchor — keeping every anchor. The whole list goes with the repair. Repairs run one layer at a time, downward only, on the user's word — never recursively in one breath.

## 6. Report

After a map run, report to the user in this order:

1. The new entry: id, block, lines, and its anchors — how many into the code, how many into earlier explanations.
2. Coverage: covered code lines out of total code lines.
3. Any warnings from `human show`, and any entries marked stale.
4. Offer to take the next explanation.

After a retext, an undo, or a sync, report what changed and confirm with `human show <code_file>`. `human show project` reports the project entries, their warnings, and the coverage as files with a pin out of the files of the project.

## 7. Train

The sessions live in the training store — an S3 bucket behind a Lambda, one JSON object per session under the user's id — and never on disk: every `train` call, the feed, and the pick read and write there. A key names the user; `human login <key>` once per machine writes it to `~/.config/human/credentials.json`, and without it `human train` refuses and says to log in. `human train --open` starts a session; it stays open until `human train --close`. A retext or a sync that makes an open row follow warns and goes on when the store does not answer; an undo that must check the open session refuses instead. While a session is open, the explain step of §2 writes **the versions** of the same abstraction — two for a new abstraction, three for a sync — and registers them with `human train`, one row per file. The user reads them side by side in the feed — `/human/feed.html` on the same address as the reader — and picks one there. Nothing goes into the map before the close.

The versions, in this order:

1. `best` — the shape the catalog gives this file today, by the rules of §2.
2. `refinement` — sync rows only. The CLI fills this slot itself with the text the map holds, and the feed labels it `current`; write it only when the user asks for a rewrite of that text. A create row has no refinement: the CLI refuses one, and the feed shows two cards, best and free.
3. `free` — the explanation that would help the user most, under no shape rule. Only the anchor rules of §1 hold.

Each version goes in with its own call, the text on stdin like `human map`, and names the shape it follows:

```bash
human train <code_file> --as best --shape sections <<'EOF'
<the text, verbatim>
EOF
```

- `--shape` is the name of the catalog shape the text follows — `rail`, `sections`, `desk`, `dialogue`, `skeleton`. A `free` text that follows no shape leaves it out. The feed shows the shape beside the slot name, so a pick says which shape won, not only which slot.

- `--kind create` is the default: a new abstraction. `--kind sync` is for a file whose code changed — run `human sync` first, so the middle slot holds the repaired text.
- `--entry <id>` when the versions refine an entry that exists; the close runs `human retext`. `--block <name>` when the versions zoom on one block; the close runs `human map --block`. Neither: a first entry of an unmapped file, or a plainer layer whose pins are `e<id>:`.
- The first call for a file makes the row and takes a full copy of the code; the next calls fill the other slots. A row of the project — `human train project` — copies every file of the project for a new abstraction, and the changed files with their diff for a sync row. Every call checks the anchors like `human map`, so a picked text can always be applied. Every call ends with the filled slots and, when one is missing, an `empty:` line — write that slot before the report; the close names every row that still has an empty slot.
- A second call with the same `--as` puts the new text on top and keeps the earlier text in the version's history — this is how a rewrite the user asks for goes in. The feed shows the rewrites of a card under a small picker, `v1 v2 v3`, so the user can read how the text came to be; the pick and the close take the latest. The code must not have changed since the row was made.
- After the last version, tell the user the feed address and stop.

The user may leave a comment with a pick — why that version won. The comment lives in the row; read it when the user asks what a pick meant.

`human train --close`, on the user's word, applies every picked row — `map` or `retext` — writes the new entry id into the row, and marks the session finished. When one apply fails, the session stays open; correct that row and close again. A row without a pick carries over: the next `human train --open` rebuilds it against the code and the map of that day, keeps every version whose anchors still hold, and drops the rest — write the dropped versions again.

## 8. The project

When the user asks how the project works — not one file, the whole — write the telling of the project. Read `human/human.json`'s top entry and the whole-file entry of every mapped file first; the telling stands on them, it does not repeat them.

- What the telling is, is yours to choose from what the project is: a set of things the user can ask for, one run from the first command to the last file written, a rulebook. The catalog has no project shape until the user validates one — when a validated shape fits, take it; when none does, choose the shape that explains, and say which you chose.
- The pins reach the files (`[the door](src/__init__.py)`), one block of a file (`[the gate](src/cmd_map.py:parse_target)`), and the anchors of the file entries (`[the checking](src/cmd_map.py:e1:the gates)`) — the last is the bridge from the project telling to the tellings of the files, so a reader walks down from the project to the file to the code. A plainer layer over the project telling pins with `e<id>:` into it, in the same map.
- One map, `human/project.json`. It holds every project entry; a plainer or a deeper telling is one more entry there, never another file.
- Show the text, then stop; on the user's word, `human map project`. Report as in §6.
- After a change: `human sync project` (§5). A file sync that mends an entry the project pins marks the project entry stale; repair it with `human sync project --stale <id>` on the user's word.
