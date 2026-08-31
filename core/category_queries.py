from __future__ import annotations

from django.db.models import Q, QuerySet

from core.models import Category, CategoryHide, CategoryKind, Users


def visible_categories_for_user(
    user: Users,
    *,
    kind: str | CategoryKind | None = None,
) -> QuerySet[Category]:
    """Базовые (не скрытые) + пользовательские активные."""
    hidden_ids = CategoryHide.objects.filter(user=user).values_list(
        "category_id", flat=True
    )
    qs = Category.objects.filter(is_active=True).filter(
        Q(user=user) | Q(user__isnull=True, is_system=True)
    ).exclude(id__in=hidden_ids)
    if kind is not None:
        qs = qs.filter(kind=kind)
    return qs.order_by("kind", "name")
