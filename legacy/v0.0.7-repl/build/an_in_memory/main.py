import random
import string
import time

_store: dict = {}


def shorten(url: str, ttl: float, alias: str = None) -> str:
    if alias is not None:
        _validate_alias(alias)
        code = alias
    else:
        code = _generate_code()
    _store[code] = {'url': url, 'created': time.time(), 'ttl': ttl, 'hits': 0}
    return code

def resolve(code: str) -> str:
    return _check_and_increment(code)

def delete(code: str) -> None:
    _store.pop(code, None)

def get_stats(code: str) -> dict:
    entry = _store[code]
    return {'url': entry['url'], 'hits': entry['hits'], 'ttl': entry['ttl'], 'created': entry['created']}


def _check_and_increment(code: str) -> str:
    entry = _store[code]
    if entry['ttl'] > 0 and time.time() - entry['created'] > entry['ttl']:
        raise ValueError(code)
    entry['hits'] += 1
    return entry['url']


def _validate_alias(alias: str) -> None:
    if alias in _store:
        entry = _store[alias]
        if entry['ttl'] == 0 or time.time() - entry['created'] <= entry['ttl']:
            raise ValueError(alias)


def _generate_code() -> str:
    chars = string.ascii_letters + string.digits
    while True:
        code = ''.join(random.choices(chars, k=6))
        if code not in _store:
            return code
