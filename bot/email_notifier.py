import asyncio
import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from typing import List, Optional
import bot.config as config

logger = logging.getLogger(__name__)

def _send_email_sync(torrent_name: str, download_dir: str, size_str: str) -> bool:
    """Synchronous function to send Modern Minimalist Receipt (Style 2B) email via SMTP."""
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

    subject = f"⚡ [Task Receipt] {torrent_name}"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    order_id = datetime.now().strftime("%Y%m%d%H%M%S")

    # Build Plain Text and HTML content
    text_content = (
        f"⚡ TRANSMISSION SERVICES - Task Receipt\n"
        f"● Download Complete (100% SUCCESS)\n\n"
        f"FILE NAME   : {torrent_name}\n"
        f"DESTINATION : {download_dir}\n"
        f"FILE SIZE   : {size_str}\n"
        f"FINISH TIME : {now_str}\n"
        f"RECEIPT ID  : TR-{order_id}\n\n"
        f"Thank you for using Transmission NAS!\n"
    )

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Task Receipt</title>
        <style>
            body {{
                margin: 0;
                padding: 30px 10px;
                background-color: #f8fafc;
                font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                color: #0f172a;
            }}
            .receipt-card {{
                max-width: 420px;
                margin: 0 auto;
                background-color: #ffffff;
                border-radius: 16px;
                padding: 28px 24px;
                box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
                border: 1px solid #e2e8f0;
            }}
            .card-header {{
                border-bottom: 1px solid #f1f5f9;
                padding-bottom: 16px;
                margin-bottom: 20px;
            }}
            .brand-logo {{
                font-size: 13px;
                font-weight: 800;
                color: #3b82f6;
                letter-spacing: 1.5px;
                text-transform: uppercase;
            }}
            .card-title {{
                font-size: 22px;
                font-weight: 800;
                color: #0f172a;
                margin-top: 4px;
                letter-spacing: -0.5px;
            }}
            .status-badge {{
                display: inline-block;
                background-color: #dcfce7;
                color: #15803d;
                font-size: 12px;
                font-weight: 700;
                padding: 4px 12px;
                border-radius: 20px;
                margin-top: 8px;
            }}
            .field-group {{
                margin-bottom: 14px;
            }}
            .field-label {{
                font-size: 11px;
                font-weight: 700;
                color: #94a3b8;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin-bottom: 4px;
            }}
            .field-value {{
                font-size: 14px;
                font-weight: 600;
                color: #1e293b;
                background-color: #f8fafc;
                padding: 10px 12px;
                border-radius: 8px;
                border: 1px solid #f1f5f9;
                word-break: break-all;
                line-height: 1.4;
            }}
            .grid-row {{
                display: table;
                width: 100%;
                margin-bottom: 14px;
            }}
            .grid-col {{
                display: table-cell;
                width: 50%;
                vertical-align: top;
            }}
            .card-footer {{
                border-top: 1px solid #f1f5f9;
                padding-top: 16px;
                margin-top: 20px;
                text-align: center;
                font-size: 12px;
                color: #94a3b8;
                font-family: 'SF Mono', Consolas, monospace;
            }}
        </style>
    </head>
    <body>
        <div class="receipt-card">
            <!-- Header -->
            <div class="card-header">
                <div class="brand-logo">⚡ TRANSMISSION SERVICES</div>
                <div class="card-title">Task Receipt</div>
                <div class="status-badge">● Download Complete</div>
            </div>

            <!-- Fields -->
            <div class="field-group">
                <div class="field-label">FILE NAME</div>
                <div class="field-value">{torrent_name}</div>
            </div>

            <div class="field-group">
                <div class="field-label">DESTINATION</div>
                <div class="field-value" style="color: #2563eb;">{download_dir}</div>
            </div>

            <!-- Two Column Grid for Size & Time -->
            <div class="field-group">
                <div class="grid-row">
                    <div class="grid-col" style="padding-right: 6px;">
                        <div class="field-label">FILE SIZE</div>
                        <div class="field-value" style="color: #16a34a; font-size: 15px; font-weight: 700;">{size_str}</div>
                    </div>
                    <div class="grid-col" style="padding-left: 6px;">
                        <div class="field-label">FINISH TIME</div>
                        <div class="field-value" style="font-size: 12px; color: #475569;">{now_str}</div>
                    </div>
                </div>
            </div>

            <!-- Footer -->
            <div class="card-footer">
                RECEIPT ID: TR-{order_id}
            </div>
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
                    pass
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
                server.sendmail(config.SMTP_USER, recipients, msg.as_string())
        
        logger.info(f"Modern receipt-style email notification successfully sent for torrent: {torrent_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email notification for '{torrent_name}': {e}")
        return False

async def send_email_notification_async(torrent_name: str, download_dir: str, size_str: str) -> bool:
    """Asynchronous wrapper around _send_email_sync to avoid blocking asyncio event loop."""
    if not config.ENABLE_EMAIL_NOTIFICATION:
        return False
    return await asyncio.to_thread(_send_email_sync, torrent_name, download_dir, size_str)
