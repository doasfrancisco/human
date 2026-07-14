import random
import string
import time

_store = {}

def _is_live(record):
    return (time.time() - record["created_at"]) < record["ttl"]

def shorten(url, ttl, alias=None):
    if alias is not None:
        if alias in _store and _is_live(_store[alias]):
            raise ValueError(f"Alias '{alias}' is already taken by a live link")
        code = alias
    else:
        while True:
            code = "".join(random.choices(string.ascii_letters + string.digits, k=6))
            if code not in _store or not _is_live(_store[code]):
                break
    _store[code] = {
        "url": url,
        "created_at": time.time(),
        "ttl": ttl,
        "hits": 0,
    }
    return code

def resolve(code):
    if code not in _store:
        raise ValueError(f"Code '{code}' does not exist")
    record = _store[code]
    if not _is_live(record):
        raise ValueError(f"Code '{code}' has expired")
    record["hits"] += 1
    return record["url"]

def stats(code):
    if code not in _store:
        raise ValueError(f"Code '{code}' does not exist")
    record = _store[code]
    if not _is_live(record):
        raise ValueError(f"Code '{code}' has expired")
    return {"hits": record["hits"]}

if __name__ == "__main__":
    code = shorten("https://example.com", ttl=60)
    print(code)
    print(resolve(code))
    print(resolve(code))
    print(stats(code))
    custom = shorten("https://other.com", ttl=60, alias="mylink")
    print(custom)
    print(resolve("mylink"))
    print(stats("mylink"))