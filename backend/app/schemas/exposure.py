from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.dataset import UserResponse


class CommitmentItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    commitment_name: str = Field(description="Readable commitment label.", examples=["Netflix"])
    commitment_source: str = Field(description="Source product type for the commitment.", examples=["Subscription"])
    monthly_amount: float = Field(description="Monthly amount attributed to the commitment.", examples=[555.0])
    total_amount: float = Field(description="Observed total amount for the commitment.", examples=[2220.0])
    commitment_type: str = Field(description="Commitment classification.", examples=["Optional"])


class FactorScoreResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    score: float = Field(description="Score assigned to the factor.", examples=[8.0])
    max_score: float = Field(description="Maximum possible score for the factor.", examples=[10.0])
    description: str = Field(description="Why the score was assigned.", examples=["Low recurring commitment burden."])
    evidence: list[str] = Field(description="Evidence used to derive the factor score.")


class CommitmentBreakdownItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    commitment_source: str = Field(description="Commitment source label.", examples=["Subscription"])
    active_commitments: int = Field(description="Active commitment count for the source.", examples=[4])
    mandatory_commitments: int = Field(description="Mandatory commitments in the source bucket.", examples=[3])
    optional_commitments: int = Field(description="Optional commitments in the source bucket.", examples=[1])
    monthly_amount: float = Field(description="Monthly amount contributed by this source.", examples=[4260.0])
    percentage_contribution: float = Field(description="Share of total monthly commitments contributed by this source.", examples=[18.2])
    largest_commitment: CommitmentItemResponse | None = Field(default=None, description="Largest commitment in the source bucket.")
    largest_optional_commitment: CommitmentItemResponse | None = Field(
        default=None,
        description="Largest optional commitment in the source bucket.",
    )


class CommitmentBreakdownResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    subscriptions: CommitmentBreakdownItemResponse = Field(description="Subscription contribution breakdown.")
    emis: CommitmentBreakdownItemResponse = Field(description="EMI contribution breakdown.")
    bnpl: CommitmentBreakdownItemResponse = Field(description="BNPL contribution breakdown.")


class CurrentFinancialStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    monthly_subscription_commitment: float = Field(description="Monthly subscription commitment.", examples=[568.0])
    monthly_emi_commitment: float = Field(description="Monthly EMI commitment.", examples=[1428.0])
    monthly_bnpl_commitment: float = Field(description="Monthly BNPL commitment.", examples=[0.0])
    monthly_total_commitments: float = Field(description="Total monthly commitment across all products.", examples=[1996.0])
    monthly_financial_capacity: float = Field(description="Monthly financial capacity.", examples=[156000.0])
    available_monthly_capacity: float = Field(description="Available monthly capacity after commitments.", examples=[154004.0])
    monthly_deficit: float = Field(description="Monthly deficit when commitments exceed capacity.", examples=[0.0])
    overcommitted_percentage: float = Field(description="Percentage of over-commitment when capacity is exceeded.", examples=[0.0])
    exposure_score: float = Field(description="Exposure score computed from commitments versus capacity.", examples=[1.28])
    exposure_formula: str = Field(description="Human-readable exposure formula explanation.", examples=["monthly_total_commitments / monthly_financial_capacity x 100"])
    current_message: str = Field(description="Summary of the user's current financial position.", examples=["Commitments remain within monthly capacity."])
    income_source: str = Field(default="Observed", description="Source label of the income (Observed, Estimated, or Manual).", examples=["Observed"])
    income_mode: str = Field(default="auto", description="Active income mode (auto, manual, or expected).", examples=["auto"])
    expected_monthly_income: float | None = Field(default=None, description="Configured expected monthly income if any.", examples=[85000.0])
    manual_monthly_income: float | None = Field(default=None, description="Configured manual monthly income if any.", examples=[75000.0])


class ExposureSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    exposure_score: float = Field(description="Exposure score computed from current commitments.", examples=[1.28])
    exposure_band: str = Field(description="Standardized exposure band derived from the exposure score.", examples=["Low"])
    explanation: str = Field(description="Short explanation of the exposure score.", examples=["Monthly commitments remain within monthly financial capacity."])
    evidence: list[str] = Field(description="Evidence used to explain the current exposure score.")
    largest_contributor: CommitmentItemResponse | None = Field(default=None, description="Largest current commitment across all products.")
    largest_optional_commitment: CommitmentItemResponse | None = Field(
        default=None,
        description="Largest optional commitment across all products.")
    commitment_concentration: str = Field(description="Narrative summary of concentration risk.", examples=["Subscription commitments are diversified across providers."])


class FinancialHealthResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    financial_health_score: float = Field(description="Deterministic financial health score on a 0-100 scale.", examples=[94.0])
    financial_health_label: str = Field(description="Health classification derived from the score.", examples=["Excellent"])
    risk_level: str = Field(description="Overall risk level derived from exposure and health.", examples=["Low"])
    rationale: list[str] = Field(description="Bullet-style rationale used for the score.")
    factor_scores: dict[str, FactorScoreResponse] = Field(description="Explainable factor-by-factor score breakdown.")


class AvailableCapacityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    available_monthly_capacity: float = Field(description="Remaining monthly capacity after current commitments.", examples=[154004.0])
    remaining_capacity_percent: float = Field(description="Share of monthly capacity that remains available.", examples=[98.72])
    monthly_deficit: float = Field(description="Monthly deficit if commitments exceed capacity.", examples=[0.0])
    overcommitted_amount: float = Field(description="Amount by which commitments exceed capacity.", examples=[0.0])
    overcommitted_percentage: float = Field(description="Percentage by which commitments exceed capacity.", examples=[0.0])
    critical_warning: str | None = Field(default=None, description="Critical warning when the user is overcommitted.")


class ExposureRecommendationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    recommendation_type: str = Field(description="Constructive recommendation label.", examples=["Subscription Review"])
    priority: str = Field(description="Priority bucket for the recommendation.", examples=["High"])
    impact_score: float = Field(description="Impact score from 0 to 100.", examples=[70.0])
    message: str = Field(description="Short recommendation message.", examples=["Review subscription commitments with the highest monthly contribution."])
    reason: str = Field(description="Why the recommendation is being made.", examples=["Subscriptions represent a material share of monthly commitments."])
    expected_benefit: str = Field(description="Expected benefit if the recommendation is followed.", examples=["Creates room for higher-priority commitments without reducing convenience."])
    action_required: str = Field(description="Concrete action the user can take.", examples=["Review recurring subscription list and keep only the subscriptions that add clear value."])
    estimated_effort: str = Field(description="How difficult it is for the user to act on the recommendation.", examples=["Easy"])
    estimated_monthly_saving: float | None = Field(default=None, description="Estimated monthly saving when it can be derived from current data.")
    estimated_annual_saving: float | None = Field(default=None, description="Estimated annual saving when it can be derived from current data.")
    estimated_exposure_reduction: float | None = Field(default=None, description="Estimated exposure reduction when it can be derived from current data.")
    financial_benefit: str | None = Field(default=None, description="Short quantitative or qualitative benefit summary when available.")


class ForecastEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    forecast_type: str = Field(description="Forecast bucket label.", examples=["Upcoming EMI Installment"])
    title: str = Field(description="Forecast event title.", examples=["EV EMI installment due"])
    expected_date: date | None = Field(default=None, description="Expected date for the future event.")
    expected_amount: float = Field(description="Expected amount associated with the future event.", examples=[18403.0])
    confidence: float = Field(description="Confidence score for the forecast event.", examples=[0.9])
    source: str = Field(description="Source intelligence engine or commitment class.", examples=["EMI"])
    evidence: list[str] = Field(description="Evidence used to forecast the event.")
    note: str = Field(description="Short explanatory note.", examples=["Based on the latest observed EMI installment cadence."])


class FinancialForecastResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    upcoming_trial_conversions: list[ForecastEventResponse] = Field(description="Forecasted trial-to-paid conversions.")
    upcoming_paid_subscriptions: list[ForecastEventResponse] = Field(description="Forecasted paid subscription charges.")
    upcoming_emi_commencements: list[ForecastEventResponse] = Field(description="Forecasted EMI commencements or renewal starts.")
    upcoming_bnpl_installments: list[ForecastEventResponse] = Field(description="Forecasted BNPL installments.")
    upcoming_autopay_charges: list[ForecastEventResponse] = Field(description="Forecasted charges expected to run via AutoPay.")
    future_monthly_commitments: float = Field(description="Projected monthly commitments after forecasted additions.", examples=[1996.0])
    future_exposure_score: float = Field(description="Projected exposure score after forecasted additions.", examples=[1.28])
    exposure_increase: float = Field(description="Increase in exposure score relative to the current state.", examples=[0.0])
    future_financial_health: str = Field(description="Projected financial health label.", examples=["Excellent"])
    has_forecast_events: bool = Field(description="Whether any forecasted events were detected within the horizon.", examples=[False])
    forecast_explanation: str = Field(description="Plain-language explanation of the forecast outcome.", examples=["No upcoming recurring commitments were detected within the forecast horizon."])
    preventive_recommendations: list[ExposureRecommendationResponse] = Field(description="Preventive recommendations driven by forecasted events.")
    forecast_notes: list[str] = Field(description="Narrative notes for the forecast section.")


class ExposureMetadataResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    generated_at: datetime = Field(description="Timestamp when the exposure report was generated.")
    execution_time_seconds: float = Field(description="Total execution time for the exposure analysis.", examples=[0.08])
    data_sources: list[str] = Field(description="Services used to build the response.", examples=[["Subscription Intelligence", "EMI Intelligence", "BNPL Intelligence"]])
    forecast_horizon_days: int = Field(description="Forecast horizon in days.", examples=[30])
    engine_version: str = Field(description="Exposure engine version for traceability.", examples=["1.0.0"])
    rules_version: str = Field(description="Ruleset version for traceability.", examples=["2026.1"])
    api_version: str = Field(description="Public API version used for the response.", examples=["v1"])


class ExposureIntelligenceResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "user_id": "U001",
                    "user_profile": {
                        "user_id": "U001",
                        "persona": "Self-Employed Users",
                        "income_type": "Business",
                        "monthly_financial_capacity": 156000,
                        "age_group": "25-34",
                        "city": "Jaipur",
                        "financial_profile": {
                            "user_id": "U001",
                            "persona": "Self-Employed Users",
                            "monthly_financial_capacity": 156000,
                            "monthly_commitments": 1675.5,
                            "exposure_score": 1.1,
                            "active_subscriptions": 1,
                            "active_emis": 1,
                            "active_bnpl": 0,
                            "total_active_commitments": 2,
                            "total_transactions": 21,
                            "transaction_success_rate": "100.0%",
                            "financial_health": "Healthy",
                            "is_leakage_user": "No",
                            "leakage_subscription_count": 0,
                            "is_heavy_bnpl_user": "No",
                            "heavy_bnpl_providers": 0,
                            "is_heavy_emi_user": "No",
                            "heavy_emi_providers": 0,
                            "special_scenario": "Normal User"
                        }
                    },
                    "current_financial_status": {
                        "monthly_subscription_commitment": 568.0,
                        "monthly_emi_commitment": 1428.0,
                        "monthly_bnpl_commitment": 0.0,
                        "monthly_total_commitments": 1996.0,
                        "monthly_financial_capacity": 156000.0,
                        "available_monthly_capacity": 154004.0,
                        "monthly_deficit": 0.0,
                        "overcommitted_percentage": 0.0,
                        "exposure_score": 1.28,
                        "exposure_formula": "monthly_total_commitments / monthly_financial_capacity x 100",
                        "current_message": "Commitments remain within monthly capacity."
                    },
                    "exposure_summary": {
                        "exposure_score": 1.28,
                        "exposure_band": "Low",
                        "explanation": "Monthly commitments remain within monthly financial capacity.",
                        "evidence": [
                            "subscriptions=568.0",
                            "emis=1428.0",
                            "bnpl=0.0",
                            "monthly_financial_capacity=156000.0",
                            "exposure_score=1.28"
                        ],
                        "largest_contributor": {
                            "commitment_name": "Kitchen EMI",
                            "commitment_source": "EMI",
                            "monthly_amount": 1428.0,
                            "total_amount": 9996.0,
                            "commitment_type": "Optional"
                        },
                        "largest_optional_commitment": {
                            "commitment_name": "Kitchen EMI",
                            "commitment_source": "EMI",
                            "monthly_amount": 1428.0,
                            "total_amount": 9996.0,
                            "commitment_type": "Optional"
                        },
                        "commitment_concentration": "EMI contributes 71.5% of total monthly commitments."
                    },
                    "financial_health": {
                        "financial_health_score": 94.0,
                        "financial_health_label": "Excellent",
                        "risk_level": "Low",
                        "rationale": [
                            "Exposure score is 1.28%.",
                            "Payment success rate is 100.0%.",
                            "AutoPay coverage is 100.0%.",
                            "2 active recurring commitments are being tracked.",
                            "The largest commitment source contributes 71.5% of monthly commitments."
                        ],
                        "factor_scores": {
                            "exposure": {
                                "score": 35.0,
                                "max_score": 35.0,
                                "description": "Minimal recurring burden relative to capacity.",
                                "evidence": ["exposure_score=1.28"]
                            },
                            "payment_behaviour": {
                                "score": 25.0,
                                "max_score": 25.0,
                                "description": "Outstanding payment reliability across recurring commitments.",
                                "evidence": ["payment_success_rate=100.0", "failed_payments=0", "pending_payments=0"]
                            },
                            "autopay": {
                                "score": 15.0,
                                "max_score": 15.0,
                                "description": "AutoPay is enabled for nearly all active commitments.",
                                "evidence": ["autopay_coverage=100.0"]
                            },
                            "commitment_diversity": {
                                "score": 7.0,
                                "max_score": 10.0,
                                "description": "Commitments are split across two product types.",
                                "evidence": ["active_sources=Subscription, EMI"]
                            },
                            "financial_discipline": {
                                "score": 10.0,
                                "max_score": 10.0,
                                "description": "The user shows strong payment discipline with efficient recurring payment handling.",
                                "evidence": ["payment_success_rate=100.0", "autopay_coverage=100.0", "failed_payments=0", "pending_payments=0"]
                            },
                            "commitment_concentration": {
                                "score": 2.0,
                                "max_score": 5.0,
                                "description": "The portfolio is heavily concentrated in one commitment source.",
                                "evidence": ["largest_source_share=71.5%"]
                            }
                        }
                    },
                    "commitment_breakdown": {
                        "subscriptions": {
                            "commitment_source": "Subscription",
                            "active_commitments": 1,
                            "mandatory_commitments": 0,
                            "optional_commitments": 1,
                            "monthly_amount": 568.0,
                            "percentage_contribution": 28.46,
                            "largest_commitment": {
                                "commitment_name": "HealthifyMe",
                                "commitment_source": "Subscription",
                                "monthly_amount": 568.0,
                                "total_amount": 3408.0,
                                "commitment_type": "Optional"
                            },
                            "largest_optional_commitment": {
                                "commitment_name": "HealthifyMe",
                                "commitment_source": "Subscription",
                                "monthly_amount": 568.0,
                                "total_amount": 3408.0,
                                "commitment_type": "Optional"
                            }
                        },
                        "emis": {
                            "commitment_source": "EMI",
                            "active_commitments": 1,
                            "mandatory_commitments": 0,
                            "optional_commitments": 1,
                            "monthly_amount": 1428.0,
                            "percentage_contribution": 71.54,
                            "largest_commitment": {
                                "commitment_name": "Kitchen EMI",
                                "commitment_source": "EMI",
                                "monthly_amount": 1428.0,
                                "total_amount": 9996.0,
                                "commitment_type": "Optional"
                            },
                            "largest_optional_commitment": {
                                "commitment_name": "Kitchen EMI",
                                "commitment_source": "EMI",
                                "monthly_amount": 1428.0,
                                "total_amount": 9996.0,
                                "commitment_type": "Optional"
                            }
                        },
                        "bnpl": {
                            "commitment_source": "BNPL",
                            "active_commitments": 0,
                            "mandatory_commitments": 0,
                            "optional_commitments": 0,
                            "monthly_amount": 0.0,
                            "percentage_contribution": 0.0,
                            "largest_commitment": None,
                            "largest_optional_commitment": None
                        }
                    },
                    "available_capacity": {
                        "available_monthly_capacity": 154004.0,
                        "remaining_capacity_percent": 98.72,
                        "monthly_deficit": 0.0,
                        "overcommitted_amount": 0.0,
                        "overcommitted_percentage": 0.0,
                        "critical_warning": None
                    },
                    "recommendations": [
                        {
                            "recommendation_type": "Maintain Current Discipline",
                            "priority": "Low",
                            "impact_score": 96.0,
                            "message": "Maintain the current financial rhythm and keep tracking recurring commitments.",
                            "reason": "The user remains within capacity and payment behaviour is stable.",
                            "expected_benefit": "Preserves the current healthy financial position.",
                            "action_required": "Continue paying on time and review new commitments before activation.",
                            "estimated_effort": "Very Easy",
                            "estimated_monthly_saving": None,
                            "estimated_annual_saving": None,
                            "estimated_exposure_reduction": None,
                            "financial_benefit": None
                        },
                        {
                            "recommendation_type": "EMI Planning",
                            "priority": "High",
                            "impact_score": 71.54,
                            "message": "Plan EMI cash flow around the largest installment commitments.",
                            "reason": "EMIs are a major fixed component of the monthly budget.",
                            "expected_benefit": "Improves repayment predictability and reduces month-end pressure.",
                            "action_required": "Align EMI dates with income timing and review the largest installments first.",
                            "estimated_effort": "Medium",
                            "estimated_monthly_saving": None,
                            "estimated_annual_saving": None,
                            "estimated_exposure_reduction": None,
                            "financial_benefit": None
                        },
                        {
                            "recommendation_type": "Subscription Review",
                            "priority": "High",
                            "impact_score": 28.46,
                            "message": "Review subscription commitments with the highest monthly contribution.",
                            "reason": "Subscriptions represent a material share of monthly commitments.",
                            "expected_benefit": "Creates room for higher-priority commitments without reducing convenience.",
                            "action_required": "Review recurring subscription list and keep only the subscriptions that add clear value.",
                            "estimated_effort": "Easy",
                            "estimated_monthly_saving": 568.0,
                            "estimated_annual_saving": 6816.0,
                            "estimated_exposure_reduction": 0.36,
                            "financial_benefit": "Estimated recurring monthly saving of Rs. 568 (Rs. 6,816 annually)."
                        }
                    ],
                    "financial_forecast": {
                        "upcoming_trial_conversions": [],
                        "upcoming_paid_subscriptions": [],
                        "upcoming_emi_commencements": [],
                        "upcoming_bnpl_installments": [],
                        "upcoming_autopay_charges": [],
                        "future_monthly_commitments": 1996.0,
                        "future_exposure_score": 1.28,
                        "exposure_increase": 0.0,
                        "future_financial_health": "Excellent",
                        "has_forecast_events": False,
                        "forecast_explanation": "No upcoming recurring commitments were detected within the forecast horizon.",
                        "preventive_recommendations": [],
                        "forecast_notes": [
                            "Forecast items are projections based on the latest observed transaction cadence.",
                            "Forecasted values are not included in the current exposure calculation.",
                            "No upcoming recurring commitments were detected within the forecast horizon."
                        ]
                    },
                    "metadata": {
                        "generated_at": "2026-07-06T11:39:53.494350Z",
                        "execution_time_seconds": 0.08,
                        "data_sources": ["Subscription Intelligence", "EMI Intelligence", "BNPL Intelligence"],
                        "forecast_horizon_days": 30,
                        "engine_version": "1.0.0",
                        "rules_version": "2026.1",
                        "api_version": "v1"
                    }
                }
            ]
        },
    )

    user_id: str = Field(description="Unique user identifier for the analyzed account.", examples=["U001"])
    payment_reliability: float | None = Field(
        default=None,
        description="Authoritative current payment reliability as a fraction from 0 to 1.",
        examples=[1.0],
    )
    user_profile: UserResponse = Field(description="User profile and financial profile data.")
    current_financial_status: CurrentFinancialStatusResponse = Field(description="Current financial position of the user.")
    exposure_summary: ExposureSummaryResponse = Field(description="Explainable exposure summary.")
    financial_health: FinancialHealthResponse = Field(description="Deterministic financial health assessment.")
    commitment_breakdown: CommitmentBreakdownResponse = Field(description="Commitment breakdown across subscriptions, EMIs, and BNPL.")
    available_capacity: AvailableCapacityResponse = Field(description="Available monthly capacity and overcommitment details.")
    recommendations: list[ExposureRecommendationResponse] = Field(description="Constructive recommendations based on current status.")
    financial_forecast: FinancialForecastResponse = Field(description="Forward-looking forecast based on the current profile.")
    metadata: ExposureMetadataResponse = Field(description="Report metadata and execution details.")