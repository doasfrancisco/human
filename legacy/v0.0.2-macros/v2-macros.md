# v0.0.2 macros

## What a macro is

A macro takes parameters and expands into fran++ primitives *before* the lexer runs. It is text-level substitution with looping — closer to Lisp than to C templates.

```fpp
macro change(denominations, target)
    variables
        remaining = {target}
        coins_used = 0

    for coin in {denominations}
        action Use{coin}
            when remaining >= {coin}
            set remaining to remaining - {coin}
            set coins_used to coins_used + 1

    constraint
        remaining between 0 and {target}
    goal
        remaining = 0

module CoinChange
    change([1, 5, 10, 25], 67)
```

The `for` loop runs at expansion time. `change([1, 5, 10, 25], 67)` unrolls into four `action Use1`, `action Use5`, `action Use10`, `action Use25` blocks — each a full state transition. The lexer never sees the macro call; it sees the expanded `.fpp`.

## Why macros mattered

Pre-v0.0.2, writing coin-change in TLA+ meant typing out one action per denomination by hand. Adding a coin meant adding an action. A macro says: "one `action` block parameterized by `coin`, then instantiate it per value."

The user writes the **decision** (coin denominations, target) while the macro encodes the **structure** (state variables, guards, updates). The machinery stops leaking into the spec.

This is the same compression move fran++ cares about — separating the idea from the machinery — applied one level up. Instead of "the program is a rule, the compiler emits the machinery," it's "the macro is a rule over programs, expansion emits the program."

## Why macros didn't finish the job

A macro is still a programmer writing a program. Somebody had to sit down and write `change(denominations, target)` with the right `for` loop and the right guards. Adding a new problem class means writing a new macro.

An LLM can write a macro. An LLM can write `change` from a one-line description. So the macro system doesn't answer the real question — it moves it up one level. The question is still: **what does the human write that the LLM can't?**

v0.0.3 takes this up directly by removing the traditional compiler altogether and asking the LLM to act as one.

## Implementation notes

- `macros.py` runs as a pre-pass on the source text.
- Braces (`{coin}`, `{target}`) mark substitution points inside action bodies.
- The `for x in {list}` loop iterates over the list passed into the macro call.
- Expansion is pure text substitution — no type system, no scoping beyond block nesting.
- Use `--expand` to dump the expanded `.fpp` before lexing, which is the main debugging tool.
