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

Open `http://localhost:8010/human/web.html`.

Everything the project writes lives in the `human/` folder — one `rm -rf human/` removes it completely.
