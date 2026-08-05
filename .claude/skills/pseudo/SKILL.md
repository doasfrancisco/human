---
name: pseudo
description: Code Semantic Zooming over .pseu sidecar files (arXiv 2510.06452). Use when the user invokes /pseudo, asks to generate pseudocode for a code file, zoom in or out on pseudocode, revise code through pseudocode, or sync a .pseu file with its source.
---

# pseudo — Code Semantic Zooming

Pseudocode is the control surface for code. Each source file gets a sidecar `<name>.pseu`. The user reads, zooms, and edits the pseudocode. You keep the pseudocode and the source in agreement.

## Files

- `<name>.pseu` — the pseudocode for `<name>`, in the same folder.
- `.<name>.pseu` — the backup: the last state you produced. Only you write it. The diff of file against backup isolates the user's edits.
- `navigation.md` — one per folder: a file list with one line per file, then the execution flow across the files.

## Tools

- `python decompile_v3/pseu_check.py <file.pseu> ...` — grammar gate. Exit 0 is green.
- `python decompile_v3/pseu_diff.py <file.pseu>` — change list of the file against its backup: ADDITION, DELETION, REPLACEMENT with line numbers, old text, new text, and three context lines.

Run the paths from the repository root, or give the full path to the tool.

## Grammar

```
Pseudocode ::= Goal Dependencies Steps
Goal       ::= 'GOAL:' Description ';'
Dependencies ::= 'DEPENDENCIES:' Description ';'
Steps      ::= 'STEPS:' (Statement)+
Statement  ::= SimpleStmt | WhileStmt | IfStmt | ForStmt
SimpleStmt ::= Description ';'
WhileStmt  ::= 'while' '(' Cond ')' '{' (Statement)+ '}'
IfStmt     ::= 'if' '(' Cond ')' '{' (Statement)+ '}'
               ('elif' '(' Cond ')' '{' (Statement)+ '}')*
               ('else' '{' (Statement)+ '}')?
ForStmt    ::= 'for' '(' Cond ')' '{' (Statement)+ '}'
```

Goal is one sentence for the whole file. Dependencies lists the other code files this file needs, or `none`. A Description is one natural-language sentence. A Cond is a short natural-language condition.

Description rules:

1. Write ASD-STE100 Simplified Technical English: short, active, plain words. No summary jargon.
2. Start with the name the line defines or uses. A function name gets parentheses, like `ask()`. Never start with "The".
3. Name the concrete things the code touches: the names, the files, the keys, the counts.
4. Never copy a code line. Never start a simple statement with `if`, `elif`, `else`, `while`, or `for`.
5. A description must not contain `;`, `{`, or `}`. A condition must not contain `;`, `{`, `}`, or unbalanced parentheses.

Example:

```
GOAL: main.py runs the 2048 game in human mode or AI mode;

DEPENDENCIES: board.py, AI/expectimax.py;

STEPS:
setup reads the mode from the command line and builds the board;
while (the board has a legal move) {
  if (the mode is AI) {
    expectimax() picks the next move;
  }
  else {
    read_key() takes the move from the player;
  }
  board.apply() slides the tiles and adds one random tile;
}
show_score() prints the final score;
```

## Operations

### generate

Input: one source file.

1. Read the source file in full.
2. Write `<name>.pseu` beside it: a coarse first view. One statement per function or stage. Use control statements only where the file's own flow branches or loops.
3. Run the checker. Repair and run again until green, at most 5 attempts. Stop and report when still red.
4. Copy the file over `.<name>.pseu`.
5. Write or update `navigation.md` in that folder.

### zoom in

Input: a `.pseu` file and target lines or a named topic.

1. Read the `.pseu` file and the source file.
2. Replace the target statement with nested statements at one level more detail, from the real code. Keep every other line unchanged.
3. Run the checker until green, at most 5 attempts.
4. Copy the file over the backup.

### zoom out

Input: a `.pseu` file and target lines.

1. Replace the target statements with one statement that holds their meaning. Keep every other line unchanged.
2. Run the checker until green, at most 5 attempts.
3. Copy the file over the backup.

### revise

Input: a user goal in natural language, when the user asks you to edit the pseudocode for them.

1. Edit the `.pseu` file to state the new behavior. Do not touch the source.
2. Run the checker until green.
3. Do not refresh the backup. The edit must stay visible to sync.
4. Run sync next, or wait when the user wants to edit more.

### sync

Input: a `.pseu` file with user edits.

1. Run the diff tool. Stop and report when it prints NO CHANGES.
2. For each change, revise the source file so the code does what the new pseudocode says. Use the context lines and the statement order to find the right code.
3. Show the user the code diff and ask for approval before you write the source file. Skip the question only when the user already told you to proceed.
4. After the source is written: check the code still parses or compiles.
5. Regenerate the changed region of the `.pseu` from the revised source, so the pseudocode reflects the code as it now is.
6. Run the checker until green.
7. Copy the file over the backup.
8. Report the change list and what the regenerated pseudocode shows. When the regenerated pseudocode does not show the user's intent, say so: the user then revises again.

## Hard rules

1. Every `.pseu` you write must pass the checker before you continue.
2. Refresh the backup after generate, zoom in, and zoom out. Never refresh it after a revise, and after sync only once the source is updated.
3. Never write a source file without showing the diff first, unless the user told you to proceed.
4. The user's `.pseu` wording wins: keep their sentences when you regenerate, unless the code no longer matches them.
