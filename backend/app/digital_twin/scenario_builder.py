from __future__ import annotations

import copy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.digital_twin.twin_engine import DigitalTwin, DigitalTwinEngine, FinancialSnapshot


class ScenarioType(str, Enum):
    CANCEL_SUBSCRIPTION = "cancel_subscription"
    ADD_SUBSCRIPTION = "add_subscription"
    NEW_EMI = "new_emi"
    CLOSE_EMI = "close_emi"
    SALARY_INCREASE = "salary_increase"
    SALARY_REDUCTION = "salary_reduction"
    CLOSE_BNPL = "close_bnpl"
    ADD_BNPL = "add_bnpl"
    ADD_OTHER = "add_other"
    OTHER_COMMITMENT = "other_commitment"


@dataclass
class Scenario:
    """
    Data structure defining a simulation scenario and parameters.
    """

    scenario_type: ScenarioType
    parameters: dict[str, Any] = field(default_factory=dict)
    description: str = ""


@dataclass
class ScenarioResult:
    """
    Result of a scenario application on a Digital Twin.
    If validation fails, success=False, modified_twin=None, applied_changes={}, message contains reason.
    """

    original_twin: DigitalTwin
    modified_twin: DigitalTwin | None
    scenario: Scenario
    applied_changes: dict[str, Any] = field(default_factory=dict)
    success: bool = True
    message: str = ""


class ScenarioBuilder:
    """
    Scenario Builder.
    Applies what-if financial modifications to an isolated Digital Twin.
    Performs validation prior to applying changes without throwing exceptions.
    Never mutates the original Digital Twin.
    """

    def __init__(self, twin_engine: DigitalTwinEngine | None = None) -> None:
        self._twin_engine = twin_engine or DigitalTwinEngine()

    @staticmethod
    def _exposure_factor_points(exposure_score: float) -> float:
        """
        Continuous interpolation of FinSight's 35-point exposure weight curve.
        """
        if exposure_score <= 5.0:
            return 35.0
        if exposure_score <= 25.0:
            return 35.0 - ((exposure_score - 5.0) / 20.0) * 5.0
        if exposure_score <= 50.0:
            return 30.0 - ((exposure_score - 25.0) / 25.0) * 8.0
        if exposure_score <= 75.0:
            return 22.0 - ((exposure_score - 50.0) / 25.0) * 10.0
        if exposure_score <= 100.0:
            return 12.0 - ((exposure_score - 75.0) / 25.0) * 8.0
        return max(0.0, 4.0 - ((exposure_score - 100.0) / 25.0) * 4.0)

    @staticmethod
    def _financial_health_label(score: float) -> str:
        """
        Authoritative financial health labels matching ExposureService thresholds.
        """
        if score >= 92.0:
            return "Excellent"
        if score >= 80.0:
            return "Healthy"
        if score >= 65.0:
            return "Moderate"
        if score >= 45.0:
            return "Risky"
        return "Critical"

    @classmethod
    def _recalculate_snapshot_metrics(
        cls,
        snapshot: FinancialSnapshot,
        baseline_snapshot: FinancialSnapshot | None = None,
    ) -> None:
        """
        Recalculates derived fields (savings, exposure score, financial health)
        after parameters are modified.
        Grounds financial health in the user's authentic baseline to eliminate
        inconsistent score/label transitions.
        """
        snapshot.monthly_income = max(0.0, float(snapshot.monthly_income))
        snapshot.monthly_commitments = max(0.0, float(snapshot.monthly_commitments))
        snapshot.monthly_savings = max(0.0, snapshot.monthly_income - snapshot.monthly_commitments)

        if snapshot.monthly_income > 0:
            raw_exposure = (snapshot.monthly_commitments / snapshot.monthly_income) * 100.0
            snapshot.exposure_score = round(max(0.0, raw_exposure), 2)
        else:
            snapshot.exposure_score = 100.0

        if snapshot.monthly_commitments <= 0.0:
            snapshot.financial_health_score = 100.0
            snapshot.financial_health_status = "Excellent"
            return

        current_exp_pts = cls._exposure_factor_points(snapshot.exposure_score)

        if baseline_snapshot is not None and baseline_snapshot.financial_health_score > 0:
            base_exp_pts = cls._exposure_factor_points(baseline_snapshot.exposure_score)
            delta_pts = current_exp_pts - base_exp_pts

            # Over-capacity penalty if exposure exceeds 100%
            if snapshot.exposure_score > 100.0:
                overcommit_penalty = (snapshot.exposure_score - 100.0) * 0.5
                delta_pts -= overcommit_penalty

            projected_score = baseline_snapshot.financial_health_score + delta_pts
            snapshot.financial_health_score = round(min(98.0, max(5.0, projected_score)), 2)
        else:
            snapshot.financial_health_score = round(min(98.0, max(5.0, 50.0 + current_exp_pts)), 2)

        snapshot.financial_health_status = cls._financial_health_label(snapshot.financial_health_score)

    @staticmethod
    def _matches_item(item: dict[str, Any], target_identifier: str) -> bool:
        if not target_identifier:
            return False
        target_lower = str(target_identifier).strip().lower()
        item_id = str(item.get("id", "")).strip().lower()
        item_name = str(item.get("name", "")).strip().lower()
        return target_lower in (item_id, item_name)

    def apply_scenario(self, twin: DigitalTwin, scenario: Scenario) -> ScenarioResult:
        """
        Validates parameters and applies requested scenario to a deep copy of the Digital Twin.
        Returns ScenarioResult with success=False if validation fails.
        """
        if not twin or not twin.snapshot:
            return ScenarioResult(
                original_twin=twin,
                modified_twin=None,
                scenario=scenario,
                applied_changes={},
                success=False,
                message="Validation failed: A valid DigitalTwin is required.",
            )

        params = scenario.parameters
        stype = scenario.scenario_type
        snap = twin.snapshot

        # Validation Step
        if stype == ScenarioType.CANCEL_SUBSCRIPTION:
            target = params.get("subscription_id") or params.get("name")
            matched_subs = [s for s in snap.subscriptions if self._matches_item(s, str(target))]
            if not matched_subs and snap.subscriptions:
                return ScenarioResult(
                    original_twin=twin,
                    modified_twin=None,
                    scenario=scenario,
                    applied_changes={},
                    success=False,
                    message=f"Validation failed: Subscription '{target}' does not exist in financial snapshot.",
                )

        elif stype == ScenarioType.CLOSE_EMI:
            target = params.get("emi_id") or params.get("name")
            matched_emis = [e for e in snap.emis if self._matches_item(e, str(target))]
            if not matched_emis and snap.emis:
                return ScenarioResult(
                    original_twin=twin,
                    modified_twin=None,
                    scenario=scenario,
                    applied_changes={},
                    success=False,
                    message=f"Validation failed: EMI '{target}' does not exist in financial snapshot.",
                )

        elif stype == ScenarioType.CLOSE_BNPL:
            target = params.get("bnpl_id") or params.get("name")
            matched_bnpl = [b for b in snap.bnpl_items if self._matches_item(b, str(target))]
            if not matched_bnpl and snap.bnpl_items:
                return ScenarioResult(
                    original_twin=twin,
                    modified_twin=None,
                    scenario=scenario,
                    applied_changes={},
                    success=False,
                    message=f"Validation failed: BNPL obligation '{target}' does not exist in financial snapshot.",
                )

        elif stype == ScenarioType.ADD_SUBSCRIPTION:
            cost = float(params.get("monthly_cost", params.get("amount", 0.0)))
            if cost <= 0.0:
                return ScenarioResult(
                    original_twin=twin,
                    modified_twin=None,
                    scenario=scenario,
                    applied_changes={},
                    success=False,
                    message="Validation failed: Subscription cost must be greater than 0.",
                )

        elif stype in (ScenarioType.NEW_EMI, ScenarioType.ADD_OTHER, ScenarioType.OTHER_COMMITMENT):
            amount = float(params.get("monthly_amount", params.get("monthly_emi", params.get("amount", 0.0))))
            if amount <= 0.0:
                return ScenarioResult(
                    original_twin=twin,
                    modified_twin=None,
                    scenario=scenario,
                    applied_changes={},
                    success=False,
                    message="Validation failed: Commitment monthly payment must be greater than 0.",
                )

        elif stype == ScenarioType.ADD_BNPL:
            amount = float(params.get("monthly_installment", params.get("amount", 0.0)))
            if amount <= 0.0:
                return ScenarioResult(
                    original_twin=twin,
                    modified_twin=None,
                    scenario=scenario,
                    applied_changes={},
                    success=False,
                    message="Validation failed: BNPL monthly installment must be greater than 0.",
                )

        elif stype == ScenarioType.SALARY_INCREASE:
            amount = float(params.get("amount", 0.0))
            pct = float(params.get("percentage", 0.0))
            if amount <= 0.0 and pct <= 0.0:
                return ScenarioResult(
                    original_twin=twin,
                    modified_twin=None,
                    scenario=scenario,
                    applied_changes={},
                    success=False,
                    message="Validation failed: Salary increase amount or percentage must be greater than 0.",
                )

        elif stype == ScenarioType.SALARY_REDUCTION:
            amount = float(params.get("amount", 0.0))
            pct = float(params.get("percentage", 0.0))
            if amount <= 0.0 and pct <= 0.0:
                return ScenarioResult(
                    original_twin=twin,
                    modified_twin=None,
                    scenario=scenario,
                    applied_changes={},
                    success=False,
                    message="Validation failed: Salary reduction amount or percentage must be greater than 0.",
                )

        # Deep Copy snapshot and metadata after validation passes
        cloned_snapshot = self._twin_engine.clone_snapshot(snap)
        cloned_metadata = copy.deepcopy(twin.metadata)
        cloned_metadata.scenario_applied = stype.value
        cloned_metadata.scenario_count += 1
        cloned_metadata.simulation_status = "simulated"
        cloned_metadata.version += 1

        modified_twin = DigitalTwin(snapshot=cloned_snapshot, metadata=cloned_metadata)
        applied_changes: dict[str, Any] = {}

        if stype == ScenarioType.CANCEL_SUBSCRIPTION:
            target = params.get("subscription_id") or params.get("name")
            matched_subs = [s for s in cloned_snapshot.subscriptions if self._matches_item(s, str(target))]
            cost = float(params.get("monthly_cost", params.get("amount", 0.0)))
            if matched_subs and "monthly_cost" in matched_subs[0]:
                cost = float(matched_subs[0]["monthly_cost"])

            cloned_snapshot.monthly_commitments = max(0.0, cloned_snapshot.monthly_commitments - cost)
            if cloned_snapshot.active_subscriptions_count > 0:
                cloned_snapshot.active_subscriptions_count -= 1
            cloned_snapshot.subscriptions = [
                s for s in cloned_snapshot.subscriptions if not self._matches_item(s, str(target))
            ]
            applied_changes = {"reduced_commitment": cost, "cancelled_subscription": target}

        elif stype == ScenarioType.ADD_SUBSCRIPTION:
            cost = float(params.get("monthly_cost", params.get("amount", 0.0)))
            name = params.get("name", "New Subscription")
            cloned_snapshot.monthly_commitments += cost
            cloned_snapshot.active_subscriptions_count += 1
            cloned_snapshot.subscriptions.append({"name": name, "monthly_cost": cost})
            applied_changes = {"added_commitment": cost, "added_subscription": name}

        elif stype in (ScenarioType.NEW_EMI, ScenarioType.ADD_OTHER, ScenarioType.OTHER_COMMITMENT):
            emi_amount = float(params.get("monthly_amount", params.get("monthly_emi", params.get("amount", 0.0))))
            default_name = "New EMI" if stype == ScenarioType.NEW_EMI else "New Commitment"
            name = params.get("name", default_name)
            cloned_snapshot.monthly_commitments += emi_amount
            cloned_snapshot.active_emis_count += 1
            cloned_snapshot.emis.append({"name": name, "monthly_emi": emi_amount})
            applied_changes = {
                "added_commitment": emi_amount,
                "added_emi" if stype == ScenarioType.NEW_EMI else "added_obligation": name,
            }

        elif stype == ScenarioType.CLOSE_EMI:
            target = params.get("emi_id") or params.get("name")
            matched_emis = [e for e in cloned_snapshot.emis if self._matches_item(e, str(target))]
            emi_amount = float(params.get("monthly_emi", params.get("amount", 0.0)))
            if matched_emis and "monthly_emi" in matched_emis[0]:
                emi_amount = float(matched_emis[0]["monthly_emi"])

            cloned_snapshot.monthly_commitments = max(0.0, cloned_snapshot.monthly_commitments - emi_amount)
            if cloned_snapshot.active_emis_count > 0:
                cloned_snapshot.active_emis_count -= 1
            cloned_snapshot.emis = [
                e for e in cloned_snapshot.emis if not self._matches_item(e, str(target))
            ]
            applied_changes = {"reduced_commitment": emi_amount, "closed_emi": target}

        elif stype == ScenarioType.SALARY_INCREASE:
            increase = float(params.get("amount", 0.0))
            if "percentage" in params and float(params["percentage"]) > 0:
                increase = cloned_snapshot.monthly_income * (float(params["percentage"]) / 100.0)
            cloned_snapshot.monthly_income += increase
            applied_changes = {"income_increase": increase, "new_income": cloned_snapshot.monthly_income}

        elif stype == ScenarioType.SALARY_REDUCTION:
            reduction = float(params.get("amount", 0.0))
            if "percentage" in params and float(params["percentage"]) > 0:
                reduction = cloned_snapshot.monthly_income * (float(params["percentage"]) / 100.0)
            cloned_snapshot.monthly_income = max(0.0, cloned_snapshot.monthly_income - reduction)
            applied_changes = {"income_reduction": reduction, "new_income": cloned_snapshot.monthly_income}

        elif stype == ScenarioType.CLOSE_BNPL:
            target = params.get("bnpl_id") or params.get("name")
            matched_bnpl = [b for b in cloned_snapshot.bnpl_items if self._matches_item(b, str(target))]
            amount = float(params.get("monthly_installment", params.get("amount", 0.0)))
            if matched_bnpl and "monthly_installment" in matched_bnpl[0]:
                amount = float(matched_bnpl[0]["monthly_installment"])

            cloned_snapshot.monthly_commitments = max(0.0, cloned_snapshot.monthly_commitments - amount)
            if cloned_snapshot.active_bnpl_count > 0:
                cloned_snapshot.active_bnpl_count -= 1
            cloned_snapshot.bnpl_items = [
                b for b in cloned_snapshot.bnpl_items if not self._matches_item(b, str(target))
            ]
            applied_changes = {"reduced_commitment": amount, "closed_bnpl": target}

        elif stype == ScenarioType.ADD_BNPL:
            amount = float(params.get("monthly_installment", params.get("amount", 0.0)))
            name = params.get("name", "New BNPL")
            cloned_snapshot.monthly_commitments += amount
            cloned_snapshot.active_bnpl_count += 1
            cloned_snapshot.bnpl_items.append({"name": name, "monthly_installment": amount})
            applied_changes = {"added_commitment": amount, "added_bnpl": name}

        duration = int(params.get("duration", params.get("installments", params.get("duration_months", 0))))
        if duration > 0 and "added_commitment" in applied_changes:
            added_amt = float(applied_changes["added_commitment"])
            applied_changes["duration_months"] = duration
            applied_changes["total_commitment"] = round(added_amt * duration, 2)

        self._recalculate_snapshot_metrics(cloned_snapshot, baseline_snapshot=snap)

        return ScenarioResult(
            original_twin=twin,
            modified_twin=modified_twin,
            scenario=scenario,
            applied_changes=applied_changes,
            success=True,
            message=f"Successfully applied scenario '{stype.value}'",
        )

    def build_scenario(self, twin: DigitalTwin, scenario: Scenario) -> ScenarioResult:
        """Convenience alias for apply_scenario."""
        return self.apply_scenario(twin, scenario)
