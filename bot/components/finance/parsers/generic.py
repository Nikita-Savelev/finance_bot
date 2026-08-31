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


DATE_ALIASES = {
    "дата",
    "date",
    "datetime",
    "дата операции",
    "дата проводки",
    "booking date",
    "value date",
}
AMOUNT_ALIASES = {
    "сумма",
    "amount",
    "sum",
    "оборот",
    "value",
    "сумма операции",
}
DEBIT_ALIASES = {"дебет", "debit", "списание", "оборот (дб)", "expense", "расход"}
CREDIT_ALIASES = {"кредит", "credit", "пополнение", "оборот (кр)", "income", "доход"}
DESC_ALIASES = {
    "описание",
    "description",
    "назначение",
    "details",
    "merchant",
    "комментарий",
    "narrative",
    "операция",
}
DIR_ALIASES = {"тип", "type", "direction", "вид операции"}


def _find_col(header: list[str], aliases: set[str]) -> int | None:
    for i, h in enumerate(header):
        if h in aliases:
            return i
    for i, h in enumerate(header):
        for a in aliases:
            if a in h:
                return i
    return None


def parse_generic(
    rows: list[list[str]],
    *,
    account_id: int,
    currency: str,
) -> ParseResult:
    if not rows or len(rows) < 2:
        return ParseResult("generic", [], error="Нужна строка заголовков и данные")

    # найти строку заголовка среди первых 5
    header_idx = 0
    header = [normalize_header(c) for c in rows[0]]
    for idx in range(min(5, len(rows))):
        cand = [normalize_header(c) for c in rows[idx]]
        if _find_col(cand, DATE_ALIASES) is not None and (
            _find_col(cand, AMOUNT_ALIASES) is not None
            or _find_col(cand, DEBIT_ALIASES) is not None
        ):
            header_idx = idx
            header = cand
            break

    i_date = _find_col(header, DATE_ALIASES)
    i_amount = _find_col(header, AMOUNT_ALIASES)
    i_debit = _find_col(header, DEBIT_ALIASES)
    i_credit = _find_col(header, CREDIT_ALIASES)
    i_desc = _find_col(header, DESC_ALIASES)
    i_dir = _find_col(header, DIR_ALIASES)

    if i_date is None:
        return ParseResult(
            "generic",
            [],
            error="Не нашёл колонку даты. Нужны заголовки вроде «Дата», «Сумма», «Описание».",
        )
    if i_amount is None and i_debit is None and i_credit is None:
        return ParseResult(
            "generic",
            [],
            error="Не нашёл колонку суммы / дебет / кредит.",
        )

    txs: list[ParsedTransaction] = []
    for row in rows[header_idx + 1 :]:
        if not any((c or "").strip() for c in row):
            continue
        d = parse_date(row[i_date] if i_date < len(row) else "")
        if not d:
            continue
        desc = ""
        if i_desc is not None and i_desc < len(row):
            desc = (row[i_desc] or "").strip()

        direction = None
        amount = Decimal("0")

        if i_debit is not None or i_credit is not None:
            debit = parse_money(row[i_debit] if i_debit is not None and i_debit < len(row) else "")
            credit = parse_money(
                row[i_credit] if i_credit is not None and i_credit < len(row) else ""
            )
            if debit > 0:
                amount, direction = debit, "expense"
            elif credit > 0:
                amount, direction = credit, "income"
            else:
                continue
        else:
            raw_amt = parse_money(row[i_amount] if i_amount < len(row) else "")
            if raw_amt == 0:
                continue
            if i_dir is not None and i_dir < len(row):
                tip = normalize_header(row[i_dir])
                if any(x in tip for x in ("доход", "income", "credit", "пополн")):
                    direction = "income"
                    amount = abs(raw_amt)
                elif any(x in tip for x in ("расход", "expense", "debit", "спис")):
                    direction = "expense"
                    amount = abs(raw_amt)
            if direction is None:
                if raw_amt < 0:
                    direction = "expense"
                    amount = abs(raw_amt)
                else:
                    # default expense for positive single amount columns (card statements)
                    direction = "expense"
                    amount = raw_amt

        direction, hint = categorize(desc, "", default_direction=direction or "expense")
        ext = make_external_id(
            account_id=account_id,
            occurred_at=d,
            amount=amount,
            direction=direction,
            description=desc,
            currency=currency,
        )
        txs.append(
            ParsedTransaction(
                occurred_at=d,
                amount=amount,
                currency=currency,
                direction=direction,
                description=desc,
                external_id=ext,
                category_hint=hint,
            )
        )

    if not txs:
        return ParseResult(
            "generic",
            [],
            error="Строки найдены, но операции не распознаны.",
        )
    return ParseResult("generic", txs)
