"""Категоризация импорта через OpenAI — один запрос на весь батч."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Sequence

import aiohttp
from loguru import logger

from bot.components.finance.parsers.base import ParsedTransaction


FALLBACK_BY_KIND = {
    "expense": "📌 Разное",
    "income": "➕ Поступления",
    "transfer": "🔁 Переводы",
}

# Краткие подсказки для модели (ключи = актуальные имена категорий)
CATEGORY_HINTS: dict[str, str] = {
    "🔁 Переводы": (
        "Переводы между своими счетами / картами; автопополнение; "
        "внешний перевод по телефону/карте; перевод себе; "
        "საკუთარ ანგარიშებს შორის"
    ),
    "💊 Здоровье": (
        "Аптеки (PHARM, PARMA, FAMILY PHARM, NATALI PHARM, GEDEON RICHTER), "
        "лаборатории (CITO LAB), клиники, стоматология (PERFECT SMILE)"
    ),
    "🛒 Продукты": (
        "Продуктовые сети: YEREVAN CITY, SAS, SUPERMARKET, GROCERY, "
        "21 MARKET, SHANE MARKET, Carrefour, Goodwill"
    ),
    "💵 Наличные": "ATM, განაღდება, снятие наличных",
    "🛍 Шопинг": "NEW BALANCE, RED STORE, MINISO, FIX PRICE, одежда/товары",
    "🍽 Кафе": (
        "Только кафе/рестораны/бары: CAFE, RESTAURANT, COFFEE, PAUL, "
        "THE TOAST, WINE, CHAYKA, ALTAR, ZERO FOOD. НЕ продукты и НЕ неизвестные"
    ),
    "🍔 Фастфуд": "HOT-DOGS, CHEBUREK, McDonalds, KFC — НЕ Yandex Go / *4121*GO",
    "🛵 Доставка": "Yandex.Eda / Яндекс.Еда / *5814*EDA — НЕ Yandex Go",
    "💱 Обмен": "ОБМЕН ВАЛЮТ, უნაღდო კონვერტაცია",
    "🏦 Инкассо": "Инкассо, прочая банковская конвертация",
    "🏋️ Спорт": "Gym, THE ONE GYM, фитнес",
    "🐱 Кошка": (
        "Зоомагазины и товары для кошки: KAKADU, VET EXPRESS, Pet City, Animania, "
        "4 Лапы, Бетховен, корма, наполнитель"
    ),
    "🎮 Развлечения": (
        "Steam, игры, кино (CINEMASTAR), SHOW4ME, CYBERCAFE, CYBER ARENA, LEDZ"
    ),
    "💇 Салон": "GLOBAL BEAUTY, барбершоп, салон — НЕ развлечения",
    "📦 Маркетплейсы": "Ozon, Wildberries, WB, Amazon",
    "🚕 Такси": "Yandex Go/Taxi, YANDEX*4121*GO, Uber, Bolt — поездки, не еда",
    "💻 IDE": "AI POWERED IDE — подписка на редактор кода",
    "☁️ Google One": "Только Google One",
    "🏧 Комиссии": "საკომისიო, комиссия банка",
    "📌 Разное": (
        "Неочевидное: MG NERSISYAN, штрафы, CONTABO/хостинг. "
        "НЕ IDE-подписки и НЕ Google One. Лучше Разное, чем угадывать кафе"
    ),
    "💳 Прочее": "Запасная для неопознанных карточных списаний",
    "💼 Зарплата": (
        "BACKEND DEVELOPMENT, договор, payroll. НЕ обычное пополнение карты"
    ),
    "📈 Проценты": "Проценты по вкладу, საპროცენტო",
    "➕ Поступления": (
        "Пополнение карты (ბარათზე თანხის ჩარიცხვა), возвраты, прочие кредиты"
    ),
}

SYSTEM_PROMPT = """\
You are a careful personal-finance categorizer for bank statement imports \
(MyCredo / Tinkoff / mixed merchants in EN, RU, KA, HY).

Rules (strict):
1. Assign EVERY transaction exactly ONE category from the provided list. \
Use the exact "name" string (including emoji).
2. Prefer specific categories over vague ones. If unsure → "📌 Разное" \
(or "💳 Прочее"). NEVER dump unknowns into "🍽 Кафе".
3. Merchant keywords in description outweigh bank_side guesses.
4. Georgian markers:
   - განაღდება / ATM → 💵 Наличные
   - საკომისიო → 🏧 Комиссии
   - უნაღდო კონვერტაცია → 💱 Обмен
   - ბარათზე თანხის ჩარიცხვა → ➕ Поступления (not salary)
5. Supermarkets (YEREVAN CITY*, SAS, GROCERY, SUPERMARKET, 21 MARKET) → 🛒 Продукты
6. Pharmacies / labs / dental (PHARM, PARMA, CITO, PERFECT SMILE) → 💊 Здоровье
7. KAKADU, VET EXPRESS and other pet supply stores → 🐱 Кошка (NOT Здоровье, NOT Разное)
8. Contabo / hosting / non-Google-One SaaS → 📌 Разное (NOT Google One)
9. Google One only if description clearly says Google One → ☁️ Google One
10. AI POWERED IDE → always 💻 IDE
11. GLOBAL BEAUTY / barbershop / beauty salon → 💇 Салон (not entertainment)
12. bank_side=income with salary/contract → 💼 Зарплата; \
generic card top-up → ➕ Поступления
13. Transfers → 🔁 Переводы; keep bank_side (income if credit / expense if debit)
14. YANDEX*4121*GO, YANDEX GO, taxi → 🚕 Такси (NOT фастфуд, NOT доставка)
15. Obey user_learned_rules in the payload as absolute overrides for matching descriptions

Respond with JSON only:
{"assignments":[{"i":0,"category":"<exact name>"}, ...]}
One entry per transaction index, no extras.
"""


@dataclass
class CategoryOption:
    name: str
    kind: str  # income | expense | transfer


@dataclass
class AiCategorizeResult:
    """hints[i] = category name for transactions[i]; None = keep existing."""

    hints: list[str | None]
    used_ai: bool
    error: str | None = None


def _openai_config() -> tuple[str | None, str]:
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    model = (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()
    return key or None, model


def _build_payload(
    transactions: Sequence[ParsedTransaction],
    categories: Sequence[CategoryOption],
    user_prefs: Sequence[dict] | None = None,
) -> dict:
    cats = []
    for c in categories:
        item = {"name": c.name, "kind": c.kind}
        hint = CATEGORY_HINTS.get(c.name)
        if hint:
            item["when_to_use"] = hint
        cats.append(item)
    txs = []
    for i, tx in enumerate(transactions):
        txs.append(
            {
                "i": i,
                "date": tx.occurred_at.isoformat(),
                "amount": str(tx.amount),
                "currency": tx.currency,
                "bank_side": tx.direction,
                "description": (tx.description or "")[:300],
            }
        )
    prefs = []
    for p in user_prefs or []:
        name = p.get("category_name")
        sample = (p.get("sample") or p.get("key") or "")[:200]
        if name and sample:
            prefs.append({"description_contains_or_equals": sample, "category": name})
    return {
        "categories": cats,
        "user_learned_rules": prefs,
        "transactions": txs,
        "instructions": (
            "Categorize each transaction using categories[].name exactly. "
            "user_learned_rules are HARD overrides from this user — "
            "if a transaction description matches a rule (same merchant / same text), "
            "you MUST use that category. "
            "YANDEX*4121*GO / YANDEX GO / taxi rides → 🚕 Такси, NEVER фастфуд. "
            "Unknown small merchants → Разное, not cafes. "
            "Return assignments for every i."
        ),
    }


def _extract_json_array(text: str) -> list:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("assignments"), list):
            return data["assignments"]
        if isinstance(data, dict) and isinstance(data.get("results"), list):
            return data["results"]
    except json.JSONDecodeError:
        pass
    m = re.search(r"\[[\s\S]*\]", text)
    if m:
        return json.loads(m.group(0))
    raise ValueError("Ответ модели не содержит JSON-массив")


async def categorize_batch_with_ai(
    transactions: Sequence[ParsedTransaction],
    categories: Sequence[CategoryOption],
    user_prefs: Sequence[dict] | None = None,
) -> AiCategorizeResult:
    """Один Chat Completions запрос на весь список транзакций."""
    n = len(transactions)
    if n == 0:
        return AiCategorizeResult([], used_ai=False)

    api_key, model = _openai_config()
    allowed = {c.name: c for c in categories}
    pref_hints = apply_user_prefs_hints(transactions, user_prefs or [], allowed)

    if not api_key:
        # без LLM — preferences + правила парсера (уже в category_hint)
        hints = [
            pref_hints[i] or (transactions[i].category_hint if transactions[i].category_hint in allowed else None)
            for i in range(n)
        ]
        return AiCategorizeResult(
            hints,
            used_ai=False,
            error="OPENAI_API_KEY не задан — использованы правила и ваши правки",
        )
    if not categories:
        return AiCategorizeResult(
            [None] * n,
            used_ai=False,
            error="Нет доступных категорий",
        )

    payload = _build_payload(transactions, categories, user_prefs)
    body = {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False),
            },
        ],
    }

    url = os.getenv("OPENAI_API_URL", "https://api.openai.com/v1/chat/completions")
    try:
        timeout = aiohttp.ClientTimeout(total=180)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            ) as resp:
                raw = await resp.text()
                if resp.status >= 400:
                    logger.warning("OpenAI categorize HTTP {}: {}", resp.status, raw[:500])
                    # даже при ошибке LLM оставляем preference-hints
                    return AiCategorizeResult(
                        pref_hints,
                        used_ai=False,
                        error=f"OpenAI HTTP {resp.status}",
                    )
                data = json.loads(raw)
    except Exception as exc:
        logger.warning("OpenAI categorize failed: {}", exc)
        return AiCategorizeResult(
            pref_hints, used_ai=False, error=f"OpenAI: {exc}"
        )

    try:
        content = data["choices"][0]["message"]["content"]
        items = _extract_json_array(content)
    except Exception as exc:
        logger.warning("OpenAI categorize parse failed: {}", exc)
        return AiCategorizeResult(
            pref_hints, used_ai=False, error=f"Разбор ответа OpenAI: {exc}"
        )

    hints: list[str | None] = [None] * n
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            idx = int(item.get("i"))
        except (TypeError, ValueError):
            continue
        if idx < 0 or idx >= n:
            continue
        name = (item.get("category") or "").strip()
        if name in allowed:
            hints[idx] = name
        else:
            lower_map = {k.lower(): k for k in allowed}
            hints[idx] = lower_map.get(name.lower())

    for i, hint in enumerate(hints):
        if pref_hints[i]:
            hints[i] = pref_hints[i]
            continue
        if hint:
            continue
        kind = transactions[i].direction or "expense"
        fb = FALLBACK_BY_KIND.get(kind)
        if fb and fb in allowed:
            hints[i] = fb
        elif allowed:
            same = next((c.name for c in categories if c.kind == kind), None)
            hints[i] = same or next(iter(allowed))

    assigned = sum(1 for h in hints if h)
    logger.info(
        "AI categorize: {}/{} assigned (prefs {}), model={}",
        assigned,
        n,
        sum(1 for h in pref_hints if h),
        model,
    )
    return AiCategorizeResult(hints, used_ai=True)


def apply_user_prefs_hints(
    transactions: Sequence[ParsedTransaction],
    user_prefs: Sequence[dict],
    allowed: dict[str, CategoryOption],
) -> list[str | None]:
    """Точное совпадение description_key → категория из предпочтений."""
    from bot.components.finance.category_prefs import description_key

    by_key = {
        (p.get("key") or "").upper(): p.get("category_name")
        for p in user_prefs
        if p.get("key") and p.get("category_name") in allowed
    }
    out: list[str | None] = [None] * len(transactions)
    if not by_key:
        return out
    for i, tx in enumerate(transactions):
        k = description_key(tx.description)
        if k in by_key:
            out[i] = by_key[k]
    return out


def apply_hints_to_transactions(
    transactions: list[ParsedTransaction],
    hints: Sequence[str | None],
    categories: Sequence[CategoryOption],
) -> None:
    """Мутирует category_hint. Direction из выписки (знак) не перетираем kind'ом категории."""
    by_name = {c.name: c for c in categories}
    for tx, hint in zip(transactions, hints):
        if not hint:
            continue
        cat = by_name.get(hint)
        if not cat:
            continue
        tx.category_hint = hint
        # Не ставим tx.direction = cat.kind: «🔁 Переводы» — expense-категория,
        # но «Перевод себе» в плюсе должен остаться income.
