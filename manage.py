#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from dotenv import load_dotenv
# from django.core.management.base import BaseCommand
# import asyncio

load_dotenv()


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings_bot.settings')
    load_dotenv()
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)

#
# class Command(BaseCommand):
#     help = 'Start the bot'
#
#     def handle(self, *args, **options):
#         from bot.main import run
#         asyncio.run(run())
#         self.stdout.write('Bot started successfully')


# from django.core.management import execute_from_command_line
# from django.core.management.commands import start_bot
#
# start_bot.Command()

if __name__ == '__main__':
    # execute_from_command_line()
    main()
