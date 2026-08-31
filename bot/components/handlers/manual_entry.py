from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from aiogram import types, Dispatcher, F
from aiogram.fsm.context import FSMContext

from connectors import postgres_connector
from bot.components.keyboards import keyboard as kb
from bot.components.utils import with_user
from bot.components.factory import ManualTxFactory
from core.models import Users, TransactionSource


DIR_LABEL = {
    "expense": "расход",
    "income": "доход",
    "transfer": "перевод",
}


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


def _parse_date(raw: str) -> date | None:
    s = (raw or "").strip()
    for fmt in ("%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


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
        lines.append(f"Комментарий: {tx.description}")
    return "\n".join(lines)


async def _edit_or_answer(event, text: str, reply_markup=None):
    if isinstance(event, types.CallbackQuery):
        try:
            await event.message.edit_text(
                text, reply_markup=reply_markup, parse_mode="HTML"
            )
        except Exception:
            await event.message.answer(
                text, reply_markup=reply_markup, parse_mode="HTML"
            )
        await event.answer()
    else:
        await event.answer(text, reply_markup=reply_markup, parse_mode="HTML")


@with_user
async def start_add(callback: types.CallbackQuery, state: FSMContext, pg_user: Users):
    await state.clear()
    if not pg_user:
        await callback.answer("Сначала регистрация", show_alert=True)
        return
    accounts = await postgres_connector.list_accounts(pg_user.id, active_only=True)
    if not accounts:
        text = (
            "<b>Добавить операцию</b>\n\n"
            "Сначала создайте счёт в разделе «Счета»."
        )
        await _edit_or_answer(callback, text, await kb.back_to_menu_kb())
        return
    await state.update_data(tx_draft={})
    await _edit_or_answer(
        callback,
        "<b>Добавить операцию</b>\n\nВыберите счёт:",
        await kb.tx_pick_account_kb(accounts),
    )


@with_user
async def pick_account(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    if not pg_user:
        await callback.answer()
        return
    account_id = int(callback.data.split(":")[-1])
    acc = await postgres_connector.get_account(pg_user.id, account_id)
    if not acc or not acc.is_active:
        await callback.answer("Счёт недоступен", show_alert=True)
        return
    data = await state.get_data()
    draft = data.get("tx_draft") or {}
    draft["account_id"] = acc.id
    draft["currency"] = acc.currency
    draft["account_name"] = acc.name
    await state.update_data(tx_draft=draft)
    await _edit_or_answer(
        callback,
        f"Счёт: <b>{acc.name}</b> ({acc.currency})\n\nТип операции:",
        await kb.tx_direction_kb(),
    )


@with_user
async def pick_direction(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    if not pg_user:
        await callback.answer()
        return
    direction = callback.data.split(":")[-1]
    if direction not in DIR_LABEL:
        await callback.answer()
        return
    data = await state.get_data()
    draft = data.get("tx_draft") or {}
    draft["direction"] = direction
    await state.update_data(tx_draft=draft)
    await state.set_state(ManualTxFactory.amount)
    await _edit_or_answer(
        callback,
        f"Тип: <b>{DIR_LABEL[direction]}</b>\n\nВведите сумму (в {draft.get('currency', '')}):",
        await kb.tx_cancel_kb(),
    )


@with_user
async def enter_amount(message: types.Message, state: FSMContext, pg_user: Users):
    if not pg_user:
        return
    amount = _parse_amount(message.text or "")
    if amount is None:
        await message.answer("Введите положительную сумму, например: 1200.50")
        return
    data = await state.get_data()
    draft = data.get("tx_draft") or {}
    draft["amount"] = str(amount)
    direction = draft.get("direction", "expense")
    await state.update_data(tx_draft=draft)
    await state.set_state(None)
    cats = await postgres_connector.list_visible_categories(pg_user.id, kind=direction)
    if not cats:
        await message.answer(
            "Нет категорий для этого типа. Добавьте категории или проверьте сид.",
            reply_markup=await kb.back_to_menu_kb(),
        )
        await state.clear()
        return
    await state.update_data(tx_cat_page=0, tx_cats_kind=direction)
    await message.answer(
        f"Сумма: <b>{amount} {draft.get('currency')}</b>\n\nВыберите категорию:",
        reply_markup=await kb.tx_categories_kb(cats, page=0),
        parse_mode="HTML",
    )


@with_user
async def cat_page(callback: types.CallbackQuery, state: FSMContext, pg_user: Users):
    if not pg_user:
        await callback.answer()
        return
    page = int(callback.data.split(":")[-1])
    data = await state.get_data()
    kind = data.get("tx_cats_kind") or (data.get("tx_draft") or {}).get("direction")
    cats = await postgres_connector.list_visible_categories(pg_user.id, kind=kind)
    await state.update_data(tx_cat_page=page)
    await _edit_or_answer(
        callback,
        "Выберите категорию:",
        await kb.tx_categories_kb(cats, page=page),
    )


@with_user
async def pick_category(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    if not pg_user:
        await callback.answer()
        return
    cat_id = int(callback.data.split(":")[-1])
    data = await state.get_data()
    draft = data.get("tx_draft") or {}
    draft["category_id"] = cat_id
    await state.update_data(tx_draft=draft)
    await state.set_state(ManualTxFactory.date)
    await _edit_or_answer(
        callback,
        "Дата операции — выберите или введите в формате ДД.ММ.ГГГГ:",
        await kb.tx_date_kb(),
    )


@with_user
async def pick_date_btn(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    if not pg_user:
        await callback.answer()
        return
    key = callback.data.split(":")[-1]
    if key == "today":
        d = date.today()
    elif key == "yesterday":
        d = date.today() - timedelta(days=1)
    else:
        await callback.answer()
        return
    await _after_date(callback, state, pg_user, d)


@with_user
async def enter_date(message: types.Message, state: FSMContext, pg_user: Users):
    if not pg_user:
        return
    d = _parse_date(message.text or "")
    if not d:
        await message.answer("Формат даты: ДД.ММ.ГГГГ")
        return
    await _after_date(message, state, pg_user, d)


async def _after_date(event, state: FSMContext, pg_user: Users, d: date):
    data = await state.get_data()
    draft = data.get("tx_draft") or {}
    draft["occurred_at"] = d.isoformat()
    await state.update_data(tx_draft=draft)
    await state.set_state(ManualTxFactory.description)
    await _edit_or_answer(
        event,
        f"Дата: <b>{d:%d.%m.%Y}</b>\n\nКомментарий (или «Без комментария»):",
        await kb.tx_skip_desc_kb(),
    )


@with_user
async def skip_desc(callback: types.CallbackQuery, state: FSMContext, pg_user: Users):
    if not pg_user:
        await callback.answer()
        return
    await _save_tx(callback, state, pg_user, description=None)


@with_user
async def enter_desc(message: types.Message, state: FSMContext, pg_user: Users):
    if not pg_user:
        return
    desc = (message.text or "").strip() or None
    await _save_tx(message, state, pg_user, description=desc)


async def _save_tx(event, state: FSMContext, pg_user: Users, description: str | None):
    data = await state.get_data()
    draft = data.get("tx_draft") or {}
    await state.clear()
    required = ("account_id", "direction", "amount", "currency", "occurred_at")
    if any(k not in draft for k in required):
        await _edit_or_answer(
            event,
            "Черновик операции потерян. Начните снова.",
            await kb.back_to_menu_kb(),
        )
        return
    tx = await postgres_connector.create_transaction(
        pg_user.id,
        account_id=draft["account_id"],
        category_id=draft.get("category_id"),
        occurred_at=date.fromisoformat(draft["occurred_at"]),
        amount=Decimal(draft["amount"]),
        currency=draft["currency"],
        direction=draft["direction"],
        description=description,
        source=TransactionSource.MANUAL,
    )
    text = f"Сохранено.\n\n{_format_tx(tx)}"
    await _edit_or_answer(event, text, await kb.back_to_menu_kb())


@with_user
async def start_delete(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    await state.clear()
    if not pg_user:
        await callback.answer("Сначала регистрация", show_alert=True)
        return
    txs = await postgres_connector.list_recent_transactions(pg_user.id, limit=15)
    if not txs:
        await _edit_or_answer(
            callback,
            "<b>Удалить операцию</b>\n\nПока нет операций.",
            await kb.back_to_menu_kb(),
        )
        return
    await _edit_or_answer(
        callback,
        "<b>Удалить операцию</b>\n\nПоследние операции — выберите:",
        await kb.tx_delete_list_kb(txs),
    )


@with_user
async def delete_view(
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
    await _edit_or_answer(callback, text, await kb.tx_delete_confirm_kb(tx.id))


@with_user
async def delete_ok(callback: types.CallbackQuery, state: FSMContext, pg_user: Users):
    if not pg_user:
        await callback.answer()
        return
    tx_id = int(callback.data.split(":")[-1])
    ok = await postgres_connector.delete_transaction(pg_user.id, tx_id)
    await callback.answer("Удалено" if ok else "Ошибка")
    await start_delete(callback, state, pg_user)


def register_handlers(dp: Dispatcher):
    dp.callback_query.register(start_add, F.data == "menu:add_tx")
    dp.callback_query.register(pick_account, F.data.startswith("tx:acc:"))
    dp.callback_query.register(pick_direction, F.data.startswith("tx:dir:"))
    dp.callback_query.register(cat_page, F.data.startswith("tx:catpage:"))
    dp.callback_query.register(pick_category, F.data.startswith("tx:pickcat:"))
    dp.callback_query.register(pick_date_btn, F.data.startswith("tx:date:"))
    dp.callback_query.register(skip_desc, F.data == "tx:desc:skip")

    dp.callback_query.register(start_delete, F.data == "menu:del_tx")
    dp.callback_query.register(delete_view, F.data.startswith("tx:delview:"))
    dp.callback_query.register(delete_ok, F.data.startswith("tx:del_ok:"))

    dp.message.register(enter_amount, ManualTxFactory.amount, F.text)
    dp.message.register(enter_date, ManualTxFactory.date, F.text)
    dp.message.register(enter_desc, ManualTxFactory.description, F.text)
