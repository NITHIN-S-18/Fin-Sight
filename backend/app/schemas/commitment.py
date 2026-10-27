from datetime import date

from pydantic import BaseModel, Field


class CommitmentItemResponse(BaseModel):
    id: int
    name: str
    category: str
    amount: float
    frequency: str
    monthly_equivalent_amount: float
    source: str
    confidence: float
    confidence_level: str
    status: str
    next_payment_date: date | None
    last_payment_date: date | None


class CommitmentSnapshotResponse(BaseModel):
    total_monthly_commitments: float
    active_commitment_count: int
    breakdown_by_category: dict[str, float]
    breakdown_by_source: dict[str, float]
    detected_commitment_count: int
    user_added_commitment_count: int
    high_confidence_detected_count: int
    excluded_low_confidence_count: int
    excluded_inactive_count: int
    excluded_trial_count: int
    commitment_items: list[CommitmentItemResponse] = Field(default_factory=list)
