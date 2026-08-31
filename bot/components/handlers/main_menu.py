from aiogram import types, Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from core.models import Users
from bot.components.keyboards import keyboard as kb
from bot.components.utils import custom_text, with_user
from bot.components.handlers.sign_up import sign_up


@with_user
async def start(message: types.Message, state: FSMContext, pg_user: Users):
    await state.clear()
    if not pg_user:
        return await sign_up(message, state)
    keyboard = await kb.menu_button(pg_user.role)
    menu_text = await custom_text(
        "Привет, %s!\nУчёт финансов — выберите раздел:",
        "finance_hello",
        formatting_attrs=(pg_user.fio or "друг",),
    )
    await message.answer(menu_text, reply_markup=keyboard, parse_mode="HTML")


@with_user
async def in_menu(
    callback: types.CallbackQuery, state: FSMContext, bot: Bot, pg_user: Users
):
    data = await state.get_data()
    if "messages_to_delete" in data:
        for message_id in data["messages_to_delete"]:
            if message_id != callback.message.message_id:
                try:
                    await bot.delete_message(
                        chat_id=callback.from_user.id, message_id=message_id
                    )
                except Exception:
                    pass
    await state.clear()
    if not pg_user:
        await callback.answer()
        return await sign_up(callback.message, state)
    keyboard = await kb.menu_button(pg_user.role)
    menu_text = await custom_text(
        "Привет, %s!\nУчёт финансов — выберите раздел:",
        "finance_hello",
        formatting_attrs=(pg_user.fio or "друг",),
    )
    try:
        await callback.message.edit_text(
            menu_text, reply_markup=keyboard, parse_mode="HTML"
        )
    except Exception:
        await callback.message.answer(
            menu_text, reply_markup=keyboard, parse_mode="HTML"
        )
    await callback.answer()


def register_handlers(dp: Dispatcher):
    dp.message.register(start, CommandStart())
    dp.callback_query.register(in_menu, F.data == "in_menu")
