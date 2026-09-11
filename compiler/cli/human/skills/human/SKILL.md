---
name: human
description: Compile a human abstraction — free text — into code, then map the code's telling and the human's own words onto the real lines with the human CLI. Use when the user invokes /human or gives an abstraction to compile into a project.
---

# human

The user writes the telling first — free text, no pins — and claude writes the code under it. The state is one `human/` folder at the project root: `human/human.json` holds the project's top entry and the file list, `human/project.json` holds the tellings of the whole — the user's abstraction among them — and each code file gets one `explanation_<path>.json` with the `/` of the path written as `__`. The `human` CLI owns the `human/` folder — never edit a map by hand. The reader is `human/web.html`, served with `human serve`.

## The run

An abstraction comes in as free text: "an http server using python that returns hello world". One run turns it into a project, end to end. The user corrects afterwards, in the reader and with `retext` / `undo` / `sync`.

1. **Register the project.** `human init` at the project root: it makes the `human/` folder, the empty project map, and the reader. Run it again after a file is added or removed, so the file list follows.

2. **Keep the user's words.** Before any code, hand the abstraction to the tool, plain — no pins, no spelling fixed, no word trimmed:

```bash
human map project --verbatim <<'EOF'
<the abstraction, verbatim>
EOF
```

The entry is flagged as the user's words and keeps this text as its origin. A pin in it is refused: the pins come in step 5, when the things they point at exist. This copy, taken before the work, is what the gate in step 5 measures against.

3. **Write the code.** Write the code files with the Write tool, no comments. The gate is static, like a compiler's: the file must parse. `human map` runs the block reader over it, and an unparseable file is a refusal. There is no run and no test — trust that code which parses does what the abstraction says.

4. **Map the detailed telling.** For each code file, one whole-file entry. Its shape comes from the catalog in `shapes/` next to this file — the rail (below) by default, the skeleton when the user thinks in the file's own structure. The shape rule holds for this telling only; the user's abstraction in step 5 is verbatim and takes no shape:

```bash
human map <code_file> <<'EOF'
<the rail, verbatim>
EOF
```

A refusal — a dead name, duplicate anchor words, a circle — is the gate speaking. Read it, fix the text, run again.

5. **Pin the user's words.** Insert pins into the abstraction — `[words](src/app.py:e1:anchor words)` into the anchors of a file's detailed entry, `[words](src/app.py)` or `[words](src/app.py:block)` into the code — and hand it back with a plain retext:

```bash
human retext project <id> <<'EOF'
<the abstraction with pins, verbatim>
EOF
```

On a flagged entry the CLI strips the pins out and compares the words with the words it holds, character for character. One changed character is a refusal. Pins go in; the user's words never change through this road.

6. **Map the project telling.** When the project has more than one file, one more entry in `human/project.json` tells how the files answer together — what the user can ask for and which file does each part. Its shape is yours to choose; its pins reach the files, their blocks, and the anchors of the file entries (`[the answer](src/app.py:e1:the answerer)`). Show it, then `human map project` on the user's word.

7. **Report.** `human show <code_file>` per file and `human show project`: the entries, the coverage, the warnings. Start `human serve` when no server runs, give the user the reader address, `http://localhost:8010/human/web.html`, and arm the watch (below) so a writing in the reader reaches you.

## The reader writes

The user can write in the reader instead of the terminal. Every entry is a notepad: a click on its text opens it in place, in its raw form — pins as `[words](target)`, the same text `human retext` takes — and a click outside, or Escape, shows it drawn again. A file with no map shows "new abstraction" above its code, and the code itself opens the same way; the empty project map shows the same line. A "new file" line at the top of the file tree makes an empty file: the user types a path from the root, folders included, like `src/app.py`, and the file opens on "new abstraction" — no event, because nothing is left for claude to do. The tree follows the files on disk, so a file claude writes shows without a reload. Once a map has an entry the line is gone, and a new telling comes by three roads. On a file with no map, the open "new abstraction" box carries a "decompile <file>" button in place of the words: a click asks claude for the whole-file telling; on an empty file the server refuses it, because the words come first and the code goes under them. On a mapped entry, the user highlights words and right-clicks: "expand abstraction" opens a write space on top, whose head "expand on abstraction <id>" is the button; it goes with or without words. An expansion is a deeper telling under the highlighted words: the entry pins those words into it, and the reader shows it above the entry, as a zoom on a block stands above the whole-file entry. A right-click on an entry head gives "create abstraction": a plainer telling over that entry, nothing to write. The same menu gives "delete abstraction": the head turns into a "delete abstraction <id>" button with a cancel beside it, and a click on it runs `human undo <name> --entry <id>` at once — refused when another entry, the project map or an open training row stands on it — with no event, because nothing is left for claude to do. Typing saves nothing; Ctrl+S keeps the draft in the browser, and "unsaved" stands in the head bar until then. The "compile" button at the top right shows while a text differs from the map, and the map changes only when it is pressed. On "compile" the server runs the CLI with the user's words, one call per changed text:

- an entry rewritten → `human retext <name> <id> --verbatim`: the origin is reset, the dependents of the old words are marked stale;
- a first telling → `human map <name> --verbatim`: plain words, a pin is refused;
- code on a file with no map → the file is written; when no pin of any map reaches it, nothing more happens;
- an expansion with words → `human map <name> --verbatim` with the words first, so the map keeps them before claude works; the event carries the new entry, the target entry and the highlighted raw text with its pins;
- an expansion without words, a decompile, a create → nothing is mapped at the click; the event alone is queued. When the machine is logged in to the training store, the server opens a training session when none is open and the event carries its id as `session`; claude then writes two versions into a row and maps nothing, the user picks in the layer over the reader, and the close maps the pick. Without a login, or when the store does not answer, the event carries no `session` and claude maps what it writes.

A refusal comes back to the browser in the CLI's words and nothing is queued. A success appends one event to `human/server/events.jsonl` — the kind, the absolute paths of the map and the file, the entry id, the old and the new text, and for a code write the pins that reach the file — and the reader shows the entry as compiling until claude is done.

**Listening.** Once per session, arm one persistent Monitor on `human watch` from the project root. It prints every event claude has not finished — one JSON line each — then follows. An event printed in an earlier session comes back with `"replay": true`: check `human show` before you sync anything, the run may be half done. When the event's run is complete, `human ack <seq>`; the queue advances and the reader drops the mark. Take the events in order, one at a time.

**The run per event.**

- `map` on the project: the user's words are in, so start at step 3 of the run — the code, the detailed tellings, the project telling, and last the pins into the user's words with a plain retext.
- `map` on a file: the user told the file in their own words; write or change the code under those words, `human sync` the maps that pin the file, then pin the words with a plain retext. A file made in the reader is empty: its map holds the words over no lines, and git has no old copy of it, so its first sync is `human sync <name> --old /dev/null`.
- `retext`: read the diff of the old and the new text, the files the pins name with their lines, and the whole project map. Write the code that the new words ask for — nothing else. Then `human sync <file>` once per changed file, `human sync project`, `human sync project --stale <id>` for every note, and last a plain retext that pins the new sentences into what they name. The user's entry may get a stale note of its own from the file syncs; the repair keeps the user's voice and warns when it changes a word.
- `code`: the pins in the event say which tellings stand on the changed file. `human sync project` re-resolves the project pins; `human sync <other file>` re-resolves a cross-file pin from another map. Mend a telling that the change made wrong.
- `decompile`: the file has no map; write its whole-file telling — step 4, the rail. With a `session`, write it twice — best by the shape rules, free under no shape rule — and register both with `human train <name> --as best` and `--as free` (§7 of the decompile skill); without one, `human map <name>` it.
- `expand` with `new_text`: the user's words are in as entry `entry`, flagged; `target` is the entry they expand and `words` the highlighted raw text. Write or change the code under the words, `human sync` the maps that pin the file, then a plain retext of `entry` that pins it into the code — never into `target`. Last, a plain retext of `target` that pins the highlighted words into an anchor of `entry` (`[the words](e<entry>:anchor words)`), so the target points down at the expansion.
- `expand` without `new_text`: write the expansion of the highlighted part of `target` yourself — the flow or a tighter rail on what those words tell — pinned into the code and the file entries, never into `target`. With a `session`, write it twice and register both with `human train <name> --target <target> --words <words> --as best` and `--as free`, `--block <name>` too when it zooms on one block; the close maps the pick and queues a `link` event for the last step. Without one, `human map <name>` it, then the same plain retext of `target`: the highlighted words pinned into an anchor of the new entry. A pin from the expansion into `target` would make it a top over `target` and close the circle for that last step.
- `create`: write a plainer telling over `target`, its heads pinned with `e<target>:` into the anchors of `target`. With a `session`, write it twice and register both with `human train <name> --as best` and `--as free`; without one, `human map <name>` it. It stands below `target` in the reader.
- `link`: the close of a training session mapped the pick of an expand row as entry `expansion`; `target` and `words` are as in `expand`. Do the last step alone: a plain retext of `target` that pins the highlighted words into an anchor of `expansion` (`[the words](e<expansion>:anchor words)`).

**A new file.** On `map`, `retext`, and `expand` with `new_text`, the words may ask for a thing no file of the project holds. Make the file then, next to the others — the Write tool, no comments, anywhere under the root except `human/` — and give it what every file gets: its whole-file entry (step 4), `human sync project` so the project telling follows, and the pins from the user's words into it. The file list follows by itself.

## Pins

A telling ties itself to real things with inline pins, written like a Markdown link:

- `[the answerer](Hello)` — the words point at a **block** of the code file: a function or a class.
- `[hello world](e1:the answer)` — the words point at an **anchor of an earlier entry**: entry 1's anchor whose bracketed words are `the answer`.
- `[the other file](src/helper.py)` — the words point at **another file of the project**, named by its path from the root; `[one piece](src/helper.py:load)` points at one block of it.

The rules:

- Pin the words that name the thing. The rest of the line stays plain text.
- Anchor words are unique inside one text. Two pins cannot share the same bracketed words.
- A block target must be a real block of the file. The CLI refuses a dead name.
- An `e<id>:` target must name an existing entry and existing anchor words inside it. It cannot make a circle, and it never crosses a file border.
- Map the detailed entry before the abstraction's pins — a pin into an entry must point at an entry that exists.
- The layout carries no meaning: rails, arrows, and rules between groups are all allowed, because the pins — not the columns — carry the structure.

## The rail shape

The whole-file entry of a code file is a rail of stages, top to bottom, one stage per block:

```
●  you ask for something                             ([main](main))
  │     You type the address into a browser.
  │     The tool keeps the call and nothing else.
  │
  ●  the tool finds the pieces                       ([block_spans](block_spans))
  │     It reads the file top to bottom and notes
  │     every named piece, with its start and its end.
  │
  ●  the last stage
        Two to four sentences, like the others.
```

The rules of the shape:

- The head of a stage is an act with the one who acts in it — "the tool finds the pieces" — in plain words. The pin sits on the right, in parentheses.
- Under the head, two to four full sentences, indented on the rail. Every sentence has a subject and a full stop; the subject is you, the tool, or the part itself.
- Keep the lines short so nothing runs off the screen. Break a sentence over two lines rather than write one long line.
- Write for a reader who does not read code. The reader knows the domain, not the vocabulary of programming. Do not use a programming word — parser, argument, handler, callback — say what the thing does instead: "the part that takes one call from a browser".
- When a part exists only to feed a later stage, say that purpose: "it does this for one reason only: so...". A "what" without a "for what" reads as trivia.
- A value that comes from outside — a typed address, a file — gets one real example.
- Say the purpose of a stage in a sentence of its own.
- A rule line (`──────`) may close the rail or set apart the stages that are not the main run.

A later entry may zoom on one dense block. A zoom may use a tighter form — one line per bound name, `name = what it binds` — because it serves a reader who already walked the rail.

**Reread before you map.** Read each line as a stranger: does it use a word the rail has not defined? Does it use a programming word? Does it say "what" where the reader needs "for what"? Fix those lines first.

## Rules

- One project can hold many files; each file gets its own detailed entry, and the abstraction's pins reach every file from the project map.
- When the code changes later, `human sync <code_file>`: exactly once per change, against the exact last-synced old version (`--old <file>` when it is not git HEAD). Then `human sync project` for the project map, and `human sync project --stale <id>` when a file's entry made the abstraction stale.
- Three roads lead to the abstraction entry. `human retext project <id>` — pins only; the words must match. `human retext project <id> --verbatim` — new words, on the user's word: the user reworded the abstraction, the text with its pins goes in as it is, and the origin is reset. `human sync` — claude rewords it when the code forces it: the smallest edit, in the user's voice, and the tool prints a warning with the changed lines. The origin stays in the map; `human show project` says when the words differ from it, and a `retext --verbatim` with the origin brings them back.
- An abstraction mapped before the flag existed is flagged with `human retext <map> <id> --verbatim` and its own text — no word changes, the entry becomes known as the user's words.
