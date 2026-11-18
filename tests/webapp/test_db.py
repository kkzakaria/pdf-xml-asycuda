"""Tests de la base SQLite de la webapp."""
import sqlite3

import pytest

from webapp import db

TABLES = {"users", "dossiers", "generations", "hs_known", "events"}


def test_db_init_idempotent(tmp_path):
    path = tmp_path / "sous" / "webapp.db"
    conn = db.connect(path)
    db.init(conn)
    db.init(conn)
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert TABLES <= names
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"

    db.upsert_user(conn, "op@karta.ci", now="2026-11-18T08:00:00+00:00")
    db.upsert_user(conn, "op@karta.ci", now="2026-11-18T09:00:00+00:00")
    row = conn.execute("SELECT first_seen, last_seen FROM users").fetchone()
    assert tuple(row) == ("2026-11-18T08:00:00+00:00", "2026-11-18T09:00:00+00:00")

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO dossiers (filename, pdf_path, status, created_by, created_at)"
            " VALUES ('a.pdf', 'p', 'inconnu', 'op@karta.ci', 'now')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO generations (dossier_id, n, settings_json, created_by, created_at)"
            " VALUES (999, 1, '{}', 'op@karta.ci', 'now')")
    conn.close()

    conn = db.connect(path)
    db.init(conn)
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
    conn.close()


# ------------------------------------------------------------------ revue finale
V1_DOSSIERS = """
CREATE TABLE users (email TEXT PRIMARY KEY, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL);
CREATE TABLE dossiers (
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
CREATE INDEX idx_dossiers_rfcv ON dossiers (rfcv_number);
CREATE TABLE generations (
    id INTEGER PRIMARY KEY, dossier_id INTEGER NOT NULL REFERENCES dossiers (id), n INTEGER NOT NULL,
    settings_json TEXT NOT NULL, summary_json TEXT, xml_path TEXT, corps_path TEXT,
    created_by TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE (dossier_id, n));
CREATE TABLE hs_known (designation TEXT NOT NULL, hs_code TEXT NOT NULL, PRIMARY KEY (designation, hs_code));
CREATE TABLE events (id INTEGER PRIMARY KEY, dossier_id INTEGER NULL REFERENCES dossiers (id),
    email TEXT NOT NULL, action TEXT NOT NULL, detail TEXT, at TEXT NOT NULL);
"""


def test_connect_waits_30s_for_writers(tmp_path):
    conn = db.connect(tmp_path / "w.db")
    assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 30000
    conn.close()


def test_fresh_db_is_v2_and_accepts_abandonne(tmp_path):
    conn = db.connect(tmp_path / "w.db")
    db.init(conn)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION == 2
    conn.execute("INSERT INTO dossiers (filename, pdf_path, status, created_by, created_at, declared_n)"
                 " VALUES ('a.pdf', 'p', 'abandonne', 'op@karta.ci', 'now', NULL)")
    conn.close()


def test_migrates_v1_database(tmp_path):
    path = tmp_path / "v1.db"
    raw = sqlite3.connect(path)
    raw.executescript(V1_DOSSIERS)
    raw.execute("INSERT INTO dossiers (id, rfcv_number, filename, pdf_path, status, created_by, created_at,"
                " declared_by, declared_at) VALUES (7, 'RCSA1', 'a.pdf', 'p', 'declare', 'op', 't', 'op', 't2')")
    raw.execute("INSERT INTO generations (dossier_id, n, settings_json, created_by, created_at)"
                " VALUES (7, 1, '{}', 'op', 't')")
    raw.execute("INSERT INTO events (dossier_id, email, action, at) VALUES (7, 'op', 'creation', 't')")
    raw.commit()
    raw.close()

    conn = db.connect(path)
    db.init(conn)
    db.init(conn)                                       # idempotent
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 2
    row = conn.execute("SELECT * FROM dossiers WHERE id = 7").fetchone()
    assert (row["rfcv_number"], row["status"], row["declared_by"], row["declared_at"], row["declared_n"]) == \
        ("RCSA1", "declare", "op", "t2", None)
    conn.execute("UPDATE dossiers SET status = 'abandonne' WHERE id = 7")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE dossiers SET status = 'inconnu' WHERE id = 7")
    with pytest.raises(sqlite3.IntegrityError):         # clés étrangères toujours actives
        conn.execute("INSERT INTO generations (dossier_id, n, settings_json, created_by, created_at)"
                     " VALUES (999, 1, '{}', 'op', 't')")
    assert conn.execute("SELECT COUNT(*) FROM generations WHERE dossier_id = 7").fetchone()[0] == 1
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    indexes = {r[1] for r in conn.execute("PRAGMA index_list(dossiers)")}
    assert "idx_dossiers_rfcv" in indexes
    conn.close()
