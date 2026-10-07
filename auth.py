"""Team login: one shared team password, and a signed cookie to remember who logged in.

How the cookie works:
- After a correct password, the server gives the browser a "session token":
  an expiry time plus a signature, e.g. "1760000000.ab12cd...".
- The signature is made with a secret key only the server knows (HMAC).
  If anyone edits the token (say, to extend the expiry), the signature no longer
  matches, so faking a login is not possible without the secret key.
"""
import hashlib
import hmac
import os
import secrets
import time

from dotenv import load_dotenv
from fastapi import HTTPException, Request

load_dotenv()

# Shared demo password, published in the README so recruiters can try the dashboard.
# Set TEAM_PASSWORD in the environment to use a private one instead.
DEMO_PASSWORD = "demo123"
TEAM_PASSWORD = os.environ.get("TEAM_PASSWORD", DEMO_PASSWORD)

# Key used to sign session tokens. Without SECRET_KEY set, a random one is made
# each time the server starts, which simply logs everyone out after a restart.
SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

COOKIE_NAME = "buglens_session"
SESSION_SECONDS = 24 * 60 * 60  # stay logged in for one day


def password_is_correct(password: str) -> bool:
    # compare_digest takes the same time whether the first or last letter is wrong,
    # so attackers can't guess the password letter by letter from response times.
    return hmac.compare_digest(password.encode(), TEAM_PASSWORD.encode())


def using_demo_password() -> bool:
    return TEAM_PASSWORD == DEMO_PASSWORD


def _sign(payload: str) -> str:
    return hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()


def create_session_token() -> str:
    expires = str(int(time.time()) + SESSION_SECONDS)
    return f"{expires}.{_sign(expires)}"


def is_logged_in(request: Request) -> bool:
    token = request.cookies.get(COOKIE_NAME, "")
    expires, _, signature = token.partition(".")
    if not expires.isdigit() or not hmac.compare_digest(signature, _sign(expires)):
        return False
    return int(expires) > time.time()


def require_team(request: Request):
    """Attach to any route that only team members may use."""
    if not is_logged_in(request):
        raise HTTPException(status_code=401, detail="Please log in as a team member.")
