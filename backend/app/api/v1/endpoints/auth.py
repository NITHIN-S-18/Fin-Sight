from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse

from app.core.config import Settings, get_settings
from app.core.security import get_current_auth_user, get_current_financial_user
from app.database.models.auth_user import AuthUser
from app.database.models.user import User
from app.schemas.auth import (
    AuthUserResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    PasswordChangeRequest,
    ProfileUpdateRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    VerifyOtpRequest,
    VerifyOtpResponse,
)
from app.services.auth_service import AuthService, get_auth_service
from app.services.data_export_service import DataExportService, get_data_export_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=AuthUserResponse, status_code=status.HTTP_201_CREATED, summary="Register an auth account")
def register(request: RegisterRequest, service: AuthService = Depends(get_auth_service)) -> AuthUserResponse:
    return service.register(request)


@router.post("/login", response_model=TokenResponse, summary="Login and receive a JWT")
def login(
    request: LoginRequest,
    settings: Settings = Depends(get_settings),
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    return service.login(request, settings)


@router.post("/forgot-password", response_model=MessageResponse, summary="Request a password reset link")
def forgot_password(
    request_data: ForgotPasswordRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    client_ip = request.client.host if request.client else ""
    return service.request_password_reset(request_data, client_ip=client_ip)


@router.post("/verify-otp", response_model=VerifyOtpResponse, summary="Verify 6-digit OTP and get password reset token")
def verify_otp(
    request_data: VerifyOtpRequest,
    service: AuthService = Depends(get_auth_service),
) -> VerifyOtpResponse:
    return service.verify_otp(request_data)


@router.post("/resend-otp", response_model=MessageResponse, summary="Resend 6-digit password reset OTP")
def resend_otp(
    request_data: ForgotPasswordRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    client_ip = request.client.host if request.client else ""
    return service.resend_otp(request_data, client_ip=client_ip)


@router.post("/reset-password", response_model=MessageResponse, summary="Reset password using a reset token")
def reset_password(
    request_data: ResetPasswordRequest,
    service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    return service.reset_password(request_data)


@router.get("/me", response_model=AuthUserResponse, summary="Get the authenticated account")
def me(user: AuthUser = Depends(get_current_auth_user)) -> AuthUserResponse:
    return AuthUserResponse.model_validate(user)


@router.patch("/me", response_model=AuthUserResponse, summary="Update the authenticated profile")
def update_me(
    request: ProfileUpdateRequest,
    user: User = Depends(get_current_financial_user),
    service: AuthService = Depends(get_auth_service),
) -> AuthUserResponse:
    return service.update_profile(user, request)


@router.post("/avatar", response_model=AuthUserResponse, summary="Upload profile avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    user: User = Depends(get_current_financial_user),
    service: AuthService = Depends(get_auth_service),
) -> AuthUserResponse:
    return await service.upload_avatar(user, file)


@router.delete("/avatar", response_model=AuthUserResponse, summary="Delete profile avatar")
def delete_avatar(
    user: User = Depends(get_current_financial_user),
    service: AuthService = Depends(get_auth_service),
) -> AuthUserResponse:
    return service.delete_avatar(user)


@router.get("/avatar/{filename}", summary="Get profile avatar file")
def get_avatar(
    filename: str,
    service: AuthService = Depends(get_auth_service),
) -> FileResponse:
    file_path = service.get_avatar_file(filename)
    suffix = file_path.suffix.lower()
    media_type = "image/png" if suffix == ".png" else "image/webp" if suffix == ".webp" else "image/jpeg"
    return FileResponse(file_path, media_type=media_type, headers={"Cache-Control": "public, max-age=86400"})


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT, summary="Change the authenticated password")
def change_password(
    request: PasswordChangeRequest,
    user: User = Depends(get_current_financial_user),
    service: AuthService = Depends(get_auth_service),
) -> None:
    service.change_password(user, request)


@router.get("/export", summary="Export the authenticated user's transactions")
def export_transactions(
    format: str = Query("csv", description="Export format: json, csv, or pdf"),
    user: User = Depends(get_current_financial_user),
    service: DataExportService = Depends(get_data_export_service),
) -> StreamingResponse:
    if format.lower() == "pdf":
        import io
        from datetime import date

        pdf_bytes = service.export_pdf(user.user_id)
        today_str = date.today().isoformat()
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="FinSight_Financial_Report_{today_str}.pdf"'},
        )
    if format.lower() == "json":
        content = service.export_json(user.user_id)
        return StreamingResponse(
            iter([content]),
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="finsight_financial_export.json"'},
        )
    content = service.export_transactions(user.user_id)
    return StreamingResponse(
        iter([content]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="finsight_transactions.csv"'},
    )
