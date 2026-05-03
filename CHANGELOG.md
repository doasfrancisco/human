# Changelog

fran++ is a hypothesis trail, not an incremental release. Each version tests a different answer to the same question: **what's the minimum a human should write, and what should the machine fill in?**

## v0.0.3 — `.human` language (LLM is the compiler)

**Hypothesis:** the compiler is Claude. The human writes 1–2 lines of intent in a `.human` file. The compiler asks about decisions that are *silent when wrong*, saves the answers to `.context`, and generates `.py`.

**What it adds:**
- Three-file split: `.human` (intent, user-owned) + `.context` (learned bindings) + `.py` (generated code).
- Named blocks with semantic key-value pairs instead of formal syntax.
- Global `.context` emerges when the same noun appears across multiple programs.
- Static vs dynamic bindings (`"my WhatsApp"` is static; block names resolve at runtime).

**What it abandons:**
- Traditional lexer/parser/codegen.
- A CLI — the runtime is Claude Code itself.
- State machines as the default abstraction.

## v0.0.2 — macros (code that writes code)

**Hypothesis:** Lisp-style macros can compress specifications without handing logic to an LLM. One line unrolls into a full state machine.

**What it adds:**
- `.fpp` input syntax (English-flavored but still structured).
- Pre-parse macro expansion (`macros.py` runs before the lexer).
- BFS search in generated Python — solves coin change, water jugs.

**What it abandons:**
- Pure TLA+ input.

**What it learned:** a macro is still a programmer writing a program. The LLM can write macros. The unsolved question is what the human does that the LLM can't.

## v0.0.1 — TLA+ → Python

**Hypothesis:** a formal specification language (TLA+) can be compiled directly to executable code. Formal verification and execution from one source.

**What it adds:**
- Lexer, parser, codegen for a TLA+ subset (with `and`/`or` in place of `/\`/`\/`).
- Python output: classes with state, action methods, a `step()` that picks actions via `random.choice`.
- Optional type invariant checks via `assert`.

**What it learned:** state machines are powerful for distributed systems and search problems but wrong for pure expressions and simple transformations. Forcing everything into TLA+ produces unnatural code.
