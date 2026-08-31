"""Базовые категории (сид) — короткие имена со смайлами."""

from __future__ import annotations

# (name, kind) — kind: income | expense | transfer
BASE_CATEGORIES: list[tuple[str, str]] = [
    ("🔁 Переводы", "expense"),
    ("💊 Здоровье", "expense"),
    ("🛒 Продукты", "expense"),
    ("💵 Наличные", "expense"),
    ("🛍 Шопинг", "expense"),
    ("🍽 Кафе", "expense"),
    ("🍔 Фастфуд", "expense"),
    ("🛵 Доставка", "expense"),
    ("💱 Обмен", "expense"),
    ("🏦 Инкассо", "expense"),
    ("🏋️ Спорт", "expense"),
    ("🎮 Развлечения", "expense"),
    ("💇 Салон", "expense"),
    ("📦 Маркетплейсы", "expense"),
    ("🚕 Такси", "expense"),
    ("💻 IDE", "expense"),
    ("☁️ Google One", "expense"),
    ("🏧 Комиссии", "expense"),
    ("📌 Разное", "expense"),
    ("💳 Прочее", "expense"),
    ("💼 Зарплата", "income"),
    ("📈 Проценты", "income"),
    ("➕ Поступления", "income"),
]

# старые длинные имена → новые (переименование in-place, FK сохраняются)
CATEGORY_RENAMES: dict[str, str] = {
    "Внутренние переводы (не траты)": "🔁 Переводы",
    "Здоровье: клиники, анализы, аптеки": "💊 Здоровье",
    "Продукты: супермаркеты": "🛒 Продукты",
    "Наличные: снятие в банкомате": "💵 Наличные",
    "Одежда и товары (шопинг)": "🛍 Шопинг",
    "Еда вне дома: кафе и рестораны": "🍽 Кафе",
    "Фастфуд": "🍔 Фастфуд",
    "Доставка еды (Яндекс)": "🛵 Доставка",
    "Обмен валюты": "💱 Обмен",
    "Инкассо / конвертация": "🏦 Инкассо",
    "Спорт и досуг": "🏋️ Спорт",
    "Развлечения и подписки (игры, стриминг)": "🎮 Развлечения",
    "Услуги: салон, барбершоп": "💇 Салон",
    "Маркетплейсы": "📦 Маркетплейсы",
    "Такси": "🚕 Такси",
    "Подписки: Google One": "☁️ Google One",
    "Комиссии банка": "🏧 Комиссии",
    "Разное": "📌 Разное",
    "Прочие карточные платежи": "💳 Прочее",
    "Доход: услуги / зарплатный перевод": "💼 Зарплата",
    "Доход: проценты": "📈 Проценты",
    "Прочие поступления": "➕ Поступления",
    # без смайла → со смайлом (если уже укоротили раньше)
    "Переводы": "🔁 Переводы",
    "Здоровье": "💊 Здоровье",
    "Продукты": "🛒 Продукты",
    "Наличные": "💵 Наличные",
    "Шопинг": "🛍 Шопинг",
    "Кафе": "🍽 Кафе",
    "Доставка": "🛵 Доставка",
    "Обмен": "💱 Обмен",
    "Инкассо": "🏦 Инкассо",
    "Спорт": "🏋️ Спорт",
    "Развлечения": "🎮 Развлечения",
    "Салон": "💇 Салон",
    "Google One": "☁️ Google One",
    "Комиссии": "🏧 Комиссии",
    "Прочее": "💳 Прочее",
    "Зарплата": "💼 Зарплата",
    "Проценты": "📈 Проценты",
    "Поступления": "➕ Поступления",
}


def seed_base_categories() -> tuple[int, int, int]:
    """Переименовывает старые, создаёт недостающие, деактивирует лишние.

    Returns (created, deactivated, total_in_seed).
    """
    from core.models import Category

    for old_name, new_name in CATEGORY_RENAMES.items():
        if old_name == new_name:
            continue
        # если новая уже есть — просто гасим старую
        if Category.objects.filter(name=new_name, user__isnull=True).exists():
            Category.objects.filter(
                name=old_name, user__isnull=True, is_system=True
            ).update(is_active=False)
            continue
        Category.objects.filter(name=old_name, user__isnull=True).update(
            name=new_name, is_system=True, is_active=True
        )

    seed_names = {name for name, _ in BASE_CATEGORIES}
    created = 0
    for name, kind in BASE_CATEGORIES:
        obj, was_created = Category.objects.get_or_create(
            name=name,
            user=None,
            defaults={
                "kind": kind,
                "is_system": True,
                "is_active": True,
            },
        )
        if was_created:
            created += 1
        else:
            changed = False
            if obj.kind != kind:
                obj.kind = kind
                changed = True
            if not obj.is_active:
                obj.is_active = True
                changed = True
            if not obj.is_system:
                obj.is_system = True
                changed = True
            if changed:
                obj.save(update_fields=["kind", "is_active", "is_system"])

    deactivated = Category.objects.filter(
        user__isnull=True, is_system=True, is_active=True
    ).exclude(name__in=seed_names).update(is_active=False)

    # Переводы — обычная категория расходов (без отдельного direction=transfer)
    _normalize_transfers_as_expense()

    return created, deactivated, len(BASE_CATEGORIES)


def _normalize_transfers_as_expense() -> None:
    from core.models import Category, Transaction

    transfer_cat = Category.objects.filter(
        name="🔁 Переводы", user__isnull=True
    ).first()
    if not transfer_cat:
        return
    if transfer_cat.kind != "expense":
        transfer_cat.kind = "expense"
        transfer_cat.save(update_fields=["kind"])

    qs = Transaction.objects.filter(direction="transfer")
    qs.filter(category_id__isnull=True).update(category_id=transfer_cat.id)
    qs.update(direction="expense")
