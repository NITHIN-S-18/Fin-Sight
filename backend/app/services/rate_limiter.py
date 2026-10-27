from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Dict, List


class PasswordResetRateLimiter:
    """Sliding-window rate limiter for password reset requests."""

    def __init__(
        self,
        max_requests_per_email: int = 5,
        email_window_seconds: int = 900,  # 15 minutes
        email_cooldown_seconds: int = 30,  # 30 seconds cooldown between successive requests
        max_requests_per_ip: int = 15,
        ip_window_seconds: int = 900,  # 15 minutes
    ) -> None:
        self.max_requests_per_email = max_requests_per_email
        self.email_window_seconds = email_window_seconds
        self.email_cooldown_seconds = email_cooldown_seconds
        self.max_requests_per_ip = max_requests_per_ip
        self.ip_window_seconds = ip_window_seconds

        self._lock = threading.Lock()
        self._email_requests: Dict[str, List[float]] = defaultdict(list)
        self._ip_requests: Dict[str, List[float]] = defaultdict(list)

    def check_and_record(self, email: str, ip: str) -> tuple[bool, str | None]:
        """Check if request is allowed; if allowed, records the timestamp and returns (True, None).

        If disallowed, returns (False, error_message).
        """
        now = time.time()
        normalized_email = email.strip().lower()
        client_ip = ip.strip()

        with self._lock:
            # Clean expired timestamps for email
            email_history = [
                t for t in self._email_requests[normalized_email]
                if now - t < self.email_window_seconds
            ]
            self._email_requests[normalized_email] = email_history

            # Check cooldown between successive requests
            if email_history and (now - email_history[-1]) < self.email_cooldown_seconds:
                remaining = int(self.email_cooldown_seconds - (now - email_history[-1]))
                return False, f"Please wait {max(1, remaining)} seconds before requesting another reset email."

            # Check max requests per email
            if len(email_history) >= self.max_requests_per_email:
                return False, "Too many password reset requests for this email. Please try again in 15 minutes."

            # Clean expired timestamps for IP
            if client_ip:
                ip_history = [
                    t for t in self._ip_requests[client_ip]
                    if now - t < self.ip_window_seconds
                ]
                self._ip_requests[client_ip] = ip_history

                # Check max requests per IP
                if len(ip_history) >= self.max_requests_per_ip:
                    return False, "Too many password reset requests from this network. Please try again later."

            # Record
            self._email_requests[normalized_email].append(now)
            if client_ip:
                self._ip_requests[client_ip].append(now)

            return True, None

    def reset(self) -> None:
        """Clear all rate limit records (primarily for testing)."""
        with self._lock:
            self._email_requests.clear()
            self._ip_requests.clear()


# Global singleton instance
password_reset_rate_limiter = PasswordResetRateLimiter()
