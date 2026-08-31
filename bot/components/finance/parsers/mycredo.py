from __future__ import annotations

from decimal import Decimal

from bot.components.finance.parsers.base import ParsedTransaction, ParseResult
from bot.components.finance.parsers.common import (
    make_external_id,
    normalize_header,
    parse_date,
    parse_money,
)
from bot.components.finance.categorizer import categorize


def looks_like_mycredo(rows: list[list[str]]) -> bool:
    if not rows:
        return False
    header = " | ".join(normalize_header(c) for c in rows[0][:12])
    return "оборот (дб)" in header or "оборот (кр)" in header or "операция" in header


def parse_mycredo(
    rows: list[list[str]],
    *,
    account_id: int,
    currency: str,
) -> ParseResult:
    if not rows:
        return ParseResult("mycredo", [], error="Пустой лист транзакций")
    header = [normalize_header(h) for h in rows[0]]

    def find(*names: str) -> int | None:
        for n in names:
            if n in header:
                return header.index(n)
        return None

    i_date = find("дата")
    i_op = find("операция")
    i_db = find("оборот (дб)")
    i_cr = find("оборот (кр)")
    i_desc = find("описание")
    if None in (i_date, i_db, i_cr):
        # fixed fallback
        i_date, i_op, i_db, i_cr, _, i_desc = 0, 1, 2, 3, 4, 5

    txs: list[ParsedTransaction] = []
    for row_num, row in enumerate(rows[1:], start=2):
        if not any((c or "").strip() for c in row[:6]):
            continue
        d = parse_date(row[i_date] if i_date is not None and i_date < len(row) else "")
        if not d:
            continue
        debit = parse_money(row[i_db] if i_db is not None and i_db < len(row) else "")
        credit = parse_money(row[i_cr] if i_cr is not None and i_cr < len(row) else "")
        op = row[i_op] if i_op is not None and i_op < len(row) else ""
        desc = row[i_desc] if i_desc is not None and i_desc < len(row) else ""
        desc_full = f"{op} {desc}".strip() if op else (desc or "").strip()

        if debit > 0 and credit > 0:
            # rare; treat larger as primary
            if debit >= credit:
                credit = Decimal("0")
            else:
                debit = Decimal("0")

        if debit > 0:
            amount = debit
            direction, hint = categorize(desc_full, op, default_direction="expense")
        elif credit > 0:
            amount = credit
            direction, hint = categorize(desc_full, op, default_direction="income")
        else:
            continue

        ext = make_external_id(
            account_id=account_id,
            occurred_at=d,
            amount=amount,
            direction=direction,
            description=desc_full,
            currency=currency,
            sequence=row_num,
        )
        txs.append(
            ParsedTransaction(
                occurred_at=d,
                amount=amount,
                currency=currency,
                direction=direction,
                description=desc_full,
                external_id=ext,
                category_hint=hint,
                raw={"operation": op, "description": desc},
            )
        )
    return ParseResult("mycredo", txs)
