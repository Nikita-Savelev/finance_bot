import os

from connectors import postgres_connector
import html
import re
from typing import Callable
import inspect
import requests
from aiogram import types


async def custom_text(default_text, key, formatting_attrs=None, html_escape=True):
    string = await postgres_connector.get_or_create_custom_text(key, default_text)
    string = re.sub("(%)([^s])", r"%%\2", string)
    if not formatting_attrs:
        return string
    else:
        if html_escape:
            formatting_attrs = tuple([html.escape(str(attr)) if attr else None for attr in formatting_attrs])
    try:
        return string % formatting_attrs
    except:
        return default_text % formatting_attrs


async def custom_button(default_text, key):
    return await postgres_connector.get_or_create_custom_button(key, default_text)


def with_user(func: Callable):
    async def wrapper(*args, **kwargs):
        from asgiref.sync import sync_to_async
        from django.db import close_old_connections

        # После рестарта Postgres Django может держать мёртвое соединение
        await sync_to_async(close_old_connections)()
        sig = inspect.signature(func)
        user_id = args[0].from_user.id
        kwargs["pg_user"] = await postgres_connector.get_user_by_id(user_id)
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in sig.parameters}
        return await func(*args, **filtered_kwargs)

    return wrapper

def get_event_data(event: types.Message | types.CallbackQuery):
    if hasattr(event, "data"):
        parts = event.data.split(":", 1)
        return parts[1] if len(parts) > 1 else event.data
    if hasattr(event, "contact") and event.contact:
        return event.contact.phone_number
    return event.text
