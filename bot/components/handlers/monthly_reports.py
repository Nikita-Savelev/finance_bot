from __future__ import annotations

from datetime import date

from aiogram import types, Dispatcher, F
from aiogram.fsm.context import FSMContext

from bot.components.keyboards import keyboard as kb
from bot.components.utils import with_user
from bot.components.finance.reports import build_monthly_report
from core.models import Users


def _month_bounds(offset: int = 0) -> tuple[int, int]:
    today = date.today()
    year, month = today.year, today.month
    month += offset
    while month < 1:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return year, month


def _split_html(text: str, limit: int = 3500) -> list[str]:
    if len(text) <= limit:
        return [text]
    parts: list[str] = []
    buf: list[str] = []
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


async def _send_report(event, text: str, reply_markup=None):
    chunks = _split_html(text)
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


@with_user
async def open_report(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    await state.clear()
    if not pg_user:
        await callback.answer("Сначала регистрация", show_alert=True)
        return
    try:
        await callback.message.edit_text(
            "<b>📋 Отчёт за месяц</b>\n\nВыберите месяц (отчёт соберётся из текущих операций):",
            reply_markup=await kb.report_period_kb(),
            parse_mode="HTML",
        )
    except Exception:
        await callback.message.answer(
            "<b>📋 Отчёт за месяц</b>\n\nВыберите месяц:",
            reply_markup=await kb.report_period_kb(),
            parse_mode="HTML",
        )
    await callback.answer()


@with_user
async def report_month(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    if not pg_user:
        await callback.answer()
        return
    offset = int(callback.data.split(":")[-1])
    year, month = _month_bounds(offset)
    await callback.answer("Собираю отчёт…")
    text = await build_monthly_report(pg_user.id, year, month)
    # already answered — send without double answer
    chunks = _split_html(text)
    try:
        await callback.message.edit_text(
            chunks[0],
            reply_markup=await kb.report_result_kb() if len(chunks) == 1 else None,
            parse_mode="HTML",
        )
    except Exception:
        await callback.message.answer(chunks[0], parse_mode="HTML")
    for chunk in chunks[1:]:
        await callback.message.answer(chunk, parse_mode="HTML")
    if len(chunks) > 1:
        await callback.message.answer("—", reply_markup=await kb.report_result_kb())


def register_handlers(dp: Dispatcher):
    dp.callback_query.register(open_report, F.data == "menu:report")
    dp.callback_query.register(report_month, F.data.startswith("report:month:"))
