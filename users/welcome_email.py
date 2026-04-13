from __future__ import annotations

import logging

from django.conf import settings
from django.template.loader import render_to_string

from messaging.services import send_email
from users.models import User

logger = logging.getLogger(__name__)


def _login_url() -> str | None:
    base: str = (settings.FRONTEND_BASE_URL or "").strip()
    return f"{base.rstrip('/')}/auth/login" if base else None


def send_welcome_email(*, user: User, role: str) -> int:
    context: dict[str, object] = {
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "role": role,
        "is_approved": user.is_approved,
        "login_url": _login_url(),
    }
    subject: str = f"Welcome to E-Clinic, {user.first_name}"
    plain_body: str = render_to_string("emails/welcome.txt", context)
    html_body: str = render_to_string("emails/welcome.html", context)
    return send_email(
        subject=subject,
        body=plain_body,
        recipient_list=[user.email],
        html_body=html_body,
    )


def send_profile_updated_email(
    *,
    user: User,
    changes: list[dict[str, str]],
    is_approval: bool = False,
) -> None:
    if not changes and not is_approval:
        return

    if is_approval:
        subject = f"Your E-Clinic account has been approved, {user.first_name}"
    else:
        subject = f"Your E-Clinic profile has been updated, {user.first_name}"

    context: dict[str, object] = {
        "first_name": user.first_name,
        "changes": changes,
        "is_approval": is_approval,
        "login_url": _login_url(),
    }
    plain_body = render_to_string("emails/profile_updated.txt", context)
    html_body = render_to_string("emails/profile_updated.html", context)

    try:
        send_email(
            subject=subject,
            body=plain_body,
            recipient_list=[user.email],
            html_body=html_body,
        )
    except Exception:
        logger.exception("Failed to enqueue profile-updated email for user %s", user.pk)
