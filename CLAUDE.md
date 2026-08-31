# Project rules

1. Never add comments or docstrings to code unless I explicitly tell you to. This includes module docstrings, class docstrings, function/method docstrings, inline `#` comments, field-level comments, and section-divider comments. Write code with no commentary by default.
2. Only report to me in ASD-STE100 Simplified Technical English.
3. If you make any changes to the CLI (compiler/cli/human.py, decompiler.py, or cmd_map.py) update the version in compiler/cli/pyproject.toml so reinstalling works and doesn't cache. Reinstall the bumped version with `uv tool install --reinstall .` from compiler/cli.
4. If you make any changes to a skill under compiler/skills/ redeploy it with `python3 deploy.py --add <skill>` from compiler/.
5. Promotion: any change to compiler/cli/decompiler.py, cmd_map.py, or human.py, to compiler/skills/decompile/SKILL.md, to compiler/PROMOTION.md, to projects/web.html, or to compiler/deploy.py is copied to its showcase twin — projects/compiler/decompiler.py, cmd_map.py, human.py, SKILL.md, PROMOTION.md, web.html, and projects/deploy/deploy.py. The full run is written in compiler/PROMOTION.md.
6. Run `human sync` exactly once per code change, against the exact last-synced old version (the showcase twin saved before the edit). A second run against the same --old corrupts the spans.
