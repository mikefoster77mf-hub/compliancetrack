FROM python:3.11-slim

WORKDIR /app

# Python deps
COPY backend/pyproject.toml .
RUN pip install --no-cache-dir fastapi uvicorn[standard] psycopg2-binary

# App code
COPY backend/main.py .
COPY html/ /app/html/

EXPOSE 8000

# Run uvicorn only — Render terminates TLS at the edge
CMD uvicorn main:app --host 0.0.0.0 --port 8000
