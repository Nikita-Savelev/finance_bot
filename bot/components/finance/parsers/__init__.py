from __future__ import annotations

from pathlib import Path

from bot.components.finance.parsers.base import ParseResult
from bot.components.finance.parsers.io import load_rows, load_xlsx_sheet_count
from bot.components.finance.parsers.mycredo import looks_like_mycredo, parse_mycredo
from bot.components.finance.parsers.generic import parse_generic
from bot.components.finance.parsers.tbank import parse_tbank_pdf


def parse_statement_file(
    path: str | Path,
    *,
    account_id: int,
    currency: str,
) -> ParseResult:
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return parse_tbank_pdf(path, account_id=account_id, currency=currency)

    if suffix in {".xlsx", ".xlsm"}:
        n_sheets = load_xlsx_sheet_count(path)
        # MyCredo: лист 1 (index 1) — движения; если один лист — он сам
        candidates: list[tuple[str, list[list[str]]]] = []
        for idx in range(min(n_sheets, 3)):
            rows = load_rows(path, sheet_index=idx)
            candidates.append((f"sheet{idx}", rows))

        for _, rows in candidates:
            if looks_like_mycredo(rows):
                return parse_mycredo(rows, account_id=account_id, currency=currency)

        # prefer sheet 1 if multi-sheet bank export
        rows = candidates[1][1] if len(candidates) > 1 else candidates[0][1]
        if looks_like_mycredo(rows):
            return parse_mycredo(rows, account_id=account_id, currency=currency)
        result = parse_generic(rows, account_id=account_id, currency=currency)
        if result.transactions or not result.error:
            return result
        # try other sheets
        for _, rows in candidates:
            result = parse_generic(rows, account_id=account_id, currency=currency)
            if result.transactions:
                return result
        return result

    rows = load_rows(path)
    if looks_like_mycredo(rows):
        return parse_mycredo(rows, account_id=account_id, currency=currency)
    return parse_generic(rows, account_id=account_id, currency=currency)
