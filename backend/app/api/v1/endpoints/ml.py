from fastapi import APIRouter, Depends, Path, status

from app.schemas.ml import (
    AnomalyResponse,
    ExposureForecastResponse,
    FinancialDistressResponse,
    FinancialIntelligenceResponseSchema,
    FinancialShortfallResponse,
    PersonaResponse,
)
from app.services.ml_service import MLService, get_ml_service
from app.core.security import get_current_financial_user, require_financial_user
from app.database.models.user import User
from app.services.shortfall_service import FinancialShortfallService, get_shortfall_service

router = APIRouter(prefix="/ml", tags=["Predictive Intelligence"])


@router.get(
    "/shortfall/{user_id}",
    response_model=FinancialShortfallResponse,
    summary="Predict next-month financial shortfall risk",
)
async def get_shortfall(
    user_id: str = Path(..., description="Unique financial user identifier."),
    current_user: User = Depends(get_current_financial_user),
    service: FinancialShortfallService = Depends(get_shortfall_service),
) -> FinancialShortfallResponse:
    return service.predict(require_financial_user(user_id, current_user))


@router.get(
    "/distress/{user_id}",
    response_model=FinancialDistressResponse,
    summary="Predict financial distress risk",
    description="Returns a business-aware distress prediction, supporting evidence, and a plain-language recommendation derived from the existing financial intelligence snapshot.",
    response_description="Explainable financial distress prediction.",
)
async def get_distress(
    user_id: str = Path(..., description="Unique user identifier such as U001.", examples=["U001"]),
    current_user: User = Depends(get_current_financial_user),
    service: MLService = Depends(get_ml_service),
) -> FinancialDistressResponse:
    return service.get_distress(require_financial_user(user_id, current_user))


@router.get(
    "/exposure/{user_id}",
    response_model=ExposureForecastResponse,
    summary="Forecast future exposure",
    description="Returns the forecasted exposure score together with explainability context and a recommendation based on the current financial profile.",
    response_description="Explainable exposure forecast.",
)
async def get_exposure_forecast(
    user_id: str = Path(..., description="Unique user identifier such as U001.", examples=["U001"]),
    current_user: User = Depends(get_current_financial_user),
    service: MLService = Depends(get_ml_service),
) -> ExposureForecastResponse:
    return service.get_exposure_forecast(require_financial_user(user_id, current_user))


@router.get(
    "/persona/{user_id}",
    response_model=PersonaResponse,
    summary="Infer financial persona",
    description="Returns a data-driven financial persona derived from cluster characteristics, together with business-oriented explanation text.",
    response_description="Explainable behavioural persona output.",
)
async def get_persona(
    user_id: str = Path(..., description="Unique user identifier such as U001.", examples=["U001"]),
    current_user: User = Depends(get_current_financial_user),
    service: MLService = Depends(get_ml_service),
) -> PersonaResponse:
    return service.get_persona(require_financial_user(user_id, current_user))


@router.get(
    "/anomaly/{user_id}",
    response_model=AnomalyResponse,
    summary="Detect financial anomalies",
    description="Returns an anomaly score and a business-friendly explanation for unusual financial behaviour.",
    response_description="Explainable anomaly detection output.",
)
async def get_anomaly(
    user_id: str = Path(..., description="Unique user identifier such as U001.", examples=["U001"]),
    current_user: User = Depends(get_current_financial_user),
    service: MLService = Depends(get_ml_service),
) -> AnomalyResponse:
    return service.get_anomaly(require_financial_user(user_id, current_user))


@router.get(
    "/intelligence/{user_id}",
    response_model=FinancialIntelligenceResponseSchema,
    summary="Get fused predictive intelligence",
    description="Returns the unified Phase 9 response by combining distress, exposure, persona, and anomaly predictions with weighted fusion and explainable insights.",
    response_description="Unified fused predictive intelligence response.",
)
async def get_intelligence(
    user_id: str = Path(..., description="Unique user identifier such as U001.", examples=["U001"]),
    current_user: User = Depends(get_current_financial_user),
    service: MLService = Depends(get_ml_service),
) -> FinancialIntelligenceResponseSchema:
    return service.get_intelligence(require_financial_user(user_id, current_user))
