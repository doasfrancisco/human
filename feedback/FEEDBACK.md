# Feedback

## 1. The doubled-line check compares words, not meaning

`human show .` warns when one line of thirty letters or more stands in the maps of two files (`dup_warnings` and `norm_dup` in `compiler/cli/human/decompiler.py`). It compares the words only. A better check must find when the same meaning is told twice across files, and stay quiet when only the words match.

Example, 2026-09-07. Both `compiler/cli/human/decompiler.py` and `compiler/cli/human/cmd_project.py` have a function `repair_stale`. The two maps (`human/explanation_compiler__cli__human__decompiler.py.json`, `human/explanation_compiler__cli__human__cmd_project.py.json`) tell it as a rail, and two stage heads got the same words:

```
●  the tool writes the second letter
●  claude answers, the tool checks
```

The sentences under the heads differ — one tells the file repair, the other the project repair. The check warned twice. False alarm: same words, different meaning.



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



## 5. Nothing says the running server is older than the page

`human init` writes the reader page out of the installed tool at every run (`cmd_init` in `compiler/cli/human/__init__.py`), but a `human serve` that already runs keeps the old code in memory. An upgrade and an init give the browser a new page while the door behind it stays old, and nothing on either side says so.

Example, 2026-09-25. The user made two human files from a folder in the tree. The new page sent the folder with the name; the server, started before the upgrade, ran the old `new_human`, which takes a name alone. Both records landed with no place and the two maps showed at the root. The refusal never came, because the old door does not know the word.

The change: give the tool one hand that reads its own version, write that version into `human/human.json` at init, put the running version in the answer of `fresh_map`, and let the reader compare the two on the refresh it already runs every five seconds. A difference shows one line: the server runs 0.0.34, the page is 0.0.43, stop it and serve again. It only makes the tool tell you when the server is behind the page, instead of you finding it by a lost folder.



## 6. The reader asks for the map of every file before it draws anything

At the start the page reads `human.json` and then runs `Promise.all(names.map(loadFile))` (`compiler/cli/human/reader/web.html`): `loadFile` asks for `explanation_<path>.json` of **every** file in the list, not only the files that have a map. `buildTree` and `open` stand after that `Promise.all`, so the frame stays empty until the last ask lands.

Example, 2026-09-25, the project `mina`:

| Thing | Value |
|---|---|
| Files in `human/human.json` | 628 |
| Maps that exist in `human/` | 127 |
| Asks the page makes at start | 628 |
| Asks that answer "not found" | ~524 |
| Round trip over the tailnet | 264 ms |
| The same 628 asks on the server machine | 0.39 s |

A browser holds six connections to one host, so 628 asks become about 105 rounds: 25 to 30 seconds of blank page. On localhost the same asks cost 0.39 s, which is why a small project on one machine feels instant. Two things make it worse: each ask carries `cache: "no-store"` and each answer `Cache-Control: no-cache`, so a reload pays it again; and 524 of the asks cost a full round trip to learn that no map exists.

The server is not the cause: `fresh_map` walks the project in 0.05 s, the tree draws 628 rows fast, and the code of a file is fetched only when it opens.

Roads, from the smallest:

- **Name the mapped files in `human/human.json`.** `write_files` already lists the files; it can mark which of them have a map. The page then asks only for the 127 that exist — 105 rounds become 21.
- **Draw the tree first.** `buildTree` needs the names alone, not the maps. Draw it, open the first file, and let the other maps land after, so nothing waits on a full set.
- **One answer for all the maps.** A road like `/human/maps` that hands out every map in one block: one round trip instead of 127, at the price of a bigger answer.



## 7. An expansion stands below its target until claude finishes

A written expansion is mapped at once — `human map <name> --verbatim` in the `expand` road of `cmd_watch.py` — but nothing ties it to the entry it expands. The reader places an entry above another only by the pins between them: `sorted` in `compiler/cli/human/reader/web.html` gives an entry a higher layer when a pin of the target points into it. That pin — `[the words](e<entry>:anchor words)` in the target — is the last step of the `expand` event, written by claude. Until that step lands, the new entry is a plain entry, drawn after the target, as if it were a second telling of the same thing.

Example, 2026-09-29, the project `mina`. The user highlighted the "NEW QUOTE REQUEST ON PLATFORM" section of entry 1, wrote an expansion and pressed compile. The server mapped entry 2 and queued event 22. The reader showed entry 2 under entry 1, not above it, and the user asked why the lower layer showed down. The event then stopped half done, so entry 2 stayed below for as long as the event stayed open. The last step had a problem of its own: the highlighted section already holds pins, and a pin cannot hold pins, so the full section can never be the pinned words — only one plain line of it.

What the change implies: the place of an expansion is known at the click — the event carries `entry`, `target` and `words` — so the reader need not wait for the pin.

- **Read the open events.** The reader already knows the queued events for the compiling mark (`queuedMark`). For an open `expand` event with an `entry`, `sorted` can count one edge from `target` into `entry`, so the expansion stands above its target from the first draw. The pin, when it lands, gives the same order, and the open edge goes away with the ack.
- **Mark the highlighted words.** Until the pin exists, the reader can underline the highlighted words in the target, faint, so the user sees what the expansion stands on.
- **Say it in the compiling line.** "entry 2 expands entry 1 and waits for claude" tells the user the order is not final yet.

A highlight that holds pins cannot be pinned whole; the reader could refuse such a highlight at the click, or the event could name the one plain line claude will pin, so the user is not surprised at the end.



## 8. The answer of a compile lists every file with no telling

A map with no code under it answers every write with its coverage: `covered: 12 of 400 files`, then `not covered:` and the name of each file no pin reaches (`print_coverage` in `compiler/cli/human/cmd_project.py`, line `print("not covered: " + ...)`). The server hands that answer to the reader whole, and the reader shows it on top of the file.

Example, 2026-09-29, the project `mina`. A compile on `mina.human` answered with three lines: the entry, `covered: 12 of 400 files`, and a `not covered:` line of 388 paths. On a wide screen it filled the whole reader, from the head bar to the bottom edge, and the words the user wrote could not be seen.

What the change implies: the answer should be as short as `covered: 12 of 400 files`. The list of files belongs to `human show`, where a person asks for it.

- **Count, not name.** `not covered: 388 files` — or drop the line, since `covered: 12 of 400` already says it.
- **Name only a few.** When the list is short, five files or fewer, name them; past that, give the count and point to `human show <name>`.
- **Cut in the reader.** The reader could show the first line of the answer and fold the rest behind a click, so a long answer never covers the words.



## 9. The server walks the whole project to answer "did a file change?"

The reader asks for `human/human.json` every 5 seconds (`refreshFiles` in `compiler/cli/human/reader/web.html`), and the server answers with a full `os.walk` of the project each time (`fresh_map` and `scan_files` in `compiler/cli/human/__init__.py`). On `mina`, 402 files, the walk runs twelve times a minute, almost always to find that nothing changed. The planned version code (a hash of the list, sent back as "no change") saves the answer, but not the walk; the folder time stamps save most of the walk, but still look at every folder.

What the change implies: the file list could cost nothing between changes.

- **A signal from the system.** The server asks the system to tell it when a file is made, removed or renamed — inotify on Linux, FSEvents on macOS, ReadDirectoryChangesW on Windows, or the `watchdog` library over all three — and changes the list and its version code only then. The cost is one more library and a different behaviour on each system, so it waits until the time stamps are not enough.



## 10. A pin could point at a collection of pins

A pin points at one place: a file, a block, or an anchor. The logic of one thought of the abstraction can be in many files. Maybe a pin could point at a collection of pins, one for each place, so the words stay whole and still reach all of them.



## 11. A refusal for a kept anchor does not say who points at it

When a new text drops an anchor that another entry pins, the compile is refused, but the refusal names only the anchor, not the entry that points at it. The user must then find that pin and fix it by hand before the words can go in.

Example, 2026-10-01. A compile on `compiler/cli/human/__init__.py` answered `entry 1: [RETEXT-ANCHORS] other entries point at the anchors ['the body']; the new text must keep them`. The new words had `[as JSON](read_body)` in place of `[the body](read_body)`. The pin was in entry 1 of `human/project.json`: `[its body read as JSON](compiler/cli/human/__init__.py:e1:the body)`.

What the change implies:

- **Name the pointers.** The refusal names each map and entry that points at the anchor, with the pin line: `project e1: [its body read as JSON](…:e1:the body)`.
- **Fix the pin in one step.** The reader offers to move that pin to an anchor of the new text, or to the block, and then compiles the words.



## 12. A sync rewords a top abstraction that is still true

When a lower abstraction changes, the sync or the stale repair of the top abstraction rewords it to agree with the new details. The top abstraction should change only when the lower change makes it untrue, so that it must add or remove a fact. When the top abstraction still tells the lower one correctly, it keeps its words.

Example, 2026-10-01. A change in the design of the reader came in through the words of `web.html`. The project sync changed three lines of the user's words in project entry 1, to agree with the new design:

- "the project name sits above in capitals with no card, the files sit in a card…"
- "a play triangle for compile" in place of "a spark for compile"
- a new line: "the caret is yellow, the colour of the dot in the tree."



## 13. A pin could point at an action

A pin points at a thing: a file, a block, or an anchor. Some words tell an action, not a thing. For example, a line of code that the compiler wrote is an action of the compiler. Maybe a pin could point at that action, so the words reach what was done and not only where it is.



## 14. The install design is simpler for vibecoders

One `curl` line installs human and its skills, with no uv, no Python and no `human skills`. Updates come by themselves, like Claude Code. A vibecoder never sees a version, a package tool or a skill folder.



## 15. Anchor words must be unique in one text

A compile is refused when two pins in one text have the same words. Words can repeat in a human text. The same name, a path or a command, often comes back in a second place.

Example, 2026-10-02. A compile on `install.human` answered `entry 1: [ANCHOR-WORDS] the anchor 'install.sh' appears twice; anchor words are unique in one text`. The text held `[install.sh](.install/install.sh)` two times.

The words are the key today: a pin from another entry reaches an anchor by its words, `[w](e1:install.sh)`. Two anchors with the same words make that key point at two places.

What the change implies: each anchor gets an id that the words do not carry.

- **An id per anchor.** The map keeps each anchor with a short id, `a1`, `a2`, given in order when the text goes in. A pin from another entry can name it: `[w](e1#a3)`.
- **The words stay the easy road.** `[w](e1:install.sh)` still works when the words are unique. When they repeat, the tool refuses only that pin, and names the ids to choose from: `install.sh is a2 and a7`.
- **An id stays with its anchor.** On a retext or a sync, an anchor keeps its id when its words and its target stay the same, so a pin from another entry does not break when the text moves around it.



## 16. Maybe build a Bun for Python

Claude Code is one file made by Bun `--compile`. The program is inside the `.exe`, and the `.exe` reads it from itself when it runs, so nothing is unpacked to a temporary folder. PyInstaller `--onefile` must unpack Python to `%TEMP%\_MEI...` on each start. On Windows, a second human that the first one started used that folder, and the folder was deleted under it (2026-10-05). The fix today is a folder build in `~/.human/current`.

The idea: a small Python runner that does what Bun does.

- **One static program.** Python and its standard library are linked into one `.exe`, with no `python312.dll` beside it.
- **The code goes inside.** The human code is added to the end of the `.exe` as a zip, and Python imports it from there in memory (`zipimport` can already do this for plain Python).
- **The hard part is native modules.** Windows loads a `.pyd` or a `.dll` only from a file on disk. Each native module must be linked in, or loaded from memory. PyOxidizer tried this (`oxidized_importer`), but it is not kept up to date now.

What this gives: one file to download, one fixed path, no temporary folder, and a fast start.



## 17. A Windows install fails while human runs

On Windows, human lives in one folder, `~\.human\current`, and the PATH points at it. An install or an update moves each old file out of that folder, then copies the new files in. Windows does not let a program move a file that a running process holds open.

Example, 2026-10-07. `irm https://doashuman.com/install.ps1 | iex` of 0.0.132 stopped with `Move-Item: The process cannot access the file because it is being used by another process.` A `human serve` and a `human watch` of 0.0.121 ran from `current` and held `_internal\base_library.zip`. The script had already moved `human.exe` and some DLLs to `~\.human\old\`, so `human` did not start from a new terminal until the processes stopped and the install ran again.

The update from the reader has the same problem: the server that moves the files is one of the processes that hold them.

On Linux this does not happen: each version has its own folder, `~/.human/versions/0.0.X`, and the `human` command is a link that the update points at the new folder. No file in use moves.

Possible solutions:

**Stop, then replace.** Keep `current`. The install stops each `human.exe` that runs from `current`, or a new `human stop` does it. Then it replaces the files. It is simple, but it stops your servers and watches, and the update from the reader still needs a separate process to do the move.

**Version folders and a `human.cmd` file.** This is the option I explained before. The one disadvantage is the "Terminate batch job (Y/N)?" question after Ctrl+C.

**Version folders and a small launcher program.** In place of the `.cmd` file, put a very small `human.exe` in `~\.human\bin`. It reads a file such as `~\.human\version` with "0.0.132" in it, and starts that version. It sends Ctrl+C and the exit code through, so there is no extra question. It changes almost never, and Windows lets you rename a running `.exe`, so the launcher itself is easy to replace. The disadvantage: it is one more program to build, in C, Go or Rust, and to sign.

**Version folders, with the PATH pointing straight at the newest one.** Each update changes the user PATH to `~\.human\versions\0.0.X\human`. There is no file and no question after Ctrl+C. The disadvantage: a terminal that is already open keeps the old PATH. An AI harness that runs for a long time also keeps using the old version until it starts again.

**Do not touch files in use, and tell the user.** The install finds the files that are in use, moves nothing, and prints "stop these human processes, then run the install again", with their process ids. There are no new parts. The disadvantage: the update from the reader cannot work this way on Windows, and you must do a manual step each time.

The `human.cmd` option: each version goes into `~\.human\versions\0.0.X`, and a folder like `~\.human\bin` in the PATH holds one file, `human.cmd`, with one line such as `@"C:\Users\<you>\.human\versions\0.0.132\human\human.exe" %*`. An update installs the new version into a new folder and changes only that line, so old servers keep running on their folder and new commands start the new version.
