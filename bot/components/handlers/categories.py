from __future__ import annotations

from aiogram import types, Dispatcher, F
from aiogram.fsm.context import FSMContext

from connectors import postgres_connector
from bot.components.keyboards import keyboard as kb
from bot.components.keyboards.keyboard import KIND_LABEL
from bot.components.utils import with_user
from bot.components.factory import CategoryFactory
from core.models import Users


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


async def _render_list(event, state: FSMContext, pg_user: Users, *, kind: str, page: int):
    cats = await postgres_connector.list_visible_categories(pg_user.id, kind=kind)
    hidden = await postgres_connector.list_hidden_categories(pg_user.id)
    await state.update_data(cat_kind=kind, cat_page=page)
    label = KIND_LABEL.get(kind, kind)
    text = (
        f"<b>🏷 Категории — {label}</b>\n\n"
        f"Видимых: {len(cats)}. ⭐ — ваши.\n"
        "Выберите категорию или создайте свою."
    )
    keyboard = await kb.categories_list_kb(
        cats, kind=kind, page=page, hidden_count=len(hidden)
    )
    await _edit_or_answer(event, text, keyboard)


@with_user
async def open_categories(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    await state.clear()
    if not pg_user:
        await callback.answer("Сначала регистрация", show_alert=True)
        return
    await _render_list(callback, state, pg_user, kind="expense", page=0)


@with_user
async def switch_kind(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    if not pg_user:
        await callback.answer()
        return
    kind = callback.data.split(":")[-1]
    if kind not in KIND_LABEL:
        await callback.answer()
        return
    await _render_list(callback, state, pg_user, kind=kind, page=0)


@with_user
async def switch_page(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    if not pg_user:
        await callback.answer()
        return
    page = int(callback.data.split(":")[-1])
    data = await state.get_data()
    kind = data.get("cat_kind") or "expense"
    await _render_list(callback, state, pg_user, kind=kind, page=page)


@with_user
async def view_category(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    if not pg_user:
        await callback.answer()
        return
    cat_id = int(callback.data.split(":")[-1])
    cat, hidden = await postgres_connector.get_category_for_user(pg_user.id, cat_id)
    if not cat:
        await callback.answer("Не найдено", show_alert=True)
        return
    scope = "базовая" if cat.is_system else "ваша"
    status = "скрыта у вас" if hidden else "видима"
    text = (
        f"<b>{cat.name}</b>\n"
        f"Тип: {KIND_LABEL.get(cat.kind, cat.kind)}\n"
        f"Источник: {scope}\n"
        f"Статус: {status}"
    )
    keyboard = await kb.category_card_kb(
        cat.id, is_system=cat.is_system, is_hidden=hidden
    )
    await _edit_or_answer(callback, text, keyboard)


@with_user
async def hide_cat(callback: types.CallbackQuery, state: FSMContext, pg_user: Users):
    if not pg_user:
        await callback.answer()
        return
    cat_id = int(callback.data.split(":")[-1])
    ok, err = await postgres_connector.hide_category(pg_user.id, cat_id)
    if not ok:
        await callback.answer(err or "Ошибка", show_alert=True)
        return
    data = await state.get_data()
    kind = data.get("cat_kind") or "expense"
    await _render_list(callback, state, pg_user, kind=kind, page=0)


@with_user
async def unhide_cat(callback: types.CallbackQuery, state: FSMContext, pg_user: Users):
    if not pg_user:
        await callback.answer()
        return
    cat_id = int(callback.data.split(":")[-1])
    ok = await postgres_connector.unhide_category(pg_user.id, cat_id)
    if not ok:
        await callback.answer("Ошибка", show_alert=True)
        return
    cat, hidden = await postgres_connector.get_category_for_user(pg_user.id, cat_id)
    if not cat:
        await callback.answer("Не найдено", show_alert=True)
        return
    text = (
        f"<b>{cat.name}</b>\n"
        f"Тип: {KIND_LABEL.get(cat.kind, cat.kind)}\n"
        f"Источник: базовая\n"
        f"Статус: {'скрыта у вас' if hidden else 'видима'}"
    )
    keyboard = await kb.category_card_kb(
        cat.id, is_system=True, is_hidden=hidden
    )
    await _edit_or_answer(callback, text, keyboard)


@with_user
async def show_hidden(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    if not pg_user:
        await callback.answer()
        return
    hidden = await postgres_connector.list_hidden_categories(pg_user.id)
    if not hidden:
        await callback.answer("Нет скрытых", show_alert=True)
        return
    text = "<b>Скрытые базовые категории</b>\n\nВыберите, чтобы вернуть."
    await _edit_or_answer(callback, text, await kb.hidden_categories_kb(hidden))


@with_user
async def start_add(callback: types.CallbackQuery, state: FSMContext, pg_user: Users):
    if not pg_user:
        await callback.answer()
        return
    await state.set_state(None)
    await _edit_or_answer(
        callback,
        "<b>Новая категория</b>\n\nВыберите тип:",
        await kb.category_kind_pick_kb(),
    )


@with_user
async def pick_new_kind(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    if not pg_user:
        await callback.answer()
        return
    kind = callback.data.split(":")[-1]
    if kind not in KIND_LABEL:
        await callback.answer()
        return
    await state.update_data(new_cat_kind=kind)
    await state.set_state(CategoryFactory.name)
    await _edit_or_answer(
        callback,
        f"Тип: <b>{KIND_LABEL[kind]}</b>\n\nВведите название категории:",
        await kb.category_cancel_kb(),
    )


@with_user
async def enter_name(message: types.Message, state: FSMContext, pg_user: Users):
    if not pg_user:
        return
    name = (message.text or "").strip()
    if not name or len(name) > 255:
        await message.answer("Введите название (до 255 символов).")
        return
    data = await state.get_data()
    kind = data.get("new_cat_kind")
    await state.clear()
    if not kind:
        await message.answer(
            "Сессия сброшена. Начните снова.",
            reply_markup=await kb.back_to_menu_kb(),
        )
        return
    cat, err = await postgres_connector.create_user_category(pg_user.id, name, kind)
    if err or not cat:
        await message.answer(
            f"Не удалось создать: {err or 'ошибка'}",
            reply_markup=await kb.category_cancel_kb(),
        )
        return
    text = (
        f"Категория создана.\n\n"
        f"<b>{cat.name}</b>\nТип: {KIND_LABEL.get(cat.kind, cat.kind)}"
    )
    keyboard = await kb.category_card_kb(
        cat.id, is_system=False, is_hidden=False
    )
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@with_user
async def delete_ask(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    if not pg_user:
        await callback.answer()
        return
    cat_id = int(callback.data.split(":")[-1])
    await _edit_or_answer(
        callback,
        "Удалить свою категорию? Базовые так удалить нельзя — только скрыть.",
        await kb.category_delete_confirm_kb(cat_id),
    )


@with_user
async def delete_ok(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    if not pg_user:
        await callback.answer()
        return
    cat_id = int(callback.data.split(":")[-1])
    ok, err = await postgres_connector.delete_user_category(pg_user.id, cat_id)
    if not ok:
        await callback.answer(err or "Ошибка", show_alert=True)
        return
    data = await state.get_data()
    kind = data.get("cat_kind") or "expense"
    await _render_list(callback, state, pg_user, kind=kind, page=0)


def register_handlers(dp: Dispatcher):
    dp.callback_query.register(open_categories, F.data == "menu:categories")
    dp.callback_query.register(switch_kind, F.data.startswith("cat:kind:"))
    dp.callback_query.register(switch_page, F.data.startswith("cat:page:"))
    dp.callback_query.register(view_category, F.data.startswith("cat:view:"))
    dp.callback_query.register(hide_cat, F.data.startswith("cat:hide:"))
    dp.callback_query.register(unhide_cat, F.data.startswith("cat:unhide:"))
    dp.callback_query.register(show_hidden, F.data == "cat:hidden")
    dp.callback_query.register(start_add, F.data == "cat:add")
    dp.callback_query.register(pick_new_kind, F.data.startswith("cat:newkind:"))
    dp.callback_query.register(delete_ask, F.data.startswith("cat:askdel:"))
    dp.callback_query.register(delete_ok, F.data.startswith("cat:del_ok:"))
    dp.message.register(enter_name, CategoryFactory.name, F.text)
