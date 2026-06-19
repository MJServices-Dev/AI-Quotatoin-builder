"""
email_service.py — Sends a generated quotation (PDF or Word) to the
recipient's email address using Python's built-in smtplib (TLS / Gmail SMTP).

Configuration (add to .env):
    EMAIL_SENDER      = your.email@gmail.com
    EMAIL_PASSWORD    = your_app_password     # Gmail App Password (not account password)
    EMAIL_SMTP_HOST   = smtp.gmail.com        # optional, default: smtp.gmail.com
    EMAIL_SMTP_PORT   = 587                   # optional, default: 587
"""

import os
import smtplib
import traceback
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

from dotenv import load_dotenv
load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
SMTP_HOST   = os.getenv("EMAIL_SMTP_HOST",  "smtp.gmail.com")
SMTP_PORT   = int(os.getenv("EMAIL_SMTP_PORT", "587"))
SENDER_ADDR = os.getenv("EMAIL_SENDER",    "")
SENDER_PASS = os.getenv("EMAIL_PASSWORD",  "")


def send_quotation_email(
    recipient_email: str,
    recipient_name:  str,
    company_name:    str,
    file_path:       str = None,
    pdf_path:        str = None,   # kept for backward-compat; prefer file_path
) -> tuple[bool, str]:
    """
    Send the generated quotation (PDF or Word) to the recipient via email.

    Args:
        recipient_email : Target email address.
        recipient_name  : Full name of the recipient (for personalisation).
        company_name    : Recipient's company name (for display).
        file_path       : Absolute path to the generated PDF or Word (.docx) file.
        pdf_path        : Deprecated alias for file_path (backward compatibility).

    Returns:
        (success: bool, message: str)
    """
    # Backward-compat: support callers that pass only pdf_path
    if file_path is None and pdf_path is not None:
        file_path = pdf_path

    if not SENDER_ADDR or not SENDER_PASS:
        return False, "Email credentials not configured. Please set EMAIL_SENDER and EMAIL_PASSWORD in .env"

    if not file_path or not os.path.isfile(file_path):
        return False, f"Attachment file not found at: {file_path}"

    # Detect file type from extension
    ext = os.path.splitext(file_path)[1].lower()
    if ext in ('.docx', '.doc'):
        mime_subtype = 'vnd.openxmlformats-officedocument.wordprocessingml.document'
        file_label   = 'Word'
    else:
        mime_subtype = 'pdf'
        file_label   = 'PDF'

    try:
        msg = MIMEMultipart()
        msg["From"]    = f"MJ Services Quotation <{SENDER_ADDR}>"
        msg["To"]      = recipient_email
        msg["Subject"] = f"Your Quotation from MJ Services — {company_name}"

        # ── Email body (HTML) ──────────────────────────────────────────────────
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
                            padding: 24px; border-radius: 12px 12px 0 0; text-align: center;">
                    <h1 style="color: #fff; margin: 0; font-size: 22px;">MJ Services</h1>
                    <p style="color: #94a3b8; margin: 6px 0 0;">Authorized Zoho Channel Partner</p>
                </div>

                <div style="background: #f8fafc; padding: 28px; border-radius: 0 0 12px 12px;
                            border: 1px solid #e2e8f0; border-top: none;">
                    <p style="font-size: 16px;">Dear <strong>{recipient_name}</strong>,</p>

                    <p>Thank you for your interest in our services. Please find attached your
                    personalized quotation ({file_label} format) prepared by the MJ Services team for
                    <strong>{company_name}</strong>.</p>

                    <div style="background: #fff3cd; border-left: 4px solid #f59e0b;
                                padding: 12px 16px; border-radius: 4px; margin: 20px 0;">
                        <strong>Disclaimer:</strong> This is a tentative quote and charges may
                        vary by 10–20%. Please contact <strong>8446655664</strong> for final pricing
                        and more information.
                    </div>

                    <p>If you have any questions or would like to discuss the quotation further,
                    feel free to reach out to us.</p>

                    <div style="margin-top: 28px; padding-top: 20px; border-top: 1px solid #e2e8f0;
                                font-size: 13px; color: #64748b;">
                        <strong>MJ Services</strong><br>
                        Authorized Zoho Channel Partner<br>
                        8446655664
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        msg.attach(MIMEText(body_html, "html"))

        # ── Attach file (PDF or Word) ───────────────────────────────────────────
        with open(file_path, "rb") as f:
            file_bytes = f.read()
        attachment = MIMEApplication(file_bytes, _subtype=mime_subtype)
        attachment.add_header(
            "Content-Disposition",
            "attachment",
            filename=os.path.basename(file_path),
        )
        msg.attach(attachment)

        # ── Send via SMTP (TLS) ────────────────────────────────────────────────
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SENDER_ADDR, SENDER_PASS)
            server.sendmail(SENDER_ADDR, recipient_email, msg.as_string())

        return True, f"Quotation ({file_label}) sent successfully to {recipient_email}"

    except smtplib.SMTPAuthenticationError:
        return False, "Email authentication failed. Please check EMAIL_SENDER and EMAIL_PASSWORD in .env"
    except smtplib.SMTPException as e:
        return False, f"SMTP error: {e}"
    except Exception as e:
        traceback.print_exc()
        return False, f"Failed to send email: {e}"
