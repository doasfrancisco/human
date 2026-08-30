import json
import sys


class Tally:
    def __init__(self):
        self.total = 0

    def add(self, n):
        self.total += n * 2


def digits(text):
    out = []
    for ch in text:
        if ch.isdigit():
            out.append(int(ch))
    return out


def spread(nums):
    top = max(nums)
    low = min(nums)
    return top - low


def report(path):
    src = open(path, encoding="utf-8").read()
    nums = digits(src)
    if not nums:
        return {"file": path, "count": 0}
    t = Tally()
    for n in nums:
        t.add(n)
    wide = spread(nums)
    line = f"{len(nums)} digits, doubled total {t.total}, spread {wide}"
    print(line)
    return {"file": path, "count": len(nums), "total": t.total, "spread": wide}


out = report(sys.argv[1] if len(sys.argv) > 1 else __file__)
print(json.dumps(out))
