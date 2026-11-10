"""Regression tests for history ownership scoping.

Run with:  python tests/test_history.py
No database connection is opened.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from history import (  # noqa: E402
    _scan_ids_from_intents,
    _scope,
    _session_for_storage,
    delete_scan,
    delete_user_history,
)

failures = []


def check(condition, label):
    if not condition:
        failures.append(label)


def scoped(session_id=None, user_id=None, prefix="AND"):
    params = []
    query = _scope("SELECT * FROM scans WHERE TRUE", params, session_id, user_id, prefix=prefix)
    return query, params


query, params = scoped(session_id="sess-1", user_id=3)
check("user_id = %s" in query, "logged-in query should filter by user_id")
check("session_id" not in query, "logged-in query must not use session_id")
check(params == [3], "logged-in params should be the user id")

query, params = scoped(session_id="sess-1", user_id=None)
check("session_id = %s" in query, "guest query should filter by session_id")
check("user_id IS NULL" in query, "guest query must exclude account-owned rows")
check(params == ["sess-1"], "guest params should be the session id")

query, params = scoped(session_id=None, user_id=None)
check(query.endswith("FALSE"), "missing owner should return no rows")
check(params == [], "missing owner should have no params")

query, params = scoped(session_id="sess-1", user_id=None, prefix="WHERE")
check("WHERE session_id" in query, "custom prefix should be honored")

check(_session_for_storage("sess-1", 3) is None, "account rows must not store a session id")
check(_session_for_storage("sess-1", None) == "sess-1", "guest rows keep their session id")

# Guests have no id, so the history deletion helpers must refuse to run.
check(delete_user_history(None) == (0, 0, []), "guests must not be able to delete history")
check(delete_scan(1, None) is None, "guests must not be able to delete a single scan")

# Scan turns are linked to a conversation through "scan:<id>" intent values.
check(
    _scan_ids_from_intents([
        {"intent": "scan:12"},
        {"intent": "scan:7"},
        {"intent": "scan:not-a-number"},
        {"intent": "greeting"},
        {"intent": None},
        {},
    ]) == [12, 7],
    "scan ids should be parsed from scan intents only",
)

if failures:
    print(f"FAILED ({len(failures)}):")
    for failure in failures:
        print("  -", failure)
    sys.exit(1)

print("All history scoping tests passed.")
