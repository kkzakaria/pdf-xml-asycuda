"""
Base SQLite de l'application web.
"""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 2

# Version 2 : statut « abandonne » et n° de la génération déclarée (declared_n).
DOSSIERS_TABLE = """
CREATE TABLE IF NOT EXISTS {name} (
    id           INTEGER PRIMARY KEY,
    rfcv_number  TEXT,
    filename     TEXT NOT NULL,
    pdf_path     TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'brouillon'
                 CHECK (status IN ('brouillon', 'declare', 'annule', 'abandonne')),
    created_by   TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    declared_by  TEXT,
    declared_at  TEXT,
    declared_n   INTEGER,
    error        TEXT
);
"""
V1_COLUMNS = ("id, rfcv_number, filename, pdf_path, status, created_by, created_at, "
              "declared_by, declared_at, error")

SCHEMA = DOSSIERS_TABLE.format(name="dossiers") + """
CREATE TABLE IF NOT EXISTS users (
    email       TEXT PRIMARY KEY,
    first_seen  TEXT NOT NULL,
    last_seen   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_dossiers_rfcv ON dossiers (rfcv_number);

CREATE TABLE IF NOT EXISTS generations (
    id             INTEGER PRIMARY KEY,
    dossier_id     INTEGER NOT NULL REFERENCES dossiers (id),
    n              INTEGER NOT NULL,
    settings_json  TEXT NOT NULL,
    summary_json   TEXT,
    xml_path       TEXT,
    corps_path     TEXT,
    created_by     TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    UNIQUE (dossier_id, n)
);

CREATE TABLE IF NOT EXISTS hs_known (
    designation  TEXT NOT NULL,
    hs_code      TEXT NOT NULL,
    PRIMARY KEY (designation, hs_code)
);

CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY,
    dossier_id  INTEGER NULL REFERENCES dossiers (id),
    email       TEXT NOT NULL,
    action      TEXT NOT NULL,
    detail      TEXT,
    at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_dossier ON events (dossier_id);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path) -> sqlite3.Connection:
    """Ouvre la base (crée le dossier parent), clés étrangères et WAL activés."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # 30 s d'attente quand un autre écrivain tient la base (busy_timeout 30000)
    conn = sqlite3.connect(path, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init(conn: sqlite3.Connection) -> None:
    """Crée les tables manquantes et met la base à la version SCHEMA_VERSION (idempotent)."""
    conn.executescript(SCHEMA)
    conn.commit()
    if conn.execute("PRAGMA user_version").fetchone()[0] < SCHEMA_VERSION:
        _migrate(conn)


def _migrate(conn: sqlite3.Connection) -> None:
    """
    Version 1 -> 2 : la table dossiers est recréée (nouvelle contrainte CHECK, colonne
    declared_n), lignes copiées. Procédure SQLite : clés étrangères suspendues le temps de la
    copie, contrôle foreign_key_check avant validation.
    """
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            # relu sous verrou : une autre connexion a pu migrer entre-temps
            if conn.execute("PRAGMA user_version").fetchone()[0] < SCHEMA_VERSION:
                columns = {r[1] for r in conn.execute("PRAGMA table_info(dossiers)")}
                if "declared_n" not in columns:
                    conn.execute(DOSSIERS_TABLE.format(name="dossiers_v2"))
                    conn.execute(f"INSERT INTO dossiers_v2 ({V1_COLUMNS}) SELECT {V1_COLUMNS} FROM dossiers")
                    conn.execute("DROP TABLE dossiers")
                    conn.execute("ALTER TABLE dossiers_v2 RENAME TO dossiers")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_dossiers_rfcv ON dossiers (rfcv_number)")
                    if conn.execute("PRAGMA foreign_key_check").fetchall():
                        raise sqlite3.IntegrityError("Migration de la base : clés étrangères incohérentes")
                conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def upsert_user(conn: sqlite3.Connection, email: str, now: str | None = None) -> None:
    """Enregistre l'utilisateur ou met à jour sa dernière visite."""
    now = now or now_iso()
    conn.execute(
        "INSERT INTO users (email, first_seen, last_seen) VALUES (?, ?, ?) "
        "ON CONFLICT (email) DO UPDATE SET last_seen = excluded.last_seen",
        (email, now, now),
    )
    conn.commit()
