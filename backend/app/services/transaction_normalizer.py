"""Normalization, extraction, and mapping engine for financial transactions from CSV and PDF."""
from __future__ import annotations

import csv
import io
import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Sequence

# Canonical FinSight database transaction fields
CANONICAL_FIELDS = {
    "transaction_date",
    "merchant_name",
    "description",
    "amount",
    "category",
    "transaction_class",
    "payment_mode",
    "frequency",
    "income_flag",
    "recurring_flag",
    "autopay_flag",
    "risk_label",
    "transaction_status",
    "is_new_subscription",
    "merchant_type",
    "commitment_type",
}

# Recognized standard bank header aliases
HEADER_ALIASES: dict[str, str] = {
    # Dates
    "date": "transaction_date",
    "transaction date": "transaction_date",
    "transaction_date": "transaction_date",
    "txn date": "transaction_date",
    "txn_date": "transaction_date",
    "trans date": "transaction_date",
    "trans_date": "transaction_date",
    "posting date": "transaction_date",
    "post date": "transaction_date",
    "value date": "value_date",
    "value_date": "value_date",
    "valuedate": "value_date",
    "transaction timestamp": "transaction_date",
    "transaction_timestamp": "transaction_date",
    "transactiontimestamp": "transaction_date",
    "timestamp": "transaction_date",
    "time": "transaction_date",

    # Amounts
    "amount": "amount",
    "txn amount": "amount",
    "transaction amount": "amount",
    "transaction_amount": "amount",
    "trans amount": "amount",
    "net amount": "amount",

    # Dual Debit / Credit & Deposit / Withdrawal columns
    "debit": "debit_amount",
    "dr": "debit_amount",
    "debit amount": "debit_amount",
    "debit_amount": "debit_amount",
    "withdrawals": "debit_amount",
    "withdrawal": "debit_amount",
    "withdrawls": "debit_amount",
    "withdrawl": "debit_amount",
    "credit": "credit_amount",
    "cr": "credit_amount",
    "credit amount": "credit_amount",
    "credit_amount": "credit_amount",
    "deposits": "credit_amount",
    "deposit": "credit_amount",

    # Descriptions / Merchant / Narration
    "description": "description",
    "narration": "description",
    "particulars": "description",
    "transaction remarks": "description",
    "remarks": "description",
    "details": "description",
    "merchant": "merchant_name",
    "merchant name": "merchant_name",
    "merchant_name": "merchant_name",
    "payee": "merchant_name",
    "party": "merchant_name",

    # Types / Direction / Mode
    "type": "transaction_type",
    "txn type": "transaction_type",
    "transaction type": "transaction_class",
    "transaction_type": "transaction_class",
    "mode": "payment_mode",
    "payment mode": "payment_mode",
    "payment_mode": "payment_mode",
    "payment method": "payment_mode",
    "channel": "payment_mode",

    # Balances (to safely ignore)
    "balance": "balance",
    "closing balance": "balance",
    "closing_balance": "balance",
    "available balance": "balance",
    "current balance": "balance",
    "currentbalance": "balance",

    # IDs & References
    "txnid": "transaction_id",
    "txn id": "transaction_id",
    "transaction id": "transaction_id",
    "transaction_id": "transaction_id",
    "ref no": "reference_id",
    "ref_no": "reference_id",
    "reference": "reference_id",
    "reference number": "reference_id",
    "cheque no": "reference_id",
    "chq no": "reference_id",

    # Categorization / Commitments
    "category": "category",
    "class": "transaction_class",
    "transaction_class": "transaction_class",
    "frequency": "frequency",
    "income flag": "income_flag",
    "income_flag": "income_flag",
    "recurring flag": "recurring_flag",
    "recurring_flag": "recurring_flag",
    "autopay flag": "autopay_flag",
    "autopay_flag": "autopay_flag",
    "risk label": "risk_label",
    "risk_label": "risk_label",
    "status": "transaction_status",
    "transaction status": "transaction_status",
    "transaction_status": "transaction_status",
}

# Merchant & pattern classification rules
SUBSCRIPTION_PATTERNS = [
    (r"\b(netflix|spotify|disney|hotstar|prime video|amazon prime|youtube|apple\.com|apple music|icloud|patreon|audible|coursera|medium|nyt|wsj|chatgpt|openai)\b", "subscription", "entertainment"),
]
EMI_PATTERNS = [
    (r"\b(hdfc bank emi|sbi emi|icici emi|bajaj finance|bajaj finserv|home loan|car loan|auto loan|personal loan|education loan|housing loan|hdfc loan|sbi loan|loan emi)\b", "emi", "loan"),
]
BNPL_PATTERNS = [
    (r"\b(simpl|lazypay|zestmoney|paytm postpaid|amazon pay later|flipkart pay later|mobikwik zip)\b", "bnpl", "bnpl"),
]
INCOME_PATTERNS = [
    r"\b(salary|payroll|stipend|interest credit|dividend|neft cr-salary|ach credit salary|bonus)\b"
]


def clean_numeric_string(raw: Any) -> float | None:
    """Parses arbitrary monetary string representation into a float."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or s in {"-", "--", "NA", "N/A", "null", "None"}:
        return None

    # Handle accounting parentheses: (123.45) -> -123.45
    is_negative = False
    if s.startswith("(") and s.endswith(")"):
        is_negative = True
        s = s[1:-1].strip()

    # Handle trailing minus: 123.45- -> -123.45
    if s.endswith("-"):
        is_negative = True
        s = s[:-1].strip()

    # Remove currency symbols and formatting commas
    s = re.sub(r"[^\d.\-+]", "", s)
    if not s or s in {"+", "-"}:
        return None

    try:
        val = float(s)
        if not math.isfinite(val):
            return None
        return -val if (is_negative and val > 0) else val
    except ValueError:
        return None


def parse_flexible_date(raw: Any) -> datetime:
    """Parses date strings across common formats (ISO, DD-Mon-YYYY, DD/MM/YYYY, MM/DD/YYYY)."""
    if raw is None:
        raise ValueError("Missing date value")
    if isinstance(raw, datetime):
        if raw.tzinfo is not None:
            return raw.astimezone(timezone.utc).replace(tzinfo=None)
        return raw
    if isinstance(raw, date):
        return datetime.combine(raw, datetime.min.time())

    s = str(raw).strip()
    if not s:
        raise ValueError("Empty date string")

    # 1. ISO format (e.g. 2026-01-05 or 2023-12-15T14:32:00+05:30)
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except ValueError:
        pass

    # 2. DD-Mon-YYYY (e.g. 20-Aug-2020, 05-Jan-2026, 20-August-2020)
    for fmt in ("%d-%b-%Y", "%d-%B-%Y", "%d %b %Y", "%d %B %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass

    # 3. Delimited formats with / or - or .
    # Match patterns like DD/MM/YYYY, MM/DD/YYYY, YYYY/MM/DD
    for fmt in (
        "%d/%m/%Y", "%d/%m/%y",
        "%d-%m-%Y", "%d-%m-%y",
        "%d.%m.%Y", "%d.%m.%y",
        "%Y/%m/%d", "%Y-%m-%d",
        "%m/%d/%Y", "%m/%d/%y",
        "%d/%m/%Y %H:%M:%S",
        "%d-%m-%Y %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
    ):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass

    raise ValueError(f"Unrecognized date format: '{s}'")


@dataclass
class ColumnMapping:
    detected_columns: dict[str, str]  # raw_header -> canonical_role
    unmapped_columns: list[str] = field(default_factory=list)
    has_dual_amounts: bool = False
    has_explicit_direction: bool = False
    date_column: str | None = None
    amount_column: str | None = None
    debit_column: str | None = None
    credit_column: str | None = None
    type_column: str | None = None
    description_column: str | None = None
    merchant_column: str | None = None


def detect_column_mappings(headers: Sequence[str | None]) -> ColumnMapping:
    """Analyzes header strings and builds semantic field mappings."""
    detected: dict[str, str] = {}
    unmapped: list[str] = []

    for raw in headers:
        if raw is None or not str(raw).strip():
            continue
        clean_raw = str(raw).strip()
        key = clean_raw.lower().replace("_", " ")
        # Also collapse consecutive spaces
        key = re.sub(r"\s+", " ", key)

        mapped_role = HEADER_ALIASES.get(key)
        if not mapped_role:
            # Check with underscores intact
            mapped_role = HEADER_ALIASES.get(clean_raw.lower())

        if mapped_role:
            detected[clean_raw] = mapped_role
        else:
            # Check direct match with canonical fields
            norm_key = key.replace(" ", "_")
            if norm_key in CANONICAL_FIELDS:
                detected[clean_raw] = norm_key
            else:
                unmapped.append(clean_raw)

    mapping = ColumnMapping(detected_columns=detected, unmapped_columns=unmapped)

    # Resolve roles
    for raw, role in detected.items():
        if role == "transaction_date" and not mapping.date_column:
            mapping.date_column = raw
        elif role == "value_date" and not mapping.date_column:
            # Secondary candidate
            mapping.date_column = raw
        elif role == "amount" and not mapping.amount_column:
            mapping.amount_column = raw
        elif role == "debit_amount" and not mapping.debit_column:
            mapping.debit_column = raw
        elif role == "credit_amount" and not mapping.credit_column:
            mapping.credit_column = raw
        elif role == "transaction_type" and not mapping.type_column:
            mapping.type_column = raw
        elif role == "description" and not mapping.description_column:
            mapping.description_column = raw
        elif role == "merchant_name" and not mapping.merchant_column:
            mapping.merchant_column = raw

    if mapping.debit_column or mapping.credit_column:
        mapping.has_dual_amounts = True
    if mapping.type_column:
        mapping.has_explicit_direction = True

    return mapping


@dataclass
class NormalizedTransaction:
    transaction_date: datetime
    amount: float
    user_id: str
    merchant_name: str | None = None
    description: str | None = None
    category: str | None = None
    transaction_class: str | None = None
    payment_mode: str | None = None
    frequency: str | None = None
    income_flag: bool | None = None
    recurring_flag: bool | None = None
    autopay_flag: bool | None = None
    risk_label: str | None = None
    transaction_status: str | None = "Success"
    is_new_subscription: bool | None = None
    merchant_type: str | None = None
    commitment_type: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)
    import_fingerprint: str | None = None
    transaction_id: str | None = None


def normalize_row_data(
    raw_row: dict[str, Any],
    mapping: ColumnMapping,
    user_id: str,
) -> NormalizedTransaction:
    """Normalizes a raw dictionary row into a canonical FinSight transaction."""
    # 1. Resolve date
    date_val = None
    if mapping.date_column and raw_row.get(mapping.date_column) is not None:
        date_val = raw_row[mapping.date_column]
    elif "transaction_date" in raw_row:
        date_val = raw_row["transaction_date"]
    elif "date" in raw_row:
        date_val = raw_row["date"]
    elif "transactionTimestamp" in raw_row:
        date_val = raw_row["transactionTimestamp"]

    if date_val is None or str(date_val).strip() == "":
        raise ValueError("transaction_date is required")

    txn_date = parse_flexible_date(date_val)

    # 2. Resolve amount and direction
    amount: float | None = None
    income_flag: bool | None = None

    if mapping.has_dual_amounts:
        # Dual columns: Deposits / Withdrawls OR Debit / Credit
        debit_val = clean_numeric_string(raw_row.get(mapping.debit_column)) if mapping.debit_column else None
        credit_val = clean_numeric_string(raw_row.get(mapping.credit_column)) if mapping.credit_column else None

        if credit_val is not None and credit_val > 0:
            amount = credit_val
            income_flag = True
        elif debit_val is not None and debit_val > 0:
            amount = debit_val
            income_flag = False
        elif (credit_val is not None and credit_val == 0) and (debit_val is not None and debit_val > 0):
            amount = debit_val
            income_flag = False
        elif (debit_val is not None and debit_val == 0) and (credit_val is not None and credit_val > 0):
            amount = credit_val
            income_flag = True
        else:
            # Fallback if both 0 or one is 0
            val = (credit_val or 0.0) or (debit_val or 0.0)
            if val > 0:
                amount = val
                income_flag = bool(credit_val and credit_val > 0)
            else:
                raise ValueError("Both debit and credit amounts are zero or empty")
    else:
        raw_amount = None
        if mapping.amount_column and raw_row.get(mapping.amount_column) is not None:
            raw_amount = raw_row[mapping.amount_column]
        elif "amount" in raw_row and raw_row.get("amount") is not None:
            raw_amount = raw_row["amount"]
        elif "Amount" in raw_row and raw_row.get("Amount") is not None:
            raw_amount = raw_row["Amount"]
        else:
            # Check any key containing amount
            for k, v in raw_row.items():
                if "amount" in k.lower() and v is not None:
                    raw_amount = v
                    break

        parsed_num = clean_numeric_string(raw_amount)
        if parsed_num is None:
            raise ValueError("amount is required and must be a valid number")

        # If negative amount, it's an expense; if positive, direction depends on type/flags
        if parsed_num < 0:
            amount = abs(parsed_num)
            income_flag = False
        else:
            amount = parsed_num

        # Check explicit type column (e.g. DEBIT / CREDIT, DR / CR)
        type_str = ""
        if mapping.type_column and raw_row.get(mapping.type_column) is not None:
            type_str = str(raw_row[mapping.type_column]).strip().upper()
        elif "type" in raw_row and raw_row["type"]:
            type_str = str(raw_row["type"]).strip().upper()

        if type_str in {"CREDIT", "CR", "DEPOSIT", "INCOME"}:
            income_flag = True
        elif type_str in {"DEBIT", "DR", "WITHDRAWAL", "EXPENSE"}:
            income_flag = False

    if amount is None or not math.isfinite(amount) or amount < 0:
        raise ValueError("amount must be a positive finite number")

    # 3. Extract description and merchant
    desc = None
    if mapping.description_column and raw_row.get(mapping.description_column):
        desc = str(raw_row[mapping.description_column]).strip()
    elif "description" in raw_row and raw_row["description"]:
        desc = str(raw_row["description"]).strip()
    elif "narration" in raw_row and raw_row["narration"]:
        desc = str(raw_row["narration"]).strip()

    merchant = None
    if mapping.merchant_column and raw_row.get(mapping.merchant_column):
        merchant = str(raw_row[mapping.merchant_column]).strip()
    elif "merchant_name" in raw_row and raw_row["merchant_name"]:
        merchant = str(raw_row["merchant_name"]).strip()
    elif "merchant" in raw_row and raw_row["merchant"]:
        merchant = str(raw_row["merchant"]).strip()

    # 4. Extract other optional fields directly if provided
    payment_mode = str(raw_row.get(mapping.detected_columns.get("mode") or raw_row.get("payment_mode") or "")).strip() or None
    category = str(raw_row.get("category") or "").strip() or None
    txn_class = str(raw_row.get("transaction_class") or "").strip() or None
    status_val = str(raw_row.get("transaction_status") or "Success").strip() or "Success"

    # 5. Smart rule-based classification on description / merchant
    combined_text = f"{merchant or ''} {desc or ''}".lower()

    # Check income signals
    if income_flag is None:
        if any(re.search(pat, combined_text) for pat in INCOME_PATTERNS):
            income_flag = True
        else:
            income_flag = False

    if income_flag:
        if not category:
            category = "income"
        if not txn_class:
            txn_class = "income"
    else:
        # Check candidate commitment patterns
        if not txn_class:
            for pat, cls_name, default_cat in SUBSCRIPTION_PATTERNS:
                if re.search(pat, combined_text):
                    txn_class = cls_name
                    if not category:
                        category = default_cat
                    break

            if not txn_class:
                for pat, cls_name, default_cat in EMI_PATTERNS:
                    if re.search(pat, combined_text):
                        txn_class = cls_name
                        if not category:
                            category = default_cat
                        break

            if not txn_class:
                for pat, cls_name, default_cat in BNPL_PATTERNS:
                    if re.search(pat, combined_text):
                        txn_class = cls_name
                        if not category:
                            category = default_cat
                        break

    # Keep merchant None if not explicitly provided, preserving raw description
    # This ensures exact parity with CSV imports that provide description but no merchant

    return NormalizedTransaction(
        transaction_date=txn_date,
        amount=round(amount, 2),
        user_id=user_id,
        merchant_name=merchant,
        description=desc,
        category=category,
        transaction_class=txn_class,
        payment_mode=payment_mode,
        income_flag=income_flag,
        transaction_status=status_val,
        raw_payload={k: v for k, v in raw_row.items() if v is not None and str(v).strip()},
    )
