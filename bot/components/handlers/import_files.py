from __future__ import annotations

import tempfile
from pathlib import Path

from aiogram import types, Dispatcher, F, Bot
from aiogram.fsm.context import FSMContext
from asgiref.sync import sync_to_async

from connectors import postgres_connector
from bot.components.keyboards import keyboard as kb
from bot.components.utils import with_user
from bot.components.factory import ImportFactory
from bot.components.finance.parsers import parse_statement_file
from bot.components.finance.ai_categorizer import (
    CategoryOption,
    apply_hints_to_transactions,
    categorize_batch_with_ai,
)
from core.models import Users, ImportBatchStatus


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
async def start_import(
    callback: types.CallbackQuery, state: FSMContext, pg_user: Users
):
    await state.clear()
    if not pg_user:
        await callback.answer("Сначала регистрация", show_alert=True)
        return
    accounts = await postgres_connector.list_accounts(pg_user.id, active_only=True)
    if not accounts:
        await _edit_or_answer(
            callback,
            "<b>📥 Импорт</b>\n\nСначала создайте счёт.",
            await kb.back_to_menu_kb(),
        )
        return
    await _edit_or_answer(
        callback,
        "<b>📥 Импорт выписки</b>\n\n"
        "Выберите счёт, на который записать операции.\n"
        "Поддерживаются <code>.xlsx</code> / <code>.csv</code> "
        "(MyCredo) и <code>.pdf</code> (справка Т-Банка).",
        await kb.import_pick_account_kb(accounts),
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
    await state.update_data(
        import_account_id=acc.id,
        import_currency=acc.currency,
        import_account_name=acc.name,
    )
    await state.set_state(ImportFactory.waiting_file)
    await _edit_or_answer(
        callback,
        f"Счёт: <b>{acc.name}</b> ({acc.currency})\n\n"
        "Пришлите файл выписки документом (не сжатым архивом).",
        await kb.import_cancel_kb(),
    )


@with_user
async def receive_file(
    message: types.Message, state: FSMContext, pg_user: Users, bot: Bot
):
    if not pg_user:
        return
    doc = message.document
    if not doc:
        await message.answer("Пришлите файл как документ.")
        return
    name = doc.file_name or "statement"
    suffix = Path(name).suffix.lower()
    if suffix not in {".xlsx", ".xlsm", ".csv", ".tsv", ".txt", ".pdf"}:
        await message.answer(
            "Поддерживаются .xlsx / .csv (MyCredo) и .pdf (Т-Банк).\n"
            f"Получен: {suffix or 'без расширения'}"
        )
        return

    data = await state.get_data()
    account_id = data.get("import_account_id")
    currency = data.get("import_currency")
    account_name = data.get("import_account_name", "")
    if not account_id or not currency:
        await state.clear()
        await message.answer(
            "Сессия импорта сброшена. Начните снова.",
            reply_markup=await kb.back_to_menu_kb(),
        )
        return

    status_msg = await message.answer("Обрабатываю файл…")
    batch = await postgres_connector.create_import_batch(
        pg_user.id, account_id, name
    )

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp_path = Path(tmp.name)
        await bot.download(doc, destination=tmp_path)

        result = await sync_to_async(parse_statement_file)(
            tmp_path,
            account_id=account_id,
            currency=currency,
        )
        if result.error and not result.transactions:
            await postgres_connector.finish_import_batch(
                batch.id,
                status=ImportBatchStatus.FAILED,
                error=result.error,
            )
            await state.clear()
            await status_msg.edit_text(
                f"Не удалось разобрать файл.\n{result.error}",
                reply_markup=await kb.import_done_kb(),
            )
            return

        await status_msg.edit_text(
            f"Распознано {len(result.transactions)} операций.\n"
            "Категоризирую через OpenAI (один запрос)…"
        )

        cat_rows = await postgres_connector.list_visible_categories(pg_user.id)
        ai_cats = [CategoryOption(name=c.name, kind=c.kind) for c in cat_rows]
        user_prefs = await postgres_connector.list_category_preferences(pg_user.id)
        ai_result = await categorize_batch_with_ai(
            result.transactions, ai_cats, user_prefs=user_prefs
        )
        apply_hints_to_transactions(result.transactions, ai_result.hints, ai_cats)

        payload = []
        for tx in result.transactions:
            cat_id = await postgres_connector.resolve_category_id(
                pg_user.id, tx.category_hint, tx.direction
            )
            payload.append(
                {
                    "occurred_at": tx.occurred_at,
                    "amount": tx.amount,
                    "currency": tx.currency,
                    "direction": tx.direction,
                    "description": tx.description,
                    "external_id": tx.external_id,
                    "category_id": cat_id,
                }
            )

        stats = await postgres_connector.import_parsed_transactions(
            pg_user.id, account_id, batch.id, payload
        )
        status = ImportBatchStatus.DONE
        if stats["failed"] and stats["created"]:
            status = ImportBatchStatus.PARTIAL
        elif stats["failed"] and not stats["created"]:
            status = ImportBatchStatus.FAILED

        await postgres_connector.finish_import_batch(
            batch.id,
            status=status,
            stats={
                **stats,
                "format": result.format_hint,
                "ai_categorize": ai_result.used_ai,
                "ai_error": ai_result.error,
            },
            error=result.error,
        )
        await state.clear()
        text = (
            f"<b>Импорт завершён</b>\n"
            f"Счёт: {account_name}\n"
            f"Формат: <code>{result.format_hint}</code>\n"
            f"Файл: {name}\n\n"
            f"Распознано: {stats['total']}\n"
            f"Новых: <b>{stats['created']}</b>\n"
            f"Дублей пропущено: {stats['duplicates']}\n"
            f"Ошибок: {stats['failed']}\n"
        )
        if ai_result.used_ai:
            text += "Категории: <b>OpenAI</b> (один запрос)\n"
        else:
            text += "Категории: правила парсера\n"
        if ai_result.error:
            text += f"⚠ {ai_result.error}\n"
        if result.error:
            text += f"\n⚠ {result.error}"
        await status_msg.edit_text(
            text, reply_markup=await kb.import_done_kb(), parse_mode="HTML"
        )
    except Exception as exc:
        await postgres_connector.finish_import_batch(
            batch.id,
            status=ImportBatchStatus.FAILED,
            error=str(exc)[:500],
        )
        await state.clear()
        await status_msg.edit_text(
            f"Ошибка импорта: {exc}",
            reply_markup=await kb.import_done_kb(),
        )
    finally:
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def register_handlers(dp: Dispatcher):
    dp.callback_query.register(start_import, F.data == "menu:import")
    dp.callback_query.register(pick_account, F.data.startswith("imp:acc:"))
    dp.message.register(
        receive_file, ImportFactory.waiting_file, F.document
    )
