# Project rules

1. Never add comments or docstrings to code unless I explicitly tell you to. This includes module docstrings, class docstrings, function/method docstrings, inline `#` comments, field-level comments, and section-divider comments. Write code with no commentary by default.
2. If you make any changes to the CLI update its version so reinstalling works and doesn't cache. Reinstall the bumped version with `uv tool install --reinstall .` Templates ship inside the package, so changing a template counts as a CLI change — bump and reinstall.
