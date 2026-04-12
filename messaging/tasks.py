from __future__ import annotations

from django.conf import settings
from django.core.mail import send_mail
from procrastinate import retry
from procrastinate.contrib.django import app


@app.task(
    queue="mail",
    retry=retry.RetryStrategy(max_attempts=4, wait=5, linear_wait=15),
)
def enqueue_send_email(
    *,
    subject: str,
    body: str,
    recipient_list: list[str],
    html_body: str | None = None,
) -> None:
    from_email: str = settings.DEFAULT_FROM_EMAIL
    send_mail(
        subject=subject,
        message=body,
        from_email=from_email,
        recipient_list=recipient_list,
        fail_silently=False,
        html_message=html_body if html_body else None,
    )
