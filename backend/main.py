from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os, socket, psycopg2, psycopg2.extras, time

app = FastAPI()

DB_HOST = os.getenv("DB_HOST", "db")
DB_USER = os.getenv("POSTGRES_USER", "myuser")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "mypassword")
DB_NAME = os.getenv("POSTGRES_DB", "myapp")


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


# ── Static files ────────────────────────────────────────────────────────────
# Mounted AFTER API routes so API paths take priority.
app.mount("/", StaticFiles(directory="/app/html", html=True), name="static")
