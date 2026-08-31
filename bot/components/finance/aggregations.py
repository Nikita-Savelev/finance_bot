"""Агрегации транзакций за период."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Iterable

from asgiref.sync import sync_to_async


ZERO = Decimal("0.00")


@dataclass
class AccountPeriodStats:
    account_id: int
    account_name: str
    currency: str
    # суммы в валюте счёта
    expense_by_cat: dict[str, Decimal] = field(default_factory=dict)
    income_by_cat: dict[str, Decimal] = field(default_factory=dict)
    expense_by_currency: dict[str, Decimal] = field(default_factory=dict)
    income_by_currency: dict[str, Decimal] = field(default_factory=dict)
    expense_native: Decimal = ZERO
    income_native: Decimal = ZERO
    # USD — для сводки «все счета» и конвертации
    expense_usd: Decimal = ZERO
    income_usd: Decimal = ZERO
    expense_rub: Decimal | None = None
    income_rub: Decimal | None = None
    tx_count: int = 0


@dataclass
class PeriodStats:
    date_from: date
    date_to: date
    expense_by_cat: dict[str, Decimal] = field(default_factory=dict)
    income_by_cat: dict[str, Decimal] = field(default_factory=dict)
    expense_by_currency: dict[str, Decimal] = field(default_factory=dict)
    income_by_currency: dict[str, Decimal] = field(default_factory=dict)
    expense_by_account: dict[str, Decimal] = field(default_factory=dict)
    by_account: list[AccountPeriodStats] = field(default_factory=list)
    expense_usd: Decimal = ZERO
    income_usd: Decimal = ZERO
    expense_rub: Decimal | None = None
    income_rub: Decimal | None = None
    tx_count: int = 0
    missing_fx: set[str] = field(default_factory=set)
    rates_fetched_at: datetime | None = None
    rub_per_usd: Decimal | None = None


def _q(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"))


def build_period_stats(
    transactions: Iterable,
    *,
    date_from: date,
    date_to: date,
    rates: dict[str, Decimal],
    rates_fetched_at: datetime | None = None,
) -> PeriodStats:
    """rates: quote -> units of quote per 1 USD."""
    stats = PeriodStats(
        date_from=date_from,
        date_to=date_to,
        rates_fetched_at=rates_fetched_at,
    )
    exp_cat: dict[str, Decimal] = defaultdict(lambda: ZERO)
    inc_cat: dict[str, Decimal] = defaultdict(lambda: ZERO)
    exp_cur: dict[str, Decimal] = defaultdict(lambda: ZERO)
    inc_cur: dict[str, Decimal] = defaultdict(lambda: ZERO)
    exp_acc: dict[str, Decimal] = defaultdict(lambda: ZERO)

    # account_id -> accumulators
    acc_data: dict[int, dict] = {}

    rub_rate = rates.get("RUB")
    if rub_rate is not None and rub_rate != 0:
        stats.rub_per_usd = Decimal(rub_rate)

    def _acc_bucket(tx) -> dict:
        acc = getattr(tx, "account", None)
        if acc is not None:
            aid = int(acc.id)
            name = acc.name
            acur = (acc.currency or tx.currency or "USD").upper()
        else:
            aid = 0
            name = "Без счёта"
            acur = (tx.currency or "USD").upper()
        if aid not in acc_data:
            acc_data[aid] = {
                "name": name,
                "currency": acur,
                "exp_cat": defaultdict(lambda: ZERO),
                "inc_cat": defaultdict(lambda: ZERO),
                "exp_cur": defaultdict(lambda: ZERO),
                "inc_cur": defaultdict(lambda: ZERO),
                "expense_native": ZERO,
                "income_native": ZERO,
                "expense_usd": ZERO,
                "income_usd": ZERO,
                "tx_count": 0,
            }
        return acc_data[aid]

    for tx in transactions:
        stats.tx_count += 1
        amount = Decimal(tx.amount)
        cur = (tx.currency or "USD").upper()
        cat_name = tx.category.name if tx.category_id else "Без категории"
        bucket = _acc_bucket(tx)
        bucket["tx_count"] += 1
        acc_label = f"{bucket['name']} ({bucket['currency']})"
        acc_cur = bucket["currency"]

        usd = _to_usd(amount, cur, rates, stats.missing_fx)
        native = _to_currency(
            amount, cur, acc_cur, rates, stats.missing_fx
        )

        # transfer считаем обычным расходом (категория «🔁 Переводы»)
        if tx.direction == "income":
            inc_cat[cat_name] += usd if usd is not None else ZERO
            inc_cur[cur] += amount
            bucket["inc_cur"][cur] += amount
            if native is not None:
                bucket["inc_cat"][cat_name] += native
                bucket["income_native"] += native
            if usd is not None:
                stats.income_usd += usd
                bucket["income_usd"] += usd
        else:
            if tx.direction == "transfer" and (
                not tx.category_id or cat_name == "Без категории"
            ):
                cat_name = "🔁 Переводы"
            exp_cat[cat_name] += usd if usd is not None else ZERO
            exp_cur[cur] += amount
            bucket["exp_cur"][cur] += amount
            if native is not None:
                bucket["exp_cat"][cat_name] += native
                bucket["expense_native"] += native
            if usd is not None:
                stats.expense_usd += usd
                exp_acc[acc_label] += usd
                bucket["expense_usd"] += usd

    stats.expense_by_cat = {k: _q(v) for k, v in exp_cat.items() if v}
    stats.income_by_cat = {k: _q(v) for k, v in inc_cat.items() if v}
    stats.expense_by_currency = {k: _q(v) for k, v in exp_cur.items() if v}
    stats.income_by_currency = {k: _q(v) for k, v in inc_cur.items() if v}
    stats.expense_by_account = {k: _q(v) for k, v in exp_acc.items() if v}
    stats.expense_usd = _q(stats.expense_usd)
    stats.income_usd = _q(stats.income_usd)
    if stats.rub_per_usd is not None:
        stats.expense_rub = _q(stats.expense_usd * stats.rub_per_usd)
        stats.income_rub = _q(stats.income_usd * stats.rub_per_usd)

    by_acc: list[AccountPeriodStats] = []
    for aid, b in acc_data.items():
        a = AccountPeriodStats(
            account_id=aid,
            account_name=b["name"],
            currency=b["currency"],
            expense_by_cat={k: _q(v) for k, v in b["exp_cat"].items() if v},
            income_by_cat={k: _q(v) for k, v in b["inc_cat"].items() if v},
            expense_by_currency={k: _q(v) for k, v in b["exp_cur"].items() if v},
            income_by_currency={k: _q(v) for k, v in b["inc_cur"].items() if v},
            expense_native=_q(b["expense_native"]),
            income_native=_q(b["income_native"]),
            expense_usd=_q(b["expense_usd"]),
            income_usd=_q(b["income_usd"]),
            tx_count=b["tx_count"],
        )
        if stats.rub_per_usd is not None:
            a.expense_rub = _q(a.expense_usd * stats.rub_per_usd)
            a.income_rub = _q(a.income_usd * stats.rub_per_usd)
        by_acc.append(a)
    by_acc.sort(key=lambda x: x.expense_usd, reverse=True)
    stats.by_account = by_acc
    return stats


def _to_usd(
    amount: Decimal,
    currency: str,
    rates: dict[str, Decimal],
    missing: set[str],
) -> Decimal | None:
    if currency == "USD":
        return amount
    rate = rates.get(currency)
    if rate is None or rate == 0:
        missing.add(currency)
        return None
    return amount / rate


def _to_currency(
    amount: Decimal,
    from_cur: str,
    to_cur: str,
    rates: dict[str, Decimal],
    missing: set[str],
) -> Decimal | None:
    """Конвертация суммы в валюту счёта через USD."""
    from_cur = (from_cur or "USD").upper()
    to_cur = (to_cur or "USD").upper()
    if from_cur == to_cur:
        return amount
    usd = _to_usd(amount, from_cur, rates, missing)
    if usd is None:
        return None
    if to_cur == "USD":
        return usd
    rate = rates.get(to_cur)
    if rate is None or rate == 0:
        missing.add(to_cur)
        return None
    return usd * rate


def format_stats_text(
    stats: PeriodStats,
    *,
    account_id: int | None = None,
    all_accounts: bool = False,
) -> str:
    """Сводка.

    - account_id=int — один счёт
    - all_accounts=True — только сводка «Все счета» (USD)
    - иначе — блоки по счетам без общей сводки
    """
    if account_id is not None:
        acc = next((a for a in stats.by_account if a.account_id == account_id), None)
        lines = [
            f"<b>📊 Статистика</b>",
            f"Период: {stats.date_from:%d.%m.%Y} — {stats.date_to:%d.%m.%Y}",
        ]
        if acc is None:
            lines.append("")
            lines.append("Нет операций по этому счёту.")
            return "\n".join(lines)
        lines.append(f"Счёт: <b>{acc.account_name}</b> ({acc.currency})")
        lines.append(f"Операций: {acc.tx_count}")
        lines.append("")
        lines.extend(_format_account_body(acc))
        lines.extend(_format_footer(stats))
        return "\n".join(lines)

    if all_accounts:
        lines = [
            f"<b>📊 Все счета</b>",
            f"Период: {stats.date_from:%d.%m.%Y} — {stats.date_to:%d.%m.%Y}",
            f"Операций: {stats.tx_count}",
            "",
        ]
        lines.extend(_format_all_accounts_body(stats))
        lines.extend(_format_footer(stats))
        return "\n".join(lines)

    lines = [
        f"<b>📊 Статистика</b>",
        f"Период: {stats.date_from:%d.%m.%Y} — {stats.date_to:%d.%m.%Y}",
        f"Операций: {stats.tx_count}",
    ]
    for acc in stats.by_account:
        lines.append("")
        lines.append(f"<b>💳 {acc.account_name}</b> ({acc.currency})")
        lines.extend(_format_account_body(acc))
    lines.extend(_format_stats_totals_footer(stats))
    return "\n".join(lines)


def _format_stats_totals_footer(stats: PeriodStats) -> list[str]:
    """Итог в USD≈RUB, курс, затем нативные суммы по каждой валюте."""
    def _amt(usd: Decimal, rub: Decimal | None) -> str:
        if rub is None:
            return f"{usd} USD"
        return f"{usd} USD ≈ {rub} RUB"

    lines: list[str] = [
        "",
        f"<b>Итого расходы:</b> {_amt(stats.expense_usd, stats.expense_rub)}",
        f"<b>Итого доходы:</b> {_amt(stats.income_usd, stats.income_rub)}",
    ]
    lines.extend(_format_footer(stats))

    exp_cur = _multi_cur_line(stats.expense_by_currency)
    inc_cur = _multi_cur_line(stats.income_by_currency)
    if exp_cur != "—" or inc_cur != "—":
        lines.append("")
        lines.append("<b>По валютам:</b>")
        if exp_cur != "—":
            lines.append(f"расходы: {exp_cur}")
        if inc_cur != "—":
            lines.append(f"доходы: {inc_cur}")
    return lines


def _format_all_accounts_body(stats: PeriodStats) -> list[str]:
    lines = [
        f"<b>Расходы</b>: <b>{stats.expense_usd} USD</b>",
    ]
    lines.extend(_cat_lines(stats.expense_by_cat, stats.expense_usd))
    if stats.expense_by_currency:
        lines.append("  по валютам: " + _cur_line(stats.expense_by_currency))
    if stats.expense_by_account:
        lines.append("  по счетам:")
        lines.extend(_cat_lines(stats.expense_by_account, stats.expense_usd))
    lines.append(f"  {_dual_total(stats.expense_usd, stats.expense_rub)}")

    lines.append("")
    lines.append(f"<b>Доходы</b>: <b>{stats.income_usd} USD</b>")
    lines.extend(_cat_lines(stats.income_by_cat, stats.income_usd))
    if stats.income_by_currency:
        lines.append("  по валютам: " + _cur_line(stats.income_by_currency))
    lines.append(f"  {_dual_total(stats.income_usd, stats.income_rub)}")

    net = _q(stats.income_usd - stats.expense_usd)
    net_rub = (
        _q(net * stats.rub_per_usd) if stats.rub_per_usd is not None else None
    )
    lines.append("")
    lines.append(
        f"<b>Чистый поток</b> (доход − расход): <b>{_dual_total(net, net_rub)}</b>"
    )
    return lines


def _format_account_body(acc: AccountPeriodStats) -> list[str]:
    """Суммы счёта — в валюте счёта, USD справочно."""
    cur = acc.currency
    lines = [
        f"<b>Расходы</b>: <b>{acc.expense_native} {cur}</b>",
    ]
    lines.extend(_cat_lines(acc.expense_by_cat, acc.expense_native))
    if len(acc.expense_by_currency) > 1:
        lines.append("  по валютам: " + _cur_line(acc.expense_by_currency))
    lines.append(f"  {_account_dual(acc.expense_native, cur, acc.expense_usd)}")

    lines.append(f"<b>Доходы</b>: <b>{acc.income_native} {cur}</b>")
    lines.extend(_cat_lines(acc.income_by_cat, acc.income_native))
    if len(acc.income_by_currency) > 1:
        lines.append("  по валютам: " + _cur_line(acc.income_by_currency))
    lines.append(f"  {_account_dual(acc.income_native, cur, acc.income_usd)}")

    net_n = _q(acc.income_native - acc.expense_native)
    net_u = _q(acc.income_usd - acc.expense_usd)
    lines.append(f"Чистый поток: <b>{net_n} {cur}</b> ≈ {net_u} USD")
    return lines


def _account_dual(native: Decimal, currency: str, usd: Decimal) -> str:
    if currency == "USD":
        return f"итого: {native} USD"
    return f"итого: {native} {currency} ≈ {usd} USD"


def _format_footer(stats: PeriodStats) -> list[str]:
    lines: list[str] = []
    if stats.missing_fx:
        lines.append("")
        lines.append(
            "⚠ Нет курса для: "
            + ", ".join(sorted(stats.missing_fx))
            + " — эти суммы не вошли в USD."
        )
    if stats.rates_fetched_at:
        ts = stats.rates_fetched_at
        rate_note = f"курс на {ts:%d.%m.%Y %H:%M} UTC"
        if stats.rub_per_usd is not None:
            rate_note += f" · 1 USD = {stats.rub_per_usd} RUB"
        lines.append(rate_note)
    return lines


def _dual_total(usd: Decimal, rub: Decimal | None) -> str:
    if rub is None:
        return f"итого: {usd} USD"
    return f"итого: {usd} USD ≈ {rub} RUB"


def _cat_lines(by_cat: dict[str, Decimal], total: Decimal) -> list[str]:
    if not by_cat:
        return ["  —"]
    out = []
    for name, amt in sorted(by_cat.items(), key=lambda x: -x[1]):
        pct = (100 * amt / total) if total else ZERO
        out.append(f"  {pct:.1f}% {name}: {amt}")
    return out


def _cur_line(by_cur: dict[str, Decimal]) -> str:
    parts = [f"{c} {a}" for c, a in sorted(by_cur.items())]
    return ", ".join(parts)


def _multi_cur_line(by_cur: dict[str, Decimal]) -> str:
    """Краткий итог: «6808.33 USD, 64017.42 RUB» или «—»."""
    if not by_cur:
        return "—"
    # USD и RUB первыми, остальные по алфавиту
    priority = {"USD": 0, "RUB": 1}
    items = sorted(
        by_cur.items(),
        key=lambda x: (priority.get(x[0], 50), x[0]),
    )
    return ", ".join(f"{_q(amt)} {cur}" for cur, amt in items)


@sync_to_async
def load_rates_map() -> tuple[dict[str, Decimal], datetime | None]:
    from core.models import CurrencyRate

    rows = list(CurrencyRate.objects.all())
    rates = {r.quote.upper(): r.rate for r in rows}
    rates.setdefault("USD", Decimal("1"))
    fetched = max((r.fetched_at for r in rows), default=None)
    return rates, fetched


@sync_to_async
def fetch_transactions(
    user_id: int,
    date_from: date,
    date_to: date,
    *,
    category_id: int | None = None,
    direction: str | None = None,
    account_id: int | None = None,
):
    from core.models import Transaction

    qs = Transaction.objects.filter(
        user_id=user_id,
        occurred_at__gte=date_from,
        occurred_at__lte=date_to,
    ).select_related("category", "account")
    if category_id is not None:
        qs = qs.filter(category_id=category_id)
    if direction is not None:
        qs = qs.filter(direction=direction)
    if account_id is not None:
        qs = qs.filter(account_id=account_id)
    return list(qs.order_by("-occurred_at", "-id"))


@sync_to_async
def category_ids_by_name(user_id: int) -> dict[str, int]:
    """Имя категории → id (видимые + системные, для кнопок детализации)."""
    from core.models import Users
    from core.category_queries import visible_categories_for_user

    user = Users.objects.filter(id=user_id).first()
    if not user:
        return {}
    return {c.name: c.id for c in visible_categories_for_user(user)}


def format_tx_detail_text(
    transactions: list,
    *,
    date_from: date,
    date_to: date,
    category_name: str | None = None,
) -> str:
    """Текстовый список операций для детализации."""
    title = "📋 Детализация"
    if category_name:
        title = f"📋 {category_name}"
    lines = [
        f"<b>{title}</b>",
        f"Период: {date_from:%d.%m.%Y} — {date_to:%d.%m.%Y}",
        f"Операций: {len(transactions)}",
        "",
    ]
    if not transactions:
        lines.append("Нет операций.")
        return "\n".join(lines)

    dir_mark = {"expense": "−", "income": "+", "transfer": "↔"}
    total_native: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for tx in transactions:
        mark = dir_mark.get(tx.direction, "?")
        cur = (tx.currency or "").upper()
        amount = _q(Decimal(tx.amount))
        cat = tx.category.name if tx.category_id else "Без категории"
        desc = (tx.description or "").replace("\n", " ").strip()
        if len(desc) > 80:
            desc = desc[:77] + "…"
        lines.append(
            f"{tx.occurred_at:%d.%m} {mark}<b>{amount} {cur}</b> · {cat}"
        )
        if desc:
            lines.append(f"  <i>{_html_escape(desc)}</i>")
        if tx.direction == "expense":
            total_native[cur] += amount

    if total_native:
        parts = [f"{_q(a)} {c}" for c, a in sorted(total_native.items())]
        lines.append("")
        prefix = "итого по категории: " if category_name else "сумма расходов в списке: "
        lines.append(prefix + ", ".join(parts))

    return "\n".join(lines)


def _html_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


async def stats_for_period(
    user_id: int, date_from: date, date_to: date
) -> PeriodStats:
    txs = await fetch_transactions(user_id, date_from, date_to)
    rates, fetched = await load_rates_map()
    return build_period_stats(
        txs,
        date_from=date_from,
        date_to=date_to,
        rates=rates,
        rates_fetched_at=fetched,
    )
