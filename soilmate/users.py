"""User accounts stored in local PostgreSQL.

No third-party auth service is involved: passwords are hashed with bcrypt and
sessions are Flask's signed cookie.
"""

import re

import psycopg2
from flask_login import UserMixin

from db import db_cursor

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,30}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 8


class User(UserMixin):
    """Flask-Login user object backed by a `users` row."""

    def __init__(self, row):
        self.numeric_id = int(row["id"])
        self.id = str(row["id"])
        self.username = row["username"]
        self.email = row["email"]


def validate_registration(username, email, password):
    """Return an error message, or None when the input is acceptable."""
    if not USERNAME_RE.match(username or ""):
        return "Username must be 3-30 characters: letters, numbers, or underscore."
    if not EMAIL_RE.match(email or ""):
        return "Please enter a valid email address."
    if len(password or "") < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    return None


def find_by_id(user_id):
    try:
        numeric_id = int(user_id)
    except (TypeError, ValueError):
        return None

    with db_cursor() as cur:
        cur.execute("SELECT id, username, email FROM users WHERE id = %s", (numeric_id,))
        row = cur.fetchone()
    return User(row) if row else None


def find_by_login(identifier):
    """Look up by username or email (case-insensitive), including password hash."""
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT id, username, email, password_hash
            FROM users
            WHERE lower(username) = lower(%s) OR lower(email) = lower(%s)
            """,
            (identifier, identifier),
        )
        return cur.fetchone()


def create_user(username, email, password_hash):
    """Insert a new account. Raises ValueError if username/email is taken."""
    try:
        with db_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO users (username, email, password_hash)
                VALUES (%s, %s, %s)
                RETURNING id, username, email
                """,
                (username, email, password_hash),
            )
            return User(cur.fetchone())
    except psycopg2.errors.UniqueViolation:
        raise ValueError("That username or email is already registered.")
