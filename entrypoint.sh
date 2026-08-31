#!/bin/sh
set -e
echo "Migration started"
python manage.py migrate --noinput
echo "migration - ok"
python manage.py seed_categories
echo "seed_categories - ok"
python manage.py collectstatic --noinput
echo "collectstatic - OK"
echo "Starting bot..."
python manage.py start_bot
