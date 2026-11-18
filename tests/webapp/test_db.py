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
