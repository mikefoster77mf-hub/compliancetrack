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
    # ── Columns needed by the upload endpoint ───────────────────────────────
    magic_token: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)


class CoiModel(Base):
    __tablename__ = "cois"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vendor_id: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    # ── Existing column uses BYTEA for the PDF binary ───────────────────────
    # ── upload endpoint also writes to disk, so we track the path separately ─
    pdf_data: Mapped[bytes | None] = mapped_column(Text, nullable=True)  # BYTEA→Text placeholder
    pdf_filename: Mapped[str] = mapped_column(String, default="")
    insurance_type: Mapped[str] = mapped_column(String, default="")
    expiring_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    issued_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[DateTime] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[DateTime] = mapped_column(DateTime, nullable=True)
    # ── Columns needed by the upload endpoint ───────────────────────────────
    pdf_path: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str | None] = mapped_column(String, nullable=True)
    notified_email: Mapped[str | None] = mapped_column(String, nullable=True)
    archived: Mapped[bool] = mapped_column(default=False)  # True = superseded by newer version


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
    #    Write to tmp FIRST so we don't lose the old file if the write fails.
    file_ext = os.path.splitext(file.filename)[1]  # always .pdf here
    new_uuid = uuid.uuid4()
    new_tmp_path = os.path.join(UPLOAD_DIR, f"{new_uuid}.pdf.tmp")
    new_final_path = os.path.join(UPLOAD_DIR, f"{new_uuid}{file_ext}")

    os.makedirs(UPLOAD_DIR, exist_ok=True)  # one-time, fast, sync is fine

    bytes_written = 0
    try:
        import aiofiles
        async with aiofiles.open(new_tmp_path, "wb") as buf:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                bytes_written += len(chunk)
                if bytes_written > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds {MAX_FILE_SIZE // (1024*1024)}MB limit",
                    )
                await buf.write(chunk)
        # Atomic rename — partial files are never visible at new_final_path
        os.replace(new_tmp_path, new_final_path)
    except HTTPException:
        # Clean up partial tmp file on size-exceeded abort
        if os.path.exists(new_tmp_path):
            os.remove(new_tmp_path)
        raise
    except Exception as e:
        # Clean up on any write failure
        if os.path.exists(new_tmp_path):
            os.remove(new_tmp_path)
        if os.path.exists(new_final_path):
            os.remove(new_final_path)
        raise HTTPException(status_code=500, detail=f"File storage failed: {e}")

    # 4. Archive the old active COI record for this vendor (if one exists)
    #    We do this BEFORE committing the new insert so the old record is
    #    safely superseded even if something fails after.
    old_coi_result = await db.execute(
        select(CoiModel).where(
            CoiModel.vendor_id == vendor_id,
            CoiModel.archived == False,
        ).order_by(CoiModel.created_at.desc())
    )
    old_coi = old_coi_result.scalar_one_or_none()

    old_pdf_path = None
    if old_coi:
        # Archive record: mark superseded, keep for audit trail
        old_coi.archived = True
        old_pdf_path = old_coi.pdf_path  # remember path so we can delete the file

    # 5. Insert the new COI record as the active version
    new_coi = CoiModel(
        vendor_id=vendor_id,
        user_id=vendor_user_id,  # owner of the vendor (from token lookup)
        pdf_path=new_final_path,
        pdf_filename=file.filename,
        status="GREEN",
        notified_email=vendor_email,
        created_at=func.now(),
        archived=False,
    )
    db.add(new_coi)
    await db.flush()  # get the new id without committing yet

    # 6. Delete the old PDF file from storage (if one existed)
    #    Safe to do after flush — old_coi is archived, new_coi is persisted.
    if old_pdf_path and os.path.exists(old_pdf_path):
        try:
            os.remove(old_pdf_path)
        except OSError:
            # Log but don't fail the upload — stale file on disk is not critical
            print(f"[warn] Could not delete old PDF: {old_pdf_path}")

    await db.commit()  # commit both the archive flag and the new insert

    # 7. Background email — fires AFTER the HTTP response is sent back to user
    background_tasks.add_task(
        send_async_email_notification,
        vendor_email=vendor_email,
        doc_name=file.filename,
    )

    # 8. Immediate response — user gets this right away; email work continues
    return {
        "status": "success",
        "message": "Certificate uploaded successfully. Processing in background.",
        "filename": os.path.basename(new_final_path),
        "replaced": old_coi is not None,
    }
