from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class TrialIntelligenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    merchant_name: str
    authorization_transaction_id: str
    authorization_amount: float
    authorization_date: date
    detected_state: str
    confidence: float = Field(ge=0, le=1)
    evidence: dict[str, object]
    possible_conversion_date: date | None
    related_recurring_payment_id: int | None
    detected_at: datetime
    updated_at: datetime
    alert_sent_in_app: bool
    alert_sent_email: bool
    email_alert_scheduled_for: datetime | None
    email_alert_sent_at: datetime | None
    status: str
    days_until_possible_conversion: int | None = None

    @classmethod
    def from_model(cls, model: object) -> "TrialIntelligenceResponse":
        value = cls.model_validate(model)
        if value.possible_conversion_date is not None:
            value.days_until_possible_conversion = (
                value.possible_conversion_date - date.today()
            ).days
        return value


class TrialIntelligenceListResponse(BaseModel):
    items: list[TrialIntelligenceResponse]
    total: int
