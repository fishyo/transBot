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
    """Synchronous function to send Terminal-styled email via SMTP."""
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

    subject = f"💻 [Terminal] Transmission Task Completed: {torrent_name}"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Build Plain Text and HTML content
    text_content = (
        f"root@omv:~# transmission-daemon --status\n"
        f"[INFO] DOWNLOAD TASK FINISHED\n\n"
        f"● STATUS       : COMPLETED (100% SUCCESS)\n"
        f"● FINISH TIME  : {now_str}\n"
        f"● FILE NAME    : {torrent_name}\n"
        f"● DOWNLOAD DIR : {download_dir}\n"
        f"● TOTAL SIZE   : {size_str}\n\n"
        f"root@omv:~# _\n"
    )

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Terminal Download Notification</title>
        <style>
            body {{
                margin: 0;
                padding: 30px 10px;
                background-color: #090d16;
                font-family: 'SF Mono', Consolas, 'Courier New', Courier, monospace, sans-serif;
                color: #c9d1d9;
            }}
            .terminal-window {{
                max-width: 520px;
                margin: 0 auto;
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-radius: 10px;
                overflow: hidden;
                box-shadow: 0 12px 36px rgba(0, 0, 0, 0.6);
            }}
            .terminal-bar {{
                background-color: #161b22;
                padding: 10px 14px;
                display: flex;
                align-items: center;
                border-bottom: 1px solid #30363d;
            }}
            .dot {{
                height: 12px;
                width: 12px;
                border-radius: 50%;
                display: inline-block;
                margin-right: 8px;
            }}
            .dot-red {{ background-color: #ff5f56; }}
            .dot-yellow {{ background-color: #ffbd2e; }}
            .dot-green {{ background-color: #27c93f; }}
            .terminal-title {{
                color: #8b949e;
                font-size: 12px;
                margin-left: auto;
                margin-right: auto;
                font-weight: bold;
                letter-spacing: 0.5px;
            }}
            .terminal-body {{
                padding: 20px;
                font-size: 13px;
                line-height: 1.7;
            }}
            .prompt {{
                color: #58a6ff;
                font-weight: bold;
            }}
            .cmd {{
                color: #f0f6fc;
            }}
            .status-box {{
                border-left: 3px solid #3fb950;
                background-color: rgba(46, 160, 67, 0.1);
                padding: 10px 14px;
                margin: 14px 0;
                border-radius: 0 6px 6px 0;
            }}
            .label {{
                color: #8b949e;
                display: inline-block;
                width: 120px;
            }}
            .val-success {{
                color: #3fb950;
                font-weight: bold;
            }}
            .val-name {{
                color: #79c0ff;
                font-weight: bold;
                word-break: break-all;
            }}
            .val-path {{
                color: #d2a8ff;
                word-break: break-all;
            }}
            .val-size {{
                color: #e3b341;
                font-weight: bold;
            }}
            .footer-line {{
                margin-top: 16px;
                padding-top: 12px;
                border-top: 1px dashed #30363d;
                color: #8b949e;
                font-size: 11px;
            }}
        </style>
    </head>
    <body>
        <div class="terminal-window">
            <!-- Terminal Header -->
            <div class="terminal-bar">
                <span class="dot dot-red"></span>
                <span class="dot dot-yellow"></span>
                <span class="dot dot-green"></span>
                <span class="terminal-title">root@omv-nas:~ (bash)</span>
            </div>

            <!-- Terminal Body -->
            <div class="terminal-body">
                <div><span class="prompt">root@omv:~#</span> <span class="cmd">transmission-daemon --status</span></div>
                <div style="color: #8b949e; font-size: 11px; margin-top: 4px;">[SYSTEM_EVENT] Download task completion signal received.</div>

                <div class="status-box">
                    <div><span class="label">● STATUS:</span> <span class="val-success">COMPLETED (100% SUCCESS)</span></div>
                    <div><span class="label">● FINISH TIME:</span> <span style="color: #e6edf3;">{now_str}</span></div>
                </div>

                <div style="margin-bottom: 12px;">
                    <div class="label">[TORRENT_NAME]</div>
                    <div class="val-name">{torrent_name}</div>
                </div>

                <div style="margin-bottom: 12px;">
                    <div class="label">[DOWNLOAD_PATH]</div>
                    <div class="val-path">{download_dir}</div>
                </div>

                <div style="margin-bottom: 12px;">
                    <div class="label">[TOTAL_SIZE]</div>
                    <div class="val-size">{size_str}</div>
                </div>

                <div class="footer-line">
                    <span class="prompt">root@omv:~#</span> _
                </div>
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
        
        logger.info(f"Terminal-style email notification successfully sent for torrent: {torrent_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email notification for '{torrent_name}': {e}")
        return False

async def send_email_notification_async(torrent_name: str, download_dir: str, size_str: str) -> bool:
    """Asynchronous wrapper around _send_email_sync to avoid blocking asyncio event loop."""
    if not config.ENABLE_EMAIL_NOTIFICATION:
        return False
    return await asyncio.to_thread(_send_email_sync, torrent_name, download_dir, size_str)
