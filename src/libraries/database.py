import re
import sqlite3
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

FIELDS = (
    "cognome",
    "nome",
    "data_nascita",
    "luogo_nascita",
    "provincia",
    "comune_iscrizione",
    "mandamento",
    "padre",
    "madre",
)


def connect_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.create_function("REGEXP", 2, _regexp)
    _init_db(conn)
    return conn


def _regexp(pattern: str, value: Optional[str]) -> int:
    if value is None:
        return 0
    try:
        return 1 if re.search(pattern, value, flags=re.IGNORECASE) else 0
    except re.error:
        return 0


def _init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS persons (
            id INTEGER PRIMARY KEY,
            cognome TEXT NOT NULL,
            nome TEXT NOT NULL,
            data_nascita TEXT,
            luogo_nascita TEXT,
            provincia TEXT,
            comune_iscrizione TEXT,
            mandamento TEXT,
            padre TEXT,
            madre TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(
                cognome,
                nome,
                data_nascita,
                luogo_nascita,
                provincia,
                comune_iscrizione,
                mandamento,
                padre,
                madre
            )
        );
        """
    )
    conn.commit()


def insert_people(conn: sqlite3.Connection, rows: Iterable[Sequence[str]]) -> int:
    payload: List[Sequence[str]] = []
    for row in rows:
        if len(row) < len(FIELDS):
            continue
        payload.append(tuple(row[: len(FIELDS)]))
    if not payload:
        return 0
    conn.executemany(
        """
        INSERT OR IGNORE INTO persons (
            cognome,
            nome,
            data_nascita,
            luogo_nascita,
            provincia,
            comune_iscrizione,
            mandamento,
            padre,
            madre
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        payload,
    )
    conn.commit()
    return len(payload)


def search_people(
    conn: sqlite3.Connection,
    pattern: str,
    fields: Optional[Sequence[str]] = None,
    limit: Optional[int] = None,
) -> List[sqlite3.Row]:
    if fields:
        selected_fields = [field for field in fields if field in FIELDS]
    else:
        selected_fields = list(FIELDS)
    if not selected_fields:
        selected_fields = list(FIELDS)
    where = " OR ".join([f"{field} REGEXP ?" for field in selected_fields])
    params: List[object] = [pattern for _ in selected_fields]
    sql = f"""
        SELECT {", ".join(FIELDS)}
        FROM persons
        WHERE {where}
        ORDER BY cognome, nome, data_nascita
    """
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(sql, params)
    return cursor.fetchall()
