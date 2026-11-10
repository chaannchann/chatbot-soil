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


def log_chat(session_id, role, message, intent=None, confidence=None,
             user_id=None, conversation_id=None):
    """Store one chat message (role is 'user' or 'bot')."""
    stored_session = _session_for_storage(session_id, user_id)
    try:
        with db_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO chat_logs
                    (session_id, user_id, conversation_id, role, message, intent, confidence)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (stored_session, user_id, conversation_id, role, message, intent, confidence),
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
    responsible for removing the uploaded file. Chat turns that reference the
    scan are removed too so the conversation does not keep a broken photo.
    """
    if user_id is None:
        return None

    with db_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM scans WHERE id = %s AND user_id = %s RETURNING filename",
            (scan_id, user_id),
        )
        row = cur.fetchone()

        if row:
            cur.execute(
                "DELETE FROM chat_logs WHERE user_id = %s AND intent = %s",
                (user_id, f"scan:{scan_id}"),
            )

    if not row:
        return None
    return row.get("filename") or ""


def conversation_for_scan(scan_id, user_id):
    """Conversation that contains a scan's chat turns, if one exists."""
    if user_id is None:
        return None

    try:
        with db_cursor() as cur:
            cur.execute(
                """
                SELECT conversation_id
                FROM chat_logs
                WHERE user_id = %s AND intent = %s
                  AND conversation_id IS NOT NULL AND conversation_id <> ''
                ORDER BY id DESC
                LIMIT 1
                """,
                (user_id, f"scan:{scan_id}"),
            )
            row = cur.fetchone()
        return row["conversation_id"] if row else None
    except Exception as error:  # noqa: BLE001
        _warn("load scan conversation", error)
        return None


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


def _scan_ids_from_intents(rows):
    """Extract numeric scan ids from ``scan:<id>`` intent values."""
    scan_ids = []
    for row in rows:
        intent = row.get("intent") if hasattr(row, "get") else None
        if not intent or not intent.startswith("scan:"):
            continue
        try:
            scan_ids.append(int(intent.split(":", 1)[1]))
        except (TypeError, ValueError):
            continue
    return scan_ids


def _conversation_filter(conversation_id):
    """SQL condition and params that select one conversation.

    Messages written before conversation ids were introduced have no value,
    so they are grouped under the synthetic ``"legacy"`` id.
    """
    if not conversation_id or conversation_id == "legacy":
        return "conversation_id IS NULL", []
    return "conversation_id = %s", [conversation_id]


def ensure_scan_conversations(user_id):
    """Give older scans a conversation so they appear in the unified history.

    New uploads are logged as chat turns directly. Scans saved before that
    change only live in the ``scans`` table, so this backfills one conversation
    per scan. Safe to run repeatedly.
    """
    if user_id is None:
        return

    try:
        with db_cursor(commit=True) as cur:
            cur.execute(
                """
                SELECT s.id, s.predicted_soil, s.confidence, s.identified, s.created_at
                FROM scans s
                WHERE s.user_id = %s
                  AND NOT EXISTS (
                      SELECT 1
                      FROM chat_logs c
                      WHERE c.user_id = s.user_id
                        AND c.intent = 'scan:' || s.id
                  )
                ORDER BY s.created_at ASC, s.id ASC
                """,
                (user_id,),
            )
            scans = [dict(row) for row in cur.fetchall()]

            for scan in scans:
                label = (
                    scan["predicted_soil"]
                    if scan["identified"] and scan["predicted_soil"]
                    else "Soil"
                )
                if scan["identified"] and scan["predicted_soil"]:
                    bot_message = (
                        f"{scan['predicted_soil']} detected with "
                        f"{(scan['confidence'] or 0):.0%} confidence."
                    )
                else:
                    bot_message = "This scan could not be identified."

                conversation_id = f"scan-{scan['id']}"
                intent = f"scan:{scan['id']}"
                cur.execute(
                    """
                    INSERT INTO chat_logs
                        (user_id, conversation_id, role, message, intent, confidence, created_at)
                    VALUES
                        (%s, %s, 'user', %s, %s, %s, %s),
                        (%s, %s, 'bot', %s, %s, %s, %s)
                    """,
                    (
                        user_id, conversation_id, f"{label} scan", intent,
                        None, scan["created_at"],
                        user_id, conversation_id, bot_message, intent,
                        scan["confidence"], scan["created_at"],
                    ),
                )
    except Exception as error:  # noqa: BLE001
        _warn("backfill scan conversations", error)


def recent_conversations(user_id, limit=20):
    """Most recent conversations for one account, newest first.

    A conversation is the set of chat rows sharing a ``conversation_id``.
    Older rows without one are reported together as ``legacy``.
    """
    if user_id is None:
        return []

    sql = """
        SELECT g.conversation_id,
               MIN(g.created_at) AS started_at,
               MAX(g.created_at) AS updated_at,
               COUNT(*) AS message_count,
               (
                   SELECT c2.message
                   FROM chat_logs c2
                   WHERE c2.user_id = %s
                     AND COALESCE(c2.conversation_id, 'legacy') = g.conversation_id
                     AND c2.role = 'user'
                   ORDER BY c2.created_at ASC, c2.id ASC
                   LIMIT 1
               ) AS title
        FROM (
            SELECT COALESCE(conversation_id, 'legacy') AS conversation_id,
                   created_at
            FROM chat_logs
            WHERE user_id = %s
        ) AS g
        GROUP BY g.conversation_id
        ORDER BY updated_at DESC
        LIMIT %s
    """
    params = [user_id, user_id, limit]

    try:
        with db_cursor() as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]
    except Exception as error:  # noqa: BLE001
        _warn("load conversations", error)
        return []


def conversation_messages(user_id, conversation_id, limit=200):
    """Messages in one conversation, oldest first."""
    if user_id is None:
        return []

    condition, condition_params = _conversation_filter(conversation_id)
    sql = f"""
        SELECT id, role, message, intent, confidence, created_at
        FROM chat_logs
        WHERE user_id = %s AND {condition}
        ORDER BY created_at DESC, id DESC
        LIMIT %s
    """
    params = [user_id] + condition_params + [limit]

    try:
        with db_cursor() as cur:
            cur.execute(sql, params)
            rows = [dict(row) for row in cur.fetchall()]
        return list(reversed(rows))
    except Exception as error:  # noqa: BLE001
        _warn("load conversation", error)
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

def delete_conversation(user_id, conversation_id):
    """Delete one conversation and any scans it contains.

    Returns ``(deleted_message_count, filenames)`` so the caller can remove the
    uploaded images too. A scan is linked to its conversation through the
    ``scan:<id>`` value stored in ``chat_logs.intent``.
    """
    if user_id is None:
        return 0, []

    condition, condition_params = _conversation_filter(conversation_id)
    params = [user_id] + condition_params

    with db_cursor(commit=True) as cur:
        cur.execute(
            f"""
            SELECT DISTINCT intent
            FROM chat_logs
            WHERE user_id = %s AND {condition} AND intent LIKE 'scan:%%'
            """,
            params,
        )
        scan_ids = _scan_ids_from_intents(cur.fetchall())

        filenames = []
        if scan_ids:
            cur.execute(
                "DELETE FROM scans WHERE user_id = %s AND id = ANY(%s) RETURNING filename",
                (user_id, scan_ids),
            )
            filenames = [
                row["filename"] for row in cur.fetchall() if row.get("filename")
            ]

        cur.execute(
            f"DELETE FROM chat_logs WHERE user_id = %s AND {condition}",
            params,
        )
        return cur.rowcount, filenames


def delete_all_chats(user_id):
    """Delete all chat history owned by user_id, including scan conversations.

    Returns ``(deleted_message_count, filenames)`` so the caller can remove the
    uploaded images that belonged to those conversations.
    """
    if user_id is None:
        return 0, []

    with db_cursor(commit=True) as cur:
        cur.execute(
            "SELECT DISTINCT intent FROM chat_logs WHERE user_id = %s AND intent LIKE 'scan:%%'",
            (user_id,),
        )
        scan_ids = _scan_ids_from_intents(cur.fetchall())

        filenames = []
        if scan_ids:
            cur.execute(
                "DELETE FROM scans WHERE user_id = %s AND id = ANY(%s) RETURNING filename",
                (user_id, scan_ids),
            )
            filenames = [
                row["filename"] for row in cur.fetchall() if row.get("filename")
            ]

        cur.execute("DELETE FROM chat_logs WHERE user_id = %s", (user_id,))
        return cur.rowcount, filenames