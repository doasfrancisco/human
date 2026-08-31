# human

Two directions, one tool. **Decompile**: Claude explains an existing code file in plain words, and every word is pinned to the real lines. **Compile**: you write a free-text abstraction, Claude writes the code under it, and your words are pinned to the real lines too. The `human` CLI owns the map files; a web reader shows the result.

## Setup

Requires [Claude Code](https://claude.com/claude-code) and [uv](https://docs.astral.sh/uv/).

```bash
uv tool install compiler/cli          # installs the `human` CLI
python3 compiler/deploy.py --all      # installs the skills into ~/.claude/skills
```

## Use

In Claude Code, inside this repo:

- `/decompile <file>` — explain an existing file, pinned to its lines.
- `/human <abstraction>` — compile free text into a project under `projects/`.

## Read

```bash
cd projects && python3 -m http.server 8010
```

Open `http://localhost:8010/web.html` and pick a project.
