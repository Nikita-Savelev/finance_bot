"""Справка Т-Банка / ТБанк «о движении средств» (PDF)."""

from __future__ import annotations

import re
import shutil
import subprocess
from decimal import Decimal
from pathlib import Path

from bot.components.finance.categorizer import categorize
from bot.components.finance.parsers.base import ParsedTransaction, ParseResult
from bot.components.finance.parsers.common import make_external_id, parse_date, parse_money

# Дата Дата сумма_оп сумма_карты описание[ карта]
_AMOUNT = r"([+-])\s*([\d\s]+[.,]\d{2})\s*([₽Դ$€]|[A-Z]{3})"
_ROW_RE = re.compile(
    rf"^(\d{{2}}\.\d{{2}}\.\d{{4}})\s+(\d{{2}}\.\d{{2}}\.\d{{4}})\s+"
    rf"{_AMOUNT}\s+{_AMOUNT}\s*(.*)$"
)
_TIME_PAIR_RE = re.compile(r"^(\d{2}:\d{2})\s+(\d{2}:\d{2})\s*(.*)$")
_CARD_TAIL_RE = re.compile(r"^(.*?)\s+(\d{4})$")
_CARD_ONLY_RE = re.compile(r"^\d{4}$")
_STOP_PREFIXES = (
    "Пополнения",
    "Расходы",
    "С уважением",
    "АО «ТБанк»",
    "АО «ТБАНК»",
    "БИК ",
)


def looks_like_tbank_pdf(text: str) -> bool:
    u = (text or "").upper()
    return (
        "ТБАНК" in u
        or "TBANK.RU" in u
        or "ТИНЬКОФФ" in u
        or "СПРАВКА О ДВИЖЕНИИ СРЕДСТВ" in u
    )


def _signed_money(sign: str, num: str) -> Decimal:
    amt = parse_money(num)
    return -amt if sign == "-" else amt


def _extract_pdf_text(path: Path) -> str:
    try:
        import pdfplumber
    except ImportError:
        pdfplumber = None

    if pdfplumber is not None:
        parts: list[str] = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                parts.append(page.extract_text() or "")
        text = "\n".join(parts)
        if text.strip():
            return text

    if shutil.which("pdftotext"):
        return subprocess.check_output(
            ["pdftotext", "-layout", str(path), "-"],
            text=True,
            errors="replace",
        )
    raise RuntimeError(
        "Для PDF Т-Банка нужен pdfplumber или утилита pdftotext (poppler-utils)"
    )


def _split_card(text: str) -> tuple[str, str]:
    """Отделить 4-значный номер карты в конце строки описания."""
    s = (text or "").strip()
    m = _CARD_TAIL_RE.match(s)
    if not m:
        return s, ""
    head, card = m.group(1).strip(), m.group(2)
    if "+" in head:
        return s, ""
    tokens = head.split()
    last = tokens[-1] if tokens else ""
    # маска PAN 445430******8359; * в YANDEX*4121*GO — не маска
    if "******" in last or re.fullmatch(r"\d+\*+\d*", last):
        return s, ""
    if re.search(r"\d{5,}", head.replace(" ", "")):
        return s, ""
    if head[-1:].isdigit():
        return s, ""
    return head, card


def parse_tbank_pdf(
    path: str | Path,
    *,
    account_id: int,
    currency: str,
) -> ParseResult:
    path = Path(path)
    try:
        text = _extract_pdf_text(path)
    except Exception as exc:
        return ParseResult("tbank", [], error=str(exc))

    if not looks_like_tbank_pdf(text):
        return ParseResult(
            "tbank",
            [],
            error="PDF не похож на справку Т-Банка о движении средств",
        )

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    txs: list[ParsedTransaction] = []
    i = 0
    seq = 0

    while i < len(lines):
        m = _ROW_RE.match(lines[i])
        if not m:
            i += 1
            continue

        op_date_s = m.group(1)
        # group: d1 d2 s1 n1 c1 s2 n2 c2 rest
        sign_card, num_card = m.group(6), m.group(7)
        rest = (m.group(9) or "").strip()

        desc_parts: list[str] = []
        card = ""
        if rest:
            head, maybe_card = _split_card(rest)
            if maybe_card:
                desc_parts.append(head)
                card = maybe_card
            else:
                desc_parts.append(rest)

        j = i + 1
        while j < len(lines):
            ln = lines[j]
            if _ROW_RE.match(ln) or ln.startswith(_STOP_PREFIXES):
                break
            tm = _TIME_PAIR_RE.match(ln)
            if tm:
                cont = tm.group(3).strip()
                if cont:
                    head, maybe_card = _split_card(cont)
                    desc_parts.append(head if maybe_card else cont)
                    if maybe_card:
                        card = maybe_card
                j += 1
                continue
            if _CARD_ONLY_RE.match(ln):
                card = ln
                j += 1
                # после карты иногда ещё хвост описания на следующей стр. — не берём
                break
            if re.fullmatch(r"\d{1,2}", ln):
                # номер страницы
                j += 1
                continue
            head, maybe_card = _split_card(ln)
            desc_parts.append(head if maybe_card else ln)
            if maybe_card:
                card = maybe_card
            j += 1

        amount = _signed_money(sign_card, num_card)
        if amount == 0:
            i = j
            continue

        occurred = parse_date(op_date_s)
        if not occurred:
            i = j
            continue

        desc = re.sub(r"\s+", " ", " ".join(desc_parts)).strip()
        if card and desc.endswith(card):
            desc = desc[: -len(card)].strip()

        if amount < 0:
            direction, hint = categorize(desc, default_direction="expense")
            abs_amount = -amount
        else:
            direction, hint = categorize(desc, default_direction="income")
            abs_amount = amount

        seq += 1
        ext = make_external_id(
            account_id=account_id,
            occurred_at=occurred,
            amount=abs_amount,
            direction=direction,
            description=desc,
            currency=currency,
            sequence=seq,
        )
        txs.append(
            ParsedTransaction(
                occurred_at=occurred,
                amount=abs_amount,
                currency=currency,
                direction=direction,
                description=desc,
                external_id=ext,
                category_hint=hint,
                raw={"card": card, "source": "tbank_pdf"},
            )
        )
        i = j

    if not txs:
        return ParseResult(
            "tbank",
            [],
            error="В PDF не найдено операций Т-Банка",
        )
    return ParseResult("tbank", txs)
