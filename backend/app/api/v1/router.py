from fastapi import APIRouter

from app.api.v1.endpoints.bnpl import router as bnpl_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.copilot import router as copilot_router
from app.api.v1.endpoints.dashboard import router as dashboard_router
from app.api.v1.endpoints.dataset import router as dataset_router
from app.api.v1.endpoints.emis import router as emis_router
from app.api.v1.endpoints.exposure import router as exposure_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.ml import router as ml_router
from app.api.v1.endpoints.subscriptions import router as subscriptions_router
from app.api.v1.endpoints.transactions import router as transactions_router
from app.api.v1.endpoints.simulator import router as simulator_router
from app.api.v1.endpoints.history import router as history_router
from app.api.v1.endpoints.recurring_payments import router as recurring_payments_router
from app.api.v1.endpoints.trial_intelligence import router as trial_intelligence_router
from app.api.v1.endpoints.commitments import router as commitments_router
from app.api.v1.endpoints.forecast import router as forecast_router
from app.api.v1.endpoints.goals import router as goals_router
from app.api.v1.endpoints.income import router as income_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(health_router)
router.include_router(dataset_router)
router.include_router(subscriptions_router)
router.include_router(emis_router)
router.include_router(bnpl_router)
router.include_router(exposure_router)
router.include_router(history_router)
router.include_router(dashboard_router)
router.include_router(ml_router)
router.include_router(copilot_router)
router.include_router(transactions_router)
router.include_router(simulator_router)
router.include_router(recurring_payments_router)
router.include_router(trial_intelligence_router)
router.include_router(commitments_router)
router.include_router(forecast_router)
router.include_router(goals_router)
router.include_router(income_router)
