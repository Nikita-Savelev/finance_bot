"""Простая категоризация по описанию (fallback без OpenAI)."""

from __future__ import annotations

INTERNAL_TRANSFER = "🔁 Переводы"


def is_internal_transfer(description: str, operation: str = "") -> bool:
    d = (description or "").upper()
    op = operation or ""
    raw = description or ""
    if "ВНУТРЕННИЙ ПЕРЕВОД" in d or "ПЕРЕВОД СО СВОЕГО" in d:
        return True
    if "ПЕРЕВОД СЕБЕ" in d:
        return True
    if "ПЕРЕВОД С ДОГОВОРА" in d:
        return True
    if "ПЕРЕВОД НА КАРТУ" in d:
        return True
    if "ВНЕШНИЙ ПЕРЕВОД" in d:
        return True
    if "ПЕРЕВОД" in d and "ДОГОВОР" in d:
        return True
    if "საკუთარ ანგარიშებს შორის" in op:
        return True
    if "ავტომატური შევსების" in raw:
        return True
    return False


def categorize(
    description: str,
    operation: str = "",
    *,
    default_direction: str = "expense",
) -> tuple[str, str | None]:
    """Returns (direction, category_hint). Знак операции (default_direction) важнее правил."""
    raw = description or ""
    d = raw.upper()
    op = operation or ""

    if is_internal_transfer(description, operation):
        # «Перевод себе» / с договора приходят в плюс → доход; исходящие → расход
        direction = "income" if default_direction == "income" else "expense"
        return direction, INTERNAL_TRANSFER

    if default_direction == "income":
        if "BACKEND DEVELOPMENT" in d or "321.FIT" in d:
            return "income", "💼 Зарплата"
        if "საპროცენტო" in op or "INTEREST" in d:
            return "income", "📈 Проценты"
        return "income", "➕ Поступления"

    if "AI POWERED IDE" in d:
        return "expense", "💻 IDE"
    if "GOOGLE" in d and "ONE" in d:
        return "expense", "☁️ Google One"
    if "საკომისიო" in op or "საკომისიო" in raw or "КОМИСС" in d:
        return "expense", "🏧 Комиссии"
    if "განაღდება" in op or "განაღდება" in raw or "ATM" in d or "СНЯТИЕ" in d:
        return "expense", "💵 Наличные"
    if "ОБМЕН ВАЛЮТ" in d:
        return "expense", "💱 Обмен"
    if (
        "YANDEX.EDA" in d
        or "ЯНДЕКС.ЕДА" in d
        or "YANDEX*5814*EDA" in d
        or "DELIVERY" in d
    ):
        return "expense", "🛵 Доставка"
    if "YANDEX" in d and ("GO" in d or "TAXI" in d or "4121" in d):
        return "expense", "🚕 Такси"
    if "OZON" in d or "WILDBERRIES" in d or "WB " in d or "FLOWWOW" in d:
        return "expense", "📦 Маркетплейсы"

    if "PHARM" in d or "АПТЕК" in d or "CITO LAB" in d or "CLINIC" in d:
        return "expense", "💊 Здоровье"
    if any(x in d for x in ("SUPERMARKET", "ПРОДУКТ", "MAGTI", "CARREFOUR", "GOODWILL")):
        return "expense", "🛒 Продукты"
    if any(x in d for x in ("CAFE", "RESTAURANT", "COFFEE", "STARBUCKS")):
        return "expense", "🍽 Кафе"

    if default_direction == "transfer":
        return "expense", INTERNAL_TRANSFER
    return default_direction, "📌 Разное"
