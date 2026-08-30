import time

FAILURES = {"user": 2, "orders": 1, "prices": 2}
DATA = {
    "user": {"id": 7, "name": "ada"},
    "orders": [{"sku": "a1", "qty": 2}, {"sku": "b2", "qty": 1}],
    "prices": {"a1": 3.5, "b2": 10.0},
}


def flaky_get(source):
    if FAILURES[source] > 0:
        FAILURES[source] -= 1
        raise ConnectionError(source)
    return DATA[source]


def fetch_user():
    wait = 0.01
    for attempt in range(5):
        try:
            return flaky_get("user")
        except ConnectionError:
            time.sleep(wait)
            wait *= 2
    raise RuntimeError("user never answered")


def fetch_orders():
    wait = 0.02
    for attempt in range(4):
        try:
            return flaky_get("orders")
        except ConnectionError:
            time.sleep(wait)
            wait *= 2
    raise RuntimeError("orders never answered")


def fetch_prices():
    wait = 0.01
    for attempt in range(6):
        try:
            raw = flaky_get("prices")
            return {sku: round(p * 1.2, 2) for sku, p in raw.items()}
        except ConnectionError:
            time.sleep(wait)
            wait *= 2
    raise RuntimeError("prices never answered")


def sum_leaves(tree):
    if isinstance(tree, dict):
        return sum(sum_leaves(v) for v in tree.values())
    return tree


def deep_flag(tree, limit):
    if isinstance(tree, dict):
        return {k: deep_flag(v, limit) for k, v in tree.items()}
    return tree > limit


def average_scores(scores):
    if not isinstance(scores, list) or not scores:
        raise ValueError("scores must be a non-empty list")
    if any(not isinstance(s, (int, float)) for s in scores):
        raise ValueError("scores must hold only numbers")
    return sum(scores) / len(scores)


def spread_scores(scores):
    if not isinstance(scores, list) or not scores:
        raise ValueError("scores must be a non-empty list")
    if any(not isinstance(s, (int, float)) for s in scores):
        raise ValueError("scores must hold only numbers")
    return max(scores) - min(scores)


def roman(n):
    steps = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"),
             (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"),
             (5, "V"), (4, "IV"), (1, "I")]
    out = ""
    for value, glyph in steps:
        while n >= value:
            out += glyph
            n -= value
    return out


def luhn_ok(number):
    digits = [int(c) for c in str(number)][::-1]
    total = 0
    for i, d in enumerate(digits):
        if i % 2:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


if __name__ == "__main__":
    user = fetch_user()
    orders = fetch_orders()
    prices = fetch_prices()
    bill = sum(prices[o["sku"]] * o["qty"] for o in orders)
    spend = {"food": {"fruit": 4, "bread": 3}, "travel": 12}
    print(user["name"], round(bill, 2))
    print(sum_leaves(spend), deep_flag(spend, 5))
    print(average_scores([3, 4, 5]), spread_scores([3, 4, 5]))
    print(roman(1987), luhn_ok(79927398713))
