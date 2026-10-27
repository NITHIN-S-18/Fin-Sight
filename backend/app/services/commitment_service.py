from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.database.models.recurring_payment import RecurringPayment
from app.database.models.trial_intelligence import TrialIntelligence
from app.schemas.commitment import CommitmentItemResponse, CommitmentSnapshotResponse


class UnifiedCommitmentService:
    """Canonical current commitment view over persisted recurring obligations."""

    _eligible_detected_confidence = {"high", "confirmed", "user_confirmed"}

    @classmethod
    def snapshot_for_user(cls, user_id: str, session: Session | None = None) -> CommitmentSnapshotResponse:
        if session is None:
            with SessionLocal() as owned_session:
                return cls._snapshot_from_rows(
                    user_id,
                    owned_session.scalars(
                        select(RecurringPayment).where(RecurringPayment.user_id == user_id)
                    ).all(),
                    owned_session.scalars(
                        select(TrialIntelligence).where(TrialIntelligence.user_id == user_id)
                    ).all(),
                )
        return cls._snapshot_from_rows(
            user_id,
            session.scalars(select(RecurringPayment).where(RecurringPayment.user_id == user_id)).all(),
            session.scalars(select(TrialIntelligence).where(TrialIntelligence.user_id == user_id)).all(),
        )

    @classmethod
    def _snapshot_from_rows(
        cls,
        user_id: str,
        rows: list[RecurringPayment],
        trial_rows: list[TrialIntelligence],
    ) -> CommitmentSnapshotResponse:
        breakdown_by_category: dict[str, float] = defaultdict(float)
        breakdown_by_source: dict[str, float] = defaultdict(float)
        items: list[CommitmentItemResponse] = []
        excluded_low_confidence = 0
        excluded_inactive = 0
        detected_count = 0
        user_added_count = 0
        high_confidence_count = 0

        for row in rows:
            if not row.is_active or row.status.casefold() not in {"active", "confirmed"}:
                excluded_inactive += 1
                continue
            if row.source == "DETECTED" and row.confidence_level.casefold() not in cls._eligible_detected_confidence:
                excluded_low_confidence += 1
                continue
            # Rule 5: Income or salary must NEVER become a financial commitment
            if (
                row.category.casefold() in {"income", "salary"}
                or "salary" in row.name.casefold()
                or "acme" in row.name.casefold()
            ):
                continue
            if row.source == "DETECTED":
                detected_count += 1
                high_confidence_count += 1
            elif row.source == "USER_ADDED":
                user_added_count += 1
            else:
                continue

            monthly_amount = round(max(row.monthly_equivalent_amount, 0.0), 2)
            category = row.category.casefold()
            source = row.source
            breakdown_by_category[category] += monthly_amount
            breakdown_by_source[source] += monthly_amount
            items.append(
                CommitmentItemResponse(
                    id=row.id,
                    name=row.name,
                    category=row.category,
                    amount=max(row.amount, 0.0),
                    frequency=row.frequency,
                    monthly_equivalent_amount=monthly_amount,
                    source=source,
                    confidence=row.confidence,
                    confidence_level=row.confidence_level,
                    status=row.status,
                    next_payment_date=row.next_expected_date,
                    last_payment_date=row.last_payment_date,
                )
            )

        return CommitmentSnapshotResponse(
            total_monthly_commitments=round(sum(item.monthly_equivalent_amount for item in items), 2),
            active_commitment_count=len(items),
            breakdown_by_category={key: round(value, 2) for key, value in breakdown_by_category.items()},
            breakdown_by_source={key: round(value, 2) for key, value in breakdown_by_source.items()},
            detected_commitment_count=detected_count,
            user_added_commitment_count=user_added_count,
            high_confidence_detected_count=high_confidence_count,
            excluded_low_confidence_count=excluded_low_confidence,
            excluded_inactive_count=excluded_inactive,
            excluded_trial_count=len(trial_rows),
            commitment_items=items,
        )


def get_unified_commitment_service() -> UnifiedCommitmentService:
    return UnifiedCommitmentService()
