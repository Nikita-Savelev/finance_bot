from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from math import ceil

from aiogram import types, Dispatcher, F
from aiogram.fsm.context import FSMContext

from connectors import postgres_connector
from bot.components.keyboards import keyboard as kb
from bot.components.utils import with_user
from bot.components.factory import StatsFactory, StatsTxEditFactory
from bot.components.finance.aggregations import (
    category_ids_by_name,
    fetch_transactions,
    format_stats_text,
    stats_for_period,
)
from core.models import Users

PAGE_SIZE = 15

DIR_LABEL = {
    "expense": "расход",
    "income": "доход",
    "transfer": "перевод",
}


def _month_bounds(offset: int = 0) -> tuple[date, date]:
    today = date.today()
    year, month = today.year, today.month
    month += offset
    while month < 1:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    return start, end


def _clamp_offset(offset: int) -> tuple[int, date, date]:
    today = date.today()
    date_from, date_to = _month_bounds(offset)
    if (date_from.year, date_from.month) > (today.year, today.month):
        offset = 0
        date_from, date_to = _month_bounds(0)
    return offset, date_from, date_to


def _parse_date(raw: str) -> date | None:
    s = (raw or "").strip()
    for fmt in ("%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _parse_amount(raw: str) -> Decimal | None:
    s = (raw or "").strip().replace(" ", "").replace("\xa0", "").replace(",", ".")
    if not s:
        return None
    try:
        val = Decimal(s)
    except (InvalidOperation, ValueError):
        return None
    if val <= 0:
        return None
    return val.quantize(Decimal("0.01"))


def _format_tx(tx) -> str:
    mark = {"expense": "−", "income": "+", "transfer": "↔"}.get(tx.direction, "")
    cat = tx.category.name if tx.category_id else "без категории"
    lines = [
        f"<b>{DIR_LABEL.get(tx.direction, tx.direction).capitalize()}</b>",
        f"{mark}{tx.amount} {tx.currency}",
        f"Счёт: {tx.account.name}",
        f"Категория: {cat}",
        f"Дата: {tx.occurred_at:%d.%m.%Y}",
    ]
    if tx.description:
        lines.append(f"Описание: {tx.description}")
    return "\n".join(lines)


async def _edit_or_answer(event, text: str, reply_markup=None):
    chunks = _split_html(text, 3500)
    if isinstance(event, types.CallbackQuery):
        try:
            await event.message.edit_text(
                chunks[0],
                reply_markup=reply_markup if len(chunks) == 1 else None,
                parse_mode="HTML",
            )
        except Exception:
            await event.message.answer(chunks[0], parse_mode="HTML")
        for chunk in chunks[1:]:
            await event.message.answer(chunk, parse_mode="HTML")
        if len(chunks) > 1 and reply_markup:
            await event.message.answer("—", reply_markup=reply_markup)
        await event.answer()
    else:
        await event.answer(chunks[0], parse_mode="HTML")
        for chunk in chunks[1:]:
            await event.answer(chunk, parse_mode="HTML")
        if reply_markup:
            await event.answer("—", reply_markup=reply_markup)


def _split_html(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]
    parts = []
    buf = []
    size = 0
    for line in text.split("\n"):
        add = len(line) + 1
        if size + add > limit and buf:
            parts.append("\n".join(buf))
            buf = [line]
            size = add
        else:
            buf.append(line)
            size += add
    if buf:
        parts.append("\n".join(buf))
    return parts or [text]


async def _show_month_stats(event, pg_user: Users, offset: int):
    today = date.today()
    date_from, date_to = _month_bounds(offset)
    answer_callback = True
    if (date_from.year, date_from.month) > (today.year, today.month):
        offset = 0
        date_from, date_to = _month_bounds(0)
        if isinstance(event, types.CallbackQuery):
            await event.answer("Это ещё будущий месяц", show_alert=True)
            answer_callback = False

    stats = await stats_for_period(pg_user.id, date_from, date_to)
    text = format_stats_text(stats)
    markup = await kb.stats_nav_kb(offset, accounts=stats.by_account)
    if isinstance(event, types.CallbackQuery) and not answer_callback:
        try:
            await event.message.edit_text(
                text, reply_markup=markup, parse_mode="HTML"
            )
        except Exception:
            await event.message.answer(text, reply_markup=markup, parse_mode="HTML")
        return
    await _edit_or_answer(event, text, markup)


async def _save_detail_ctx(
    state: FSMContext,
    *,
    offset: int,
    page: int,
    cat_id: int | None,
    account_id: int = 0,
    direction: str | None = None,
):
    await state.update_data(
        stats_detail={
            "offset": offset,
            "page": page,
            "cat_id": cat_id,
            "account_id": account_id,
            "direction": direction,
        }
    )


async def _show_detail_list(
    event,
    state: FSMContext,
    pg_user: Users,
    *,
    offset: int,
    page: int = 0,
    category_id: int | None = None,
    account_id: int = 0,
    direction: str | None = None,
):
    offset, date_from, date_to = _clamp_offset(offset)
    stats = await stats_for_period(pg_user.id, date_from, date_to)
    cat_map = await category_ids_by_name(pg_user.id)
    name_by_id = {v: k for k, v in cat_map.items()}
    acc_id = int(account_id or 0)
    filter_acc = acc_id if acc_id > 0 else None

    fetch_kwargs = {}
    if filter_acc is not None:
        fetch_kwargs["account_id"] = filter_acc
    if category_id is not None:
        fetch_kwargs["category_id"] = category_id
    if direction is not None:
        fetch_kwargs["direction"] = direction

    all_txs = await fetch_transactions(pg_user.id, date_from, date_to, **fetch_kwargs)
    cat_name = name_by_id.get(category_id) if category_id is not None else None

    total = len(all_txs)
    page_count = max(1, ceil(total / PAGE_SIZE)) if total else 1
    page = max(0, min(page, page_count - 1))
    chunk = all_txs[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]

    await _save_detail_ctx(
        state,
        offset=offset,
        page=page,
        cat_id=category_id,
        account_id=acc_id,
        direction=direction,
    )

    if filter_acc is not None:
        acc = next((a for a in stats.by_account if a.account_id == filter_acc), None)
        scope = acc.account_name if acc else f"Счёт #{filter_acc}"
        text = format_stats_text(stats, account_id=filter_acc)
    else:
        scope = "Все счета"
        text = format_stats_text(stats, all_accounts=True)

    filter_bits = [scope]
    if direction == "income":
        filter_bits.append("Доходы")
    elif direction == "expense":
        filter_bits.append("Расходы")
    if cat_name:
        filter_bits.append(cat_name)
    filter_bits.append(f"{total} оп.")
    filter_bits.append(f"стр. {page + 1}/{page_count}")
    text += f"\n\n<i>{' · '.join(filter_bits)}</i>"

    markup = await kb.stats_detail_kb(
        offset=offset,
        account_id=acc_id,
        page=page,
        page_count=page_count,
        transactions=chunk,
        active_cat_id=category_id,
        active_cat_label=cat_name,
        direction=direction,
    )
    await _edit_or_answer(event, text, markup)


@with_user
async def stats_cats_menu(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    """stats:cats:{offset}:{account_id}"""
    if not pg_user:
        await callback.answer()
        return
    parts = callback.data.split(":")
    offset = int(parts[2])
    acc_id = int(parts[3]) if len(parts) > 3 else 0
    offset, date_from, date_to = _clamp_offset(offset)
    stats = await stats_for_period(pg_user.id, date_from, date_to)
    cat_map = await category_ids_by_name(pg_user.id)
    data = await state.get_data()
    ctx = data.get("stats_detail") or {}
    active = ctx.get("cat_id")

    filter_acc = acc_id if acc_id > 0 else None
    if filter_acc is not None:
        acc = next((a for a in stats.by_account if a.account_id == filter_acc), None)
        expense_by_cat = acc.expense_by_cat if acc else {}
        expense_total = acc.expense_native if acc else 0
        income_by_cat = acc.income_by_cat if acc else {}
        income_total = acc.income_native if acc else 0
        text = format_stats_text(stats, account_id=filter_acc)
    else:
        expense_by_cat = stats.expense_by_cat
        expense_total = stats.expense_usd
        income_by_cat = stats.income_by_cat
        income_total = stats.income_usd
        text = format_stats_text(stats, all_accounts=True)
    text += "\n\n<b>Выберите категорию:</b>"
    markup = await kb.stats_cats_kb(
        offset=offset,
        account_id=acc_id,
        expense_by_cat=expense_by_cat,
        expense_usd=expense_total,
        income_by_cat=income_by_cat,
        income_usd=income_total,
        cat_id_by_name=cat_map,
        active_cat_id=active,
    )
    await _edit_or_answer(callback, text, markup)


async def _restore_detail_from_state(
    event, state: FSMContext, pg_user: Users
):
    data = await state.get_data()
    ctx = data.get("stats_detail") or {
        "offset": 0,
        "page": 0,
        "cat_id": None,
        "account_id": 0,
        "direction": None,
    }
    await state.set_state(None)
    await _show_detail_list(
        event,
        state,
        pg_user,
        offset=int(ctx.get("offset", 0)),
        page=int(ctx.get("page", 0)),
        category_id=ctx.get("cat_id"),
        account_id=int(ctx.get("account_id") or 0),
        direction=ctx.get("direction"),
    )


@with_user
async def open_stats(callback: types.CallbackQuery, state: FSMContext, pg_user: Users):
    await state.clear()
    if not pg_user:
        await callback.answer("Сначала регистрация", show_alert=True)
        return
    await _show_month_stats(callback, pg_user, 0)


@with_user
async def stats_month(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    if not pg_user:
        await callback.answer()
        return
    await state.clear()
    offset = int(callback.data.split(":")[-1])
    await _show_month_stats(callback, pg_user, offset)


@with_user
async def stats_detail(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    """stats:detail:{offset}:{account_id}:{page}  (account_id=0 — все счета)"""
    if not pg_user:
        await callback.answer()
        return
    parts = callback.data.split(":")
    offset = int(parts[2])
    if len(parts) >= 5:
        account_id = int(parts[3])
        page = int(parts[4])
    else:
        # старый формат stats:detail:{offset}:{page}
        account_id = 0
        page = int(parts[3]) if len(parts) > 3 else 0
    await _show_detail_list(
        callback,
        state,
        pg_user,
        offset=offset,
        page=page,
        category_id=None,
        account_id=account_id,
        direction=None,
    )


@with_user
async def stats_detail_income(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    """stats:din:{offset}:{account_id}:{page} — только доходы"""
    if not pg_user:
        await callback.answer()
        return
    parts = callback.data.split(":")
    offset = int(parts[2])
    account_id = int(parts[3]) if len(parts) > 3 else 0
    page = int(parts[4]) if len(parts) > 4 else 0
    await _show_detail_list(
        callback,
        state,
        pg_user,
        offset=offset,
        page=page,
        category_id=None,
        account_id=account_id,
        direction="income",
    )


@with_user
async def stats_detail_category(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    """stats:dcat:{offset}:{account_id}:{cat_id}:{page}"""
    if not pg_user:
        await callback.answer()
        return
    parts = callback.data.split(":")
    offset = int(parts[2])
    if len(parts) >= 6:
        account_id = int(parts[3])
        cat_id = int(parts[4])
        page = int(parts[5]) if len(parts) > 5 else 0
    else:
        # старый формат stats:dcat:{offset}:{cat_id}:{page}
        account_id = 0
        cat_id = int(parts[3])
        page = int(parts[4]) if len(parts) > 4 else 0
    await _show_detail_list(
        callback,
        state,
        pg_user,
        offset=offset,
        page=page,
        category_id=cat_id,
        account_id=account_id,
        direction=None,
    )


@with_user
async def stats_noop(callback: types.CallbackQuery, state: FSMContext, pg_user: Users):
    await callback.answer()


@with_user
async def stats_tx_open(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    if not pg_user:
        await callback.answer()
        return
    await state.set_state(None)
    tx_id = int(callback.data.split(":")[-1])
    tx = await postgres_connector.get_transaction(pg_user.id, tx_id)
    if not tx:
        await callback.answer("Не найдено", show_alert=True)
        return
    text = f"<b>Операция</b>\n\n{_format_tx(tx)}"
    await _edit_or_answer(callback, text, await kb.stats_tx_card_kb(tx.id))


@with_user
async def stats_tx_back(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    if not pg_user:
        await callback.answer()
        return
    await _restore_detail_from_state(callback, state, pg_user)


@with_user
async def stats_tx_del_ask(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    if not pg_user:
        await callback.answer()
        return
    tx_id = int(callback.data.split(":")[-1])
    tx = await postgres_connector.get_transaction(pg_user.id, tx_id)
    if not tx:
        await callback.answer("Не найдено", show_alert=True)
        return
    text = f"Удалить эту операцию?\n\n{_format_tx(tx)}"
    await _edit_or_answer(
        callback, text, await kb.stats_tx_delete_confirm_kb(tx.id)
    )


@with_user
async def stats_tx_del_ok(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    if not pg_user:
        await callback.answer()
        return
    tx_id = int(callback.data.split(":")[-1])
    ok = await postgres_connector.delete_transaction(pg_user.id, tx_id)
    await callback.answer("Удалено" if ok else "Ошибка")
    await _restore_detail_from_state(callback, state, pg_user)


@with_user
async def stats_tx_edit_cat(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    if not pg_user:
        await callback.answer()
        return
    tx_id = int(callback.data.split(":")[-1])
    tx = await postgres_connector.get_transaction(pg_user.id, tx_id)
    if not tx:
        await callback.answer("Не найдено", show_alert=True)
        return
    cats = await postgres_connector.list_visible_categories(
        pg_user.id, kind=tx.direction
    )
    await _edit_or_answer(
        callback,
        f"Выберите категорию:\n\n{_format_tx(tx)}",
        await kb.stats_tx_edit_cats_kb(cats, tx_id, page=0),
    )


@with_user
async def stats_tx_edit_cat_page(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    if not pg_user:
        await callback.answer()
        return
    # stats:txcatpage:{tx_id}:{page}
    parts = callback.data.split(":")
    tx_id = int(parts[2])
    page = int(parts[3])
    tx = await postgres_connector.get_transaction(pg_user.id, tx_id)
    if not tx:
        await callback.answer("Не найдено", show_alert=True)
        return
    cats = await postgres_connector.list_visible_categories(
        pg_user.id, kind=tx.direction
    )
    await _edit_or_answer(
        callback,
        f"Выберите категорию:\n\n{_format_tx(tx)}",
        await kb.stats_tx_edit_cats_kb(cats, tx_id, page=page),
    )


@with_user
async def stats_tx_set_cat(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    if not pg_user:
        await callback.answer()
        return
    # stats:txsetcat:{tx_id}:{cat_id}
    parts = callback.data.split(":")
    tx_id = int(parts[2])
    cat_id = int(parts[3])
    cat, hidden = await postgres_connector.get_category_for_user(pg_user.id, cat_id)
    if not cat or hidden:
        await callback.answer("Категория недоступна", show_alert=True)
        return
    tx = await postgres_connector.update_transaction(
        pg_user.id, tx_id, category_id=cat.id
    )
    if not tx:
        await callback.answer("Ошибка", show_alert=True)
        return

    await postgres_connector.upsert_category_preference(
        pg_user.id, tx.description, cat.id
    )
    similar = await postgres_connector.count_similar_transactions_in_month(
        pg_user.id,
        tx.description,
        year=tx.occurred_at.year,
        month=tx.occurred_at.month,
        exclude_tx_id=tx.id,
        category_id=cat.id,
    )
    await callback.answer("Категория обновлена")
    text = (
        f"<b>Операция</b>\n\n{_format_tx(tx)}\n\n"
        f"Правило сохранено для похожих описаний."
    )
    if similar:
        text += (
            f"\nНашёл ещё <b>{similar}</b> с тем же описанием за "
            f"{tx.occurred_at:%m.%Y}. Применить?"
        )
        markup = await kb.stats_tx_cat_apply_kb(tx.id, cat.id, similar)
    else:
        markup = await kb.stats_tx_card_kb(tx.id)
    await _edit_or_answer(callback, text, markup)


@with_user
async def stats_tx_cat_apply_all(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    """stats:txcatall:{tx_id}:{cat_id}"""
    if not pg_user:
        await callback.answer()
        return
    parts = callback.data.split(":")
    tx_id = int(parts[2])
    cat_id = int(parts[3])
    tx = await postgres_connector.get_transaction(pg_user.id, tx_id)
    cat, hidden = await postgres_connector.get_category_for_user(pg_user.id, cat_id)
    if not tx or not cat or hidden:
        await callback.answer("Не найдено", show_alert=True)
        return
    n = await postgres_connector.apply_category_to_similar_in_month(
        pg_user.id,
        tx.description,
        cat.id,
        year=tx.occurred_at.year,
        month=tx.occurred_at.month,
        exclude_tx_id=tx.id,
    )
    await postgres_connector.upsert_category_preference(
        pg_user.id, tx.description, cat.id
    )
    await callback.answer(f"Обновлено: {n}")
    text = (
        f"<b>Операция</b>\n\n{_format_tx(tx)}\n\n"
        f"Категория <b>{cat.name}</b> применена к ещё {n} операциям за месяц."
    )
    await _edit_or_answer(callback, text, await kb.stats_tx_card_kb(tx.id))


@with_user
async def stats_tx_cat_apply_one(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    """stats:txcatone:{tx_id}"""
    if not pg_user:
        await callback.answer()
        return
    tx_id = int(callback.data.split(":")[-1])
    tx = await postgres_connector.get_transaction(pg_user.id, tx_id)
    if not tx:
        await callback.answer("Не найдено", show_alert=True)
        return
    await callback.answer()
    text = f"<b>Операция</b>\n\n{_format_tx(tx)}"
    await _edit_or_answer(callback, text, await kb.stats_tx_card_kb(tx.id))


@with_user
async def stats_tx_edit_amt(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    if not pg_user:
        await callback.answer()
        return
    tx_id = int(callback.data.split(":")[-1])
    tx = await postgres_connector.get_transaction(pg_user.id, tx_id)
    if not tx:
        await callback.answer("Не найдено", show_alert=True)
        return
    await state.update_data(edit_tx_id=tx_id)
    await state.set_state(StatsTxEditFactory.amount)
    await _edit_or_answer(
        callback,
        f"Текущая сумма: <b>{tx.amount} {tx.currency}</b>\n\n"
        "Введите новую сумму:",
        await kb.stats_tx_edit_cancel_kb(tx_id),
    )


@with_user
async def stats_tx_edit_date(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    if not pg_user:
        await callback.answer()
        return
    tx_id = int(callback.data.split(":")[-1])
    tx = await postgres_connector.get_transaction(pg_user.id, tx_id)
    if not tx:
        await callback.answer("Не найдено", show_alert=True)
        return
    await state.update_data(edit_tx_id=tx_id)
    await state.set_state(StatsTxEditFactory.date)
    await _edit_or_answer(
        callback,
        f"Текущая дата: <b>{tx.occurred_at:%d.%m.%Y}</b>\n\n"
        "Введите дату (ДД.ММ.ГГГГ):",
        await kb.stats_tx_edit_cancel_kb(tx_id),
    )


@with_user
async def stats_tx_edit_desc(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    if not pg_user:
        await callback.answer()
        return
    tx_id = int(callback.data.split(":")[-1])
    tx = await postgres_connector.get_transaction(pg_user.id, tx_id)
    if not tx:
        await callback.answer("Не найдено", show_alert=True)
        return
    await state.update_data(edit_tx_id=tx_id)
    await state.set_state(StatsTxEditFactory.description)
    cur = tx.description or "—"
    await _edit_or_answer(
        callback,
        f"Текущее описание:\n<i>{cur}</i>\n\n"
        "Введите новое описание (или «-» чтобы очистить):",
        await kb.stats_tx_edit_cancel_kb(tx_id),
    )


@with_user
async def stats_tx_enter_amount(
    message: types.Message, state: FSMContext, pg_user: Users
):
    if not pg_user:
        return
    data = await state.get_data()
    tx_id = data.get("edit_tx_id")
    amount = _parse_amount(message.text or "")
    if not tx_id or amount is None:
        await message.answer("Сумма должна быть числом > 0")
        return
    tx = await postgres_connector.update_transaction(
        pg_user.id, tx_id, amount=amount
    )
    await state.set_state(None)
    if not tx:
        await message.answer("Ошибка сохранения")
        return
    await message.answer(
        f"Сумма обновлена.\n\n{_format_tx(tx)}",
        reply_markup=await kb.stats_tx_card_kb(tx.id),
        parse_mode="HTML",
    )


@with_user
async def stats_tx_enter_date(
    message: types.Message, state: FSMContext, pg_user: Users
):
    if not pg_user:
        return
    data = await state.get_data()
    tx_id = data.get("edit_tx_id")
    d = _parse_date(message.text or "")
    if not tx_id or not d:
        await message.answer("Формат: ДД.ММ.ГГГГ")
        return
    tx = await postgres_connector.update_transaction(
        pg_user.id, tx_id, occurred_at=d
    )
    await state.set_state(None)
    if not tx:
        await message.answer("Ошибка сохранения")
        return
    await message.answer(
        f"Дата обновлена.\n\n{_format_tx(tx)}",
        reply_markup=await kb.stats_tx_card_kb(tx.id),
        parse_mode="HTML",
    )


@with_user
async def stats_tx_enter_desc(
    message: types.Message, state: FSMContext, pg_user: Users
):
    if not pg_user:
        return
    data = await state.get_data()
    tx_id = data.get("edit_tx_id")
    if not tx_id:
        await message.answer("Сессия сброшена")
        await state.clear()
        return
    raw = (message.text or "").strip()
    desc = None if raw in {"-", "—", ""} else raw
    tx = await postgres_connector.update_transaction(
        pg_user.id, tx_id, description=desc
    )
    await state.set_state(None)
    if not tx:
        await message.answer("Ошибка сохранения")
        return
    await message.answer(
        f"Описание обновлено.\n\n{_format_tx(tx)}",
        reply_markup=await kb.stats_tx_card_kb(tx.id),
        parse_mode="HTML",
    )


@with_user
async def stats_custom_start(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    if not pg_user:
        await callback.answer()
        return
    await state.set_state(StatsFactory.date_from)
    await _edit_or_answer(
        callback,
        "Введите <b>начало</b> периода (ДД.ММ.ГГГГ):",
        await kb.stats_cancel_kb(),
    )


@with_user
async def stats_date_from(message: types.Message, state: FSMContext, pg_user: Users):
    if not pg_user:
        return
    d = _parse_date(message.text or "")
    if not d:
        await message.answer("Формат: ДД.ММ.ГГГГ")
        return
    await state.update_data(stats_from=d.isoformat())
    await state.set_state(StatsFactory.date_to)
    await message.answer(
        f"С: <b>{d:%d.%m.%Y}</b>\n\nВведите <b>конец</b> периода (ДД.ММ.ГГГГ):",
        reply_markup=await kb.stats_cancel_kb(),
        parse_mode="HTML",
    )


@with_user
async def stats_date_to(message: types.Message, state: FSMContext, pg_user: Users):
    if not pg_user:
        return
    d_to = _parse_date(message.text or "")
    if not d_to:
        await message.answer("Формат: ДД.ММ.ГГГГ")
        return
    data = await state.get_data()
    d_from = date.fromisoformat(data["stats_from"])
    await state.clear()
    if d_to < d_from:
        d_from, d_to = d_to, d_from
    stats = await stats_for_period(pg_user.id, d_from, d_to)
    text = format_stats_text(stats)
    await _edit_or_answer(
        message, text, await kb.stats_nav_kb(0, accounts=stats.by_account)
    )


def register_handlers(dp: Dispatcher):
    dp.callback_query.register(open_stats, F.data == "menu:stats")
    dp.callback_query.register(stats_month, F.data.startswith("stats:month:"))
    dp.callback_query.register(stats_detail, F.data.startswith("stats:detail:"))
    dp.callback_query.register(stats_detail_income, F.data.startswith("stats:din:"))
    dp.callback_query.register(stats_detail_category, F.data.startswith("stats:dcat:"))
    dp.callback_query.register(stats_cats_menu, F.data.startswith("stats:cats:"))
    dp.callback_query.register(stats_noop, F.data == "stats:noop")
    dp.callback_query.register(stats_tx_back, F.data == "stats:txback")
    dp.callback_query.register(stats_tx_open, F.data.startswith("stats:tx:"))
    dp.callback_query.register(stats_tx_del_ok, F.data.startswith("stats:txdelok:"))
    dp.callback_query.register(stats_tx_del_ask, F.data.startswith("stats:txdel:"))
    dp.callback_query.register(stats_tx_set_cat, F.data.startswith("stats:txsetcat:"))
    dp.callback_query.register(
        stats_tx_cat_apply_all, F.data.startswith("stats:txcatall:")
    )
    dp.callback_query.register(
        stats_tx_cat_apply_one, F.data.startswith("stats:txcatone:")
    )
    dp.callback_query.register(
        stats_tx_edit_cat_page, F.data.startswith("stats:txcatpage:")
    )
    dp.callback_query.register(
        stats_tx_edit_cat, F.data.startswith("stats:txedit:cat:")
    )
    dp.callback_query.register(
        stats_tx_edit_amt, F.data.startswith("stats:txedit:amt:")
    )
    dp.callback_query.register(
        stats_tx_edit_date, F.data.startswith("stats:txedit:date:")
    )
    dp.callback_query.register(
        stats_tx_edit_desc, F.data.startswith("stats:txedit:desc:")
    )
    dp.callback_query.register(stats_custom_start, F.data == "stats:custom")
    dp.message.register(stats_date_from, StatsFactory.date_from, F.text)
    dp.message.register(stats_date_to, StatsFactory.date_to, F.text)
    dp.message.register(stats_tx_enter_amount, StatsTxEditFactory.amount, F.text)
    dp.message.register(stats_tx_enter_date, StatsTxEditFactory.date, F.text)
    dp.message.register(stats_tx_enter_desc, StatsTxEditFactory.description, F.text)
