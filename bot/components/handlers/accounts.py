from __future__ import annotations

import re

from aiogram import types, Dispatcher, F
from aiogram.fsm.context import FSMContext
from asgiref.sync import sync_to_async

from connectors import postgres_connector
from bot.components.keyboards import keyboard as kb
from bot.components.utils import with_user
from bot.components.factory import AccountFactory
from core.models import Users, Transaction


def _norm_currency(raw: str) -> str | None:
    code = (raw or "").strip().upper().replace("₽", "RUB").replace("$", "USD")
    if not code or len(code) > 16:
        return None
    if not re.fullmatch(r"[A-Z0-9]{2,16}", code):
        return None
    return code


def _format_account_card(acc) -> str:
    lines = [
        f"<b>💳 {acc.name}</b>",
        f"Валюта: <code>{acc.currency}</code>",
    ]
    if acc.bank_label:
        lines.append(f"Банк: {acc.bank_label}")
    if acc.country:
        lines.append(f"Страна: {acc.country}")
    lines.append(f"Статус: {'активен' if acc.is_active else 'скрыт'}")
    if acc.notes:
        lines.append(f"Заметки: {acc.notes}")
    return "\n".join(lines)


async def _edit_or_answer(event, text: str, reply_markup=None):
    parse = "HTML"
    if isinstance(event, types.CallbackQuery):
        try:
            await event.message.edit_text(
                text, reply_markup=reply_markup, parse_mode=parse
            )
        except Exception:
            await event.message.answer(
                text, reply_markup=reply_markup, parse_mode=parse
            )
        await event.answer()
    else:
        await event.answer(text, reply_markup=reply_markup, parse_mode=parse)


@sync_to_async
def _can_delete(account_id: int) -> bool:
    return not Transaction.objects.filter(account_id=account_id).exists()


@with_user
async def open_accounts(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    await state.clear()
    if not pg_user:
        await callback.answer("Сначала регистрация", show_alert=True)
        return
    accounts = await postgres_connector.list_accounts(pg_user.id, active_only=False)
    active = [a for a in accounts if a.is_active]
    hidden = [a for a in accounts if not a.is_active]
    if not accounts:
        text = (
            "<b>💳 Счета</b>\n\n"
            "Пока нет счетов. Создайте первый — без него нельзя добавлять операции."
        )
    else:
        text = f"<b>💳 Счета</b>\n\nАктивных: {len(active)}"
        if hidden:
            text += f", скрытых: {len(hidden)}"
        text += "\nВыберите счёт или создайте новый."
    keyboard = await kb.accounts_list_kb(active + hidden)
    await _edit_or_answer(callback, text, keyboard)


@with_user
async def view_account(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    await state.clear()
    if not pg_user:
        await callback.answer("Сначала регистрация", show_alert=True)
        return
    account_id = int(callback.data.split(":")[-1])
    acc = await postgres_connector.get_account(pg_user.id, account_id)
    if not acc:
        await callback.answer("Счёт не найден", show_alert=True)
        return
    can_delete = await _can_delete(acc.id)
    keyboard = await kb.account_card_kb(
        acc.id, is_active=acc.is_active, can_delete=can_delete
    )
    await _edit_or_answer(callback, _format_account_card(acc), keyboard)


@with_user
async def start_add_account(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    if not pg_user:
        await callback.answer("Сначала регистрация", show_alert=True)
        return
    await state.set_state(AccountFactory.name)
    await state.update_data(acc_draft={})
    text = (
        "<b>Новый счёт</b>\n\n"
        "Введите название (например: <code>Credo USD</code> или <code>Тинек …5566</code>)."
    )
    await _edit_or_answer(callback, text, await kb.account_cancel_kb())


@with_user
async def add_name(message: types.Message, state: FSMContext, pg_user: Users):
    if not pg_user:
        return
    name = (message.text or "").strip()
    if not name or len(name) > 255:
        await message.answer("Введите корректное название (до 255 символов).")
        return
    data = await state.get_data()
    draft = data.get("acc_draft") or {}
    draft["name"] = name
    await state.update_data(acc_draft=draft)
    await state.set_state(AccountFactory.currency)
    await message.answer(
        f"Название: <b>{name}</b>\n\nВыберите валюту или введите код (USD, RUB, GEL…):",
        reply_markup=await kb.account_currency_kb(),
        parse_mode="HTML",
    )


@with_user
async def add_currency_callback(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    if not pg_user:
        await callback.answer()
        return
    code = callback.data.split(":")[-1]
    await _set_currency_and_ask_bank(callback, state, code)


@with_user
async def add_currency_text(
    message: types.Message, state: FSMContext, pg_user: Users
):
    if not pg_user:
        return
    code = _norm_currency(message.text or "")
    if not code:
        await message.answer("Не понял валюту. Пример: USD, RUB, GEL.")
        return
    await _set_currency_and_ask_bank(message, state, code)


async def _set_currency_and_ask_bank(event, state: FSMContext, code: str):
    data = await state.get_data()
    draft = data.get("acc_draft") or {}
    draft["currency"] = code
    await state.update_data(acc_draft=draft)
    await state.set_state(AccountFactory.bank)
    text = (
        f"Валюта: <code>{code}</code>\n\n"
        "Введите банк (необязательно) или нажмите «Пропустить»."
    )
    await _edit_or_answer(event, text, await kb.account_skip_kb("acc:skip_bank"))


@with_user
async def add_bank_text(message: types.Message, state: FSMContext, pg_user: Users):
    if not pg_user:
        return
    bank = (message.text or "").strip() or None
    data = await state.get_data()
    draft = data.get("acc_draft") or {}
    draft["bank_label"] = bank
    await state.update_data(acc_draft=draft)
    await state.set_state(AccountFactory.country)
    await message.answer(
        "Введите страну (необязательно) или нажмите «Пропустить».",
        reply_markup=await kb.account_skip_kb("acc:skip_country"),
    )


@with_user
async def skip_bank(callback: types.CallbackQuery, state: FSMContext, pg_user: Users):
    if not pg_user:
        await callback.answer()
        return
    data = await state.get_data()
    draft = data.get("acc_draft") or {}
    draft["bank_label"] = None
    await state.update_data(acc_draft=draft)
    await state.set_state(AccountFactory.country)
    await _edit_or_answer(
        callback,
        "Введите страну (необязательно) или нажмите «Пропустить».",
        await kb.account_skip_kb("acc:skip_country"),
    )


@with_user
async def add_country_text(
    message: types.Message, state: FSMContext, pg_user: Users
):
    if not pg_user:
        return
    country = (message.text or "").strip() or None
    await _finish_create(message, state, pg_user, country)


@with_user
async def skip_country(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    if not pg_user:
        await callback.answer()
        return
    await _finish_create(callback, state, pg_user, None)


async def _finish_create(event, state: FSMContext, pg_user: Users, country: str | None):
    data = await state.get_data()
    draft = data.get("acc_draft") or {}
    await state.clear()
    acc, err = await postgres_connector.create_account(
        pg_user.id,
        name=draft.get("name"),
        currency=draft.get("currency"),
        bank_label=draft.get("bank_label"),
        country=country,
        is_active=True,
    )
    if err or not acc:
        await _edit_or_answer(
            event,
            f"Не удалось создать счёт: {err or 'ошибка'}",
            await kb.back_to_menu_kb(),
        )
        return
    text = f"Счёт создан.\n\n{_format_account_card(acc)}"
    keyboard = await kb.account_card_kb(acc.id, is_active=True, can_delete=True)
    await _edit_or_answer(event, text, keyboard)


@with_user
async def hide_account(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    if not pg_user:
        await callback.answer()
        return
    account_id = int(callback.data.split(":")[-1])
    ok = await postgres_connector.set_account_active(pg_user.id, account_id, False)
    await callback.answer("Скрыт" if ok else "Ошибка")
    acc = await postgres_connector.get_account(pg_user.id, account_id)
    if not acc:
        return
    can_delete = await _can_delete(acc.id)
    keyboard = await kb.account_card_kb(
        acc.id, is_active=acc.is_active, can_delete=can_delete
    )
    try:
        await callback.message.edit_text(
            _format_account_card(acc), reply_markup=keyboard, parse_mode="HTML"
        )
    except Exception:
        pass


@with_user
async def show_account(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    if not pg_user:
        await callback.answer()
        return
    account_id = int(callback.data.split(":")[-1])
    ok = await postgres_connector.set_account_active(pg_user.id, account_id, True)
    await callback.answer("Вернули" if ok else "Ошибка")
    acc = await postgres_connector.get_account(pg_user.id, account_id)
    if not acc:
        return
    can_delete = await _can_delete(acc.id)
    keyboard = await kb.account_card_kb(
        acc.id, is_active=acc.is_active, can_delete=can_delete
    )
    try:
        await callback.message.edit_text(
            _format_account_card(acc), reply_markup=keyboard, parse_mode="HTML"
        )
    except Exception:
        pass


@with_user
async def delete_ask(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    if not pg_user:
        await callback.answer()
        return
    account_id = int(callback.data.split(":")[-1])
    await _edit_or_answer(
        callback,
        "Удалить счёт безвозвратно? Это можно только если на нём нет операций.",
        await kb.account_delete_confirm_kb(account_id),
    )


@with_user
async def delete_ok(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    if not pg_user:
        await callback.answer()
        return
    account_id = int(callback.data.split(":")[-1])
    ok, err = await postgres_connector.delete_account(pg_user.id, account_id)
    if not ok:
        await callback.answer(err or "Ошибка", show_alert=True)
        acc = await postgres_connector.get_account(pg_user.id, account_id)
        if acc:
            can_delete = await _can_delete(acc.id)
            keyboard = await kb.account_card_kb(
                acc.id, is_active=acc.is_active, can_delete=can_delete
            )
            try:
                await callback.message.edit_text(
                    _format_account_card(acc), reply_markup=keyboard, parse_mode="HTML"
                )
            except Exception:
                pass
        return
    await callback.answer("Удалён")
    await open_accounts(callback, state, pg_user)


def register_handlers(dp: Dispatcher):
    dp.callback_query.register(open_accounts, F.data == "menu:accounts")
    dp.callback_query.register(view_account, F.data.startswith("acc:view:"))
    dp.callback_query.register(start_add_account, F.data == "acc:add")
    dp.callback_query.register(
        add_currency_callback, AccountFactory.currency, F.data.startswith("acc:cur:")
    )
    dp.callback_query.register(skip_bank, AccountFactory.bank, F.data == "acc:skip_bank")
    dp.callback_query.register(
        skip_country, AccountFactory.country, F.data == "acc:skip_country"
    )
    dp.callback_query.register(hide_account, F.data.startswith("acc:hide:"))
    dp.callback_query.register(show_account, F.data.startswith("acc:show:"))
    dp.callback_query.register(delete_ok, F.data.startswith("acc:del_ok:"))
    dp.callback_query.register(delete_ask, F.data.startswith("acc:askdel:"))

    dp.message.register(add_name, AccountFactory.name, F.text)
    dp.message.register(add_currency_text, AccountFactory.currency, F.text)
    dp.message.register(add_bank_text, AccountFactory.bank, F.text)
    dp.message.register(add_country_text, AccountFactory.country, F.text)
