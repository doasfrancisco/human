---
name: human
description: Compile human into code, then map the code's abstraction and pint to real lines with the human CLI. Use when the user invokes /human, gives an abstraction to compile into a project, asks how a code file works,
---

# human

The user writes the human code first with pins into things that already exist — and AI harness-as-compiler writes the compiled code. 
When the user asks how code that is already there works, AI harness writes human code: a short global explanation as flow instead.

The state is one `human/` folder at the project root: 
    `human/human.json` holds the file list, 
    each code file gets one `abstraction_<path>.json` with the `/` of the path written as `__`, 
    each human file the user makes gets one `human_<name>.json`. 

A human file is:
    A pure abstraction. It's human code over any file the user describes.
    It answers to its bare name, example: `payments`, everywhere a file path goes. 
The `human` CLI owns the `human/` folder — never edit an abstraction directly.
The web comes inside the human program install location, served with `human serve`.



## First use

The first time the user asks you for code in a project with no `human/` folder, start them on human before anything else. 
The user never types `human init`; you run it.


1. **Register the project.** 
`human init` at the root: it makes the `human/` folder, gives the project its id, and starts the reader


2. **A project with code.** 
Write the first global flow of the whole project with `human map <human_file>`:
    Very short, one numbered line per step, with pins. 
    Then write one new line for it: a small change the user would likely want, that breaks nothing. 
    Leave it as a tip because the CLI puts the line in a draft of the flow, under the line you name; the reader opens on it, lights it, shows the tip under it, and lights the green compile button.

```bash
human tip <human_file> --entry 1 --after "<words of the line above it, as the map holds them>" --add "<the new line, with its spaces in front>" --say "<one sentence: what the new line asks for, and that the green button compiles it>"
```


3. **A project with no code.** 
Leave the first abstraction for the user to compile.

```bash
human tip <human_file> --draft "web with lots of animations that explain how human works" --say "Press the green button: claude writes the code for these words."
```

`<human_file>` is the first human file that `human init` made and named in its line "made the first human file <human_file>.human". The tip keeps the words as a draft in it that is not compiled, and the reader opens on it with the green compile button lit.


4. **Give the address.**
Give the user the reader address that `human init` printed, and arm the watch (below). 
The tip goes away when the user compiles that file or clicks "got it".

5. **No code by chat.** 
When the user goes on asking to write code through AI harness chat directly and not compiling human through web, refuse.
Give the reader address and explain shortly how human works



## The run

An abstraction comes in, AI harness writes the new code end to end based on the human abstraction

1. **Register the project.** 
`human init` at the project root: 
    it makes the `human/` folder and the first human file,
    gives the project its id, starts the reader, 
    it gives the project to the human server of the machine, or starts one in the background, prints the reader address. 
Run it again after a file is added or removed, so the file list follows.

2. **Add the user's abstraction**
Before wrting code, hand the abstraction to the Cli. no spelling fixed, no word trimmed:

```bash
human map <code file or human code> --verbatim <<'EOF'
<the abstraction, verbatim>
EOF
```

The abstraction is flagged as the user's abstraction and keeps it, with the pins taken out, as its origin. 
A pin in it is checked like any pin: it goes in when its target exists, and a pin into no real code or abstraction is refused. 
On a new project nothing exists yet, so the words go in plain and the pins come in step 5. 
The origin, taken before the work, is what the gate in step 5 measures against.

3. **Write the code.** 
Write the code files, no comments. 
The gate is static, like a compiler's: the file must parse. `human map` and `human sync` run the block reader over it, and an unparseable file is a refusal. 
There is no run and no test, trust that code which parses does what the abstraction says.

4. **Sync the code that was there before.** 
When the abstractions linked to code that already existed, its lines moved.
`human sync <file>` once per changed file
`human sync <human>` with `--for <id>`, the user's abstraction. 
The code was written for the abstractions, so their spans and pins follow the code and the AI harness rewords nothing in them. 
The other abstractions touched by the change are reworded as usual.
A stale note is repaired with `human sync <that map> --stale <id>`. 
A new project has nothing to sync.

5. **Pin the user's words.**
When the abstraction text holds no pin yet, insert them:
    `[words](src/app.py)` into a file, 
    `[words](src/app.py:block)` into one block 
and hand the text back with a plain retext:

```bash
human retext <human> <id> <<'EOF'
<the abstraction with pins, verbatim>
EOF
```

On a flagged abstraction the CLI strips the pins out and compares the words with the words it holds, character for character. 
One changed character is a refusal. 
Pins go in; the user's abstraction text never change through this road. 
A pin that makes a circle over the maps is refused too.

The user's abstraction text and the code are the whole result. 
Write no abstraction unless the user asks for one.

6. **A human file, when the user asks for one.** 
When the abstraction is about one part of the project and not the whole, it goes in a human file: `human map <bare name>` makes `human/human_<name>.json` on the first run. 
The user makes one from the web too, with the "new human file" line. 
A human file may stand on another human file; the chain never turns back on itself, and the CLI refuses a circle over the whole graph of maps.

7. **Report.**
`human show <file>` per file
`human show <bare_name>`: per human file
The reader runs since `human init`, which printed its address, like `http://localhost:8010/<project id>/human/web.html`; 
`human serve` prints it again, and starts the server when none runs. 
Give the user that address and arm the watch (below) so a writing in the reader reaches you.



## The reader writes

The user writes in the web instead of the AI harness chat. 
Every abstraction is a notepad: 
    a click on its text opens it in place, in its raw form
    pins as `[words](target)`, 
    the same text `human retext` takes
    a click outside, or Escape, shows it drawn again. 
A file with no map shows "new abstraction" above its code, the code itself opens the same way;
A right click on the file tree, on a file, on a folder, or on the empty space under them opens a small list with "create file"
A name box opens under the row that was clicked. 
"create file":
    takes a path from the root; 
    a click on a folder, or on a file, puts the typed name inside that folder,  and empty space takes the root, or the folder that space stands under. 
    if file finishes with <bare_name>.human, take the bare name one word, no folder, no suffix, whatever row the click landed on, and makes an empty map with no code under it, refused when another human file or a file at the root holds that name; it opens on its new abstraction with no code under it, and queues no event either
Escape, or a second pick of the same option, closes the box or the list
The tree follows the files on disk, so a file the AI harness writes shows without a reload. 
Once a map has an abstraction the line is gone, and a new abstraction comes by two roads, each with the user's words:
    On a mapped abstraction, the user highlights words and right-clicks: 
        "expand abstraction" opens a write space on top, whose head "expand on abstraction <id>" is the button;  it goes only with words. 
        An expansion is a deeper abstraction under the highlighted words: the entry pins those words into it, and the reader shows it above the abstraction, as a zoom on a block stands above the whole-file abstraction. 
        A right-click on an abstarction head gives "create abstraction": a higher and shorter new abstraction of that abstraction; it opens the same write space on top, whose head "create on abstraction <id>" is the button, and it goes only with words. 
        The same menu gives "delete abstraction": the head turns into a "delete abstraction <id>" button with a cancel beside it, and a click on it runs `human undo <name> --entry <id>` at once, refused when another abstraction pins to it, with no event because nothing is left for AI harness to do. 
Typing saves nothing; Ctrl+S keeps the draft in the browser
The "compile" button at the top right shows while a text differs from the map, and the map changes only when it is pressed. 
On "compile" the server runs the CLI with the user's abstraction text, one call per changed text:

- an abstraction rewritten → `human retext <name> <id> --verbatim`: the origin is reset, the dependents of the old text are marked stale;
- a first abstraction → `human map <name> --verbatim`: a pin goes in when its target exists, a pin into nothing is refused;
- code on a file with no map → the file is written; when no pin of any map reaches it, nothing more happens;
- an expansion or a create → `human map <name> --verbatim` with the words first, so the map keeps them before AI harness works; the event carries the new abstraction, the target abstraction, and for an expansion the highlighted raw text with its pins.

A refusal comes back to the browser in the CLI's words and nothing is queued. 
A success appends one event to `human/server/events.jsonl: 
    the kind, the absolute paths of the map and the file, the abstraction id, the old and the new text, and for a code write the pins that reach the file
    the reader shows the abstraction as compiling until claude is done.

**Listening.** 
Once per session, arm one persistent Monitor on `human watch` from the project root, with no pipe after it:  a filter such as `grep` can hold back the last event until the next one comes. 
It prints every event AI harness has not finished — one JSON line each — then follows. 
An event printed in an earlier session comes back with `"maybe_started": true`: check `human show` before you sync anything, the run may be half done. 
When the event's run is complete, `human ack <seq>`; the queue advances and the reader drops the mark. Take the events in order, one at a time.

**The run per event.**

- `map` on human file: 
    the user's abstraction text are in, so start at step 3 of the run, the code, the sync with `--for <entry>`, and last the pins into the user's abstraction text with a retext when they hold none.
- `map` on a code file: 
    the user told the file in their abstraction; write or change the code under those words, 
    `human sync <file> --for <entry>`, 
    `human sync` the other maps that pin the file, then pin the words with a retext when they hold none. 
    A file made in the reader is empty: its map holds the words over no lines, and git has no old copy of it, so its first sync is `human sync <name> --old /dev/null`.

- `retext`: 
    Tead the diff of the old and the new text, the files the pins name with their lines. 
    Compare what the old and the new text ask of the program, and decide the new code from the new text: 
        it can add code, remove code, or both. 
    Then `human sync <file>` once per changed file, 
    `human sync <bare name>` for every human file that pins a changed file each with `--for <entry>` on the map the event names, because the code was written for those words and AI harness must not reword them , 
    `human sync <that map> --stale <id>` for every note — each note names the map it waits on —, 
    A retext that pins the new sentences into what they name. 
    The user's entry may get a stale note of its own from the file syncs; the repair keeps the user's voice and warns when it changes a word.

- `code`: 
    the pins in the event say which abstraction ids stand on the changed file, and from which map. 
    `human sync <bare name>` reresolves pins in a human file; 
    `human sync <other file>` re-resolves a cross-file pin from another map. Mend an abstraction that the change made wrong.

- `expand`: 
    the user's abstractions are in with id, `entry`, flagged; 
    `target` is the abstraction id they expand and `words` the highlighted raw text. 
    Write or change the code under the words, `human sync` the maps that pin the file — `--for <entry>` on the map of `name` —, then a retext of `entry` that pins it into the code — never into `target`. 
    Last, a retext of `target` that pins the highlighted words into an anchor of `entry` (`[the words](e<entry>:anchor words)`), so the target points down at the expansion.

- `create`: 
    the user's shorter abstraction over `target` is in with id `entry`, flagged; 
    a retext of `entry` pins its heads with `e<target>:` into the anchors of `target`. 
    It stands below `target` in the reader.



**A new file.** 
On `map`, `retext`, and `expand`, the abstraction text may ask for a thing no file of the project holds. 
Make the file then, no comments, anywhere under the root except `human/`
Give it the pins from the user's abstracion code into it
The file list follows by itself.



## Pins

An abstraction ties itself to real things with inline pins, written like a Markdown link:

- `[the answerer](Hello)`
    the words point at a **block** of the code file: a function or a class.
- `[hello world](e1:the answer)`
    the words point at an **anchor of an earlier abstraction**: abstraction 1's anchor whose bracketed words are `the answer`.
- `[the other file](src/helper.py)`
    the human code points at **another file of the project**, named by its path from the root; `[one piece](src/helper.py:load)` points at one block of it.
- `[the gates](src/cmd_map.py:e1:the checking)`
    the human code point at **an anchor of an abstrction of another file's map**:  abstraction 1 of `src/cmd_map.py`, its anchor `the checking`. 
    This pin lives in a map of pure human code
- `[the money side](payments)`
    the human code points at **a map with pure human code**, by its bare name; 
    `[the sum](payments:e1:the adding)` points at one anchor of one of its abstractions. 
    These live in the human files only.


The rules:

- Pin the words that name the thing. The rest of the line stays plain text.
- Anchor words are unique inside one text. Two pins cannot share the same bracketed words.
- A block target must be a real block of the file. The CLI refuses a dead name.
- An `e<id>:` target must name an existing abstarction and existing anchor words inside it. It cannot make a circle — the check runs over the whole graph of maps — and it never crosses a file border.
- A pin into an abstraction must point at an abstarction that exists: map that entry first.
- Layering runs one way: a shorter higher abstraction pins with `e<id>:` into a more detailed one and holds no lines of its own; the detailed one pins into the code. So the map reads: abstraction→ anchor → block → lines.
- The layout carries no meaning.



## Explain

When the user asks how a file or a block works, read the file and write its abstraction. 
The first abstraction of a code file covers the whole file.
A shorter higher layer abstraction pins its heads with `e<id>:` into the anchors of the abstraction below it.

**Show, then map.** 
When the user asks in the terminal, show the abstraction text and stop, even when the message sounds like approval in advance; on "map it", pipe the exact text into the tool:

```bash
human map <code_file> --block <name> <<'EOF'
<the abstraction, verbatim>
EOF
```

Leave `--block` out for a whole-file abstraction. 
`human map <bare name>` map the a human file. 
The run makes no compiler call: the tool checks every pin, refuses duplicates, dead names and circles, and appends one entry.



## Report

After a map, report in this order: 
    the new abstraction, id, block, lines, and its pins, how many into the code and how many into earlier abstraction; 
    the coverage, covered code lines out of all; the warnings of `human show` and any abstraction marked stale;
After a retext, an undo or a sync, say what changed and confirm with `human show <code_file>`.



## Rewrite

A new rewrite may change anything except the anchors other entries point at; 
the tool refuses a text that drops one. 
When an abstraction text changed, the human code that point into this one are marked stale; repair each with `human sync <map> --stale <id>` on the user's abstraction. 
A retext never takes a stale mark off the entry itself — only the repair does, so the tool knows the mending happened.

On an abstraction flagged as the user's, a retext is pins only, and one changed character is refused; 
`--verbatim` is the road for new words of the user, and the origin is reset. 



## Rollback
"Rollback" or "undo": `human undo <code_file>` removes the last abstraction, and `--entry <id>` one specific abstraction; 
an abstraction that other entries point into cannot go before them.



## Rules

- One project can hold many files;
- When the code changes later, `human sync <code_file>`: exactly once per change, against the exact last-synced old version (`--old <file>` when it is not git HEAD). 
    Add `--for <id>` when the change was written for the words of abstraction `<id>`: that abstratction follows the code with no reword. 
    Then `human sync <bare name>` for every human file whose pins reach the change,
    `human sync <that map> --stale <id>` when a file's abstraction made an abstraction stale there.
- `human sync`, leads an abstraction, because AI harness rewords it when the code forces it: the smallest edit, in the user's voice, and the tool prints a warning with the changed lines. The origin stays in the map; 
- An abstraction mapped before the flag existed is flagged with `human retext <map> <id> --verbatim` and its own text — no word changes, the abstraction becomes the user's.
