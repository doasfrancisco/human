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

## 3. A stale repair cuts what the parent never named

`human sync <name> --stale <id>` mends a child entry against the parent entries that changed (`repair_stale` and `STALE_PROMPT` in `compiler/cli/human/decompiler.py`). It reads a thing the parent does not name as a thing that went away. That is right when the code lost a feature, and wrong when the parent never named it.

Example, 2026-09-24. The human file went into the code, and the project telling in `human/project.json` got it. The five file entries it stands on — `cmd_map.py`, `cmd_watch.py`, `cmd_train.py`, `cmd_project.py`, `decompiler.py` — hold the user's own words, written before the feature, and name it nowhere. `human sync project --stale 1` then cut the feature out of the project telling, in seven places:

```
- [cli refuses a circle over the maps](…decompiler.py:e1:check_cycle)
+ [cli refuses a circle](…decompiler.py:e1:check_cycle)

- in every map with no code under it, when one of its abstractions pins the mended one
+ in the project map, when one of its abstractions pins the mended one

- a human file can be the parent of a human file.
+ (cut)
```

Every cut sentence was true of the code. The repair was undone by hand. Two entries disagree until the user names the feature in the parent as well, and until then every `--stale` run tries to cut it out again.

## 4. The tool has no rename, and a path is a key in five places

Nothing in the CLI moves a file. `mv` alone breaks the project, because a path is not only where a file lives:

- it names the map — `human/explanation_<path, with __ for each />.json`;
- it stands inside that map as `code_file`;
- it is the target of every pin that reaches the file from another map — `[w](src/app.py)` and `[w](src/app.py:block)`;
- it is one line of the file list in `human/human.json`;
- it is the photo an open training row keeps, in `file` and in `map` (`cmd_train.py`).

A human file is the same with its bare name: the record `human/human_<name>.json`, and the pins `[w](payments)` and `[w](payments:e1:words)`.

Example, 2026-09-24. The user asked to rename a file, a human file too, from the reader. There is no `human rename`, and the right-click list of the file tree offers only "create file" and "create human". After a rename by hand, `human init` reads the new path as a file with no map, the old map stands under a name no file holds, and every pin into the old path answers nothing.

What the change implies: a rename is the first act that writes many maps at once. It must move the file, move the map, write the new `code_file`, change every pin in every other map, change the file list, and refuse — not half-do — while a training row stands on the file. It is nearer to `undo` than to `map`: one refusal, or one whole move.

## 5. A first telling refuses a pin, when it could check it

`verbatim_record` in `compiler/cli/human/cmd_map.py` stops a `human map --verbatim` that holds one pin: "the user's words go in plain; the pins come after, with human retext". The rule is older than the reader. It came from the run, where the user's abstraction lands before the code exists, so no pin can point anywhere yet.

In the reader the user writes a first telling on a file, on the project, or on a human file, and the things they name are already there. The refusal makes them compile once with no pin, then open the same text again and compile a second time.

The change: drop the refusal, and let the pins of a first telling go through the check every other pin gets — `build_anchors` and `check_cycle` in `compiler/cli/human/decompiler.py`. It is deterministic and makes no claude call: a target that is not a real block, not a file of the project, or not an existing anchor of an existing entry comes back as an error in the same words as a retext gives. The user reads it in the reader and mends the text before it lands.
