---
name: human
description: Compile a human abstraction — free text — into code, then map the code's telling and the human's own words onto the real lines with the human CLI. Use when the user invokes /human or /decompile, gives an abstraction to compile into a project, asks how a code file works, or says "map it".
---

# human

The user writes the telling first — free text, with pins only into things that already exist — and claude writes the code under it. When the user asks how code that is already there works, claude writes its telling instead, in the shape the catalog gives the file (Explain, below). The state is one `human/` folder at the project root: `human/human.json` holds the project's top entry and the file list, `human/project.json` holds the tellings of the whole — the user's abstraction among them —, each code file gets one `explanation_<path>.json` with the `/` of the path written as `__`, and each human file the user makes gets one `human_<name>.json`. A human file is a map with no code under it, like the project map, but over the files the user chooses: it answers to its bare name — `payments` — everywhere a file path goes. The `human` CLI owns the `human/` folder — never edit a map by hand. The reader comes inside the human program, served with `human serve`.

## The run

An abstraction comes in as free text: "an http server using python that returns hello world". One run turns it into a project, end to end. The user corrects afterwards, in the reader and with `retext` / `undo` / `sync`.

1. **Register the project.** `human init` at the project root: it makes the `human/` folder and the empty project map, and gives the project its id. Run it again after a file is added or removed, so the file list follows.

2. **Keep the user's words.** Before any code, hand the abstraction to the tool — no spelling fixed, no word trimmed:

```bash
human map project --verbatim <<'EOF'
<the abstraction, verbatim>
EOF
```

The entry is flagged as the user's words and keeps this text, with the pins taken out, as its origin. A pin in it is checked like any pin: it goes in when its target exists, and a pin into no real code or abstraction is refused. On a new project nothing exists yet, so the words go in plain and the pins come in step 5. The origin, taken before the work, is what the gate in step 5 measures against.

3. **Write the code.** Write the code files with the Write tool, no comments. The gate is static, like a compiler's: the file must parse. `human map` and `human sync` run the block reader over it, and an unparseable file is a refusal. There is no run and no test — trust that code which parses does what the abstraction says.

4. **Sync the code that was there before.** When the words went onto code that already existed, its lines moved: `human sync <file>` once per changed file, and `human sync project` with `--for <id>`, the entry of the user's words. The code was written for those words, so their spans and pins follow the code and claude rewords nothing in them. The other tellings the change touches are reworded as usual, and a stale note is repaired with `human sync <that map> --stale <id>`. A new project has nothing to sync.

5. **Pin the user's words.** When the words hold no pin yet, insert them — `[words](src/app.py)` into a file, `[words](src/app.py:block)` into one block — and hand the text back with a plain retext:

```bash
human retext project <id> <<'EOF'
<the abstraction with pins, verbatim>
EOF
```

On a flagged entry the CLI strips the pins out and compares the words with the words it holds, character for character. One changed character is a refusal. Pins go in; the user's words never change through this road. A pin that makes a circle over the maps is refused too.

The user's words and the code are the whole result. Write no telling of a file and no telling of the project unless the user asks for one: the explain road (Explain, below) and the reader's decompile, expand and create give those.

6. **A human file, when the user asks for one.** When the telling is about one part of the project and not the whole, it goes in a human file: `human map <bare name>` makes `human/human_<name>.json` on the first run and takes the same pins as the project telling. The user makes one from the reader too, with the "new human file" line. A human file may stand on another human file; the chain never turns back on itself, and the CLI refuses a circle over the whole graph of maps.

7. **Report.** `human show <code_file>` per file and `human show project`: the entries, the coverage, the warnings. Run `human serve`: it starts the one human server of the machine, or gives the project to the one that runs, and prints the reader address, like `http://localhost:8010/<project id>/human/web.html`. Give the user that address and arm the watch (below) so a writing in the reader reaches you.

## The reader writes

The user can write in the reader instead of the terminal. Every entry is a notepad: a click on its text opens it in place, in its raw form — pins as `[words](target)`, the same text `human retext` takes — and a click outside, or Escape, shows it drawn again. A file with no map shows "new abstraction" above its code, and the code itself opens the same way; the empty project map shows the same line. A right click on the file tree — on a file, on a folder, or on the empty space under them — opens a small list with "create file" and "create human", and a name box opens under the row that was clicked. "create file" takes a path from the root, folders included, like `src/app.py`; a click on a folder, or on a file, puts the typed name inside that folder, and empty space takes the root, or the folder that space stands under. The file opens on "new abstraction" — no event, because nothing is left for claude to do. "create human" takes a bare name — one word, no folder, no suffix, whatever row the click landed on — and makes an empty map with no code under it, refused when another human file or a file at the root holds that name; it opens on its new abstraction with no code under it, and queues no event either. Escape, or a second pick of the same option, closes the box or the list, and a pick of the other option turns the box to that kind and empties it. The tree follows the files on disk, so a file claude writes shows without a reload. Once a map has an entry the line is gone, and a new telling comes by three roads. On a file with no map, the open "new abstraction" box carries a "decompile <file>" button in place of the words: a click asks claude for the whole-file telling; on an empty file the server refuses it, because the words come first and the code goes under them. On a mapped entry, the user highlights words and right-clicks: "expand abstraction" opens a write space on top, whose head "expand on abstraction <id>" is the button; it goes with or without words. An expansion is a deeper telling under the highlighted words: the entry pins those words into it, and the reader shows it above the entry, as a zoom on a block stands above the whole-file entry. A right-click on an entry head gives "create abstraction": a plainer telling over that entry, nothing to write. The same menu gives "delete abstraction": the head turns into a "delete abstraction <id>" button with a cancel beside it, and a click on it runs `human undo <name> --entry <id>` at once — refused when another entry, the project map or an open training row stands on it — with no event, because nothing is left for claude to do. Typing saves nothing; Ctrl+S keeps the draft in the browser, and "unsaved" stands in the head bar until then. The "compile" button at the top right shows while a text differs from the map, and the map changes only when it is pressed. On "compile" the server runs the CLI with the user's words, one call per changed text:

- an entry rewritten → `human retext <name> <id> --verbatim`: the origin is reset, the dependents of the old words are marked stale;
- a first telling → `human map <name> --verbatim`: a pin goes in when its target exists, a pin into nothing is refused;
- code on a file with no map → the file is written; when no pin of any map reaches it, nothing more happens;
- an expansion with words → `human map <name> --verbatim` with the words first, so the map keeps them before claude works; the event carries the new entry, the target entry and the highlighted raw text with its pins;
- an expansion without words, a decompile, a create → nothing is mapped at the click; the event alone is queued. When the machine is logged in to the training store, the server opens a training session when none is open for this project — a session belongs to one user and one project, the id `human init` wrote into `human/human.json` — and the event carries its id as `session`; claude then writes two versions into a row and maps nothing, the user picks in the layer over the reader, and the close maps the pick. Without a login, or when the store does not answer, the event carries no `session` and claude maps what it writes.

A refusal comes back to the browser in the CLI's words and nothing is queued. A success appends one event to `human/server/events.jsonl` — the kind, the absolute paths of the map and the file, the entry id, the old and the new text, and for a code write the pins that reach the file — and the reader shows the entry as compiling until claude is done.

**Listening.** Once per session, arm one persistent Monitor on `human watch` from the project root. It prints every event claude has not finished — one JSON line each — then follows. An event printed in an earlier session comes back with `"replay": true`: check `human show` before you sync anything, the run may be half done. When the event's run is complete, `human ack <seq>`; the queue advances and the reader drops the mark. Take the events in order, one at a time.

**The run per event.**

- `map` on the project: the user's words are in, so start at step 3 of the run — the code, the sync with `--for <entry>`, and last the pins into the user's words with a plain retext when they hold none.
- `map` on a file: the user told the file in their own words; write or change the code under those words, `human sync <file> --for <entry>`, `human sync` the other maps that pin the file, then pin the words with a plain retext when they hold none. A file made in the reader is empty: its map holds the words over no lines, and git has no old copy of it, so its first sync is `human sync <name> --old /dev/null`.
- `retext`: read the diff of the old and the new text, the files the pins name with their lines, and the whole project map. Write the code that the new words ask for — nothing else. Then `human sync <file>` once per changed file, `human sync project` and `human sync <bare name>` for every human file that pins a changed file — each with `--for <entry>` on the map the event names, because the code was written for those words and claude must not reword them —, `human sync <that map> --stale <id>` for every note — each note names the map it waits on —, and last a plain retext that pins the new sentences into what they name. The user's entry may get a stale note of its own from the file syncs; the repair keeps the user's voice and warns when it changes a word.
- `code`: the pins in the event say which tellings stand on the changed file, and from which map. `human sync project` re-resolves the project pins, `human sync <bare name>` those of a human file; `human sync <other file>` re-resolves a cross-file pin from another map. Mend a telling that the change made wrong.
- `decompile`: the file has no map; write its whole-file telling — the rail, below. With a `session`, write it twice — best by the shape rules, free under no shape rule — and register both with `human train <name> --as best` and `--as free` (Train, below); without one, `human map <name>` it.
- `expand` with `new_text`: the user's words are in as entry `entry`, flagged; `target` is the entry they expand and `words` the highlighted raw text. Write or change the code under the words, `human sync` the maps that pin the file — `--for <entry>` on the map of `name` —, then a plain retext of `entry` that pins it into the code — never into `target`. Last, a plain retext of `target` that pins the highlighted words into an anchor of `entry` (`[the words](e<entry>:anchor words)`), so the target points down at the expansion.
- `expand` without `new_text`: write the expansion of the highlighted part of `target` yourself — the flow or a tighter rail on what those words tell — pinned into the code and the file entries, never into `target`. With a `session`, write it twice and register both with `human train <name> --target <target> --words <words> --as best` and `--as free`, `--block <name>` too when it zooms on one block; the close maps the pick and queues a `link` event for the last step. Without one, `human map <name>` it, then the same plain retext of `target`: the highlighted words pinned into an anchor of the new entry. A pin from the expansion into `target` would make it a top over `target` and close the circle for that last step.
- `create`: write a plainer telling over `target`, its heads pinned with `e<target>:` into the anchors of `target`. With a `session`, write it twice and register both with `human train <name> --as best` and `--as free`; without one, `human map <name>` it. It stands below `target` in the reader.
- `link`: the close of a training session mapped the pick of an expand row as entry `expansion`; `target` and `words` are as in `expand`. Do the last step alone: a plain retext of `target` that pins the highlighted words into an anchor of `expansion` (`[the words](e<expansion>:anchor words)`).

**A new file.** On `map`, `retext`, and `expand` with `new_text`, the words may ask for a thing no file of the project holds. Make the file then, next to the others — the Write tool, no comments, anywhere under the root except `human/` — and give it the pins from the user's words into it, and `human sync project` so the project map follows. The file list follows by itself.

## Pins

A telling ties itself to real things with inline pins, written like a Markdown link:

- `[the answerer](Hello)` — the words point at a **block** of the code file: a function or a class.
- `[hello world](e1:the answer)` — the words point at an **anchor of an earlier entry**: entry 1's anchor whose bracketed words are `the answer`.
- `[the other file](src/helper.py)` — the words point at **another file of the project**, named by its path from the root; `[one piece](src/helper.py:load)` points at one block of it.
- `[the gates](src/cmd_map.py:e1:the checking)` — the words point at **an anchor of an entry of another file's map**: entry 1 of `src/cmd_map.py`, its anchor `the checking`. This pin lives in a map with no code under it only.
- `[the money side](payments)` — the words point at **a map with no code under it**, by its bare name; `[the sum](payments:e1:the adding)` points at one anchor of one of its entries. These two live in the project map and in the human files only.

The rules:

- Pin the words that name the thing. The rest of the line stays plain text.
- Anchor words are unique inside one text. Two pins cannot share the same bracketed words.
- A block target must be a real block of the file. The CLI refuses a dead name.
- An `e<id>:` target must name an existing entry and existing anchor words inside it. It cannot make a circle — the check runs over the whole graph of maps — and it never crosses a file border.
- A pin into an entry must point at an entry that exists: map that entry first.
- The pins of `human/human.json` are file and `file:block` pins only.
- When code moves to another file, its telling moves with it. The old entry keeps one short stage with a pin to the new file, never the sentences. A sentence lives in one map only; every other map points at it.
- Layering runs one way: a plainer telling pins with `e<id>:` into a more detailed one and holds no lines of its own; the detailed one pins into the code. So the map reads: telling → anchor → block → lines.
- The layout carries no meaning: rails, arrows, and rules between groups are all allowed, because the pins — not the columns — carry the structure.

## Explain

When the user asks how a file or a block works, or a `decompile` event comes in, read the file and write its telling. The folder `shapes/` next to this file is the catalog of validated shapes, each with its rules and one example. The shape follows the kind of file:

- a file with one real run — a web page, a script that runs top to bottom — takes the **rail** (`shapes/rail.md`, below);
- a code file that is a set of functions takes the **sections** (`shapes/sections.md`): one head per block in story order, the inputs in the head, full sentences under it, the small helpers below a rule;
- a file that only reads what the user types and hands it on takes the **desk** (`shapes/desk.md`): one head per command;
- a rulebook — a skill, a procedure — takes the **dialogue** (`shapes/dialogue.md`): who says what, turn by turn;
- a zoom on one block takes the rail.

Read the shape file before you write. When the user has validated another shape for a project — like the skeleton, the file's own structure in plain words — that shape takes the whole-file place there.

**Who the reader is.** Write for a reader who does not read code. The reader knows the domain of the file, not the vocabulary of programming. When the user validates a different level, keep that level for the rest of the session.

**The first telling of a code file covers the whole file.** Every later telling is a zoom on one block or a plainer layer over the whole. A zoom walks the block's own run and pins the block and the names inside it. A plainer layer pins its heads with `e<id>:` into the anchors of the entry below it.

The wording rules hold for every shape:

- Use the real names from the code only inside pin targets. Do not invent names.
- Simple words, one idea per line.
- Do not write a coined word — a word of programming or of this project — before a line defines it, or say what the thing does in place of its class.
- When a binding exists only to feed one later step, the line says that purpose.
- Compress by dropping the fields the reader does not need yet, never by dropping the verbs.
- A value that comes from outside — typed input, a file — gets one real example and what the step keeps from it.
- A definition states the permission before the constraint.
- When the user says which phrasing made them understand, build the definition from those exact words.
- A definition lives in place, indented under the stage where the reader meets it, never in an entry of its own.
- The answer is never prose. "Explain simpler" gets a simpler text in the same shape.

**A markdown file.** Its blocks are its headings. A document that tells a procedure takes the dialogue; any other document takes the rail, one stage per section. **A web page.** Its blocks are every tag that appears once and every named function inside a `<script>`. A zoom on the look takes one line per visual role. `human lines <code_file>` shows the file with line numbers.

**Show, then map.** When the user asks in the terminal, show the text and stop, even when the message sounds like approval in advance; on "map it", pipe the exact text into the tool:

```bash
human map <code_file> --block <name> <<'EOF'
<the telling, verbatim>
EOF
```

Leave `--block` out for a whole-file entry. `human map .` maps the top entry of `human/human.json`, one line per file; `human map project` and `human map <bare name>` map the project telling and a human file. A `decompile` event from the reader maps at once, because the click was the word. The run makes no claude call: the tool checks every pin, refuses duplicates, dead names and circles, and appends one entry.

## Report

After a map, report in this order: the new entry — id, block, lines, and its pins, how many into the code and how many into earlier entries —; the coverage, covered code lines out of all; the warnings of `human show` and any entry marked stale; then offer the next telling — a zoom on one block, a plainer one over the whole, or the project. After a retext, an undo or a sync, say what changed and confirm with `human show <code_file>`.

## Rewrite and rollback

The user pastes text — a whole entry, a fragment, or one line — instead of naming entry ids. Find the entry it belongs to; a pin in the paste is what the user points at. A clearer wording goes in place with `human retext <code_file> <id>`. The new text may change anything except the anchors other entries point at; the tool refuses a text that drops one. When a word changed, the entries that point into this one are marked stale; repair each with `human sync <map> --stale <id>` on the user's word. A retext never takes a stale mark off the entry itself — only the repair does, so the tool knows the mending happened.

On an entry flagged as the user's words, a plain retext is pins only, and one changed character is refused; `--verbatim` is the road for new words of the user, and the origin is reset. "Rollback" or "undo": `human undo <code_file>` removes the last entry, and `--entry <id>` one entry; an entry that other entries point into cannot go before them.

## Train

The sessions live in the training store, under the user's id and stamped with the project id `human init` wrote into `human/human.json`, never on disk. `human login <key>` once per machine; without it `human train` refuses. `human train --open` starts a session and `human train --close` ends it; a reader write that asks claude for a telling opens one by itself. While a session is open, write **the versions** of one telling and register each with its own call, text on stdin, with the shape it follows:

```bash
human train <code_file> --as best --shape sections <<'EOF'
<the text, verbatim>
EOF
```

1. `best` — the shape the catalog gives the file, by the rules of Explain.
2. `refinement` — sync rows only; the tool fills it with the text the map holds, shown as `current`. Write it only when the user asks for a rewrite of that text.
3. `free` — the telling that would help the user most, under no shape rule; only the pin rules hold.

- `--shape` names the catalog shape: `rail`, `sections`, `desk`, `dialogue`, `skeleton`. A `free` text that follows none leaves it out.
- `--kind create` is the default; `--kind sync` is for a changed file, after `human sync`.
- `--entry <id>` refines an entry that exists, and the close runs a retext; `--block <name>` zooms on one block; `--target <id> --words <text>` expands highlighted words, must not pin into the target, and the close queues a `link` event.
- The first call makes the row and copies the code; the next calls with the same options fill the other slots. Every call checks the pins like `human map` and ends with the filled slots and an `empty:` line for a missing one: fill it before the report.
- A second call with the same `--as` keeps the earlier text in the version's history, shown as `v1 v2 v3`; the pick takes the latest.
- After the last version, tell the user the versions wait in the reader and stop.

The close maps every picked row. A create row with no pick takes best, or free when best is missing; a sync row with no pick carries over to the next session. When one apply fails, the session stays open; correct that row and close again.

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

- One project can hold many files; the abstraction's pins reach every file from the project map.
- When the code changes later, `human sync <code_file>`: exactly once per change, against the exact last-synced old version (`--old <file>` when it is not git HEAD). Add `--for <id>` when the change was written for the words of entry `<id>`: that entry follows the code with no reword. Then `human sync project` for the project map, `human sync <bare name>` for every human file whose pins reach the change, and `human sync <that map> --stale <id>` when a file's entry made an abstraction stale there.
- Three roads lead to the abstraction entry. `human retext project <id>` — pins only; the words must match. `human retext project <id> --verbatim` — new words, on the user's word: the user reworded the abstraction, the text with its pins goes in as it is, and the origin is reset. `human sync` — claude rewords it when the code forces it: the smallest edit, in the user's voice, and the tool prints a warning with the changed lines. The origin stays in the map; `human show project` says when the words differ from it, and a `retext --verbatim` with the origin brings them back.
- An abstraction mapped before the flag existed is flagged with `human retext <map> <id> --verbatim` and its own text — no word changes, the entry becomes known as the user's words.
