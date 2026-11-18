"""
Base SQLite de l'application web.
"""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    email       TEXT PRIMARY KEY,
    first_seen  TEXT NOT NULL,
    last_seen   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dossiers (
    id           INTEGER PRIMARY KEY,
    rfcv_number  TEXT,
    filename     TEXT NOT NULL,
    pdf_path     TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'brouillon'
                 CHECK (status IN ('brouillon', 'declare', 'annule')),
    created_by   TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    declared_by  TEXT,
    declared_at  TEXT,
    error        TEXT
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
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init(conn: sqlite3.Connection) -> None:
    """Crée les tables manquantes (idempotent)."""
    conn.executescript(SCHEMA)
    conn.commit()


def upsert_user(conn: sqlite3.Connection, email: str, now: str | None = None) -> None:
    """Enregistre l'utilisateur ou met à jour sa dernière visite."""
    now = now or now_iso()
    conn.execute(
        "INSERT INTO users (email, first_seen, last_seen) VALUES (?, ?, ?) "
        "ON CONFLICT (email) DO UPDATE SET last_seen = excluded.last_seen",
        (email, now, now),
    )
    conn.commit()
