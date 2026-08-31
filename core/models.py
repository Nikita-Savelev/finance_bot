from django.db import models
from django.db.models import Q, UniqueConstraint


class CategoryKind(models.TextChoices):
    INCOME = "income", "Доход"
    EXPENSE = "expense", "Расход"
    TRANSFER = "transfer", "Перевод"


class TransactionDirection(models.TextChoices):
    INCOME = "income", "Доход"
    EXPENSE = "expense", "Расход"
    TRANSFER = "transfer", "Перевод"


class TransactionSource(models.TextChoices):
    MANUAL = "manual", "Вручную"
    IMPORT = "import", "Импорт"
    PDF = "pdf", "PDF"


class ImportBatchStatus(models.TextChoices):
    PENDING = "pending", "В очереди"
    DONE = "done", "Готово"
    FAILED = "failed", "Ошибка"
    PARTIAL = "partial", "Частично"


class Users(models.Model):
    tg_id = models.BigIntegerField(verbose_name="Telegram id")
    role = models.CharField(blank=True, null=True, verbose_name="Роль")
    fio = models.CharField(blank=True, null=True, verbose_name="ФИО")
    phone = models.CharField(blank=True, null=True, verbose_name="Телефон")
    email = models.CharField(blank=True, null=True, verbose_name="Почта")
    tg_username = models.CharField(blank=True, null=True, verbose_name="TG username")

    class Meta:
        db_table = "users"
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self):
        return str(self.fio or self.tg_username or self.tg_id)


class Mailings(models.Model):
    id = models.BigAutoField(primary_key=True)
    message = models.CharField(verbose_name="Сообщение")
    mailing_date = models.DateTimeField(blank=True, null=True, verbose_name="Дата отправки")
    complete = models.BooleanField(default=False, verbose_name="Отправленно")
    image = models.ImageField(blank=True, null=True, verbose_name="Фото")

    class Meta:
        db_table = "mailings"
        verbose_name = "Рассылки"
        verbose_name_plural = "Рассылка"


class CustomTexts(models.Model):
    key = models.CharField(verbose_name="Ключ")
    text = models.CharField(blank=True, verbose_name="Текст")

    class Meta:
        db_table = "custom_texts"
        verbose_name = "Текст"
        verbose_name_plural = "Текста в боте"

    def __str__(self):
        return self.text


class CustomButtons(models.Model):
    key = models.CharField(verbose_name="Ключ")
    text = models.CharField(blank=True, verbose_name="Текст")

    class Meta:
        db_table = "custom_buttons"
        verbose_name = "Кнопка"
        verbose_name_plural = "Кнопки"

    def __str__(self):
        return self.text


class Account(models.Model):
    user = models.ForeignKey(
        Users,
        on_delete=models.CASCADE,
        related_name="accounts",
        verbose_name="Пользователь",
    )
    name = models.CharField(max_length=255, verbose_name="Название")
    currency = models.CharField(max_length=16, verbose_name="Валюта")
    bank_label = models.CharField(
        max_length=255, blank=True, null=True, verbose_name="Банк"
    )
    country = models.CharField(
        max_length=128, blank=True, null=True, verbose_name="Страна"
    )
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    notes = models.TextField(blank=True, null=True, verbose_name="Заметки")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")

    class Meta:
        db_table = "accounts"
        verbose_name = "Счёт"
        verbose_name_plural = "Счета"
        constraints = [
            UniqueConstraint(
                fields=["user", "name"],
                name="accounts_user_name_uniq",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.currency})"


class Category(models.Model):
    name = models.CharField(max_length=255, verbose_name="Название")
    kind = models.CharField(
        max_length=16,
        choices=CategoryKind.choices,
        verbose_name="Тип",
    )
    is_system = models.BooleanField(default=False, verbose_name="Базовая")
    user = models.ForeignKey(
        Users,
        on_delete=models.CASCADE,
        related_name="categories",
        blank=True,
        null=True,
        verbose_name="Пользователь",
    )
    is_active = models.BooleanField(default=True, verbose_name="Активна")

    class Meta:
        db_table = "categories"
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
        constraints = [
            UniqueConstraint(
                fields=["name"],
                condition=Q(user__isnull=True),
                name="categories_system_name_uniq",
            ),
            UniqueConstraint(
                fields=["user", "name"],
                condition=Q(user__isnull=False),
                name="categories_user_name_uniq",
            ),
        ]

    def __str__(self):
        scope = "system" if self.is_system else f"user:{self.user_id}"
        return f"{self.name} [{self.kind}/{scope}]"


class CategoryHide(models.Model):
    user = models.ForeignKey(
        Users,
        on_delete=models.CASCADE,
        related_name="hidden_categories",
        verbose_name="Пользователь",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="hidden_by",
        verbose_name="Категория",
    )

    class Meta:
        db_table = "category_hides"
        verbose_name = "Скрытая категория"
        verbose_name_plural = "Скрытые категории"
        constraints = [
            UniqueConstraint(
                fields=["user", "category"],
                name="category_hides_user_category_uniq",
            ),
        ]

    def __str__(self):
        return f"{self.user_id} hides {self.category_id}"


class CategoryPreference(models.Model):
    """Ручные правки категорий: описание → категория (обучение под пользователя)."""

    user = models.ForeignKey(
        Users,
        on_delete=models.CASCADE,
        related_name="category_preferences",
        verbose_name="Пользователь",
    )
    description_key = models.CharField(
        max_length=500, verbose_name="Ключ описания"
    )
    description_sample = models.TextField(verbose_name="Пример описания")
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="preferences",
        verbose_name="Категория",
    )
    hit_count = models.PositiveIntegerField(default=1, verbose_name="Раз применено")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    class Meta:
        db_table = "category_preferences"
        verbose_name = "Предпочтение категории"
        verbose_name_plural = "Предпочтения категорий"
        constraints = [
            UniqueConstraint(
                fields=["user", "description_key"],
                name="category_prefs_user_desc_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["user", "description_key"],
                name="catpref_user_key_idx",
            ),
        ]

    def __str__(self):
        return f"{self.description_key[:40]} → {self.category_id}"


class ImportBatch(models.Model):
    user = models.ForeignKey(
        Users,
        on_delete=models.CASCADE,
        related_name="import_batches",
        verbose_name="Пользователь",
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        related_name="import_batches",
        blank=True,
        null=True,
        verbose_name="Счёт",
    )
    filename = models.CharField(max_length=512, verbose_name="Файл")
    format_hint = models.CharField(
        max_length=128, blank=True, null=True, verbose_name="Формат"
    )
    status = models.CharField(
        max_length=16,
        choices=ImportBatchStatus.choices,
        default=ImportBatchStatus.PENDING,
        verbose_name="Статус",
    )
    error_message = models.TextField(blank=True, null=True, verbose_name="Ошибка")
    stats_json = models.JSONField(blank=True, null=True, verbose_name="Статистика")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")

    class Meta:
        db_table = "import_batches"
        verbose_name = "Импорт"
        verbose_name_plural = "Импорты"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.filename} [{self.status}]"


class Transaction(models.Model):
    user = models.ForeignKey(
        Users,
        on_delete=models.CASCADE,
        related_name="transactions",
        verbose_name="Пользователь",
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="transactions",
        verbose_name="Счёт",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        related_name="transactions",
        blank=True,
        null=True,
        verbose_name="Категория",
    )
    occurred_at = models.DateField(verbose_name="Дата")
    amount = models.DecimalField(
        max_digits=18, decimal_places=2, verbose_name="Сумма"
    )
    currency = models.CharField(max_length=16, verbose_name="Валюта")
    direction = models.CharField(
        max_length=16,
        choices=TransactionDirection.choices,
        verbose_name="Направление",
    )
    description = models.TextField(blank=True, null=True, verbose_name="Описание")
    source = models.CharField(
        max_length=16,
        choices=TransactionSource.choices,
        default=TransactionSource.MANUAL,
        verbose_name="Источник",
    )
    import_batch = models.ForeignKey(
        ImportBatch,
        on_delete=models.SET_NULL,
        related_name="transactions",
        blank=True,
        null=True,
        verbose_name="Пакет импорта",
    )
    external_id = models.CharField(
        max_length=255, blank=True, null=True, verbose_name="Внешний id"
    )
    counterpart_account = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        related_name="counterpart_transactions",
        blank=True,
        null=True,
        verbose_name="Счёт-контрагент",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создана")

    class Meta:
        db_table = "transactions"
        verbose_name = "Транзакция"
        verbose_name_plural = "Транзакции"
        ordering = ["-occurred_at", "-id"]
        constraints = [
            UniqueConstraint(
                fields=["user", "external_id"],
                condition=Q(external_id__isnull=False),
                name="transactions_user_external_id_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "occurred_at"]),
            models.Index(fields=["account", "occurred_at"]),
        ]

    def __str__(self):
        return f"{self.occurred_at} {self.direction} {self.amount} {self.currency}"


class MonthlyReport(models.Model):
    user = models.ForeignKey(
        Users,
        on_delete=models.CASCADE,
        related_name="monthly_reports",
        verbose_name="Пользователь",
    )
    year = models.PositiveIntegerField(verbose_name="Год")
    month = models.PositiveSmallIntegerField(verbose_name="Месяц")
    summary_json = models.JSONField(blank=True, null=True, verbose_name="Сводка")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлён")

    class Meta:
        db_table = "monthly_reports"
        verbose_name = "Месячный отчёт"
        verbose_name_plural = "Месячные отчёты"
        constraints = [
            UniqueConstraint(
                fields=["user", "year", "month"],
                name="monthly_reports_user_year_month_uniq",
            ),
        ]

    def __str__(self):
        return f"{self.month:02d}.{self.year} user={self.user_id}"


class CurrencyRate(models.Model):
    """Курс: сколько единиц quote за 1 USD (как в exchangerate API)."""

    quote = models.CharField(max_length=16, unique=True, verbose_name="Валюта")
    rate = models.DecimalField(
        max_digits=24, decimal_places=10, verbose_name="Курс (quote за 1 USD)"
    )
    fetched_at = models.DateTimeField(verbose_name="Получен")
    source = models.CharField(max_length=64, default="exchangerate.fun", verbose_name="Источник")

    class Meta:
        db_table = "currency_rates"
        verbose_name = "Курс валюты"
        verbose_name_plural = "Курсы валют"

    def __str__(self):
        return f"1 USD = {self.rate} {self.quote}"
