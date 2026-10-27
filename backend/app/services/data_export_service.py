import csv
import io
import json
from datetime import datetime, timezone

from app.database.models.user import User
from app.database.connection import SessionLocal


TRANSACTION_FIELDS = (
    "transaction_id",
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
)


class DataExportService:
    def export_transactions(self, user_id: str) -> str:
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=TRANSACTION_FIELDS)
        writer.writeheader()
        with SessionLocal() as session:
            user = session.query(User).filter(User.user_id == user_id).one_or_none()
            if user is None:
                return output.getvalue()
            for transaction in sorted(user.transactions, key=lambda item: item.transaction_date):
                writer.writerow({field: getattr(transaction, field) for field in TRANSACTION_FIELDS})
        return output.getvalue()

    def export_json(self, user_id: str) -> str:
        with SessionLocal() as session:
            user = session.query(User).filter(User.user_id == user_id).one_or_none()
            if user is None:
                return json.dumps({"user_id": user_id, "transactions": [], "exported_at": datetime.now(timezone.utc).isoformat()})
            txns = []
            for transaction in sorted(user.transactions, key=lambda item: item.transaction_date):
                txns.append({field: getattr(transaction, field) for field in TRANSACTION_FIELDS})
            data = {
                "user_id": user_id,
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "transaction_count": len(txns),
                "transactions": txns,
            }
            return json.dumps(data, indent=2, default=str)

    def export_pdf(self, user_id: str) -> bytes:
        from app.services.pdf_report_service import get_financial_report_pdf_service

        return get_financial_report_pdf_service().generate_report(user_id)


def get_data_export_service() -> DataExportService:
    return DataExportService()

