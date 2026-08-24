"""Shared PostgreSQL thread-local access for Tenshin Arts apps.

Canonical source: website/dropins/ — sync with deploy/sync-dropins.sh.
Each app calls configure() once, then uses db() and init_schema().
"""
from __future__ import annotations

import threading

import psycopg
from psycopg.rows import dict_row

_local = threading.local()
_url_fn = None


def configure(get_database_url):
    """Register how to resolve DATABASE_URL (callable or string)."""
    global _url_fn
    if callable(get_database_url):
        _url_fn = get_database_url
    else:
        _url_fn = lambda: get_database_url  # noqa: E731


def _resolve_url() -> str:
    if _url_fn is None:
        raise RuntimeError("tenshin_db.configure() was not called")
    url = _url_fn()
    scheme = url.split(":", 1)[0].lower()
    if scheme not in ("postgresql", "postgres"):
        raise RuntimeError(
            f"DATABASE_URL must be PostgreSQL (got {scheme!r}). "
            "The fleet does not use SQLite.")
    return url


def _connect():
    return psycopg.connect(_resolve_url(), row_factory=dict_row)


class Cursor:
    def __init__(self, cur):
        self._cur = cur

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    def __iter__(self):
        return iter(self._cur)

    @property
    def lastrowid(self):
        row = self._cur.fetchone()
        return row["id"] if row else None


class Connection:
    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=None):
        cur = self._conn.cursor()
        cur.execute(sql.replace("?", "%s"), params or ())
        return Cursor(cur)

    def executemany(self, sql, params_seq):
        cur = self._conn.cursor()
        cur.executemany(sql.replace("?", "%s"), params_seq)
        return Cursor(cur)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()


def db():
    """Per-thread connection. Web workers never share a transaction."""
    conn = getattr(_local, "conn", None)
    if conn is None or conn.closed:
        conn = _connect()
        _local.conn = conn
    return Connection(conn)


def init_schema(statements):
    c = db()
    for stmt in statements:
        c.execute(stmt)
    c.commit()


def demo_connection():
    """Connect for module self-checks; caller must rollback and close."""
    conn = psycopg.connect(_resolve_url(), row_factory=dict_row)
    conn.autocommit = False
    return Connection(conn)
