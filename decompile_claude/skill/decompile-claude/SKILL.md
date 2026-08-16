---
name: decompile-claude
description: Explain a code file in the flow shape and map each explanation onto real code lines with the dmap CLI. Use when the user invokes /decompile-claude, asks for a flow-shape explanation of code, or says "map it" / "map this explanation".
---

# decompile-claude

Two operations: **explain** and **map**. The state is one JSON file per code file, `explanation_<file_name>.json`, written next to the code file. The dmap CLI owns that file — never edit it by hand; every operation you need is a dmap command (`map`, `retext`, `undo`, `show`, `lines`). The map grows delta by delta: every map run appends one entry and never changes the entries before it.

## How the user points at things

The user pastes text — a whole entry, a fragment, or one line — instead of naming entry ids or parts. Find what the pasted text belongs to in the map file, then act on that entry or part. When the paste is one flow line, it names a part; "go deeper" on it means a new zoom entry inside that part's lines.

## 1. Explain

When the user asks how a file or a block works, read the file and write the explanation in the flow shape:

```
name            = what the step binds, in simple words    (helper_one)

for each item, bottom up:
    one line per inner step    (helper_two)
```

**The first explanation of a file covers the whole file.** Its flow is the module layer, top to bottom: the imports, each module binding, one line per function or class with its role — name the block in parentheses at the end of its line, so the map ties the line to the block's span — and the entry point. After the first map run the coverage is the full file. Every later explanation is a zoom.

The rules of the shape:

- One line per bound name. The left column is the name. The line ends with the real function names, in parentheses.
- One step is one physical line. Never break a line for width — the reader slides sideways. A new line starts only for a new step.
- A loop is a header line with indented step lines.
- Use the real names from the code. Do not invent names.
- Simple words, one idea per line. A dense clause after the `=` is what makes a flow hard to follow.
- A zoom hangs on one instruction — one line of the parent entry's text. When the user pastes a line, that line is the instruction. The zoom explanation must stay inside the code lines that instruction reaches.

**The question shape.** When a block is a chain of checks — a gate, a validator — the `name = must be ...` form reads badly. Write each check as a question, with its stop error on the right:

```
for each part, in the order of the text:
    is the part name new?                            no -> PART-NAME stops
    do the own lines sit inside the block lines?     no -> PART-BOUNDS stops
```

Each question and its answer stay on one line.

**Definitions live inside the flow.** When a concept needs a definition, put it as indented lines at the point where the reader meets it — the first lines under the loop or the name that uses it. Do not create a separate zoom entry just to hold a definition; the user found that confusing.

**The format is always the flow shape** for code, even when the user says "explain simpler" — answer with a simpler flow, not with prose. One short read-me line under the flow is fine; paragraphs are not. Prose is right only for questions about the system itself ("what is a part, why do we have parts"), not about code.

Run `dmap lines <code_file>` to see the file with line numbers.

**Show the explanation, then stop. Do not touch the map until the user gives the word.** This holds even when the user's message sounds like approval in advance ("add it", "what do you recommend?") — show the flow first, map on the next word.

## 2. Map

When the user says "map it", or gives an explanation to map, pipe the exact explanation text into dmap:

```bash
dmap map <code_file> --block <name> --within <id>:<part> --at "<instruction>" <<'EOF'
<the explanation text, verbatim>
EOF
```

- `--block` is the block the text explains. Omit it when unsure; the mapper infers it.
- `--within` names the parent entry and part when this explanation expands one part of an earlier entry, for example `--within 1:layers`. Omit it for the first entry of a file.
- `--at` gives the instruction: the exact line of the parent part's text that this zoom expands, without its leading spaces. Every zoom carries one — dmap rejects a zoom without it. The mapper can find the instruction alone, but pass `--at` when the user pointed at a line.
- **Everything after the first entry is a zoom.** The first entry of a file is the whole-file flow and the only top-level entry. Every other explanation hangs with `--within` on the part, and through its instruction on the line, that reaches it — even when the user asked about a block by name. In the reader a zoom folds under its instruction line; a top-level entry always shows and never folds.
- dmap runs `claude -p` for the mapping, checks the answer up to 8 times, appends one entry, recomputes coverage, and writes the file. It returns a delta only.

## 3. Rewrite and rollback

When the user approves a clearer wording for an entry that is already mapped, do not map again — replace the text in place:

```bash
dmap retext <code_file> <id> <<'EOF'
<the new text, verbatim>
EOF
```

The rewrite must keep every column-0 part name, in order — the mapped lines and the web reader hang on those names. It must also keep every line a child zoom hangs on as its instruction. dmap rejects a text that drops or renames a part, or that drops an instruction line with a child.

When the user says "rollback" or "undo", remove the last entry:

```bash
dmap undo <code_file>
```

Undo pops the newest entry and recomputes coverage. An entry with children cannot be undone before its children.

## 4. Report

After a map run, report to the user in this order:

1. The new entry: id, block, lines, part names, and its `within` parent if it has one.
2. Coverage: covered code lines out of total code lines.
3. The lines that are not covered. Say what each missing range is: the imports, the entry point, or a block with no explanation yet.
4. Offer to take the next explanation.

After a retext or an undo, report what changed and confirm the parts and coverage with `dmap show <code_file>`.
