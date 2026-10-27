from __future__ import annotations

import logging
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, Optional

import httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger("finsight.email")


class EmailDeliveryError(Exception):
    """Raised when an email cannot be delivered through the configured provider."""
    pass


class EmailService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._last_sent_email: Optional[Dict[str, Any]] = None

    @property
    def last_sent_email(self) -> Optional[Dict[str, Any]]:
        """Available for testing and local development inspection."""
        return self._last_sent_email

    def clear_last_sent_email(self) -> None:
        self._last_sent_email = None

    def send_password_reset_otp(self, recipient_email: str, otp: str) -> None:
        expires_minutes = self.settings.auth_password_reset_otp_expire_minutes
        subject = f"Your FinSight verification code: {otp}"
        plain_text = (
            f"Hello,\n\n"
            f"Your verification code to reset your FinSight password is:\n\n"
            f"  {otp}\n\n"
            f"This code will expire in {expires_minutes} minutes.\n\n"
            f"If you did not request a password reset, you can safely ignore this email. "
            f"Your account remains secure.\n\n"
            f"— The FinSight Security Team"
        )
        html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Your FinSight verification code</title>
</head>
<body style="margin: 0; padding: 0; background-color: #0b1120; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #f1f5f9;">
  <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #0b1120; padding: 40px 20px;">
    <tr>
      <td align="center">
        <table width="100%" max-width="560" border="0" cellspacing="0" cellpadding="0" style="max-width: 560px; background-color: #111a2e; border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 16px; overflow: hidden; box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);">
          <tr>
            <td style="padding: 32px 36px; background: linear-gradient(135deg, rgba(79, 70, 229, 0.2) 0%, rgba(56, 189, 248, 0.1) 100%); border-bottom: 1px solid rgba(255, 255, 255, 0.08);">
              <h1 style="margin: 0; font-size: 24px; font-weight: 700; color: #ffffff; letter-spacing: -0.5px;">
                Fin<span style="color: #6366f1;">Sight</span>
              </h1>
              <p style="margin: 4px 0 0 0; font-size: 11px; font-family: monospace; text-transform: uppercase; letter-spacing: 1.5px; color: #818cf8;">
                Financial Exposure Intelligence
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding: 36px 36px 28px 36px;">
              <h2 style="margin: 0 0 16px 0; font-size: 18px; font-weight: 600; color: #ffffff;">
                Password Reset Verification Code
              </h2>
              <p style="margin: 0 0 24px 0; font-size: 14px; line-height: 1.6; color: #94a3b8;">
                Enter this 6-digit verification code to reset the password for <strong style="color: #cbd5e1;">{recipient_email}</strong>:
              </p>
              <div style="margin: 28px 0; text-align: center;">
                <span style="display: inline-block; padding: 16px 32px; font-size: 32px; font-weight: 700; letter-spacing: 8px; color: #818cf8; background-color: #0c1322; border: 1px solid rgba(99, 102, 241, 0.4); border-radius: 12px; font-family: monospace;">
                  {otp}
                </span>
              </div>
              <p style="margin: 24px 0 0 0; font-size: 12px; line-height: 1.5; color: #64748b;">
                This code is valid for <strong>{expires_minutes} minutes</strong> and can only be used once. Never share this code with anyone.
              </p>
              <div style="margin-top: 24px; padding: 14px 16px; background-color: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.06); border-radius: 8px;">
                <p style="margin: 0; font-size: 12px; color: #94a3b8; line-height: 1.5;">
                  <strong>Didn't request this?</strong> If you did not make this request, you can safely ignore this email. Your current password remains unchanged.
                </p>
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding: 24px 36px; background-color: #0c1322; border-top: 1px solid rgba(255, 255, 255, 0.06); text-align: center;">
              <p style="margin: 0; font-size: 11px; color: #64748b;">
                &copy; FinSight Financial Exposure Intelligence. All rights reserved.
              </p>
              <p style="margin: 6px 0 0 0; font-size: 10px; color: #475569;">
                This is an automated security notification. Do not reply to this email.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""
        self._last_sent_email = {
            "to": recipient_email,
            "subject": subject,
            "otp": otp,
            "plain_text": plain_text,
            "html_content": html_content,
        }

        console_banner = (
            "\n"
            + "=" * 78 + "\n"
            + " [FINSIGHT LOCAL DEV OTP DISPATCH]\n"
            + f" To: {recipient_email}\n"
            + f" Verification Code (OTP): {otp}\n"
            + f" Expires In: {expires_minutes} minutes\n"
            + " Delivery Mode: console (no external email sent)\n"
            + " Note: In local development, enter this 6-digit code in the FinSight UI.\n"
            + "=" * 78 + "\n"
        )

        self._dispatch(recipient_email, subject, plain_text, html_content, console_banner)

    def send_password_reset_email(self, recipient_email: str, reset_token: str) -> None:
        base_url = self.settings.frontend_base_url.rstrip("/")
        reset_link = f"{base_url}/reset-password?token={reset_token}"
        expires_minutes = self.settings.auth_password_reset_token_expire_minutes

        subject = "Reset your FinSight password"
        plain_text = (
            f"Hello,\n\n"
            f"We received a request to reset the password for your FinSight account.\n\n"
            f"To reset your password, visit the following link:\n"
            f"{reset_link}\n\n"
            f"This link will expire in {expires_minutes} minutes.\n\n"
            f"If you did not request this password reset, you can safely ignore this email. "
            f"Your account remains secure and your password will not be changed.\n\n"
            f"— The FinSight Security Team"
        )

        html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Reset your FinSight password</title>
</head>
<body style="margin: 0; padding: 0; background-color: #0b1120; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #f1f5f9;">
  <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #0b1120; padding: 40px 20px;">
    <tr>
      <td align="center">
        <table width="100%" max-width="560" border="0" cellspacing="0" cellpadding="0" style="max-width: 560px; background-color: #111a2e; border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 16px; overflow: hidden; box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);">
          <tr>
            <td style="padding: 32px 36px; background: linear-gradient(135deg, rgba(79, 70, 229, 0.2) 0%, rgba(56, 189, 248, 0.1) 100%); border-bottom: 1px solid rgba(255, 255, 255, 0.08);">
              <h1 style="margin: 0; font-size: 24px; font-weight: 700; color: #ffffff; letter-spacing: -0.5px;">
                Fin<span style="color: #6366f1;">Sight</span>
              </h1>
              <p style="margin: 4px 0 0 0; font-size: 11px; font-family: monospace; text-transform: uppercase; letter-spacing: 1.5px; color: #818cf8;">
                Financial Exposure Intelligence
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding: 36px 36px 28px 36px;">
              <h2 style="margin: 0 0 16px 0; font-size: 18px; font-weight: 600; color: #ffffff;">
                Password Reset Request
              </h2>
              <p style="margin: 0 0 24px 0; font-size: 14px; line-height: 1.6; color: #94a3b8;">
                We received a request to reset the password associated with your account (<strong style="color: #cbd5e1;">{recipient_email}</strong>). Click the secure button below to choose a new password.
              </p>
              <table border="0" cellspacing="0" cellpadding="0" style="margin: 28px 0;">
                <tr>
                  <td align="center" style="border-radius: 10px; background: linear-gradient(135deg, #4f46e5 0%, #6366f1 100%); box-shadow: 0 4px 14px rgba(79, 70, 229, 0.4);">
                    <a href="{reset_link}" target="_blank" style="display: inline-block; padding: 13px 28px; font-size: 14px; font-weight: 600; color: #ffffff; text-decoration: none; border-radius: 10px;">
                      Reset Password
                    </a>
                  </td>
                </tr>
              </table>
              <p style="margin: 24px 0 0 0; font-size: 12px; line-height: 1.5; color: #64748b;">
                This link is valid for <strong>{expires_minutes} minutes</strong> and can only be used once. If it expires, you can request a new one from the FinSight sign-in page.
              </p>
              <div style="margin-top: 24px; padding: 14px 16px; background-color: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.06); border-radius: 8px;">
                <p style="margin: 0; font-size: 12px; color: #94a3b8; line-height: 1.5;">
                  <strong>Didn't request this?</strong> If you did not make this request, please ignore this email. Your current password remains unchanged.
                </p>
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding: 24px 36px; background-color: #0c1322; border-top: 1px solid rgba(255, 255, 255, 0.06); text-align: center;">
              <p style="margin: 0; font-size: 11px; color: #64748b;">
                &copy; FinSight Financial Exposure Intelligence. All rights reserved.
              </p>
              <p style="margin: 6px 0 0 0; font-size: 10px; color: #475569;">
                This is an automated security notification. Do not reply to this email.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""
        self._last_sent_email = {
            "to": recipient_email,
            "subject": subject,
            "reset_link": reset_link,
            "reset_token": reset_token,
            "plain_text": plain_text,
            "html_content": html_content,
        }

        console_banner = (
            "\n"
            + "=" * 78 + "\n"
            + " [FINSIGHT LOCAL DEV EMAIL DISPATCH]\n"
            + f" To: {recipient_email}\n"
            + f" Subject: {subject}\n"
            + f" Reset Link: {reset_link}\n"
            + " Delivery Mode: console (no external email sent)\n"
            + " Note: To deliver real emails, set RESEND_API_KEY or SMTP credentials in backend/.env.\n"
            + "=" * 78 + "\n"
        )

        self._dispatch(recipient_email, subject, plain_text, html_content, console_banner)

    def _dispatch(self, recipient: str, subject: str, text: str, html: str, console_banner: str) -> None:
        provider = (self.settings.email_delivery_provider or "auto").lower().strip()
        is_prod = self.settings.environment.lower() in {"production", "prod"}

        if provider == "resend":
            self._send_via_resend(recipient, subject, text, html)
        elif provider == "smtp":
            self._send_via_smtp(recipient, subject, text, html)
        elif provider == "console":
            if is_prod:
                raise EmailDeliveryError("Console email delivery is forbidden in production environment")
            self._write_console_banner(console_banner, recipient)
        elif provider == "auto":
            if self.settings.resend_api_key:
                self._send_via_resend(recipient, subject, text, html)
            elif self.settings.smtp_host:
                self._send_via_smtp(recipient, subject, text, html)
            elif is_prod:
                raise EmailDeliveryError("No external email provider configured for production environment")
            else:
                self._write_console_banner(console_banner, recipient)
        else:
            if is_prod:
                raise EmailDeliveryError(f"Invalid email_delivery_provider '{provider}' in production")
            logger.warning(
                "Unknown email_delivery_provider '%s', defaulting to console delivery mode for local dev.",
                provider,
            )
            self._write_console_banner(console_banner, recipient)

    def _write_console_banner(self, banner: str, recipient: str) -> None:
        logger.info("Password reset dispatch for %s (Delivery mode: console/dev).", recipient)
        try:
            sys.stderr.write(banner)
            sys.stderr.flush()
        except Exception:
            pass

    def _send_via_resend(self, recipient: str, subject: str, text: str, html: str) -> None:
        if not self.settings.resend_api_key:
            raise EmailDeliveryError("Resend API key is not configured")

        from_email = self.settings.resend_from_email or "onboarding@resend.dev"
        from_name = self.settings.resend_from_name or "FinSight"
        from_header = f"{from_name} <{from_email}>"

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {self.settings.resend_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "from": from_header,
                        "to": [recipient],
                        "subject": subject,
                        "text": text,
                        "html": html,
                    },
                )
            if response.status_code >= 400:
                logger.error("Resend API rejected email: %s - %s", response.status_code, response.text)
                raise EmailDeliveryError(f"Email service provider error: {response.status_code}")
        except httpx.RequestError as exc:
            logger.error("Network error while connecting to Resend: %s", exc)
            raise EmailDeliveryError("Failed to reach email service provider") from exc

    def _send_via_smtp(self, recipient: str, subject: str, text: str, html: str) -> None:
        if not self.settings.smtp_host:
            raise EmailDeliveryError("SMTP host is not configured")

        sender = self.settings.smtp_from_email or "noreply@finsight.app"
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = recipient

        msg.attach(MIMEText(text, "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))

        try:
            with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=10.0) as server:
                if self.settings.smtp_use_tls:
                    server.starttls()
                if self.settings.smtp_username and self.settings.smtp_password:
                    server.login(self.settings.smtp_username, self.settings.smtp_password)
                server.send_message(msg)
        except (smtplib.SMTPException, OSError) as exc:
            logger.error("SMTP delivery failed: %s", exc)
            raise EmailDeliveryError("Failed to deliver email via SMTP") from exc


email_service = EmailService()


def get_email_service() -> EmailService:
    return email_service
