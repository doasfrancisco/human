# Project rules

1. Never add comments or docstrings to code unless I explicitly tell you to. This includes module docstrings, class docstrings, function/method docstrings, inline `#` comments, field-level comments, and section-divider comments. Write code with no commentary by default.
2. Only report to me in ASD-STE100 Simplified Technical English.
3. If you make any changes under compiler/cli/ update the version in compiler/cli/pyproject.toml so reinstalling works and doesn't cache. Bump only the last number (0.0.X) and never the first two. Reinstall the bumped version with `uv tool install --reinstall .` from compiler/cli.
4. If you make any changes to a skill under compiler/cli/human/skills/ or to the shapes under compiler/cli/human/shapes/ redeploy with `human skills` after the reinstall.
5. If you make any changes under compiler/cli/human/reader/ (web.html, trees.js, shiki.js) stop the human server and start it again with `human serve` after the reinstall, because the server deploys the reader to ~/.human when it starts.
6. This repo is its own human project: the maps live in human/ at the root. Run `human sync <file>` exactly once per code change to a mapped file, against the exact last-synced old version (`--old <saved copy>` when it is not git HEAD). A second run against the same --old corrupts the spans.
7. Never push a tag unless I ask for a release. $git-push pushes commits only. A release is: bump 0.0.X in pyproject, push, then tag v0.0.X and push the tag. The tag starts .github/workflows/release.yml, which builds human for every platform and puts it in R2 at downloads.doashuman.com. PyPI gets no new release: .github/workflows/publish.yml runs only by hand.
