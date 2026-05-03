# fran++ v0.0.3 — the language

## The rule

Every line is a human decision that is **silent when wrong**.
Everything else is compiled away. You never see it.

## The structure

Every program is a named block of key-value pairs.
Every value is a phrase. Every phrase is a decision you own.

```
name
    key: value
    key: value
```

That's the whole syntax.

---

## Programs

### 1. Email triage

```
urgent-emails
    when: new email
    from: client
    age: < 48h
    do: summarize, suggest reply
    send: WhatsApp
```

5 decisions. All silent when wrong.
- "client" — wrong definition? Wrong emails surfaced. No crash.
- "48h" — wrong threshold? Miss urgent ones. No crash.
- "WhatsApp" — wrong channel? Goes to wrong place. No crash.

### 2. Coin change

```
coin-change
    coins: 1, 3, 4
    target: 6
    optimize: fewest coins
```

3 decisions.
- [1, 3, 4] — wrong denominations? Wrong answer. No crash.
- 6 — wrong target? Wrong answer. No crash.
- "fewest coins" — maybe meant "fewest distinct denominations." No crash.

### 3. Binary search

```
find
    in: sorted list
    target: x
```

2 decisions.
- "sorted" — if list isn't sorted, wrong result. No crash.
- "x" — wrong target? Finds wrong thing. No crash.

### 4. Morning tasks

```
morning-tasks
    when: 9am daily
    source: Notion
    filter: due < 48h OR starred
    rank: urgency
    send: WhatsApp
```

### 5. Ticket routing

```
ticket-routing
    when: new GLPI ticket
    category: infrastructure
    assign: Francisco
    escalate: age > 4h AND priority = high
    notify: WhatsApp
```

### 6. Agent-crystallized rule

An agent (Claude Code) ran once, reasoned through a failing test,
and deposited this rule so it never has to reason again:

```
fix-schema-tests
    when: tests fail AND schema changed
    update: fixtures
    not: source code
```

---

## Composition

Blocks reference other blocks by name.

```
my-clients
    source: contacts
    tag: client

urgent-emails
    when: new email
    from: my-clients        ← references the block above
    age: < 48h
    do: summarize
    send: WhatsApp
```

"my-clients" is defined once, used anywhere. The compiler resolves
the reference. If `my-clients` changes, everything downstream changes.

A pipeline is just blocks that reference each other:

```
raw-tasks
    source: Notion

urgent-tasks
    data: raw-tasks
    filter: due < 48h OR starred

morning-report
    when: 9am daily
    data: urgent-tasks
    rank: urgency
    send: WhatsApp
```

Three blocks. Each one makes 1-2 decisions. The pipeline emerges
from the references, not from explicit sequencing.

---

## What the compiler does

```
urgent-emails                        ← you write this (5 decisions)
    when: new email
    from: client
    age: < 48h
    do: summarize, suggest reply
    send: WhatsApp
```

```python
# compiler emits this (you never see it)

def on_new_email(email):
    if not is_client(email.sender):
        return
    if email.age > timedelta(hours=48):
        return
    summary = llm_summarize(email.body)
    reply = llm_suggest_reply(email.body)
    whatsapp_send(f"{summary}\n\nSuggested reply:\n{reply}")

gmail_watch(callback=on_new_email)    # machine code
```

30 lines of Python. 0 of them are your decisions.
The 5 decisions live in the block. Everything else is machinery.

---

## What about the context file?

First compile of `from: client` — compiler asks: "Who counts as a client?"
You say: "Anyone in my contacts tagged 'client'."

That goes in the context file:

```
context:
    client → contacts tagged "client"
```

Next time, it compiles without asking. Same block + same context =
same Python. The program never changes. The context file grows.

---

## The keys

Not a fixed set. But patterns emerge:

| Key | What it decides | Example |
|-----|----------------|---------|
| when | trigger | new email, 9am daily, tests fail |
| source/in/from | where data comes from | Notion, contacts, sorted list |
| filter | what to keep | due < 48h, unread, category = X |
| rank/optimize | what to maximize/minimize | urgency, fewest coins |
| do/update/assign | what action to take | summarize, update fixtures |
| send/notify | where output goes | WhatsApp, Slack |
| not | what to explicitly avoid | source code, mocks |

The keys aren't keywords in a grammar. They're semantic slots.
The compiler reads them as natural language, not as syntax.

---

## Is this Turing-complete?

Blocks + references + agents adding new blocks = a growing rule set.

Each block is a state transition. Blocks that reference other blocks
create chains. An agent can add blocks at runtime. The rule set evolves.

This is a production system — rules that fire on conditions and
transform state. Production systems are Turing-complete.

But honestly: Turing-completeness might be the wrong goal. The
language handles rules. Agents handle judgment. Python handles
everything else. The question isn't "can this replace Python?" but
"what percentage of the programs I actually write are rules?"

If the answer is 80%, the language covers 80% of your work and
the rest stays in Python/agent territory. That might be enough.

---

## What this ISN'T

- Not YAML. YAML is a data format. This compiles to executable code.
- Not IFTTT. IFTTT has fixed triggers. This has natural language conditions.
- Not a prompt. Prompts are freeform. This has named blocks, typed slots,
  and references. Structure is what makes it debuggable and composable.
- Not Python with fewer keywords. Python conflates your decisions with
  machine code. This separates them by construction.
