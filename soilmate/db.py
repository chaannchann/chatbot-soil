"""Shared PostgreSQL access helpers.

Kept in its own module so app.py, planting.py, and the history/accounts code
can all use the same connection settings without importing each other.
"""

from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor

from config import Config


def get_db():
    """Open a new connection using credentials from .env."""
    return psycopg2.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        database=Config.DB_NAME,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        cursor_factory=RealDictCursor,
    )


@contextmanager
def db_cursor(commit=False):
    """Yield a cursor and always close the connection afterwards."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            yield cur
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
