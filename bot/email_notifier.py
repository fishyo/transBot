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
    """Synchronous function to send receipt-styled email via SMTP."""
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

    subject = f"🧾 [Transmission 存根] 下载完成: {torrent_name}"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    order_id = datetime.now().strftime("%Y%m%d%H%M%S")

    # Build Plain Text and HTML content
    text_content = (
        f"======== TRANSMISSION RECEIPT / 任务存根 ========\n"
        f"完成时间: {now_str}\n"
        f"订单编号: {order_id}\n"
        f"--------------------------------------------------\n"
        f"📛 任务名称: {torrent_name}\n"
        f"📁 保存路径: {download_dir}\n"
        f"💾 文件体积: {size_str}\n"
        f"状态: 已完成 (100% SUCCESS)\n"
        f"==================================================\n"
        f"感谢使用 Transmission NAS 自动下映系统！\n"
    )

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Download Receipt</title>
        <style>
            body {{
                margin: 0;
                padding: 30px 10px;
                background-color: #f1f5f9;
                font-family: 'SF Mono', Consolas, 'Courier New', Courier, monospace, sans-serif;
                color: #1e293b;
            }}
            .receipt-container {{
                max-width: 400px;
                margin: 0 auto;
                background: #ffffff;
                border-radius: 8px;
                padding: 24px 20px;
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.08);
                border: 1px solid #e2e8f0;
                position: relative;
            }}
            .receipt-header {{
                text-align: center;
                padding-bottom: 16px;
                border-bottom: 2px dashed #94a3b8;
            }}
            .store-name {{
                font-size: 18px;
                font-weight: 900;
                letter-spacing: 2px;
                color: #0f172a;
                text-transform: uppercase;
                margin-top: 4px;
            }}
            .receipt-title {{
                font-size: 12px;
                color: #64748b;
                letter-spacing: 1px;
                margin-top: 4px;
                font-weight: bold;
            }}
            .status-badge {{
                display: inline-block;
                background-color: #f0fdf4;
                color: #16a34a;
                border: 1px solid #bbf7d0;
                padding: 4px 12px;
                border-radius: 12px;
                font-size: 13px;
                font-weight: bold;
                margin-top: 10px;
                letter-spacing: 1px;
            }}
            .meta-section {{
                font-size: 12px;
                color: #475569;
                margin: 16px 0;
                line-height: 1.8;
            }}
            .meta-row {{
                display: flex;
                justify-content: space-between;
            }}
            .dashed-line {{
                border-top: 1px dashed #cbd5e1;
                margin: 14px 0;
            }}
            .section-label {{
                text-align: center;
                font-size: 11px;
                font-weight: bold;
                color: #94a3b8;
                letter-spacing: 2px;
                margin-bottom: 14px;
            }}
            .item-block {{
                margin-bottom: 14px;
            }}
            .item-title {{
                font-size: 11px;
                font-weight: bold;
                color: #64748b;
                margin-bottom: 4px;
            }}
            .item-value {{
                background: #f8fafc;
                padding: 10px;
                border-radius: 6px;
                border: 1px solid #e2e8f0;
                font-size: 13px;
                word-break: break-all;
                color: #0f172a;
                font-weight: 600;
                line-height: 1.4;
            }}
            .barcode-section {{
                text-align: center;
                margin-top: 20px;
            }}
            .barcode-lines {{
                font-family: monospace;
                font-size: 18px;
                letter-spacing: 4px;
                font-weight: bold;
                color: #334155;
                user-select: none;
            }}
            .receipt-footer {{
                text-align: center;
                font-size: 11px;
                color: #64748b;
                margin-top: 12px;
                font-style: italic;
            }}
        </style>
    </head>
    <body>
        <div class="receipt-container">
            <!-- Header -->
            <div class="receipt-header">
                <div style="font-size: 28px;">🧾</div>
                <div class="store-name">TRANSMISSION NAS</div>
                <div class="receipt-title">★ 下载完成结账存根 ★</div>
                <div class="status-badge">✔ DOWNLOAD SUCCESS</div>
            </div>

            <!-- Order Metadata -->
            <div class="meta-section">
                <div class="meta-row">
                    <span>完成时间:</span>
                    <span style="font-weight: bold; color: #0f172a;">{now_str}</span>
                </div>
                <div class="meta-row">
                    <span>存根编号:</span>
                    <span style="font-weight: bold; color: #0f172a;">TR-{order_id}</span>
                </div>
                <div class="meta-row">
                    <span>服务类型:</span>
                    <span style="font-weight: bold; color: #0f172a;">BT/Magnet 离线下载</span>
                </div>
            </div>

            <div class="dashed-line"></div>
            <div class="section-label">--- 任务详情清单 ---</div>

            <!-- Receipt Content Items -->
            <div class="item-block">
                <div class="item-title">📛 资源名称 (ITEM NAME)</div>
                <div class="item-value">{torrent_name}</div>
            </div>

            <div class="item-block">
                <div class="item-title">📁 保存位置 (SAVE PATH)</div>
                <div class="item-value" style="color: #2563eb;">{download_dir}</div>
            </div>

            <div class="item-block">
                <div class="item-title">💾 总体积 (TOTAL SIZE)</div>
                <div class="item-value" style="color: #16a34a; font-size: 14px;">{size_str}</div>
            </div>

            <div class="dashed-line" style="border-top: 2px dashed #94a3b8;"></div>

            <!-- Barcode & Footer -->
            <div class="barcode-section">
                <div class="barcode-lines">|||| | ||||| || |||| ||| |||||</div>
                <div style="font-size: 10px; color: #94a3b8; margin-top: 4px;">* TR-BOT-{order_id} *</div>
            </div>

            <div class="receipt-footer">
                Thank you for using Transmission NAS Bot!<br>
                感谢使用 • 祝您观影愉快
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
        
        logger.info(f"Receipt email notification successfully sent for torrent: {torrent_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email notification for '{torrent_name}': {e}")
        return False

async def send_email_notification_async(torrent_name: str, download_dir: str, size_str: str) -> bool:
    """Asynchronous wrapper around _send_email_sync to avoid blocking asyncio event loop."""
    if not config.ENABLE_EMAIL_NOTIFICATION:
        return False
    return await asyncio.to_thread(_send_email_sync, torrent_name, download_dir, size_str)
