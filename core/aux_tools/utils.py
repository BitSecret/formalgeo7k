import json
from sympy import Float


def load_json(filename):
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, filename):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def rough_equal(a, b):
    """Accuracy is controlled at 0.01"""
    return abs(a - b) < 0.01


def number_round(n):
    """Round to 6 if n is Float."""
    if isinstance(n, Float):
        return n.round(6)
    return n
