# rail

The detailed telling of a whole file — code or markdown. Claude writes it. The reader walks the main run of the file, stage by stage, from the first thing the user does to the last thing the tool writes. For a markdown file the stages follow its sections, one pin per heading.

Validated on: every file of the compiler project.

## Rules

- Three to eight stages down a rail: `●` heads with `│` lines under them.
- A head is an act with the one who acts in it — "the tool reads the file" — never a bare name.
- The pin sits on the right of the head, in parentheses: `([the start](main))`.
- Under each head stand two to four full sentences, indented on the rail. Every sentence has a subject — you, the tool, or the part itself — and a full stop.
- Keep the lines short. Break a sentence over two lines rather than let it run off the screen.
- Say the purpose of a stage in a sentence of its own. A stage that says only what happens reads as trivia.
- No programming words. Say what the thing does in place of its class: "the part that takes one call from a browser".
- A value that comes from outside — a typed address, a file — gets one real example.
- A rule line (`──────`) sets apart the stages that are not the main run.

## Example

```
●  a call comes in                                   ([the answerer](Hello))
  │     Somebody opens the address in a browser.
  │     The answerer takes that one call.
  │     It is built on python's own kit for machines
  │     that answer web calls, so it only has to say
  │     what the answer is.
  │
  ●  the words go back                                 ([the answer](do_GET))
  │     For every page the browser asks for, the same
  │     words go back: hello world.
  │     The answer is marked as plain text, and its
  │     size is said first, so the browser knows
  │     where the answer ends.
  │
  ●  the door opens                                    ([the start](main))
        The start opens door number 8000 and waits.
        It answers calls forever, one after the other,
        until a person stops it.

──────────────
        The last two lines run the start only when a
        person launches this file directly.
```
