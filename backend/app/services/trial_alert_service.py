from __future__ import annotations

import html
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select

from app.core.config import get_settings
from app.database.connection import SessionLocal
from app.database.models.auth_user import AuthUser
from app.database.models.trial_intelligence import TrialIntelligence
from app.database.models.user import User

logger = logging.getLogger(__name__)


class ResendTrialAlertService:
    def send_due_alert(self, trial_id: int) -> bool:
        settings = get_settings()
        if not settings.resend_api_key or not settings.resend_from_email:
            logger.warning("Resend trial alerts are not configured; retaining alert for retry")
            return False
        with SessionLocal() as session:
            trial = session.get(TrialIntelligence, trial_id)
            if trial is None or trial.alert_sent_email or trial.possible_conversion_date is None:
                return False
            account = session.scalar(
                select(AuthUser)
                .join(User, User.auth_user_id == AuthUser.id)
                .where(User.user_id == trial.user_id)
            )
            if account is None:
                return False
            date_text = trial.possible_conversion_date.isoformat()
            subject = "FinSight Alert: Possible subscription conversion coming up"
            body = (
                f"Hi {html.escape(account.display_name or 'there')},\n\n"
                "FinSight detected a possible free trial or authorization for:\n\n"
                f"Merchant: {html.escape(trial.merchant_name)}\n"
                f"Authorization: ₹{trial.authorization_amount:g}\n\n"
                f"A recurring charge may occur around: {date_text}\n\n"
                "This is an informational alert based on transaction patterns."
            )
            try:
                response = httpx.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                    json={
                        "from": f"{settings.resend_from_name} <{settings.resend_from_email}>",
                        "to": [account.email],
                        "subject": subject,
                        "text": body,
                    },
                    timeout=5.0,
                )
                response.raise_for_status()
            except (httpx.HTTPError, OSError):
                logger.exception("Resend trial alert delivery failed")
                return False
            trial.alert_sent_email = True
            trial.email_alert_sent_at = datetime.now(timezone.utc)
            session.commit()
            return True
