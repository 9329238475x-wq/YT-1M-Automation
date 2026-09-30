from __future__ import annotations

import os
import ssl
import smtplib
import logging
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

logger = logging.getLogger("notifier")

# Load credentials from .md or environment
ROOT = Path(__file__).resolve().parent.parent
MD_FILE = ROOT / ".md"

def _load_credentials() -> tuple[str, str, str]:
    email = os.getenv("DUBSTUDIO_EMAIL", "")
    to_email = os.getenv("DUBSTUDIO_TO_EMAIL", "")
    app_pass = os.getenv("DUBSTUDIO_APP_PASS", "")

    if (not email or not app_pass) and MD_FILE.exists():
        try:
            content = MD_FILE.read_text(encoding="utf-8")
            for line in content.splitlines():
                line = line.strip()
                if "DUBSTUDIO_EMAIL" in line and "=" in line:
                    email = line.split("=", 1)[1].strip().strip('"').strip("'")
                elif "DUBSTUDIO_TO_EMAIL" in line and "=" in line:
                    to_email = line.split("=", 1)[1].strip().strip('"').strip("'")
                elif "DUBSTUDIO_APP_PASS" in line and "=" in line:
                    app_pass = line.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception as exc:
            logger.warning(f"Error reading .md file for credentials: {exc}")

    # Fallbacks from user configuration
    if not email:
        email = "9329238475x@gmail.com"
    if not to_email:
        to_email = email
    if not app_pass:
        app_pass = "ziqkkzjwffqnzrgn"

    return email, app_pass, to_email


def send_upload_success_email(
    channel_name: str,
    channel_id: str,
    video_title: str,
    video_id: str,
    privacy: str = "private",
    duration_display: str = "Full",
    theme_name: str = "Rain Ambience",
    extra_note: str = "",
    recipient_email: Optional[str] = None
) -> bool:
    """
    Sends a formatted notification email to user's Gmail when a video is
    successfully uploaded to YouTube via the automation pipeline.
    """
    sender_email, app_pass, default_recipient = _load_credentials()
    actual_recipient = (recipient_email or "").strip() or default_recipient
    if not sender_email or not app_pass or not actual_recipient:
        logger.error("Cannot send email: Missing Gmail SMTP credentials.")
        return False

    youtube_watch_url = f"https://youtu.be/{video_id}"
    channel_url = f"https://www.youtube.com/channel/{channel_id}"
    now_ist = datetime.now().strftime("%d %b %Y, %I:%M %p")

    channel_display = channel_name.strip() if channel_name else "YouTube Channel"
    subject = f"🎉 {channel_display} - Video Success | {video_title[:45]}"

    # Plain text alternative
    text_content = f"""
{channel_display.upper()} - VIDEO SUCCESS
======================================================
Channel: {channel_display} ({channel_id})
Status: Video Upload Success!

Video Title: {video_title}
Video Link: {youtube_watch_url}
Privacy: {privacy.upper()}
Duration: {duration_display}
Theme: {theme_name}
Timestamp: {now_ist}

Cleanup Notice: All temporary render files and output video files were automatically deleted from the server to save disk space.

View Video: {youtube_watch_url}
Visit Channel: {channel_url}
======================================================
"""

    # High-aesthetic Dark Glassmorphic HTML template
    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>YouTube Upload Notification</title>
  <style>
    body {{
      background-color: #080808;
      color: #ffffff;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      margin: 0;
      padding: 30px 15px;
    }}
    .email-container {{
      max-width: 620px;
      margin: 0 auto;
      background: #111111;
      border: 1px solid #222222;
      border-radius: 16px;
      overflow: hidden;
      box-shadow: 0 16px 48px rgba(0,0,0,0.9);
    }}
    .email-header {{
      background: linear-gradient(135deg, #1f0206 0%, #0d0103 100%);
      border-bottom: 1px solid #2e080f;
      padding: 26px 30px 22px;
      text-align: center;
    }}
    .brand-pill {{
      display: inline-block;
      background: #ff0033;
      color: #ffffff;
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      padding: 4px 12px;
      border-radius: 9999px;
      margin-bottom: 12px;
    }}
    .header-title {{
      margin: 0;
      font-size: 22px;
      font-weight: 800;
      color: #ffffff;
      letter-spacing: -0.02em;
    }}
    .email-body {{
      padding: 32px 30px;
    }}
    .status-alert {{
      background: rgba(16, 185, 129, 0.1);
      border: 1px solid rgba(16, 185, 129, 0.3);
      border-radius: 10px;
      padding: 12px 18px;
      margin-bottom: 24px;
      display: flex;
      align-items: center;
      gap: 12px;
    }}
    .status-text {{
      color: #10b981;
      font-size: 14px;
      font-weight: 700;
    }}
    .info-card {{
      background: #161616;
      border: 1px solid #262626;
      border-radius: 12px;
      padding: 20px;
      margin-bottom: 24px;
    }}
    .field-row {{
      display: flex;
      justify-content: space-between;
      padding: 8px 0;
      border-bottom: 1px solid #202020;
      font-size: 13px;
    }}
    .field-row:last-child {{
      border-bottom: none;
    }}
    .field-key {{
      color: #888888;
      font-weight: 500;
    }}
    .field-val {{
      color: #ffffff;
      font-weight: 700;
      text-align: right;
    }}
    .video-title-box {{
      background: #0a0a0a;
      border: 1px solid #282828;
      border-radius: 10px;
      padding: 16px;
      margin-bottom: 26px;
    }}
    .video-title-label {{
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: #888888;
      margin-bottom: 6px;
      font-weight: 700;
    }}
    .video-title-text {{
      font-size: 15px;
      color: #ffffff;
      font-weight: 700;
      line-height: 1.4;
      margin: 0;
    }}
    .cta-button {{
      display: block;
      background: #ff0033;
      color: #ffffff !important;
      text-decoration: none;
      font-weight: 800;
      font-size: 15px;
      text-align: center;
      padding: 16px 28px;
      border-radius: 10px;
      box-shadow: 0 4px 20px rgba(255, 0, 51, 0.4);
      margin-bottom: 16px;
    }}
    .sec-button {{
      display: block;
      background: #1c1c1c;
      color: #cccccc !important;
      text-decoration: none;
      font-weight: 600;
      font-size: 13px;
      text-align: center;
      padding: 12px 20px;
      border-radius: 10px;
      border: 1px solid #333333;
    }}
    .cleanup-box {{
      margin-top: 24px;
      padding: 12px 16px;
      background: #0c0c0c;
      border-radius: 8px;
      border-left: 3px solid #3b82f6;
      font-size: 12px;
      color: #999999;
      line-height: 1.5;
    }}
    .email-footer {{
      padding: 20px 30px;
      border-top: 1px solid #202020;
      text-align: center;
      font-size: 11px;
      color: #555555;
      background: #0b0b0b;
    }}
  </style>
</head>
<body>
  <div class="email-container">
    <div class="email-header">
      <span class="brand-pill">CHANNEL: {channel_display}</span>
      <h1 class="header-title">{channel_display} - Video Success</h1>
      <div style="margin: 6px 0 0; font-size: 13px; color: #10b981; font-weight: 700;">✓ Video Upload &amp; Publish Completed</div>
    </div>

    <div class="email-body">
      <div class="status-alert">
        <span style="font-size: 20px;">✅</span>
        <div class="status-text">{channel_display} - Video Upload Success!</div>
      </div>

      <div class="video-title-box">
        <div class="video-title-label">Uploaded Video Title</div>
        <p class="video-title-text">{video_title}</p>
      </div>

      <div class="info-card">
        <div class="field-row">
          <span class="field-key">Channel</span>
          <span class="field-val">{channel_name}</span>
        </div>
        <div class="field-row">
          <span class="field-key">Privacy Mode</span>
          <span class="field-val" style="color:#f59e0b;text-transform:uppercase;">{privacy}</span>
        </div>
        <div class="field-row">
          <span class="field-key">Video Duration</span>
          <span class="field-val">{duration_display}</span>
        </div>
        <div class="field-row">
          <span class="field-key">Sound Theme</span>
          <span class="field-val">{theme_name}</span>
        </div>
        <div class="field-row">
          <span class="field-key">YouTube Video ID</span>
          <span class="field-val" style="font-family:monospace;color:#ff4d6d;">{video_id}</span>
        </div>
        <div class="field-row">
          <span class="field-key">Published Time</span>
          <span class="field-val">{now_ist}</span>
        </div>
      </div>

      <a href="{youtube_watch_url}" class="cta-button" target="_blank">
        ▶ Watch Video on YouTube
      </a>

      <a href="{channel_url}" class="sec-button" target="_blank">
        🔗 Visit YouTube Channel ({channel_name})
      </a>

      <div class="cleanup-box">
        🧹 <strong>Auto-Cleanup Complete:</strong> All local temporary audio clips, image frames, and final MP4 files were automatically deleted from the server disk.
      </div>
    </div>

    <div class="email-footer">
      YT-1M Studio Multi-Channel Automation &bull; Automated System Alert
    </div>
  </div>
</body>
</html>
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"YT-1M Studio <{sender_email}>"
    msg["To"] = actual_recipient

    part1 = MIMEText(text_content, "plain", "utf-8")
    part2 = MIMEText(html_content, "html", "utf-8")
    msg.attach(part1)
    msg.attach(part2)

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(sender_email, app_pass)
            server.sendmail(sender_email, [actual_recipient], msg.as_string())
        logger.info(f"Upload notification email sent successfully to {actual_recipient}")
        return True
    except Exception as exc:
        logger.error(f"Failed to send upload email via SMTP: {exc}")
        return False
