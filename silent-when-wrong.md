# Silent when wrong

The load-bearing principle of fran++. Every future version is judged against it.

## Definition

A decision is **silent when wrong** if a mistake produces wrong output instead of crashing.

- **Loud when wrong:** Gmail API auth fails → `401 Unauthorized`. Date parsing breaks → `ValueError`. Wrong SQL → syntax error. You see it immediately.
- **Silent when wrong:** "client = people tagged `customer`" when you meant `lead` → the program runs fine, sends summaries to the wrong people, and you don't notice until a client complains.

## The rule

**The compiler asks the human about silent-when-wrong decisions. And only those.**

Everything else is machine code — the compiler's problem. It picks, and if it picks wrong, something will crash loudly and you'll fix it without needing to have known in advance.

This is the rule that makes the `.human` file short. You don't write the machinery because the machinery is *loud when wrong*. You only write the things that would rot silently.

## The fault line

Context files split decisions into two kinds:

```
btree.context:
    # user decisions (silent when wrong):
    information → products (name, price)
    sort by → price

    # compiler defaults (edit to tune):
    branching factor → 4
```

- Wrong user decision → user's fault → edit `.human`.
- Wrong compiler default → compiler's fault → tune `.context`.

That boundary is where debugging starts. If something is silently wrong, look at the user decisions first. If something crashed, look at the generated code.

## Worked examples

Every `.human` block decomposes the same way. Silent-when-wrong decisions become phrases in the spec. The machinery stays invisible.

### Urgent email triage

```
urgent email:
    from: client
    unread: yes
    age: < 48h
    action: summarize, suggest reply
```

Silent when wrong: who counts as "client"; whether 48h is the right threshold; whether you want "summarize" or "forward to assistant."

Machine code (invisible): Gmail API auth, IMAP vs API, pagination, date parsing, LLM summarization call, response formatting. All of this crashes visibly if something's off.

### Coin change

```
coin change:
    coins: 1, 3, 4
    target: 6
    optimize: fewest
```

Silent when wrong: the denominations, the target, what "fewest" means (fewest total coins vs fewest distinct denominations).

Machine code: BFS vs DP vs greedy, state representation, queue, visited set.

### Task sync

```
task sync:
    source: Notion
    urgent: due < 48h OR starred
    rank by: urgency
    send to: WhatsApp
    when: 9am daily
```

Silent when wrong: is it still Notion (or did you move to Linear?); is urgency "due-date-proximity" or "starred-count"; is WhatsApp the right destination; is 9am early enough.

### GLPI ticket routing

```
new tickets:
    status: new
    category: infrastructure
    assign to: Francisco
    escalate if: age > 4h AND priority = high
    notify: WhatsApp
```

Silent when wrong: the category filter (miss tickets from other categories); assignee (should it be the team?); 4h threshold; whether GLPI's priority field is `high` or numeric.

## Where it breaks

Not every program decomposes into "phrase-sized silent-when-wrong decisions + machinery." Some require **policies** — branching judgment that depends on reading context.

```
fix tests:
    run: pytest
    scope: changed files only
    strategy: ???
```

"Fix tests" requires deciding *what* to fix: the test, the code, or neither. That's not a threshold or a category. It's a decision tree:

> if test expectations are outdated → update test
> if code regressed → revert
> if new feature broke an old test → check if old behavior was intentional

That's a policy, not a declaration. Maybe the language needs a second primitive for policies. Or maybe these programs are out of scope for compilation and belong in agent workflows instead.

## Open question

Is there a program that doesn't decompose into "silent-when-wrong phrases + machinery"? If so, that's the wall. "Fix failing tests" might be the wall. Or the wall might be much further out.
