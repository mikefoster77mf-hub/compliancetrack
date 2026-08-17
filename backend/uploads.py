import os
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Depends
from sqlalchemy import select, insert, update, text, func
from sqlalchemy.ext.asyncio import AsyncSession
from async_db import get_async_db, Base

router = APIRouter(prefix="/api/v1", tags=["uploads"])

UPLOAD_DIR = "uploaded_cois"
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB cap for COI PDFs


# ── ORM models (match existing psycopg2 schema + columns needed by upload) ─

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, Date, DateTime, Text


class VendorModel(Base):
    __tablename__ = "vendors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, default="")
    phone: Mapped[str] = mapped_column(String, default="")
    address: Mapped[str] = mapped_column(String, default="")
    notes: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[DateTime] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[DateTime] = mapped_column(DateTime, nullable=True)
    # ── Columns needed by the upload endpoint (add to DB if not present) ──
    magic_token: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)


class CoiModel(Base):
    __tablename__ = "cois"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vendor_id: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    # ── Existing column uses BYTEA for the PDF binary; upload endpoint also ─
    # ── writes to disk, so we track the file path separately.                ─
    pdf_data: Mapped[bytes | None] = mapped_column(Text, nullable=True)  # BYTEA→Text placeholder
    pdf_filename: Mapped[str] = mapped_column(String, default="")
    insurance_type: Mapped[str] = mapped_column(String, default="")
    expiring_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    issued_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[DateTime] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[DateTime] = mapped_column(DateTime, nullable=True)
    # ── Columns needed by the upload endpoint (add to DB if not present) ──
    pdf_path: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str | None] = mapped_column(String, nullable=True)
    notified_email: Mapped[str | None] = mapped_column(String, nullable=True)


# ── Async email dispatch (runs in background AFTER response) ──────────────

async def send_async_email_notification(vendor_email: str, doc_name: str):
    """Fire-and-forget email. Runs in background task — never blocks the request.

    Replace the print with real aiosmtplib / Resend / SendGrid call when ready.
    """
    print(f"[background] Sending compliance notification email to {vendor_email} "
          f"for {doc_name}")


# ── Upload endpoint ────────────────────────────────────────────────────────

@router.post("/upload/{token}")
async def upload_coi_document(
    token: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_db),
):
    # 1. Quick extension check — in-memory, non-blocking
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF certificates are accepted.")

    # 2. Token → vendor lookup — native async SQLAlchemy, no thread needed
    result = await db.execute(
        select(VendorModel.id, VendorModel.user_id, VendorModel.email, VendorModel.name).where(
            VendorModel.magic_token == token
        )
    )
    vendor = result.fetchone()
    if not vendor:
        raise HTTPException(status_code=404, detail="Invalid magic link.")
    vendor_id, vendor_user_id, vendor_email, vendor_name = vendor

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

    # 4. DB status update — native async SQLAlchemy insert
    await db.execute(
        insert(CoiModel).values(
            vendor_id=vendor_id,
            user_id=vendor_user_id,  # owner of the vendor (from token lookup)
            pdf_path=final_path,
            pdf_filename=file.filename,
            status="GREEN",
            notified_email=vendor_email,
            created_at=func.now(),
        )
    )
    await db.commit()  # explicit commit — get_async_db also commits on yield, but we need it now

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
