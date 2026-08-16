FROM python:3.11-slim

WORKDIR /app

# ── Python deps ──
COPY backend/pyproject.toml .
RUN pip install --no-cache-dir fastapi uvicorn psycopg2-binary

# ── App code ──
COPY backend/main.py .
COPY html/ /usr/share/nginx/html/
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80 443 8000

# Run nginx + uvicorn
CMD nginx && uvicorn main:app --host 0.0.0.0 --port 8000
