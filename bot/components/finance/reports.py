"""Сборка текстового месячного отчёта (OVERVIEW §5)."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal

from asgiref.sync import sync_to_async

from bot.components.finance.aggregations import (
    ZERO,
    _q,
    _to_usd,
    load_rates_map,
)


MONTH_NAMES_RU = {
    1: "январь",
    2: "февраль",
    3: "март",
    4: "апрель",
    5: "май",
    6: "июнь",
    7: "июль",
    8: "август",
    9: "сентябрь",
    10: "октябрь",
    11: "ноябрь",
    12: "декабрь",
}


@sync_to_async
def fetch_month_transactions(user_id: int, year: int, month: int):
    from calendar import monthrange
    from core.models import Transaction

    date_from = date(year, month, 1)
    date_to = date(year, month, monthrange(year, month)[1])
    txs = list(
        Transaction.objects.filter(
            user_id=user_id,
            occurred_at__gte=date_from,
            occurred_at__lte=date_to,
        )
        .select_related("account", "category")
        .order_by("account_id", "occurred_at", "id")
    )
    return txs, date_from, date_to


def _section_for_account(
    account,
    txs: list,
    rates: dict[str, Decimal],
    missing_fx: set[str],
) -> tuple[str, Decimal]:
    """Returns (section_text, expense_usd)."""
    exp_cat: dict[str, Decimal] = defaultdict(lambda: ZERO)
    inc_cat: dict[str, Decimal] = defaultdict(lambda: ZERO)
    exp_native = ZERO
    inc_native = ZERO
    exp_usd = ZERO
    inc_usd = ZERO
    currency = (account.currency or "USD").upper()

    for tx in txs:
        amount = Decimal(tx.amount)
        cur = (tx.currency or currency).upper()
        cat = tx.category.name if tx.category_id else "Без категории"
        usd = _to_usd(amount, cur, rates, missing_fx)
        if tx.direction == "income":
            inc_native += amount
            if usd is not None:
                inc_usd += usd
                inc_cat[cat] += usd
        else:
            if tx.direction == "transfer" and (
                not tx.category_id or cat == "Без категории"
            ):
                cat = "🔁 Переводы"
            exp_native += amount
            if usd is not None:
                exp_usd += usd
                exp_cat[cat] += usd

    exp_usd, inc_usd = _q(exp_usd), _q(inc_usd)
    exp_native, inc_native = _q(exp_native), _q(inc_native)

    lines = [
        f"=== Счёт: {account.name} ({currency}) ===",
        f"Операций: {len(txs)}",
        "",
        f"--- Траты по категориям ---",
    ]
    if exp_cat:
        for name, amt in sorted(exp_cat.items(), key=lambda x: -x[1]):
            pct = (100 * amt / exp_usd) if exp_usd else ZERO
            lines.append(f"  {name}: {_q(amt)} USD ({pct:.1f}%)")
    else:
        lines.append("  —")

    lines.append("")
    lines.append("--- Доходы по типам ---")
    if inc_cat:
        for name, amt in sorted(inc_cat.items(), key=lambda x: -x[1]):
            pct = (100 * amt / inc_usd) if inc_usd else ZERO
            lines.append(f"  {name}: {_q(amt)} USD ({pct:.1f}%)")
    else:
        lines.append("  —")

    lines.append("")
    lines.append(
        f"итого трат: {exp_native} {currency} или {exp_usd} USD"
    )
    if inc_native:
        lines.append(f"итого доходов: {inc_native} {currency} или {inc_usd} USD")

    return "\n".join(lines), exp_usd


async def build_monthly_report(user_id: int, year: int, month: int) -> str:
    txs, date_from, date_to = await fetch_month_transactions(user_id, year, month)
    rates, fetched_at = await load_rates_map()
    missing_fx: set[str] = set()

    month_name = MONTH_NAMES_RU.get(month, str(month))
    header = f"{month:02d}.{year} отчет за {month_name}"
    lines = [
        f"<b>{header}</b>",
        f"Период: {date_from:%d.%m.%Y} — {date_to:%d.%m.%Y}",
        "",
    ]

    if not txs:
        lines.append("Нет операций за этот месяц.")
        return "\n".join(lines)

    by_account: dict[int, list] = defaultdict(list)
    accounts_map = {}
    for tx in txs:
        by_account[tx.account_id].append(tx)
        accounts_map[tx.account_id] = tx.account

    parts_usd: list[tuple[str, Decimal]] = []
    for account_id, account_txs in sorted(
        by_account.items(), key=lambda x: accounts_map[x[0]].name.lower()
    ):
        acc = accounts_map[account_id]
        section, exp_usd = _section_for_account(acc, account_txs, rates, missing_fx)
        lines.append(section)
        lines.append("")
        parts_usd.append((acc.name, exp_usd))

    # сводный итог трат
    total = _q(sum((p[1] for p in parts_usd), ZERO))
    if parts_usd:
        detail = " + ".join(f"{amt} USD ({name})" for name, amt in parts_usd)
        lines.append(f"<b>итого трат:</b> {detail} = <b>{total} USD</b>")

    if missing_fx:
        lines.append("")
        lines.append("⚠ Нет курса для: " + ", ".join(sorted(missing_fx)))

    if fetched_at:
        lines.append(f"курс на {fetched_at:%d.%m.%Y %H:%M} UTC (авто)")

    text = "\n".join(lines)

    await _upsert_report_cache(user_id, year, month, total, len(txs), fetched_at)
    return text


@sync_to_async
def _upsert_report_cache(
    user_id: int,
    year: int,
    month: int,
    expense_usd: Decimal,
    tx_count: int,
    rates_fetched_at: datetime | None,
):
    from core.models import MonthlyReport

    summary = {
        "expense_usd": str(expense_usd),
        "tx_count": tx_count,
        "rates_fetched_at": rates_fetched_at.isoformat() if rates_fetched_at else None,
    }
    MonthlyReport.objects.update_or_create(
        user_id=user_id,
        year=year,
        month=month,
        defaults={"summary_json": summary},
    )
