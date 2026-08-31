# Stub: эта миграция уже применена в БД (rename индексов Transaction).
# Операции пустые — индексы уже имеют новые имена.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_finance_domain"),
    ]

    operations = []
