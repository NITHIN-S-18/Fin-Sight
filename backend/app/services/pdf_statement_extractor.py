"""PDF Statement extraction engine using pypdf for text-based tables and records."""
from __future__ import annotations

import io
import re
from dataclasses import dataclass
from typing import Any

from pypdf import PdfReader

# Standard date regex patterns commonly seen in bank statements
# e.g. 20-Aug-2020, 2026-01-05, 05/01/2026, 05-01-2026
DATE_REGEX = re.compile(
    r"\b(?:\d{4}[-/]\d{2}[-/]\d{2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{1,2}-(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*-\d{2,4}|\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4})\b",
    re.IGNORECASE,
)

# Amount regex pattern: matches 1,250.00, 500, 10.50 (optional CR/DR/Cr/Dr)
AMOUNT_REGEX = re.compile(
    r"\b(?:\d{1,3}(?:,\d{3})*|\d+)\.\d{2}(?:\s*(?:CR|DR|Cr|Dr))?\b"
)


@dataclass
class PdfExtractionResult:
    is_encrypted: bool
    is_scanned: bool
    total_pages: int
    extracted_text_chars: int
    raw_rows: list[dict[str, Any]]
    column_headers: list[str]
    error_message: str | None = None


class PdfStatementExtractor:
    """Extracts statement transaction records from PDF documents."""

    @staticmethod
    def extract_transactions(file_bytes: bytes) -> PdfExtractionResult:
        stream = io.BytesIO(file_bytes)
        try:
            reader = PdfReader(stream)
        except Exception as exc:
            return PdfExtractionResult(
                is_encrypted=False,
                is_scanned=False,
                total_pages=0,
                extracted_text_chars=0,
                raw_rows=[],
                column_headers=[],
                error_message=f"Corrupted or invalid PDF file: {exc}",
            )

        if reader.is_encrypted:
            # Check if empty password decrypts
            try:
                decrypted = reader.decrypt("")
                if decrypted == 0:
                    return PdfExtractionResult(
                        is_encrypted=True,
                        is_scanned=False,
                        total_pages=len(reader.pages),
                        extracted_text_chars=0,
                        raw_rows=[],
                        column_headers=[],
                        error_message="The PDF statement is password-protected. Please remove the password and re-upload.",
                    )
            except Exception:
                return PdfExtractionResult(
                    is_encrypted=True,
                    is_scanned=False,
                    total_pages=len(reader.pages),
                    extracted_text_chars=0,
                    raw_rows=[],
                    column_headers=[],
                    error_message="The PDF statement is password-protected. Please remove the password and re-upload.",
                )

        total_pages = len(reader.pages)
        full_text_pages: list[str] = []
        total_chars = 0

        for page in reader.pages:
            try:
                txt = page.extract_text() or ""
            except Exception:
                txt = ""
            full_text_pages.append(txt)
            total_chars += len(txt.strip())

        # Check if scanned PDF (no extractable text characters)
        if total_chars < 50:
            return PdfExtractionResult(
                is_encrypted=False,
                is_scanned=True,
                total_pages=total_pages,
                extracted_text_chars=total_chars,
                raw_rows=[],
                column_headers=[],
                error_message=(
                    "This PDF appears to be a scanned image with no extractable text. "
                    "FinSight requires electronic text-based PDF statements or CSV files. "
                    "Scanned image OCR is currently not enabled in this environment."
                ),
            )

        # Parse text into lines and detect tabular transaction records
        parsed_rows: list[dict[str, Any]] = []
        headers_found: list[str] = ["Date", "Description", "Amount", "Type"]

        for page_idx, page_text in enumerate(full_text_pages):
            lines = page_text.splitlines()
            for line in lines:
                line_str = line.strip()
                if not line_str:
                    continue

                # Ignore common statement headers & footers
                lower_line = line_str.lower()
                if any(
                    kw in lower_line
                    for kw in (
                        "page ",
                        "statement of account",
                        "account summary",
                        "opening balance",
                        "closing balance",
                        "customer care",
                        "branch address",
                        "ifsc code",
                    )
                ):
                    continue

                # Check if the line begins with or contains a valid transaction date
                date_match = DATE_REGEX.search(line_str)
                if not date_match:
                    continue

                date_str = date_match.group(0)
                # Check for amounts on the line
                amounts = AMOUNT_REGEX.findall(line_str)
                if not amounts:
                    continue

                # Extract description by removing date and amounts from line
                desc_part = line_str
                desc_part = desc_part.replace(date_str, "", 1)
                for amt_str in amounts:
                    desc_part = desc_part.replace(amt_str, "", 1)
                desc_clean = re.sub(r"\s+", " ", desc_part).strip()

                # Determine amounts and types
                # Typically: [Debit/Withdrawal, Credit/Deposit, Balance] or [Amount, Balance]
                primary_amount_str = amounts[0]
                is_credit = False
                is_debit = False

                if "cr" in primary_amount_str.lower():
                    is_credit = True
                elif "dr" in primary_amount_str.lower():
                    is_debit = True

                # If there are multiple amounts (e.g. Debit, Credit, Balance)
                if len(amounts) >= 2 and not is_credit and not is_debit:
                    # If line indicates credit/deposit
                    if any(kw in desc_clean.lower() for kw in ("salary", "credit", "deposit", "refund")):
                        is_credit = True
                    else:
                        is_debit = True

                clean_num_str = re.sub(r"[^\d.]", "", primary_amount_str)
                try:
                    amt_val = float(clean_num_str)
                except ValueError:
                    continue

                row_dict: dict[str, Any] = {
                    "transaction_date": date_str,
                    "description": desc_clean or "Bank Transaction",
                    "amount": amt_val,
                    "transaction_type": "CREDIT" if is_credit else "DEBIT",
                }
                parsed_rows.append(row_dict)

        if not parsed_rows:
            return PdfExtractionResult(
                is_encrypted=False,
                is_scanned=False,
                total_pages=total_pages,
                extracted_text_chars=total_chars,
                raw_rows=[],
                column_headers=[],
                error_message="No transaction records could be identified in the uploaded PDF. Please verify that this is a bank statement containing transaction tables.",
            )

        return PdfExtractionResult(
            is_encrypted=False,
            is_scanned=False,
            total_pages=total_pages,
            extracted_text_chars=total_chars,
            raw_rows=parsed_rows,
            column_headers=headers_found,
            error_message=None,
        )
