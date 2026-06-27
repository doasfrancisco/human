# Nia sources for fran++

## Rules

- **Never pipe `nia` output through `head -N` or `tail -N`.** The output can be 2000+ lines. You MUST read ALL of it. If the output is split across chunks, read every chunk before proceeding. Missing a single source leads to wrong follow-up searches and wasted user time.
- **If the source is a package/library, always ask how to install it** (pip name, Python/Node version, any extras). E.g. `"how do I install X - pip name, python version, async extras?"`

## Sources

| Dep | Nia identifier | Type |
|---|---|---|
| AWS docs (Bedrock API keys, boto3, runtime) | `https://docs.aws.amazon.com/` | documentation |
| FastAPI framework | `fastapi/fastapi` / `d97110e7-825a-463f-87f6-7e21fe6cab4b` | repository |

## Examples

```bash
nia search query "AWS_BEARER_TOKEN_BEDROCK boto3 example" --docs "https://docs.aws.amazon.com/"
nia search query "bedrock-runtime converse Python" --docs "https://docs.aws.amazon.com/"
nia sources resolve "https://docs.aws.amazon.com/" --type documentation
nia sources tree ad88402b-a9e3-4281-a9ee-7d484a943b8f
nia sources grep ad88402b-a9e3-4281-a9ee-7d484a943b8f "AWS_BEARER_TOKEN_BEDROCK"
nia sources read ad88402b-a9e3-4281-a9ee-7d484a943b8f bedrock/latest/userguide/api-keys-use.md
nia search query "FastAPI route static files templates websocket examples" --repos "fastapi/fastapi"
nia repos tree d97110e7-825a-463f-87f6-7e21fe6cab4b
```

### Multi-source query

```bash
# Example
nia search query "how do I authenticate a Bedrock Converse call" \
  --docs "https://docs.aws.amazon.com/,https://platform.claude.com/docs"
```
