---
name: shapes
description: Grow or correct the shape catalog of the human compiler in compiler/shapes/. Use when an abstraction shape did not sufficiently explain and the user shows what the ideal shape would have looked like.
---

# shapes

The catalog is one folder, `compiler/shapes/`: one file per shape, each with its rules and one general example, so it is easy to see when a shape fits. This skill is the only door into that folder — the decompiler and the compiler read it, only this skill writes it.

## The input

The run needs one thing from the user: what the ideal shape would have looked like. A sketch, a photo, a marked screenshot of the reader, or the rewritten abstraction itself — anything that shows the shape the current catalog failed to produce.

## The comparison

Read the input against every shape in the folder — its rules and its example — and take one decision:

- **a new shape**, when no existing shape could have produced the ideal;
- **a rule added or changed**, when a shape fits but one of its rules pushed the words the wrong way;
- **the example changed**, when the rules stand but the example teaches them badly.

The smallest change that would have produced the ideal wins.

## The validation

Show the decision and the exact new text of the shape file. Write nothing yet. On the user's word, write the file; without the word, the catalog does not change. A shape file records which project validated it.

## Why

So the next time the decompiler or the compiler reaches for a shape, it gets closer to the perfect abstraction.
