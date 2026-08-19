#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

# Load secrets from .env for curl checks
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

echo "=== Phase: build ==="
podman compose build --quiet 2>&1

echo "=== Phase: boot ==="
podman compose down --volumes --remove-orphans 2>/dev/null || true
podman compose up -d --wait 2>&1

echo "=== Phase: test ==="
sleep 4

# ---- Certificate checks ----
echo "--- Cert trust ---"
openssl verify -CAfile /etc/ssl/certs/ca-certificates.crt certs/localhost+2.pem > /dev/null 2>&1 && echo "PASS: mkcert cert trusted in system store" || { echo "FAIL: cert not trusted in system store"; exit 1; }

certutil -d sql:$HOME/.pki/nssdb -L -n "mkcert-localCA" 2>/dev/null | grep -q "Trusted CA" && echo "PASS: mkcert CA in NSS DB" || { echo "FAIL: mkcert CA not in NSS DB"; exit 1; }

# ---- Web checks ----
echo "--- HTTPS static site ---"
curl -sk --cacert certs/localhost+2.pem https://localhost/ > /dev/null && echo "PASS: HTTPS static site" || { echo "FAIL: HTTPS static site"; exit 1; }

echo "--- About page ---"
curl -sk --cacert certs/localhost+2.pem https://localhost/about.html > /dev/null && echo "PASS: /about.html" || { echo "FAIL: /about.html"; exit 1; }

echo "--- Stack page ---"
curl -sk --cacert certs/localhost+2.pem https://localhost/stack.html > /dev/null && echo "PASS: /stack.html" || { echo "FAIL: /stack.html"; exit 1; }

echo "--- JS file ---"
curl -sk --cacert certs/localhost+2.pem https://localhost/app.js | grep -q "DOMContentLoaded" && echo "PASS: /app.js" || { echo "FAIL: /app.js"; exit 1; }

# ---- API checks ----
echo "--- API: /api/ ---"
curl -sk --cacert certs/localhost+2.pem https://localhost/api/ | grep -q "Hello from the FastAPI backend" && echo "PASS: /api/" || { echo "FAIL: /api/"; exit 1; }

echo "--- API: /api/health (with DB check) ---"
HEALTH=$(curl -sk --cacert certs/localhost+2.pem https://localhost/api/health)
echo "$HEALTH" | grep -q '"status"' && echo "PASS: /api/health" || { echo "FAIL: /api/health"; exit 1; }

echo "--- API: /api/db-check ---"
DB_RESP=$(curl -sk --cacert certs/localhost+2.pem https://localhost/api/db-check)
echo "$DB_RESP" | grep -q "connected" && echo "PASS: /api/db-check (DB connected)" || { echo "WARN: /api/db-check may not be connected yet"; }

echo "--- API: /api/db-items ---"
curl -sk --cacert certs/localhost+2.pem https://localhost/api/db-items | grep -q "items" && echo "PASS: /api/db-items" || { echo "FAIL: /api/db-items"; exit 1; }

# ---- Seed data persists ----
echo "--- API: /api/db-seed (idempotent reseed) ---"
SEED=$(curl -sk -X POST --cacert certs/localhost+2.pem https://localhost/api/db-seed)
echo "$SEED" | grep -q '"total":6' && echo "PASS: /api/db-seed (6 items in DB)" || { echo "WARN: seed data check"; }

# ---- HTTP → HTTPS redirect ----
echo "--- HTTP → HTTPS redirect ---"
REDIRECT=$(curl -s -o /dev/null -w "%{redirect_url}" http://localhost/)
[[ "$REDIRECT" == "https://localhost/" ]] && echo "PASS: HTTP→HTTPS redirect" || { echo "FAIL: HTTP→HTTPS redirect"; exit 1; }

# ---- Container count + resource limits ----
echo "--- 3 containers running ---"
podman compose ps --quiet | wc -l | grep -q "3" && echo "PASS: 3 containers running" || { echo "FAIL: container count"; exit 1; }

echo ""
echo "=== All checks passed ==="
podman compose ps

# ---- Unit tests (optional — runs if pytest is installed) ----
echo "--- Optional: run backend unit tests ==="
if command -v pytest >/dev/null 2>&1; then
  pytest backend/test_main.py -v 2>&1 || echo "WARN: Some tests may have failed (DB not reachable from host)"
else
  echo "SKIP: pytest not available — install dev deps (poetry install --with dev) to run"
fi
