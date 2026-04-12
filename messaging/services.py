from __future__ import annotations

from messaging.tasks import enqueue_send_email

def send_email(
    *,
    subject: str,
    body: str,
    recipient_list: list[str],
    html_body: str | None = None,
) -> int:
    return enqueue_send_email.defer(
        subject=subject,
        body=body,
        recipient_list=recipient_list,
        html_body=html_body,
    )
