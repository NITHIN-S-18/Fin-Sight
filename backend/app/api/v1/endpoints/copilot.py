from __future__ import annotations

from typing import Any, Generator
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.copilot.copilot_service import CopilotService, get_copilot_service
from app.copilot.tools import parse_and_sanitize_document
from app.core.security import get_current_financial_user, require_financial_user
from app.database.connection import SessionLocal
from app.database.models.user import User
from app.services.dataset_service import DatasetService, get_dataset_service
from app.schemas.copilot import (
    AssistantChatRequest,
    AssistantChatResponse,
    ConversationDetailResponse,
    ConversationResponse,
    CopilotQueryRequest,
    CopilotResponse,
    CopilotSuggestionsResponse,
    CreateConversationRequest,
)

router = APIRouter(prefix="/copilot", tags=["Copilot"])


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


# ─────────────────────────────────────────────────────────────
# Option C: Assistant Chat & Conversation Persistence Routes
# ─────────────────────────────────────────────────────────────

@router.post(
    "/chat",
    response_model=AssistantChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Chat with FinSight General-Purpose AI and Financial Assistant",
    description="Processes multi-turn conversations across General AI (programming, CS, writing), Personal Financial Intelligence (FinSight ground truth), and RAG documentation.",
)
def chat_with_assistant(
    request: AssistantChatRequest,
    current_user: User = Depends(get_current_financial_user),
    copilot_service: CopilotService = Depends(get_copilot_service),
    db: Session = Depends(get_db),
) -> AssistantChatResponse:
    if not request.message or not request.message.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message cannot be empty",
        )
    return copilot_service.chat(
        user_id=current_user.user_id,
        message=request.message,
        conversation_id=request.conversation_id,
        document_context=request.document_context,
        db_session=db,
    )


@router.get(
    "/conversations",
    response_model=list[ConversationResponse],
    status_code=status.HTTP_200_OK,
    summary="List Authenticated User's Conversations",
)
def list_conversations(
    current_user: User = Depends(get_current_financial_user),
    copilot_service: CopilotService = Depends(get_copilot_service),
    db: Session = Depends(get_db),
) -> list[ConversationResponse]:
    return copilot_service.list_conversations(user_id=current_user.user_id, db_session=db)


@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create New Conversation",
)
def create_conversation(
    request: CreateConversationRequest = CreateConversationRequest(),
    current_user: User = Depends(get_current_financial_user),
    copilot_service: CopilotService = Depends(get_copilot_service),
    db: Session = Depends(get_db),
) -> ConversationResponse:
    return copilot_service.create_conversation(
        user_id=current_user.user_id,
        title=request.title,
        db_session=db,
    )


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Conversation Messages History",
)
def get_conversation_detail(
    conversation_id: str,
    current_user: User = Depends(get_current_financial_user),
    copilot_service: CopilotService = Depends(get_copilot_service),
    db: Session = Depends(get_db),
) -> ConversationDetailResponse:
    detail = copilot_service.get_conversation_detail(
        user_id=current_user.user_id,
        conversation_id=conversation_id,
        db_session=db,
    )
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or unauthorized",
        )
    return detail


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete Conversation",
)
def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_financial_user),
    copilot_service: CopilotService = Depends(get_copilot_service),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    deleted = copilot_service.delete_conversation(
        user_id=current_user.user_id,
        conversation_id=conversation_id,
        db_session=db,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or unauthorized",
        )
    return {"success": True, "deleted_id": conversation_id}


@router.patch(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Conversation Title",
)
def update_conversation(
    conversation_id: str,
    request: CreateConversationRequest,
    current_user: User = Depends(get_current_financial_user),
    copilot_service: CopilotService = Depends(get_copilot_service),
    db: Session = Depends(get_db),
) -> ConversationResponse:
    updated = copilot_service.update_conversation_title(
        user_id=current_user.user_id,
        conversation_id=conversation_id,
        title=request.title or "New Conversation",
        db_session=db,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or unauthorized",
        )
    return updated


@router.post(
    "/documents/analyze",
    status_code=status.HTTP_200_OK,
    summary="Safely Analyze Uploaded Document",
)
async def analyze_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_financial_user),
) -> dict[str, Any]:
    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Uploaded file exceeds maximum allowed size of 5 MB",
        )
    try:
        sanitized_text = parse_and_sanitize_document(file.filename or "document.txt", contents)
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to process document: {exc}")

    return {
        "filename": file.filename,
        "extracted_text": sanitized_text,
        "document_text": sanitized_text,
        "length": len(sanitized_text),
        "char_count": len(sanitized_text),
    }


# ─────────────────────────────────────────────────────────────
# Legacy Phase 10 Decision Routes
# ─────────────────────────────────────────────────────────────

@router.post(
    "/query",
    response_model=CopilotResponse,
    status_code=status.HTTP_200_OK,
    summary="Query AI Financial Decision Copilot (Legacy)",
    description="Processes natural language financial queries, detects intent, routes execution, runs Digital Twin simulations, and returns structured decision intelligence responses.",
)
def query_copilot(
    request: CopilotQueryRequest,
    current_user: User = Depends(get_current_financial_user),
    dataset_service: DatasetService = Depends(get_dataset_service),
    copilot_service: CopilotService = Depends(get_copilot_service),
) -> CopilotResponse:
    target_user_id = require_financial_user(request.user_id, current_user) if request.user_id else current_user.user_id
    if not dataset_service.get_user_transactions(target_user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload transactions before using Copilot")
    return copilot_service.query_copilot(
        user_id=target_user_id,
        question=request.question,
        scenario_parameters=request.scenario_parameters,
    )


@router.get(
    "/suggestions/{user_id}",
    response_model=CopilotSuggestionsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Proactive Copilot Suggestions & Opportunity Feed",
    description="Generates proactive financial opportunities, savings suggestions, and Behavioral Financial DNA archetype insights for a given user.",
)
def get_copilot_suggestions(
    user_id: str,
    current_user: User = Depends(get_current_financial_user),
    dataset_service: DatasetService = Depends(get_dataset_service),
    copilot_service: CopilotService = Depends(get_copilot_service),
) -> CopilotSuggestionsResponse:
    if not dataset_service.get_user_transactions(current_user.user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload transactions before using Copilot")
    return copilot_service.get_copilot_suggestions(user_id=require_financial_user(user_id, current_user))
