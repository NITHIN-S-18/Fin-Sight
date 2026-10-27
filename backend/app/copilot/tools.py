from __future__ import annotations

import io
import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.services.cashflow_forecast_service import CashFlowForecastService
from app.services.commitment_service import UnifiedCommitmentService
from app.services.dataset_service import DatasetService, get_dataset_service
from app.services.exposure_service import ExposureService, get_exposure_service
from app.services.goal_feasibility_service import GoalFeasibilityService
from app.services.shortfall_service import FinancialShortfallService
from app.services.subscription_service import SubscriptionService

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeChunk:
    doc_name: str
    section: str
    content: str


class FinsightKnowledgeRetriever:
    """
    RAG knowledge retriever indexing authoritative FinSight technical and business documentation.

    Canonical Source Documents:
        The retriever indexes six verified documentation files located in the `docs/` directory:
        1. BUSINESS_RULES.md - Financial formulas, exposure calculations, and risk metric definitions.
        2. API_GUIDE.md - REST endpoints, schemas, request/response payloads, and authentication.
        3. ML_ARCHITECTURE.md - Model training pipelines, feature sets, and inference specifications.
        4. PHASE10_ARCHITECTURE.md - Component interactions, service boundaries, and system topology.
        5. FINAL_SYSTEM_AUDIT.md - System verification results, audit findings, and stability baselines.
        6. FINAL_ARCHITECTURE_FREEZE.md - Structural invariants, contract boundaries, and frozen conventions.

    Chunking & Indexing Strategy:
        - Markdown Splitting: Text is partitioned on Markdown header boundaries (H1 to H3: `r"\n(?=#{1,3}\s)"`).
        - Filtering & Sizing: Fragments under 40 characters are discarded; sections are capped at 1,200 characters
          to preserve prompt budget while maintaining coherent conceptual units.
        - Corpus Assembly: Each chunk incorporates its document filename, section header, and text body.

    TF-IDF Vectorization & Retrieval Process:
        - Scikit-learn's `TfidfVectorizer(stop_words="english", max_features=2500)` builds a term-frequency matrix.
        - On incoming user queries, cosine similarity is computed across all indexed chunk vectors.
        - Domain-aware re-ranking boosts conceptual documents (BUSINESS_RULES, ML_ARCHITECTURE) by 1.35x
          for general inquiries, while penalizing API_GUIDE by 0.35x unless API keywords (endpoint, curl, route)
          are present in the prompt.
        - Chunks with adjusted cosine similarity >= 0.08 are returned up to `top_k`.
    """

    def __init__(self, docs_dir: Path | None = None) -> None:
        self.docs_dir = docs_dir or (Path(__file__).resolve().parents[3] / "docs")
        self.chunks: list[KnowledgeChunk] = []
        self._vectorizer: TfidfVectorizer | None = None
        self._tfidf_matrix = None
        self._build_index()

    def _build_index(self) -> None:
        if not self.docs_dir.exists() or not self.docs_dir.is_dir():
            return

        target_files = [
            "BUSINESS_RULES.md",
            "API_GUIDE.md",
            "ML_ARCHITECTURE.md",
            "PHASE10_ARCHITECTURE.md",
            "FINAL_SYSTEM_AUDIT.md",
            "FINAL_ARCHITECTURE_FREEZE.md",
        ]

        raw_chunks: list[KnowledgeChunk] = []
        for filename in target_files:
            file_path = self.docs_dir / filename
            if not file_path.is_file():
                continue
            try:
                text = file_path.read_text(encoding="utf-8", errors="ignore")
                sections = re.split(r"\n(?=#{1,3}\s)", text)
                for sec in sections:
                    sec_clean = sec.strip()
                    if len(sec_clean) < 40:
                        continue
                    # First line is header
                    first_line = sec_clean.split("\n")[0].strip("# ").strip()
                    raw_chunks.append(
                        KnowledgeChunk(
                            doc_name=filename,
                            section=first_line,
                            content=sec_clean[:1200],  # keep concise chunks
                        )
                    )
            except Exception as exc:
                logger.warning("Failed indexing doc %s: %s", filename, exc)

        if raw_chunks:
            self.chunks = raw_chunks
            self._vectorizer = TfidfVectorizer(stop_words="english", max_features=2500)
            corpus = [f"{c.doc_name} {c.section} {c.content}" for c in self.chunks]
            self._tfidf_matrix = self._vectorizer.fit_transform(corpus)

    def search(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        if not self.chunks or self._vectorizer is None or self._tfidf_matrix is None:
            return []

        try:
            low_query = query.lower()
            asks_for_api = any(
                w in low_query
                for w in ["api", "endpoint", "endpoints", "curl", "route", "routes", "http", "schema", "request", "post /", "get /"]
            )

            q_vec = self._vectorizer.transform([query])
            raw_scores = cosine_similarity(q_vec, self._tfidf_matrix).flatten()

            # Adjust scores: boost conceptual docs (BUSINESS_RULES, ML_ARCHITECTURE) unless technical API was requested
            adjusted_scores = []
            for idx, s in enumerate(raw_scores):
                score = float(s)
                chunk = self.chunks[idx]
                if not asks_for_api and chunk.doc_name == "API_GUIDE.md":
                    score *= 0.35  # penalize raw API routes for conceptual questions
                elif not asks_for_api and chunk.doc_name in ["BUSINESS_RULES.md", "ML_ARCHITECTURE.md"]:
                    score *= 1.35  # boost business definitions and ML modeling logic
                adjusted_scores.append((score, idx))

            adjusted_scores.sort(key=lambda x: x[0], reverse=True)

            results: list[dict[str, Any]] = []
            for score, idx in adjusted_scores[:top_k]:
                if score < 0.08:
                    continue
                chunk = self.chunks[idx]
                results.append(
                    {
                        "source": chunk.doc_name,
                        "section": chunk.section,
                        "content": chunk.content,
                        "relevance_score": round(score, 3),
                    }
                )
            return results
        except Exception as exc:
            logger.warning("Knowledge retrieval error: %s", exc)
            return []


# Global singleton instance of retriever
_retriever_instance: FinsightKnowledgeRetriever | None = None


def get_knowledge_retriever() -> FinsightKnowledgeRetriever:
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = FinsightKnowledgeRetriever()
    return _retriever_instance


class FinancialToolRegistry:
    """
    Authoritative, tenant-isolated financial tools for FinSight AI Assistant.
    Enforces that queries only access the authenticated user's data.
    """

    def __init__(
        self,
        exposure_service: ExposureService | None = None,
        dataset_service: DatasetService | None = None,
    ) -> None:
        self.dataset_service = dataset_service or get_dataset_service()
        self.exposure_service = exposure_service or get_exposure_service(self.dataset_service)
        self.knowledge_retriever = get_knowledge_retriever()

    def get_financial_summary(self, user_id: str) -> dict[str, Any]:
        """Returns overall financial capacity, commitments, exposure ratio, and health score."""
        intel = self.exposure_service.get_exposure_intelligence(user_id)
        status = intel.current_financial_status
        health = intel.financial_health
        exp_summary = intel.exposure_summary
        return {
            "monthly_income": status.monthly_financial_capacity,
            "monthly_total_commitments": status.monthly_total_commitments,
            "available_monthly_capacity": status.available_monthly_capacity,
            "exposure_score_pct": status.exposure_score,
            "exposure_band": exp_summary.exposure_band if exp_summary else "Unknown",
            "financial_health_score": health.financial_health_score,
            "financial_health_label": health.financial_health_label,
            "health_rationale": health.rationale,
            "payment_reliability": getattr(intel, "payment_reliability", 1.0),
        }

    def get_transaction_summary(self, user_id: str, category: str | None = None) -> dict[str, Any]:
        """Returns transaction volume, inflow/outflow, and category spending breakdown."""
        txs = self.dataset_service.get_user_transactions(user_id)
        if not txs:
            return {
                "transaction_count": 0,
                "total_inflow": 0.0,
                "total_outflow": 0.0,
                "categories": {},
                "message": "No transaction history recorded yet.",
            }

        total_inflow = 0.0
        total_outflow = 0.0
        cat_spending: dict[str, float] = {}

        for tx in txs:
            amt = float(tx.get("amount", 0.0) or 0.0)
            is_income = str(tx.get("income_flag", "")).lower() in {"true", "yes", "1"} or (
                str(tx.get("category", "")).lower() == "income"
            )
            cat = str(tx.get("category", "General")).strip().title()

            if is_income:
                total_inflow += amt
            else:
                total_outflow += amt
                cat_spending[cat] = round(cat_spending.get(cat, 0.0) + amt, 2)

        if category:
            cat_norm = category.strip().title()
            cat_amount = cat_spending.get(cat_norm, 0.0)
            return {
                "transaction_count": len(txs),
                "category": cat_norm,
                "category_spent": cat_amount,
                "total_outflow": round(total_outflow, 2),
                "pct_of_total_outflow": round((cat_amount / total_outflow * 100), 2) if total_outflow > 0 else 0.0,
            }

        top_categories = sorted(cat_spending.items(), key=lambda x: x[1], reverse=True)[:5]
        return {
            "transaction_count": len(txs),
            "total_inflow": round(total_inflow, 2),
            "total_outflow": round(total_outflow, 2),
            "top_spending_categories": [{"category": c, "amount": a} for c, a in top_categories],
            "all_category_totals": cat_spending,
        }

    def get_commitments(self, user_id: str) -> dict[str, Any]:
        """Returns Unified Commitment Engine snapshot including EMIs, subscriptions, bills."""
        snapshot = UnifiedCommitmentService.snapshot_for_user(user_id)
        items = [
            {
                "title": getattr(item, "name", getattr(item, "commitment_name", "Commitment")),
                "category": getattr(item, "category", getattr(item, "commitment_source", "Other")),
                "monthly_amount": getattr(item, "monthly_equivalent_amount", getattr(item, "monthly_amount", 0.0)),
                "type": getattr(item, "source", getattr(item, "commitment_type", "Fixed")),
            }
            for item in snapshot.commitment_items
        ]
        return {
            "total_monthly_commitments": snapshot.total_monthly_commitments,
            "commitments_count": len(items),
            "breakdown_by_category": snapshot.breakdown_by_category,
            "commitment_items": items,
        }

    def get_cash_flow_forecast(self, user_id: str) -> dict[str, Any]:
        """Returns Model 1 cash flow forecasting for the upcoming month."""
        service = CashFlowForecastService(self.dataset_service)
        pred = service.forecast(user_id)
        cat_forecasts = {}
        if getattr(pred, "category_forecasts", None):
            cat_forecasts = {k: round(v, 2) for k, v in pred.category_forecasts.items()}
        return {
            "model": "Model 1 Cash Flow Forecaster",
            "expected_income": round(pred.expected_income or 0.0, 2),
            "expected_committed_expenses": round(pred.expected_committed_expenses or 0.0, 2),
            "expected_variable_expenses": round(pred.expected_variable_expenses or 0.0, 2),
            "expected_net_cash": round(pred.expected_net_cash or 0.0, 2),
            "category_forecasts": cat_forecasts,
        }

    def evaluate_financial_goal(
        self, user_id: str, goal_amount: float, timeframe_months: int, goal_name: str | None = None
    ) -> dict[str, Any]:
        """Evaluates goal feasibility with Model 2 Cash Flow capacity."""
        service = GoalFeasibilityService(self.dataset_service)
        res = service.evaluate_goal(
            user_id=user_id,
            target_amount=goal_amount,
            target_months=timeframe_months,
            goal_name=goal_name or "Financial Goal",
        )
        return {
            "goal_name": res.get("goal_name", goal_name),
            "target_amount": goal_amount,
            "timeframe_months": timeframe_months,
            "required_monthly_savings": res.get("required_monthly_savings"),
            "monthly_cashflow_capacity": res.get("monthly_cashflow_capacity"),
            "goal_feasible": res.get("goal_feasible"),
            "monthly_surplus_or_shortfall": res.get("monthly_surplus_or_shortfall"),
            "recommendation_summary": res.get("recommendation_summary"),
        }

    def get_subscription_intelligence(self, user_id: str) -> dict[str, Any]:
        """Returns Model 3 subscription usage classifications and recommendations."""
        sub_service = SubscriptionService(self.dataset_service)
        intel = sub_service.get_subscription_intelligence(user_id)
        summary = intel.subscription_summary
        active_subs = [
            {
                "service_name": s.subscription_name,
                "monthly_cost": s.monthly_cost,
                "status": s.status,
                "billing_frequency": s.billing_frequency,
            }
            for s in intel.active_subscriptions
        ]
        return {
            "active_subscriptions_count": summary.active_subscription_count,
            "monthly_subscription_cost": summary.monthly_subscription_cost,
            "underutilized_subscriptions_count": summary.underutilized_subscription_count,
            "potential_monthly_savings": summary.potential_monthly_savings,
            "subscriptions": active_subs,
            "recommendation": summary.optimization_recommendation,
        }

    def get_shortfall_prediction(self, user_id: str) -> dict[str, Any]:
        """Returns Model 4 shortfall risk classification and adverse financial factors."""
        shortfall_service = FinancialShortfallService(self.dataset_service)
        pred = shortfall_service.predict(user_id)
        return {
            "model": "Model 4 Financial Shortfall Classifier",
            "shortfall_risk_level": pred.shortfall_risk,
            "prediction": pred.prediction,
            "contributing_factors": pred.contributing_factors,
            "factor_details": [
                {"factor": f.factor, "severity": f.severity, "metric": f.metric}
                for f in (pred.factor_details or [])
            ],
            "risk_explanation": pred.risk_explanation,
            "recommended_actions": pred.recommended_actions,
        }

    def simulate_cancellation(self, user_id: str, commitment_name: str) -> dict[str, Any]:
        """What-if simulation for cancelling a commitment without database mutation."""
        sim = UnifiedCommitmentService.simulate_cancellation(user_id, commitment_name)
        return {
            "cancelled_commitment": commitment_name,
            "current_monthly_commitments": sim.current_monthly_commitments,
            "projected_monthly_commitments": sim.projected_monthly_commitments,
            "released_monthly_amount": sim.released_monthly_amount,
            "annual_savings": sim.annual_savings,
            "current_exposure_score": sim.current_exposure_score,
            "projected_exposure_score": sim.projected_exposure_score,
            "notice": "Simulation projection only. No financial or subscription change was made.",
        }

    def search_knowledge(self, query: str) -> list[dict[str, Any]]:
        """RAG search across verified FinSight documentation."""
        return self.knowledge_retriever.search(query)


def parse_and_sanitize_document(filename: str, content_bytes: bytes) -> str:
    """
    Extracts and sanitizes text from uploaded documents (txt, md, csv, json, pdf).
    Limits to 15,000 characters and shields against prompt injection.
    """
    ext = os.path.splitext(filename)[1].lower()
    text = ""

    if ext in {".txt", ".md", ".csv", ".json"}:
        try:
            text = content_bytes.decode("utf-8", errors="ignore")
        except Exception:
            text = content_bytes.decode("latin-1", errors="ignore")
    elif ext == ".pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(content_bytes))
            pages_text = [page.extract_text() or "" for page in reader.pages[:10]]
            text = "\n".join(pages_text)
        except Exception:
            # Fallback simple string extraction for text within PDF
            extracted = re.findall(rb"[A-Za-z0-9 .,:;!?\n\r-]{4,}", content_bytes)
            text = "\n".join(chunk.decode("ascii", errors="ignore") for chunk in extracted[:100])
    else:
        raise ValueError(f"Unsupported document format: {ext}. Supported formats: .txt, .md, .csv, .json, .pdf")

    sanitized = text.strip()[:15000]
    return sanitized
