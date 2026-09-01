# Project rules

1. Never add comments or docstrings to code unless I explicitly tell you to. This includes module docstrings, class docstrings, function/method docstrings, inline `#` comments, field-level comments, and section-divider comments. Write code with no commentary by default.
2. Only report to me in ASD-STE100 Simplified Technical English.
3. If you make any changes under compiler/cli/ update the version in compiler/cli/pyproject.toml so reinstalling works and doesn't cache. Bump only the last number (0.0.X) and never the first two. Reinstall the bumped version with `uv tool install --reinstall .` from compiler/cli.
4. If you make any changes to a skill under compiler/cli/human/skills/ or to the shapes under compiler/cli/human/shapes/ redeploy with `human skills` after the reinstall.
5. If you make any changes under compiler/cli/human/reader/ (web.html, trees.js) redeploy in this repo using `human init` after the reinstall.
6. This repo is its own human project: the maps live in human/ at the root. Run `human sync <file>` exactly once per code change to a mapped file, against the exact last-synced old version (`--old <saved copy>` when it is not git HEAD). A second run against the same --old corrupts the spans.
