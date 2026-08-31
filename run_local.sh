#!/usr/bin/env bash
# Локальный запуск бота. Postgres — только docker: docker compose up -d postgres_db
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -d .venv ]]; then
  echo "Нет .venv — создай: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

# load_dotenv в manage.py не перезапишет уже заданные переменные
export PG_HOST="${PG_HOST:-127.0.0.1}"
export PG_PORT="${PG_PORT:-5434}"

exec .venv/bin/python manage.py start_bot
