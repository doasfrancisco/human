# PROMOTION

When you run this file, carry every change to its twin, so the public version always matches the showcase. The change happens in projects/compiler — the full project — and the copy updates the public version in compiler/. A change made on the public side comes back the same way. This file lives in the showcase only — it has no twin.

## The pairs

| showcase (the change happens here) | public twin |
|---|---|
| projects/compiler/decompiler.py | compiler/cli/decompiler.py |
| projects/compiler/cmd_map.py | compiler/cli/cmd_map.py |
| projects/compiler/human.py | compiler/cli/human.py |
| projects/compiler/deploy.py | compiler/deploy.py |
| projects/compiler/skills/decompile/SKILL.md | compiler/skills/decompile/SKILL.md |
| projects/compiler/skills/human/SKILL.md | compiler/skills/human/SKILL.md |
| projects/compiler/skills/shapes/SKILL.md | compiler/skills/shapes/SKILL.md |
| projects/compiler/shapes/README.md | compiler/shapes/README.md |
| projects/compiler/shapes/rail.md | compiler/shapes/rail.md |
| projects/compiler/shapes/skeleton.md | compiler/shapes/skeleton.md |
| projects/compiler/web.html | projects/web.html |

## The run

For each changed file, in this order:

1. Save the old showcase copy before you edit: `cp <showcase file> /tmp/pre_<name>`. This copy is the last version the map knew.
2. Edit the showcase file, then sync its map exactly once: `human sync <showcase file> --old /tmp/pre_<name>`. Never run this twice against the same `--old`.
3. Copy the showcase file over its public twin.
4. Rule 3 of CLAUDE.md runs when the cli changed; rule 4 runs when a skill or a shape changed.
5. Confirm with `human show <showcase file>` and report any warning.

A file without a map skips step 2 and step 5.

When the change was made on the public side first, copy it over the showcase file — saving the old showcase copy first — and run the same sync.
