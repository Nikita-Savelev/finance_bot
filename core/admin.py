from django.contrib import admin
from django.db import models
from django.forms import ModelForm
from django.forms.widgets import Textarea

from .models import (
    Account,
    Category,
    CategoryHide,
    CategoryPreference,
    CurrencyRate,
    CustomButtons,
    CustomTexts,
    ImportBatch,
    Mailings,
    MonthlyReport,
    Transaction,
    Users,
)


@admin.register(Users)
class UserAdmin(admin.ModelAdmin):
    list_display = ("id", "tg_id", "fio", "tg_username", "role")
    search_fields = ("tg_id", "fio", "tg_username")


@admin.register(CustomTexts)
class CustomTextsAdmin(admin.ModelAdmin):
    list_display = ("key", "text")
    search_fields = ("key",)
    formfield_overrides = {
        models.CharField: {"widget": Textarea(attrs={"rows": 10, "cols": 80})},
    }


@admin.register(CustomButtons)
class CustomButtonsAdmin(admin.ModelAdmin):
    list_display = ("key", "text")
    search_fields = ("key",)
    formfield_overrides = {
        models.CharField: {"widget": Textarea(attrs={"rows": 10, "cols": 80})},
    }


class MailingsForm(ModelForm):
    class Meta:
        model = Mailings
        exclude = ["id", "complete"]


@admin.register(Mailings)
class MailingsAdmin(admin.ModelAdmin):
    form = MailingsForm
    list_display = ("id", "message", "complete")


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "name", "currency", "bank_label", "country", "is_active")
    list_filter = ("currency", "is_active", "country")
    search_fields = ("name", "bank_label", "user__tg_id", "user__fio")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "kind", "is_system", "user", "is_active")
    list_filter = ("kind", "is_system", "is_active")
    search_fields = ("name",)


@admin.register(CategoryHide)
class CategoryHideAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "category")
    search_fields = ("user__tg_id", "category__name")


@admin.register(CategoryPreference)
class CategoryPreferenceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "description_key",
        "category",
        "hit_count",
        "updated_at",
    )
    list_filter = ("category",)
    search_fields = ("description_key", "description_sample", "user__tg_id")


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "filename", "account", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("filename", "user__tg_id")
    readonly_fields = ("created_at",)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "occurred_at",
        "user",
        "account",
        "direction",
        "amount",
        "currency",
        "category",
        "source",
    )
    list_filter = ("direction", "source", "currency")
    search_fields = ("description", "external_id", "user__tg_id")
    date_hierarchy = "occurred_at"
    raw_id_fields = ("user", "account", "category", "import_batch", "counterpart_account")


@admin.register(MonthlyReport)
class MonthlyReportAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "year", "month", "updated_at")
    list_filter = ("year", "month")
    search_fields = ("user__tg_id",)


@admin.register(CurrencyRate)
class CurrencyRateAdmin(admin.ModelAdmin):
    list_display = ("quote", "rate", "fetched_at", "source")
    search_fields = ("quote",)
    ordering = ("quote",)
