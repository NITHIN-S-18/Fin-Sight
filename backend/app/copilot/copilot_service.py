from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import re
from typing import Any

from fastapi import Depends
from sqlalchemy.orm import Session

from app.copilot.intent_detector import IntentDetector
from app.copilot.intent_router import IntentRouter
from app.copilot.llm_provider import (
    CopilotLLMProvider,
    GENERAL_ASSISTANT_SYSTEM_PROMPT,
    build_llm_provider,
)
from app.copilot.response_generator import ResponseGenerator
from app.copilot.tools import FinancialToolRegistry, get_knowledge_retriever
from app.database.models.conversation import (
    Conversation,
    ConversationMessage,
    generate_conv_id,
    generate_msg_id,
)
from app.decision.decision_engine import DecisionContext, DecisionEngine
from app.digital_twin.comparison_engine import ComparisonEngine
from app.digital_twin.scenario_builder import Scenario, ScenarioBuilder, ScenarioType
from app.digital_twin.twin_engine import DigitalTwinEngine, FinancialSnapshot
from app.dna.dna_engine import DNAEngine
from app.experience.opportunity_engine import OpportunityEngine
from app.schemas.copilot import (
    AssistantChatResponse,
    ConversationDetailResponse,
    ConversationMessageResponse,
    ConversationResponse,
    CopilotOpportunityItem,
    CopilotQueryRequest,
    CopilotResponse,
    CopilotSuggestionsResponse,
)
from app.core.config import get_settings
from app.services.dataset_service import DatasetService, get_dataset_service
from app.services.exposure_service import ExposureService, get_exposure_service

logger = logging.getLogger(__name__)


class CopilotService:
    """
    Full AI Assistant and Financial Decision Copilot Service.
    Supports Option C: General-Purpose AI (coding, CS, QA) + Personal Financial Intelligence (FinSight).
    """

    def __init__(
        self,
        exposure_service: ExposureService | None = None,
        intent_detector: IntentDetector | None = None,
        intent_router: IntentRouter | None = None,
        twin_engine: DigitalTwinEngine | None = None,
        scenario_builder: ScenarioBuilder | None = None,
        comparison_engine: ComparisonEngine | None = None,
        decision_engine: DecisionEngine | None = None,
        dna_engine: DNAEngine | None = None,
        opportunity_engine: OpportunityEngine | None = None,
        response_generator: ResponseGenerator | None = None,
        llm_provider: CopilotLLMProvider | None = None,
        tool_registry: FinancialToolRegistry | None = None,
        dataset_service: DatasetService | None = None,
    ) -> None:
        self._exposure_service = exposure_service
        self._dataset_service = dataset_service or get_dataset_service()
        self._intent_detector = intent_detector or IntentDetector()
        self._intent_router = intent_router or IntentRouter()
        self._twin_engine = twin_engine or DigitalTwinEngine()
        self._scenario_builder = scenario_builder or ScenarioBuilder(twin_engine=self._twin_engine)
        self._comparison_engine = comparison_engine or ComparisonEngine()
        self._decision_engine = decision_engine or DecisionEngine()
        self._dna_engine = dna_engine or DNAEngine()
        self._opportunity_engine = opportunity_engine or OpportunityEngine()
        self._response_generator = response_generator or ResponseGenerator()
        self._llm_provider = llm_provider
        self._tool_registry = tool_registry or FinancialToolRegistry(
            exposure_service=self._exposure_service,
            dataset_service=self._dataset_service,
        )

    # ─────────────────────────────────────────────────────────────
    # Option C: Conversational Assistant Orchestration
    # ─────────────────────────────────────────────────────────────

    def chat(
        self,
        user_id: str,
        message: str,
        conversation_id: str | None,
        document_context: str | None,
        db_session: Session,
    ) -> AssistantChatResponse:
        """
        Processes a multi-turn user message across General AI, Personal Finance, RAG, and Document QA.
        Enforces tenant isolation using authenticated user_id.
        """
        clean_msg = message.strip()
        now_dt = datetime.now(timezone.utc)

        # 1. Resolve or create Conversation
        conversation: Conversation | None = None
        if conversation_id:
            conversation = (
                db_session.query(Conversation)
                .filter(Conversation.id == conversation_id, Conversation.user_id == user_id)
                .first()
            )

        if conversation is None:
            conv_title = clean_msg[:50].replace("\n", " ").strip() or "New Conversation"
            conversation = Conversation(
                id=generate_conv_id(),
                user_id=user_id,
                title=conv_title,
                created_at=now_dt,
                updated_at=now_dt,
            )
            db_session.add(conversation)
            db_session.flush()

        active_conv_id = conversation.id

        # 2. Domain and Intent Classification
        domain, intent, tool_calls, context_data = self._classify_and_fetch_context(
            user_id=user_id,
            message=clean_msg,
            document_context=document_context,
        )

        # 3. Retrieve recent conversation history for multi-turn context
        history_records = (
            db_session.query(ConversationMessage)
            .filter(
                ConversationMessage.conversation_id == active_conv_id,
                ConversationMessage.user_id == user_id,
            )
            .order_by(ConversationMessage.created_at.asc())
            .all()
        )
        recent_history = history_records[-6:] if len(history_records) > 6 else history_records

        # 4. Construct LLM Prompts
        llm_messages: list[dict[str, str]] = []
        for hist in recent_history:
            role = "user" if hist.sender == "user" else "model"
            llm_messages.append({"role": role, "content": hist.text})

        # Augment current user prompt with ground truth / RAG context if applicable
        current_turn_prompt = clean_msg
        if context_data:
            if domain == "personal_finance":
                current_turn_prompt = (
                    f"{clean_msg}\n\n"
                    f"[AUTHORITATIVE FINSIGHT BACKEND DATA - GROUND TRUTH]:\n"
                    f"{json.dumps(context_data, indent=2)}\n"
                    f"(Note: Use this exact financial data. Never contradict it.)"
                )
            elif domain == "platform_docs":
                current_turn_prompt = (
                    f"{clean_msg}\n\n"
                    f"[VERIFIED FINSIGHT PLATFORM DOCUMENTATION]:\n"
                    f"{json.dumps(context_data, indent=2)}"
                )
            elif domain == "document_qa":
                current_turn_prompt = (
                    f"{clean_msg}\n\n"
                    f"[ATTACHED USER DOCUMENT (UNTRUSTED REFERENCE)]:\n"
                    f"{context_data.get('document_text', '')}"
                )

        llm_messages.append({"role": "user", "content": current_turn_prompt})

        # 5. Call LLM Provider
        assistant_text: str | None = None
        provider_name = "deterministic_fallback"

        if self._llm_provider is not None:
            assistant_text = self._llm_provider.generate_chat_response(
                messages=llm_messages,
                system_instruction=GENERAL_ASSISTANT_SYSTEM_PROMPT,
                max_tokens=1500,
            )
            if assistant_text:
                provider_name = getattr(
                    self._llm_provider,
                    "last_provider",
                    getattr(self._llm_provider, "provider_name", "gemini"),
                )

        # 6. Fallback if LLM unavailable or returned empty
        if not assistant_text:
            assistant_text = self._build_offline_fallback(
                domain=domain,
                intent=intent,
                clean_msg=clean_msg,
                context_data=context_data,
            )
            provider_name = "deterministic_fallback"

        # 7. Persist messages to database
        user_msg_id = generate_msg_id()
        asst_msg_id = generate_msg_id()

        user_db_msg = ConversationMessage(
            id=user_msg_id,
            conversation_id=active_conv_id,
            user_id=user_id,
            sender="user",
            text=clean_msg,
            intent=intent,
            tool_calls=[],
            metadata_payload={},
            created_at=now_dt,
        )

        metadata_dict = {
            "domain": domain,
            "generated_by": provider_name,
            "llm_fallback": provider_name == "deterministic_fallback",
        }

        asst_db_msg = ConversationMessage(
            id=asst_msg_id,
            conversation_id=active_conv_id,
            user_id=user_id,
            sender="assistant",
            text=assistant_text,
            intent=intent,
            tool_calls=tool_calls,
            metadata_payload=metadata_dict,
            created_at=now_dt,
        )

        # Update conversation title if first user message
        if conversation.title in {"New Conversation", "New Chat", ""} and len(history_records) == 0:
            conversation.title = clean_msg[:50].replace("\n", " ").strip() or "Financial Query"

        conversation.updated_at = now_dt
        db_session.add(user_db_msg)
        db_session.add(asst_db_msg)
        db_session.commit()

        # Extract factors or recommendations if present in context
        factors: list[str] = []
        if isinstance(context_data, dict):
            if "contributing_factors" in context_data:
                factors.extend(context_data["contributing_factors"])
            elif "health_rationale" in context_data:
                factors.extend(context_data["health_rationale"])

        recommendation_str = None
        if isinstance(context_data, dict) and "recommendation" in context_data:
            recommendation_str = str(context_data["recommendation"])

        return AssistantChatResponse(
            conversation_id=active_conv_id,
            message_id=asst_msg_id,
            text=assistant_text,
            response=assistant_text,
            intent=intent,
            domain=domain,
            tool_calls=tool_calls,
            factors=factors[:4],
            recommendation=recommendation_str,
            action=None,
            metadata=metadata_dict,
            created_at=now_dt.isoformat(),
        )

    def _classify_and_fetch_context(
        self,
        user_id: str,
        message: str,
        document_context: str | None,
    ) -> tuple[str, str, list[dict[str, Any]], dict[str, Any] | None]:
        """
        Routes the user's message to the appropriate domain, executes authorized tools,
        and returns domain, intent, tool_calls, and structured context.
        """
        low = message.lower().strip()
        # Phonetic and common spelling normalization for robust intent routing
        norm_low = (
            low.replace("finacial", "financial")
            .replace("fiancial", "financial")
            .replace("tis ", "this ")
        )
        tool_calls: list[dict[str, Any]] = []

        # A. Document QA
        if document_context and len(document_context.strip()) > 0:
            return (
                "document_qa",
                "document_analysis",
                [{"tool": "analyze_document", "size_chars": len(document_context)}],
                {"document_text": document_context},
            )

        # B. Pure Greetings (e.g. "hi", "hello", "hey", "good morning")
        is_greeting = bool(
            re.match(r"^\s*(hi|hii+|hello|hey|heyy+|greetings|howdy|good\s+(morning|afternoon|evening|day))\b", norm_low)
        ) and len(norm_low.split()) <= 4
        if is_greeting:
            return ("general_ai", "greeting", [], {"is_greeting": True})

        # C. System & Platform Overview (e.g. "so what exactly this web does", "what does this app do", "what is finsight")
        overview_patterns = [
            "what does this web", "what does this app", "what does this website",
            "what is this web", "what is this app", "what is this website",
            "what exactly this web", "what exactly this app", "what does finsight",
            "what is finsight", "about finsight", "tell me about this web",
            "explain this app", "explain this platform", "how does this web",
            "how does this app", "what can this app do", "what can this website do",
            "how can this web help", "how does finsight work", "what is this system",
            "what does this system do", "tell me about finsight",
        ]
        is_platform_overview = any(p in norm_low for p in overview_patterns) or (
            any(w in norm_low for w in ["web", "website", "app", "platform", "system", "finsight"])
            and any(w in norm_low for w in ["what does", "what do", "how does", "what exactly", "purpose", "overview", "what is"])
        )
        if is_platform_overview:
            chunks = self._tool_registry.search_knowledge("FinSight system overview architecture")
            tool_calls.append({"tool": "search_finsight_knowledge", "matches": len(chunks)})
            return ("platform_docs", "platform_overview", tool_calls, {"matches": chunks, "topic": "platform_overview"})

        # D. Financial Exposure: Calculation Methodology (Conceptual) vs Personal Value
        has_exposure_mention = "exposure" in norm_low or "exposur" in norm_low

        is_methodology_query = any(w in norm_low for w in [
            "how is", "how are", "formula", "methodology", "explain how",
            "calculation", "calculate", "how do you", "definition", "how does", "what is"
        ])

        is_personal_reference = any(p in norm_low for p in [
            "my", "mine", "current", "i am", "am i"
        ])

        if has_exposure_mention:
            # If user asks how it is calculated OR does not reference personal values: conceptual
            if (is_methodology_query and not any(p in norm_low for p in ["what is my", "what's my", "show my", "what is our"])) or not is_personal_reference:
                chunks = self._tool_registry.search_knowledge("financial exposure calculation formula")
                tool_calls.append({"tool": "search_finsight_knowledge", "matches": len(chunks)})
                return ("platform_docs", "platform_knowledge", tool_calls, {"matches": chunks, "concept": "financial_exposure"})
            else:
                # User asking for their specific personal exposure value / numbers
                is_personal_exposure = True
        else:
            is_personal_exposure = False

        # E. Other Platform & Technical RAG
        rag_patterns = [
            "model 1", "model 2", "model 3", "model 4",
            "discretionary policy", "commitment engine", "digital twin",
            "how is health score calculated", "explain health score",
            "how does model", "cash flow model", "shortfall model",
        ]
        is_rag_query = any(p in norm_low for p in rag_patterns)
        if is_rag_query:
            chunks = self._tool_registry.search_knowledge(message)
            tool_calls.append({"tool": "search_finsight_knowledge", "matches": len(chunks)})
            return ("platform_docs", "platform_knowledge", tool_calls, {"matches": chunks})

        # F. Personal Financial Queries
        finance_keywords = [
            "commitment", "commitments", "recurring", "emi", "emis", "loan", "loans",
            "subscription", "subscriptions", "spending", "spend", "spent", "expense", "expenses",
            "salary", "income", "budget", "cash flow", "cashflow", "forecast", "shortfall",
            "afford", "savings goal", "savings", "balance", "transaction", "transactions",
            "financial health", "netflix", "spotify", "rent", "broadband", "electricity",
        ]
        has_personal_intent = is_personal_exposure or (
            any(k in norm_low for k in finance_keywords) and (
                any(p in norm_low for p in ["my", "i ", "i'm", "me", "mine", "current", "what are", "how much", "can i", "do i"])
                or any(k in norm_low for k in ["forecast", "shortfall", "commitments", "recurring", "subscriptions"])
            )
        )

        if has_personal_intent:
            # Check if user has transactions
            txs = self._dataset_service.get_user_transactions(user_id)
            if not txs:
                return (
                    "personal_finance",
                    "missing_data",
                    [],
                    {"error": "No uploaded transactions found for this account."},
                )

            # Sub-routing to specific tools
            if any(k in norm_low for k in ["forecast", "cash flow", "cashflow", "next month", "inflow", "net cash"]):
                data = self._tool_registry.get_cash_flow_forecast(user_id)
                tool_calls.append({"tool": "get_cash_flow_forecast", "status": "success"})
                return ("personal_finance", "cash_flow_forecast", tool_calls, data)

            if any(k in norm_low for k in ["shortfall", "risk of running out", "adverse factor", "deficit"]):
                data = self._tool_registry.get_shortfall_prediction(user_id)
                tool_calls.append({"tool": "get_shortfall_prediction", "status": "success"})
                return ("personal_finance", "shortfall_prediction", tool_calls, data)

            if any(k in norm_low for k in ["subscription", "netflix", "spotify", "underutilised", "underutilized"]):
                data = self._tool_registry.get_subscription_intelligence(user_id)
                tool_calls.append({"tool": "get_subscription_intelligence", "status": "success"})
                return ("personal_finance", "subscription_intelligence", tool_calls, data)

            if any(k in norm_low for k in ["cancel", "what if i cancel", "simulate cancel"]):
                item_name = "Netflix" if "netflix" in norm_low else "Spotify" if "spotify" in norm_low else "Subscription"
                data = self._tool_registry.simulate_cancellation(user_id, item_name)
                tool_calls.append({"tool": "simulate_cancellation", "item": item_name, "status": "success"})
                return ("personal_finance", "what_if_simulation", tool_calls, data)

            if any(k in norm_low for k in ["commitment", "commitments", "recurring", "emi", "emis", "loan", "bill", "rent", "broadband"]):
                data = self._tool_registry.get_commitments(user_id)
                tool_calls.append({"tool": "get_commitments", "status": "success"})
                return ("personal_finance", "recurring_commitments", tool_calls, data)

            if any(k in norm_low for k in ["goal", "target", "save for", "afford"]):
                amounts = re.findall(r"\b\d{4,8}\b", norm_low)
                goal_amt = float(amounts[0]) if amounts else 100000.0
                data = self._tool_registry.evaluate_financial_goal(
                    user_id=user_id,
                    goal_amount=goal_amt,
                    timeframe_months=6,
                    goal_name="Target Goal",
                )
                tool_calls.append({"tool": "evaluate_financial_goal", "amount": goal_amt, "status": "success"})
                return ("personal_finance", "goal_feasibility", tool_calls, data)

            if any(k in norm_low for k in ["spend", "spending", "food", "grocery", "dining", "travel", "shopping"]):
                cat_match = None
                for cat in ["Food", "Dining", "Groceries", "Travel", "Shopping", "Entertainment", "Utilities"]:
                    if cat.lower() in norm_low:
                        cat_match = cat
                        break
                data = self._tool_registry.get_transaction_summary(user_id, category=cat_match)
                tool_calls.append({"tool": "get_transaction_summary", "category": cat_match, "status": "success"})
                return ("personal_finance", "spending_analysis", tool_calls, data)

            # Default financial summary (exposure & health)
            data = self._tool_registry.get_financial_summary(user_id)
            tool_calls.append({"tool": "get_financial_summary", "status": "success"})
            return ("personal_finance", "financial_health_and_exposure", tool_calls, data)

        # G. General-Purpose AI (Programming, CS, Academic, Writing, General QA)
        return ("general_ai", "general_knowledge", [], None)

    def _build_offline_fallback(
        self,
        domain: str,
        intent: str,
        clean_msg: str,
        context_data: dict[str, Any] | None,
    ) -> str:
        """
        Builds a high-quality, formatted offline response when the external LLM is offline.
        """
        if domain == "personal_finance" and context_data:
            if "error" in context_data:
                return (
                    "### ⚠️ Transaction History Required\n\n"
                    "FinSight requires transaction records to analyze your personal financial position. "
                    "Please navigate to the **Upload** page to load your statement."
                )

            if intent == "cash_flow_forecast":
                return (
                    f"### 📈 Cash Flow Forecast (Model 1 Ground Truth)\n\n"
                    f"- **Expected Inflow:** ₹{context_data.get('expected_income', 0):,.2f}\n"
                    f"- **Committed Contractual Expenses:** ₹{context_data.get('expected_committed_expenses', 0):,.2f}\n"
                    f"- **Variable Living Expenses:** ₹{context_data.get('expected_variable_expenses', 0):,.2f}\n"
                    f"- **Projected Net Cashflow:** **₹{context_data.get('expected_net_cash', 0):,.2f}**\n\n"
                    f"*Forecast derived authoritatively by Model 1.*"
                )

            if intent == "recurring_commitments":
                items = context_data.get("commitment_items", [])
                lines = [
                    f"### 💳 Unified Recurring Commitments\n\n"
                    f"You have **{context_data.get('commitments_count', 0)} active recurring commitments** "
                    f"totaling **₹{context_data.get('total_monthly_commitments', 0):,.2f}/month**.\n"
                ]
                for item in items[:6]:
                    lines.append(f"- **{item['title']}**: ₹{item['monthly_amount']:,.2f}/mo ({item['category'].title()})")
                return "\n".join(lines)

            if intent == "shortfall_prediction":
                risk = context_data.get("shortfall_risk_level", "LOW")
                pred = context_data.get("prediction", "UNLIKELY_SHORTFALL")
                factors = context_data.get("contributing_factors", [])
                return (
                    f"### 🛡️ Financial Shortfall Prediction (Model 4)\n\n"
                    f"- **Risk Classification:** **{risk}**\n"
                    f"- **Prediction:** {pred}\n"
                    f"- **Primary Factors:** {', '.join(factors) if factors else 'No critical adverse factors detected.'}\n"
                )

            if intent == "subscription_intelligence":
                subs = context_data.get("subscriptions", [])
                return (
                    f"### 📺 Subscription Intelligence (Model 3)\n\n"
                    f"You have **{context_data.get('active_subscriptions_count', 0)} active subscriptions** "
                    f"totaling **₹{context_data.get('monthly_subscription_cost', 0):,.2f}/month**.\n\n"
                    f"- **Active Services:** {', '.join(s['service_name'] for s in subs)}\n"
                    f"- **Potential Savings:** ₹{context_data.get('potential_monthly_savings', 0):,.2f}/month\n"
                    f"- **Recommendation:** {context_data.get('recommendation', 'Active engagement')}"
                )

            # Default financial summary fallback
            income = context_data.get("monthly_income", 0)
            commitments = context_data.get("monthly_total_commitments", 0)
            avail = context_data.get("available_monthly_capacity", 0)
            score = context_data.get("exposure_score_pct", 0)
            health = context_data.get("financial_health_score", 0)
            label = context_data.get("financial_health_label", "Moderate")
            return (
                f"### 📊 Financial Exposure & Health Summary\n\n"
                f"- **Monthly Inflow / Capacity:** ₹{income:,.2f}\n"
                f"- **Total Monthly Commitments:** ₹{commitments:,.2f}\n"
                f"- **Available Capacity:** ₹{avail:,.2f}\n"
                f"- **Financial Exposure Ratio:** **{score:.2f}%**\n"
                f"- **Health Score:** **{health:.1f}/100** ({label})\n\n"
                f"*Data verified from your authentic FinSight backend state.*"
            )

        if domain == "document_qa" and context_data and "document_text" in context_data:
            doc_text = context_data["document_text"].strip()
            preview = doc_text[:350].replace("\n", " ").strip()
            line_count = len([l for l in doc_text.split("\n") if l.strip()])
            return (
                f"### 📄 Document Summary\n\n"
                f"**Extracted Highlights:**\n"
                f"- **Content Volume:** {len(doc_text):,} characters across {line_count} lines\n"
                f"- **Overview:** {preview}...\n\n"
                f"*(Derived directly from your uploaded document)*"
            )

        if intent == "greeting" or (context_data and context_data.get("is_greeting")):
            return (
                "Hello! I am your FinSight AI Assistant. How can I assist you today? "
                "You can ask about your financial exposure, recurring commitments, "
                "cash flow forecasts, or explore financial and programming concepts."
            )

        if intent == "platform_overview" or (context_data and context_data.get("topic") == "platform_overview"):
            return (
                "### 🌐 What FinSight Does\n\n"
                "**FinSight** is an AI-powered **Financial Exposure Intelligence System** designed to give you predictive visibility and active control over your finances before cash flow strains emerge.\n\n"
                "#### 🔑 Major Features & Intelligence Modules\n"
                "1. **Unified Recurring Commitment Engine:** Consolidates all fixed monthly obligations—including EMIs, personal loans, utility bills, and subscriptions—tracking renewal cycles and true contractual liabilities.\n"
                "2. **Financial Exposure Analytics:** Measures what proportion of your safe financial capacity is locked into non-negotiable commitments, classifying your risk into transparent tiers (Low, Moderate, High, Critical).\n"
                "3. **30-Day Cash Flow Forecasting (Model 1):** Predicts expected payroll inflows, committed expenses, and discretionary spending buffers so you know your exact end-of-month net position.\n"
                "4. **Subscription Usage Intelligence (Model 3):** Identifies underutilized or duplicate services (such as Netflix or YouTube Premium) and provides instant What-If cancellation simulations showing annual savings.\n"
                "5. **Shortfall Prediction & Early Warning (Model 4):** Employs machine learning decision trees to alert you weeks in advance if your account is on trajectory for a liquidity deficit.\n"
                "6. **Goal Feasibility (Digital Twin):** Simulates ambitious savings targets against your forecasted cash flows to determine whether they are realistically achievable without financial stress.\n\n"
                "💡 *How You Benefit:* Rather than just displaying backward-looking spending history, FinSight actively safeguards your liquidity and helps you make proactive, risk-aware financial decisions."
            )

        if domain == "platform_docs":
            low_msg = clean_msg.lower()
            if (
                "exposure" in low_msg
                or "exposur" in low_msg
                or (context_data and context_data.get("concept") == "financial_exposure")
            ):
                return (
                    "### 📊 How Financial Exposure Is Calculated\n\n"
                    "**Financial Exposure** measures the percentage of your sustainable monthly financial capacity that is already claimed by non-negotiable, recurring commitments.\n\n"
                    "#### 1. Core Mathematical Formula\n"
                    "FinSight derives your exposure score by evaluating your committed contractual outflows against your sustainable capacity:\n\n"
                    "$$\\text{Exposure Score (\\%)} = \\left( \\frac{\\text{Total Monthly Commitments}}{\\text{Monthly Financial Capacity}} \\right) \\times 100$$\n\n"
                    "#### 2. Components Defined\n"
                    "- **Total Monthly Commitments:** Sum of all active EMIs, loans, utility bills, subscriptions, and verified contractual obligations.\n"
                    "- **Monthly Financial Capacity:** The maximum safe allocation for fixed commitments, defined as **50% of your average net monthly income** under standard balanced budgeting.\n\n"
                    "#### 3. Standard Risk Bands\n"
                    "- **Low (< 40%):** Strong flexibility; safe buffer against income shocks.\n"
                    "- **Moderate (40% – 60%):** Balanced obligations; manageable cashflow.\n"
                    "- **High (60% – 80%):** Elevated strain; vulnerable to missed payments during emergencies.\n"
                    "- **Critical (> 80%):** Severe debt burden; restructuring or cancellation advised.\n\n"
                    "💡 *Takeaway: Keeping your exposure ratio under 50% guarantees you retain ample room for emergency savings and discretionary living.*"
                )

            if "cash flow" in low_msg or "cashflow" in low_msg or "forecast" in low_msg:
                return (
                    "### 📈 Cash Flow Forecasting Methodology (Model 1)\n\n"
                    "FinSight uses a supervised **Ridge Regression & XGBoost** ensemble (Model 1) to forecast cash flows 30 days ahead:\n\n"
                    "- **Expected Income:** Modeled from historical payroll, salary, and recurring inflows.\n"
                    "- **Committed Expenses:** Aggregated by the Unified Commitment Engine.\n"
                    "- **Variable Expenses:** Forecasted across discretionary categories using rolling averages.\n"
                    "- **Expected Net Cash:** `Expected Income - (Committed + Variable Expenses)`."
                )

            if "shortfall" in low_msg:
                return (
                    "### 🛡️ Financial Shortfall Prediction Methodology (Model 4)\n\n"
                    "FinSight uses **Model 4 (Gradient Boosted Decision Trees)** to predict end-of-month cash deficit risk:\n\n"
                    "- **Cash Buffer Analysis:** Compares projected net cashflow against minimum safety thresholds.\n"
                    "- **Expense Acceleration:** Detects anomalous spikes in discretionary categories.\n"
                    "- **Classification:** Outputs a binary risk label (`LIKELY_SHORTFALL` vs `UNLIKELY_SHORTFALL`) with probability confidence."
                )

            # General documentation conceptual summary
            if context_data and "matches" in context_data:
                chunks = context_data["matches"]
                first = chunks[0] if chunks else None
                if first:
                    clean_content = first.get("content", "").replace("GET /", "Endpoint: /").strip()
                    return (
                        f"### 📖 {first.get('section', 'FinSight Architecture')}\n\n"
                        f"{clean_content}\n\n"
                        f"*(Reference: `{first.get('source', 'Documentation')}`)*"
                    )

        if domain == "general_ai":
            low_msg = clean_msg.lower()
            if "reverse" in low_msg and "string" in low_msg:
                return (
                    "### 🐍 Python String Reversal\n\n"
                    "In Python, the most idiomatic, efficient, and clean way to reverse a string is using slice notation with step `-1`:\n\n"
                    "```python\n"
                    "def reverse_string(text: str) -> str:\n"
                    "    \"\"\"Reverses the input string using slice syntax.\"\"\"\n"
                    "    return text[::-1]\n"
                    "\n"
                    "# Example:\n"
                    "# print(reverse_string(\"FinSight\"))  # Output: \"thgiSniF\"\n"
                    "```\n\n"
                    "#### Alternative with `reversed()`:\n"
                    "```python\n"
                    "def reverse_string_builtin(text: str) -> str:\n"
                    "    return \"\".join(reversed(text))\n"
                    "```\n\n"
                    "Both methods have $\\mathcal{O}(n)$ time complexity and $\\mathcal{O}(n)$ space complexity."
                )

            if "big-o" in low_msg or "big o" in low_msg or "complexity" in low_msg:
                return (
                    "### ⏱️ Big-O Notation Explained\n\n"
                    "**Big-O notation** describes the upper bound of an algorithm's runtime or space complexity as input size ($n$) scales towards infinity.\n\n"
                    "#### Primary Complexity Classes:\n"
                    "- $\\mathcal{O}(1)$ — **Constant Time:** Direct hash map/dictionary lookup regardless of size.\n"
                    "- $\\mathcal{O}(\\log n)$ — **Logarithmic Time:** Efficient dividing search, such as binary search.\n"
                    "- $\\mathcal{O}(n)$ — **Linear Time:** Single iteration across a list of items.\n"
                    "- $\\mathcal{O}(n \\log n)$ — **Linearithmic Time:** Optimal comparison sorting (e.g., Merge Sort, Timsort).\n"
                    "- $\\mathcal{O}(n^2)$ — **Quadratic Time:** Nested loops inspecting element pairs.\n\n"
                    "#### Example Comparison:\n"
                    "```python\n"
                    "# O(1) Constant time\n"
                    "def get_first_item(items: list):\n"
                    "    return items[0] if items else None\n\n"
                    "# O(n) Linear time\n"
                    "def calculate_total(items: list) -> float:\n"
                    "    total = 0.0\n"
                    "    for x in items:\n"
                    "        total += x\n"
                    "    return total\n"
                    "```"
                )

            if any(k in low_msg for k in ["python", "code", "function", "algorithm", "debug", "sql"]):
                return (
                    f"### 💻 Technical Assistant Response\n\n"
                    f"Here is a structured explanation for your query:\n\n"
                    f"```python\n"
                    f"# Solution / Implementation structure for: {clean_msg[:40]}\n"
                    f"def solve():\n"
                    f"    pass\n"
                    f"```\n\n"
                    f"Please specify any additional constraints or sample inputs if you need further optimization."
                )

            return (
                "### ℹ️ Offline Assistant Notice\n\n"
                "The external AI language model is temporarily unavailable due to upstream API rate limits. "
                "I am operating in deterministic mode and can provide verified answers on:\n\n"
                "- **FinSight Financial Intelligence:** System features, exposure calculation formulas, Model 1 cash flows, and Model 4 shortfall predictions.\n"
                "- **Your Authenticated Profile:** Your exposure ratio, recurring commitments, spending summary, and savings goal feasibility.\n"
                "- **Programming & Computer Science:** Big-O complexity, data structures, and Python implementations.\n\n"
                "Please feel free to ask a question on any of these topics!"
            )

        return (
            "FinSight AI Assistant is ready. You can ask conceptual questions about financial metrics, "
            "request code examples and debugging help, or query your authenticated personal financial data."
        )

    # ─────────────────────────────────────────────────────────────
    # Conversation Persistence Management
    # ─────────────────────────────────────────────────────────────

    def list_conversations(self, user_id: str, db_session: Session) -> list[ConversationResponse]:
        """Lists active conversations for the authenticated user."""
        convs = (
            db_session.query(Conversation)
            .filter(Conversation.user_id == user_id, Conversation.is_archived.is_(False))
            .order_by(Conversation.updated_at.desc())
            .all()
        )
        results: list[ConversationResponse] = []
        for c in convs:
            msg_count = len(c.messages)
            last_msg = c.messages[-1].text if c.messages else "New conversation"
            preview = last_msg[:60].replace("\n", " ").strip()
            results.append(
                ConversationResponse(
                    id=c.id,
                    title=c.title,
                    created_at=c.created_at.isoformat(),
                    updated_at=c.updated_at.isoformat(),
                    message_count=msg_count,
                    preview=preview,
                )
            )
        return results

    def create_conversation(
        self, user_id: str, title: str | None, db_session: Session
    ) -> ConversationResponse:
        """Creates a new conversation record."""
        now_dt = datetime.now(timezone.utc)
        conv = Conversation(
            id=generate_conv_id(),
            user_id=user_id,
            title=title.strip() if title and title.strip() else "New Conversation",
            created_at=now_dt,
            updated_at=now_dt,
        )
        db_session.add(conv)
        db_session.commit()
        db_session.refresh(conv)
        return ConversationResponse(
            id=conv.id,
            title=conv.title,
            created_at=conv.created_at.isoformat(),
            updated_at=conv.updated_at.isoformat(),
            message_count=0,
            preview="Ask about code or personal finances...",
        )

    def get_conversation_detail(
        self, user_id: str, conversation_id: str, db_session: Session
    ) -> ConversationDetailResponse | None:
        """Fetches full conversation message history with tenant isolation."""
        conv = (
            db_session.query(Conversation)
            .filter(Conversation.id == conversation_id, Conversation.user_id == user_id)
            .first()
        )
        if not conv:
            return None

        msgs: list[ConversationMessageResponse] = [
            ConversationMessageResponse(
                id=m.id,
                conversation_id=m.conversation_id,
                sender=m.sender,
                role=m.sender,
                text=m.text,
                content=m.text,
                intent=m.intent,
                tool_calls=m.tool_calls or [],
                metadata=m.metadata_payload or {},
                created_at=m.created_at.isoformat(),
            )
            for m in conv.messages
        ]

        return ConversationDetailResponse(
            id=conv.id,
            title=conv.title,
            created_at=conv.created_at.isoformat(),
            updated_at=conv.updated_at.isoformat(),
            messages=msgs,
        )

    def delete_conversation(self, user_id: str, conversation_id: str, db_session: Session) -> bool:
        """Permanently deletes a conversation owned by the authenticated user."""
        conv = (
            db_session.query(Conversation)
            .filter(Conversation.id == conversation_id, Conversation.user_id == user_id)
            .first()
        )
        if not conv:
            return False
        db_session.delete(conv)
        db_session.commit()
        return True

    def update_conversation_title(
        self, user_id: str, conversation_id: str, title: str, db_session: Session
    ) -> ConversationResponse | None:
        """Updates the title of an active conversation with tenant isolation."""
        conv = (
            db_session.query(Conversation)
            .filter(Conversation.id == conversation_id, Conversation.user_id == user_id)
            .first()
        )
        if not conv:
            return None
        clean_title = title.strip()[:200] or "Conversation"
        conv.title = clean_title
        conv.updated_at = datetime.now(timezone.utc)
        db_session.commit()
        last_msg = conv.messages[-1].text if conv.messages else ""
        return ConversationResponse(
            id=conv.id,
            title=conv.title,
            created_at=conv.created_at.isoformat(),
            updated_at=conv.updated_at.isoformat(),
            message_count=len(conv.messages),
            preview=last_msg[:60].replace("\n", " ").strip(),
        )

    # ─────────────────────────────────────────────────────────────
    # Legacy Phase 10 Compatibility Methods
    # ─────────────────────────────────────────────────────────────

    def _build_financial_snapshot(self, user_id: str) -> FinancialSnapshot:
        if self._exposure_service is None:
            raise RuntimeError("Copilot requires an exposure service")

        exposure_intel = self._exposure_service.get_exposure_intelligence(user_id)
        status = exposure_intel.current_financial_status
        health = exposure_intel.financial_health
        breakdown = exposure_intel.commitment_breakdown

        subs: list[dict[str, Any]] = []
        emis: list[dict[str, Any]] = []
        bnpls: list[dict[str, Any]] = []

        def largest_item(bucket: Any) -> dict[str, Any] | None:
            item = bucket.largest_commitment if bucket else None
            if item is None:
                return None
            return {
                "id": item.commitment_name,
                "name": item.commitment_name,
                "monthly_amount": item.monthly_amount,
            }

        if breakdown:
            if item := largest_item(breakdown.subscriptions):
                subs.append({**item, "monthly_cost": item["monthly_amount"]})
            if item := largest_item(breakdown.emis):
                emis.append({**item, "monthly_emi": item["monthly_amount"]})
            if item := largest_item(breakdown.bnpl):
                bnpls.append({**item, "monthly_installment": item["monthly_amount"]})

        return FinancialSnapshot(
            user_id=user_id,
            monthly_income=status.monthly_financial_capacity,
            monthly_commitments=status.monthly_total_commitments,
            exposure_score=status.exposure_score,
            financial_health_score=health.financial_health_score,
            financial_health_status=health.financial_health_label,
            active_subscriptions_count=breakdown.subscriptions.active_commitments if breakdown else 0,
            active_emis_count=breakdown.emis.active_commitments if breakdown else 0,
            active_bnpl_count=breakdown.bnpl.active_commitments if breakdown else 0,
            monthly_savings=max(0.0, status.available_monthly_capacity),
            subscriptions=subs,
            emis=emis,
            bnpl_items=bnpls,
            metadata={"user_id": user_id},
        )

    def query_copilot(
        self,
        user_id: str,
        question: str,
        scenario_parameters: dict[str, Any] | None = None,
    ) -> CopilotResponse:
        snapshot = self._build_financial_snapshot(user_id)
        match = self._intent_detector.detect_intent(question)
        route = self._intent_router.route(match)

        comparison = None
        if route.requires_simulation or scenario_parameters:
            twin = self._twin_engine.create_twin(snapshot)
            stype = ScenarioType.CANCEL_SUBSCRIPTION
            params = dict(scenario_parameters or {})

            if "cancel" in question.lower() or "sub" in question.lower():
                stype = ScenarioType.CANCEL_SUBSCRIPTION
                if "subscription_id" not in params and "name" not in params and snapshot.subscriptions:
                    params["subscription_id"] = snapshot.subscriptions[0].get("id", "sub_netflix")
            elif "salary" in question.lower() or "income" in question.lower():
                stype = ScenarioType.SALARY_INCREASE
                if "percentage" not in params and "amount" not in params:
                    params["percentage"] = 15.0
            elif "emi" in question.lower() or "loan" in question.lower():
                stype = ScenarioType.CLOSE_EMI
                if "emi_id" not in params and "name" not in params and snapshot.emis:
                    params["emi_id"] = snapshot.emis[0].get("id", "emi_phone")

            scenario = Scenario(scenario_type=stype, parameters=params, description=question)
            scenario_res = self._scenario_builder.apply_scenario(twin, scenario)

            if scenario_res.success and scenario_res.modified_twin:
                comparison = self._comparison_engine.compare(twin, scenario_res.modified_twin)

        context = DecisionContext(
            financial_snapshot=snapshot,
            comparison_result=comparison,
            intent_route=route,
            metadata={"user_id": user_id, "question": question},
        )
        decision_result = self._decision_engine.evaluate_decision(context)
        opportunity_feed = self._opportunity_engine.generate_opportunities(snapshot, decision_result)
        formatted_dict = self._response_generator.generate_response(
            decision_result=decision_result,
            comparison=comparison,
            opportunity_feed=opportunity_feed,
        )
        if self._llm_provider is not None:
            llm_context = {
                "intent": formatted_dict["intent"],
                "recommendation": formatted_dict["recommendation"],
                "confidence": formatted_dict["confidence"],
                "supporting_factors": formatted_dict["supporting_factors"],
                "financial_snapshot": {
                    "monthly_income": snapshot.monthly_income,
                    "monthly_commitments": snapshot.monthly_commitments,
                    "exposure_score": snapshot.exposure_score,
                    "financial_health_score": snapshot.financial_health_score,
                    "financial_health_status": snapshot.financial_health_status,
                    "monthly_savings": snapshot.monthly_savings,
                },
            }
            explanation = self._llm_provider.generate_explanation(question, llm_context)
            if explanation:
                provider_name = getattr(
                    self._llm_provider,
                    "last_provider",
                    getattr(self._llm_provider, "provider_name", "llm"),
                )
                formatted_dict["summary"] = explanation
                formatted_dict["metadata"] = {
                    **formatted_dict["metadata"],
                    "generated_by": provider_name,
                    "llm_fallback": False,
                }
            else:
                formatted_dict["metadata"] = {
                    **formatted_dict["metadata"],
                    "generated_by": "deterministic_fallback",
                    "llm_fallback": True,
                }

        return CopilotResponse(**formatted_dict)

    def get_copilot_suggestions(self, user_id: str) -> CopilotSuggestionsResponse:
        snapshot = self._build_financial_snapshot(user_id)
        dna = self._dna_engine.generate_dna(snapshot)
        context = DecisionContext(
            financial_snapshot=snapshot,
            intent_route=None,
            metadata={"user_id": user_id, "mode": "proactive_suggestions"},
        )
        decision_result = self._decision_engine.evaluate_decision(context)
        feed = self._opportunity_engine.generate_opportunities(snapshot, decision_result, dna)

        opp_items: list[CopilotOpportunityItem] = [
            CopilotOpportunityItem(
                opportunity_id=o.opportunity_id,
                title=o.title,
                priority=o.priority.value,
                description=o.description,
                expected_benefit=o.expected_benefit,
                estimated_monthly_savings=o.estimated_monthly_savings,
            )
            for o in feed.opportunities
        ]

        summary = (
            f"Proactive financial suggestions for {user_id} ({dna.primary_archetype.value.replace('_', ' ').title()}): "
            f"Found {len(opp_items)} high-value financial actions."
        )

        return CopilotSuggestionsResponse(
            user_id=user_id,
            primary_archetype=dna.primary_archetype.value,
            opportunities=opp_items,
            summary=summary,
            generated_at=feed.generated_at,
        )


def get_copilot_service(
    exposure_service: ExposureService = Depends(get_exposure_service),
    settings: Any = Depends(get_settings),
) -> CopilotService:
    """FastAPI Dependency Provider for CopilotService."""
    dataset_service = get_dataset_service()
    if not isinstance(exposure_service, ExposureService):
        exposure_service = get_exposure_service(dataset_service)
    if not hasattr(settings, "copilot_llm_enabled") or hasattr(settings, "dependency"):
        settings = get_settings()
    return CopilotService(
        exposure_service=exposure_service,
        llm_provider=build_llm_provider(settings),
        dataset_service=dataset_service,
    )
