from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass
class ParsedTransaction:
    occurred_at: date
    amount: Decimal
    currency: str
    direction: str  # income | expense | transfer
    description: str
    external_id: str | None = None
    category_hint: str | None = None
    raw: dict = field(default_factory=dict)


@dataclass
class ParseResult:
    format_hint: str
    transactions: list[ParsedTransaction]
    error: str | None = None
