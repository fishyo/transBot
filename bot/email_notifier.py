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
    """Synchronous function to send Style 2B (Modern Minimalist Receipt) email via SMTP."""
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
    </head>
    <body style="margin: 0; padding: 30px 10px; background-color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #0f172a;">
        <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
            <tr>
                <td align="center">
                    <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 420px; background-color: #ffffff; border-radius: 16px; padding: 28px 24px; box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06); border: 1px solid #e2e8f0;">
                        <!-- Header -->
                        <tr>
                            <td style="border-bottom: 1px solid #f1f5f9; padding-bottom: 16px;">
                                <div style="font-size: 13px; font-weight: 800; color: #3b82f6; letter-spacing: 1.5px; text-transform: uppercase;">⚡ TRANSMISSION SERVICES</div>
                                <div style="font-size: 22px; font-weight: 800; color: #0f172a; margin-top: 4px; letter-spacing: -0.5px;">Task Receipt</div>
                                <div style="display: inline-block; background-color: #dcfce7; color: #15803d; font-size: 12px; font-weight: 700; padding: 4px 12px; border-radius: 20px; margin-top: 8px;">● Download Complete</div>
                            </td>
                        </tr>

                        <!-- Field 1: FILE NAME -->
                        <tr>
                            <td style="padding-top: 16px;">
                                <div style="font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">FILE NAME / 文件名称</div>
                                <div style="font-size: 14px; font-weight: 600; color: #0f172a; background-color: #f8fafc; padding: 10px 12px; border-radius: 8px; border: 1px solid #f1f5f9; word-break: break-all; line-height: 1.4;">
                                    {torrent_name}
                                </div>
                            </td>
                        </tr>

                        <!-- Field 2: DESTINATION -->
                        <tr>
                            <td style="padding-top: 14px;">
                                <div style="font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">DESTINATION / 保存路径</div>
                                <div style="font-size: 13px; font-weight: 600; color: #2563eb; background-color: #f8fafc; padding: 10px 12px; border-radius: 8px; border: 1px solid #f1f5f9; word-break: break-all; line-height: 1.4;">
                                    {download_dir}
                                </div>
                            </td>
                        </tr>

                        <!-- Two Columns: FILE SIZE & TIME -->
                        <tr>
                            <td style="padding-top: 14px;">
                                <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
                                    <tr>
                                        <td width="50%" style="padding-right: 6px; vertical-align: top;">
                                            <div style="font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">FILE SIZE / 体积</div>
                                            <div style="font-size: 15px; font-weight: 700; color: #16a34a; background-color: #f8fafc; padding: 10px 12px; border-radius: 8px; border: 1px solid #f1f5f9;">
                                                {size_str}
                                            </div>
                                        </td>
                                        <td width="50%" style="padding-left: 6px; vertical-align: top;">
                                            <div style="font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">TIME / 完成时间</div>
                                            <div style="font-size: 12px; font-weight: 600; color: #475569; background-color: #f8fafc; padding: 10px 12px; border-radius: 8px; border: 1px solid #f1f5f9;">
                                                {now_str}
                                            </div>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>

                        <!-- Footer -->
                        <tr>
                            <td style="border-top: 1px solid #f1f5f9; padding-top: 16px; margin-top: 20px; text-align: center; font-size: 11px; color: #94a3b8; font-family: 'SF Mono', Consolas, monospace;">
                                RECEIPT ID: TR-{order_id}
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
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
