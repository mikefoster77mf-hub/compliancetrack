#!/usr/bin/env python3
"""One-time migration: add `timezone` column to the live `users` table.

Safe to run on a live database — if the column already exists it raises
a caught psycopg2.errors.DuplicateColumn and exits cleanly.
"""

import os
import psycopg2


def migrate():
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "db"),
        user=os.getenv("POSTGRES_USER", "myuser"),
        password=os.getenv("POSTGRES_PASSWORD", "mypassword"),
        dbname=os.getenv("POSTGRES_DB", "myapp"),
    )
    cur = conn.cursor()

    try:
        cur.execute("ALTER TABLE users ADD COLUMN timezone TEXT DEFAULT 'UTC';")
        conn.commit()
        print("OK: column 'users.timezone' added with default 'UTC'.")
    except psycopg2.errors.DuplicateColumn:
        conn.rollback()
        print("OK: column 'users.timezone' already exists — nothing to do.")
    except Exception as e:
        conn.rollback()
        print(f"FAILED: {e}")
        raise SystemExit(1)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    migrate()
