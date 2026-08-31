# Generated manually for finance domain models

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Account",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255, verbose_name="Название")),
                ("currency", models.CharField(max_length=16, verbose_name="Валюта")),
                ("bank_label", models.CharField(blank=True, max_length=255, null=True, verbose_name="Банк")),
                ("country", models.CharField(blank=True, max_length=128, null=True, verbose_name="Страна")),
                ("is_active", models.BooleanField(default=True, verbose_name="Активен")),
                ("notes", models.TextField(blank=True, null=True, verbose_name="Заметки")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создан")),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="accounts",
                        to="core.users",
                        verbose_name="Пользователь",
                    ),
                ),
            ],
            options={
                "verbose_name": "Счёт",
                "verbose_name_plural": "Счета",
                "db_table": "accounts",
            },
        ),
        migrations.CreateModel(
            name="Category",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255, verbose_name="Название")),
                (
                    "kind",
                    models.CharField(
                        choices=[("income", "Доход"), ("expense", "Расход"), ("transfer", "Перевод")],
                        max_length=16,
                        verbose_name="Тип",
                    ),
                ),
                ("is_system", models.BooleanField(default=False, verbose_name="Базовая")),
                ("is_active", models.BooleanField(default=True, verbose_name="Активна")),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="categories",
                        to="core.users",
                        verbose_name="Пользователь",
                    ),
                ),
            ],
            options={
                "verbose_name": "Категория",
                "verbose_name_plural": "Категории",
                "db_table": "categories",
            },
        ),
        migrations.CreateModel(
            name="CurrencyRate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quote", models.CharField(max_length=16, unique=True, verbose_name="Валюта")),
                ("rate", models.DecimalField(decimal_places=10, max_digits=24, verbose_name="Курс (quote за 1 USD)")),
                ("fetched_at", models.DateTimeField(verbose_name="Получен")),
                ("source", models.CharField(default="exchangerate.fun", max_length=64, verbose_name="Источник")),
            ],
            options={
                "verbose_name": "Курс валюты",
                "verbose_name_plural": "Курсы валют",
                "db_table": "currency_rates",
            },
        ),
        migrations.CreateModel(
            name="ImportBatch",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("filename", models.CharField(max_length=512, verbose_name="Файл")),
                ("format_hint", models.CharField(blank=True, max_length=128, null=True, verbose_name="Формат")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "В очереди"),
                            ("done", "Готово"),
                            ("failed", "Ошибка"),
                            ("partial", "Частично"),
                        ],
                        default="pending",
                        max_length=16,
                        verbose_name="Статус",
                    ),
                ),
                ("error_message", models.TextField(blank=True, null=True, verbose_name="Ошибка")),
                ("stats_json", models.JSONField(blank=True, null=True, verbose_name="Статистика")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создан")),
                (
                    "account",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="import_batches",
                        to="core.account",
                        verbose_name="Счёт",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="import_batches",
                        to="core.users",
                        verbose_name="Пользователь",
                    ),
                ),
            ],
            options={
                "verbose_name": "Импорт",
                "verbose_name_plural": "Импорты",
                "db_table": "import_batches",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="MonthlyReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("year", models.PositiveIntegerField(verbose_name="Год")),
                ("month", models.PositiveSmallIntegerField(verbose_name="Месяц")),
                ("summary_json", models.JSONField(blank=True, null=True, verbose_name="Сводка")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлён")),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="monthly_reports",
                        to="core.users",
                        verbose_name="Пользователь",
                    ),
                ),
            ],
            options={
                "verbose_name": "Месячный отчёт",
                "verbose_name_plural": "Месячные отчёты",
                "db_table": "monthly_reports",
            },
        ),
        migrations.CreateModel(
            name="Transaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("occurred_at", models.DateField(verbose_name="Дата")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=18, verbose_name="Сумма")),
                ("currency", models.CharField(max_length=16, verbose_name="Валюта")),
                (
                    "direction",
                    models.CharField(
                        choices=[("income", "Доход"), ("expense", "Расход"), ("transfer", "Перевод")],
                        max_length=16,
                        verbose_name="Направление",
                    ),
                ),
                ("description", models.TextField(blank=True, null=True, verbose_name="Описание")),
                (
                    "source",
                    models.CharField(
                        choices=[("manual", "Вручную"), ("import", "Импорт"), ("pdf", "PDF")],
                        default="manual",
                        max_length=16,
                        verbose_name="Источник",
                    ),
                ),
                ("external_id", models.CharField(blank=True, max_length=255, null=True, verbose_name="Внешний id")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создана")),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="transactions",
                        to="core.account",
                        verbose_name="Счёт",
                    ),
                ),
                (
                    "category",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="transactions",
                        to="core.category",
                        verbose_name="Категория",
                    ),
                ),
                (
                    "counterpart_account",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="counterpart_transactions",
                        to="core.account",
                        verbose_name="Счёт-контрагент",
                    ),
                ),
                (
                    "import_batch",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="transactions",
                        to="core.importbatch",
                        verbose_name="Пакет импорта",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="transactions",
                        to="core.users",
                        verbose_name="Пользователь",
                    ),
                ),
            ],
            options={
                "verbose_name": "Транзакция",
                "verbose_name_plural": "Транзакции",
                "db_table": "transactions",
                "ordering": ["-occurred_at", "-id"],
            },
        ),
        migrations.CreateModel(
            name="CategoryHide",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "category",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="hidden_by",
                        to="core.category",
                        verbose_name="Категория",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="hidden_categories",
                        to="core.users",
                        verbose_name="Пользователь",
                    ),
                ),
            ],
            options={
                "verbose_name": "Скрытая категория",
                "verbose_name_plural": "Скрытые категории",
                "db_table": "category_hides",
            },
        ),
        migrations.AddConstraint(
            model_name="account",
            constraint=models.UniqueConstraint(fields=("user", "name"), name="accounts_user_name_uniq"),
        ),
        migrations.AddConstraint(
            model_name="category",
            constraint=models.UniqueConstraint(
                condition=models.Q(user__isnull=True),
                fields=("name",),
                name="categories_system_name_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="category",
            constraint=models.UniqueConstraint(
                condition=models.Q(user__isnull=False),
                fields=("user", "name"),
                name="categories_user_name_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="categoryhide",
            constraint=models.UniqueConstraint(
                fields=("user", "category"),
                name="category_hides_user_category_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="monthlyreport",
            constraint=models.UniqueConstraint(
                fields=("user", "year", "month"),
                name="monthly_reports_user_year_month_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="transaction",
            constraint=models.UniqueConstraint(
                condition=models.Q(external_id__isnull=False),
                fields=("user", "external_id"),
                name="transactions_user_external_id_uniq",
            ),
        ),
        migrations.AddIndex(
            model_name="transaction",
            index=models.Index(fields=["user", "occurred_at"], name="tx_user_occurred_idx"),
        ),
        migrations.AddIndex(
            model_name="transaction",
            index=models.Index(fields=["account", "occurred_at"], name="tx_account_occurred_idx"),
        ),
    ]
