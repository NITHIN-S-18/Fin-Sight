from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from app.database.connection import SessionLocal
from app.database.models.recurring_payment import RecurringPayment
from app.database.models.transaction import Transaction
from app.database.models.trial_intelligence import TrialIntelligence
from app.schemas.trial_intelligence import TrialIntelligenceListResponse, TrialIntelligenceResponse
from app.services.financial_rules import classify_transaction_status
from app.services.trial_alert_service import ResendTrialAlertService


class TrialIntelligenceService:
    _trial_words = ("trial", "free trial", "promo", "promotional", "introductory", "verification")
    _authorization_words = ("authorization", "authorisation", "verify", "verification", "preauth", "hold")
    _duration_pattern = re.compile(r"(\d{1,3})\s*(?:day|days|week|weeks|month|months)")

    @staticmethod
    def _merchant(transaction: Transaction) -> str:
        return (transaction.merchant_name or transaction.description or "").strip()

    @staticmethod
    def _is_success(transaction: Transaction) -> bool:
        return classify_transaction_status(transaction.transaction_status) == "successful"

    @classmethod
    def _evidence_for(cls, transaction: Transaction) -> dict[str, object]:
        text = f"{transaction.merchant_name or ''} {transaction.description or ''}".lower()
        return {
            "authorization_signal": transaction.amount in {1, 2},
            "authorization_wording": any(word in text for word in cls._authorization_words),
            "trial_wording": any(word in text for word in cls._trial_words),
            "merchant": cls._merchant(transaction),
        }

    @classmethod
    def reconcile(cls, user_id: str) -> int:
        with SessionLocal() as session:
            transactions = session.scalars(
                select(Transaction)
                .where(Transaction.user_id == user_id)
                .order_by(Transaction.transaction_date)
            ).all()
            auth_rows = [
                row for row in transactions
                if cls._is_success(row) and row.amount in {1, 2} and cls._merchant(row)
            ]
            changed = 0
            for authorization in auth_rows:
                merchant = cls._merchant(authorization)
                evidence = cls._evidence_for(authorization)
                related = [
                    row for row in transactions
                    if row.id != authorization.id
                    and cls._merchant(row).casefold() == merchant.casefold()
                    and row.transaction_date > authorization.transaction_date
                    and cls._is_success(row)
                    and row.amount > 2
                ]
                paid_dates = [row.transaction_date.date() for row in related]
                later_paid_count = len(related)
                duration_match = cls._duration_pattern.search(
                    f"{authorization.merchant_name or ''} {authorization.description or ''}".lower()
                )
                conversion_date: date | None = None
                if duration_match and evidence["trial_wording"]:
                    raw = int(duration_match.group(1))
                    duration_text = duration_match.group(0)
                    days = raw * 7 if "week" in duration_text else raw * 30 if "month" in duration_text else raw
                    conversion_date = authorization.transaction_date.date() + timedelta(days=days)
                    evidence["explicit_trial_duration"] = duration_text
                if later_paid_count >= 2:
                    state = "confirmed_recurring"
                    confidence = 0.95
                elif conversion_date is not None:
                    state = "possible_conversion"
                    confidence = 0.85
                elif evidence["trial_wording"] or evidence["authorization_wording"]:
                    state = "possible_trial"
                    confidence = 0.7
                else:
                    state = "authorization_hold"
                    confidence = 0.55
                evidence["later_paid_transaction_count"] = later_paid_count
                existing = session.scalar(
                    select(TrialIntelligence).where(
                        TrialIntelligence.user_id == user_id,
                        TrialIntelligence.authorization_transaction_id == authorization.transaction_id,
                    )
                )
                if existing is None:
                    existing = TrialIntelligence(
                        user_id=user_id,
                        merchant_name=merchant,
                        authorization_transaction_id=authorization.transaction_id,
                        authorization_amount=abs(authorization.amount),
                        authorization_date=authorization.transaction_date.date(),
                        detected_state=state,
                        confidence=confidence,
                        evidence=evidence,
                        possible_conversion_date=conversion_date,
                        alert_sent_in_app=True,
                        email_alert_scheduled_for=(
                            datetime.combine(conversion_date, datetime.min.time(), tzinfo=timezone.utc)
                            - timedelta(days=2)
                            if conversion_date is not None and state == "possible_conversion"
                            else None
                        ),
                        status="active",
                    )
                    session.add(existing)
                    changed += 1
                else:
                    existing.detected_state = state if confidence >= existing.confidence else existing.detected_state
                    existing.confidence = max(existing.confidence, confidence)
                    existing.evidence = {**(existing.evidence or {}), **evidence}
                    if conversion_date is not None:
                        existing.possible_conversion_date = conversion_date
                        if existing.email_alert_scheduled_for is None:
                            existing.email_alert_scheduled_for = (
                                datetime.combine(conversion_date, datetime.min.time(), tzinfo=timezone.utc)
                                - timedelta(days=2)
                            )
            session.commit()
            return changed

    @classmethod
    def list_for_user(cls, user_id: str) -> TrialIntelligenceListResponse:
        with SessionLocal() as session:
            rows = session.scalars(
                select(TrialIntelligence)
                .where(TrialIntelligence.user_id == user_id, TrialIntelligence.status == "active")
                .order_by(TrialIntelligence.authorization_date.desc())
            ).all()
            items = [TrialIntelligenceResponse.from_model(row) for row in rows]
            return TrialIntelligenceListResponse(items=items, total=len(items))

    @classmethod
    def get_for_user(cls, user_id: str, trial_id: int) -> TrialIntelligenceResponse:
        from fastapi import HTTPException, status

        with SessionLocal() as session:
            row = session.scalar(
                select(TrialIntelligence).where(
                    TrialIntelligence.id == trial_id,
                    TrialIntelligence.user_id == user_id,
                )
            )
            if row is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trial alert not found")
            return TrialIntelligenceResponse.from_model(row)

    @classmethod
    def dispatch_due_alerts(cls) -> None:
        now = datetime.now(timezone.utc)
        with SessionLocal() as session:
            ids = session.scalars(
                select(TrialIntelligence.id).where(
                    TrialIntelligence.status == "active",
                    TrialIntelligence.alert_sent_email.is_(False),
                    TrialIntelligence.email_alert_scheduled_for <= now,
                )
            ).all()
        sender = ResendTrialAlertService()
        for trial_id in ids:
            try:
                sender.send_due_alert(trial_id)
            except Exception:
                # Delivery is deliberately isolated from transaction ingestion.
                continue
