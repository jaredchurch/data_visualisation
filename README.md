# Data Visualisation

A self-hosted web app that lets you connect to PostgreSQL databases, run SELECT queries to ingest data into DuckDB, and render interactive bar/line/pie charts — all from a browser.

## Features

- **Email/password accounts** — JWT auth, bcrypt passwords, no external services needed
- **Objects** — organisational containers for connections, queries, and charts
- **PostgreSQL connections** — store multiple connections per object; test them before saving
- **Query ingestion** — run SELECT queries against Postgres and store results in DuckDB
- **Auto-join** — when multiple query results share column names, charts auto-FULL OUTER JOIN them
- **Charts** — bar, horizontal bar, line, pie, doughnut with configurable measure (`SUM(field)`, `COUNT(*)`, etc.) and dimension
- **DuckDB backend** — fast analytical queries on ingested data; stored in a Docker volume
- **Single-file SPA** — no build step; vanilla JS + Chart.js

## Quick start

```bash
git clone https://github.com/jaredchurch/data_visualisation
cd data_visualisation

# Set a real secret key in docker-compose.yml first, then:
docker compose up --build
```

Open http://localhost:8000 — create an account and start building.

## Usage flow

1. **Create an Object** (e.g. "Sales Dashboard")
2. **Add a Connection** → fill in your Postgres host/port/db/user/pass → Test it
3. **Add a Query** → pick the connection, write a SELECT, give it a target table name → Save
4. **Run the Query** → data is fetched from Postgres and stored in DuckDB
5. **Add a Chart** → choose measure (e.g. `SUM(revenue)`) and dimension (e.g. `product`) → View it

### Auto-join

If you have two queries whose result tables share column names (e.g. both have `product_id`), the chart builder will automatically `FULL OUTER JOIN` them on those shared columns. No SQL needed.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `DUCKDB_PATH` | `/data/app.duckdb` | Path to DuckDB file (inside container) |
| `SECRET_KEY` | *(insecure default)* | JWT signing secret — **change this** |

## Architecture

```
Dockerfile          — Debian bookworm + Python 3 + uvicorn
docker-compose.yml  — Service + named volume for DuckDB
requirements.txt
app/
  main.py           — FastAPI routes
  auth.py           — JWT auth helpers
  db.py             — DuckDB connection manager + schema init
  models.py         — Pydantic request/response schemas
  pg_connector.py   — Postgres runner + DuckDB ingest + join logic
  static/
    index.html      — SPA shell
    app.js          — Client-side router and API calls
    style.css       — Styles
```

## API

Full interactive docs at http://localhost:8000/api/docs once running.
