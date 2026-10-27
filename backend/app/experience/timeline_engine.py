from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from app.digital_twin.comparison_engine import FinancialComparison
from app.digital_twin.twin_engine import FinancialSnapshot
from app.dna.dna_engine import FinancialDNA


class TimelineSection(str, Enum):
    HISTORICAL = "historical"
    CURRENT = "current"
    FUTURE = "future"
    ALTERNATIVE_FUTURE = "alternative_future"


class TimelineCategory(str, Enum):
    MILESTONE = "milestone"
    COMMITMENT = "commitment"
    ANOMALY = "anomaly"
    EXPOSURE_CHANGE = "exposure_change"
    SIMULATION_BRANCH = "simulation_branch"


@dataclass
class TimelineItem:
    """
    Data structure representing a single financial timeline event or projection milestone.
    """

    item_id: str
    title: str
    timestamp: str
    section: TimelineSection
    category: TimelineCategory
    description: str
    impact: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FinancialJourneyTimeline:
    """
    Complete Financial Journey Timeline combining historical, current, future, and alternative branch events.
    """

    user_id: str
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    historical_events: list[TimelineItem] = field(default_factory=list)
    current_position: list[TimelineItem] = field(default_factory=list)
    future_projections: list[TimelineItem] = field(default_factory=list)
    alternative_futures: list[TimelineItem] = field(default_factory=list)
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class TimelineEngine:
    """
    Timeline Engine.

    Constructs an interactive Financial Journey Timeline representing historical milestones,
    current anchor position, projected future commitments, and alternative simulated branches.
    Does NOT calculate machine learning predictions or raw business rules directly.
    """

    def build_timeline(
        self,
        snapshot: FinancialSnapshot,
        comparison: FinancialComparison | None = None,
        dna: FinancialDNA | None = None,
    ) -> FinancialJourneyTimeline:
        """
        Constructs a complete FinancialJourneyTimeline for the given snapshot.
        """
        user_id = snapshot.user_id
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        historical_events: list[TimelineItem] = []
        current_position: list[TimelineItem] = []
        future_projections: list[TimelineItem] = []
        alternative_futures: list[TimelineItem] = []

        # 1. Historical Events (Sample reconstructable historical milestones)
        h1_time = (now - timedelta(days=90)).isoformat()
        historical_events.append(
            TimelineItem(
                item_id=f"hist_1_{uuid.uuid4().hex[:6]}",
                title="Account Setup & Initial Profile Detection",
                timestamp=h1_time,
                section=TimelineSection.HISTORICAL,
                category=TimelineCategory.MILESTONE,
                description="Financial profile initialized in FinSight platform.",
                impact="Established baseline exposure score and financial health tracking.",
                metadata={"income": snapshot.monthly_income},
            )
        )

        if snapshot.active_emis_count > 0:
            h2_time = (now - timedelta(days=45)).isoformat()
            historical_events.append(
                TimelineItem(
                    item_id=f"hist_2_{uuid.uuid4().hex[:6]}",
                    title="Active EMI Obligation Started",
                    timestamp=h2_time,
                    section=TimelineSection.HISTORICAL,
                    category=TimelineCategory.COMMITMENT,
                    description=f"Detected active EMI loan commitment.",
                    impact="Increased monthly commitment burden.",
                    metadata={"emis_count": snapshot.active_emis_count},
                )
            )

        # 2. Current Position Anchor
        current_position.append(
            TimelineItem(
                item_id=f"curr_1_{uuid.uuid4().hex[:6]}",
                title="Current Financial Status Anchor",
                timestamp=now_iso,
                section=TimelineSection.CURRENT,
                category=TimelineCategory.MILESTONE,
                description=f"Health Status: {snapshot.financial_health_status} (Score: {snapshot.financial_health_score:.1f}/100)",
                impact=f"Monthly Exposure: {snapshot.exposure_score:.1f}%, Savings: {snapshot.monthly_savings:.2f}",
                metadata={
                    "commitments": snapshot.monthly_commitments,
                    "subscriptions": snapshot.active_subscriptions_count,
                    "emis": snapshot.active_emis_count,
                    "bnpl": snapshot.active_bnpl_count,
                },
            )
        )

        if dna:
            current_position.append(
                TimelineItem(
                    item_id=f"curr_2_{uuid.uuid4().hex[:6]}",
                    title=f"Financial Archetype: {dna.primary_archetype.value.replace('_', ' ').title()}",
                    timestamp=now_iso,
                    section=TimelineSection.CURRENT,
                    category=TimelineCategory.MILESTONE,
                    description=dna.explainability,
                    impact="Behavioral fingerprint active.",
                    metadata={"archetype": dna.primary_archetype.value},
                )
            )

        # 3. Future Projections (30 and 60 days ahead)
        f1_time = (now + timedelta(days=30)).isoformat()
        future_projections.append(
            TimelineItem(
                item_id=f"fut_1_{uuid.uuid4().hex[:6]}",
                title="Upcoming Subscription Renewals & AutoPay",
                timestamp=f1_time,
                section=TimelineSection.FUTURE,
                category=TimelineCategory.COMMITMENT,
                description=f"Projected AutoPay execution for {snapshot.active_subscriptions_count} active subscriptions.",
                impact=f"Expected recurring deduction of commitments.",
                metadata={"subscriptions_count": snapshot.active_subscriptions_count},
            )
        )

        f2_time = (now + timedelta(days=60)).isoformat()
        future_projections.append(
            TimelineItem(
                item_id=f"fut_2_{uuid.uuid4().hex[:6]}",
                title="60-Day Financial Exposure Forecast",
                timestamp=f2_time,
                section=TimelineSection.FUTURE,
                category=TimelineCategory.EXPOSURE_CHANGE,
                description="Projected exposure trajectory under current commitment structure.",
                impact=f"Exposure expected to remain around {snapshot.exposure_score:.1f}%.",
                metadata={"exposure_score": snapshot.exposure_score},
            )
        )

        # 4. Alternative Future Branch (If Digital Twin comparison is provided)
        if comparison:
            alt_time = (now + timedelta(days=30)).isoformat()
            exp_metric = comparison.metrics.get("exposure")
            commit_metric = comparison.metrics.get("monthly_commitments")
            exp_diff = exp_metric.difference if exp_metric else 0.0
            commit_diff = commit_metric.difference if commit_metric else 0.0

            alternative_futures.append(
                TimelineItem(
                    item_id=f"alt_1_{uuid.uuid4().hex[:6]}",
                    title=f"Simulated Branch: {comparison.scenario_type or 'Scenario Simulation'}",
                    timestamp=alt_time,
                    section=TimelineSection.ALTERNATIVE_FUTURE,
                    category=TimelineCategory.SIMULATION_BRANCH,
                    description=comparison.summary,
                    impact=f"Exposure Delta: {exp_diff:+.2f}%, Commitments Delta: {commit_diff:+.2f}",
                    metadata={
                        "comparison_id": comparison.comparison_id,
                        "scenario_type": comparison.scenario_type,
                    },
                )
            )

        summary = (
            f"Financial Journey Timeline generated for {user_id}: {len(historical_events)} historical, "
            f"{len(current_position)} current, {len(future_projections)} future, and {len(alternative_futures)} alternative events."
        )

        return FinancialJourneyTimeline(
            user_id=user_id,
            generated_at=now_iso,
            historical_events=historical_events,
            current_position=current_position,
            future_projections=future_projections,
            alternative_futures=alternative_futures,
            summary=summary,
            metadata={"user_id": user_id},
        )

    def generate_timeline(
        self,
        snapshot: FinancialSnapshot,
        comparison: FinancialComparison | None = None,
        dna: FinancialDNA | None = None,
    ) -> FinancialJourneyTimeline:
        """Convenience alias for build_timeline."""
        return self.build_timeline(snapshot, comparison, dna)
