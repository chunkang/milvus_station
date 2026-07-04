# ┌──────────────────────────────────────────────────────────────────────────┐
# │ milvus_station                                                           │
# │ Author  : Chun Kang <kurapa@kurapa.com>                                  │
# │ Created : 2026-07-03  (PDT, UTC-07:00)                                   │
# └──────────────────────────────────────────────────────────────────────────┘

"""Data-console DB introspection & pagination (MariaDB via PyMySQL).

This module powers the read-only "data console" browse endpoints. It
exposes helpers to list non-system databases, their tables, columns and
paginated rows.

SECURITY
--------
Database / table / column names arrive from untrusted user input and are
used as SQL *identifiers* (which cannot be parameterised as bind values).
Every identifier is therefore validated against ``information_schema``
BEFORE use: it must exactly match an existing, non-system object. Only
then is it backtick-quoted (with embedded backticks escaped) and
interpolated. All *values* (LIMIT/OFFSET, WHERE params) are passed as
bound parameters. A hostile name such as ``x; DROP TABLE y`` never
matches an existing object and is rejected with 404 before any raw query
is built.

The PyMySQL driver is imported lazily inside :func:`get_connection` so
unit tests (which monkeypatch :func:`fetch_all` / :func:`fetch_one`) do
not require the package nor a live database.
"""

from __future__ import annotations

from typing import Any, Sequence

from fastapi import HTTPException

from .config import Settings, get_settings

# Schemas that are part of the server itself and must never be browsed.
SYSTEM_SCHEMAS: frozenset[str] = frozenset(
    {"information_schema", "mysql", "performance_schema", "sys"}
)

# Column data types whose contents are meaningful to embed as text.
# Column types offered for embedding. Text types carry natural-language
# meaning; numeric/temporal types are also allowed so they can be included as
# labelled "column: value" context in the combined embedding text (e.g. a
# movie's year or rating alongside its title and overview).
EMBEDDABLE_TYPES: frozenset[str] = frozenset(
    {
        # text
        "char", "varchar", "text", "tinytext", "mediumtext", "longtext", "json",
        # numeric
        "tinyint", "smallint", "mediumint", "int", "integer", "bigint",
        "decimal", "numeric", "float", "double", "real", "bit",
        # temporal
        "year", "date", "datetime", "timestamp", "time",
    }
)

# Numeric column types, split by the scalar kind used when they are stored as
# typed Milvus fields for range filtering. Integer-like types map to
# ``DataType.INT64``; fractional types map to ``DataType.DOUBLE``. Compared
# case-insensitively against ``information_schema.COLUMNS.DATA_TYPE``.
NUMERIC_INT_TYPES: frozenset[str] = frozenset(
    {"tinyint", "smallint", "mediumint", "int", "integer", "bigint", "year", "bit"}
)
NUMERIC_FLOAT_TYPES: frozenset[str] = frozenset(
    {"decimal", "numeric", "float", "double", "real"}
)

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100


def get_connection(settings: Settings | None = None):
    """Open a PyMySQL connection using service settings (DictCursor).

    Imported lazily so the driver is only required at actual call time.
    """
    settings = settings or get_settings()

    import pymysql  # lazy import
    from pymysql.cursors import DictCursor

    return pymysql.connect(
        host=settings.mariadb_host,
        port=settings.mariadb_port,
        user=settings.mariadb_user,
        password=settings.mariadb_password,
        database=settings.mariadb_db,
        cursorclass=DictCursor,
        connect_timeout=int(settings.probe_timeout_seconds) or 1,
    )


def fetch_all(
    sql: str, params: Sequence[Any] = (), settings: Settings | None = None
) -> list[dict[str, Any]]:
    """Execute ``sql`` with bound ``params`` and return all rows.

    This is the single low-level DB seam; unit tests monkeypatch it.
    """
    conn = get_connection(settings)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())
    finally:
        conn.close()


def fetch_one(
    sql: str, params: Sequence[Any] = (), settings: Settings | None = None
) -> dict[str, Any] | None:
    """Execute ``sql`` with bound ``params`` and return the first row."""
    conn = get_connection(settings)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()
    finally:
        conn.close()


# --------------------------------------------------------------------------
# Identifier validation & quoting
# --------------------------------------------------------------------------
def quote_ident(name: str) -> str:
    """Backtick-quote an identifier, escaping embedded backticks.

    Only ever called with a value already validated against
    information_schema, but escaping is applied defensively regardless.
    """
    return "`" + name.replace("`", "``") + "`"


def list_databases(settings: Settings | None = None) -> list[str]:
    """Return sorted non-system schema names."""
    rows = fetch_all(
        "SELECT SCHEMA_NAME FROM information_schema.SCHEMATA",
        (),
        settings,
    )
    names = [
        row["SCHEMA_NAME"]
        for row in rows
        if row["SCHEMA_NAME"] not in SYSTEM_SCHEMAS
    ]
    return sorted(names)


def validate_database(db: str, settings: Settings | None = None) -> str:
    """Ensure ``db`` is a known non-system schema, else 404."""
    if db in SYSTEM_SCHEMAS or db not in list_databases(settings):
        raise HTTPException(status_code=404, detail=f"database not found: {db}")
    return db


def list_tables(db: str, settings: Settings | None = None) -> list[dict[str, Any]]:
    """Return ``[{"name","rows"}]`` for a validated database."""
    validate_database(db, settings)
    rows = fetch_all(
        "SELECT TABLE_NAME, TABLE_ROWS FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = %s",
        (db,),
        settings,
    )
    return [
        {"name": row["TABLE_NAME"], "rows": int(row["TABLE_ROWS"] or 0)}
        for row in rows
    ]


def validate_table(db: str, table: str, settings: Settings | None = None) -> str:
    """Ensure ``table`` exists in validated ``db``, else 404."""
    names = {t["name"] for t in list_tables(db, settings)}
    if table not in names:
        raise HTTPException(
            status_code=404, detail=f"table not found: {db}.{table}"
        )
    return table


def _column_rows(
    db: str, table: str, settings: Settings | None = None
) -> list[dict[str, Any]]:
    """Raw information_schema.COLUMNS rows for a validated table."""
    return fetch_all(
        "SELECT COLUMN_NAME, DATA_TYPE, COLUMN_KEY, ORDINAL_POSITION "
        "FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
        "ORDER BY ORDINAL_POSITION",
        (db, table),
        settings,
    )


def list_columns(
    db: str, table: str, settings: Settings | None = None
) -> list[dict[str, Any]]:
    """Return ``[{"name","type","embeddable"}]`` for a validated table."""
    validate_database(db, settings)
    validate_table(db, table, settings)
    rows = _column_rows(db, table, settings)
    if not rows:
        raise HTTPException(
            status_code=404, detail=f"table not found: {db}.{table}"
        )
    return [
        {
            "name": row["COLUMN_NAME"],
            "type": row["DATA_TYPE"],
            "embeddable": str(row["DATA_TYPE"]).lower() in EMBEDDABLE_TYPES,
        }
        for row in rows
    ]


def column_types(
    db: str, table: str, settings: Settings | None = None
) -> dict[str, str]:
    """Return ``{column_name: data_type_lowercase}`` for a table.

    Reuses :func:`_column_rows` (information_schema). The caller is expected to
    have validated ``db``/``table`` already (``build_index`` does). This is a
    thin introspection helper used to decide which selected columns are numeric
    (stored as typed Milvus scalar fields) versus text (embedded).
    """
    rows = _column_rows(db, table, settings)
    return {
        row["COLUMN_NAME"]: str(row["DATA_TYPE"]).lower() for row in rows
    }


def numeric_kind(data_type: str) -> str | None:
    """Classify a column ``data_type`` as ``"int"``, ``"float"`` or ``None``.

    ``None`` means the type is not numeric (text/temporal) and should be
    embedded as text rather than stored as a filterable scalar field.
    """
    dt = str(data_type or "").lower()
    if dt in NUMERIC_INT_TYPES:
        return "int"
    if dt in NUMERIC_FLOAT_TYPES:
        return "float"
    return None


def validate_column(
    db: str, table: str, column: str, settings: Settings | None = None
) -> str:
    """Ensure ``column`` exists in validated ``db.table``, else 404."""
    names = {c["name"] for c in list_columns(db, table, settings)}
    if column not in names:
        raise HTTPException(
            status_code=404,
            detail=f"column not found: {db}.{table}.{column}",
        )
    return column


def primary_key(
    db: str, table: str, settings: Settings | None = None
) -> str:
    """Return the primary-key column, or the first column as fallback."""
    rows = _column_rows(db, table, settings)
    if not rows:
        raise HTTPException(
            status_code=404, detail=f"table not found: {db}.{table}"
        )
    for row in rows:
        if str(row.get("COLUMN_KEY", "")).upper() == "PRI":
            return row["COLUMN_NAME"]
    return rows[0]["COLUMN_NAME"]


# --------------------------------------------------------------------------
# JSON-safe value coercion
# --------------------------------------------------------------------------
def jsonify(value: Any) -> Any:
    """Coerce non-JSON-native scalars (datetime/Decimal/bytes) to str."""
    import datetime
    import decimal

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, decimal.Decimal):
        return str(value)
    if isinstance(value, (bytes, bytearray)):
        try:
            return value.decode("utf-8", "replace")
        except Exception:
            return str(value)
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    return str(value)


def _clamp_page(page: int, page_size: int) -> tuple[int, int]:
    """Clamp pagination inputs to safe bounds."""
    page = max(1, int(page))
    page_size = int(page_size)
    if page_size < 1:
        page_size = DEFAULT_PAGE_SIZE
    page_size = min(page_size, MAX_PAGE_SIZE)
    return page, page_size


def get_rows(
    db: str,
    table: str,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Return a paginated slice of a validated table.

    ``db`` and ``table`` are validated against information_schema and then
    backtick-quoted; LIMIT/OFFSET are bound integer parameters.
    """
    validate_database(db, settings)
    validate_table(db, table, settings)
    page, page_size = _clamp_page(page, page_size)

    columns = [c["name"] for c in list_columns(db, table, settings)]

    qualified = f"{quote_ident(db)}.{quote_ident(table)}"

    total_row = fetch_one(
        f"SELECT COUNT(*) AS cnt FROM {qualified}", (), settings
    )
    total = int((total_row or {}).get("cnt", 0))

    offset = (page - 1) * page_size
    data_rows = fetch_all(
        f"SELECT * FROM {qualified} LIMIT %s OFFSET %s",
        (page_size, offset),
        settings,
    )

    serialised: list[list[Any]] = [
        [jsonify(row.get(col)) for col in columns] for row in data_rows
    ]

    return {
        "database": db,
        "table": table,
        "page": page,
        "page_size": page_size,
        "total": total,
        "columns": columns,
        "rows": serialised,
    }


def read_pk_text(
    db: str,
    table: str,
    pk_column: str,
    text_column: str,
    limit: int = 1000,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    """Read ``(pk, text)`` pairs from a validated table (bounded LIMIT).

    Both column names are validated and backtick-quoted; the limit is a
    bound integer parameter.
    """
    qualified = f"{quote_ident(db)}.{quote_ident(table)}"
    pk_q = quote_ident(pk_column)
    text_q = quote_ident(text_column)
    rows = fetch_all(
        f"SELECT {pk_q} AS pk, {text_q} AS text FROM {qualified} LIMIT %s",
        (int(limit),),
        settings,
    )
    return rows


def read_pk_columns(
    db: str,
    table: str,
    pk_column: str,
    columns: list[str],
    limit: int = 1000,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    """Read ``pk`` plus each of ``columns`` from a validated table.

    Every identifier (db, table, pk, and each column) is backtick-quoted;
    the limit is a bound integer parameter. Each returned row is a dict
    ``{"pk": ..., "<col>": ..., ...}`` keyed by the original column names,
    so callers can combine several fields into one text before embedding.
    """
    qualified = f"{quote_ident(db)}.{quote_ident(table)}"
    pk_q = quote_ident(pk_column)
    # Alias each selected column to its own name so the result dict is keyed
    # by the original column name (independent of any AS the driver applies).
    select_cols = ", ".join(
        f"{quote_ident(col)} AS {quote_ident(col)}" for col in columns
    )
    rows = fetch_all(
        f"SELECT {pk_q} AS pk, {select_cols} FROM {qualified} LIMIT %s",
        (int(limit),),
        settings,
    )
    return rows


def read_rows_by_pks(
    db: str,
    table: str,
    pk_column: str,
    pks: Sequence[Any],
    settings: Settings | None = None,
) -> dict[int, dict[str, Any]]:
    """Fetch full source rows for the given primary-key values.

    Used to hydrate Milvus search hits with the complete originating MariaDB
    row so the UI can display any column (e.g. ``actors``) regardless of which
    columns were embedded. ``db``/``table``/``pk_column`` are validated against
    information_schema and backtick-quoted; every pk is passed as a *bound*
    parameter (one ``%s`` placeholder each) -- never interpolated -- so this is
    safe against injection even though it selects every column.

    Returns a mapping ``{pk (int) -> {column: jsonified value}}`` covering each
    row found. An empty ``pks`` yields ``{}`` without touching the database.
    """
    validate_database(db, settings)
    validate_table(db, table, settings)
    validate_column(db, table, pk_column, settings)

    if not pks:
        return {}

    qualified = f"{quote_ident(db)}.{quote_ident(table)}"
    pk_q = quote_ident(pk_column)
    placeholders = ", ".join(["%s"] * len(pks))
    rows = fetch_all(
        f"SELECT * FROM {qualified} WHERE {pk_q} IN ({placeholders})",
        tuple(pks),
        settings,
    )

    result: dict[int, dict[str, Any]] = {}
    for row in rows:
        pk_value = int(row[pk_column])
        result[pk_value] = {col: jsonify(val) for col, val in row.items()}
    return result
