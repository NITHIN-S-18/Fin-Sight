from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class FinancialSnapshot:
    """
    Data structure representing an isolated financial snapshot of a user.
    """

    user_id: str
    monthly_income: float
    monthly_commitments: float
    exposure_score: float
    financial_health_score: float
    financial_health_status: str
    active_subscriptions_count: int = 0
    active_emis_count: int = 0
    active_bnpl_count: int = 0
    monthly_savings: float = 0.0
    subscriptions: list[dict[str, Any]] = field(default_factory=list)
    emis: list[dict[str, Any]] = field(default_factory=list)
    bnpl_items: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TwinMetadata:
    """
    Metadata associated with a Digital Twin instance.
    Includes tracking fields independent of any database or external persistence.
    """

    twin_id: str
    created_at: str
    original_user_id: str
    scenario_count: int = 0
    parent_snapshot_id: str | None = None
    simulation_status: str = "created"
    scenario_applied: str | None = None
    version: int = 1


@dataclass
class DigitalTwin:
    """
    In-memory isolated Digital Twin containing snapshot data and execution metadata.
    """

    snapshot: FinancialSnapshot
    metadata: TwinMetadata


class DigitalTwinEngine:
    """
    Digital Twin Engine.
    Generates isolated, in-memory copies of user financial snapshots for simulation.
    No database, file system, or API persistence.
    """

    def clone_snapshot(self, snapshot: FinancialSnapshot) -> FinancialSnapshot:
        """
        Creates a completely independent deep copy of a FinancialSnapshot.
        Guarantees original snapshot object remains untouched.
        """
        return copy.deepcopy(snapshot)

    def validate_snapshot(self, snapshot: FinancialSnapshot) -> bool:
        """
        Validates essential invariants of a FinancialSnapshot.
        """
        if snapshot is None:
            return False
        if not snapshot.user_id:
            return False
        if snapshot.monthly_income < 0.0 or snapshot.monthly_commitments < 0.0:
            return False
        if snapshot.exposure_score < 0.0 or snapshot.financial_health_score < 0.0:
            return False
        return True

    def create_twin(
        self,
        snapshot: FinancialSnapshot,
        twin_id: str | None = None,
        scenario_name: str | None = None,
    ) -> DigitalTwin:
        """
        Generates a new DigitalTwin containing a deep-copied FinancialSnapshot and metadata.
        """
        if not self.validate_snapshot(snapshot):
            raise ValueError("Invalid FinancialSnapshot provided to DigitalTwinEngine.")

        snapshot_copy = self.clone_snapshot(snapshot)
        generated_id = twin_id or str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()
        parent_id = str(snapshot.metadata.get("snapshot_id", snapshot.user_id))

        metadata = TwinMetadata(
            twin_id=generated_id,
            created_at=now_iso,
            original_user_id=snapshot.user_id,
            scenario_count=0,
            parent_snapshot_id=parent_id,
            simulation_status="created",
            scenario_applied=scenario_name,
            version=1,
        )

        return DigitalTwin(snapshot=snapshot_copy, metadata=metadata)
