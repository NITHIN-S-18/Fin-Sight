from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.database.connection import SessionLocal
from app.database.models.user import User
from app.repositories.user_repository import UserRepository


class PostgresUserRepository(UserRepository):
    """PostgreSQL-backed implementation of the user repository interface.

    All user and financial-profile data is read from PostgreSQL.
    """

    def __init__(self, session_factory: Any | None = None) -> None:
        self._session_factory = session_factory or SessionLocal

    @staticmethod
    def _as_int_or_float(value: Any) -> Any:
        if value is None:
            return None

        if isinstance(value, float) and value.is_integer():
            return int(value)

        return value

    @staticmethod
    def _serialize_profile(profile: Any) -> dict[str, Any]:
        return {
            "user_id": profile.user_id,
            "persona": profile.persona,
            "monthly_financial_capacity": PostgresUserRepository._as_int_or_float(
                profile.financial_capacity
            ),
            "monthly_commitments": profile.monthly_commitments,
            "exposure_score": profile.exposure_score,
            "active_subscriptions": profile.active_subscriptions,
            "active_emis": profile.active_emis,
            "active_bnpl": profile.active_bnpl,
            "total_active_commitments": profile.total_active_commitments,
            "total_transactions": profile.total_transactions,
            "transaction_success_rate": profile.transaction_success_rate,
            "financial_health": profile.financial_health,
            "is_leakage_user": profile.is_leakage_user,
            "leakage_subscription_count": profile.leakage_subscription_count,
            "is_heavy_bnpl_user": profile.is_heavy_bnpl_user,
            "heavy_bnpl_providers": profile.heavy_bnpl_providers,
            "is_heavy_emi_user": profile.is_heavy_emi_user,
            "heavy_emi_providers": profile.heavy_emi_providers,
            "special_scenario": profile.special_scenario,
        }

    def _serialize_user(
        self,
        row: User,
        include_profile: bool = False,
    ) -> dict[str, Any]:

        data = {
            "user_id": row.user_id,
            "persona": row.persona,
            "income_type": row.income_type,
            "monthly_financial_capacity": self._as_int_or_float(
                row.monthly_financial_capacity
            ),
            "age_group": row.age_group,
            "city": row.city,
        }

        if include_profile:
            profile = row.financial_profile

            data["financial_profile"] = (
                self._serialize_profile(profile)
                if profile is not None
                else None
            )

        return data

    def get_by_id(self, identifier: Any) -> Any:
        return self.get_user(str(identifier))

    def get_all(self) -> list[Any]:
        return self.get_users()

    def get_user(self, user_id: str) -> Any:
        with self._session_factory() as session:
            row = (
                session.execute(
                    select(User).where(User.user_id == user_id)
                )
                .scalar_one_or_none()
            )

            if row is None:
                raise KeyError(f"User not found: {user_id}")

            return self._serialize_user(
                row,
                include_profile=True,
            )

    def get_users(self) -> list[Any]:
        with self._session_factory() as session:
            rows = (
                session.execute(select(User))
                .scalars()
                .all()
            )

            return [
                self._serialize_user(row)
                for row in rows
            ]