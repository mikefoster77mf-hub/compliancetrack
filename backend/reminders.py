"""Email reminder dispatch for ComplianceTrack.

Runs daily to find COIs expiring within the user's configured window
and sends reminder emails via SendGrid.

Date arithmetic is done per-user in their configured timezone so that
"today" and the expiry cutoff reflect when the user actually perceives
a deadline — not the server's clock and not UTC.

Requires each user to have a `timezone` column on the users table.
Defaults to UTC when the column is missing or empty.

SENDING IDENTITY
----------------
Automated vendor reminders are sent from a DEDICATED SUBDOMAIN, never from
the primary corporate domain. Configure the sender address via env vars:

    REMINDER_FROM_EMAIL=alerts@notifications.compliancetrack.app
    REMINDER_FROM_NAME="ComplianceTrack Alerts"

Default: alerts@notifications.compliancetrack.app (dedicated subdomain).

Before go-live:
  1. Verify the subdomain in SendGrid (Settings → Sender Authentication →
     Domain Verification). SendGrid will give you SPF/DKIM/DMARC DNS records
     to add to your DNS panel.
  2. Store your SendGrid API key as SENDGRID_API_KEY in .env (never committed).
  3. Confirm the subdomain is NOT your primary workspace domain — a vendor
     reporting an alert as spam should not damage internal corporate deliverability.

IDEMPOTENCY
-----------
Each COI gets an `alert_sent_at` timestamp and a `last_reminder_days_out`
snapshot on the cois table. A COI is only re-alerted when:
  - It has never been alerted before (alert_sent_at IS NULL), OR
  - The last alert was more than 24 hours ago.

This prevents the daily scheduler (or a manual re-run / restart) from
spamming the same vendor repeatedly.

SEVERITY
--------
Emails are multipart (text + HTML). The HTML body renders a colored banner
based on how far out the expiry is relative to the user's local "today":

  > 30 days  →  INFO (neutral blue-grey)
  7-30 days  →  WARNING (orange  #f0ad4e) — soft warning before escalation
  <= 7 days  →  CRITICAL (red    #d9534f) — escalate to the vendor
  expired     →  CRITICAL (red) — document is past due

TRANSPORT
---------
SendGrid API only. SMTP fallback removed — single transport, one place to
debug deliverability. Requires `sendgrid` pip package.
"""

import os
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import psycopg2
import psycopg2.extras


def get_db():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "db"),
        user=os.getenv("POSTGRES_USER", "myuser"),
        password=os.getenv("POSTGRES_PASSWORD", "mypassword"),
        dbname=os.getenv("POSTGRES_DB", "myapp"),
    )


def utc_today():
    """Return today's date in UTC (server's reference clock)."""
    return datetime.now(timezone.utc).date()


def user_today_in_timezone(tz_name: str) -> date:
    """Return today's date as the user would see it in their local timezone."""
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = timezone.utc
    return datetime.now(tz).date()


# ── Dedicated subdomain sender identity ─────────────────────────────────────────

REMINDER_FROM_EMAIL = os.getenv(
    "REMINDER_FROM_EMAIL",
    "alerts@notifications.compliancetrack.app",
)
REMINDER_FROM_NAME = os.getenv(
    "REMINDER_FROM_NAME",
    "ComplianceTrack Alerts",
)

# ── SendGrid API key (from .env, never committed) ───────────────────────────────

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")


# ── Severity thresholds (in days, relative to user's local today) ──────────────

DAYS_WARNING = 30   # orange from 7 up to and including 30
DAYS_CRITICAL = 7   # red from 0 up to and including 7


# ── Severity helpers ────────────────────────────────────────────────────────────

def severity_for_days_out(days_out: int):
    """Return (label, css_hex, text) for a given days-out value.

    days_out > 0   → days until expiry
    days_out = 0   → expires today
    days_out < 0   → already expired (abs value = days past due)
    """
    if days_out < 0:
        return ("Expired", "#d9534f", "This certificate is past due.")
    if days_out <= DAYS_CRITICAL:
        return ("Critical", "#d9534f", "This certificate expires very soon.")
    if days_out <= DAYS_WARNING:
        return ("Warning", "#f0ad4e", "This certificate is expiring soon.")
    return ("Info", "#5bc0de", "This certificate is still valid.")


# ── HTML email body with severity-colored banner ────────────────────────────────

def build_email_html(
    user_name: str,
    vendor_name: str,
    insurance_type: str,
    expiring_date_iso: str,
    days_out: int,
):
    """Return an HTML body with a severity-colored alert banner."""
    label, color, message = severity_for_days_out(days_out)
    iso = expiring_date_iso or "No date on file"
    dashboard_url = "https://compliancetrack.app/dashboard"

    return f"""\
<html>
  <head><meta charset="utf-8"></head>
  <body style="margin:0;padding:0;font-family:Arial,Helvetica,sans-serif;
               color:#333;background:#f4f6f8;">
    <table role="presentation" cellpadding="0" cellspacing="0" width="100%"
           style="max-width:600px;margin:0 auto;background:#fff;">
      <tr><td style="padding:24px 28px;">
        <h1 style="margin:0 0 4px;font-size:20px;color:#333;">
          ComplianceTrack Alert
        </h1>
        <p style="margin:0 0 18px;font-size:14px;color:#666;">
          Hi {user_name},
        </p>

        <table role="presentation" cellpadding="0" cellspacing="0"
               style="border-left:4px solid {color};background:#f9fafb;">
          <tr><td style="padding:14px 18px;">
            <p style="margin:0 0 6px;font-size:14px;">
              <strong>{label}</strong>
            </p>
            <p style="margin:0 0 6px;font-size:14px;">
              {message}
            </p>
            <p style="margin:0;font-size:14px;">
              The Certificate of Insurance for
              <strong>{vendor_name}</strong>
              ({insurance_type}) expires on
              <strong>{iso}</strong>.
            </p>
          </td></tr>
        </table>

        <p style="margin:18px 0 0;font-size:14px;color:#666;">
          Days until expiry (your local calendar):
          <strong>{abs(days_out) if days_out < 0 else days_out}</strong>.
        </p>

        <p style="margin:18px 0 0;font-size:14px;color:#333;">
          Log in to ComplianceTrack to review or renew:
          <a href="{dashboard_url}" style="color:#0066cc;">{dashboard_url}</a>
        </p>

        <hr style="border:none;border-top:1px solid #e0e0e0;margin:22px 0;">
        <p style="margin:0;font-size:12px;color:#999;">
          -- ComplianceTrack Alerts &lt;{REMINDER_FROM_EMAIL}&gt;
        </p>
      </td></tr>
    </table>
  </body>
</html>
"""


# ── Main dispatch ────────────────────────────────────────────────────────────────

def check_and_send():
    """Find COIs expiring soon and send reminder emails via SendGrid.

    Called once per day by the scheduler (or manually for testing).
    For each user we compute "today" in their own timezone so that a COI
    expiring on the Nth calendar day from now is picked up regardless of
    where the user is located.

    Idempotency: a COI is only re-alerted if its last alert was more than
    24 hours ago (or it has never been alerted). After a successful send we
    stamp alert_sent_at and last_reminder_days_out so the next run skips it.
    """
    if not SENDGRID_API_KEY:
        print(
            "SENDGRID_API_KEY not set — skipping reminder dispatch. "
            "Configure it in .env to enable vendor alerts."
        )
        return

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # ── Grab reminder settings per user, including their timezone ──────────
    cur.execute(
        """
        SELECT u.id, u.email, u.name, u.timezone,
               rs.days_before_expiry, rs.email_enabled
        FROM users u
        JOIN reminder_settings rs ON u.id = rs.user_id
        WHERE rs.email_enabled = TRUE;
        """
    )
    users = cur.fetchall()

    now_utc = datetime.now(timezone.utc)

    for user in users:
        tz_name = user["timezone"] or "UTC"
        today = user_today_in_timezone(tz_name)
        days_before = user["days_before_expiry"]
        cutoff = today + timedelta(days=days_before)

        # ── COIs expiring in [today, cutoff] that haven't been alerted
        # recently. alert_sent_at is NULL when never alerted; otherwise we
        # compare against 24 hours ago in UTC so the guard is host-independent.
        twenty_four_hours_ago = (now_utc - timedelta(hours=24)).isoformat()
        cur.execute(
            """
            SELECT c.id, c.vendor_id, c.pdf_filename AS insurance_type,
                   c.expiring_date,
                   v.name AS vendor_name
            FROM cois c
            JOIN vendors v ON c.vendor_id = v.id
            WHERE c.user_id = %s
              AND c.expiring_date IS NOT NULL
              AND c.expiring_date >= %s
              AND c.expiring_date <= %s
              AND c.archived = FALSE
              AND (
                  c.alert_sent_at IS NULL
                  OR c.alert_sent_at < %s::timestamptz
              )
            ORDER BY c.expiring_date;
            """,
            (user["id"], today, cutoff, twenty_four_hours_ago),
        )
        cois = cur.fetchall()

        for coi in cois:
            send_reminder_email(
                conn=conn,
                cur=cur,
                coi_id=coi["id"],
                to_email=user["email"],
                user_name=user["name"] or user["email"],
                vendor_name=coi["vendor_name"],
                insurance_type=coi["insurance_type"] or "Certificate of Insurance",
                expiring_date=coi["expiring_date"],
                user_today=today,
            )

    cur.close()
    conn.close()


def send_reminder_email(
    conn,
    cur,
    coi_id: int,
    to_email: str,
    user_name: str,
    vendor_name: str,
    insurance_type: str,
    expiring_date,
    user_today: date,
):
    """Send a single reminder email via SendGrid and stamp the send on the COI.

    After a successful send we UPDATE the cois row with alert_sent_at = NOW()
    and last_reminder_days_out so the daily scheduler does not re-send the
    same alert within 24 hours.

    conn / cur are reused for the UPDATE so we don't open a second connection.
    """
    # ── Severity from user's perspective ────────────────────────────────────
    if expiring_date is None:
        days_out = 0
    else:
        expiring = expiring_date.date() if hasattr(expiring_date, "date") else expiring_date
        days_out = (expiring - user_today).days

    label, _, _ = severity_for_days_out(days_out)
    subject = f"COI {label} - {vendor_name} - {insurance_type}"
    text_body = (
        f"Hi {user_name},\n\n"
        f"The Certificate of Insurance for {vendor_name} ({insurance_type}) "
        f"expires on {expiring_date.isoformat() if expiring_date else 'no date on file'}.\n\n"
        f"Days until expiry (your local calendar): {abs(days_out) if days_out < 0 else days_out}.\n\n"
        f"Log in to ComplianceTrack to review or renew:\n"
        f"https://compliancetrack.app/dashboard\n\n"
        f"-- ComplianceTrack Alerts\n"
    )
    html_body = build_email_html(
        user_name=user_name,
        vendor_name=vendor_name,
        insurance_type=insurance_type,
        expiring_date_iso=expiring_date.isoformat() if expiring_date else "No date on file",
        days_out=days_out,
    )

    # ── Send via SendGrid API ─────────────────────────────────────────────────
    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail, To, From, Content

        sg = sendgrid.SendGridAPIClient(api_key=SENDGRID_API_KEY)
        mail = Mail(
            from_email=From(email=REMINDER_FROM_EMAIL, name=REMINDER_FROM_NAME),
            to_emails=To(email=to_email),
            subject=subject,
            plain_text_content=Content("text/plain", text_body),
            html_content=Content("text/html", html_body),
        )
        # NOTE: SendGrid appends an unsubscribe footer to every email by default.
        # For transactional compliance alerts (vendors must not be able to
        # "unsubscribe" from a legal notice), disable Subscription Tracking in
        # SendGrid's dashboard: Mail Settings → Subscription Tracking → uncheck
        # "Enable Subscription Tracking". Omit asm here so we don't rely on a
        # suppression group that may not exist in the account yet.

        response = sg.client.mail.send.post(request_body=mail.get())
        if response.status_code in (200, 202):
            print(
                f"[sendgrid] Alert sent to {to_email}: {subject} "
                f"(status {response.status_code})"
            )
            sent = True
        else:
            print(
                f"[sendgrid] Unexpected status {response.status_code} for {to_email}: "
                f"{subject}"
            )
            sent = False
    except Exception as e:
        print(f"SendGrid email failed for {to_email}: {e}")
        sent = False

    # ── Idempotency stamp — only if the send actually succeeded ─────────────
    if sent:
        cur.execute(
            """
            UPDATE cois
            SET alert_sent_at = NOW()::timestamptz,
                last_reminder_days_out = %s
            WHERE id = %s;
            """,
            (days_out, coi_id),
        )
        conn.commit()


# ── Migration helper (run once against the live DB) ────────────────────────────

def migrate_add_alert_columns():
    """Add alert_sent_at + last_reminder_days_out to cois if they are missing.

    Safe to run on a live database — catches DuplicateColumn and exits cleanly.
    Run BEFORE the first deploy that ships the new reminders.py.
    """
    conn = get_db()
    cur = conn.cursor()
    for column, ddl in (
        ("alert_sent_at", "ALTER TABLE cois ADD COLUMN alert_sent_at TIMESTAMPTZ DEFAULT NULL;"),
        ("last_reminder_days_out", "ALTER TABLE cois ADD COLUMN last_reminder_days_out INTEGER DEFAULT NULL;"),
    ):
        try:
            cur.execute(ddl)
            conn.commit()
            print(f"OK: column cois.{column} added.")
        except psycopg2.errors.DuplicateColumn:
            conn.rollback()
            print(f"OK: column cois.{column} already exists.")
        except Exception as e:
            conn.rollback()
            print(f"FAILED on cois.{column}: {e}")
            raise SystemExit(1)
    cur.close()
    conn.close()
