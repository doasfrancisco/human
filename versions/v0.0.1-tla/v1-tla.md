# fran++ changes from standard TLA+

Differences between fran++ syntax and standard TLA+.

| Standard TLA+ | fran++ alternative | Why |
|---------------|-------------------|-----|
| `/\` | `and` | Readable, no escaping needed |
| `\/` | `or` | Same |

Both forms are accepted. You can mix them in the same spec.
