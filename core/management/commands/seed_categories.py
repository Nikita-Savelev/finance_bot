from django.core.management.base import BaseCommand

from core.category_seed import seed_base_categories


class Command(BaseCommand):
    help = "Создаёт/обновляет базовые категории (system) по сиду"

    def handle(self, *args, **options):
        created, deactivated, total = seed_base_categories()
        self.stdout.write(
            self.style.SUCCESS(
                f"Базовые категории: создано {created}, "
                f"деактивировано устаревших {deactivated}, в сиде {total}"
            )
        )
