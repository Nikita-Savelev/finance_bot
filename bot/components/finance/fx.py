"""Курсы валют к USD: sync из API и конвертация.

Схема rate: сколько единиц quote за 1 USD (как в exchangerate API).
amount_usd = amount_quote / rate
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import aiohttp
from asgiref.sync import sync_to_async
from loguru import logger

DEFAULT_FX_API_URL = "https://api.exchangerate.fun/latest?base=USD"
DEFAULT_INTERVAL_SEC = 3600


def _fx_api_url() -> str:
    return os.getenv("FX_API_URL") or DEFAULT_FX_API_URL


def _fx_interval_sec() -> int:
    raw = os.getenv("FX_SYNC_INTERVAL_SEC") or str(DEFAULT_INTERVAL_SEC)
    try:
        return max(60, int(raw))
    except ValueError:
        return DEFAULT_INTERVAL_SEC


@sync_to_async
def _upsert_rates(rates: dict[str, Any], source: str, fetched_at: datetime) -> int:
    from core.models import CurrencyRate

    count = 0
    for quote, value in rates.items():
        code = str(quote).upper().strip()
        if not code or code == "USD":
            continue
        try:
            rate = Decimal(str(value))
        except Exception:
            continue
        if rate <= 0:
            continue
        CurrencyRate.objects.update_or_create(
            quote=code,
            defaults={
                "rate": rate,
                "fetched_at": fetched_at,
                "source": source,
            },
        )
        count += 1
    # USD к себе
    CurrencyRate.objects.update_or_create(
        quote="USD",
        defaults={
            "rate": Decimal("1"),
            "fetched_at": fetched_at,
            "source": source,
        },
    )
    return count + 1


async def fetch_and_store_rates(session: aiohttp.ClientSession | None = None) -> int:
    """Тянет курсы и пишет в БД. Возвращает число upsert-нутых валют."""
    url = _fx_api_url()
    own_session = session is None
    if own_session:
        session = aiohttp.ClientSession()
    assert session is not None
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            resp.raise_for_status()
            payload = await resp.json(content_type=None)
    finally:
        if own_session:
            await session.close()

    rates = payload.get("rates") or {}
    if not isinstance(rates, dict) or not rates:
        raise ValueError(f"FX API: пустой rates в ответе ({url})")

    source = "exchangerate.fun"
    if "exchangerate" in url:
        source = url.split("/")[2] if "://" in url else "fx_api"

    fetched_at = datetime.now(timezone.utc)
    # timestamp от API, если есть
    ts = payload.get("timestamp")
    if isinstance(ts, (int, float)):
        fetched_at = datetime.fromtimestamp(ts, tz=timezone.utc)

    n = await _upsert_rates(rates, source=source, fetched_at=fetched_at)
    logger.info(f"FX sync: обновлено {n} курсов ({source})")
    return n


@sync_to_async
def get_rate(quote: str) -> Decimal | None:
    from core.models import CurrencyRate

    code = (quote or "").upper().strip()
    if code == "USD":
        return Decimal("1")
    row = CurrencyRate.objects.filter(quote=code).first()
    return row.rate if row else None


@sync_to_async
def get_rates_fetched_at() -> datetime | None:
    from core.models import CurrencyRate

    row = CurrencyRate.objects.order_by("-fetched_at").first()
    return row.fetched_at if row else None


async def to_usd(amount: Decimal | float | str, currency: str) -> Decimal | None:
    """Конвертация в USD. None если курса нет."""
    code = (currency or "").upper().strip()
    amt = Decimal(str(amount))
    if code == "USD":
        return amt
    rate = await get_rate(code)
    if rate is None or rate == 0:
        return None
    return (amt / rate).quantize(Decimal("0.01"))


async def fx_sync_loop(stop_event: asyncio.Event | None = None) -> None:
    """Фоновый цикл: сразу sync, затем каждый час."""
    interval = _fx_interval_sec()
    logger.info(f"FX sync loop started, interval={interval}s")
    while True:
        try:
            await fetch_and_store_rates()
        except Exception as exc:
            logger.warning(f"FX sync failed: {exc}")
        if stop_event is None:
            await asyncio.sleep(interval)
        else:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval)
                break
            except asyncio.TimeoutError:
                continue
