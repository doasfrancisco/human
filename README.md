# fran++ v0.0.5 — explained free-text context

## One-line summary

v0.0.5 is a way to code from human language where both the source and the intermediate context are free text, and every generated line of code can be explained by tracing it back through that context to the original human intent.

```text
.human  →  .context  →  .py
intent     expanded     generated
text       text         code
```

The important change from v0.0.4 is this:

```text
v0.0.4: .context is JSON IR
v0.0.5: .context is free text
```

But the free text is not vague chat. It is structured by explanation and provenance.

---

## The core idea

The user writes a small human phrase:

```text
insertion sort
```

The compiler expands that into a more explicit `.context` file:

```text
This program implements insertion sort.
It accepts a list of comparable items.
It returns a new list sorted in ascending order.
It is stable: equal items keep their relative order.
The algorithm scans from left to right, treating the left side as sorted.
For each item, save it as the key.
Shift earlier items right while they are greater than the key.
Insert the key into the gap.
```

Then the compiler generates Python from that `.context`.

The key requirement is that the generated Python must map back to the `.context` lines, and the `.context` lines must map back to the `.human` text.

So even though `.context` is free text, it is still a debuggable intermediate representation.

---

## Incremental language logic

A `.human` compile should not always be treated as a brand new request from scratch.

A later `.human` snapshot may be a refinement of an earlier snapshot:

```text
H1: insertion sort
H2: insertion sort of 1 5 4
```

In that case, the compiler should understand H2 as:

```text
base intent: insertion sort
new detail: use/example input 1 5 4
```

The new context should inherit the existing meaning of `insertion sort` and then apply the new detail. It should not replace the whole implementation with a different program unless the new human text explicitly asks for a different program.

For this example, the expected evolution is closer to:

```text
The program implements insertion sort.
The function is named insertion_sort.
The function accepts a list of comparable elements.
The demo/input list is [1, 5, 4].
The demo calls insertion_sort([1, 5, 4]).
```

not:

```text
Rewrite the program as a full step-by-step trace of sorting [1, 5, 4].
```

unless the user asked for tracing.

This means `.human → .context` should eventually be an update operation:

```text
previous .human + previous .context + new .human
    ↓
updated .context
```

not only:

```text
new .human
    ↓
new .context from scratch
```

The same rule applies at the code stage. If `.context` adds an example input, `.py` should preserve the existing function and add or update the demo call. It should not change the function contract unless the context says to.

### Context inheritance

A `.context` line can have different kinds of origin:

```text
inherited   copied forward from an earlier context
updated     inherited but modified by a newer human detail
added       introduced by a newer human detail
default     supplied by compiler convention
manual      edited directly by the user
```

For example:

```text
H1 span "insertion sort" → C1-C18 algorithm/function contract
H2 span "1 5 4"         → C19 demo input list [1, 5, 4]
```

The compiler should preserve this origin information so the UI can answer questions like:

```text
What context came from "insertion sort"?
What context came from "1 5 4"?
What code came from the inherited base?
What code came from the new refinement?
```

### Refinement rule

When human text adds detail to an existing intent, the compiler should prefer the smallest compatible change.

```text
"insertion sort" → build the insertion_sort function
"insertion sort of 1 5 4" → keep the insertion_sort function, add/use [1, 5, 4]
```

A new human snapshot may still intentionally change the program. But that change should be explicit, and the provenance map should show which earlier context/code lines became stale or were replaced.

---

## Files

A v0.0.5 program has these files:

```text
sort.human      user-owned source intent
sort.context    generated/expanded free-text context
sort.py         generated runnable Python
sort.explain    generated explanation/provenance map
```

Only `.human` is definitely user-owned.

`.context` is generated, but it should be readable and editable.

`.py` is generated and disposable.

`.explain` is generated and disposable.

---

## `.human`

`.human` is the compact thing the user writes.

It can be tiny:

```text
insertion sort
```

It can include more detail:

```text
insertion sort descending
```

It can eventually be multiple lines:

```text
read the numbers
sort them with insertion sort
print the result
```

The `.human` file does not need formal syntax. It is ordinary human language.

The compiler's job is to understand it, expand it, and preserve a trace from the expansion back to the original words.

---

## `.context`

`.context` is the expanded understanding of `.human`.

It is free text, not JSON.

However, it should be written in a disciplined way: one meaningful decision per line.

Good `.context`:

```text
This program implements insertion sort.
It accepts a list of comparable items.
It returns a new list sorted in ascending order.
It is stable: equal items keep their relative order.
The algorithm scans from left to right, treating the left side as sorted.
For each item, save it as the key.
Shift earlier items right while they are greater than the key.
Insert the key into the gap.
```

Bad `.context`:

```text
Do insertion sort in the usual way and make it work.
```

The bad version is too compressed. It cannot explain code line by line.

`.context` should contain the information needed to generate code. It should expose defaults instead of hiding them.

For example, if the user writes:

```text
insertion sort
```

then the context may add:

```text
It returns a new list sorted in ascending order.
It is stable: equal items keep their relative order.
```

Those lines are compiler-supplied defaults, but they are still anchored to the original phrase `insertion sort`.

---

## `.py`

`.py` is generated from `.context`.

The generated code should not secretly depend on `.human` directly. The path is:

```text
.human → .context → .py
```

not:

```text
.human ─────────→ .py
```

Every meaningful generated code line should have a reason in `.context`.

Example generated code:

```python
"""Compiled from .human via .context — DO NOT EDIT."""

def insertion_sort(items):
    result = list(items)
    for i in range(1, len(result)):
        key = result[i]
        j = i - 1
        while j >= 0 and result[j] > key:
            result[j + 1] = result[j]
            j -= 1
        result[j + 1] = key
    return result
```

Possible line mapping:

```text
P3  def insertion_sort(items):
    ← C1: This program implements insertion sort.
    ← C2: It accepts a list of comparable items.

P4  result = list(items)
    ← C2: It accepts a list of comparable items.
    ← C3: It returns a new list sorted in ascending order.

P5  for i in range(1, len(result)):
    ← C5: The algorithm scans from left to right, treating the left side as sorted.

P6  key = result[i]
    ← C6: For each item, save it as the key.

P8  while j >= 0 and result[j] > key:
    ← C3: It returns a new list sorted in ascending order.
    ← C7: Shift earlier items right while they are greater than the key.

P11 result[j + 1] = key
    ← C8: Insert the key into the gap.

P12 return result
    ← C3: It returns a new list sorted in ascending order.
```

---

## `.explain`

`.explain` is the provenance file.

It explains how text became context and how context became code.

For now, it can be simple and line-based.

Example:

```text
# sort.explain

Human lines:
H1: insertion sort

Context lines:
C1: This program implements insertion sort.
    derives from H1 phrase "insertion sort".

C2: It accepts a list of comparable items.
    derives from H1 phrase "insertion sort" as the standard input shape for this generated routine.

C3: It returns a new list sorted in ascending order.
    derives from H1 phrase "insertion sort".
    default: ascending, because no descending order was requested.

C4: It is stable: equal items keep their relative order.
    derives from H1 phrase "insertion sort".
    default: stability, because insertion sort is stable by standard definition.

C5: The algorithm scans from left to right, treating the left side as sorted.
    derives from H1 phrase "insertion sort".

C6: For each item, save it as the key.
    derives from H1 phrase "insertion sort".

C7: Shift earlier items right while they are greater than the key.
    derives from C3 and H1.

C8: Insert the key into the gap.
    derives from H1 phrase "insertion sort".

Python lines:
P3: def insertion_sort(items):
    derives from C1, C2.

P4: result = list(items)
    derives from C2, C3.

P5: for i in range(1, len(result)):
    derives from C5.

P6: key = result[i]
    derives from C6.

P7: j = i - 1
    derives from C5, C7.

P8: while j >= 0 and result[j] > key:
    derives from C3, C7.

P9: result[j + 1] = result[j]
    derives from C7.

P10: j -= 1
    derives from C7.

P11: result[j + 1] = key
    derives from C8.

P12: return result
    derives from C3.
```

The exact format is not finalized. The important thing is the trace.

---

## What “maps to insertion sort itself” means

If `.human` contains only:

```text
insertion sort
```

then every generated `.context` line is ultimately anchored to that phrase.

That means the compiler should be able to say:

```text
H1 phrase "insertion sort" caused C1-C8.
C1-C8 caused P3-P12.
Therefore P3-P12 are ultimately explained by H1 phrase "insertion sort".
```

This is the first version of semantic mapping.

At the beginning, this can be line-based:

```text
H1 → C1-C8 → P3-P12
```

Later it should become character/span-based:

```text
H1 chars 1-14, "insertion sort" → C1-C8
```

Later still, it can become semantic:

```text
concept:insertion_sort_algorithm → C1-C8 → P3-P12
concept:ascending_order_default → C3, C7, P8
concept:stable_sort_default → C4
```

---

## Kinds of mappings

v0.0.5 starts simple but should leave room for richer mappings.

### 1. Line mapping

The first implementation can map whole lines:

```text
H1 → C1
C1 → P3
```

This is easiest to build and inspect.

### 2. Character-span mapping

Later, mappings can point to exact character ranges:

```text
H1:1-14 → C1-C8
```

Where `H1:1-14` is the phrase `insertion sort`.

### 3. Semantic mapping

Later, mappings can point to concepts:

```text
"insertion sort" → concept:insertion_sort
concept:insertion_sort → C1, C5, C6, C7, C8
concept:ascending_default → C3, P8
```

This matters because one human phrase can imply many implementation decisions.

### 4. Code-region mapping

Generated code can also be mapped as ranges:

```text
P5-P11 implements C5-C8.
```

This is useful when a whole loop implements a whole algorithmic step.

---

## Defaults

A `.context` line may include information not literally written in `.human`.

Example:

```text
.human: insertion sort
.context: It returns a new list sorted in ascending order.
```

The word `ascending` was not written by the user. It is a compiler default.

Defaults are allowed, but they must be explained.

The `.explain` file should mark them:

```text
C3 defaults to ascending because H1 says "insertion sort" and does not specify descending.
```

A default is not ungrounded. It is anchored to a human phrase plus a compiler convention.

---

## Debugging model

v0.0.5 has three possible fault lines.

### 1. `.context` is wrong

Example:

```text
.human: insertion sort descending
.context: It returns a new list sorted in ascending order.
```

Then the bug is in the human-to-context stage.

### 2. `.context` is right but `.py` is wrong

Example:

```text
.context: It returns a new list sorted in descending order.
.py: while result[j] > key
```

The context says descending, but the code uses the ascending comparison.

Then the bug is in the context-to-code stage.

### 3. `.py` is right but `.explain` is wrong

Example:

```text
.py line maps to the wrong context line.
```

Then the bug is in provenance generation.

This is why `.explain` is its own artifact. Explanation is part of the language, not a side note.

---

## Human editing model

The user may edit `.human` and regenerate everything.

The user may also edit `.context` to steer code generation more precisely.

Example:

```text
It sorts the list in place instead of returning a copy.
```

If `.context` is edited manually, the compiler should eventually preserve or update provenance:

```text
C3 was manually edited by user.
P4 and P12 derive from edited C3.
```

This is not implemented yet, but it is part of the design direction.

---

## Why free-text `.context` instead of JSON

JSON is precise, but it can become too artificial.

Free-text `.context` has different advantages:

- it is easier for humans to read,
- it is easier for humans to edit,
- it can contain explanations and rationale,
- it can preserve ambiguity when needed,
- it is closer to how the user thinks.

The risk is that free text can become vague.

v0.0.5 solves that with explanation mapping: prose is allowed, but it must still account for generated code.

---

## Rule of v0.0.5

The rule is not “generate code from human language.”

The rule is:

```text
Generate code from expanded human context, and preserve the explanation chain.
```

The explanation chain is:

```text
.py line
  ← .context line(s)
    ← .human line/span/phrase
```

If that chain breaks, the compiler has failed, even if the code runs.

---

## Minimal v0.0.5 target

The first working version only needs to support one example:

```text
insertion sort
```

It should produce:

```text
sort.human
sort.context
sort.py
sort.explain
```

The first version can use line-level mapping only.

It does not need character spans yet.

It does not need semantic concept IDs yet.

It does not need bidirectional editing yet.

But it should be designed so those can be added later.

---

## Non-goals for the first version

Do not build a full programming language yet.

Do not build a general parser yet.

Do not require `.context` to have JSON, YAML, TOML, XML, or any other formal structure.

Do not hide defaults.

Do not generate code without an explanation chain.

Do not treat `.explain` as optional.

---

## Final shape

v0.0.5 is about making generated code accountable to human language.

```text
small human intent
    ↓
expanded human-readable context
    ↓
runnable code
    ↓
line-by-line explanation back to the original intent
```

The `.context` file is no longer a machine-looking IR.

It is a human-readable explanation that still behaves like an IR because every generated code line must trace back to it.

---

## Paul Graham, The Hundred-Year Language

"I think the fundamental operators are the most important factor in a language's long term survival. The rest you can change. It's like the rule that in buying a house you should consider location first of all. Everything else you can fix later, but you can't fix the location.

I think it's important not just that the axioms be well chosen, but that there be few of them. Mathematicians have always felt this way about axioms-- the fewer, the better-- and I think they're onto something.

At the very least, it has to be a useful exercise to look closely at the core of a language to see if there are any axioms that could be weeded out. I've found in my long career as a slob that cruft breeds cruft, and I've seen this happen in software as well as under beds and in the corners of rooms.

I have a hunch that the main branches of the evolutionary tree pass through the languages that have the smallest, cleanest cores. The more of a language you can write in itself, the better."

"Languages evolve slowly because they're not really technologies. Languages are notation. A program is a formal description of the problem you want a computer to solve for you. So the rate of evolution in programming languages is more like the rate of evolution in mathematical notation than, say, transportation or communications. Mathematical notation does evolve, but not with the giant leaps you see in technology."

"There's good waste, and bad waste. I'm interested in good waste-- the kind where, by spending more, we can get simpler designs. How will we take advantage of the opportunities to waste cycles that we'll get from new, faster hardware?

The desire for speed is so deeply engrained in us, with our puny computers, that it will take a conscious effort to overcome it. In language design, we should be consciously seeking out situations where we can trade efficiency for even the smallest increase in convenience."

"If we think of the core of a language as a set of axioms, surely it's gross to have additional axioms that add no expressive power, simply for the sake of efficiency. Efficiency is important, but I don't think that's the right way to get it."

"The right way to solve that problem, I think, is to separate the meaning of a program from the implementation details. Instead of having both lists and strings, have just lists, with some way to give the compiler optimization advice that will allow it to lay out strings as contiguous bytes if necessary. Since speed doesn't matter in most of a program, you won't ordinarily need to bother with this sort of micromanagement. This will be more and more true as computers get faster."

"Saying less about implementation should also make programs more flexible. Specifications change while a program is being written, and this is not only inevitable, but desirable.
"

"What programmers in a hundred years will be looking for, most of all, is a language where you can throw together an unbelievably inefficient version 1 of a program with the least possible effort. At least, that's how we'd describe it in present-day terms. What they'll say is that they want a language that's easy to program in."

"
Inefficient software isn't gross. What's gross is a language that makes programmers do needless work. Wasting programmer time is the true inefficiency, not wasting machine time. This will become ever more clear as computers get faster."

"There are more shocking prospects even than that. The Lisp that McCarthy described in 1960, for example, didn't have numbers. Logically, you don't need to have a separate notion of numbers, because you can represent them as lists: the integer n could be represented as a list of n elements. You can do math this way. It's just unbearably inefficient."

"Could a programming language go so far as to get rid of numbers as a fundamental data type? I ask this not so much as a serious question as as a way to play chicken with the future. It's like the hypothetical case of an irresistible force meeting an immovable object-- here, an unimaginably inefficient implementation meeting unimaginably great resources. I don't see why not. The future is pretty long. If there's something we can do to decrease the number of axioms in the core language, that would seem to be the side to bet on as t approaches infinity. If the idea still seems unbearable in a hundred years, maybe it won't in a thousand."

"Just to be clear about this, I'm not proposing that all numerical calculations would actually be carried out using lists. I'm proposing that the core language, prior to any additional notations about implementation, be defined this way. In practice any program that wanted to do any amount of math would probably represent numbers in binary, but this would be an optimization, not part of the core language semantics."

"Another way to burn up cycles is to have many layers of software between the application and the hardware. This too is a trend we see happening already: many recent languages are compiled into byte code. Bill Woods once told me that, as a rule of thumb, each layer of interpretation costs a factor of 10 in speed. This extra cost buys you flexibility."

"Writing software as multiple layers is a powerful technique even within applications. Bottom-up programming means writing a program as a series of layers, each of which serves as a language for the one above. This approach tends to yield smaller, more flexible programs. It's also the best route to that holy grail, reusability. A language is by definition reusable. The more of your application you can push down into a language for writing that type of application, the more of your software will be reusable."

"One way to design a language is to just write down the program you'd like to be able to write, regardless of whether there is a compiler that can translate it or hardware that can run it. When you do this you can assume unlimited resources. It seems like we ought to be able to imagine unlimited resources as well today as in a hundred years.

"What program would one like to write? Whatever is least work. Except not quite: whatever would be least work if your ideas about programming weren't already influenced by the languages you're currently used to. Such influence can be so pervasive that it takes a great effort to overcome it. You'd think it would be obvious to creatures as lazy as us how to express a program with the least effort. In fact, our ideas about what's possible tend to be so limited by whatever language we think in that easier formulations of programs seem very surprising. They're something you have to discover, not something you naturally sink into."

"One helpful trick here is to use the length of the program as an approximation for how much work it is to write. Not the length in characters, of course, but the length in distinct syntactic elements-- basically, the size of the parse tree. It may not be quite true that the shortest program is the least work to write, but it's close enough that you're better off aiming for the solid target of brevity than the fuzzy, nearby one of least work. Then the algorithm for language design becomes: look at a program and ask, is there any way to write this that's shorter?"

"
Now we have two ideas that, if you combine them, suggest interesting possibilities: (1) the hundred-year language could, in principle, be designed today, and (2) such a language, if it existed, might be good to program in today. When you see these ideas laid out like that, it's hard not to think, why not try writing the hundred-year language now?"

"When you're working on language design, I think it is good to have such a target and to keep it consciously in mind. When you learn to drive, one of the principles they teach you is to align the car not by lining up the hood with the stripes painted on the road, but by aiming at some point in the distance. Even if all you care about is what happens in the next ten feet, this is the right answer. I think we can and should do the same thing with programming languages."
