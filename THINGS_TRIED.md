# Things tried

The goal: easily keep up with the software an AI builds for me. Read it fast, understand its structure, stay current as it changes.

## Tried

- **Visualizing with graphs.** The images of the graph did not compress information. A picture of every node and edge is as large as the program.
- **Abstracting up.** Turn the code into layers of explanation: per-block texts over line ranges, then beats, then stories with examples, then free flows. The mechanics work (anchoring, coverage checks, bottom-up context, links). But the right words and the right explanation at each step become really hard to build. A forced layer produces paraphrase; the good words only exist where the code holds a real surprise.

## Considered and rejected

- **Delta reading** (explain only what changed, never the whole state). Never tried it, but instinct says this is not the way.
- **Traces** (the program as its archetypal runs, data as the protagonist). A trace might still be hard to follow. I still have to think really hard to follow how an algorithm works. What I want is simple explanations of things.
- **Regeneration** (keep the minimal text that regenerates the program, read that instead of the code). I tried this when going from text to code. It is not really an easy path to follow.
- **The predicted FAQ** (the questions I would ask, answered in advance). Weak. I am looking for powerful ways to understand code.
- **The decision log** (the program as the choices that shaped it). Decisions should not matter on code. The structure and the understanding of it give me more power.

## What works when I see it

- **The summary-line format** (proven in chat, 2026-08-15): each answer is a set of collapsed blocks. The summary line gives the answer in 12 words or less. The body gives the proof. Reading only the summary lines gives the full result; a block is opened only when proof is wanted. This made chat answers fast to use — the same shape should work for code.

The one format that reads easily so far: a tiny concrete example, then the rules I would guess wrong. Like this, for a function that cuts a file into per-statement cells:

> Example: a four-line file
>
>     1  def double(n):
>     2      return n + n
>     3
>     4  print(double(2))
>
> becomes three cells: [1,1] the def line, [2,2] the return, [4,4] the print. An inner statement gets its own cell; the outer one keeps only its own lines. A file that is not Python is cut at its blank lines instead.

## Beliefs so far

- Tests and spec-driven development are not the solution. They do not let you understand the structure of a program really fast.
- Structure, and the understanding of it, is what gives me power. The paradigm must compress structure.
- It has to be another form of compression. I do not yet know the right paradigm.
