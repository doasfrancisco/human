---
name: human
description: Compile a human abstraction — free text — into code, then map the code's telling and the human's own words onto the real lines with the human CLI. Use when the user invokes /human or gives an abstraction to compile into a project.
---

# human

The user writes the telling first — free text, no pins — and claude writes the code under it. The state is one project folder under `projects/<name>/`: the code files, one `explanation_<file>.json` per code file, the abstraction in `abstraction.txt`, and one entry per project in `projects/projects.json`. The `human` CLI owns the map files — never edit one by hand. The reader is `projects/web.html`.

## The run

An abstraction comes in as free text: "an http server using python that returns hello world". One run turns it into a project, end to end. The user corrects afterwards, in the reader and with `retext` / `undo` / `sync`.

1. **Keep the user's words.** Write the abstraction verbatim into `<project>/abstraction.txt`. Do not fix a spelling, do not trim a word. This file is the source the gate in step 5 measures against.

2. **Write the code.** Make the project folder and write the code files with the Write tool, no comments. The gate is static, like a compiler's: the file must parse. `human map` runs the block reader over it, and an unparseable file is a refusal. There is no run and no test — trust that code which parses does what the abstraction says.

3. **Register the project.** `human init projects/<name>` scans the folder for code files and writes the project's entry in `projects.json`. Run it again after a file is added or removed.

4. **Map the detailed telling.** For each code file, one whole-file entry in the rail shape (below):

```bash
human map <code_file> <<'EOF'
<the rail, verbatim>
EOF
```

A refusal — a dead name, duplicate anchor words, a circle — is the gate speaking. Read it, fix the text, run again.

5. **Map the user's words on top.** Insert pins into the abstraction — `[words](e1:anchor words)` pointing into the detailed entry — and map with the verbatim gate:

```bash
human map <code_file> --verbatim abstraction.txt <<'EOF'
<the abstraction with pins, verbatim>
EOF
```

The CLI strips the pins out and compares the rest against `abstraction.txt` character for character. A changed word is a refusal. Pins go in; the user's words never change.

6. **Report.** `human show <code_file>` per file: the entries, the coverage, the warnings. Give the user the reader address when a server runs over `projects/`.

## Pins

A telling ties itself to real things with inline pins, written like a Markdown link:

- `[the answerer](Hello)` — the words point at a **block** of the code file: a function or a class.
- `[hello world](e1:the answer)` — the words point at an **anchor of an earlier entry**: entry 1's anchor whose bracketed words are `the answer`.
- `[the other file](helper.py)` — the words point at **another file of the project**; `[one piece](helper.py:load)` points at one block of it.

The rules:

- Pin the words that name the thing. The rest of the line stays plain text.
- Anchor words are unique inside one text. Two pins cannot share the same bracketed words.
- A block target must be a real block of the file. The CLI refuses a dead name.
- An `e<id>:` target must name an existing entry and existing anchor words inside it. It cannot make a circle, and it never crosses a file border.
- Map the detailed entry before the abstraction — an `e<id>:` pin must point at an entry that exists.
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

- One project can hold many files; each file gets its own detailed entry, and the abstraction's pins may cross files with `[words](file.py:block)` pins.
- When the code changes later, `human sync <code_file>`: exactly once per change, against the exact last-synced old version (`--old <file>` when it is not git HEAD).
- When the user rewords the abstraction, write the new words to `abstraction.txt` first, then `human retext` with the pins re-inserted — the same verbatim law holds by hand: strip the pins, and the text must equal the file.
- A repair must never change the words of the abstraction entry. When a sync or a stale repair would touch them, re-pin only.
