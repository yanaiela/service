"""
SMTP email sender for review reminder emails.
"""

import smtplib
from email.mime.text import MIMEText

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


def send_reminder_emails(sender_email, password, missing_entries, test_email=None):
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

    for entry in missing_entries:
        recipient = test_email if test_email else entry["reviewer_email"]
        subject = f"Review reminder: {entry['paper_title']}"
        body = (
            f"Dear {entry['reviewer_name']},\n"
            f"\n"
            f"\n"
            f"I am reaching out about a paper for which I'm serving as an area chair (AC), "
            f"and you are a reviewer.\n"
            f"\n"
            f"The paper is called \"{entry['paper_title']}\"\n"
            f"\n"
            f"\n"
            f"The review deadline has passed, and I need to ensure the paper receives at least 3 reviews.\n"
            f"\n"
            f"Are you able to submit a review for this paper in the next day or two?\n"
            f"\n"
            f"\n"
            f"Best,\n"
            f"\n"
            f"Yanai"
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
