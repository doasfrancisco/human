# IDEAS

## Context provenance across refinements

Problem/question:

> but my worry is on .context how do i know what comes from "insertion sort" and what comes from "1 5 4". it's easy to pass the context from "insertion sort" and update it with "1 5 4" but i want to know which sections come from both. maybe pressing ctrl + click on "insertion sort" moves me to context and that section highlighted? same for "1 5 4"?
>
> but what happens if i change context itself?
>
> also, ideallly the "context" intermediate and .human (start file) aren't actually two. but rather i can infinitely go one level of abstraction deeper (until i reach code) keeping track of the tree.
>
> but i'm not sure of this.

## Design direction

Treat every compile as a provenance-preserving refinement, not just a fresh prompt.

Example:

```text
H1: insertion sort
H2: insertion sort of 1 5 4
```

The second snapshot should be interpreted as:

```text
base concept: insertion sort
new refinement: example/input list [1, 5, 4]
```

So the context should preserve the inherited insertion-sort function contract and add the new input/demo detail, instead of rewriting the entire program around tracing one list.

## UI idea

Ctrl/Cmd-click a human span:

```text
insertion sort
```

Then highlight all derived context lines and code lines.

Ctrl/Cmd-click another span:

```text
1 5 4
```

Then highlight only the context/code introduced by that refinement.

This requires span-level or concept-level provenance, not just line-level provenance.

## Editing context directly

If the user edits `.context`, those lines should become user-authored context nodes.

Possible statuses:

```text
inherited   copied from an earlier context
added       created by a newer human refinement
updated     changed from an inherited context line
default     compiler-supplied assumption
manual      directly edited by the user
stale       derived from an older source that changed
conflict    human/context/code disagree
```

Manual context edits should not erase provenance. They should fork or patch the provenance graph:

```text
H span → old C line → P lines
             ↓ edited by user
          new C line → regenerated P lines
```

## Infinite abstraction levels

Maybe `.human` and `.context` are not fundamentally different file types.

Maybe they are levels in a refinement stack:

```text
level 0: compact human intent
level 1: expanded intent
level 2: implementation decisions
level 3: language-specific design
level 4: code
```

Each level lowers the program one step closer to executable code while preserving links back upward.

In that model, `.context` is just one chosen intermediate level for v0.0.5, not the final shape of the language.

## Semantic units

Maybe I have to find a way to divide what's written into semantic units.

For example:

```text
insertion sort of 1 5 4
```

might become:

```text
insertion sort
1 5 4
```

But I don't know how to do this generally, or what algorithms are used for it.

The important part is that these units should be useful for provenance: each unit should be something that can cause context/code.
