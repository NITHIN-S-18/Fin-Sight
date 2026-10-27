from __future__ import annotations

import io
import logging
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.core.exceptions import (
    ExposureDataUnavailableError,
    SubscriptionNotFoundError,
    UserNotFoundError,
)
from app.database.connection import SessionLocal
from app.database.models.user import User
from app.services.cashflow_forecast_service import (
    CashFlowForecastService,
    get_cashflow_forecast_service,
)
from app.services.commitment_service import UnifiedCommitmentService
from app.services.dataset_service import DatasetService, get_dataset_service
from app.services.exposure_service import ExposureService, get_exposure_service
from app.services.goal_feasibility_service import (
    GoalFeasibilityService,
    get_goal_feasibility_service,
)
from app.services.history_service import HistoryService
from app.services.shortfall_service import (
    FinancialShortfallService,
    get_shortfall_service,
)
from app.services.subscription_service import SubscriptionService

logger = logging.getLogger(__name__)


# ── ReportLab Color Palette (Fintech Slate / Navy / Indigo) ──────────────────
NAVY_PRIMARY = colors.HexColor("#0F172A")
NAVY_SECONDARY = colors.HexColor("#1E293B")
SLATE_DARK = colors.HexColor("#334155")
SLATE_BODY = colors.HexColor("#475569")
SLATE_MUTED = colors.HexColor("#64748B")
SLATE_LIGHT = colors.HexColor("#F1F5F9")
BG_CARD = colors.HexColor("#F8FAFC")
ACCENT_INDIGO = colors.HexColor("#4F46E5")
ACCENT_INDIGO_LIGHT = colors.HexColor("#EEF2FF")
EMERALD_GREEN = colors.HexColor("#059669")
EMERALD_LIGHT = colors.HexColor("#ECFDF5")
AMBER_WARN = colors.HexColor("#D97706")
AMBER_LIGHT = colors.HexColor("#FFFBEB")
ROSE_ALERT = colors.HexColor("#E11D48")
ROSE_LIGHT = colors.HexColor("#FFF1F2")
BORDER_LIGHT = colors.HexColor("#E2E8F0")
BORDER_DARK = colors.HexColor("#CBD5E1")


def _get_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "doc_title": ParagraphStyle(
            "DocTitle",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=18,
            textColor=colors.white,
        ),
        "doc_subtitle": ParagraphStyle(
            "DocSubtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#94A3B8"),
        ),
        "header_meta_right": ParagraphStyle(
            "HeaderMetaRight",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor("#CBD5E1"),
            alignment=2,
        ),
        "header_meta_right_bold": ParagraphStyle(
            "HeaderMetaRightBold",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10.5,
            textColor=colors.white,
            alignment=2,
        ),
        "section_title": ParagraphStyle(
            "SectionTitle",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=13.5,
            textColor=NAVY_PRIMARY,
        ),
        "section_subtitle": ParagraphStyle(
            "SectionSubtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=10,
            textColor=SLATE_MUTED,
        ),
        "body": ParagraphStyle(
            "ReportBody",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=SLATE_BODY,
        ),
        "body_bold": ParagraphStyle(
            "ReportBodyBold",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=11,
            textColor=NAVY_PRIMARY,
        ),
        "card_title": ParagraphStyle(
            "CardTitle",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7,
            leading=8.5,
            textColor=SLATE_MUTED,
            alignment=1,
        ),
        "card_value": ParagraphStyle(
            "CardValue",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=13,
            textColor=NAVY_PRIMARY,
            alignment=1,
        ),
        "card_sub": ParagraphStyle(
            "CardSub",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=6.5,
            leading=8,
            textColor=SLATE_MUTED,
            alignment=1,
        ),
        "table_header": ParagraphStyle(
            "TableHeader",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9.5,
            textColor=NAVY_PRIMARY,
        ),
        "table_header_right": ParagraphStyle(
            "TableHeaderRight",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9.5,
            textColor=NAVY_PRIMARY,
            alignment=2,
        ),
        "table_cell": ParagraphStyle(
            "TableCell",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=9.5,
            textColor=SLATE_BODY,
        ),
        "table_cell_bold": ParagraphStyle(
            "TableCellBold",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9.5,
            textColor=NAVY_PRIMARY,
        ),
        "table_cell_right": ParagraphStyle(
            "TableCellRight",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=9.5,
            textColor=SLATE_BODY,
            alignment=2,
        ),
        "table_cell_right_bold": ParagraphStyle(
            "TableCellRightBold",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9.5,
            textColor=NAVY_PRIMARY,
            alignment=2,
        ),
        "notice_box_text": ParagraphStyle(
            "NoticeBoxText",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=10.5,
            textColor=NAVY_SECONDARY,
        ),
        "bullet_item": ParagraphStyle(
            "BulletItem",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=10.5,
            textColor=SLATE_BODY,
            leftIndent=12,
        ),
    }


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas for dynamic running header and 'Page X of Y' footer."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[dict[str, Any]] = []

    def showPage(self) -> None:
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_decorations(num_pages)
            super().showPage()
        super().save()

    def _draw_decorations(self, num_pages: int) -> None:
        self.saveState()
        # Running Header on page 2 and later
        if self._pageNumber > 1:
            self.setFont("Helvetica-Bold", 8)
            self.setFillColor(NAVY_PRIMARY)
            self.drawString(36, 816, "FINSIGHT")
            self.setFont("Helvetica", 8)
            self.setFillColor(SLATE_MUTED)
            self.drawString(84, 816, "— Financial Exposure Intelligence Report")
            self.drawRightString(559, 816, "CONFIDENTIAL")
            self.setStrokeColor(BORDER_DARK)
            self.setLineWidth(0.5)
            self.line(36, 808, 559, 808)

        # Running Footer on all pages
        self.setStrokeColor(BORDER_DARK)
        self.setLineWidth(0.5)
        self.line(36, 30, 559, 30)
        self.setFont("Helvetica", 7)
        self.setFillColor(SLATE_MUTED)
        self.drawString(36, 20, "FinSight Financial Exposure Intelligence System | Strictly Confidential")
        self.drawRightString(559, 20, f"Page {self._pageNumber} of {num_pages}")
        self.restoreState()


class FinancialReportPdfService:
    """Enterprise-grade, authoritative PDF Financial Analysis Report Generator."""

    PAGE_WIDTH = 523  # printable width (595 - 2*36)

    def __init__(
        self,
        dataset_service: DatasetService | None = None,
        exposure_service: ExposureService | None = None,
        forecast_service: CashFlowForecastService | None = None,
        goal_service: GoalFeasibilityService | None = None,
        shortfall_service: FinancialShortfallService | None = None,
    ) -> None:
        self._dataset_service = dataset_service or get_dataset_service()
        self._exposure_service = exposure_service or get_exposure_service()
        self._forecast_service = forecast_service or get_cashflow_forecast_service()
        self._goal_service = goal_service or get_goal_feasibility_service()
        self._shortfall_service = shortfall_service or get_shortfall_service()
        self._subscription_service = SubscriptionService(self._dataset_service)
        self._history_service = HistoryService(self._dataset_service)

    @staticmethod
    def _currency(value: float | None) -> str:
        if value is None:
            return "₹0.00"
        return f"₹{value:,.2f}"

    @staticmethod
    def _percent(value: float | None) -> str:
        if value is None:
            return "0.0%"
        return f"{value:.1f}%"

    def generate_report(self, user_id: str) -> bytes:
        styles = _get_styles()

        # ── 1. Gather User & Account Profile ───────────────────────────
        with SessionLocal() as session:
            user_row = session.query(User).filter(User.user_id == user_id).one_or_none()
            auth_user = user_row.auth_user if user_row else None
            display_name = auth_user.display_name if auth_user and auth_user.display_name else "FinSight Member"
            email = auth_user.email if auth_user else "N/A"
            city = user_row.city if user_row and user_row.city else "Not Specified"
            persona = user_row.persona if user_row and user_row.persona else "General Member"
            created_at_dt = auth_user.created_at if auth_user else (user_row.created_at if user_row else None)

        # ── 2. Gather Transactions & Dataset Overview ───────────────────
        transactions = self._dataset_service.get_user_transactions(user_id)
        has_transactions = bool(transactions)
        total_txns = len(transactions)

        credit_txns = [
            t for t in transactions
            if str(t.get("income_flag", "")).lower() in ("true", "yes", "1")
            or str(t.get("transaction_class", "")).lower() == "income"
        ]
        debit_txns = [t for t in transactions if t not in credit_txns]

        total_credits = sum(float(t.get("amount") or 0.0) for t in credit_txns)
        total_debits = sum(float(t.get("amount") or 0.0) for t in debit_txns)
        net_cash_flow = total_credits - total_debits

        valid_dates = [t.get("transaction_date") for t in transactions if t.get("transaction_date")]
        if valid_dates:
            min_date = min(valid_dates)
            max_date = max(valid_dates)
            date_range_str = f"{min_date} to {max_date}"
        else:
            date_range_str = "No transaction records"

        # Category spending aggregation
        category_spending: dict[str, float] = defaultdict(float)
        category_counts: dict[str, int] = defaultdict(int)
        for t in debit_txns:
            cat = str(t.get("category") or "Uncategorized").title()
            category_spending[cat] += float(t.get("amount") or 0.0)
            category_counts[cat] += 1

        # ── 3. Gather Exposure & Financial Health Intelligence ──────────
        try:
            exposure_intel = self._exposure_service.get_exposure_intelligence(user_id)
            cfs = exposure_intel.current_financial_status
            es = exposure_intel.exposure_summary
            fh = exposure_intel.financial_health
            recommendations = exposure_intel.recommendations

            monthly_capacity = cfs.monthly_financial_capacity
            monthly_commitments = cfs.monthly_total_commitments
            available_capacity = cfs.available_monthly_capacity
            exposure_score = cfs.exposure_score
            exposure_band = es.exposure_band
            exposure_explanation = es.explanation
            health_score = fh.financial_health_score
            health_label = fh.financial_health_label
            health_rationale = fh.rationale
            income_source = getattr(cfs, "income_source", "Observed")
            income_mode = getattr(cfs, "income_mode", "auto")
        except (ExposureDataUnavailableError, UserNotFoundError, Exception) as exc:
            logger.info("Exposure intel unavailable for user %s: %s", user_id, exc)
            monthly_capacity = 0.0
            monthly_commitments = 0.0
            available_capacity = 0.0
            exposure_score = 0.0
            exposure_band = "Not Evaluated"
            exposure_explanation = "Upload bank transaction statement to evaluate financial exposure."
            health_score = 0
            health_label = "Unavailable"
            health_rationale = ["Upload bank transactions to generate financial health score."]
            income_source = "None"
            income_mode = "auto"
            recommendations = []

        # ── 4. Gather Unified Commitments ──────────────────────────────
        try:
            commitments_snapshot = UnifiedCommitmentService.snapshot_for_user(user_id)
            commitment_items = getattr(commitments_snapshot, "commitment_items", getattr(commitments_snapshot, "items", []))
            total_monthly_commitments = getattr(commitments_snapshot, "total_monthly_commitments", getattr(commitments_snapshot, "total_monthly_commitment", 0.0))
            commitments_by_cat = commitments_snapshot.breakdown_by_category
        except Exception as exc:
            logger.warning("Commitments snapshot error for %s: %s", user_id, exc)
            commitment_items = []
            total_monthly_commitments = 0.0
            commitments_by_cat = {}

        # ── 5. Gather Cash Flow Forecast (Model 1) ─────────────────────
        try:
            forecast_intel = self._forecast_service.forecast(user_id)
        except Exception:
            forecast_intel = None

        # ── 6. Gather Subscription Intelligence (Model 3) ──────────────
        try:
            sub_intel = self._subscription_service.get_subscription_intelligence(user_id)
        except (SubscriptionNotFoundError, Exception):
            sub_intel = None

        # ── 7. Gather Goal Feasibility (Model 2) ────────────────────────
        try:
            goals_list = self._goal_service.list_for_user(user_id)
        except Exception:
            goals_list = []

        # ── 8. Gather Shortfall Prediction (Model 4) ────────────────────
        try:
            shortfall_intel = self._shortfall_service.predict(user_id)
        except Exception:
            shortfall_intel = None

        # ── 9. Gather Historical Cash Flow Trends ───────────────────────
        try:
            history_intel = self._history_service.get_history(user_id)
            history_points = history_intel.points
        except Exception:
            history_points = []

        # ── BUILD PDF STORY ─────────────────────────────────────────────
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=36,
            rightMargin=36,
            topMargin=44,
            bottomMargin=44,
        )
        story: list[Any] = []

        # Top Header Banner
        now_utc = datetime.now(timezone.utc)
        header_table = Table(
            [
                [
                    Paragraph("FINSIGHT FINANCIAL REPORT", styles["doc_title"]),
                    Paragraph(
                        f"<b>GENERATED:</b> {now_utc.strftime('%Y-%m-%d %H:%M UTC')}<br/>"
                        f"<b>ACCOUNT:</b> {user_id[:16]}…",
                        styles["header_meta_right"],
                    ),
                ],
                [
                    Paragraph("Comprehensive Financial Exposure & Predictive Intelligence Assessment", styles["doc_subtitle"]),
                    Paragraph("STATUS: <b>VERIFIED FINANCIAL AUDIT</b>", styles["header_meta_right_bold"]),
                ],
            ],
            colWidths=[330, 193],
        )
        header_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), NAVY_PRIMARY),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ])
        )
        story.append(header_table)
        story.append(Spacer(1, 10))

        # Client Profile & Audit Metadata Card
        meta_table = Table(
            [
                [
                    Paragraph("<b>Client Name:</b>", styles["body"]),
                    Paragraph(display_name, styles["body_bold"]),
                    Paragraph("<b>Financial User ID:</b>", styles["body"]),
                    Paragraph(user_id, styles["body"]),
                ],
                [
                    Paragraph("<b>Registered Email:</b>", styles["body"]),
                    Paragraph(email, styles["body"]),
                    Paragraph("<b>City / Persona:</b>", styles["body"]),
                    Paragraph(f"{city} | {persona}", styles["body"]),
                ],
                [
                    Paragraph("<b>Statement Period:</b>", styles["body"]),
                    Paragraph(date_range_str, styles["body_bold"]),
                    Paragraph("<b>Analyzed Transactions:</b>", styles["body"]),
                    Paragraph(f"{total_txns} total ({len(credit_txns)} credits, {len(debit_txns)} debits)", styles["body"]),
                ],
                [
                    Paragraph("<b>Income Basis:</b>", styles["body"]),
                    Paragraph(f"{income_source} ({income_mode})", styles["body"]),
                    Paragraph("<b>Active Commitments:</b>", styles["body"]),
                    Paragraph(f"{len(commitment_items)} active recurring obligation(s)", styles["body_bold"]),
                ],
            ],
            colWidths=[110, 151, 120, 142],
        )
        meta_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), BG_CARD),
                ("BOX", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ])
        )
        story.append(meta_table)
        story.append(Spacer(1, 14))

        # Executive Summary Section
        story.append(self._section_header("EXECUTIVE SUMMARY", "Holistic assessment of financial exposure, capacity, and solvency risks", styles))
        story.append(Spacer(1, 6))

        # 8-Card Metric Grid (2 rows x 4 columns)
        card_w = self.PAGE_WIDTH / 4.0
        exp_var_val = forecast_intel.expected_variable_expenses if (forecast_intel and forecast_intel.forecast_available) else (total_debits / max(len(history_points), 1) if history_points else 0.0)
        shortfall_risk_label = shortfall_intel.shortfall_risk if (shortfall_intel and shortfall_intel.available) else "UNAVAILABLE"

        metric_cards = [
            [
                self._build_card("MONTHLY CAPACITY", self._currency(monthly_capacity), f"Source: {income_source}", styles),
                self._build_card("MONTHLY COMMITMENTS", self._currency(monthly_commitments), f"{len(commitment_items)} active", styles),
                self._build_card("VARIABLE SPENDING", self._currency(exp_var_val), "Forecast / Monthly Avg", styles),
                self._build_card("AVAILABLE CAPACITY", self._currency(available_capacity), "Net Cash Headroom", styles),
            ],
            [
                self._build_card("FINANCIAL EXPOSURE", self._percent(exposure_score), exposure_band, styles, highlight="exposure", score=exposure_score),
                self._build_card("FINANCIAL HEALTH", f"{health_score}/100", health_label, styles, highlight="health", score=health_score),
                self._build_card("SHORTFALL RISK", shortfall_risk_label, "Model 4 Outlook", styles, highlight="shortfall", text=shortfall_risk_label),
                self._build_card("SAVINGS GOALS", f"{len(goals_list)} Configured", f"{sum(1 for g in goals_list if getattr(g, 'goal_feasible', False))} Feasible", styles),
            ],
        ]
        cards_table = Table(metric_cards, colWidths=[card_w] * 4)
        cards_table.setStyle(
            TableStyle([
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ])
        )
        story.append(cards_table)
        story.append(Spacer(1, 8))

        # Executive Summary Narrative Callout
        summary_narrative = (
            f"Based on <b>{total_txns} verified transactions</b> across <b>{date_range_str}</b>, "
            f"your financial capacity is assessed at <b>{self._currency(monthly_capacity)}</b> per month. "
            f"Active recurring commitments consume <b>{self._currency(monthly_commitments)}</b> ({self._percent(exposure_score)} of capacity), "
            f"leaving <b>{self._currency(available_capacity)}</b> in unencumbered monthly headroom. "
            f"Your Financial Health Score is <b>{health_score}/100 ({health_label})</b> with exposure classified in the <b>{exposure_band}</b> tier."
        )
        story.append(self._callout_box(summary_narrative, styles))
        story.append(Spacer(1, 14))

        # SECTION 1 & 2: Cash Inflows & Outflows
        story.append(self._section_header("1. CASH FLOW INFLOWS & OUTFLOWS ANALYSIS", "Breakdown of observed credits, living expenses, and category distributions", styles))
        story.append(Spacer(1, 6))

        inflow_summary_table = Table(
            [
                [
                    Paragraph("<b>Metric</b>", styles["table_header"]),
                    Paragraph("<b>Total Amount</b>", styles["table_header_right"]),
                    Paragraph("<b>Transaction Count</b>", styles["table_header_right"]),
                    Paragraph("<b>Monthly Average</b>", styles["table_header_right"]),
                ],
                [
                    Paragraph("Cash Inflows (Credits / Income)", styles["table_cell_bold"]),
                    Paragraph(self._currency(total_credits), styles["table_cell_right_bold"]),
                    Paragraph(str(len(credit_txns)), styles["table_cell_right"]),
                    Paragraph(self._currency(total_credits / max(len(history_points), 1)), styles["table_cell_right"]),
                ],
                [
                    Paragraph("Cash Outflows (Debits / Expenses)", styles["table_cell_bold"]),
                    Paragraph(self._currency(total_debits), styles["table_cell_right_bold"]),
                    Paragraph(str(len(debit_txns)), styles["table_cell_right"]),
                    Paragraph(self._currency(total_debits / max(len(history_points), 1)), styles["table_cell_right"]),
                ],
                [
                    Paragraph("Net Cash Flow Difference", styles["table_cell_bold"]),
                    Paragraph(self._currency(net_cash_flow), styles["table_cell_right_bold"]),
                    Paragraph(str(total_txns), styles["table_cell_right"]),
                    Paragraph(self._currency(net_cash_flow / max(len(history_points), 1)), styles["table_cell_right"]),
                ],
            ],
            colWidths=[163, 120, 120, 120],
        )
        inflow_summary_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), SLATE_LIGHT),
                ("BOX", (0, 0), (-1, -1), 0.5, BORDER_DARK),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ])
        )
        story.append(inflow_summary_table)
        story.append(Spacer(1, 8))

        # Category spending table (Top categories)
        if category_spending:
            sorted_cats = sorted(category_spending.items(), key=lambda x: x[1], reverse=True)[:8]
            cat_rows = [
                [
                    Paragraph("<b>Expense Category</b>", styles["table_header"]),
                    Paragraph("<b>Total Outflow</b>", styles["table_header_right"]),
                    Paragraph("<b>Share of Expenses</b>", styles["table_header_right"]),
                    Paragraph("<b>Transactions</b>", styles["table_header_right"]),
                ]
            ]
            for cat_name, cat_amt in sorted_cats:
                share_pct = (cat_amt / total_debits * 100.0) if total_debits > 0 else 0.0
                cat_rows.append([
                    Paragraph(cat_name, styles["table_cell"]),
                    Paragraph(self._currency(cat_amt), styles["table_cell_right"]),
                    Paragraph(self._percent(share_pct), styles["table_cell_right"]),
                    Paragraph(str(category_counts[cat_name]), styles["table_cell_right"]),
                ])
            cat_table = Table(cat_rows, colWidths=[163, 120, 120, 120])
            cat_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), SLATE_LIGHT),
                    ("BOX", (0, 0), (-1, -1), 0.5, BORDER_DARK),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_CARD]),
                    ("TOPPADDING", (0, 0), (-1, -1), 3.5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ])
            )
            story.append(cat_table)
        story.append(Spacer(1, 14))

        # SECTION 3: Recurring Commitments Breakdown (Unified Engine)
        story.append(self._section_header("2. RECURRING COMMITMENTS BREAKDOWN (UNIFIED ENGINE)", "Authoritative recurring obligations identified across Subscriptions, EMIs, and BNPL accounts", styles))
        story.append(Spacer(1, 6))

        if commitment_items:
            comm_rows = [
                [
                    Paragraph("<b>Obligation Name</b>", styles["table_header"]),
                    Paragraph("<b>Category</b>", styles["table_header"]),
                    Paragraph("<b>Monthly Burden</b>", styles["table_header_right"]),
                    Paragraph("<b>Source</b>", styles["table_header"]),
                    Paragraph("<b>Confidence</b>", styles["table_header"]),
                    Paragraph("<b>Next Due Date</b>", styles["table_header"]),
                ]
            ]
            for c in commitment_items:
                mo_amt = getattr(c, "monthly_equivalent_amount", getattr(c, "monthly_amount", getattr(c, "amount", 0.0)))
                due_dt = getattr(c, "next_payment_date", getattr(c, "next_due_date", "Recurring"))
                comm_rows.append([
                    Paragraph(c.name, styles["table_cell_bold"]),
                    Paragraph(c.category.title(), styles["table_cell"]),
                    Paragraph(self._currency(mo_amt), styles["table_cell_right_bold"]),
                    Paragraph(c.source, styles["table_cell"]),
                    Paragraph(c.confidence_level.title(), styles["table_cell"]),
                    Paragraph(str(due_dt or "Recurring"), styles["table_cell"]),
                ])
            # Total row
            comm_rows.append([
                Paragraph("<b>TOTAL RECURRING COMMITMENTS</b>", styles["table_cell_bold"]),
                Paragraph("<b>All Buckets</b>", styles["table_cell"]),
                Paragraph(f"<b>{self._currency(total_monthly_commitments)}</b>", styles["table_cell_right_bold"]),
                Paragraph("—", styles["table_cell"]),
                Paragraph("—", styles["table_cell"]),
                Paragraph("—", styles["table_cell"]),
            ])
            comm_table = Table(comm_rows, colWidths=[143, 85, 85, 65, 75, 70])
            comm_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), SLATE_LIGHT),
                    ("BOX", (0, 0), (-1, -1), 0.5, BORDER_DARK),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, BG_CARD]),
                    ("BACKGROUND", (0, -1), (-1, -1), ACCENT_INDIGO_LIGHT),
                    ("TOPPADDING", (0, 0), (-1, -1), 3.5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ])
            )
            story.append(comm_table)
        else:
            story.append(
                self._callout_box(
                    "<b>No Recurring Commitments Identified:</b> The Unified Commitment Engine did not identify active "
                    "recurring EMIs, subscriptions, or BNPL obligations in your uploaded transactions. Realized exposure is 0.0%.",
                    styles,
                )
            )
        story.append(Spacer(1, 14))

        # SECTION 4: Financial Exposure & Solvency Capacity
        story.append(self._section_header("3. FINANCIAL EXPOSURE & CAPACITY ASSESSMENT", "Committed fixed costs relative to total monthly capacity and discretionary resilience", styles))
        story.append(Spacer(1, 6))

        exposure_info_text = (
            f"<b>Exposure Formula:</b> Realized Exposure (%) = [Monthly Recurring Commitments / Monthly Capacity] × 100.<br/>"
            f"At <b>{self._percent(exposure_score)}</b>, your exposure falls into the <b>{exposure_band}</b> category. "
            f"{exposure_explanation}"
        )
        story.append(self._callout_box(exposure_info_text, styles))
        story.append(Spacer(1, 8))

        # Exposure Tiers Benchmark Table
        tiers_table = Table(
            [
                [
                    Paragraph("<b>Exposure Tier</b>", styles["table_header"]),
                    Paragraph("<b>Threshold Range</b>", styles["table_header"]),
                    Paragraph("<b>Risk Implication</b>", styles["table_header"]),
                    Paragraph("<b>Current Status</b>", styles["table_header"]),
                ],
                [
                    Paragraph("Low Exposure", styles["table_cell_bold"]),
                    Paragraph("< 30% of capacity", styles["table_cell"]),
                    Paragraph("Substantial discretionary headroom; highly resilient to income fluctuations.", styles["table_cell"]),
                    Paragraph("<b>ACTIVE</b>" if exposure_band.lower() == "low" else "—", styles["table_cell_bold"] if exposure_band.lower() == "low" else styles["table_cell"]),
                ],
                [
                    Paragraph("Moderate Exposure", styles["table_cell_bold"]),
                    Paragraph("30% – 50% of capacity", styles["table_cell"]),
                    Paragraph("Balanced commitments; prudent monitoring of non-essential additions advised.", styles["table_cell"]),
                    Paragraph("<b>ACTIVE</b>" if exposure_band.lower() == "moderate" else "—", styles["table_cell_bold"] if exposure_band.lower() == "moderate" else styles["table_cell"]),
                ],
                [
                    Paragraph("High Exposure", styles["table_cell_bold"]),
                    Paragraph("50% – 70% of capacity", styles["table_cell"]),
                    Paragraph("Elevated fixed overhead; savings capacity constrained.", styles["table_cell"]),
                    Paragraph("<b>ACTIVE</b>" if exposure_band.lower() == "high" else "—", styles["table_cell_bold"] if exposure_band.lower() == "high" else styles["table_cell"]),
                ],
                [
                    Paragraph("Critical Exposure", styles["table_cell_bold"]),
                    Paragraph("> 70% of capacity", styles["table_cell"]),
                    Paragraph("Over-committed; severe vulnerability to income disruptions or unforeseen shocks.", styles["table_cell"]),
                    Paragraph("<b>ACTIVE</b>" if exposure_band.lower() == "critical" else "—", styles["table_cell_bold"] if exposure_band.lower() == "critical" else styles["table_cell"]),
                ],
            ],
            colWidths=[100, 110, 233, 80],
        )
        tiers_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), SLATE_LIGHT),
                ("BOX", (0, 0), (-1, -1), 0.5, BORDER_DARK),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_CARD]),
                ("TOPPADDING", (0, 0), (-1, -1), 3.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ])
        )
        story.append(tiers_table)
        story.append(Spacer(1, 14))

        # SECTION 5: Financial Health Assessment
        story.append(self._section_header("4. FINANCIAL HEALTH ASSESSMENT", "Multi-factor financial stability score and behavioral rationale", styles))
        story.append(Spacer(1, 6))

        health_box_content = [
            Paragraph(f"<b>Financial Health Score: {health_score} / 100 ({health_label})</b>", styles["body_bold"]),
            Spacer(1, 4),
            Paragraph("<b>Core Rationales & Observations:</b>", styles["body"]),
        ]
        for rat in health_rationale:
            health_box_content.append(Paragraph(f"• {rat}", styles["bullet_item"]))
        health_box_content.extend([
            Spacer(1, 4),
            Paragraph(
                "<i><b>Methodological Disclaimer:</b> FinSight evaluates cash-flow solvency, commitment stability, "
                "and payment regularity. This score does NOT assess total liquid bank balances, external investments, "
                "or formal credit agency bureaus (e.g., CIBIL/Experian).</i>",
                styles["body"],
            ),
        ])
        story.append(self._card_box(health_box_content, BG_CARD))
        story.append(Spacer(1, 14))

        # SECTION 6: Historical Cash Flow & Monthly Trends
        if history_points:
            story.append(self._section_header("5. HISTORICAL CASH FLOW & REALIZED EXPOSURE TRENDS", "Monthly chronological breakdown of income, variable spending, fixed commitments, and exposure", styles))
            story.append(Spacer(1, 6))

            hist_rows = [
                [
                    Paragraph("<b>Month</b>", styles["table_header"]),
                    Paragraph("<b>Inflows</b>", styles["table_header_right"]),
                    Paragraph("<b>Variable Spend</b>", styles["table_header_right"]),
                    Paragraph("<b>Commitments</b>", styles["table_header_right"]),
                    Paragraph("<b>Net Flow</b>", styles["table_header_right"]),
                    Paragraph("<b>Exposure</b>", styles["table_header_right"]),
                    Paragraph("<b>Health</b>", styles["table_header_right"]),
                ]
            ]
            for p in history_points:
                net_mo = p.income - (p.spending + p.commitments)
                hist_rows.append([
                    Paragraph(p.month, styles["table_cell_bold"]),
                    Paragraph(self._currency(p.income), styles["table_cell_right"]),
                    Paragraph(self._currency(p.spending), styles["table_cell_right"]),
                    Paragraph(self._currency(p.commitments), styles["table_cell_right"]),
                    Paragraph(self._currency(net_mo), styles["table_cell_right_bold"]),
                    Paragraph(self._percent(p.exposure), styles["table_cell_right"]),
                    Paragraph(f"{p.financial_health}/100", styles["table_cell_right"]),
                ])
            hist_table = Table(hist_rows, colWidths=[65, 78, 78, 78, 78, 70, 76])
            hist_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), SLATE_LIGHT),
                    ("BOX", (0, 0), (-1, -1), 0.5, BORDER_DARK),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_CARD]),
                    ("TOPPADDING", (0, 0), (-1, -1), 3.5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ])
            )
            story.append(hist_table)
            story.append(Spacer(1, 14))

        # SECTION 7: Predictive Intelligence: Forward Forecast (Model 1)
        story.append(self._section_header("6. FORWARD CASH FLOW FORECAST (MODEL 1)", "Machine learning cash-flow projection and expected liquidity margins", styles))
        story.append(Spacer(1, 6))

        if forecast_intel and forecast_intel.forecast_available:
            fc_table = Table(
                [
                    [
                        Paragraph("<b>Forecast Parameter</b>", styles["table_header"]),
                        Paragraph("<b>Projected Amount</b>", styles["table_header_right"]),
                        Paragraph("<b>Analytical Basis</b>", styles["table_header"]),
                    ],
                    [
                        Paragraph("Forecast Horizon Month", styles["table_cell_bold"]),
                        Paragraph(str(forecast_intel.forecast_month), styles["table_cell_right_bold"]),
                        Paragraph("Immediate next financial calendar cycle", styles["table_cell"]),
                    ],
                    [
                        Paragraph("Expected Inflow / Income", styles["table_cell_bold"]),
                        Paragraph(self._currency(forecast_intel.expected_income), styles["table_cell_right_bold"]),
                        Paragraph("Based on recurring inflow patterns & manual settings", styles["table_cell"]),
                    ],
                    [
                        Paragraph("Expected Committed Expenses", styles["table_cell_bold"]),
                        Paragraph(self._currency(forecast_intel.expected_committed_expenses), styles["table_cell_right_bold"]),
                        Paragraph("Unified recurring commitment engine obligations", styles["table_cell"]),
                    ],
                    [
                        Paragraph("Expected Variable Expenses", styles["table_cell_bold"]),
                        Paragraph(self._currency(forecast_intel.expected_variable_expenses), styles["table_cell_right_bold"]),
                        Paragraph("Model 1 machine learning predictive estimate", styles["table_cell"]),
                    ],
                    [
                        Paragraph("Projected Net Cash Margin", styles["table_cell_bold"]),
                        Paragraph(self._currency(forecast_intel.expected_net_cash), styles["table_cell_right_bold"]),
                        Paragraph("Projected discretionary liquidity surplus / buffer", styles["table_cell"]),
                    ],
                ],
                colWidths=[183, 140, 200],
            )
            fc_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), SLATE_LIGHT),
                    ("BOX", (0, 0), (-1, -1), 0.5, BORDER_DARK),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_CARD]),
                    ("TOPPADDING", (0, 0), (-1, -1), 3.5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ])
            )
            story.append(fc_table)
        else:
            avail_months = getattr(forecast_intel, "history_months_available", len(history_points)) if forecast_intel else len(history_points)
            story.append(
                self._callout_box(
                    f"<b>Forecast Prerequisite Notice:</b> Model 1 requires a minimum of 6 continuous months of verified "
                    f"transaction history to generate forward-looking cash flow projections safely without risk of overfitting. "
                    f"Currently available: <b>{avail_months} months</b>.",
                    styles,
                )
            )
        story.append(Spacer(1, 14))

        # SECTION 8: Subscription Intelligence (Model 3)
        story.append(self._section_header("7. SUBSCRIPTION INTELLIGENCE & OPTIMIZATION (MODEL 3)", "Recurring digital services, autopay coverage, and potential savings", styles))
        story.append(Spacer(1, 6))

        if sub_intel and sub_intel.subscription_summary.subscription_count > 0:
            ss = sub_intel.subscription_summary
            sub_meta = Table(
                [
                    [
                        Paragraph(f"<b>Active Subscriptions:</b> {ss.subscription_count}", styles["body"]),
                        Paragraph(f"<b>Monthly Spend:</b> {self._currency(ss.monthly_subscription_cost)}", styles["body"]),
                        Paragraph(f"<b>Annualized:</b> {self._currency(ss.monthly_subscription_cost * 12)}", styles["body"]),
                        Paragraph(f"<b>Autopay Share:</b> {self._percent(sub_intel.autopay_statistics.autopay_share_of_subscriptions * 100)}", styles["body"]),
                    ]
                ],
                colWidths=[130, 131, 131, 131],
            )
            sub_meta.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), BG_CARD),
                    ("BOX", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ])
            )
            story.append(sub_meta)
            story.append(Spacer(1, 6))

            if sub_intel.active_subscriptions:
                sub_rows = [
                    [
                        Paragraph("<b>Service / Merchant</b>", styles["table_header"]),
                        Paragraph("<b>Monthly Cost</b>", styles["table_header_right"]),
                        Paragraph("<b>Autopay</b>", styles["table_header"]),
                        Paragraph("<b>Frequency</b>", styles["table_header"]),
                        Paragraph("<b>Engagement Status</b>", styles["table_header"]),
                    ]
                ]
                for sub_item in sub_intel.active_subscriptions:
                    m_name = getattr(sub_item, "merchant_name", getattr(sub_item, "service_name", "Subscription"))
                    m_cost = getattr(sub_item, "average_subscription_amount", getattr(sub_item, "monthly_cost", 0.0))
                    is_auto = "Enabled" if getattr(sub_item, "autopay_enabled", False) else "Manual"
                    f_freq = str(getattr(sub_item, "recurring_frequency", getattr(sub_item, "billing_frequency", "Monthly"))).title()
                    u_class = str(getattr(sub_item, "merchant_type", getattr(sub_item, "usage_classification", "Digital Service"))).title()
                    sub_rows.append([
                        Paragraph(m_name, styles["table_cell_bold"]),
                        Paragraph(self._currency(m_cost), styles["table_cell_right_bold"]),
                        Paragraph(is_auto, styles["table_cell"]),
                        Paragraph(f_freq, styles["table_cell"]),
                        Paragraph(u_class, styles["table_cell"]),
                    ])
                sub_table = Table(sub_rows, colWidths=[163, 90, 80, 90, 100])
                sub_table.setStyle(
                    TableStyle([
                        ("BACKGROUND", (0, 0), (-1, 0), SLATE_LIGHT),
                        ("BOX", (0, 0), (-1, -1), 0.5, BORDER_DARK),
                        ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_CARD]),
                        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ])
                )
                story.append(sub_table)
        else:
            story.append(self._callout_box("No recurring digital subscriptions detected in your transactions.", styles))
        story.append(Spacer(1, 14))

        # SECTION 9: Financial Goals Feasibility (Model 2)
        story.append(self._section_header("8. FINANCIAL GOAL FEASIBILITY (MODEL 2)", "Feasibility simulation for configured savings goals based on unencumbered capacity", styles))
        story.append(Spacer(1, 6))

        if goals_list:
            goal_rows = [
                [
                    Paragraph("<b>Goal Name</b>", styles["table_header"]),
                    Paragraph("<b>Target Target</b>", styles["table_header_right"]),
                    Paragraph("<b>Horizon</b>", styles["table_header"]),
                    Paragraph("<b>Required/mo</b>", styles["table_header_right"]),
                    Paragraph("<b>Feasibility</b>", styles["table_header"]),
                    Paragraph("<b>Discretionary Plan</b>", styles["table_header"]),
                ]
            ]
            for g in goals_list:
                status_str = "Feasible" if getattr(g, "goal_feasible", False) else "Challenging"
                req_save = getattr(g, "required_monthly_saving", 0.0) or 0.0
                adj_count = len(getattr(g, "suggested_category_adjustments", getattr(g, "discretionary_adjustments", [])) or [])
                goal_rows.append([
                    Paragraph(g.goal_name, styles["table_cell_bold"]),
                    Paragraph(self._currency(g.goal_amount), styles["table_cell_right"]),
                    Paragraph(f"{g.goal_months} mos", styles["table_cell"]),
                    Paragraph(self._currency(req_save), styles["table_cell_right_bold"]),
                    Paragraph(f"<b>{status_str}</b>", styles["table_cell_bold"] if status_str == "Feasible" else styles["table_cell"]),
                    Paragraph(f"{adj_count} trimmable categories" if adj_count else "Direct capacity", styles["table_cell"]),
                ])
            goal_table = Table(goal_rows, colWidths=[123, 75, 55, 85, 85, 100])
            goal_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), SLATE_LIGHT),
                    ("BOX", (0, 0), (-1, -1), 0.5, BORDER_DARK),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_CARD]),
                    ("TOPPADDING", (0, 0), (-1, -1), 3.5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ])
            )
            story.append(goal_table)
        else:
            story.append(
                self._callout_box(
                    "<b>No Active Goals Configured:</b> You have not configured any savings targets in FinSight yet. "
                    "Configure financial goals in the Goals module to simulate monthly feasibility against your net cash capacity.",
                    styles,
                )
            )
        story.append(Spacer(1, 14))

        # SECTION 10: Cash Shortfall Prediction (Model 4)
        story.append(self._section_header("9. CASH SHORTFALL RISK PREDICTION (MODEL 4)", "Machine learning early-warning detection for impending cash shortfalls", styles))
        story.append(Spacer(1, 6))

        if shortfall_intel and shortfall_intel.available:
            sf_content = [
                Paragraph(
                    f"<b>Shortfall Risk Classification: {shortfall_intel.shortfall_risk}</b> "
                    f"(Target Horizon: {shortfall_intel.next_month_horizon})",
                    styles["body_bold"],
                ),
                Spacer(1, 3),
                Paragraph(
                    getattr(shortfall_intel, "risk_explanation", None)
                    or getattr(shortfall_intel, "explanation", None)
                    or "Model 4 evaluated cash-flow buffers against projected obligations.",
                    styles["body"],
                ),
            ]
            sf_factors = (
                getattr(shortfall_intel, "contributing_factors", None)
                or getattr(shortfall_intel, "top_factors", None)
                or []
            )
            if sf_factors:
                sf_content.extend([
                    Spacer(1, 4),
                    Paragraph("<b>Key Contributing Risk Factors:</b>", styles["body_bold"]),
                ])
                for f in sf_factors:
                    sf_content.append(Paragraph(f"• {f}", styles["bullet_item"]))
            sf_actions = getattr(shortfall_intel, "recommended_actions", []) or []
            if sf_actions:
                sf_content.extend([
                    Spacer(1, 4),
                    Paragraph("<b>Recommended Preventative Steps:</b>", styles["body_bold"]),
                ])
                for act in sf_actions:
                    sf_content.append(Paragraph(f"• {act}", styles["bullet_item"]))
            story.append(self._card_box(sf_content, BG_CARD))
        else:
            story.append(
                self._callout_box(
                    "<b>Shortfall Model Prerequisite Notice:</b> Model 4 requires a minimum of 6 continuous months of "
                    "verified transaction history to assess next-month cash shortfall probability accurately.",
                    styles,
                )
            )
        story.append(Spacer(1, 14))

        # SECTION 11: Prioritized Action Recommendations
        if recommendations:
            story.append(self._section_header("10. PRIORITIZED FINANCIAL ACTION RECOMMENDATIONS", "Tailored analytical steps to optimize exposure, reduce recurring overhead, and reinforce liquidity", styles))
            story.append(Spacer(1, 6))

            rec_rows = [
                [
                    Paragraph("<b>Priority</b>", styles["table_header"]),
                    Paragraph("<b>Recommendation</b>", styles["table_header"]),
                    Paragraph("<b>Target Action</b>", styles["table_header"]),
                ]
            ]
            for idx, r in enumerate(recommendations[:5], 1):
                prio_label = str(getattr(r, "priority", ("HIGH" if idx == 1 else ("MEDIUM" if idx <= 3 else "LOW")))).upper()
                rec_title = getattr(r, "recommendation_type", getattr(r, "title", "Financial Optimization"))
                rec_desc = getattr(r, "action_required", getattr(r, "message", getattr(r, "description", "")))
                rec_rows.append([
                    Paragraph(f"<b>{prio_label}</b>", styles["table_cell_bold"]),
                    Paragraph(rec_title, styles["table_cell_bold"]),
                    Paragraph(rec_desc, styles["table_cell"]),
                ])
            rec_table = Table(rec_rows, colWidths=[65, 150, 308])
            rec_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), SLATE_LIGHT),
                    ("BOX", (0, 0), (-1, -1), 0.5, BORDER_DARK),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_CARD]),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ])
            )
            story.append(rec_table)
            story.append(Spacer(1, 14))

        # SECTION 12: Methodology & Transparent Governance Disclosures
        story.append(self._section_header("11. METHODOLOGY, MODEL GOVERNANCE & DISCLAIMERS", "Transparent system architecture disclosures and regulatory terms", styles))
        story.append(Spacer(1, 6))

        governance_text = (
            "<b>1. Machine Learning Governance:</b> FinSight operates four specialized financial intelligence engines: "
            "Model 1 (Predictive Cash Flow Forecasting), Model 2 (Goal Feasibility & Discretionary Expense Trimming), "
            "Model 3 (Subscription Usage Intelligence), and Model 4 (Forward Shortfall Risk Classifier). "
            "Predictive models strictly enforce a 6-month historical data threshold to prevent ungrounded inferences.<br/><br/>"
            "<b>2. Strict Tenant Isolation:</b> All calculations, historical metrics, and forecasts in this report are "
            "computed strictly from transaction data associated with the authenticated user ID. No cross-tenant data pooling "
            "or third-party analytics sharing occurs.<br/><br/>"
            "<b>3. Decision Support Disclaimer:</b> This report is generated solely for informational and analytical decision-support "
            "purposes. FinSight is not a registered investment advisor, banking institution, or credit bureau. "
            "Calculations reflect transaction trends in uploaded statements and do not constitute formal legal, tax, or investment advice."
        )
        story.append(self._card_box([Paragraph(governance_text, styles["body"])], BG_CARD))

        # Build Document
        doc.build(story, canvasmaker=NumberedCanvas)
        return buffer.getvalue()

    # ── Helper Component Builders ─────────────────────────────────────────────

    def _section_header(self, title: str, subtitle: str, styles: dict[str, ParagraphStyle]) -> KeepTogether:
        header_table = Table(
            [
                [
                    Paragraph(title, styles["section_title"]),
                ],
                [
                    Paragraph(subtitle, styles["section_subtitle"]),
                ],
                [
                    HRFlowable(width="100%", thickness=1, color=BORDER_DARK, spaceBefore=3, spaceAfter=0),
                ],
            ],
            colWidths=[self.PAGE_WIDTH],
        )
        header_table.setStyle(
            TableStyle([
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ])
        )
        return KeepTogether([header_table])

    def _build_card(
        self,
        title: str,
        value: str,
        sub: str,
        styles: dict[str, ParagraphStyle],
        highlight: str | None = None,
        score: float | None = None,
        text: str | None = None,
    ) -> Table:
        bg = BG_CARD
        border = BORDER_LIGHT
        if highlight == "exposure" and score is not None:
            if score >= 70:
                bg, border = ROSE_LIGHT, ROSE_ALERT
            elif score >= 50:
                bg, border = AMBER_LIGHT, AMBER_WARN
            elif score < 30:
                bg, border = EMERALD_LIGHT, EMERALD_GREEN
        elif highlight == "health" and score is not None:
            if score >= 75:
                bg, border = EMERALD_LIGHT, EMERALD_GREEN
            elif score >= 50:
                bg, border = AMBER_LIGHT, AMBER_WARN
            else:
                bg, border = ROSE_LIGHT, ROSE_ALERT
        elif highlight == "shortfall" and text:
            t = text.lower()
            if "high" in t or "critical" in t:
                bg, border = ROSE_LIGHT, ROSE_ALERT
            elif "moderate" in t:
                bg, border = AMBER_LIGHT, AMBER_WARN
            elif "low" in t:
                bg, border = EMERALD_LIGHT, EMERALD_GREEN

        card_table = Table(
            [
                [Paragraph(title, styles["card_title"])],
                [Spacer(1, 2)],
                [Paragraph(value, styles["card_value"])],
                [Spacer(1, 2)],
                [Paragraph(sub, styles["card_sub"])],
            ],
            colWidths=[self.PAGE_WIDTH / 4.0 - 4],
        )
        card_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), bg),
                ("BOX", (0, 0), (-1, -1), 0.5, border),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ])
        )
        return card_table

    def _callout_box(self, content_html: str, styles: dict[str, ParagraphStyle]) -> Table:
        table = Table(
            [[Paragraph(content_html, styles["notice_box_text"])]],
            colWidths=[self.PAGE_WIDTH],
        )
        table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), ACCENT_INDIGO_LIGHT),
                ("BOX", (0, 0), (-1, -1), 0.5, ACCENT_INDIGO),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ])
        )
        return table

    def _card_box(self, flowables: list[Any], bg_color: colors.Color) -> Table:
        table = Table([[flowables]], colWidths=[self.PAGE_WIDTH])
        table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), bg_color),
                ("BOX", (0, 0), (-1, -1), 0.5, BORDER_DARK),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ])
        )
        return table


_pdf_report_service: FinancialReportPdfService | None = None


def get_financial_report_pdf_service() -> FinancialReportPdfService:
    global _pdf_report_service
    if _pdf_report_service is None:
        _pdf_report_service = FinancialReportPdfService()
    return _pdf_report_service
