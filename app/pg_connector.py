"""
PostgreSQL connector and DuckDB ingest logic.

For each query:
  1. Connect to the source PostgreSQL database.
  2. Run the (SELECT-only) SQL.
  3. Ingest the result set into DuckDB under a per-object schema.
  4. Return row count + column names.

Auto-join logic:
  When a chart references two tables that share column names,
  this module generates a FULL OUTER JOIN automatically so that
  chart queries don't need to be hand-written.
"""

from __future__ import annotations
import re
from typing import List, Tuple, Dict, Any

import duckdb
from sqlalchemy import create_engine, text

from .db import get_conn


# ── Safety ────────────────────────────────────────────────────────────────────

_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|GRANT|REVOKE|COPY|EXEC)\b",
    re.IGNORECASE,
)

def _assert_select_only(sql: str):
    if _FORBIDDEN.search(sql):
        raise ValueError("Only SELECT statements are permitted.")


# ── Schema helpers ────────────────────────────────────────────────────────────

def _object_schema(object_id: int) -> str:
    return f"obj_{object_id}"

def _ensure_schema(conn: duckdb.DuckDBPyConnection, object_id: int):
    schema = _object_schema(object_id)
    conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')


# ── Run query and ingest ──────────────────────────────────────────────────────

def run_and_ingest(
    object_id: int,
    connection_row: dict,
    query_name: str,
    sql: str,
    target_table: str,
) -> Tuple[int, List[str]]:
    """
    Execute *sql* against the PostgreSQL connection described by
    *connection_row*, then store results in DuckDB as
    obj_<object_id>.<target_table>.

    Returns (row_count, column_names).
    """
    _assert_select_only(sql)

    dsn = (
        f"postgresql+psycopg2://{connection_row['username']}:{connection_row['password']}"
        f"@{connection_row['host']}:{connection_row['port']}/{connection_row['dbname']}"
    )
    engine = create_engine(dsn, pool_pre_ping=True)

    with engine.connect() as pg_conn:
        result = pg_conn.execute(text(sql))
        columns = list(result.keys())
        rows    = result.fetchall()

    # Validate target table name (alphanumeric + underscore only)
    if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', target_table):
        raise ValueError("target_table must be a simple identifier (letters, digits, underscores).")

    duck = get_conn()
    _ensure_schema(duck, object_id)
    schema = _object_schema(object_id)
    full_name = f'"{schema}"."{target_table}"'

    # Drop and recreate for a clean load
    duck.execute(f"DROP TABLE IF EXISTS {full_name}")

    if rows:
        # Register the data as a relation then CREATE TABLE AS SELECT
        import pandas as pd
        df = pd.DataFrame(rows, columns=columns)
        duck.register("_ingest_tmp", df)
        duck.execute(f"CREATE TABLE {full_name} AS SELECT * FROM _ingest_tmp")
        duck.unregister("_ingest_tmp")
    else:
        # Create empty table with correct columns
        col_defs = ", ".join(f'"{c}" VARCHAR' for c in columns)
        duck.execute(f"CREATE TABLE {full_name} ({col_defs})")

    return len(rows), columns


# ── List tables in an object's schema ────────────────────────────────────────

def list_object_tables(object_id: int) -> List[Dict[str, Any]]:
    duck  = get_conn()
    schema = _object_schema(object_id)
    rows  = duck.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = ?",
        [schema]
    ).fetchall()
    result = []
    for (tname,) in rows:
        cols = duck.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = ? AND table_name = ? ORDER BY ordinal_position",
            [schema, tname]
        ).fetchall()
        result.append({
            "table": tname,
            "columns": [c[0] for c in cols]
        })
    return result


# ── Build chart query with auto-join ─────────────────────────────────────────

def build_chart_query(
    object_id: int,
    measure_expr: str,
    dimension_col: str,
) -> str:
    """
    Build a DuckDB SQL query for a chart.

    - If only one table exists, query it directly.
    - If multiple tables exist, FULL OUTER JOIN them on columns
      that are identical across all tables.
    - measure_expr  e.g. "SUM(revenue)"  or  "COUNT(*)"
    - dimension_col e.g. "category"
    """
    schema  = _object_schema(object_id)
    tables  = list_object_tables(object_id)

    if not tables:
        raise ValueError("No ingested tables found for this object.")

    if len(tables) == 1:
        tname = tables[0]["table"]
        return (
            f'SELECT "{dimension_col}", {measure_expr} AS measure_value '
            f'FROM "{schema}"."{tname}" '
            f'GROUP BY "{dimension_col}" '
            f'ORDER BY measure_value DESC'
        )

    # Find shared columns across ALL tables (used as join keys)
    col_sets = [set(t["columns"]) for t in tables]
    shared   = col_sets[0].intersection(*col_sets[1:])

    if not shared:
        raise ValueError(
            "No common column names found across tables — "
            "cannot auto-join.  Ensure the tables share at least one column name."
        )

    # Build join chain: t0 FULL OUTER JOIN t1 ON ... FULL OUTER JOIN t2 ON ...
    aliases = [f"t{i}" for i in range(len(tables))]
    base    = f'"{schema}"."{tables[0]["table"]}" AS {aliases[0]}'
    joins   = []
    for i in range(1, len(tables)):
        conds = " AND ".join(
            f'{aliases[0]}."{c}" = {aliases[i]}."{c}"'
            for c in sorted(shared)
        )
        joins.append(
            f'FULL OUTER JOIN "{schema}"."{tables[i]["table"]}" AS {aliases[i]} ON {conds}'
        )

    # COALESCE the shared key columns so NULLs from either side are handled
    coalesce_dim = (
        "COALESCE(" +
        ", ".join(f'{a}."{dimension_col}"' for a in aliases) +
        ")"
    )

    from_clause = base + " " + " ".join(joins)

    return (
        f"SELECT {coalesce_dim} AS \"{dimension_col}\", "
        f"{measure_expr} AS measure_value "
        f"FROM {from_clause} "
        f'GROUP BY "{dimension_col}" '
        f"ORDER BY measure_value DESC"
    )


def execute_chart_query(object_id: int, sql: str) -> Dict[str, Any]:
    """Run a chart query and return labels + values."""
    duck = get_conn()
    rows = duck.execute(sql).fetchall()
    if not rows:
        return {"labels": [], "values": []}
    labels = [str(r[0]) if r[0] is not None else "(null)" for r in rows]
    values = [float(r[1]) if r[1] is not None else 0.0 for r in rows]
    return {"labels": labels, "values": values}
