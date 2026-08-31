import asyncio
from django.core.management.base import BaseCommand
from bot.main import run

class Command(BaseCommand):
    help = 'Запуск бота'

    def handle(self, *args, **options):
        self.stdout.write('Bot started')
        asyncio.run(run())