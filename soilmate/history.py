"""Persistence for scan and chat history.

Logging is best-effort: if PostgreSQL is unavailable the chatbot and soil
analysis must keep working, so failures are reported on stderr instead of
being raised into the request.
"""

import sys

from db import db_cursor


def _warn(action, error):
    print(f"[history] could not {action}: {error}", file=sys.stderr)


def _session_for_storage(session_id, user_id):
    """Account rows must not also carry a browser session id.

    Otherwise logging out and continuing as a guest would expose the account's
    history through the old session-scoped query.
    """
    return None if user_id is not None else session_id


def log_chat(session_id, role, message, intent=None, confidence=None, user_id=None):
    """Store one chat message (role is 'user' or 'bot')."""
    stored_session = _session_for_storage(session_id, user_id)
    try:
        with db_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO chat_logs (session_id, user_id, role, message, intent, confidence)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (stored_session, user_id, role, message, intent, confidence),
            )
        return True
    except Exception as error:  # noqa: BLE001 - logging must never break a request
        _warn("save chat message", error)
        return False


def log_scan(session_id, filename, predicted_soil, confidence, identified, user_id=None):
    """Store one soil-image prediction and return its new id (or None)."""
    stored_session = _session_for_storage(session_id, user_id)
    try:
        with db_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO scans
                    (session_id, user_id, filename, predicted_soil, confidence, identified)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (stored_session, user_id, filename, predicted_soil, confidence, identified),
            )
            return cur.fetchone()["id"]
    except Exception as error:  # noqa: BLE001
        _warn("save scan", error)
        return None


def delete_scan(scan_id, user_id):
    """Delete one scan owned by ``user_id`` and return its filename.

    Returns ``None`` when no such scan belongs to that account. The caller is
    responsible for removing the uploaded file.
    """
    if user_id is None:
        return None

    with db_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM scans WHERE id = %s AND user_id = %s RETURNING filename",
            (scan_id, user_id),
        )
        row = cur.fetchone()

    if not row:
        return None
    return row.get("filename") or ""


def delete_user_history(user_id):
    """Delete all scans and chat messages owned by one account.

    Returns ``(scan_count, chat_count, filenames)`` so the caller can also
    remove the uploaded image files. Guest ids are intentionally rejected.
    """
    if user_id is None:
        return 0, 0, []

    with db_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM scans WHERE user_id = %s RETURNING filename",
            (user_id,),
        )
        rows = cur.fetchall()
        filenames = [row["filename"] for row in rows if row.get("filename")]

        cur.execute("DELETE FROM chat_logs WHERE user_id = %s", (user_id,))
        chat_count = cur.rowcount

    return len(rows), chat_count, filenames


def _scope(query, params, session_id, user_id, prefix="AND"):
    """Restrict history to one owner.

    Account rows are matched by ``user_id`` only. Guest rows are matched by
    ``session_id`` *and* ``user_id IS NULL`` so a logged-in user's history can
    never leak back through the browser session after logout. With neither
    owner, return no rows instead of every row in the table.
    """
    if user_id is not None:
        query += f" {prefix} user_id = %s"
        params.append(user_id)
    elif session_id:
        query += f" {prefix} session_id = %s AND user_id IS NULL"
        params.append(session_id)
    else:
        query += f" {prefix} FALSE"
    return query


def recent_scans(session_id=None, user_id=None, limit=12):
    """Most recent scans for a user, or for an anonymous session."""
    sql = "SELECT id, filename, predicted_soil, confidence, identified, created_at FROM scans WHERE TRUE"
    params = []
    sql = _scope(sql, params, session_id, user_id)
    sql += " ORDER BY created_at DESC, id DESC LIMIT %s"
    params.append(limit)

    try:
        with db_cursor() as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]
    except Exception as error:  # noqa: BLE001
        _warn("load scans", error)
        return []


def recent_chats(session_id=None, user_id=None, limit=40):
    """Chat messages in chronological order, ready to replay into the feed."""
    sql = "SELECT id, role, message, intent, confidence, created_at FROM chat_logs WHERE TRUE"
    params = []
    sql = _scope(sql, params, session_id, user_id)
    sql += " ORDER BY created_at DESC, id DESC LIMIT %s"
    params.append(limit)

    try:
        with db_cursor() as cur:
            cur.execute(sql, params)
            rows = [dict(row) for row in cur.fetchall()]
        return list(reversed(rows))
    except Exception as error:  # noqa: BLE001
        _warn("load chat history", error)
        return []


def get_scan(scan_id, session_id=None, user_id=None):
    """Fetch a single scan, scoped to the current user or session."""
    sql = """
        SELECT id, filename, predicted_soil, confidence, identified, created_at
        FROM scans
        WHERE id = %s
    """
    params = [scan_id]
    sql = _scope(sql, params, session_id, user_id)

    try:
        with db_cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
        return dict(row) if row else None
    except Exception as error:  # noqa: BLE001
        _warn("load scan", error)
        return None
