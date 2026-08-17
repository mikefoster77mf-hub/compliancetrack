FROM python:3.11-slim

WORKDIR /app

# Python deps (install from pyproject.toml so new deps are picked up)
COPY backend/pyproject.toml .
RUN pip install --no-cache-dir bcrypt itsdangerous jinja2 python-multipart fastapi uvicorn[standard] psycopg2-binary

# App code
COPY backend/main.py .
COPY backend/scheduler.py .
COPY backend/reminders.py .
# HTML (served by FastAPI StaticFiles) — bust Docker layer cache on every build
COPY html/ /app/html/
COPY Dockerfile /app/Dockerfile

EXPOSE 8000

# Run uvicorn only — Render terminates TLS at the edge
# (rebuild trigger: force cache invalidation after HTML fixes)
CMD uvicorn main:app --host 0.0.0.0 --port 8000 --forwarded-allow-ips="*"
