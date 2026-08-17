import os
import uuid
import asyncio
import psycopg2
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks

router = APIRouter(prefix="/api/v1", tags=["uploads"])

UPLOAD_DIR = "uploaded_cois"
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB cap for COI PDFs


# ── DB helper (self-contained, no circular import with main.py) ────────────

def get_db():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "db"),
        user=os.getenv("POSTGRES_USER", "myuser"),
        password=os.getenv("POSTGRES_PASSWORD", "mypassword"),
        dbname=os.getenv("POSTGRES_DB", "myapp"),
    )


# ── Async email dispatch (runs in background AFTER response) ──────────────

async def send_async_email_notification(vendor_email: str, doc_name: str):
    """Fire-and-forget email. Runs in background task — never blocks the request.

    Replace the print with real aiosmtplib / Resend / SendGrid call when ready.
    This function is already async — just await your email client inside.
    """
    print(f"[background] Sending compliance notification email to {vendor_email} "
          f"for {doc_name}")


# ── Upload endpoint ────────────────────────────────────────────────────────

@router.post("/upload/{token}")
async def upload_coi_document(
    token: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    # 1. Quick extension check — in-memory, non-blocking
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF certificates are accepted.")

    # 2. Token → vendor lookup — DB call in a thread, never blocks the event loop
    vendor = await asyncio.to_thread(_lookup_vendor_by_token, token)
    if not vendor:
        raise HTTPException(status_code=404, detail="Invalid magic link.")
    vendor_email = vendor["email"]

    # 3. Secure async file write — atomic tmp + rename, 1MB chunks
    file_ext = os.path.splitext(file.filename)[1]  # always .pdf here
    unique_name = f"{uuid.uuid4()}{file_ext}"
    tmp_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}.pdf.tmp")
    final_path = os.path.join(UPLOAD_DIR, unique_name)

    os.makedirs(UPLOAD_DIR, exist_ok=True)  # one-time, fast, sync is fine

    bytes_written = 0
    try:
        import aiofiles
        async with aiofiles.open(tmp_path, "wb") as buf:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                bytes_written += len(chunk)
                if bytes_written > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds {MAX_FILE_SIZE // (1024*1024)}MB limit",
                    )
                await buf.write(chunk)
        # Atomic rename — partial files are never visible at final_path
        os.replace(tmp_path, final_path)
    except HTTPException:
        # Clean up partial tmp file on size-exceeded abort
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise
    except Exception as e:
        # Clean up on any write failure
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        if os.path.exists(final_path):
            os.remove(final_path)
        raise HTTPException(status_code=500, detail=f"File storage failed: {e}")

    # 4. DB status update — also off the event loop (sync psycopg2 in a thread)
    await asyncio.to_thread(
        _update_coi_status, vendor["id"], final_path, vendor_email
    )

    # 5. Background email — fires AFTER the HTTP response is sent back to user
    background_tasks.add_task(
        send_async_email_notification,
        vendor_email=vendor_email,
        doc_name=file.filename,
    )

    # 6. Immediate response — user gets this right away; email/db work continues
    return {
        "status": "success",
        "message": "Certificate uploaded successfully. Processing in background.",
        "filename": unique_name,
    }


# ── Sync DB helpers (run in threads, never on the event loop) ─────────────

def _lookup_vendor_by_token(token: str) -> dict | None:
    """Sync psycopg2 lookup — called via asyncio.to_thread in the endpoint.

    Replace the query with your actual token→vendor mapping.
    Expected columns: vendors.magic_token TEXT, vendors.email TEXT, vendors.id SERIAL.
    """
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, email, name FROM vendors WHERE magic_token = %s;",
            (token,),
        )
        row = cur.fetchone()
        cur.close()
        if row:
            return {"id": row[0], "email": row[1], "name": row[2]}
    finally:
        conn.close()
    return None


def _update_coi_status(vendor_id: int, file_path: str, vendor_email: str):
    """Sync psycopg2 update — called via asyncio.to_thread in the endpoint.

    Inserts a record into the cois table tracking the uploaded file.
    Adjust the table/column names to match your schema.
    """
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO cois (vendor_id, pdf_path, status, notified_email, created_at)
            VALUES (%s, %s, 'GREEN', %s, NOW())
            ON CONFLICT (vendor_id, pdf_path) DO UPDATE SET status = 'GREEN';
            """,
            (vendor_id, file_path, vendor_email),
        )
        conn.commit()
        cur.close()
    finally:
        conn.close()
