# PROMOTION

When you run this file, promote every source file you changed to its showcase twin, so the showcase always shows the code that runs.

## The pairs

| source | twin |
|---|---|
| compiler/cli/decompiler.py | projects/compiler/decompiler.py |
| compiler/cli/cmd_map.py | projects/compiler/cmd_map.py |
| compiler/cli/human.py | projects/compiler/human.py |
| compiler/skills/decompile/SKILL.md | projects/compiler/SKILL.md |
| compiler/PROMOTION.md | projects/compiler/PROMOTION.md |
| projects/web.html | projects/compiler/web.html |
| compiler/deploy.py | projects/deploy/deploy.py |

## The run

For each changed source, in this order:

1. Save the twin before you touch it: `cp <twin> /tmp/pre_<name>`. This copy is the last synced version.
2. Copy the source over the twin: `cp <source> <twin>`.
3. If the twin has a map, sync it exactly once: `human sync <twin> --old /tmp/pre_<name>`. Never run this twice against the same `--old`.
4. Confirm with `human show <twin>` and report any warning.

A twin without a map skips steps 3 and 4.
