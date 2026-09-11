# The human programming language

Human is the first open source AI programming language that makes it possible to code using LLMs.

## Setup

Requires [Claude Code](https://claude.com/claude-code) and [uv](https://docs.astral.sh/uv/).

```bash
uv tool install humanlang
human skills          # installs the /human and /decompile skills into ~/.claude/skills
```

Upgrade to the latest version with:

```bash
uv tool upgrade humanlang
human skills          # refresh the installed skills too
human init            # run in each project to refresh its reader
```

## Use

In your project:

```bash
human init            # creates the human/ folder: the maps and the reader live there
```

Then in Claude Code:

- `/human <abstraction>` — compile free text into code, mapped to your words.
- `/decompile <file>` — explain an existing file, pinned to its lines.

## Read

```bash
human serve
```

Open `http://localhost:8010/human/web.html`. Every entry opens as a notepad, and "compile" hands your words to claude. A "new file" line at the top of the file tree makes an empty file, in a new folder too; write its abstraction and claude writes the code under it.

## Train

```bash
human train --open    # start a session; /decompile now writes three versions per file
human train --close   # map the versions you picked and finish the session
```

Pick in the reader at `http://localhost:8010/human/web.html`: an open session shows as a layer over it, swipe sideways for the versions, down for the next file, and say why you picked if you want. A "close training" button applies the picks; a new abstraction you do not pick takes best, a sync you do not pick carries over. A write in the reader that asks claude for a telling opens a session by itself. The sessions live in the training store, one JSON per session under your user and per project, with a copy of the code and of the abstraction each row worked on; `human login <key>` once per machine names you, and `human init` gives the project its id.

Everything the project writes lives in the `human/` folder — one `rm -rf human/` removes it completely.
