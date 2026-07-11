# Self-hosting plan: using the language to build the language

1. **Don't swallow main.py.** It's ~2,400 lines in one unit; a .human edit would make the LLM regenerate the whole file, and one bad regeneration bricks the engine. That's why reading it as one giant traced blob feels hard — it is too big a unit.
2. **Extract one small, pure organ** from main.py into its own file — best first candidate: the heuristic attribution functions (phrase_tokens, stopword filtering, keyword scoring) or parse_split_sections. Pure logic, no FastAPI, no I/O, ~50–100 lines, imported by main.py.
3. **Author its .human + .context and adopt it** — the bootstrap-once move already built. Now that module has real phrase-level provenance at a size where the links are actually readable.
4. **From then on, change that module only through the editor.** Reword the phrase, recompile the unit, run the engine to verify. The engine is now compiling a piece of itself.
5. **Repeat one module at a time**, keeping the rest of main.py as ordinary hand-maintained code. Each extraction shrinks the "assembly-only" core.

One prerequisite worth adding before step 4: a smoke test (compile a toy program end-to-end via the API) so a bad LLM regeneration of an engine module is caught in seconds. The other prerequisites are editable unit code and split-preserving .context saves — self-hosting means constant round-tripping between code edits and context edits.
