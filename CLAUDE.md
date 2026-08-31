# Project rules

1. Never add comments or docstrings to code unless I explicitly tell you to. This includes module docstrings, class docstrings, function/method docstrings, inline `#` comments, field-level comments, and section-divider comments. Write code with no commentary by default.
2. projects/compiler mirrors compiler/. Any modification on one side is copied to the other side in the same motion: a change in projects/compiler updates compiler/ exactly.
3. If you make any changes to the CLI (compiler/cli/*) update the version in compiler/cli/pyproject.toml so reinstalling works and doesn't cache. Reinstall the bumped version with `uv tool install --reinstall .` from compiler/cli.
4. If you make any changes to a skill under compiler/skills/ redeploy it with `python3 deploy.py --add <skill>` from compiler/.
5. Only report to me in ASD-STE100 Simplified Technical English.
6. Run `human sync` exactly once per code change, against the exact last-synced old version (the showcase twin saved before the edit). A second run against the same --old corrupts the spans.