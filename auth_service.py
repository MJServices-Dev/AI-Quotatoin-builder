"""
auth_service.py — Flask-compatible port of chatbot/auth.py.
Uses db_service.supabase instead of the Streamlit-dependent chatbot/db.py.
All function signatures are identical so chatbot logic can be reused directly.

Message ordering strategy
─────────────────────────
The Supabase `chats` table stores one row per user-message/assistant-response
pair. Row insertion order is not guaranteed when multiple rows are bulk-inserted
in the same request — leading to shuffled history on reload.

Fix: every save_history call writes ONE extra "anchor" row that encodes the
complete, ordered message list as a JSON array (messages_json column).
load_history_file reads that column first; if unavailable it falls back to
reconstructing from individual rows sorted by seq then created_at.
"""

import re
import json
import hashlib
from datetime import datetime
import traceback
from werkzeug.security import generate_password_hash, check_password_hash

from db_service import supabase


# ─── Password & Key Helpers ──────────────────────────────────────────────────

def hash_pw(pw: str) -> str:
    """Hash of a password string."""
    return generate_password_hash(pw.strip())


def company_key(company: str) -> str:
    """Normalised key from company name (used as login ID)."""
    cleaned = re.sub(r"[^a-z0-9_]", " ", company.strip().lower())
    key = "_".join(cleaned.split())
    return key or "unknown"


# ─── User CRUD ───────────────────────────────────────────────────────────────

def register_user(name: str, company: str, phone: str, email: str, password: str) -> tuple:
    """Register a new user with role='user'. Returns (success, key_or_error)."""
    key = company_key(company)
    if not key:
        return False, "Company name is invalid."
    try:
        existing = supabase.table("users").select("id").eq("key", key).execute()
        if existing.data:
            return False, "A company with that name is already registered."
    except Exception as e:
        return False, f"Database connection error. ({type(e).__name__})"
    try:
        supabase.table("users").insert({
            "key": key,
            "name": name.strip(),
            "company": company.strip(),
            "phone": phone.strip(),
            "email": email.strip(),
            "pw_hash": hash_pw(password),
            "role": "user",
        }).execute()
        return True, key
    except Exception as e:
        return False, f"Registration failed: {e}"


def login_user(company: str, password: str) -> tuple:
    """Authenticate a user. Returns (success, key_or_error, user_dict)."""
    key = company_key(company)
    try:
        result = supabase.table("users").select("*").eq("key", key).execute()
    except Exception as e:
        return False, f"Database connection error. ({type(e).__name__})", {}
    if not result.data:
        return False, "Company not found. Please register first.", {}
    user = result.data[0]
    
    # Backwards compatibility check
    db_hash = user.get("pw_hash", "")
    if db_hash.startswith("pbkdf2:sha256:") or db_hash.startswith("scrypt:"):
        is_valid = check_password_hash(db_hash, password)
    else:
        # Legacy unsalted SHA-256
        is_valid = (db_hash == hashlib.sha256(password.strip().encode()).hexdigest())

    if not is_valid:
        return False, "Wrong password.", {}
    return True, key, {
        "key": user["key"],
        "name": user["name"],
        "company": user["company"],
        "phone": user.get("phone", ""),
        "email": user.get("email", ""),
        "role": user.get("role", "user"),
    }


def is_admin(user: dict) -> bool:
    """Check if a user dict has the admin role."""
    return user.get("role") == "admin"


# ─── Chat History ─────────────────────────────────────────────────────────────

def save_history(user_key: str, session_id: str, messages: list, title: str):
    """
    Save/update a chat session to Supabase.

    Strategy (order-preserving):
    1. Delete all existing rows for this session.
    2. Insert one row per user/assistant pair (legacy compatibility).
    3. Insert ONE EXTRA "anchor" row (seq=-1) that stores the complete ordered
       message list as JSON in the `messages_json` column.  This is the
       authoritative source used by load_history_file so order is always exact.
    """
    try:
        supabase.table("chats").delete() \
            .eq("user_key", user_key).eq("session_id", session_id).execute()

        rows: list = []
        seq  = 0
        i    = 0
        while i < len(messages):
            msg = messages[i]
            if msg["role"] == "user":
                user_msg      = msg["content"]
                assistant_msg = ""
                if i + 1 < len(messages) and messages[i + 1]["role"] == "assistant":
                    assistant_msg = messages[i + 1]["content"]
                    i += 1
                rows.append({
                    "user_key": user_key, "session_id": session_id, "title": title,
                    "user_message": user_msg, "assistant_response": assistant_msg,
                    "seq": seq,
                })
                seq += 1
            elif msg["role"] == "assistant" and not rows:
                # AI greeting — no user message precedes it
                rows.append({
                    "user_key": user_key, "session_id": session_id, "title": title,
                    "user_message": "", "assistant_response": msg["content"],
                    "seq": seq,
                })
                seq += 1
            i += 1

        # ── Anchor row: full ordered message list ─────────────────────────────
        # seq = -1 so it sorts before all real rows and is easy to identify.
        anchor = {
            "user_key":       user_key,
            "session_id":     session_id,
            "title":          title,
            "user_message":   "__messages_json__",   # sentinel — never shown
            "assistant_response": json.dumps(messages, ensure_ascii=False),
            "seq":            -1,
        }

        all_rows = [anchor] + rows

        try:
            supabase.table("chats").insert(all_rows).execute()
        except Exception:
            # `seq` column may not exist yet — retry without it
            rows_no_seq = [{k: v for k, v in r.items() if k != "seq"} for r in all_rows]
            supabase.table("chats").insert(rows_no_seq).execute()
    except Exception as e:
        print(f"[save_history] Error: {e}")
        traceback.print_exc()


def list_histories(user_key: str) -> list:
    """List all saved chat sessions for a user, newest first."""
    try:
        result = (
            supabase.table("chats")
            .select("session_id, title, created_at, seq")
            .eq("user_key", user_key)
            .order("created_at", desc=True)
            .execute()
        )
    except Exception:
        try:
            result = (
                supabase.table("chats")
                .select("session_id, title, created_at")
                .eq("user_key", user_key)
                .order("created_at", desc=True)
                .execute()
            )
        except Exception:
            return []
    sessions = {}
    for row in result.data:
        sid = row["session_id"]
        if sid == "__quotation_metrics__":
            continue
        if sid not in sessions:
            sessions[sid] = {
                "title": row["title"] or "Untitled",
                "saved_at": _iso_to_ts(row["created_at"]),
                "messages": [],
            }
        if row.get("seq") != -1:
            sessions[sid]["messages"].append(1)
    items = sorted(sessions.items(), key=lambda x: x[1]["saved_at"], reverse=True)
    return [(f"{sid}.json", meta) for sid, meta in items]


def load_history_file(user_key: str, filename: str) -> dict:
    """
    Load a specific chat session, preserving exact message order.

    Priority:
    1. Anchor row (seq=-1 / user_message='__messages_json__'): contains the
       complete ordered message list as JSON — used when present.
    2. Fallback: reconstruct from individual rows sorted by seq then created_at.
    """
    session_id = filename.replace(".json", "")

    # ── Fetch all rows, ordered by seq ascending ──────────────────────────────
    try:
        result = (
            supabase.table("chats")
            .select("user_message, assistant_response, title, created_at, seq")
            .eq("user_key", user_key)
            .eq("session_id", session_id)
            .order("seq", desc=False)
            .execute()
        )
    except Exception:
        # seq column missing — fall back to created_at ordering
        result = (
            supabase.table("chats")
            .select("user_message, assistant_response, title, created_at")
            .eq("user_key", user_key)
            .eq("session_id", session_id)
            .order("created_at", desc=False)
            .execute()
        )

    rows  = result.data or []
    title = "Untitled"

    # ── Strategy 1: anchor row with full JSON ─────────────────────────────────
    for row in rows:
        if row.get("user_message") == "__messages_json__":
            title = row.get("title") or title
            try:
                messages = json.loads(row["assistant_response"])
                if isinstance(messages, list) and messages:
                    return {"messages": messages, "title": title}
            except (json.JSONDecodeError, TypeError):
                pass  # fall through to strategy 2
            break

    # ── Strategy 2: reconstruct from individual pair rows ─────────────────────
    # Sort rows: seq=-1 anchor first (skip it), then by seq asc, then created_at
    pair_rows = [
        r for r in rows
        if r.get("user_message") != "__messages_json__"
    ]
    # Re-sort robustly: rows with valid seq ASC, then by created_at
    def _sort_key(r):
        seq_val = r.get("seq")
        if seq_val is None or seq_val < 0:
            seq_val = 9999
        return (seq_val, r.get("created_at") or "")

    pair_rows.sort(key=_sort_key)

    messages: list = []
    for row in pair_rows:
        title = row.get("title") or title
        um = row.get("user_message", "")
        ar = row.get("assistant_response", "")
        # Emit in the correct conversation order:
        # If there's no user message this is an AI-only row (greeting)
        if um:
            messages.append({"role": "user",      "content": um})
        if ar:
            messages.append({"role": "assistant", "content": ar})

    return {"messages": messages, "title": title}


def delete_history_file(user_key: str, filename: str):
    """Delete a saved chat session."""
    try:
        session_id = filename.replace(".json", "")
        supabase.table("chats").delete().eq("user_key", user_key).eq("session_id", session_id).execute()
    except Exception as e:
        print(f"[delete_history_file] Error: {e}")
        traceback.print_exc()


def make_title(messages: list) -> str:
    """Generate a title from the first user message."""
    for m in messages:
        if m["role"] == "user":
            txt = m["content"].strip().replace("\n", " ")
            return txt[:45] + ("…" if len(txt) > 45 else "")
    return "Untitled chat"


# ─── Admin Helpers ────────────────────────────────────────────────────────────

def list_all_users() -> list:
    """Return all registered users (for admin dashboard)."""
    try:
        result = (
            supabase.table("users")
            .select("key, name, company, phone, email, role, created_at")
            .order("created_at", desc=True)
            .execute()
        )
        return result.data
    except Exception as e:
        print(f"[list_all_users] Error: {e}")
        traceback.print_exc()
        return []



def admin_delete_session(user_key: str, session_id: str):
    """Delete all chat rows for a given session (admin only)."""
    try:
        supabase.table("chats").delete().eq("user_key", user_key).eq("session_id", session_id).execute()
    except Exception as e:
        print(f"[admin_delete_session] Error: {e}")
        traceback.print_exc()

def increment_quotation_count(user_key: str):
    """Log a generated quotation using the chats table as persistent storage."""
    try:
        supabase.table("chats").insert({
            "user_key": user_key,
            "session_id": "__quotation_metrics__",
            "title": "Quotation Generated",
            "user_message": "quotation_generated",
            "assistant_response": datetime.now().isoformat()
        }).execute()
    except Exception as e:
        print(f"[increment_quotation_count] Error: {e}")

def get_quotation_counts() -> dict:
    """Return a dictionary of user_key -> quotation_count."""
    try:
        res = supabase.table("chats").select("user_key").eq("session_id", "__quotation_metrics__").execute()
        counts = {}
        for row in res.data:
            uk = row.get("user_key")
            if uk:
                counts[uk] = counts.get(uk, 0) + 1
        return counts
    except Exception as e:
        print(f"[get_quotation_counts] Error: {e}")
        return {}


# ─── Internal Helpers ─────────────────────────────────────────────────────────

def _iso_to_ts(iso_str: str) -> float:
    """Convert ISO datetime string to Unix timestamp."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.timestamp()
    except Exception:
        return 0.0
