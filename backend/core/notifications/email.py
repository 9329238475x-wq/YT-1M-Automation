from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


def send_upload_success_email(*, video_title: str, youtube_url: str, published_at: str | None = None) -> None:
    """Send a success notification after a confirmed YouTube upload.

    Credentials are read only from environment variables; never commit them to Git.
    Required: YT1M_GMAIL_USER, YT1M_GMAIL_APP_PASSWORD, YT1M_NOTIFICATION_EMAIL.
    """
    sender = os.getenv("YT1M_GMAIL_USER")
    app_password = os.getenv("YT1M_GMAIL_APP_PASSWORD")
    recipient = os.getenv("YT1M_NOTIFICATION_EMAIL")
    if not all((sender, app_password, recipient)):
        raise RuntimeError("Email notification is not configured. Set YT1M_GMAIL_USER, YT1M_GMAIL_APP_PASSWORD and YT1M_NOTIFICATION_EMAIL.")

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = f"YouTube upload successful: {video_title}"
    when = published_at or "Scheduled/published time not provided"
    msg.set_content(f"Your YT-1M Automation job completed successfully.\n\nTitle: {video_title}\nYouTube: {youtube_url}\nTime: {when}\n")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(sender, app_password)
        smtp.send_message(msg)
