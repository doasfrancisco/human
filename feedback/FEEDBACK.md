# Feedback

## 1. The doubled-line check compares words, not meaning

`human show .` warns when one line of thirty letters or more stands in the maps of two files (`dup_warnings` and `norm_dup` in `compiler/cli/human/decompiler.py`). It compares the words only. A better check must find when the same meaning is told twice across files, and stay quiet when only the words match.

Example, 2026-09-07. Both `compiler/cli/human/decompiler.py` and `compiler/cli/human/cmd_project.py` have a function `repair_stale`. The two maps (`human/explanation_compiler__cli__human__decompiler.py.json`, `human/explanation_compiler__cli__human__cmd_project.py.json`) tell it as a rail, and two stage heads got the same words:

```
●  the tool writes the second letter
●  claude answers, the tool checks
```

The sentences under the heads differ — one tells the file repair, the other the project repair. The check warned twice. False alarm: same words, different meaning.

## 2. Ctrl+S could save into the map, not only into the browser

Today the reader keeps a written text in the browser until the user presses compile, and the compile is what writes to disk. The other road, not built:

Saved in the map. Ctrl+S writes the words into the map on disk, as a retext, with no claude call. The compile then only sends the code road. This needs one new call in the server, and a Ctrl+S with a pin that fails would be refused on the spot.

Decided 2026-09-08: the browser save. The map changes only on compile.
