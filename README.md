# finance_bot

Telegram-бот учёта личных финансов: мультивалютные счета, импорт выписок, статистика и автокатегоризация операций.

Стек: **Python 3.12**, **Django ORM**, **aiogram 3**, **PostgreSQL**, **Docker Compose**.

## Возможности

- **Счета** — несколько счетов в разных валютах (USD, RUB и др.)
- **Ручной ввод** — доходы и расходы с категорией и описанием
- **Импорт** — выписки MyCredo (xlsx) и Т-Банк (pdf)
- **Категории** — базовый набор + свои; обучение на правках пользователя
- **Статистика** — по месяцам и счетам, свод в USD с актуальным курсом
- **Курсы** — автообновление раз в час (FX API)
- **Django Admin** — редкие правки и просмотр данных

## Быстрый старт (локально)

Postgres в Docker, бот на хосте — удобно для разработки.

```bash
cp .env.example .env   # заполнить BOT_TOKEN, ADMIN_ID, SECRET_KEY, OPENAI_API_KEY
# пароль PG в .env должен совпадать с docker-compose.yaml

docker compose up -d postgres_db

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_categories

./run_local.sh   # PG_HOST=127.0.0.1, PG_PORT=5434
```

Перезапуск бота: `Ctrl+C` → снова `./run_local.sh`.

## Docker (сервер / полный стек)

```bash
cp .env.example .env
# PG_HOST=postgres_db, PG_PORT=5432 — для compose-сети

docker compose up -d --build
```

Сервисы:

| Сервис | Назначение | Порт |
|--------|------------|------|
| `main_bot` | Telegram-бот | — |
| `django_admin` | Django Admin | 8002 |
| `postgres_db` | PostgreSQL | 5434 → 5432 |

После старта контейнера бота автоматически: migrate, seed категорий, collectstatic.

## Переменные окружения

См. `.env.example`. Обязательные:

| Переменная | Описание |
|------------|----------|
| `BOT_TOKEN` | Токен Telegram-бота |
| `ADMIN_ID` | Telegram ID администратора |
| `SECRET_KEY` | Django secret key |
| `PG_*` | Подключение к Postgres |
| `OPENAI_API_KEY` | Категоризация при импорте |

## Структура проекта

```
bot/                  # aiogram: handlers, keyboards, finance-модули
  components/finance/ # парсеры, FX, статистика, AI-категоризация
core/                 # Django models, migrations, management commands
connectors/           # async-доступ к БД из бота
settings_bot/         # Django settings
docs/                 # продуктовая и техническая документация
```

## Полезные команды

```bash
.venv/bin/python manage.py seed_categories
.venv/bin/python manage.py sync_fx
docker compose logs -f main_bot
```

## Документация

- [docs/OVERVIEW.md](docs/OVERVIEW.md) — продуктовый обзор MVP
- [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) — техтребования и этапы
