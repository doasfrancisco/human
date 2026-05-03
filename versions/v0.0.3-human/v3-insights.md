# fran++ v0.0.3 insights

## Prior conversation

The ideas in v0.0.3 evolved from an earlier design session: https://claude.ai/share/2f029b87-0a24-462e-93ed-3de49d16fc9a

---

## The .human file never changes

The `.human` file is exactly what the user wrote. Nothing more.

```
sort a list
```

That's the source code. The compiler's questions and the user's answers go in the `.context` file. The source never changes.

Three files, three jobs:

```
sort.human     → what you own (intent)
sort.context   → what the compiler learned (bindings)
sort.py        → what the machine runs (implementation)
```

## The compiler is lazy

It compiles what it can, asks about what it can't, and saves every answer.

```
Compiling: sort a list

→ "sort" — I know how to sort.
→ "a list" — what list?

    What data are you sorting?
    > my tasks

→ Saved to context: "a list" → tasks from Notion
→ But: sort by what?

    What property should I sort by?
    > due date

→ Saved to context: "sort by" → due_date
→ Saved to context: "sort order" → ascending (default, not asked)

Compiled.
```

Second time you write `sort a list` — compiles instantly, no questions. Same context = same Python.

The compiler only asks about **decisions that are silent when wrong.** It never asks "should I use quicksort or mergesort?" — that's machine code. It only asks things where a wrong guess would silently produce wrong results.

## The compiler IS Claude

No separate script. No API wrapper. Claude is the compiler. The conversation is the compilation process. When you write a `.human` file, Claude reads it, identifies missing decisions, asks, saves answers to `.context`, and writes the `.py`.

## Static vs dynamic bindings

Two kinds of context:

```
# Static — fixed forever, lives in .context:
"my WhatsApp" → +51 987 654 321

# Dynamic — changes per run, resolved by block references:
"a list" → whatever was produced by the previous block
```

Block names are dynamic bindings:

```
my-tasks
    source: Notion
    filter: due < 48h

sorted-tasks
    do: sort my-tasks       ← "my-tasks" resolves at runtime
    order: descending
```

The binding resolution order: if a noun matches a block name, it's dynamic. Otherwise, check context. If not in context, ask. Same as variable scoping — local before global.

## Global context emerges, it isn't declared

The global `.context` is the stuff that's true about you regardless of which `.human` file is running. But you don't write it upfront. It emerges when the compiler notices the same noun across multiple programs.

```
project/
    .context         ← "products" = (name, price) — used by multiple files
    btree.human
    btree.context    ← only btree-specific stuff (branching factor)
    sort.human
    sort.context     ← only sort-specific stuff
```

When `btree.human` defines "products" and later `find cheapest product` references "product" — the compiler migrates the binding to global `.context`.

That's type inference, but for meaning, not types. Haskell infers structure. This compiler infers semantics.

## Delegated decisions vs owned decisions

When the user said "pick any you like" for the B+ tree, three decisions were delegated to the compiler. The compiler picked and saved its picks to `.context`. But these are different from user decisions:

```
btree.context:
    # user decisions:
    information → products (name, price)
    sort by → price

    # compiler defaults (edit to tune):
    branching factor → 4
```

Wrong information = user's fault, fix the `.human`. Wrong branching factor = compiler's fault, tune the `.context`.

That boundary between owned decisions and compiler defaults is the fault line. That's where debugging starts.

## The B+ tree example

```
btree.human    →  1 line.    "b+ tree to sort information"
btree.context  →  4 lines.   Products, price, branching factor 4.
btree.py       →  100 lines. B+ tree with insert, split, leaf traversal.
```

1 line of intent. 4 decisions in context. 100 lines of machine code you never read.
