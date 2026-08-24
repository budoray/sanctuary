"""Dice expression parser and roller for Sanctuary.

Supports standard OSRIC notation such as 3d6, d20, 1d8+2, 2d6-1,
and compound expressions like d6+d4+3.
"""
from __future__ import annotations

import random
import re


_DICE_RE = re.compile(r"^(\d*)d(\d+)$", re.IGNORECASE)


class DiceError(ValueError):
    """Raised when a dice expression cannot be parsed or rolled."""


def _parse_die_term(term: str) -> tuple[int, int]:
    match = _DICE_RE.match(term)
    if not match:
        raise DiceError(f"Invalid dice term: '{term}'")
    count = int(match.group(1)) if match.group(1) else 1
    sides = int(match.group(2))
    if count < 1 or sides < 1:
        raise DiceError(f"Dice term must have positive count and sides: '{term}'")
    return count, sides


def roll_expression(expression: str) -> dict:
    """Parse and roll a dice expression.

    Returns a dict with:
        expression: original string
        total: numeric result
        parts: list of rolled terms/modifiers
    """
    if not expression or not expression.strip():
        raise DiceError("Empty dice expression")

    # Split into signed terms, preserving leading +/-.
    tokens = re.split(r"(?=[+-])", expression.replace(" ", ""))
    total = 0
    parts: list[dict] = []

    for raw in tokens:
        if not raw:
            continue
        sign = -1 if raw.startswith("-") else 1
        body = raw.lstrip("+-")
        if not body:
            raise DiceError(f"Invalid term in expression: '{expression}'")

        if "d" in body.lower():
            count, sides = _parse_die_term(body)
            results = [random.randint(1, sides) for _ in range(count)]
            term_total = sum(results)
            parts.append(
                {
                    "type": "dice",
                    "sign": sign,
                    "count": count,
                    "sides": sides,
                    "results": results,
                    "term_total": term_total,
                }
            )
        else:
            try:
                value = int(body)
            except ValueError as exc:
                raise DiceError(f"Invalid term: '{body}'") from exc
            term_total = value
            parts.append(
                {
                    "type": "modifier",
                    "sign": sign,
                    "value": value,
                    "term_total": term_total,
                }
            )

        total += sign * term_total

    return {
        "expression": expression,
        "total": total,
        "parts": parts,
    }
