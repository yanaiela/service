"""
SMTP email sender for review reminder emails.
"""

import smtplib
from email.mime.text import MIMEText
from pathlib import Path

SMTP_SERVERS = {
    "gmail.com": ("smtp.gmail.com", 587),
    "outlook.com": ("smtp-mail.outlook.com", 587),
    "hotmail.com": ("smtp-mail.outlook.com", 587),
    "yahoo.com": ("smtp.mail.yahoo.com", 587),
}


def _get_smtp_server(email: str):
    """Return (host, port) for the given email address."""
    domain = email.rsplit("@", 1)[1].lower()
    if domain in SMTP_SERVERS:
        return SMTP_SERVERS[domain]
    return (f"smtp.{domain}", 587)


def send_reminder_emails(sender_email, sender_name, password, missing_entries, test_email=None):
    """
    Send reminder emails via SMTP.

    If test_email is provided, all emails are sent to that address instead.
    Returns list of (recipient_email, success_bool[, error_str]) tuples.
    """
    host, port = _get_smtp_server(sender_email)
    results = []

    try:
        server = smtplib.SMTP(host, port)
        server.starttls()
        server.login(sender_email, password)
    except Exception as e:
        return [(entry["reviewer_email"], False, f"SMTP login failed: {e}") for entry in missing_entries]

    template_path = Path(__file__).parent / "templates" / "reminder_email.txt"
    template = template_path.read_text()

    for entry in missing_entries:
        if entry.get("flag") == "Emergency":
            results.append((entry["reviewer_email"], False, "Skipped: reviewer declared emergency"))
            continue
        recipient = test_email if test_email else entry["reviewer_email"]
        if "*" in recipient or "@" not in recipient:
            results.append((recipient, False, "No valid email address available (masked or missing)"))
            continue
        subject = f"Review reminder: {entry['paper_title']}"
        body = template.format(
            reviewer_name=entry["reviewer_name"],
            paper_title=entry["paper_title"],
            sender_name=sender_name,
        )

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = sender_email
        msg["To"] = recipient

        try:
            server.sendmail(sender_email, [recipient], msg.as_string())
            results.append((recipient, True))
        except Exception as e:
            results.append((recipient, False, str(e)))

    server.quit()
    return results
