from __future__ import annotations

import hashlib
import re
from datetime import datetime, date, timedelta
from decimal import Decimal, InvalidOperation


def parse_money(cell: str | None) -> Decimal:
    """MyCredo и аналоги: ``6,488.00`` (тысячи через запятую) или ``1.234,56`` (EU)."""
    if cell is None:
        return Decimal("0")
    s = str(cell).strip().replace("\xa0", "").replace(" ", "")
    if not s:
        return Decimal("0")
    s = re.sub(r"[^\d,.\-]", "", s)
    if not s or s in {".", "-", "-.", ",", "-,"}:
        return Decimal("0")

    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            # 1.234,56
            s = s.replace(".", "").replace(",", ".")
        else:
            # 6,488.00
            s = s.replace(",", "")
    elif "," in s:
        whole, frac = s.split(",", 1)
        if frac.isdigit() and len(frac) in (1, 2):
            s = f"{whole}.{frac}"
        else:
            s = s.replace(",", "")

    try:
        return Decimal(s)
    except InvalidOperation:
        return Decimal("0")


def parse_date(cell: str | None) -> date | None:
    if cell is None:
        return None
    s = str(cell).strip()
    if not s:
        return None
    if re.fullmatch(r"\d+(\.\d+)?", s):
        try:
            serial = float(s)
            if 20000 < serial < 80000:
                return (datetime(1899, 12, 30) + timedelta(days=int(serial))).date()
        except (ValueError, OverflowError):
            pass
    m = re.match(r"(\d{2}\.\d{2}\.\d{4})", s)
    if m:
        try:
            return datetime.strptime(m.group(1), "%d.%m.%Y").date()
        except ValueError:
            pass
    for fmt in ("%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            continue
    return None


def make_external_id(
    *,
    account_id: int,
    occurred_at: date,
    amount: Decimal,
    direction: str,
    description: str,
    currency: str,
    sequence: int | None = None,
) -> str:
    raw = (
        f"{account_id}|{occurred_at.isoformat()}|{amount}|"
        f"{direction}|{(description or '').strip()}|{currency}|{sequence or ''}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]


def normalize_header(h: str) -> str:
    return re.sub(r"\s+", " ", (h or "").strip().lower())
