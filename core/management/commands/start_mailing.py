import asyncio
from django.core.management.base import BaseCommand
from bot.mailing_bot import start


class Command(BaseCommand):
    help = 'Запуск рассылок'

    def handle(self, *args, **options):
        self.stdout.write('Mailing_bot started')
        asyncio.run(start())

