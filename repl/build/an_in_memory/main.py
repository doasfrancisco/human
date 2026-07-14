import random
import string
import time

store: dict = {}

def shorten(url: str, ttl: float = 0, alias: str = None) -> str:
    if alias is not None:
        validate_alias(alias)
        code = alias
    else:
        code = generate_code()
    store[code] = {"url": url, "created": __import__('time').time(), "ttl": ttl, "hits": 0}
    return code

def resolve(code: str) -> str:
    return check_and_increment(code)

def delete_mapping(code: str) -> None:
    if code not in store:
        raise KeyError(code)
    del store[code]

def get_stats(code: str) -> dict:
    if code not in store:
        raise KeyError(code)
    entry = store[code]
    return {"url": entry["url"], "created": entry["created"], "ttl": entry["ttl"], "hits": entry["hits"]}


def is_expired(entry: dict) -> bool:
    return entry["ttl"] > 0 and time.time() - entry["created"] > entry["ttl"]

def check_and_increment(code: str) -> str:
    if code not in store:
        raise KeyError(code)
    entry = store[code]
    if is_expired(entry):
        raise ValueError("expired")
    entry["hits"] += 1
    return entry["url"]

def validate_alias(alias: str) -> None:
    if alias in store and not is_expired(store[alias]):
        raise ValueError("alias taken")


def generate_code() -> str:
    chars = string.ascii_letters + string.digits
    while True:
        code = ''.join(random.choices(chars, k=6))
        if code not in store:
            return code
