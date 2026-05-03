# fran++ insights

Ongoing design notes and realizations.

## LLMs are part of the language

The compiler isn't just a syntax transformer. LLMs play a role:

- User says "fizzbuzz" → LLM knows the algorithm → emits compressed form: `divisors {3: "Fizz", 5: "Buzz"}`
- The compressed form is what fran++ actually compiles to Python
- The pipeline: **English → (LLM) → fran++ → (compiler) → Python**

Without the LLM, fran++ is just another syntax. With it, English becomes the input language.

## Compression = separating the idea from the machinery

FizzBuzz is not an if/elif chain. It's a rule: `{3: "Fizz", 5: "Buzz"}`. The if/elif chain is machinery that implements the rule. fran++ should express rules, not machinery.

Good compression: `divisors {3: "Fizz", 5: "Buzz"}`
Bad compression: same logic with fewer characters

The test: can you look at the fran++ code and immediately see the **decision** without reading the **implementation**?

## State machines aren't always the right abstraction

v0.0.1 forced everything into state machines (TLA+ style). That works for:
- Things that change over time
- Rules about what's allowed/forbidden
- Concurrent processes

It doesn't work for:
- Pure expressions (`1 + 3 + 5`)
- Simple transformations (fizzbuzz)
- Anything where there's no meaningful "state"

fran++ should use the simplest abstraction that fits. Expressions when possible, state machines only when needed.

## Rules and goals, not steps

The most powerful thing TLA+ does is NOT describing an algorithm step by step (that's just Python with different syntax). It's powerful **when it describes rules and goals and lets the machine figure out the steps.**

DieHard example: you don't write "fill big, pour into small, empty small..." — you write "here are the jugs, here are the allowed moves, find me 4 gallons." The model checker explores every possible path and finds the solution.

fran++ should work the same way: you state what's true, what's allowed, and what you want. The machine does the rest.

## What fran++ is NOT

- Not just Python with different syntax (that adds nothing)
- Not a replacement for LLMs (they're a collaborator, not a competitor)
- Not a verification tool only (TLA+ already does that)

## Macros: code that writes code

v2 added Lisp-style macros to fran++. A macro takes parameters and expands into fran++ primitives at compile time — before the lexer runs. Unlike templates (slot-filling), macros can loop, so one line like `change([1, 3, 4], 6)` unrolls into a full state machine with one action per denomination.

This matters because the user writes only the **decision** (which coins, what target) while the macro encodes the **structure** (state variables, guards, updates). The user never touches the machinery.

But macros don't solve the real problem. A macro is still a programmer writing a program. LLMs can write macros. The question is what the human does that the LLM can't.

## Computation is state + rules + goals

A Turing machine is: tape (state) + transition table (rules) + halt condition (goal). fran++'s state machine model already captures this — water jugs, coin change, any search problem.

But workflows are ALSO Turing machines. "Sync Notion tasks, rank by urgency, send to WhatsApp" is: state (`tasks: not loaded`), rules (`can fetch`, `can rank`, `can send`), goal (`tasks sent, ranked`). It's a trivial machine with one path instead of many.

The model is the same. The notation problem is: how do you write both coin change and Notion sync in the same language without the notation becoming either too terse (LLM fills in too much, unverifiable) or too explicit (human writes implementation, just Python with fewer keywords)?

## The design tension

- **Too terse** → LLM decides too much → can't verify correctness (the .human file problem)
- **Too explicit** → human writes machinery → no advantage over Python (the current .fpp problem)
- **Just right** → human expresses the minimum structure that determines correctness, LLM fills in everything else

For coin change, the minimum structure is: denominations, target, "minimize." For Notion sync, it's: source, ranking criterion, destination. For "make failing tests pass," it's... unclear — and that's where the language doesn't exist yet.

The language emerges from finding the **minimum correctness-determining structure** for each class of problem. PG's method: write programs you wish you could write, for real problems, and see where the notation needs more structure and where it can afford less.

## Open questions

- What's the right level of compression? Too compressed = unreadable. Too verbose = just Python.
- How does the LLM know which fran++ constructs to emit? Does fran++ need a standard library of patterns (divisors, accumulators, state machines)?
- Where exactly does verification fit? Is it automatic, optional, or the whole point?
- Can one notation handle both search problems (many paths) and workflows (one path)?
- What's the minimum structure for each problem class that makes LLM output correct by construction?
- Is "state + rules + goals" the right primitive set, or is something missing?
