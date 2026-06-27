# fran++ v0.0.3 sketches

Design method: write programs I wish I could write (PG principle 1).
Design rule: surface ONLY decisions that are silent when wrong.

Everything else is machine code — the compiler's problem.

---

## Program 1: urgent email triage

```
urgent email:
    from: client
    unread: yes
    age: < 48h
    action: summarize, suggest reply
```

Silent-when-wrong decisions:
- "client" — who counts as a client? If wrong, misses important email. No crash.
- "48h" — threshold. If should be 24h, you miss urgent ones. No crash.
- "summarize, suggest reply" — maybe you wanted "forward to assistant" instead. No crash.

Machine code (invisible):
- Gmail API auth, IMAP vs API, pagination, date parsing, LLM summarization call,
  response formatting — all of this crashes visibly if wrong.

---

## Program 2: coin change

```
coin change:
    coins: 1, 3, 4
    target: 6
    optimize: fewest
```

Silent-when-wrong decisions:
- [1, 3, 4] — the denominations. Wrong list = wrong answer, no crash.
- 6 — the target. Wrong number = wrong answer, no crash.
- "fewest" — maybe you wanted "fewest different denominations" not "fewest total coins." No crash.

Machine code (invisible):
- BFS vs DP vs greedy, state representation, queue, visited set — all machinery.

---

## Program 3: task sync

```
task sync:
    source: Notion
    urgent: due < 48h OR starred
    rank by: urgency
    send to: WhatsApp
    when: 9am daily
```

Silent-when-wrong decisions:
- "Notion" — maybe tasks moved to Linear. No crash, just empty results.
- "48h OR starred" — urgency definition. Wrong = wrong priorities surfaced.
- "urgency" — ranking criterion. Maybe you wanted "due date" not "urgency score."
- "WhatsApp" — maybe you wanted Slack. Sends to wrong place, no crash.
- "9am" — maybe you needed 7am. Runs fine, just late.

---

## Program 4: GLPI ticket routing

```
new tickets:
    status: new
    category: infrastructure
    assign to: Francisco
    escalate if: age > 4h AND priority = high
    notify: WhatsApp
```

Silent-when-wrong decisions:
- "infrastructure" — category filter. Wrong = misses tickets from other categories.
- "Francisco" — maybe should be the team, not one person.
- "4h" — escalation threshold.
- "high" — what if GLPI uses "very high" or numeric priorities?

---

## Program 5: make failing tests pass

```
fix tests:
    run: pytest
    scope: changed files only
    strategy: ???
```

This one BREAKS. "Fix tests" requires judgment about WHAT to fix — the test
or the code? That's not a threshold or a category. It's a decision tree that
depends on reading the code, understanding intent, and choosing between
multiple valid fixes.

The "strategy" slot can't be filled with a phrase. It needs something like:
"if test expectations are outdated, update test. if code regressed, revert.
if new feature broke old test, check if old behavior was intentional."

That's not a declaration anymore. That's a policy. Maybe policies are a
different primitive.

---

## What pattern emerges?

Programs 1-4 all look like:

```
[name]:
    [filter decisions]    — what to look at
    [threshold decisions] — where to draw lines
    [action decisions]    — what to do with results
    [routing decisions]   — where to send output
    [timing decisions]    — when to run
```

Every slot is a phrase. Every phrase is a decision that's silent when wrong.
The machine handles everything between the slots.

Program 5 doesn't fit. It requires a POLICY — a branching decision tree
where the right choice depends on context that can't be compressed to a phrase.

Maybe the language has two constructs:
- **declarations** for filter/threshold/action/routing/timing (programs 1-4)
- **policies** for branching judgment calls (program 5)

Or maybe program 5 is simply out of scope — it's the kind of thing that
requires a human (or an agent) in the loop, not a compiled program.

---

## Open question

Is there a program that DOESN'T decompose into "phrase-sized decisions that
are silent when wrong" + "machine code"? If so, that's where this language
hits its wall. Program 5 might be that wall. Or the wall might be further out
than I think.
