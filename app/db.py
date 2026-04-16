"""
DuckDB connection manager.

All user data (accounts, objects, connections, query definitions,
chart configs) is stored in a single DuckDB file.  The actual
ingested query results live in per-object schemas.
"""

import os
import threading
import duckdb

DUCKDB_PATH = os.environ.get("DUCKDB_PATH", "/data/app.duckdb")

# DuckDB connections are NOT thread-safe when shared, so we give each
# thread its own connection that opens the same file.
_local = threading.local()


def get_conn() -> duckdb.DuckDBPyConnection:
    """Return a per-thread DuckDB connection."""
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = duckdb.connect(DUCKDB_PATH)
    return _local.conn


def init_db():
    """Create all system tables if they don't exist."""
    conn = get_conn()

    conn.execute("""
        CREATE SEQUENCE IF NOT EXISTS seq_users START 1;
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER DEFAULT nextval('seq_users') PRIMARY KEY,
            email       VARCHAR UNIQUE NOT NULL,
            hashed_pw   VARCHAR NOT NULL,
            created_at  TIMESTAMP DEFAULT now()
        );
    """)

    conn.execute("""
        CREATE SEQUENCE IF NOT EXISTS seq_objects START 1;
        CREATE TABLE IF NOT EXISTS objects (
            id          INTEGER DEFAULT nextval('seq_objects') PRIMARY KEY,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            name        VARCHAR NOT NULL,
            description VARCHAR,
            created_at  TIMESTAMP DEFAULT now()
        );
    """)

    conn.execute("""
        CREATE SEQUENCE IF NOT EXISTS seq_connections START 1;
        CREATE TABLE IF NOT EXISTS pg_connections (
            id          INTEGER DEFAULT nextval('seq_connections') PRIMARY KEY,
            object_id   INTEGER NOT NULL REFERENCES objects(id) ON DELETE CASCADE,
            name        VARCHAR NOT NULL,
            host        VARCHAR NOT NULL,
            port        INTEGER DEFAULT 5432,
            dbname      VARCHAR NOT NULL,
            username    VARCHAR NOT NULL,
            password    VARCHAR NOT NULL,
            created_at  TIMESTAMP DEFAULT now()
        );
    """)

    conn.execute("""
        CREATE SEQUENCE IF NOT EXISTS seq_queries START 1;
        CREATE TABLE IF NOT EXISTS pg_queries (
            id            INTEGER DEFAULT nextval('seq_queries') PRIMARY KEY,
            connection_id INTEGER NOT NULL REFERENCES pg_connections(id) ON DELETE CASCADE,
            object_id     INTEGER NOT NULL REFERENCES objects(id) ON DELETE CASCADE,
            name          VARCHAR NOT NULL,
            sql_text      VARCHAR NOT NULL,
            target_table  VARCHAR NOT NULL,
            last_run_at   TIMESTAMP,
            row_count     INTEGER,
            created_at    TIMESTAMP DEFAULT now()
        );
    """)

    conn.execute("""
        CREATE SEQUENCE IF NOT EXISTS seq_charts START 1;
        CREATE TABLE IF NOT EXISTS charts (
            id          INTEGER DEFAULT nextval('seq_charts') PRIMARY KEY,
            object_id   INTEGER NOT NULL REFERENCES objects(id) ON DELETE CASCADE,
            name        VARCHAR NOT NULL,
            chart_type  VARCHAR DEFAULT 'bar',
            measure     VARCHAR NOT NULL,
            dimension   VARCHAR NOT NULL,
            created_at  TIMESTAMP DEFAULT now()
        );
    """)
