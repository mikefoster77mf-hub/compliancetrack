"""Email reminder dispatch for ComplianceTrack.

Runs daily to find COIs expiring within the user's configured window
and sends reminder emails via Resend (preferred) or SMTP fallback.
"""

import os
from datetime import date, timedelta
import psycopg2
import psycopg2.extras


def get_db():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "db"),
        user=os.getenv("POSTGRES_USER", "myuser"),
        password=os.getenv("POSTGRES_PASSWORD", "mypassword"),
        dbname=os.getenv("POSTGRES_DB", "myapp"),
    )


def check_and_send():
    """Find COIs expiring soon and send reminder emails.

    Called once per day by the scheduler (or manually for testing).
    """
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    today = date.today()

    # Get all users with reminder settings
    cur.execute(
        """
        SELECT u.id, u.email, u.name, u.password_hash,
               rs.days_before_expiry, rs.email_enabled
        FROM users u
        JOIN reminder_settings rs ON u.id = rs.user_id
        WHERE rs.email_enabled = TRUE;
        """
    )
    users = cur.fetchall()

    for user in users:
        days_before = user["days_before_expiry"]
        cutoff = today + timedelta(days=days_before)

        # Find COIs for this user expiring within the window
        cur.execute(
            """
            SELECT c.id, c.vendor_id, c.insurance_type, c.expiring_date,
                   v.name AS vendor_name
            FROM cois c
            JOIN vendors v ON c.vendor_id = v.id
            WHERE c.user_id = %s
              AND c.expiring_date IS NOT NULL
              AND c.expiring_date >= %s
              AND c.expiring_date <= %s
            ORDER BY c.expiring_date;
            """,
            (user["id"], today, cutoff),
        )
        cois = cur.fetchall()

        for coi in cois:
            send_reminder_email(
                to_email=user["email"],
                user_name=user["name"] or user["email"],
                vendor_name=coi["vendor_name"],
                insurance_type=coi["insurance_type"] or "Certificate of Insurance",
                expiring_date=coi["expiring_date"].isoformat(),
            )

    cur.close()
    conn.close()


def send_reminder_email(to_email, user_name, vendor_name, insurance_type, expiring_date):
    """Send a single reminder email.

    Uses Resend API if RESEND_API_KEY is set, otherwise falls back to SMTP.
    """
    subject = f"COI Expiring - {vendor_name} - {insurance_type}"
    body = (
        f"Hi {user_name},\n\n"
        f"The Certificate of Insurance for {vendor_name} ({insurance_type}) "
        f"is expiring on {expiring_date}.\n\n"
        f"Log in to ComplianceTrack to review or renew:\n"
        f"https://compliancetrack.app/dashboard\n\n"
        f"-- ComplianceTrack\n"
    )

    api_key = os.getenv("RESEND_API_KEY")
    if api_key:
        try:
            import resend
            resend.api_key = api_key
            resend.Emails.send({
                "from": "ComplianceTrack <onboarding@resend.dev>",
                "to": [to_email],
                "subject": subject,
                "text": body,
            })
        except Exception as e:
            print(f"Resend email failed for {to_email}: {e}")
    else:
        # SMTP fallback
        smtp_host = os.getenv("SMTP_HOST")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USER")
        smtp_pass = os.getenv("SMTP_PASSWORD")
        if smtp_host and smtp_user and smtp_pass:
            try:
                import smtplib
                from email.message import EmailMessage
                msg = EmailMessage()
                msg["Subject"] = subject
                msg["From"] = "ComplianceTrack <noreply@compliancetrack.app>"
                msg["To"] = to_email
                msg.set_content(body)
                with smtplib.SMTP(smtp_host, smtp_port) as s:
                    s.starttls()
                    s.login(smtp_user, smtp_pass)
                    s.send_message(msg)
            except Exception as e:
                print(f"SMTP email failed for {to_email}: {e}")
        else:
            print(f"No email backend configured. Would have sent to {to_email}: {subject}")
