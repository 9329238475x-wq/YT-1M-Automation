from __future__ import annotations

import json
import logging
import os
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from google_auth_oauthlib.flow import Flow
from fastapi import Request, Response

logger = logging.getLogger("auth")

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
CLIENT_SECRETS_FILE = PROJECT / "client_secrets.json"
USERS_FILE = ROOT / "users.json"
SESSIONS_FILE = ROOT / "sessions.json"
AUTH_STATES_FILE = ROOT / "oauth_user_states.json"

# Google Scopes for Pure User Authentication (Gmail / Google Account ONLY - No YouTube scopes)
USER_LOGIN_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]



# ================= DATA PERSISTENCE =================

def load_users() -> Dict[str, Dict[str, Any]]:
    """Loads all users dictionary keyed by email."""
    if not USERS_FILE.exists():
        return {}
    try:
        content = USERS_FILE.read_text(encoding="utf-8").strip()
        if not content:
            return {}
        data = json.loads(content)
        if isinstance(data, dict):
            return data
    except Exception as exc:
        logger.error(f"Error loading users.json: {exc}")
    return {}


def save_users(users: Dict[str, Dict[str, Any]]) -> None:
    """Persists users dictionary to users.json."""
    try:
        USERS_FILE.write_text(json.dumps(users, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except Exception as exc:
        logger.error(f"Error saving users.json: {exc}")


def load_sessions() -> Dict[str, Dict[str, Any]]:
    """Loads active session records keyed by session token."""
    if not SESSIONS_FILE.exists():
        return {}
    try:
        content = SESSIONS_FILE.read_text(encoding="utf-8").strip()
        if not content:
            return {}
        data = json.loads(content)
        if isinstance(data, dict):
            return data
    except Exception as exc:
        logger.error(f"Error loading sessions.json: {exc}")
    return {}


def save_sessions(sessions: Dict[str, Dict[str, Any]]) -> None:
    """Persists sessions dictionary to sessions.json."""
    try:
        SESSIONS_FILE.write_text(json.dumps(sessions, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except Exception as exc:
        logger.error(f"Error saving sessions.json: {exc}")


def _save_auth_state(state: str, verifier: Optional[str]) -> None:
    data = {}
    if AUTH_STATES_FILE.exists():
        try:
            data = json.loads(AUTH_STATES_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data[state] = {
        "verifier": verifier,
        "created_at": datetime.now().isoformat()
    }
    AUTH_STATES_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _get_auth_state_verifier(state: str) -> Optional[str]:
    if not AUTH_STATES_FILE.exists():
        return None
    try:
        data = json.loads(AUTH_STATES_FILE.read_text(encoding="utf-8"))
        if state in data:
            entry = data.pop(state)
            try:
                AUTH_STATES_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
            except Exception:
                pass
            return entry.get("verifier")
    except Exception as exc:
        logger.warning(f"Error popping auth state {state}: {exc}")
    return None


def ensure_client_secrets() -> None:
    """Restores client_secrets.json from GOOGLE_CLIENT_SECRETS_JSON env var if missing."""
    if not CLIENT_SECRETS_FILE.exists():
        env_content = os.getenv("GOOGLE_CLIENT_SECRETS_JSON", "").strip()
        if env_content:
            try:
                CLIENT_SECRETS_FILE.write_text(env_content, encoding="utf-8")
                logger.info("Restored client_secrets.json from GOOGLE_CLIENT_SECRETS_JSON environment variable.")
            except Exception as exc:
                logger.error(f"Failed to write client_secrets.json: {exc}")

# ================= OAUTH FLOW =================

def get_google_auth_url(redirect_uri: str) -> tuple[str, str]:
    """Generates the Google OAuth authorization URL for user login."""
    ensure_client_secrets()
    if not CLIENT_SECRETS_FILE.exists():
        raise FileNotFoundError(f"client_secrets.json not found in project root: {CLIENT_SECRETS_FILE}")

    flow = Flow.from_client_secrets_file(
        str(CLIENT_SECRETS_FILE),
        scopes=USER_LOGIN_SCOPES,
        redirect_uri=redirect_uri
    )
    auth_url, state = flow.authorization_url(
        prompt="select_account consent",
        access_type="offline"
    )
    if getattr(flow, "code_verifier", None):
        _save_auth_state(state, flow.code_verifier)
    return auth_url, state


def process_user_oauth(code: str, redirect_uri: str, state: Optional[str] = None) -> Dict[str, Any]:
    """
    Exchanges code for credentials, queries Google UserInfo API,
    and returns a user dictionary.
    """
    ensure_client_secrets()
    if not CLIENT_SECRETS_FILE.exists():
        raise FileNotFoundError(f"client_secrets.json not found in project root: {CLIENT_SECRETS_FILE}")

    flow = Flow.from_client_secrets_file(
        str(CLIENT_SECRETS_FILE),
        scopes=USER_LOGIN_SCOPES,
        redirect_uri=redirect_uri,
        state=state
    )
    if state:
        verifier = _get_auth_state_verifier(state)
        if verifier:
            flow.code_verifier = verifier

    flow.fetch_token(code=code)
    credentials = flow.credentials

    # Fetch user info using Google OAuth2 Userinfo endpoint
    user_info = {}
    try:
        resp = requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {credentials.token}"},
            timeout=10
        )
        if resp.ok:
            user_info = resp.json()
        else:
            logger.warning(f"Failed to fetch userinfo from Google: {resp.status_code} {resp.text}")
    except Exception as exc:
        logger.error(f"Error contacting userinfo endpoint: {exc}")

    email = user_info.get("email") or ""
    if not email:
        raise ValueError("Could not retrieve email from Google Account.")

    name = user_info.get("name") or email.split("@")[0]
    picture = user_info.get("picture") or ""
    sub = user_info.get("sub") or str(uuid.uuid4())

    # Save or update user
    users = load_users()
    now_str = datetime.now().isoformat()

    if email in users:
        user = users[email]
        user["name"] = name
        user["picture"] = picture
        user["last_login"] = now_str
    else:
        user = {
            "id": sub,
            "email": email,
            "name": name,
            "picture": picture,
            "created_at": now_str,
            "last_login": now_str,
            "channels": []
        }
        users[email] = user

    save_users(users)
    return user


# ================= SESSION MANAGEMENT =================

SESSION_COOKIE_NAME = "yt1m_session"
SESSION_DURATION_DAYS = 30


def create_session(email: str) -> str:
    """Creates a new session token for the given user email."""
    session_token = "sess_" + uuid.uuid4().hex + uuid.uuid4().hex[:8]
    sessions = load_sessions()
    now = datetime.now()
    expires_at = now + timedelta(days=SESSION_DURATION_DAYS)

    sessions[session_token] = {
        "email": email,
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat()
    }
    save_sessions(sessions)
    return session_token


def terminate_session(session_token: str) -> None:
    """Removes a session token."""
    sessions = load_sessions()
    if session_token in sessions:
        sessions.pop(session_token, None)
        save_sessions(sessions)


def get_current_user_from_request(request: Request) -> Optional[Dict[str, Any]]:
    """Extracts session token from cookie or header and returns user dict."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        # Check Authorization header Bearer token
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()

    if not token:
        return None

    sessions = load_sessions()
    session_data = sessions.get(token)
    if not session_data:
        return None

    # Check expiration
    expires_at_str = session_data.get("expires_at")
    if expires_at_str:
        try:
            expires_at = datetime.fromisoformat(expires_at_str)
            if datetime.now() > expires_at:
                terminate_session(token)
                return None
        except Exception:
            pass

    email = session_data.get("email")
    if not email:
        return None

    users = load_users()
    user = users.get(email)
    if user:
        return user

    # Fallback user if missing from users.json
    return {
        "email": email,
        "name": email.split("@")[0],
        "picture": "",
        "channels": []
    }


def attach_channel_to_user(email: str, channel_id: str) -> None:
    """Links a channel ID to the user's account in users.json."""
    users = load_users()
    if email not in users:
        users[email] = {
            "email": email,
            "name": email.split("@")[0],
            "picture": "",
            "created_at": datetime.now().isoformat(),
            "last_login": datetime.now().isoformat(),
            "channels": [channel_id]
        }
    else:
        chan_list = users[email].get("channels", [])
        if channel_id not in chan_list:
            chan_list.append(channel_id)
            users[email]["channels"] = chan_list

    save_users(users)
