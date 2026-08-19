"""Lemon Squeezy payment integration for ComplianceTrack.

Handles checkout creation, webhook verification, and subscription gating.

Required env vars:
    LEMON_SQUEEZY_API_KEY       - API key from Lemon Squeezy dashboard
    LEMON_SQUEEZY_STORE_ID      - Your store ID
    LEMON_SQUEEZY_WEBHOOK_SECRET - Webhook signing secret
    LEMON_SQUEEZY_VARIANT_ID_MONTHLY - Variant ID for monthly plan
    LEMON_SQUEEZY_VARIANT_ID_ANNUAL  - Variant ID for annual plan
"""

import hashlib
import hmac
import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

logger = logging.getLogger("payments")

# ── Config ───────────────────────────────────────────────────────────────────

LS_API_KEY = os.getenv("LEMON_SQUEEZY_API_KEY")
LS_STORE_ID = os.getenv("LEMON_SQUEEZY_STORE_ID")
LS_WEBHOOK_SECRET = os.getenv("LEMON_SQUEEZY_WEBHOOK_SECRET")
LS_VARIANT_MONTHLY = os.getenv("LEMON_SQUEEZY_VARIANT_ID_MONTHLY")
LS_VARIANT_ANNUAL = os.getenv("LEMON_SQUEEZY_VARIANT_ID_ANNUAL")

LS_BASE_URL = "https://api.lemonsqueezy.com/v1"


def _headers() -> dict:
    """Default headers for Lemon Squeezy API calls."""
    return {
        "Accept": "application/vnd.api+json",
        "Content-Type": "application/vnd.api+json",
        "Authorization": f"Bearer {LS_API_KEY}",
    }


# ── Checkout creation ────────────────────────────────────────────────────────

async def create_checkout(
    variant_id: str,
    user_id: int,
    email: str,
    name: str,
    redirect_url: str | None = None,
) -> str:
    """Create a Lemon Squeezy checkout and return the checkout URL.

    Args:
        variant_id: The Lemon Squeezy variant ID for the plan.
        user_id: Your app's user ID — passed as custom_data so webhooks
                 can identify which user the event belongs to.
        email: Pre-fill the checkout email.
        name: Pre-fill the checkout name.
        redirect_url: Where to send the user after successful payment.

    Returns:
        The checkout URL to redirect the user to.
    """
    if not LS_API_KEY or not LS_STORE_ID:
        raise RuntimeError("Lemon Squeezy API key or store ID not configured")

    payload = {
        "data": {
            "type": "checkouts",
            "attributes": {
                "checkout_options": {
                    "button_color": "#7047EB",
                    "desc": True,
                    "media": True,
                    "logo": True,
                },
                "checkout_data": {
                    "email": email,
                    "name": name,
                    "custom": {
                        "user_id": str(user_id),
                    },
                },
            },
            "relationships": {
                "store": {
                    "data": {"type": "stores", "id": str(LS_STORE_ID)}
                },
                "variant": {
                    "data": {"type": "variants", "id": str(variant_id)}
                },
            },
        }
    }

    if redirect_url:
        payload["data"]["attributes"]["product_options"] = {
            "redirect_url": redirect_url
        }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{LS_BASE_URL}/checkouts",
            json=payload,
            headers=_headers(),
            timeout=15,
        )

    if resp.status_code not in (200, 201):
        logger.error(
            "Lemon Squeezy checkout creation failed: %s %s",
            resp.status_code,
            resp.text,
        )
        raise HTTPException(
            status_code=502,
            detail="Payment provider error — could not create checkout.",
        )

    data = resp.json()
    return data["data"]["attributes"]["url"]


# ── Webhook verification ─────────────────────────────────────────────────────

def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """Verify that a webhook payload genuinely came from Lemon Squeezy.

    Uses HMAC-SHA256 with the configured webhook secret.
    """
    if not LS_WEBHOOK_SECRET:
        logger.warning("LEMON_SQUEEZY_WEBHOOK_SECRET not set — skipping verification")
        return True

    expected = hmac.new(
        LS_WEBHOOK_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


# ── Webhook event handlers ───────────────────────────────────────────────────

def handle_order_created(data: dict[str, Any]) -> None:
    """Handle a one-time purchase (if you ever sell non-subscription products)."""
    custom = data.get("meta", {}).get("custom_data", {})
    user_id = custom.get("user_id")
    logger.info("Order created for user %s", user_id)


def handle_subscription_created(data: dict[str, Any], db_get, db_release) -> None:
    """Activate a subscription when Lemon Squeezy sends subscription_created."""
    custom = data.get("meta", {}).get("custom_data", {})
    user_id = custom.get("user_id")
    if not user_id:
        return

    subscription_id = data["data"]["id"]
    variant_id = data["data"]["attributes"]["variant_id"]
    ends_at = data["data"]["attributes"].get("ends_at")
    status = data["data"]["attributes"]["status"]

    conn = db_get()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE users
        SET subscription_status = %s,
            subscription_id = %s,
            subscription_plan = %s,
            subscription_ends_at = %s,
            lemon_squeezy_customer_id = %s
        WHERE id = %s;
        """,
        (
            status,
            subscription_id,
            str(variant_id),
            ends_at,
            str(data["data"]["attributes"].get("customer_id", "")),
            int(user_id),
        ),
    )
    conn.commit()
    cur.close()
    db_release(conn)
    logger.info("Subscription %s activated for user %s", subscription_id, user_id)


def handle_subscription_updated(data: dict[str, Any], db_get, db_release) -> None:
    """Sync subscription status on renewal, pause, or cancellation."""
    subscription_id = data["data"]["id"]
    status = data["data"]["attributes"]["status"]
    ends_at = data["data"]["attributes"].get("ends_at")

    conn = db_get()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE users
        SET subscription_status = %s,
            subscription_ends_at = %s
        WHERE subscription_id = %s;
        """,
        (status, ends_at, subscription_id),
    )
    conn.commit()
    cur.close()
    db_release(conn)
    logger.info("Subscription %s updated to %s", subscription_id, status)


def handle_subscription_cancelled(data: dict[str, Any], db_get, db_release) -> None:
    """Mark subscription as cancelled in our DB."""
    subscription_id = data["data"]["id"]
    ends_at = data["data"]["attributes"].get("ends_at")

    conn = db_get()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE users
        SET subscription_status = 'cancelled',
            subscription_ends_at = %s
        WHERE subscription_id = %s;
        """,
        (ends_at, subscription_id),
    )
    conn.commit()
    cur.close()
    db_release(conn)
    logger.info("Subscription %s cancelled", subscription_id)


# ── Router ───────────────────────────────────────────────────────────────────

def create_payments_router(get_db, release_db, get_current_user) -> APIRouter:
    """Create the payments router. Returns the router to be included in the app.

    Args:
        get_db: The get_db() function from main.py
        release_db: The release_db() function from main.py
        get_current_user: The get_current_user() function from main.py
    """
    router = APIRouter(prefix="/api/payments", tags=["payments"])

    @router.post("/checkout")
    async def create_user_checkout(
        request: Request,
        user=Depends(get_current_user),
    ):
        """Create a Lemon Squeezy checkout for the authenticated user.

        Body: {"plan": "monthly" | "annual"}
        Returns: {"checkout_url": "https://..."}
        """
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated.")

        body = await request.json()
        plan = body.get("plan", "monthly")

        if plan == "annual":
            variant_id = LS_VARIANT_ANNUAL
        else:
            variant_id = LS_VARIANT_MONTHLY

        if not variant_id:
            raise HTTPException(
                status_code=400,
                detail=f"Plan '{plan}' is not configured.",
            )

        checkout_url = await create_checkout(
            variant_id=variant_id,
            user_id=user["id"],
            email=user["email"],
            name=user.get("name", ""),
            redirect_url="https://compliancetrack.app/dashboard",
        )
        return {"checkout_url": checkout_url}

    @router.get("/subscription")
    async def get_subscription_status(user=Depends(get_current_user)):
        """Get the current user's subscription status."""
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated.")

        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT subscription_status, subscription_plan,
                   subscription_ends_at, subscription_id
            FROM users WHERE id = %s;
            """,
            (user["id"],),
        )
        row = cur.fetchone()
        cur.close()
        release_db(conn)

        if not row:
            return {"subscription_status": "none"}

        return {
            "subscription_status": row[0] or "none",
            "subscription_plan": row[1],
            "subscription_ends_at": row[2],
            "subscription_id": row[3],
        }

    @router.post("/webhook")
    async def webhook(request: Request):
        """Receive and process Lemon Squeezy webhooks.

        Verifies the signature, then dispatches to the right handler
        based on the event name.
        """
        raw_body = await request.body()
        signature = request.headers.get("X-Signature", "")

        if not verify_webhook_signature(raw_body, signature):
            raise HTTPException(status_code=401, detail="Invalid signature.")

        payload = await request.json()
        event_name = payload.get("meta", {}).get("event_name", "")

        if event_name == "order_created":
            handle_order_created(payload)
        elif event_name == "subscription_created":
            handle_subscription_created(payload, get_db, release_db)
        elif event_name == "subscription_updated":
            handle_subscription_updated(payload, get_db, release_db)
        elif event_name == "subscription_cancelled":
            handle_subscription_cancelled(payload, get_db, release_db)
        else:
            logger.info("Unhandled webhook event: %s", event_name)

        return {"status": "ok"}

    return router
