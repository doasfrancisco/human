# Human CLI rules

1. If you make any changes to the human CLI update its version so reinstalling works and doesn't cache. Reinstall the bumped version with `uv tool install --reinstall .` from compiler/cli.
2. The human tool carries the dmap package inside its own install. If decompile/cli/decompiler.py or cmd_map.py changes, also reinstall human with `uv tool install --reinstall .` from compiler/cli, or the human tool keeps the old machinery.
3. If you make any changes to compiler/skill/human/SKILL.md redeploy using compiler/deploy.py with `python3 deploy.py --add human`.
4. compiler/projects/web.html and trees.js are copies of the decompile reader. If decompile/projects/web.html or trees.js changes, copy the new version over.
