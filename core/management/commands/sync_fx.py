from django.core.management.base import BaseCommand
from asgiref.sync import async_to_sync

from bot.components.finance.fx import fetch_and_store_rates


class Command(BaseCommand):
    help = "Однократно обновить курсы валют к USD"

    def handle(self, *args, **options):
        n = async_to_sync(fetch_and_store_rates)()
        self.stdout.write(self.style.SUCCESS(f"Обновлено курсов: {n}"))
