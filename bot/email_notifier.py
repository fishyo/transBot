import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from typing import List, Optional
import bot.config as config

logger = logging.getLogger(__name__)

def _send_email_sync(torrent_name: str, download_dir: str, size_str: str) -> bool:
    """Synchronous function to send email via SMTP."""
    if not config.ENABLE_EMAIL_NOTIFICATION:
        return False

    if not config.SMTP_SERVER or not config.SMTP_USER or not config.SMTP_PASSWORD:
        logger.warning("Email notification is enabled but SMTP settings are incomplete.")
        return False

    # Recipients
    recipients = config.EMAIL_TO if config.EMAIL_TO else [config.SMTP_USER]
    if isinstance(recipients, str):
        recipients = [r.strip() for r in recipients.split(",") if r.strip()]

    if not recipients:
        logger.warning("No recipient email address specified for email notifications.")
        return False

    subject = f"🔔 [Transmission] 下载完成: {torrent_name}"

    # Build Plain Text and HTML content
    text_content = (
        f"🔔 Transmission 下载完成！\n\n"
        f"📛 文件名称: {torrent_name}\n"
        f"📁 保存目录: {download_dir}\n"
        f"💾 文件大小: {size_str}\n"
    )

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f4f6f8; margin: 0; padding: 20px; }}
            .card {{ background: #ffffff; border-radius: 8px; max-width: 500px; margin: 0 auto; padding: 24px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); border-top: 4px solid #2ecc71; }}
            .title {{ font-size: 18px; font-weight: bold; color: #2c3e50; margin-bottom: 16px; border-bottom: 1px solid #eeeeee; padding-bottom: 12px; }}
            .item {{ margin-bottom: 12px; font-size: 14px; color: #555555; }}
            .label {{ font-weight: bold; color: #333333; }}
            .value {{ font-family: monospace; background: #f8f9fa; padding: 2px 6px; border-radius: 4px; color: #2980b9; word-break: break-all; }}
            .footer {{ margin-top: 20px; font-size: 12px; color: #999999; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="title">🔔 Transmission 下载完成</div>
            <div class="item"><span class="label">📛 文件名称：</span> {torrent_name}</div>
            <div class="item"><span class="label">📁 保存目录：</span> <span class="value">{download_dir}</span></div>
            <div class="item"><span class="label">💾 文件大小：</span> {size_str}</div>
            <div class="footer">来自 Transmission Telegram Bot 自动化通知</div>
        </div>
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = config.SMTP_USER
    msg["To"] = ", ".join(recipients)

    msg.attach(MIMEText(text_content, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        if config.SMTP_USE_SSL or config.SMTP_PORT == 465:
            with smtplib.SMTP_SSL(config.SMTP_SERVER, config.SMTP_PORT, timeout=15) as server:
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
                server.sendmail(config.SMTP_USER, recipients, msg.as_string())
        else:
            with smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT, timeout=15) as server:
                server.ehlo()
                try:
                    server.starttls()
                    server.ehlo()
                except Exception:
                    # STARTTLS might not be supported or required by some local mail servers
                    pass
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
                server.sendmail(config.SMTP_USER, recipients, msg.as_string())
        
        logger.info(f"Email notification successfully sent for torrent: {torrent_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email notification for '{torrent_name}': {e}")
        return False

async def send_email_notification_async(torrent_name: str, download_dir: str, size_str: str) -> bool:
    """Asynchronous wrapper around _send_email_sync to avoid blocking asyncio event loop."""
    if not config.ENABLE_EMAIL_NOTIFICATION:
        return False
    return await asyncio.to_thread(_send_email_sync, torrent_name, download_dir, size_str)
