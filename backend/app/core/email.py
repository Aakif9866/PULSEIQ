"""Minimal SMTP email sending — stdlib only (smtplib + email.mime), no new
dependency. Deliberately not a general-purpose email service: PulseIQ has
exactly one email use case today (anomaly alerts), so this stays a single
small function rather than a templating framework.
"""
import smtplib
from email.mime.text import MIMEText

from app.core.config import settings


class EmailNotConfiguredError(Exception):
    """Raised when send_email is called but no SMTP_HOST is set. Callers
    (app.services.monitor_service) catch this the same way they catch any
    other alert-delivery failure — it never corrupts anomaly detection
    state, it only means the anomaly's alert_sent stays False and
    alert_error records why."""


def send_email(*, to: str, subject: str, body_text: str) -> None:
    if not settings.SMTP_HOST or not settings.SMTP_FROM_EMAIL:
        raise EmailNotConfiguredError(
            "SMTP_HOST/SMTP_FROM_EMAIL are not configured; email alerting is disabled."
        )

    message = MIMEText(body_text, "plain", "utf-8")
    message["Subject"] = subject
    message["From"] = settings.SMTP_FROM_EMAIL
    message["To"] = to

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
        if settings.SMTP_USE_TLS:
            server.starttls()
        if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM_EMAIL, [to], message.as_string())
