# todo

## Structure for the part gates, not text matching

The gates that tie parts to text lines all work by flat text matching today: retext matches the first word of a line against a part name, the reader matched chunks to parts by count, the map-time instruction check falls back to "any line of the entry" when the counts disagree. First-word matching is flaky: a definition line that happens to start with a part's word fools it, and two parts with the same first word collide.

The structural fix, in steps:

- Cheap first: match the full part name as the prefix of a stripped line (before the `=` or the `:`), not the first word. In-order walk over every line stays.
- Real structure: parse the flow text into an indent tree - each line a node under the nearest shallower line. A part anchors to a node. Loops and definition lines become children instead of noise the matcher steps over.
- Store each part's anchor line in the JSON at map time, so retext and the readers stop re-deriving the text-to-part pairing on every load.

Build the tree only if prefix matching still misfires.

## The coined-term gate (dmap)

The flow-shape rules against jargon live only in SKILL.md. An ungated rule is a wish: the first `main` zoom of decompile_v14 used "sequent", "premises", "silent", "pure" with no definitions, and only the user's confusion caught it.

The gate, at map time, deterministic where possible:

- Collect the nouns of each flow line of the new text.
- A noun passes when it is plain English, or a name from the block span table, or defined in an earlier indented line of the same text.
- Reject the text when a coined noun appears before its definition; name the line, so the retry loop can fix it — same shape as the check_entry gates.

Open questions:

- "Plain English" needs a word list or a classifier call. A word list is free but incomplete; a classifier call costs one more claude run per map.
- A too-strict gate blocks good texts. Start it as a warning, not a stop?

Hold this until the stale-map work (dmap sync) is done, and build it only if the SKILL.md rules keep failing.
