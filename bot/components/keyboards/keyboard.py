from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from bot.components.utils import custom_button


async def menu_button(role=None):
    """Главное меню finance_bot (role оставлен для совместимости вызовов)."""
    buttons = [
        [
            InlineKeyboardButton(
                text=await custom_button("➕ Добавить операцию", "menu_add_tx_btn_v2"),
                callback_data="menu:add_tx",
            ),
        ],
        [
            InlineKeyboardButton(
                text=await custom_button("📊 Статистика", "menu_stats_btn_v2"),
                callback_data="menu:stats",
            ),
        ],
        [
            InlineKeyboardButton(
                text=await custom_button("📥 Импорт выписки / таблицы", "menu_import_btn_v2"),
                callback_data="menu:import",
            ),
        ],
        [
            InlineKeyboardButton(
                text=await custom_button("💳 Счета", "menu_accounts_btn_v2"),
                callback_data="menu:accounts",
            ),
            InlineKeyboardButton(
                text=await custom_button("🏷 Категории", "menu_categories_btn_v2"),
                callback_data="menu:categories",
            ),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def back_to_menu_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=await custom_button("« В меню", "back_menu_btn"),
                    callback_data="in_menu",
                )
            ]
        ]
    )


async def sign_up_kb(action, callback="sign_up"):
    if action == "fio":
        buttons = [
            [
                InlineKeyboardButton(
                    text=await custom_button("Использовать имя из Telegram", "sign_up_use_tg"),
                    callback_data=f"{callback}:use_tg_name",
                )
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    if action == "check_data":
        buttons = [
            [
                InlineKeyboardButton(
                    text=await custom_button("Изменить имя", "change_fio_button"),
                    callback_data=f"{callback}:fio",
                )
            ],
            [
                InlineKeyboardButton(
                    text=await custom_button("✅ Подтвердить", "change_confirm_button"),
                    callback_data=f"{callback}:confirm",
                )
            ],
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    return None


def remove_reply_kb():
    return ReplyKeyboardRemove()


async def accounts_list_kb(accounts: list):
    rows = []
    for acc in accounts:
        mark = "" if acc.is_active else " (скрыт)"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"💳 {acc.name} · {acc.currency}{mark}",
                    callback_data=f"acc:view:{acc.id}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text=await custom_button("➕ Новый счёт", "acc_add_btn"),
                callback_data="acc:add",
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text=await custom_button("« В меню", "back_menu_btn"),
                callback_data="in_menu",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def account_card_kb(account_id: int, *, is_active: bool, can_delete: bool):
    rows = []
    if is_active:
        rows.append(
            [
                InlineKeyboardButton(
                    text="👁 Скрыть счёт",
                    callback_data=f"acc:hide:{account_id}",
                )
            ]
        )
    else:
        rows.append(
            [
                InlineKeyboardButton(
                    text="✅ Вернуть в список",
                    callback_data=f"acc:show:{account_id}",
                )
            ]
        )
    if can_delete:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🗑 Удалить",
                    callback_data=f"acc:askdel:{account_id}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(text="« К счетам", callback_data="menu:accounts"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def account_delete_confirm_kb(account_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, удалить",
                    callback_data=f"acc:del_ok:{account_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Отмена",
                    callback_data=f"acc:view:{account_id}",
                )
            ],
        ]
    )


async def account_currency_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="USD", callback_data="acc:cur:USD"),
                InlineKeyboardButton(text="RUB", callback_data="acc:cur:RUB"),
                InlineKeyboardButton(text="GEL", callback_data="acc:cur:GEL"),
            ],
            [
                InlineKeyboardButton(text="EUR", callback_data="acc:cur:EUR"),
                InlineKeyboardButton(text="AMD", callback_data="acc:cur:AMD"),
            ],
            [
                InlineKeyboardButton(
                    text="« Отмена",
                    callback_data="menu:accounts",
                )
            ],
        ]
    )


async def account_cancel_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="« Отмена",
                    callback_data="menu:accounts",
                )
            ],
        ]
    )


async def account_skip_kb(skip_action: str):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Пропустить",
                    callback_data=skip_action,
                )
            ],
            [
                InlineKeyboardButton(
                    text="« Отмена",
                    callback_data="menu:accounts",
                )
            ],
        ]
    )


async def tx_pick_account_kb(accounts: list):
    rows = [
        [
            InlineKeyboardButton(
                text=f"💳 {acc.name} · {acc.currency}",
                callback_data=f"tx:acc:{acc.id}",
            )
        ]
        for acc in accounts
    ]
    rows.append(
        [InlineKeyboardButton(text="« В меню", callback_data="in_menu")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def tx_direction_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📉 Расход", callback_data="tx:dir:expense"),
                InlineKeyboardButton(text="📈 Доход", callback_data="tx:dir:income"),
            ],
            [
                InlineKeyboardButton(
                    text="🔁 Перевод", callback_data="tx:dir:transfer"
                ),
            ],
            [InlineKeyboardButton(text="« Отмена", callback_data="in_menu")],
        ]
    )


async def tx_categories_kb(categories: list, *, page: int = 0, page_size: int = 8):
    total = len(categories)
    start = page * page_size
    chunk = categories[start : start + page_size]
    rows = [
        [
            InlineKeyboardButton(
                text=cat.name[:60],
                callback_data=f"tx:pickcat:{cat.id}",
            )
        ]
        for cat in chunk
    ]
    nav = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(text="‹", callback_data=f"tx:catpage:{page - 1}")
        )
    if start + page_size < total:
        nav.append(
            InlineKeyboardButton(text="›", callback_data=f"tx:catpage:{page + 1}")
        )
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="« Отмена", callback_data="in_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def tx_date_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Сегодня", callback_data="tx:date:today"),
                InlineKeyboardButton(text="Вчера", callback_data="tx:date:yesterday"),
            ],
            [InlineKeyboardButton(text="« Отмена", callback_data="in_menu")],
        ]
    )


async def tx_skip_desc_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Без комментария", callback_data="tx:desc:skip"
                )
            ],
            [InlineKeyboardButton(text="« Отмена", callback_data="in_menu")],
        ]
    )


async def tx_cancel_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="« Отмена", callback_data="in_menu")]
        ]
    )


async def tx_delete_list_kb(transactions: list):
    dir_mark = {"expense": "−", "income": "+", "transfer": "↔"}
    rows = []
    for tx in transactions:
        mark = dir_mark.get(tx.direction, "?")
        cat = tx.category.name if tx.category_id else "без категории"
        label = (
            f"{tx.occurred_at:%d.%m} {mark}{tx.amount} {tx.currency} · {tx.account.name}"
        )
        if len(label) > 55:
            label = label[:52] + "…"
        rows.append(
            [InlineKeyboardButton(text=label, callback_data=f"tx:delview:{tx.id}")]
        )
    rows.append([InlineKeyboardButton(text="« В меню", callback_data="in_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def tx_delete_confirm_kb(tx_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Удалить", callback_data=f"tx:del_ok:{tx_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Отмена", callback_data="menu:del_tx"
                )
            ],
        ]
    )


KIND_LABEL = {
    "expense": "Расход",
    "income": "Доход",
    "transfer": "Перевод",
}


async def categories_list_kb(
    categories: list,
    *,
    kind: str | None = "expense",
    page: int = 0,
    page_size: int = 8,
    hidden_count: int = 0,
):
    rows = [
        [
            InlineKeyboardButton(
                text=("• " if kind == "expense" else "") + "Расход",
                callback_data="cat:kind:expense",
            ),
            InlineKeyboardButton(
                text=("• " if kind == "income" else "") + "Доход",
                callback_data="cat:kind:income",
            ),
            InlineKeyboardButton(
                text=("• " if kind == "transfer" else "") + "Перевод",
                callback_data="cat:kind:transfer",
            ),
        ]
    ]
    start = page * page_size
    chunk = categories[start : start + page_size]
    for cat in chunk:
        prefix = "⭐ " if not cat.is_system else ""
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{prefix}{cat.name}"[:60],
                    callback_data=f"cat:view:{cat.id}",
                )
            ]
        )
    nav = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(text="‹", callback_data=f"cat:page:{page - 1}")
        )
    if start + page_size < len(categories):
        nav.append(
            InlineKeyboardButton(text="›", callback_data=f"cat:page:{page + 1}")
        )
    if nav:
        rows.append(nav)
    rows.append(
        [
            InlineKeyboardButton(
                text="➕ Своя категория", callback_data="cat:add"
            )
        ]
    )
    if hidden_count:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"👁 Скрытые ({hidden_count})",
                    callback_data="cat:hidden",
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton(text="« В меню", callback_data="in_menu")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def category_card_kb(
    category_id: int, *, is_system: bool, is_hidden: bool
):
    rows = []
    if is_system:
        if is_hidden:
            rows.append(
                [
                    InlineKeyboardButton(
                        text="✅ Показать снова",
                        callback_data=f"cat:unhide:{category_id}",
                    )
                ]
            )
        else:
            rows.append(
                [
                    InlineKeyboardButton(
                        text="👁 Скрыть у себя",
                        callback_data=f"cat:hide:{category_id}",
                    )
                ]
            )
    else:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🗑 Удалить",
                    callback_data=f"cat:askdel:{category_id}",
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton(text="« К категориям", callback_data="menu:categories")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def category_delete_confirm_kb(category_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Удалить",
                    callback_data=f"cat:del_ok:{category_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Отмена",
                    callback_data=f"cat:view:{category_id}",
                )
            ],
        ]
    )


async def category_kind_pick_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📉 Расход", callback_data="cat:newkind:expense"
                ),
                InlineKeyboardButton(
                    text="📈 Доход", callback_data="cat:newkind:income"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔁 Перевод", callback_data="cat:newkind:transfer"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="« Отмена", callback_data="menu:categories"
                )
            ],
        ]
    )


async def category_cancel_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="« Отмена", callback_data="menu:categories"
                )
            ]
        ]
    )


async def hidden_categories_kb(categories: list):
    rows = [
        [
            InlineKeyboardButton(
                text=f"👁 {cat.name}"[:60],
                callback_data=f"cat:view:{cat.id}",
            )
        ]
        for cat in categories
    ]
    rows.append(
        [InlineKeyboardButton(text="« К категориям", callback_data="menu:categories")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


_MONTH_NAMES_RU_SHORT = {
    1: "янв",
    2: "фев",
    3: "мар",
    4: "апр",
    5: "май",
    6: "июн",
    7: "июл",
    8: "авг",
    9: "сен",
    10: "окт",
    11: "ноя",
    12: "дек",
}


async def stats_nav_kb(
    offset: int = 0,
    *,
    year: int | None = None,
    month: int | None = None,
    accounts: list | None = None,
):
    """Навигация по месяцам + детализация по счетам."""
    from datetime import date as _date

    today = _date.today()
    y, m = today.year, today.month
    m += offset
    while m < 1:
        m += 12
        y -= 1
    while m > 12:
        m -= 12
        y += 1
    if year is not None and month is not None:
        y, m = year, month

    label = f"{_MONTH_NAMES_RU_SHORT.get(m, m)} {y}"
    prev_m = m - 1 if m > 1 else 12
    row_nav = [
        InlineKeyboardButton(
            text=f"‹ {_MONTH_NAMES_RU_SHORT.get(prev_m, '…')}",
            callback_data=f"stats:month:{offset - 1}",
        ),
        InlineKeyboardButton(text=label, callback_data=f"stats:month:{offset}"),
    ]
    if (y, m) < (today.year, today.month):
        next_m = m + 1 if m < 12 else 1
        row_nav.append(
            InlineKeyboardButton(
                text=f"{_MONTH_NAMES_RU_SHORT.get(next_m, '…')} ›",
                callback_data=f"stats:month:{offset + 1}",
            )
        )

    rows: list[list[InlineKeyboardButton]] = [row_nav]

    if accounts:
        for acc in accounts:
            name = getattr(acc, "account_name", None) or getattr(acc, "name", "Счёт")
            short = name if len(name) <= 22 else name[:21] + "…"
            aid = int(getattr(acc, "account_id", getattr(acc, "id", 0)))
            rows.append(
                [
                    InlineKeyboardButton(
                        text=f"📋 {short}",
                        callback_data=f"stats:detail:{offset}:{aid}:0",
                    )
                ]
            )
    rows.append(
        [
            InlineKeyboardButton(
                text="📋 Все счета",
                callback_data=f"stats:detail:{offset}:0:0",
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text="Произвольный период", callback_data="stats:custom"
            )
        ]
    )
    rows.append([InlineKeyboardButton(text="« В меню", callback_data="in_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def stats_detail_kb(
    *,
    offset: int,
    account_id: int,
    page: int,
    page_count: int,
    transactions: list,
    active_cat_id: int | None = None,
    active_cat_label: str | None = None,
    direction: str | None = None,
):
    """Транзакции кнопками + пагинация + категории / доходы."""
    dir_mark = {"expense": "−", "income": "+", "transfer": "↔"}
    rows: list[list[InlineKeyboardButton]] = []
    acc = int(account_id or 0)

    for tx in transactions:
        mark = dir_mark.get(tx.direction, "")
        cat = tx.category.name if tx.category_id else "—"
        desc = (tx.description or "").replace("\n", " ").replace("|", "/").strip()
        for pref in ("საბარათე ოპერაცია ", "გადახდა - ", "განაღდება - "):
            if desc.startswith(pref):
                desc = desc[len(pref) :]
        label = (
            f"{tx.occurred_at:%d.%m}|{mark}{tx.amount} {tx.currency}"
            f"|{cat}|{desc}"
        )
        if len(label) > 64:
            label = label[:61] + "…"
        rows.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"stats:tx:{tx.id}",
                )
            ]
        )

    if page_count > 1:
        nav = []
        if page > 0:
            nav.append(
                InlineKeyboardButton(
                    text="‹",
                    callback_data=_detail_page_cb(
                        offset, acc, active_cat_id, page - 1, direction
                    ),
                )
            )
        nav.append(
            InlineKeyboardButton(
                text=f"{page + 1}/{page_count}",
                callback_data=_detail_page_cb(
                    offset, acc, active_cat_id, page, direction
                ),
            )
        )
        if page + 1 < page_count:
            nav.append(
                InlineKeyboardButton(
                    text="›",
                    callback_data=_detail_page_cb(
                        offset, acc, active_cat_id, page + 1, direction
                    ),
                )
            )
        rows.append(nav)

    cat_btn_text = "📂 Категории"
    if active_cat_label:
        short = active_cat_label if len(active_cat_label) <= 24 else active_cat_label[:23] + "…"
        cat_btn_text = f"📂 {short}"
    income_mark = "• " if direction == "income" and active_cat_id is None else ""
    rows.append(
        [
            InlineKeyboardButton(
                text=cat_btn_text,
                callback_data=f"stats:cats:{offset}:{acc}",
            ),
            InlineKeyboardButton(
                text=f"{income_mark}📈 Доходы",
                callback_data=f"stats:din:{offset}:{acc}:0",
            ),
        ]
    )
    if active_cat_id is not None or direction is not None:
        rows.append(
            [
                InlineKeyboardButton(
                    text="Все операции",
                    callback_data=f"stats:detail:{offset}:{acc}:0",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="« К сводке",
                callback_data=f"stats:month:{offset}",
            ),
            InlineKeyboardButton(text="« Меню", callback_data="in_menu"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def stats_cats_kb(
    *,
    offset: int,
    account_id: int,
    expense_by_cat: dict,
    expense_usd,
    cat_id_by_name: dict[str, int],
    active_cat_id: int | None = None,
    income_by_cat: dict | None = None,
    income_usd=None,
):
    """Экран выбора категории: расходы и доходы отдельными блоками."""
    from decimal import Decimal

    acc = int(account_id or 0)
    rows: list[list[InlineKeyboardButton]] = []

    def _cat_rows(by_cat: dict, total_raw) -> list[InlineKeyboardButton]:
        total = Decimal(str(total_raw or 0))
        items = sorted(
            by_cat.items(),
            key=lambda x: Decimal(str(x[1])),
            reverse=True,
        )
        btns: list[InlineKeyboardButton] = []
        for name, amt in items:
            cid = cat_id_by_name.get(name)
            if cid is None:
                continue
            pct = (100 * Decimal(str(amt)) / total) if total else Decimal(0)
            mark = "•" if active_cat_id == cid else ""
            short = name if len(name) <= 16 else name[:15] + "…"
            label = f"{mark}{pct:.0f}% {short}".strip()
            if len(label) > 30:
                label = label[:29] + "…"
            btns.append(
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"stats:dcat:{offset}:{acc}:{cid}:0",
                )
            )
        return btns

    if expense_by_cat:
        rows.append(
            [InlineKeyboardButton(text="📉 Расходы", callback_data="stats:noop")]
        )
        exp_btns = _cat_rows(expense_by_cat, expense_usd)
        for i in range(0, len(exp_btns), 3):
            rows.append(exp_btns[i : i + 3])

    if income_by_cat:
        rows.append(
            [InlineKeyboardButton(text="📈 Доходы", callback_data="stats:noop")]
        )
        inc_btns = _cat_rows(income_by_cat, income_usd)
        for i in range(0, len(inc_btns), 3):
            rows.append(inc_btns[i : i + 3])

    rows.append(
        [
            InlineKeyboardButton(
                text="Все операции",
                callback_data=f"stats:detail:{offset}:{acc}:0",
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text="« Назад",
                callback_data=_detail_page_cb(offset, acc, active_cat_id, 0),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _detail_page_cb(
    offset: int,
    account_id: int,
    cat_id: int | None,
    page: int,
    direction: str | None = None,
) -> str:
    acc = int(account_id or 0)
    if cat_id is not None:
        return f"stats:dcat:{offset}:{acc}:{cat_id}:{page}"
    if direction == "income":
        return f"stats:din:{offset}:{acc}:{page}"
    return f"stats:detail:{offset}:{acc}:{page}"


async def stats_tx_card_kb(tx_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🏷 Категория",
                    callback_data=f"stats:txedit:cat:{tx_id}",
                ),
                InlineKeyboardButton(
                    text="💰 Сумма",
                    callback_data=f"stats:txedit:amt:{tx_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📅 Дата",
                    callback_data=f"stats:txedit:date:{tx_id}",
                ),
                InlineKeyboardButton(
                    text="📝 Описание",
                    callback_data=f"stats:txedit:desc:{tx_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🗑 Удалить",
                    callback_data=f"stats:txdel:{tx_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="« Назад",
                    callback_data="stats:txback",
                ),
            ],
        ]
    )


async def stats_tx_cat_apply_kb(tx_id: int, cat_id: int, similar_count: int):
    """После смены категории: применить к похожим за месяц или только эту."""
    rows = []
    if similar_count > 0:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"Применить к {similar_count} похожим за месяц",
                    callback_data=f"stats:txcatall:{tx_id}:{cat_id}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="Только эту",
                callback_data=f"stats:txcatone:{tx_id}",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def stats_tx_delete_confirm_kb(tx_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Удалить",
                    callback_data=f"stats:txdelok:{tx_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="« Отмена",
                    callback_data=f"stats:tx:{tx_id}",
                )
            ],
        ]
    )


async def stats_tx_edit_cats_kb(categories: list, tx_id: int, *, page: int = 0):
    page_size = 8
    start = page * page_size
    chunk = categories[start : start + page_size]
    rows = [
        [
            InlineKeyboardButton(
                text=cat.name[:60],
                callback_data=f"stats:txsetcat:{tx_id}:{cat.id}",
            )
        ]
        for cat in chunk
    ]
    nav = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(
                text="‹", callback_data=f"stats:txcatpage:{tx_id}:{page - 1}"
            )
        )
    if start + page_size < len(categories):
        nav.append(
            InlineKeyboardButton(
                text="›", callback_data=f"stats:txcatpage:{tx_id}:{page + 1}"
            )
        )
    if nav:
        rows.append(nav)
    rows.append(
        [
            InlineKeyboardButton(
                text="« Назад", callback_data=f"stats:tx:{tx_id}"
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def stats_tx_edit_cancel_kb(tx_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="« Отмена", callback_data=f"stats:tx:{tx_id}"
                )
            ]
        ]
    )


async def stats_period_kb():
    """Совместимость: сразу ведём на навигацию текущего месяца."""
    return await stats_nav_kb(0)


async def stats_result_kb():
    return await stats_nav_kb(0)


async def stats_cancel_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="« Отмена", callback_data="menu:stats")]
        ]
    )


async def import_pick_account_kb(accounts: list):
    rows = [
        [
            InlineKeyboardButton(
                text=f"💳 {acc.name} · {acc.currency}",
                callback_data=f"imp:acc:{acc.id}",
            )
        ]
        for acc in accounts
    ]
    rows.append([InlineKeyboardButton(text="« В меню", callback_data="in_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def import_cancel_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="« Отмена", callback_data="in_menu")]
        ]
    )


async def import_done_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 Статистика", callback_data="menu:stats"
                )
            ],
            [InlineKeyboardButton(text="« В меню", callback_data="in_menu")],
        ]
    )


async def report_period_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Этот месяц", callback_data="report:month:0"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Прошлый месяц", callback_data="report:month:-1"
                )
            ],
            [
                InlineKeyboardButton(
                    text="« В меню", callback_data="in_menu"
                )
            ],
        ]
    )


async def report_result_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Другой месяц", callback_data="menu:report"
                )
            ],
            [InlineKeyboardButton(text="« В меню", callback_data="in_menu")],
        ]
    )
