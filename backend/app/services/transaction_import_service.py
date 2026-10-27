from __future__ import annotations

import csv
import hashlib
import io
import logging
import math
import secrets
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select

from app.database.connection import SessionLocal
from app.database.models.transaction import Transaction
from app.database.models.transaction_import import TransactionImport
from app.database.models.user import User
from app.schemas.imports import (
    ImportPreviewResponse,
    SampleTransactionItem,
    TransactionUploadResponse,
)
from app.services.dataset_service import get_dataset_service, invalidate_dataset_service_cache
from app.services.financial_profile_sync_service import FinancialProfileSyncService
from app.services.pdf_statement_extractor import PdfStatementExtractor
from app.services.recurring_payment_service import RecurringPaymentService
from app.services.transaction_normalizer import (
    CANONICAL_FIELDS,
    HEADER_ALIASES,
    ColumnMapping,
    NormalizedTransaction,
    detect_column_mappings,
    normalize_row_data,
)
from app.services.trial_intelligence_service import TrialIntelligenceService

logger = logging.getLogger(__name__)

# Temporary in-memory token cache for dry-run preview batches (expires or cleaned after confirmation)
# Key: token -> {"auth_user_id": int, "user_id": str, "file_name": str, "rows": list[dict], "created_at": datetime}
PREVIEW_CACHE: dict[str, dict[str, Any]] = {}
MAX_PREVIEW_CACHE_SIZE = 100


class TransactionImportService:
    """
    Ingests, validates, normalizes, and persists user transaction batches from CSV/PDF statements.

    Deduplication & Transaction Hashing:
        To guarantee idempotency and prevent double-counting across overlapping statement uploads,
        this service generates a deterministic SHA-256 fingerprint for each transaction record via `_fingerprint`.

        Participating Fields:
            - user_id: Scopes the fingerprint to the financial tenant, preventing false matches across users.
            - transaction_date: Normalized ISO-8601 string, anchoring the transaction in time.
            - transaction_id: Original statement/external transaction reference if available.
            - merchant_name: Normalized merchant identity string.
            - description: Raw or parsed transaction description text.
            - amount: Normalized float formatted strictly to 2 decimal places (f"{amount:.2f}"),
              preventing floating-point serialization discrepancies across imports.

        Deduplication Handling:
            - In pre-flight preview (`generate_preview`), computed fingerprints are compared against
              existing user transaction fingerprints in the database to report an estimated duplicate count.
            - In final confirmation (`confirm_import` / `import_file`), records whose SHA-256 fingerprint
              already exists in the user's ledger are skipped, while new non-duplicate records are assigned
              a deterministic internal ID (`IMP-{user_id}-{fp[:24]}`) and persisted.
    """
    _aliases = {
        "date": "transaction_date",
        "transaction date": "transaction_date",
        "merchant": "merchant_name",
        "amount": "amount",
        "transaction type": "transaction_class",
        "transaction_type": "transaction_class",
    }
    _transaction_fields = CANONICAL_FIELDS

    def __init__(self, profile_sync_service: FinancialProfileSyncService | None = None) -> None:
        self._profile_sync_service = profile_sync_service or FinancialProfileSyncService()

    @staticmethod
    def _text(value: Any) -> str | None:
        value = "" if value is None else str(value).strip()
        return value or None

    @staticmethod
    def _bool(value: Any) -> bool | None:
        normalized = str(value).strip().lower() if value is not None else ""
        if not normalized:
            return None
        if normalized in {"yes", "true", "1", "y"}:
            return True
        if normalized in {"no", "false", "0", "n"}:
            return False
        raise ValueError("expected yes/no or true/false")

    @classmethod
    def _normalize_headers(cls, headers: list[str | None]) -> list[str]:
        normalized = []
        for header in headers:
            key = (header or "").strip().lower().replace("_", " ")
            normalized.append(cls._aliases.get(key, key.replace(" ", "_")))
        return normalized

    @classmethod
    def _validate_headers(cls, headers: list[str | None]) -> list[str]:
        normalized = cls._normalize_headers(headers)
        if any(not header for header in normalized):
            raise ValueError("CSV headers must not be blank")
        if len(normalized) != len(set(normalized)):
            raise ValueError("CSV contains duplicate columns")
        required = {"transaction_date", "amount"}
        missing = required - set(normalized)
        if missing:
            raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
        unsupported = set(normalized) - cls._transaction_fields
        if unsupported:
            raise ValueError(
                f"Unsupported transaction columns: {', '.join(sorted(unsupported))}"
            )
        return normalized

    @staticmethod
    def _fingerprint(user_id: str, row: dict[str, Any] | NormalizedTransaction) -> str:
        """
        Computes a deterministic SHA-256 fingerprint for deduplication.

        Hash string format:
            f"{user_id}|{date_iso}|{tx_id}|{merchant}|{desc}|{amount:.2f}"
        """
        if isinstance(row, NormalizedTransaction):
            values = [
                user_id,
                row.transaction_date.isoformat(),
                row.transaction_id or "",
                row.merchant_name or "",
                row.description or "",
                f"{row.amount:.2f}",
            ]
        else:
            dt = row["transaction_date"]
            dt_str = dt.isoformat() if isinstance(dt, datetime) else str(dt)
            values = [
                user_id,
                dt_str,
                row.get("transaction_id") or "",
                row.get("merchant_name") or "",
                row.get("description") or "",
                f"{row['amount']:.2f}",
            ]
        return hashlib.sha256("|".join(values).encode("utf-8")).hexdigest()

    async def generate_preview(
        self,
        auth_user_id: int,
        user_id: str,
        upload: UploadFile,
    ) -> ImportPreviewResponse:
        """Parses CSV or PDF and produces a pre-flight validation preview without persisting."""
        filename = upload.filename or "unknown_file"
        lower_name = filename.lower()
        if not (lower_name.endswith(".csv") or lower_name.endswith(".pdf")):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Supported formats are CSV and PDF.",
            )

        content = await upload.read()
        if len(content) == 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Uploaded file is empty.",
            )

        raw_rows: list[dict[str, Any]] = []
        file_type = "pdf" if lower_name.endswith(".pdf") else "csv"
        detected_map: dict[str, str] = {}
        unmapped_cols: list[str] = []

        if file_type == "pdf":
            extraction = PdfStatementExtractor.extract_transactions(content)
            if extraction.error_message:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=extraction.error_message,
                )
            raw_rows = extraction.raw_rows
            mapping = detect_column_mappings(extraction.column_headers)
            detected_map = mapping.detected_columns
            unmapped_cols = mapping.unmapped_columns
        else:
            try:
                text = content.decode("utf-8-sig")
            except UnicodeDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="CSV must be UTF-8 encoded",
                ) from None

            reader = csv.DictReader(io.StringIO(text))
            if not reader.fieldnames:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="CSV must contain a header row",
                )
            mapping = detect_column_mappings(reader.fieldnames)
            detected_map = mapping.detected_columns
            unmapped_cols = mapping.unmapped_columns

            for raw in reader:
                raw_rows.append(dict(raw))

        if not raw_rows:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="No transaction rows found in file",
            )

        # Validate rows and check duplicate estimates
        valid_rows: list[NormalizedTransaction] = []
        validation_errors: list[str] = []
        total_credits = 0.0
        total_debits = 0.0

        with SessionLocal() as session:
            existing_fps = set(
                session.scalars(
                    select(Transaction.import_fingerprint).where(Transaction.user_id == user_id)
                ).all()
            )

        est_duplicates = 0
        dates: list[datetime] = []

        for idx, row_dict in enumerate(raw_rows, start=1):
            try:
                norm = normalize_row_data(row_dict, mapping, user_id)
                fp = self._fingerprint(user_id, norm)
                norm.import_fingerprint = fp
                if fp in existing_fps:
                    est_duplicates += 1
                else:
                    existing_fps.add(fp)

                valid_rows.append(norm)
                dates.append(norm.transaction_date)
                if norm.income_flag:
                    total_credits += norm.amount
                else:
                    total_debits += norm.amount
            except Exception as exc:
                if len(validation_errors) < 20:
                    validation_errors.append(f"Row {idx}: {exc}")

        # Store preview in memory cache
        token = secrets.token_urlsafe(24)
        if len(PREVIEW_CACHE) > MAX_PREVIEW_CACHE_SIZE:
            PREVIEW_CACHE.clear()

        PREVIEW_CACHE[token] = {
            "auth_user_id": auth_user_id,
            "user_id": user_id,
            "file_name": filename,
            "rows": [
                {
                    "transaction_date": r.transaction_date,
                    "amount": r.amount,
                    "merchant_name": r.merchant_name,
                    "description": r.description,
                    "category": r.category,
                    "transaction_class": r.transaction_class,
                    "payment_mode": r.payment_mode,
                    "income_flag": r.income_flag,
                    "transaction_status": r.transaction_status,
                    "import_fingerprint": r.import_fingerprint,
                }
                for r in valid_rows
            ],
            "created_at": datetime.now(timezone.utc),
        }

        sample_items = [
            SampleTransactionItem(
                transaction_date=r.transaction_date.strftime("%Y-%m-%d"),
                merchant_name=r.merchant_name,
                description=r.description,
                amount=r.amount,
                direction="Income" if r.income_flag else "Expense",
                category=r.category,
                transaction_class=r.transaction_class,
            )
            for r in valid_rows[:10]
        ]

        min_d = min(dates).strftime("%Y-%m-%d") if dates else None
        max_d = max(dates).strftime("%Y-%m-%d") if dates else None

        return ImportPreviewResponse(
            file_type=file_type,
            file_name=filename,
            total_candidate_rows=len(raw_rows),
            valid_rows_count=len(valid_rows),
            invalid_rows_count=len(raw_rows) - len(valid_rows),
            ambiguous_rows_count=0,
            estimated_duplicate_count=est_duplicates,
            date_range_start=min_d,
            date_range_end=max_d,
            total_credits=round(total_credits, 2),
            total_debits=round(total_debits, 2),
            detected_mappings=detected_map,
            unmapped_columns=unmapped_cols,
            sample_transactions=sample_items,
            validation_errors=validation_errors,
            preview_token=token,
        )

    def confirm_preview_import(
        self,
        auth_user_id: int,
        user_id: str,
        preview_token: str,
    ) -> TransactionUploadResponse:
        """Commits transactions validated during a preview session."""
        cached = PREVIEW_CACHE.get(preview_token)
        if not cached:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Preview session has expired or is invalid. Please re-upload.",
            )

        if cached["auth_user_id"] != auth_user_id or cached["user_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Preview session does not belong to the current authenticated account.",
            )

        rows = cached["rows"]
        file_name = cached["file_name"]
        return self._persist_normalized_records(auth_user_id, user_id, file_name, rows)

    def _persist_normalized_records(
        self,
        auth_user_id: int,
        user_id: str,
        file_name: str,
        rows: list[dict[str, Any]],
    ) -> TransactionUploadResponse:
        """Atomic persistence, duplicate suppression, and financial synchronization."""
        with SessionLocal() as session:
            owned_user = session.scalar(
                select(User).where(
                    User.user_id == user_id,
                    User.auth_user_id == auth_user_id,
                )
            )
            if owned_user is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="The financial identity does not belong to this account",
                )

            dates = [r["transaction_date"] for r in rows if isinstance(r.get("transaction_date"), datetime)]
            import_record = TransactionImport(
                auth_user_id=auth_user_id,
                file_name=file_name,
                status="processed",
                transaction_count=0,
                transaction_start_date=min(dates) if dates else None,
                transaction_end_date=max(dates) if dates else None,
            )
            session.add(import_record)
            session.flush()

            existing = set(
                session.scalars(
                    select(Transaction.import_fingerprint).where(Transaction.user_id == user_id)
                ).all()
            )

            accepted = 0
            duplicates = 0
            for row in rows:
                fp = row.get("import_fingerprint") or self._fingerprint(user_id, row)
                if fp in existing:
                    duplicates += 1
                    continue

                transaction_id = f"IMP-{user_id}-{fp[:24]}"
                clean_row = dict(row)
                clean_row.pop("transaction_id", None)
                clean_row.pop("user_id", None)
                clean_row.pop("import_fingerprint", None)

                session.add(
                    Transaction(
                        transaction_id=transaction_id,
                        user_id=user_id,
                        import_fingerprint=fp,
                        **clean_row,
                    )
                )
                existing.add(fp)
                accepted += 1

            import_record.transaction_count = accepted

            # Downstream intelligence synchronization
            persisted_transactions = session.scalars(
                select(Transaction).where(Transaction.user_id == user_id)
            ).all()
            self._profile_sync_service.synchronize(session, owned_user, persisted_transactions)
            session.commit()
            session.refresh(import_record)

            invalidate_dataset_service_cache()
            RecurringPaymentService(get_dataset_service()).reconcile(user_id)

            # Re-project after recurring reconciliation
            persisted_transactions = session.scalars(
                select(Transaction).where(Transaction.user_id == user_id)
            ).all()
            self._profile_sync_service.synchronize(session, owned_user, persisted_transactions)
            session.commit()

            reconcile_status = "completed"
            try:
                TrialIntelligenceService.reconcile(user_id)
                TrialIntelligenceService.dispatch_due_alerts()
            except Exception:
                logger.warning(
                    "Trial intelligence reconciliation failed after transaction import",
                    exc_info=True,
                )
                reconcile_status = "partial"

            return TransactionUploadResponse(
                import_record=import_record,
                accepted_count=accepted,
                duplicate_count=duplicates,
                rejected_count=0,
                validation_errors=[],
                reconciliation_status=reconcile_status,
            )

    async def import_csv(self, auth_user_id: int, user_id: str, upload: UploadFile) -> TransactionUploadResponse:
        """
        Direct upload endpoint handling CSV and PDF files.
        Maintains 100% backward compatibility with existing contract and tests.
        """
        filename = upload.filename or ""
        lower_name = filename.lower()

        if lower_name.endswith(".pdf"):
            # PDF file branch
            content = await upload.read()
            extraction = PdfStatementExtractor.extract_transactions(content)
            if extraction.error_message:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=extraction.error_message,
                )
            mapping = detect_column_mappings(extraction.column_headers)
            normalized_rows = []
            for r in extraction.raw_rows:
                norm = normalize_row_data(r, mapping, user_id)
                normalized_rows.append({
                    "transaction_date": norm.transaction_date,
                    "amount": norm.amount,
                    "merchant_name": norm.merchant_name,
                    "description": norm.description,
                    "category": norm.category,
                    "transaction_class": norm.transaction_class,
                    "payment_mode": norm.payment_mode,
                    "income_flag": norm.income_flag,
                    "transaction_status": norm.transaction_status,
                    "import_fingerprint": self._fingerprint(user_id, norm),
                })
            return self._persist_normalized_records(auth_user_id, user_id, filename, normalized_rows)

        if not lower_name.endswith(".csv"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Only CSV files are accepted",
            )

        content = await upload.read()
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="CSV must be UTF-8 encoded",
            ) from None

        # Check if file adheres to strict classic schema or modern bank format
        # First try classic DictReader validation
        try:
            reader = csv.DictReader(io.StringIO(text), strict=True)
            if not reader.fieldnames:
                raise ValueError("CSV must contain a header row")

            # Check if strict headers pass (classic test suite behavior)
            raw_fieldnames = list(reader.fieldnames)
            is_classic_schema = False
            try:
                validated_fieldnames = self._validate_headers(raw_fieldnames)
                reader.fieldnames = validated_fieldnames
                is_classic_schema = True
            except ValueError as ve:
                err_msg = str(ve)
                # If duplicate column, blank header, or unsupported column in classic upload, fail as expected
                if "duplicate columns" in err_msg or "blank" in err_msg or "Unsupported transaction columns" in err_msg:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail=err_msg,
                    )
                # If missing required columns, check if modern bank mapping handles it (e.g. Deposits/Withdrawls)
                mapping = detect_column_mappings(raw_fieldnames)
                if not mapping.date_column or (not mapping.amount_column and not mapping.has_dual_amounts):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail=err_msg,
                    )
                is_classic_schema = False

            rows: list[dict[str, Any]] = []
            errors: list[str] = []

            if is_classic_schema:
                for line_number, raw in enumerate(reader, start=2):
                    try:
                        if None in raw:
                            raise ValueError("row contains more values than the header")
                        if any(value is None for value in raw.values()):
                            raise ValueError("row contains fewer values than the header")
                        parsed: dict[str, Any] = {
                            key: self._text(value)
                            for key, value in raw.items()
                            if key in self._transaction_fields
                        }
                        if parsed.get("transaction_date") is None:
                            raise ValueError("transaction_date is required")
                        if parsed.get("amount") is None:
                            raise ValueError("amount is required")
                        parsed["transaction_date"] = datetime.fromisoformat(str(parsed["transaction_date"]))
                        parsed["amount"] = float(str(parsed["amount"]).replace(",", ""))
                        if not math.isfinite(parsed["amount"]):
                            raise ValueError("amount must be finite")
                        for field in ("income_flag", "recurring_flag", "autopay_flag", "is_new_subscription"):
                            parsed[field] = self._bool(parsed.get(field))
                        parsed["user_id"] = user_id
                        parsed["import_fingerprint"] = self._fingerprint(user_id, parsed)
                        rows.append(parsed)
                    except (TypeError, ValueError) as exc:
                        errors.append(f"Row {line_number}: {exc}")
            else:
                # Modern flexible mapping branch (Dataset A, Dataset B, various bank layouts)
                mapping = detect_column_mappings(raw_fieldnames)
                for line_number, raw in enumerate(reader, start=2):
                    try:
                        norm = normalize_row_data(raw, mapping, user_id)
                        row_dict = {
                            "transaction_date": norm.transaction_date,
                            "amount": norm.amount,
                            "merchant_name": norm.merchant_name,
                            "description": norm.description,
                            "category": norm.category,
                            "transaction_class": norm.transaction_class,
                            "payment_mode": norm.payment_mode,
                            "income_flag": norm.income_flag,
                            "transaction_status": norm.transaction_status,
                            "import_fingerprint": self._fingerprint(user_id, norm),
                        }
                        rows.append(row_dict)
                    except (TypeError, ValueError) as exc:
                        errors.append(f"Row {line_number}: {exc}")

            if errors:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail={"message": "CSV contains invalid rows", "errors": errors},
                )

        except HTTPException:
            raise
        except (csv.Error, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(exc),
            ) from None

        return self._persist_normalized_records(auth_user_id, user_id, filename, rows)


def get_transaction_import_service() -> TransactionImportService:
    return TransactionImportService()