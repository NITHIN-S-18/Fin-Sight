from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class CopilotQueryRequest(BaseModel):
    user_id: str | None = Field(default=None, description="Deprecated target identifier; the JWT identity is authoritative")
    question: str = Field(..., min_length=1, description="Natural language financial question or query")
    scenario_parameters: dict[str, Any] | None = Field(
        default=None, description="Optional parameters for simulation scenarios"
    )


class CopilotResponse(BaseModel):
    intent: str = Field(..., description="Detected financial intent")
    recommendation: str = Field(..., description="Primary recommendation title")
    confidence: float = Field(..., description="Decision confidence score (0-100)")
    confidence_level: str = Field(..., description="Decision confidence level")
    summary: str = Field(..., description="Natural language response summary")
    supporting_factors: list[str] = Field(
        default_factory=list, description="Supporting financial factors"
    )
    simulation_available: bool = Field(
        ..., description="Indicates if Digital Twin simulation is available"
    )
    suggested_next_action: str = Field(..., description="Suggested next action for user")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Execution and routing metadata"
    )


class CopilotOpportunityItem(BaseModel):
    opportunity_id: str = Field(..., description="Unique opportunity identifier")
    title: str = Field(..., description="Opportunity title")
    priority: str = Field(..., description="Priority level (critical, high, medium, low)")
    description: str = Field(..., description="Opportunity description")
    expected_benefit: str = Field(..., description="Expected financial benefit")
    estimated_monthly_savings: float = Field(
        default=0.0, description="Estimated monthly savings"
    )


class CopilotSuggestionsResponse(BaseModel):
    user_id: str = Field(..., description="User identifier")
    primary_archetype: str = Field(..., description="Behavioral Financial DNA archetype")
    opportunities: list[CopilotOpportunityItem] = Field(
        default_factory=list, description="Proactive opportunity feed"
    )
    summary: str = Field(..., description="Proactive suggestions summary")
    generated_at: str = Field(..., description="Timestamp of suggestion generation")


# --- Option C General-Purpose + Personal Financial Assistant Schemas ---

class CreateConversationRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200, description="Optional custom conversation title")


class ConversationMessageResponse(BaseModel):
    id: str
    conversation_id: str
    sender: str  # "user" | "assistant"
    role: str = "user"  # alias for sender
    text: str
    content: str = ""  # alias for text
    intent: str | None = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class ConversationResponse(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0
    preview: str | None = None


class ConversationDetailResponse(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    messages: list[ConversationMessageResponse] = Field(default_factory=list)


class AssistantChatRequest(BaseModel):
    conversation_id: str | None = Field(default=None, description="Active conversation identifier")
    message: str = Field(..., min_length=1, description="User prompt or question")
    document_context: str | None = Field(default=None, description="Optional attached document text")


class AssistantChatResponse(BaseModel):
    conversation_id: str
    message_id: str
    text: str
    response: str = ""  # alias for text
    intent: str = "general_ai"
    domain: str = "general_ai"  # "general_ai" | "personal_finance" | "platform_docs" | "document_qa"
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    factors: list[str] = Field(default_factory=list)
    recommendation: str | None = None
    action: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
