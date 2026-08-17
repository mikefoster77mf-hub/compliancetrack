from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os, socket, psycopg2, psycopg2.extras, time, bcrypt, itsdangerous, base64
from datetime import date, datetime, timedelta

app = FastAPI()

DB_HOST = os.getenv("DB_HOST", "db")
DB_USER = os.getenv("POSTGRES_USER", "myuser")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "mypassword")
DB_NAME = os.getenv("POSTGRES_DB", "myapp")

# ── Auth ─────────────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
_sig = itsdangerous.Signer(SECRET_KEY)

templates = Jinja2Templates(directory="/app/html/templates")

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()

def check_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())

def sign_user_id(user_id: int) -> str:
    return _sig.sign(str(user_id)).decode()

def unsign_user_id(token: str) -> int | None:
    try:
        return int(_sig.unsign(token.encode()).decode())
    except Exception:
        return None

async def get_current_user(request: Request) -> dict | None:
    """Read session cookie, look up user. Returns user dict or None."""
    token = request.cookies.get("session")
    if not token:
        return None
    user_id = unsign_user_id(token)
    if user_id is None:
        return None
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT id, email, name, created_at FROM users WHERE id = %s;", (user_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return dict(row)
    except Exception:
        pass
    return None


def get_db():
    return psycopg2.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASS, dbname=DB_NAME
    )


# ── API routes (registered first so they take priority over static mount) ──

@app.get("/api/health")
async def api_health():
    db_ok = False
    db_version = None
    db_latency_ms = None
    try:
        start = time.monotonic()
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT version();")
        db_version = cur.fetchone()[0]
        cur.close()
        conn.close()
        db_ok = True
        db_latency_ms = round((time.monotonic() - start) * 1000, 1)
    except Exception:
        pass

    status = "healthy" if db_ok else "degraded"
    return {
        "status": status,
        "db": {
            "connected": db_ok,
            "version": db_version,
            "latency_ms": db_latency_ms,
        },
    }


@app.get("/api/db-check")
async def api_db_check():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]
        cur.execute(
            "SELECT datname FROM pg_database WHERE datistemplate = false;"
        )
        dbs = [row[0] for row in cur.fetchall()]
        cur.close()
        conn.close()
        return {
            "database": DB_NAME,
            "connected": True,
            "postgresql_version": version,
            "databases": dbs,
        }
    except Exception as e:
        return {
            "database": DB_NAME,
            "connected": False,
            "error": str(e),
        }


@app.get("/api/db-items")
async def api_db_items():
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            """
        )
        cur.execute("SELECT id, name, created_at FROM items ORDER BY id;")
        rows = cur.fetchall()
        cur.close()
        conn.commit()
        conn.close()
        return {"items": [dict(r) for r in rows]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/db-seed")
async def api_db_seed():
    sample_items = [
        "Podman Compose Stack",
        "Nginx Reverse Proxy",
        "FastAPI Backend",
        "PostgreSQL Database",
        "mkcert TLS Certificate",
        "systemd Auto-start",
    ]
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            """
        )

        inserted = 0
        for name in sample_items:
            cur.execute(
                "INSERT INTO items (name) VALUES (%s) ON CONFLICT DO NOTHING RETURNING id;",
                (name,),
            )
            if cur.fetchone():
                inserted += 1

        cur.execute("SELECT id, name, created_at FROM items ORDER BY id;")
        rows = cur.fetchall()
        cur.close()
        conn.commit()
        conn.close()
        return {
            "seeded": inserted,
            "total": len(rows),
            "items": [dict(r) for r in rows],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/waitlist")
async def api_waitlist(data: dict):
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    company = (data.get("company") or "").strip()
    projects = (data.get("projects") or "").strip()

    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="A valid email address is required.")

    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS waitlist (
                id SERIAL PRIMARY KEY,
                name TEXT,
                email TEXT NOT NULL UNIQUE,
                company TEXT,
                projects TEXT,
                signed_up_at TIMESTAMPTZ DEFAULT NOW()
            );
            """
        )

        cur.execute(
            """
            INSERT INTO waitlist (name, email, company, projects)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (email) DO UPDATE SET
                name = EXCLUDED.name,
                company = EXCLUDED.company,
                projects = EXCLUDED.projects,
                signed_up_at = NOW()
            RETURNING id, name, email, company, projects, signed_up_at;
            """,
            (name, email, company, projects),
        )
        row = cur.fetchone()
        cur.close()
        conn.commit()
        conn.close()

        return {
            "status": "signed_up",
            "id": row["id"],
            "email": row["email"],
            "message": "You're on the list. We'll be in touch when we launch.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/auth/signup")
async def api_auth_signup(data: dict):
    email = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()
    name = (data.get("name") or "").strip()

    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="A valid email address is required.")
    if not password or len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    hashed = hash_password(password)

    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                name TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            """
        )

        cur.execute(
            "INSERT INTO users (email, password_hash, name) VALUES (%s, %s, %s) RETURNING id, email, name;",
            (email, hashed, name),
        )
        row = cur.fetchone()
        cur.close()
        conn.commit()
        conn.close()

        return {"id": row["id"], "email": row["email"], "name": row["name"]}
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/auth/login")
async def api_auth_login(data: dict, response: Response):
    email = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()

    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="A valid email address is required.")

    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT id, email, name, password_hash FROM users WHERE email = %s;", (email,))
        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row or not check_password(password, row["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid email or password.")

        user_id = row["id"]
        token = sign_user_id(user_id)

        response.set_cookie(
            key="session",
            value=token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=86400 * 30,
        )

        return {"id": user_id, "email": row["email"], "name": row["name"]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/auth/logout")
async def api_auth_logout(response: Response):
    response.delete_cookie(key="session")
    return {"status": "logged_out"}


@app.get("/api/auth/me")
async def api_auth_me(request: Request):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return {"id": user["id"], "email": user["email"], "name": user["name"]}


# ── Auth pages ────────────────────────────────────────────────────────────────

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "user": None, "error": None})


@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request, "user": None, "error": None})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    user = await get_current_user(request)
    if not user:
        return templates.TemplateResponse("login.html", {"request": request, "user": None, "error": "Please log in to continue."})
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": user})


# ── Vendor pages ─────────────────────────────────────────────────────────────

@app.get("/vendors", response_class=HTMLResponse)
async def vendors_list_page(request: Request):
    user = await get_current_user(request)
    if not user:
        return templates.TemplateResponse("login.html", {"request": request, "user": None, "error": "Please log in to continue."})
    return templates.TemplateResponse("vendors/list.html", {"request": request, "user": user})


@app.get("/vendors/add", response_class=HTMLResponse)
async def vendors_add_page(request: Request):
    user = await get_current_user(request)
    if not user:
        return templates.TemplateResponse("login.html", {"request": request, "user": None, "error": "Please log in to continue."})
    return templates.TemplateResponse("vendors/add.html", {"request": request, "user": user})


@app.get("/vendors/{vendor_id}", response_class=HTMLResponse)
async def vendors_detail_page(request: Request, vendor_id: int):
    user = await get_current_user(request)
    if not user:
        return templates.TemplateResponse("login.html", {"request": request, "user": None, "error": "Please log in to continue."})
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT id, name, email, phone, address, notes, created_at, updated_at FROM vendors WHERE id = %s AND user_id = %s;", (vendor_id, user["id"]))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return templates.TemplateResponse("dashboard.html", {"request": request, "user": user, "error": "Vendor not found."})
        return templates.TemplateResponse("vendors/detail.html", {"request": request, "user": user, "vendor": dict(row)})
    except Exception:
        return templates.TemplateResponse("dashboard.html", {"request": request, "user": user, "error": "Could not load vendor."})


@app.get("/vendors/{vendor_id}/edit", response_class=HTMLResponse)
async def vendors_edit_page(request: Request, vendor_id: int):
    user = await get_current_user(request)
    if not user:
        return templates.TemplateResponse("login.html", {"request": request, "user": None, "error": "Please log in to continue."})
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT id, name, email, phone, address, notes, created_at, updated_at FROM vendors WHERE id = %s AND user_id = %s;", (vendor_id, user["id"]))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return templates.TemplateResponse("dashboard.html", {"request": request, "user": user, "error": "Vendor not found."})
        return templates.TemplateResponse("vendors/edit.html", {"request": request, "user": user, "vendor": dict(row)})
    except Exception:
        return templates.TemplateResponse("dashboard.html", {"request": request, "user": user, "error": "Could not load vendor."})


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    user = await get_current_user(request)
    if not user:
        return templates.TemplateResponse("login.html", {"request": request, "user": None, "error": "Please log in to continue."})
    return templates.TemplateResponse("settings.html", {"request": request, "user": user})


@app.get("/vendors/{vendor_id}/cois", response_class=HTMLResponse)
async def cois_list_page(request: Request, vendor_id: int):
    user = await get_current_user(request)
    if not user:
        return templates.TemplateResponse("login.html", {"request": request, "user": None, "error": "Please log in to continue."})
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT id, name FROM vendors WHERE id = %s AND user_id = %s;", (vendor_id, user["id"]))
        vendor = cur.fetchone()
        cur.close()
        conn.close()
        if not vendor:
            return templates.TemplateResponse("dashboard.html", {"request": request, "user": user, "error": "Vendor not found."})
        return templates.TemplateResponse("cois/list.html", {"request": request, "user": user, "vendor_id": vendor_id, "vendor_name": vendor["name"]})
    except Exception:
        return templates.TemplateResponse("dashboard.html", {"request": request, "user": user, "error": "Could not load COIs."})


@app.get("/vendors/{vendor_id}/cois/add", response_class=HTMLResponse)
async def cois_upload_page(request: Request, vendor_id: int):
    user = await get_current_user(request)
    if not user:
        return templates.TemplateResponse("login.html", {"request": request, "user": None, "error": "Please log in to continue."})
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT id, name FROM vendors WHERE id = %s AND user_id = %s;", (vendor_id, user["id"]))
        vendor = cur.fetchone()
        cur.close()
        conn.close()
        if not vendor:
            return templates.TemplateResponse("dashboard.html", {"request": request, "user": user, "error": "Vendor not found."})
        return templates.TemplateResponse("cois/upload.html", {"request": request, "user": user, "vendor_id": vendor_id, "vendor_name": vendor["name"]})
    except Exception:
        return templates.TemplateResponse("dashboard.html", {"request": request, "user": user, "error": "Could not load COI form."})


# ── Vendors API ──────────────────────────────────────────────────────────────

@app.get("/api/vendors")
async def api_vendors(request: Request):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated.")

    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS vendors (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                email TEXT DEFAULT '',
                phone TEXT DEFAULT '',
                address TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
            """
        )
        cur.execute(
            "SELECT id, name, email, phone, address, notes, created_at, updated_at FROM vendors WHERE user_id = %s ORDER BY name;",
            (user["id"],),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return {"vendors": [dict(r) for r in rows]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/vendors")
async def api_vendors_create(data: dict, request: Request):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated.")

    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    phone = (data.get("phone") or "").strip()
    address = (data.get("address") or "").strip()
    notes = (data.get("notes") or "").strip()

    if not name:
        raise HTTPException(status_code=400, detail="Vendor name is required.")

    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS vendors (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                email TEXT DEFAULT '',
                phone TEXT DEFAULT '',
                address TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
            """
        )
        cur.execute(
            "INSERT INTO vendors (user_id, name, email, phone, address, notes) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id, name, email, phone, address, notes, created_at, updated_at;",
            (user["id"], name, email, phone, address, notes),
        )
        row = cur.fetchone()
        cur.close()
        conn.commit()
        conn.close()
        return {"id": row["id"], "name": row["name"], "email": row["email"], "phone": row["phone"], "address": row["address"], "notes": row["notes"], "created_at": row["created_at"], "updated_at": row["updated_at"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/vendors/{vendor_id}")
async def api_vendors_get(request: Request, vendor_id: int):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated.")

    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT id, name, email, phone, address, notes, created_at, updated_at FROM vendors WHERE id = %s AND user_id = %s;",
            (vendor_id, user["id"]),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="Vendor not found.")
        return {"id": row["id"], "name": row["name"], "email": row["email"], "phone": row["phone"], "address": row["address"], "notes": row["notes"], "created_at": row["created_at"], "updated_at": row["updated_at"]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/vendors/{vendor_id}")
async def api_vendors_update(request: Request, vendor_id: int, data: dict):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated.")

    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    phone = (data.get("phone") or "").strip()
    address = (data.get("address") or "").strip()
    notes = (data.get("notes") or "").strip()

    if not name:
        raise HTTPException(status_code=400, detail="Vendor name is required.")

    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "UPDATE vendors SET name = %s, email = %s, phone = %s, address = %s, notes = %s, updated_at = NOW() WHERE id = %s AND user_id = %s RETURNING id, name, email, phone, address, notes, created_at, updated_at;",
            (name, email, phone, address, notes, vendor_id, user["id"]),
        )
        row = cur.fetchone()
        cur.close()
        conn.commit()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="Vendor not found.")
        return {"id": row["id"], "name": row["name"], "email": row["email"], "phone": row["phone"], "address": row["address"], "notes": row["notes"], "created_at": row["created_at"], "updated_at": row["updated_at"]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/vendors/{vendor_id}")
async def api_vendors_delete(request: Request, vendor_id: int):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated.")

    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "DELETE FROM vendors WHERE id = %s AND user_id = %s RETURNING id;",
            (vendor_id, user["id"]),
        )
        row = cur.fetchone()
        cur.close()
        conn.commit()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="Vendor not found.")
        return {"status": "deleted", "id": vendor_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── COIs API ────────────────────────────────────────────────────────────────

@app.get("/api/cois")
async def api_cois(request: Request, vendor_id: int | None = None):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated.")

    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS cois (
                id SERIAL PRIMARY KEY,
                vendor_id INTEGER NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                pdf_data BYTEA DEFAULT NULL,
                pdf_filename TEXT DEFAULT '',
                insurance_type TEXT DEFAULT '',
                expiring_date DATE DEFAULT NULL,
                issued_date DATE DEFAULT NULL,
                notes TEXT DEFAULT '',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
            """
        )

        if vendor_id:
            cur.execute(
                "SELECT c.id, c.vendor_id, c.insurance_type, c.expiring_date, c.issued_date, c.notes, c.created_at, c.updated_at, v.name AS vendor_name FROM cois c JOIN vendors v ON c.vendor_id = v.id WHERE c.vendor_id = %s AND c.user_id = %s ORDER BY c.expiring_date;",
                (vendor_id, user["id"]),
            )
        else:
            cur.execute(
                "SELECT c.id, c.vendor_id, c.insurance_type, c.expiring_date, c.issued_date, c.notes, c.created_at, c.updated_at, v.name AS vendor_name FROM cois c JOIN vendors v ON c.vendor_id = v.id WHERE c.user_id = %s ORDER BY c.expiring_date;",
                (user["id"],),
            )

        rows = cur.fetchall()
        cur.close()
        conn.close()
        result = []
        for r in rows:
            d = dict(r)
            if d.get("expiring_date"):
                d["expiring_date"] = d["expiring_date"].isoformat()
            if d.get("issued_date"):
                d["issued_date"] = d["issued_date"].isoformat()
            if d.get("created_at"):
                d["created_at"] = d["created_at"].isoformat()
            d["pdf_data"] = bool(d.get("pdf_data"))
            # Status
            status_color = "var(--text-hinting)"
            status_bg = "var(--surface-elevated)"
            status_label = "No date"
            if d.get("expiring_date"):
                exp = date.fromisoformat(d["expiring_date"])
                if exp < date.today():
                    status_color = "var(--error)"
                    status_bg = "var(--surface-error)"
                    status_label = "Expired"
                elif exp <= date.today() + timedelta(days=30):
                    status_color = "var(--warning)"
                    status_bg = "var(--surface-warning)"
                    status_label = "Expiring soon"
                else:
                    status_color = "var(--success)"
                    status_bg = "var(--surface-success)"
                    status_label = "Valid"
            d["status_color"] = status_color
            d["status_bg"] = status_bg
            d["status_label"] = status_label
            result.append(d)
        return {"cois": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/cois")
async def api_cois_create(
    request: Request,
    vendor_id: int,
    insurance_type: str = "",
    expiring_date: str = "",
    issued_date: str = "",
    notes: str = "",
    pdf: bytes | None = None,
):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated.")

    # Verify vendor ownership
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id FROM vendors WHERE id = %s AND user_id = %s;", (vendor_id, user["id"]))
    vendor = cur.fetchone()
    if not vendor:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Vendor not found.")

    pdf_data = None
    pdf_filename = ""
    if pdf:
        pdf_data = base64.b64encode(pdf).decode()
        pdf_filename = getattr(pdf, "filename", "certificate.pdf") or "certificate.pdf"

    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS cois (
                id SERIAL PRIMARY KEY,
                vendor_id INTEGER NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                pdf_data BYTEA DEFAULT NULL,
                pdf_filename TEXT DEFAULT '',
                insurance_type TEXT DEFAULT '',
                expiring_date DATE DEFAULT NULL,
                issued_date DATE DEFAULT NULL,
                notes TEXT DEFAULT '',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
            """
        )

        expiring = None
        if expiring_date:
            try:
                expiring = datetime.strptime(expiring_date, "%Y-%m-%d").date()
            except Exception:
                pass

        issued = None
        if issued_date:
            try:
                issued = datetime.strptime(issued_date, "%Y-%m-%d").date()
            except Exception:
                pass

        cur.execute(
            "INSERT INTO cois (vendor_id, user_id, pdf_data, pdf_filename, insurance_type, expiring_date, issued_date, notes) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id, vendor_id, insurance_type, expiring_date, issued_date, notes, created_at, updated_at;",
            (vendor_id, user["id"], pdf_data, pdf_filename, insurance_type, expiring, issued, notes),
        )
        row = cur.fetchone()
        cur.close()
        conn.commit()
        conn.close()

        return {
            "id": row["id"],
            "vendor_id": row["vendor_id"],
            "insurance_type": row["insurance_type"],
            "expiring_date": row["expiring_date"].isoformat() if row["expiring_date"] else None,
            "issued_date": row["issued_date"].isoformat() if row["issued_date"] else None,
            "notes": row["notes"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/cois/{coi_id}")
async def api_cois_get(request: Request, coi_id: int):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated.")

    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT c.id, c.vendor_id, c.pdf_data, c.pdf_filename, c.insurance_type,
                   c.expiring_date, c.issued_date, c.notes, c.created_at, c.updated_at,
                   v.name AS vendor_name
            FROM cois c JOIN vendors v ON c.vendor_id = v.id
            WHERE c.id = %s AND c.user_id = %s;
            """,
            (coi_id, user["id"]),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="COI not found.")
        result = dict(row)
        if result["expiring_date"]:
            result["expiring_date"] = result["expiring_date"].isoformat()
        if result["issued_date"]:
            result["issued_date"] = result["issued_date"].isoformat()
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/cois/{coi_id}/download")
async def api_cois_download(request: Request, coi_id: int):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated.")

    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT pdf_data, pdf_filename FROM cois WHERE id = %s AND user_id = %s;",
            (coi_id, user["id"]),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row or not row["pdf_data"]:
            raise HTTPException(status_code=404, detail="COI not found or no PDF uploaded.")
        pdf_bytes = base64.b64decode(row["pdf_data"])
        filename = row["pdf_filename"] or "certificate.pdf"
        return Response(content=pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=\"{filename}\""})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/cois/{coi_id}")
async def api_cois_delete(request: Request, coi_id: int):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated.")

    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "DELETE FROM cois WHERE id = %s AND user_id = %s RETURNING id;",
            (coi_id, user["id"]),
        )
        row = cur.fetchone()
        cur.close()
        conn.commit()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="COI not found.")
        return {"status": "deleted", "id": coi_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Dashboard stats API ────────────────────────────────────────────────────

@app.get("/api/dashboard")
async def api_dashboard(request: Request):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated.")

    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Ensure tables exist
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS cois (
                id SERIAL PRIMARY KEY,
                vendor_id INTEGER NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                pdf_data BYTEA DEFAULT NULL,
                pdf_filename TEXT DEFAULT '',
                insurance_type TEXT DEFAULT '',
                expiring_date DATE DEFAULT NULL,
                issued_date DATE DEFAULT NULL,
                notes TEXT DEFAULT '',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS vendors (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                email TEXT DEFAULT '',
                phone TEXT DEFAULT '',
                address TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
            """
        )

        today = date.today()
        thirty_days = today + timedelta(days=30)

        # Counts
        cur.execute("SELECT COUNT(*) AS cnt FROM vendors WHERE user_id = %s;", (user["id"],))
        vendor_count = cur.fetchone()["cnt"]

        cur.execute("SELECT COUNT(*) AS cnt FROM cois WHERE user_id = %s;", (user["id"],))
        coi_count = cur.fetchone()["cnt"]

        cur.execute("SELECT COUNT(*) AS cnt FROM cois WHERE user_id = %s AND expiring_date IS NOT NULL AND expiring_date <= %s;", (user["id"], thirty_days))
        expiring_soon_or_expired = cur.fetchone()["cnt"]

        cur.execute("SELECT COUNT(*) AS cnt FROM cois WHERE user_id = %s AND expiring_date IS NOT NULL AND expiring_date < %s;", (user["id"], today))
        expired = cur.fetchone()["cnt"]

        valid = coi_count - expiring_soon_or_expired

        # Expiring soon list (not yet expired)
        cur.execute(
            """
            SELECT c.id, c.vendor_id, c.insurance_type, c.expiring_date, v.name AS vendor_name
            FROM cois c JOIN vendors v ON c.vendor_id = v.id
            WHERE c.user_id = %s AND c.expiring_date IS NOT NULL AND c.expiring_date >= %s AND c.expiring_date <= %s
            ORDER BY c.expiring_date
            LIMIT 10;
            """,
            (user["id"], today, thirty_days),
        )
        expiring_soon_list = [dict(r) for r in cur.fetchall()]
        for item in expiring_soon_list:
            if item["expiring_date"]:
                item["expiring_date"] = item["expiring_date"].isoformat()

        # Recent COIs
        cur.execute(
            """
            SELECT c.id, c.vendor_id, c.insurance_type, c.expiring_date, v.name AS vendor_name
            FROM cois c JOIN vendors v ON c.vendor_id = v.id
            WHERE c.user_id = %s
            ORDER BY c.created_at DESC
            LIMIT 10;
            """,
            (user["id"],),
        )
        recent_cois = [dict(r) for r in cur.fetchall()]
        for item in recent_cois:
            if item["expiring_date"]:
                item["expiring_date"] = item["expiring_date"].isoformat()

        cur.close()
        conn.close()

        return {
            "stats": {
                "vendor_count": vendor_count,
                "coi_count": coi_count,
                "expiring_soon": expiring_soon_or_expired - expired,
                "expired": expired,
                "valid": max(0, valid),
            },
            "expiring_soon_list": expiring_soon_list,
            "recent_cois": recent_cois,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Settings API ────────────────────────────────────────────────────────────

@app.get("/api/settings")
async def api_settings(request: Request):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated.")

    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS reminder_settings (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                days_before_expiry INTEGER NOT NULL DEFAULT 30,
                email_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
            """
        )
        cur.execute("SELECT days_before_expiry, email_enabled, updated_at FROM reminder_settings WHERE user_id = %s;", (user["id"],))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return {"days_before_expiry": row["days_before_expiry"], "email_enabled": row["email_enabled"], "updated_at": row["updated_at"]}
        return {"days_before_expiry": 30, "email_enabled": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/settings")
async def api_settings_update(request: Request, data: dict):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated.")

    days = data.get("days_before_expiry", 30)
    email_enabled = data.get("email_enabled", True)
    if not isinstance(days, int) or days < 1:
        days = 30
    if not isinstance(email_enabled, bool):
        email_enabled = True

    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS reminder_settings (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                days_before_expiry INTEGER NOT NULL DEFAULT 30,
                email_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
            """
        )
        cur.execute(
            "INSERT INTO reminder_settings (user_id, days_before_expiry, email_enabled) VALUES (%s, %s, %s) ON CONFLICT (user_id) DO UPDATE SET days_before_expiry = %s, email_enabled = %s, updated_at = NOW() RETURNING days_before_expiry, email_enabled, updated_at;",
            (user["id"], days, email_enabled, days, email_enabled),
        )
        row = cur.fetchone()
        cur.close()
        conn.commit()
        conn.close()
        return {"days_before_expiry": row["days_before_expiry"], "email_enabled": row["email_enabled"], "updated_at": row["updated_at"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Static files ────────────────────────────────────────────────────────────
# Mounted AFTER API routes so API paths take priority.
app.mount("/", StaticFiles(directory="/app/html", html=True), name="static")
