from aiogram import types, Dispatcher, F
from aiogram.fsm.context import FSMContext
from connectors import postgres_connector
from bot.components.keyboards import keyboard as kb
from bot.components.utils import custom_text, get_event_data
from bot.components.factory import UserFactory


def _tg_display_name(user: types.User) -> str:
    parts = [user.first_name or "", user.last_name or ""]
    name = " ".join(p for p in parts if p).strip()
    return name or (user.username and f"@{user.username}") or str(user.id)


async def sign_up(event: types.Message | types.CallbackQuery, state: FSMContext):
    """Короткая регистрация: только отображаемое имя."""
    chain = {
        "fio": "Как вас отображать в боте?\nВведите имя текстом или нажмите кнопку ниже.",
        "check_data": "Проверьте данные:\n\n<b>Имя:</b> %s",
    }
    data = await state.get_data()
    if "user_data" not in data:
        welcome = await custom_text(
            "Добро пожаловать в бот учёта финансов.\nПройдите короткую регистрацию.",
            "finance_welcome",
        )
        await event.answer(welcome)
        data["user_data"] = {}

    # Первый вызов из /start — ещё нет ответа на шаг, только показываем fio
    if "expected_node" not in data and not hasattr(event, "data"):
        await state.update_data(expected_node="fio", user_data=data["user_data"])
        keyboard = await kb.sign_up_kb("fio")
        step_text = await custom_text(chain["fio"], "sign_up_fio")
        text = f"<b>Шаг 1/{len(chain)}</b>\n{step_text}"
        await event.answer(text, reply_markup=keyboard, parse_mode="HTML")
        return await state.set_state(UserFactory.sign_up)

    expected_node_data = get_event_data(event)
    if "expected_node" in data:
        if data["expected_node"] == "check_data" and expected_node_data != "confirm":
            # вернулись к правке поля (callback sign_up:fio)
            data["user_data"].pop(expected_node_data, None)
        elif data["expected_node"] == "fio":
            if expected_node_data == "use_tg_name":
                data["user_data"]["fio"] = _tg_display_name(event.from_user)
            else:
                name = (expected_node_data or "").strip()
                if not name or name.startswith("/"):
                    tip = await custom_text(
                        "Введите имя или нажмите кнопку «Использовать имя из Telegram».",
                        "sign_up_fio_retry",
                    )
                    keyboard = await kb.sign_up_kb("fio")
                    if hasattr(event, "data"):
                        await event.message.answer(tip, reply_markup=keyboard)
                    else:
                        await event.answer(tip, reply_markup=keyboard)
                    return await state.set_state(UserFactory.sign_up)
                data["user_data"]["fio"] = name
        elif data["expected_node"] == "check_data" and expected_node_data == "confirm":
            data["user_data"]["check_data"] = "confirm"

    for node, node_text in chain.items():
        if node not in data["user_data"]:
            await state.update_data(expected_node=node, user_data=data["user_data"])
            keyboard = await kb.sign_up_kb(node)
            if node == "check_data":
                additional = (data["user_data"]["fio"],)
            else:
                additional = None
            action_text = await custom_text(node_text, f"sign_up_{node}", additional)
            text = f"<b>Шаг {len(data['user_data']) + 1}/{len(chain)}</b>\n{action_text}"
            if hasattr(event, "data"):
                await event.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            else:
                await event.answer(text, reply_markup=keyboard, parse_mode="HTML")
            return await state.set_state(UserFactory.sign_up)

    data["user_data"]["tg_username"] = event.from_user.username
    data["user_data"]["tg_id"] = event.from_user.id
    data["user_data"]["role"] = "user"
    # check_data — служебный ключ, в Users не пишем
    payload = {
        k: v
        for k, v in data["user_data"].items()
        if k in {"tg_id", "tg_username", "fio", "role", "phone", "email"}
    }
    await postgres_connector.add_user(payload)
    await state.clear()
    text = await custom_text(
        "Готово! Выберите действие в меню.",
        "finance_sign_up_succ",
    )
    keyboard = await kb.menu_button()
    if hasattr(event, "data"):
        await event.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await event.answer(text, reply_markup=keyboard, parse_mode="HTML")


def register_handlers(dp: Dispatcher):
    dp.callback_query.register(sign_up, F.data.startswith("sign_up:"))
    dp.message.register(sign_up, UserFactory.sign_up, F.text)
