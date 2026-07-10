"""Compiled from .human via .context — DO NOT EDIT."""
import random

if __name__ == "__main__":
    value = random.randint(1, 100)
    print(value)
    assert 1 <= value <= 100, f"Value {value} is out of range [1, 100]"
