# Project rules

1. Never add comments or docstrings to code unless I explicitly tell you to. This includes module docstrings, class docstrings, function/method docstrings, inline `#` comments, field-level comments, and section-divider comments. Write code with no commentary by default.
2. If you make any changes to the CLI update its version so reinstalling works and doesn't cache. Reinstall the bumped version with `uv tool install --reinstall .`
3. If you make any changes to decompile/skill/decompile-claude/SKILL.md redeploy using decompile/deploy.py
4. If you make any changes to the CLI decompiler.py or cmd_map.py files, decompile/skill/decompile-claude/SKILL.md or decompile/projects/web.html. Promote it and copy it to the version found at projects/decompiler/decompiler.py, projects/decompiler/cmd_map.py, projects/decompiler/SKILL.md, projects/decompiler/web.html