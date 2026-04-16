"""
Data Visualisation App — FastAPI entry point.

Routes
──────
POST /api/auth/register
POST /api/auth/login

GET  /api/objects
POST /api/objects
GET  /api/objects/{oid}
DELETE /api/objects/{oid}

GET  /api/objects/{oid}/connections
POST /api/objects/{oid}/connections
DELETE /api/objects/{oid}/connections/{cid}
POST /api/objects/{oid}/connections/{cid}/test

GET  /api/objects/{oid}/queries
POST /api/objects/{oid}/queries
DELETE /api/objects/{oid}/queries/{qid}
POST /api/objects/{oid}/queries/{qid}/run

GET  /api/objects/{oid}/tables

GET  /api/objects/{oid}/charts
POST /api/objects/{oid}/charts
DELETE /api/objects/{oid}/charts/{chid}
GET  /api/objects/{oid}/charts/{chid}/data

GET  / → serves SPA
"""

from __future__ import annotations
from datetime import datetime
from typing import List

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .db import get_conn, init_db
from .auth import (
    current_user, create_user, get_user_by_email,
    verify_password, create_token
)
from .models import (
    RegisterRequest, LoginRequest, TokenResponse,
    ObjectCreate, ObjectOut,
    ConnectionCreate, ConnectionOut,
    QueryCreate, QueryOut, RunQueryResponse,
    ChartCreate, ChartOut, ChartData,
    TableInfo,
)
from .pg_connector import (
    run_and_ingest, list_object_tables,
    build_chart_query, execute_chart_query,
)

app = FastAPI(title="Data Visualisation", docs_url="/api/docs")

# ── Startup ───────────────────────────────────────────────────────────────────

@app.on_event("startup")
def startup():
    init_db()

# ── Static files (SPA) ───────────────────────────────────────────────────────

app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/", include_in_schema=False)
def serve_spa():
    return FileResponse("app/static/index.html")


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.post("/api/auth/register", response_model=TokenResponse, status_code=201)
def register(req: RegisterRequest):
    if get_user_by_email(req.email):
        raise HTTPException(400, "Email already registered")
    if len(req.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    user  = create_user(req.email, req.password)
    token = create_token(user["id"], user["email"])
    return TokenResponse(access_token=token, email=user["email"])

@app.post("/api/auth/login", response_model=TokenResponse)
def login(req: LoginRequest):
    user = get_user_by_email(req.email)
    if not user or not verify_password(req.password, user["hashed_pw"]):
        raise HTTPException(401, "Invalid email or password")
    token = create_token(user["id"], user["email"])
    return TokenResponse(access_token=token, email=user["email"])


# ── Objects ───────────────────────────────────────────────────────────────────

def _get_object_or_404(oid: int, user: dict) -> dict:
    conn = get_conn()
    row  = conn.execute(
        "SELECT id, name, description FROM objects WHERE id = ? AND user_id = ?",
        [oid, user["id"]]
    ).fetchone()
    if not row:
        raise HTTPException(404, "Object not found")
    return {"id": row[0], "name": row[1], "description": row[2]}

@app.get("/api/objects", response_model=List[ObjectOut])
def list_objects(user=Depends(current_user)):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, name, description FROM objects WHERE user_id = ? ORDER BY created_at DESC",
        [user["id"]]
    ).fetchall()
    return [ObjectOut(id=r[0], name=r[1], description=r[2]) for r in rows]

@app.post("/api/objects", response_model=ObjectOut, status_code=201)
def create_object(req: ObjectCreate, user=Depends(current_user)):
    conn = get_conn()
    conn.execute(
        "INSERT INTO objects (user_id, name, description) VALUES (?, ?, ?)",
        [user["id"], req.name, req.description]
    )
    row = conn.execute(
        "SELECT id, name, description FROM objects WHERE user_id = ? ORDER BY id DESC LIMIT 1",
        [user["id"]]
    ).fetchone()
    return ObjectOut(id=row[0], name=row[1], description=row[2])

@app.get("/api/objects/{oid}", response_model=ObjectOut)
def get_object(oid: int, user=Depends(current_user)):
    return _get_object_or_404(oid, user)

@app.delete("/api/objects/{oid}", status_code=204)
def delete_object(oid: int, user=Depends(current_user)):
    _get_object_or_404(oid, user)
    conn = get_conn()
    conn.execute("DELETE FROM objects WHERE id = ?", [oid])


# ── Connections ───────────────────────────────────────────────────────────────

@app.get("/api/objects/{oid}/connections", response_model=List[ConnectionOut])
def list_connections(oid: int, user=Depends(current_user)):
    _get_object_or_404(oid, user)
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, name, host, port, dbname, username FROM pg_connections WHERE object_id = ?",
        [oid]
    ).fetchall()
    return [ConnectionOut(id=r[0], name=r[1], host=r[2], port=r[3], dbname=r[4], username=r[5]) for r in rows]

@app.post("/api/objects/{oid}/connections", response_model=ConnectionOut, status_code=201)
def create_connection(oid: int, req: ConnectionCreate, user=Depends(current_user)):
    _get_object_or_404(oid, user)
    conn = get_conn()
    conn.execute(
        "INSERT INTO pg_connections (object_id, name, host, port, dbname, username, password) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [oid, req.name, req.host, req.port, req.dbname, req.username, req.password]
    )
    row = conn.execute(
        "SELECT id, name, host, port, dbname, username FROM pg_connections "
        "WHERE object_id = ? ORDER BY id DESC LIMIT 1", [oid]
    ).fetchone()
    return ConnectionOut(id=row[0], name=row[1], host=row[2], port=row[3], dbname=row[4], username=row[5])

@app.delete("/api/objects/{oid}/connections/{cid}", status_code=204)
def delete_connection(oid: int, cid: int, user=Depends(current_user)):
    _get_object_or_404(oid, user)
    get_conn().execute("DELETE FROM pg_connections WHERE id = ? AND object_id = ?", [cid, oid])

@app.post("/api/objects/{oid}/connections/{cid}/test")
def test_connection(oid: int, cid: int, user=Depends(current_user)):
    _get_object_or_404(oid, user)
    row = get_conn().execute(
        "SELECT host, port, dbname, username, password FROM pg_connections WHERE id = ? AND object_id = ?",
        [cid, oid]
    ).fetchone()
    if not row:
        raise HTTPException(404, "Connection not found")
    from sqlalchemy import create_engine, text
    dsn = f"postgresql+psycopg2://{row[3]}:{row[4]}@{row[0]}:{row[1]}/{row[2]}"
    try:
        engine = create_engine(dsn, connect_args={"connect_timeout": 5})
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        return {"ok": True, "message": "Connection successful"}
    except Exception as e:
        raise HTTPException(400, f"Connection failed: {e}")


# ── Queries ───────────────────────────────────────────────────────────────────

@app.get("/api/objects/{oid}/queries", response_model=List[QueryOut])
def list_queries(oid: int, user=Depends(current_user)):
    _get_object_or_404(oid, user)
    rows = get_conn().execute(
        "SELECT id, name, connection_id, sql_text, target_table, last_run_at, row_count "
        "FROM pg_queries WHERE object_id = ?", [oid]
    ).fetchall()
    return [QueryOut(
        id=r[0], name=r[1], connection_id=r[2], sql_text=r[3],
        target_table=r[4],
        last_run_at=str(r[5]) if r[5] else None,
        row_count=r[6]
    ) for r in rows]

@app.post("/api/objects/{oid}/queries", response_model=QueryOut, status_code=201)
def create_query(oid: int, req: QueryCreate, user=Depends(current_user)):
    _get_object_or_404(oid, user)
    # Verify connection belongs to this object
    crow = get_conn().execute(
        "SELECT id FROM pg_connections WHERE id = ? AND object_id = ?",
        [req.connection_id, oid]
    ).fetchone()
    if not crow:
        raise HTTPException(404, "Connection not found on this object")
    conn = get_conn()
    conn.execute(
        "INSERT INTO pg_queries (object_id, connection_id, name, sql_text, target_table) "
        "VALUES (?, ?, ?, ?, ?)",
        [oid, req.connection_id, req.name, req.sql_text, req.target_table]
    )
    row = conn.execute(
        "SELECT id, name, connection_id, sql_text, target_table, last_run_at, row_count "
        "FROM pg_queries WHERE object_id = ? ORDER BY id DESC LIMIT 1", [oid]
    ).fetchone()
    return QueryOut(id=row[0], name=row[1], connection_id=row[2], sql_text=row[3],
                    target_table=row[4], last_run_at=None, row_count=None)

@app.delete("/api/objects/{oid}/queries/{qid}", status_code=204)
def delete_query(oid: int, qid: int, user=Depends(current_user)):
    _get_object_or_404(oid, user)
    get_conn().execute("DELETE FROM pg_queries WHERE id = ? AND object_id = ?", [qid, oid])

@app.post("/api/objects/{oid}/queries/{qid}/run", response_model=RunQueryResponse)
def run_query(oid: int, qid: int, user=Depends(current_user)):
    _get_object_or_404(oid, user)
    conn = get_conn()
    qrow = conn.execute(
        "SELECT id, connection_id, name, sql_text, target_table "
        "FROM pg_queries WHERE id = ? AND object_id = ?", [qid, oid]
    ).fetchone()
    if not qrow:
        raise HTTPException(404, "Query not found")
    crow = conn.execute(
        "SELECT host, port, dbname, username, password FROM pg_connections WHERE id = ?",
        [qrow[1]]
    ).fetchone()
    if not crow:
        raise HTTPException(404, "Connection not found")
    connection_row = dict(zip(["host","port","dbname","username","password"], crow))
    try:
        row_count, columns = run_and_ingest(
            object_id=oid,
            connection_row=connection_row,
            query_name=qrow[2],
            sql=qrow[3],
            target_table=qrow[4],
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Query execution failed: {e}")
    conn.execute(
        "UPDATE pg_queries SET last_run_at = ?, row_count = ? WHERE id = ?",
        [datetime.utcnow(), row_count, qid]
    )
    return RunQueryResponse(
        row_count=row_count,
        columns=columns,
        message=f"Ingested {row_count} rows into table '{qrow[4]}'"
    )


# ── Tables ────────────────────────────────────────────────────────────────────

@app.get("/api/objects/{oid}/tables", response_model=List[TableInfo])
def get_tables(oid: int, user=Depends(current_user)):
    _get_object_or_404(oid, user)
    return list_object_tables(oid)


# ── Charts ────────────────────────────────────────────────────────────────────

@app.get("/api/objects/{oid}/charts", response_model=List[ChartOut])
def list_charts(oid: int, user=Depends(current_user)):
    _get_object_or_404(oid, user)
    rows = get_conn().execute(
        "SELECT id, name, chart_type, measure, dimension FROM charts WHERE object_id = ?", [oid]
    ).fetchall()
    return [ChartOut(id=r[0], name=r[1], chart_type=r[2], measure=r[3], dimension=r[4]) for r in rows]

@app.post("/api/objects/{oid}/charts", response_model=ChartOut, status_code=201)
def create_chart(oid: int, req: ChartCreate, user=Depends(current_user)):
    _get_object_or_404(oid, user)
    conn = get_conn()
    conn.execute(
        "INSERT INTO charts (object_id, name, chart_type, measure, dimension) VALUES (?,?,?,?,?)",
        [oid, req.name, req.chart_type, req.measure, req.dimension]
    )
    row = conn.execute(
        "SELECT id, name, chart_type, measure, dimension FROM charts "
        "WHERE object_id = ? ORDER BY id DESC LIMIT 1", [oid]
    ).fetchone()
    return ChartOut(id=row[0], name=row[1], chart_type=row[2], measure=row[3], dimension=row[4])

@app.delete("/api/objects/{oid}/charts/{chid}", status_code=204)
def delete_chart(oid: int, chid: int, user=Depends(current_user)):
    _get_object_or_404(oid, user)
    get_conn().execute("DELETE FROM charts WHERE id = ? AND object_id = ?", [chid, oid])

@app.get("/api/objects/{oid}/charts/{chid}/data", response_model=ChartData)
def get_chart_data(oid: int, chid: int, user=Depends(current_user)):
    _get_object_or_404(oid, user)
    row = get_conn().execute(
        "SELECT measure, dimension FROM charts WHERE id = ? AND object_id = ?", [chid, oid]
    ).fetchone()
    if not row:
        raise HTTPException(404, "Chart not found")
    measure, dimension = row
    try:
        sql  = build_chart_query(oid, measure, dimension)
        data = execute_chart_query(oid, sql)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Chart query failed: {e}")
    return ChartData(labels=data["labels"], values=data["values"], sql=sql)
