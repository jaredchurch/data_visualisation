"""Pydantic request/response models."""

from typing import Optional, List
from pydantic import BaseModel, EmailStr


# ── Auth ──────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    email: str


# ── Objects ───────────────────────────────────────────────────────────────────

class ObjectCreate(BaseModel):
    name: str
    description: Optional[str] = None

class ObjectOut(BaseModel):
    id: int
    name: str
    description: Optional[str]


# ── Connections ───────────────────────────────────────────────────────────────

class ConnectionCreate(BaseModel):
    name: str
    host: str
    port: int = 5432
    dbname: str
    username: str
    password: str

class ConnectionOut(BaseModel):
    id: int
    name: str
    host: str
    port: int
    dbname: str
    username: str


# ── Queries ───────────────────────────────────────────────────────────────────

class QueryCreate(BaseModel):
    name: str
    connection_id: int
    sql_text: str
    target_table: str

class QueryOut(BaseModel):
    id: int
    name: str
    connection_id: int
    sql_text: str
    target_table: str
    last_run_at: Optional[str]
    row_count: Optional[int]

class RunQueryResponse(BaseModel):
    row_count: int
    columns: List[str]
    message: str


# ── Charts ────────────────────────────────────────────────────────────────────

class ChartCreate(BaseModel):
    name: str
    chart_type: str = "bar"
    measure: str      # e.g. "SUM(revenue)"
    dimension: str    # e.g. "category"

class ChartOut(BaseModel):
    id: int
    name: str
    chart_type: str
    measure: str
    dimension: str

class ChartData(BaseModel):
    labels: List[str]
    values: List[float]
    sql: str


# ── Tables ────────────────────────────────────────────────────────────────────

class TableInfo(BaseModel):
    table: str
    columns: List[str]
