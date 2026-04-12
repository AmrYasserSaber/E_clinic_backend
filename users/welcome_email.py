from __future__ import annotations

from django.conf import settings
from django.template.loader import render_to_string

from messaging.services import send_email
from users.models import User


def send_welcome_email(*, user: User, role: str) -> int:
    base: str = (settings.FRONTEND_BASE_URL or "").strip()
    login_url: str | None = f"{base.rstrip('/')}/auth/login" if base else None
    context: dict[str, object] = {
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "role": role,
        "is_approved": user.is_approved,
        "login_url": login_url,
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
