from core.models import (
    Users,
    Account,
    CustomTexts,
    CustomButtons,
)
from asgiref.sync import sync_to_async
from django.db import IntegrityError


def build_model_object(model_obj, **field_values):
    model_fields = {field.name for field in model_obj._meta.get_fields()}
    for field, value in field_values.items():
        if field in model_fields:
            setattr(model_obj, field, value)
    model_obj.save()
    return model_obj


@sync_to_async
def add_user(field_values):
    return build_model_object(Users(), **field_values)


@sync_to_async
def get_user_by_id(user_id):
    return Users.objects.filter(tg_id=user_id).first()


@sync_to_async
def get_or_create_custom_text(key, default_text):
    try:
        return CustomTexts.objects.get(key=key).text
    except CustomTexts.DoesNotExist:
        custom_text = CustomTexts(key=key, text=default_text)
        custom_text.save()
        return default_text


@sync_to_async
def get_or_create_custom_button(key, default_text):
    try:
        button = CustomButtons.objects.get(key=key)
        return button.text
    except CustomButtons.DoesNotExist:
        custom_button = CustomButtons(key=key, text=default_text)
        custom_button.save()
        return default_text


@sync_to_async
def list_accounts(user_id: int, *, active_only: bool = True):
    qs = Account.objects.filter(user_id=user_id).order_by("name")
    if active_only:
        qs = qs.filter(is_active=True)
    return list(qs)


@sync_to_async
def get_account(user_id: int, account_id: int):
    return Account.objects.filter(user_id=user_id, id=account_id).first()


@sync_to_async
def create_account(user_id: int, **fields):
    """Returns (account, error_message)."""
    try:
        acc = Account(user_id=user_id, **fields)
        acc.save()
        return acc, None
    except IntegrityError:
        return None, "Счёт с таким названием уже есть."


@sync_to_async
def set_account_active(user_id: int, account_id: int, is_active: bool) -> bool:
    updated = Account.objects.filter(user_id=user_id, id=account_id).update(
        is_active=is_active
    )
    return bool(updated)


@sync_to_async
def delete_account(user_id: int, account_id: int):
    acc = Account.objects.filter(user_id=user_id, id=account_id).first()
    if not acc:
        return False, "Счёт не найден."
    if acc.transactions.exists():
        return False, "На счёте есть операции — можно только скрыть."
    acc.delete()
    return True, None


@sync_to_async
def list_visible_categories(user_id: int, kind: str | None = None):
    from core.category_queries import visible_categories_for_user
    from core.models import Users

    user = Users.objects.filter(id=user_id).first()
    if not user:
        return []
    return list(visible_categories_for_user(user, kind=kind))


@sync_to_async
def create_transaction(user_id: int, **fields):
    from core.models import Transaction

    tx = Transaction(user_id=user_id, **fields)
    tx.save()
    return (
        Transaction.objects.select_related("account", "category")
        .filter(id=tx.id)
        .first()
    )


@sync_to_async
def list_recent_transactions(user_id: int, limit: int = 15):
    from core.models import Transaction

    return list(
        Transaction.objects.filter(user_id=user_id)
        .select_related("account", "category")
        .order_by("-occurred_at", "-id")[:limit]
    )


@sync_to_async
def get_transaction(user_id: int, tx_id: int):
    from core.models import Transaction

    return (
        Transaction.objects.filter(user_id=user_id, id=tx_id)
        .select_related("account", "category")
        .first()
    )


@sync_to_async
def update_transaction(user_id: int, tx_id: int, **fields):
    from core.models import Transaction

    allowed = {
        "category_id",
        "occurred_at",
        "amount",
        "description",
        "direction",
        "account_id",
        "currency",
    }
    payload = {k: v for k, v in fields.items() if k in allowed}
    if not payload:
        return (
            Transaction.objects.filter(user_id=user_id, id=tx_id)
            .select_related("account", "category")
            .first()
        )
    updated = Transaction.objects.filter(user_id=user_id, id=tx_id).update(**payload)
    if not updated:
        return None
    return (
        Transaction.objects.filter(user_id=user_id, id=tx_id)
        .select_related("account", "category")
        .first()
    )


@sync_to_async
def delete_transaction(user_id: int, tx_id: int) -> bool:
    from core.models import Transaction

    deleted, _ = Transaction.objects.filter(user_id=user_id, id=tx_id).delete()
    return bool(deleted)

@sync_to_async
def get_category_for_user(user_id: int, category_id: int):
    """Returns (category, is_hidden) or (None, False)."""
    from core.models import Category, CategoryHide
    from django.db.models import Q

    cat = (
        Category.objects.filter(id=category_id)
        .filter(Q(user_id=user_id) | Q(user__isnull=True, is_system=True))
        .first()
    )
    if not cat:
        return None, False
    hidden = CategoryHide.objects.filter(
        user_id=user_id, category_id=category_id
    ).exists()
    return cat, hidden


@sync_to_async
def create_user_category(user_id: int, name: str, kind: str):
    from core.models import Category
    from django.db import IntegrityError

    try:
        cat = Category(
            name=name.strip(),
            kind=kind,
            user_id=user_id,
            is_system=False,
            is_active=True,
        )
        cat.save()
        return cat, None
    except IntegrityError:
        return None, "Категория с таким названием уже есть."


@sync_to_async
def hide_category(user_id: int, category_id: int):
    from core.models import Category, CategoryHide

    cat = Category.objects.filter(
        id=category_id, user__isnull=True, is_system=True, is_active=True
    ).first()
    if not cat:
        return False, "Скрыть можно только базовую категорию."
    CategoryHide.objects.get_or_create(user_id=user_id, category_id=category_id)
    return True, None


@sync_to_async
def unhide_category(user_id: int, category_id: int) -> bool:
    from core.models import CategoryHide

    deleted, _ = CategoryHide.objects.filter(
        user_id=user_id, category_id=category_id
    ).delete()
    return bool(deleted)


@sync_to_async
def delete_user_category(user_id: int, category_id: int):
    from core.models import Category, Transaction

    cat = Category.objects.filter(
        id=category_id, user_id=user_id, is_system=False
    ).first()
    if not cat:
        return False, "Удалить можно только свою категорию."
    if Transaction.objects.filter(category_id=category_id).exists():
        return False, "Категория используется в операциях — сначала смените их."
    cat.delete()
    return True, None


@sync_to_async
def list_hidden_categories(user_id: int):
    from core.models import Category

    return list(
        Category.objects.filter(
            hidden_by__user_id=user_id, is_system=True
        ).order_by("kind", "name")
    )


@sync_to_async
def create_import_batch(user_id: int, account_id: int, filename: str, format_hint: str = ""):
    from core.models import ImportBatch, ImportBatchStatus

    batch = ImportBatch(
        user_id=user_id,
        account_id=account_id,
        filename=filename,
        format_hint=format_hint or None,
        status=ImportBatchStatus.PENDING,
    )
    batch.save()
    return batch


@sync_to_async
def finish_import_batch(batch_id: int, *, status: str, stats: dict | None = None, error: str | None = None):
    from core.models import ImportBatch

    ImportBatch.objects.filter(id=batch_id).update(
        status=status,
        stats_json=stats,
        error_message=error,
    )


@sync_to_async
def resolve_category_id(user_id: int, hint: str | None, kind: str):
    """Find visible category by exact name hint."""
    if not hint:
        return None
    from core.category_queries import visible_categories_for_user
    from core.models import Users

    user = Users.objects.filter(id=user_id).first()
    if not user:
        return None
    qs = visible_categories_for_user(user, kind=kind).filter(name=hint)
    cat = qs.first()
    return cat.id if cat else None


@sync_to_async
def import_parsed_transactions(user_id: int, account_id: int, batch_id: int, parsed_list: list):
    """Create transactions with dedup by external_id. parsed_list: list of dicts."""
    from core.models import Transaction, TransactionSource
    from django.db import IntegrityError

    created = 0
    duplicates = 0
    failed = 0
    for item in parsed_list:
        try:
            if item.get("external_id"):
                exists = Transaction.objects.filter(
                    user_id=user_id, external_id=item["external_id"]
                ).exists()
                if exists:
                    duplicates += 1
                    continue
            Transaction.objects.create(
                user_id=user_id,
                account_id=account_id,
                category_id=item.get("category_id"),
                occurred_at=item["occurred_at"],
                amount=item["amount"],
                currency=item["currency"],
                direction=item["direction"],
                description=item.get("description") or None,
                source=TransactionSource.IMPORT,
                import_batch_id=batch_id,
                external_id=item.get("external_id"),
            )
            created += 1
        except IntegrityError:
            duplicates += 1
        except Exception:
            failed += 1
    return {"created": created, "duplicates": duplicates, "failed": failed, "total": len(parsed_list)}


@sync_to_async
def upsert_category_preference(user_id: int, description: str | None, category_id: int):
    """Сохранить/обновить правило описание → категория."""
    from core.models import CategoryPreference
    from bot.components.finance.category_prefs import description_key
    from django.db.models import F

    key = description_key(description)
    if not key:
        return None
    sample = " ".join((description or "").split())[:500]
    obj, created = CategoryPreference.objects.get_or_create(
        user_id=user_id,
        description_key=key,
        defaults={
            "description_sample": sample,
            "category_id": category_id,
            "hit_count": 1,
        },
    )
    if not created:
        CategoryPreference.objects.filter(id=obj.id).update(
            category_id=category_id,
            description_sample=sample,
            hit_count=F("hit_count") + 1,
        )
        obj.refresh_from_db()
    return obj


@sync_to_async
def list_category_preferences(user_id: int) -> list[dict]:
    """Список предпочтений для промпта: [{key, sample, category_name}, ...]"""
    from core.models import CategoryPreference

    rows = (
        CategoryPreference.objects.filter(user_id=user_id)
        .select_related("category")
        .order_by("-updated_at")[:200]
    )
    return [
        {
            "key": r.description_key,
            "sample": r.description_sample,
            "category_name": r.category.name,
            "category_id": r.category_id,
        }
        for r in rows
        if r.category_id and r.category.is_active
    ]


@sync_to_async
def count_similar_transactions_in_month(
    user_id: int,
    description: str | None,
    *,
    year: int,
    month: int,
    exclude_tx_id: int | None = None,
    category_id: int | None = None,
) -> int:
    """Сколько операций с тем же описанием в месяце (опционально ещё не с этой категорией)."""
    from calendar import monthrange
    from datetime import date
    from core.models import Transaction
    from bot.components.finance.category_prefs import description_key

    key = description_key(description)
    if not key:
        return 0
    d_from = date(year, month, 1)
    d_to = date(year, month, monthrange(year, month)[1])
    qs = Transaction.objects.filter(
        user_id=user_id,
        occurred_at__gte=d_from,
        occurred_at__lte=d_to,
    ).exclude(description__isnull=True).exclude(description="")
    if exclude_tx_id:
        qs = qs.exclude(id=exclude_tx_id)
    if category_id is not None:
        qs = qs.exclude(category_id=category_id)
    # точное сопоставление через нормализацию в Python (описаний за месяц немного)
    count = 0
    for desc in qs.values_list("description", flat=True):
        if description_key(desc) == key:
            count += 1
    return count


@sync_to_async
def apply_category_to_similar_in_month(
    user_id: int,
    description: str | None,
    category_id: int,
    *,
    year: int,
    month: int,
    exclude_tx_id: int | None = None,
) -> int:
    """Проставить категорию всем с тем же описанием за месяц. Returns updated count."""
    from calendar import monthrange
    from datetime import date
    from core.models import Transaction
    from bot.components.finance.category_prefs import description_key

    key = description_key(description)
    if not key:
        return 0
    d_from = date(year, month, 1)
    d_to = date(year, month, monthrange(year, month)[1])
    qs = Transaction.objects.filter(
        user_id=user_id,
        occurred_at__gte=d_from,
        occurred_at__lte=d_to,
    ).exclude(description__isnull=True).exclude(description="")
    if exclude_tx_id:
        qs = qs.exclude(id=exclude_tx_id)
    ids = [
        tid
        for tid, desc in qs.values_list("id", "description")
        if description_key(desc) == key
    ]
    if not ids:
        return 0
    return Transaction.objects.filter(id__in=ids, user_id=user_id).update(
        category_id=category_id
    )
