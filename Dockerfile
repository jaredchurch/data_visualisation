FROM debian:bookworm-slim

# ── System deps ───────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv \
    libpq-dev gcc \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ── Python env ────────────────────────────────────────────────────────────────
WORKDIR /app
COPY requirements.txt .
RUN python3 -m venv /venv \
 && /venv/bin/pip install --upgrade pip \
 && /venv/bin/pip install --no-cache-dir -r requirements.txt

ENV PATH="/venv/bin:$PATH"

# ── App source ────────────────────────────────────────────────────────────────
COPY app/ ./app/

# ── Data directory (DuckDB files live here; mount as a volume) ─────────────────
RUN mkdir -p /data && chmod 777 /data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
