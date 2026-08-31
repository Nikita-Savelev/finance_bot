import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "core",
            "0003_rename_tx_user_occurred_idx_transaction_user_id_3a7681_idx_and_more",
        ),
    ]

    operations = [
        migrations.CreateModel(
            name="CategoryPreference",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "description_key",
                    models.CharField(max_length=500, verbose_name="Ключ описания"),
                ),
                (
                    "description_sample",
                    models.TextField(verbose_name="Пример описания"),
                ),
                (
                    "hit_count",
                    models.PositiveIntegerField(
                        default=1, verbose_name="Раз применено"
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Создано"
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="Обновлено"),
                ),
                (
                    "category",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="preferences",
                        to="core.category",
                        verbose_name="Категория",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="category_preferences",
                        to="core.users",
                        verbose_name="Пользователь",
                    ),
                ),
            ],
            options={
                "verbose_name": "Предпочтение категории",
                "verbose_name_plural": "Предпочтения категорий",
                "db_table": "category_preferences",
            },
        ),
        migrations.AddIndex(
            model_name="categorypreference",
            index=models.Index(
                fields=["user", "description_key"], name="catpref_user_key_idx"
            ),
        ),
        migrations.AddConstraint(
            model_name="categorypreference",
            constraint=models.UniqueConstraint(
                fields=("user", "description_key"),
                name="category_prefs_user_desc_uniq",
            ),
        ),
    ]
