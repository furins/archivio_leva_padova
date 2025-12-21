import hashlib
import re
import sqlite3
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

DATA_FIELDS = (
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

PERSON_FIELDS = DATA_FIELDS + ("fonte", "hash_unico")


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
            fonte TEXT,
            hash_unico TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS known_names (
            id INTEGER PRIMARY KEY,
            nome TEXT NOT NULL,
            fonte TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS queries (
            id INTEGER PRIMARY KEY,
            cognome TEXT NOT NULL,
            nome_triplette TEXT NOT NULL,
            cognome_esatto INTEGER NOT NULL,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            risultato_count INTEGER NOT NULL,
            UNIQUE(cognome, nome_triplette, cognome_esatto)
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS surnames_queue (
            id INTEGER PRIMARY KEY,
            cognome TEXT NOT NULL,
            stato TEXT NOT NULL,
            fonte TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(cognome)
        );
        """
    )
    _ensure_column(conn, "persons", "fonte", "TEXT")
    _ensure_column(conn, "persons", "hash_unico", "TEXT")
    _ensure_column(conn, "known_names", "nome", "TEXT")
    _ensure_column(conn, "known_names", "fonte", "TEXT")
    _ensure_column(conn, "known_names", "created_at", "TEXT")
    _ensure_column(conn, "known_names", "updated_at", "TEXT")
    _ensure_column(conn, "queries", "timestamp", "TEXT")
    _ensure_column(conn, "queries", "risultato_count", "INTEGER")
    _ensure_column(conn, "surnames_queue", "stato", "TEXT")
    _ensure_column(conn, "surnames_queue", "fonte", "TEXT")
    _ensure_column(conn, "surnames_queue", "timestamp", "TEXT")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS persons_hash_unico_idx "
        "ON persons(hash_unico);"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS surnames_queue_stato_idx "
        "ON surnames_queue(stato);"
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS known_names_nome_idx "
        "ON known_names(nome);"
    )
    _backfill_hashes(conn)
    conn.commit()


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    cursor = conn.execute(f"PRAGMA table_info({table});")
    existing = {row[1] for row in cursor.fetchall()}
    if column in existing:
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition};")


def _backfill_hashes(conn: sqlite3.Connection) -> None:
    cursor = conn.execute(
        f"""
        SELECT id, {", ".join(DATA_FIELDS)}
        FROM persons
        WHERE hash_unico IS NULL OR hash_unico = "";
        """
    )
    rows = cursor.fetchall()
    if not rows:
        return
    payload: List[Sequence[str]] = []
    for row in rows:
        person_id = row[0]
        data = row[1:]
        payload.append((_hash_person(data), person_id))
    conn.executemany(
        "UPDATE persons SET hash_unico = ? WHERE id = ?;",
        payload,
    )


def _hash_person(values: Sequence[Optional[str]]) -> str:
    normalized = [
        (value or "").strip().lower()
        for value in values[: len(DATA_FIELDS)]
    ]
    digest = hashlib.sha256("|".join(normalized).encode("utf-8")).hexdigest()
    return digest


def normalize_surname(cognome: str) -> str:
    return cognome.strip().title()


def normalize_surname_prefix(cognome: str) -> str:
    normalized = normalize_surname(cognome)
    if not normalized:
        return ""
    return normalized[:3]


def normalize_name(nome: str) -> str:
    return nome.strip().title()


def upsert_people(
    conn: sqlite3.Connection,
    rows: Iterable[Sequence[str]],
    fonte: str,
) -> int:
    payload: List[Sequence[str]] = []
    for row in rows:
        if len(row) < len(DATA_FIELDS):
            continue
        values = list(row[: len(DATA_FIELDS)])
        hash_unico = _hash_person(values)
        payload.append((*values, fonte, hash_unico))
    if not payload:
        return 0
    conn.executemany(
        f"""
        INSERT INTO persons ({", ".join(PERSON_FIELDS)})
        VALUES ({", ".join(["?"] * len(PERSON_FIELDS))})
        ON CONFLICT(hash_unico) DO UPDATE SET
            cognome = excluded.cognome,
            nome = excluded.nome,
            data_nascita = excluded.data_nascita,
            luogo_nascita = excluded.luogo_nascita,
            provincia = excluded.provincia,
            comune_iscrizione = excluded.comune_iscrizione,
            mandamento = excluded.mandamento,
            padre = excluded.padre,
            madre = excluded.madre,
            fonte = excluded.fonte;
        """,
        payload,
    )
    conn.commit()
    return len(payload)


def upsert_names(
    conn: sqlite3.Connection,
    names: Iterable[str],
    fonte: str,
) -> int:
    payload: List[Sequence[str]] = []
    for name in names:
        normalized = normalize_name(name)
        if not normalized:
            continue
        payload.append((normalized, fonte))
    if not payload:
        return 0
    conn.executemany(
        """
        INSERT INTO known_names (nome, fonte, created_at, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT(nome) DO UPDATE SET
            fonte = excluded.fonte,
            updated_at = CURRENT_TIMESTAMP;
        """,
        payload,
    )
    conn.commit()
    return len(payload)


def fetch_known_names(conn: sqlite3.Connection) -> List[str]:
    cursor = conn.execute(
        """
        SELECT nome
        FROM known_names
        ORDER BY nome;
        """
    )
    return [row[0] for row in cursor.fetchall()]


def record_query(
    conn: sqlite3.Connection,
    cognome: str,
    nome_triplette: str,
    cognome_esatto: bool,
    risultato_count: int,
) -> None:
    conn.execute(
        """
        INSERT INTO queries (
            cognome,
            nome_triplette,
            cognome_esatto,
            timestamp,
            risultato_count
        )
        VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)
        ON CONFLICT(cognome, nome_triplette, cognome_esatto) DO UPDATE SET
            timestamp = excluded.timestamp,
            risultato_count = excluded.risultato_count;
        """,
        (cognome, nome_triplette, int(bool(cognome_esatto)), risultato_count),
    )
    conn.commit()


def query_exists(
    conn: sqlite3.Connection,
    cognome: str,
    nome_triplette: str,
    cognome_esatto: bool,
) -> bool:
    cursor = conn.execute(
        """
        SELECT 1
        FROM queries
        WHERE cognome = ?
          AND nome_triplette = ?
          AND cognome_esatto = ?
        LIMIT 1;
        """,
        (cognome, nome_triplette, int(bool(cognome_esatto))),
    )
    return cursor.fetchone() is not None


def enqueue_surname(
    conn: sqlite3.Connection,
    cognome: str,
    fonte: str,
    stato: str = "pending",
    use_prefix: bool = True,
) -> None:
    normalized = normalize_surname_prefix(cognome) if use_prefix else normalize_surname(cognome)
    if not normalized:
        return
    conn.execute(
        """
        INSERT INTO surnames_queue (cognome, stato, fonte, timestamp)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(cognome) DO NOTHING;
        """,
        (normalized, stato, fonte),
    )
    conn.commit()


def fetch_pending_surnames(
    conn: sqlite3.Connection,
    limit: int,
) -> List[str]:
    cursor = conn.execute(
        """
        SELECT cognome
        FROM surnames_queue
        WHERE stato = "pending"
        ORDER BY timestamp
        LIMIT ?;
        """,
        (limit,),
    )
    return [row[0] for row in cursor.fetchall()]


def fetch_known_surnames(conn: sqlite3.Connection) -> List[str]:
    cursor = conn.execute(
        """
        SELECT cognome
        FROM surnames_queue
        ORDER BY cognome;
        """
    )
    return [row[0] for row in cursor.fetchall()]


def fetch_surnames(conn: sqlite3.Connection) -> List[str]:
    cursor = conn.execute(
        """
        SELECT DISTINCT cognome
        FROM persons
        ORDER BY cognome;
        """
    )
    return [row[0] for row in cursor.fetchall()]


def count_query_triplette(
    conn: sqlite3.Connection,
    cognome: str,
    cognome_esatto: bool,
) -> int:
    normalized = (
        normalize_surname(cognome)
        if cognome_esatto
        else normalize_surname_prefix(cognome)
    )
    cursor = conn.execute(
        """
        SELECT COUNT(*)
        FROM queries
        WHERE cognome = ?
          AND cognome_esatto = ?;
        """,
        (normalized, int(bool(cognome_esatto))),
    )
    return int(cursor.fetchone()[0])


def mark_surname_done(
    conn: sqlite3.Connection,
    cognome: str,
    cognome_esatto: bool,
) -> None:
    normalized = (
        normalize_surname(cognome)
        if cognome_esatto
        else normalize_surname_prefix(cognome)
    )
    if not normalized:
        return
    if cognome_esatto:
        clause = "cognome = ?"
        params = (normalized,)
    else:
        clause = "cognome = ? OR cognome LIKE ?"
        params = (normalized, f"{normalized}%")
    conn.execute(
        f"""
        UPDATE surnames_queue
        SET stato = "done",
            timestamp = CURRENT_TIMESTAMP
        WHERE {clause};
        """,
        params,
    )
    conn.commit()


def normalize_queue_surnames(conn: sqlite3.Connection) -> int:
    cursor = conn.execute(
        """
        SELECT cognome, stato, fonte, timestamp
        FROM surnames_queue;
        """
    )
    rows = cursor.fetchall()
    changes = 0
    for cognome, stato, fonte, timestamp in rows:
        normalized = normalize_surname_prefix(cognome)
        if not normalized or normalized == cognome:
            continue
        existing = conn.execute(
            """
            SELECT stato
            FROM surnames_queue
            WHERE cognome = ?;
            """,
            (normalized,),
        ).fetchone()
        if existing:
            if stato == "pending" and existing[0] != "pending":
                conn.execute(
                    """
                    UPDATE surnames_queue
                    SET stato = "pending",
                        timestamp = CURRENT_TIMESTAMP
                    WHERE cognome = ?;
                    """,
                    (normalized,),
                )
        else:
            conn.execute(
                """
                INSERT INTO surnames_queue (cognome, stato, fonte, timestamp)
                VALUES (?, ?, ?, ?);
                """,
                (normalized, stato, fonte, timestamp),
            )
        conn.execute(
            """
            DELETE FROM surnames_queue
            WHERE cognome = ?;
            """,
            (cognome,),
        )
        changes += 1
    if changes:
        conn.commit()
    return changes


def fetch_cached_triplette(
    conn: sqlite3.Connection,
    cognome: str,
    cognome_esatto: bool,
) -> set[str]:
    cursor = conn.execute(
        """
        SELECT nome_triplette
        FROM queries
        WHERE cognome = ?
          AND cognome_esatto = ?;
        """,
        (cognome, int(bool(cognome_esatto))),
    )
    return {row[0] for row in cursor.fetchall()}


def fetch_people(
    conn: sqlite3.Connection,
    cognome: str,
    cognome_esatto: bool,
) -> List[sqlite3.Row]:
    if cognome_esatto:
        clause = "cognome = ?"
        param = cognome
    else:
        clause = "cognome LIKE ?"
        param = f"%{cognome}%"
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        f"""
        SELECT {", ".join(DATA_FIELDS)}
        FROM persons
        WHERE {clause}
        ORDER BY cognome, nome, data_nascita;
        """,
        (param,),
    )
    return cursor.fetchall()


def search_people(
    conn: sqlite3.Connection,
    pattern: str,
    fields: Optional[Sequence[str]] = None,
    limit: Optional[int] = None,
) -> List[sqlite3.Row]:
    if fields:
        selected_fields = [field for field in fields if field in DATA_FIELDS]
    else:
        selected_fields = list(DATA_FIELDS)
    if not selected_fields:
        selected_fields = list(DATA_FIELDS)
    where = " OR ".join([f"{field} REGEXP ?" for field in selected_fields])
    params: List[object] = [pattern for _ in selected_fields]
    sql = f"""
        SELECT {", ".join(DATA_FIELDS)}
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
