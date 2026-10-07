import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from ai import AIError, structure_report
from auth import (
    COOKIE_NAME, DEMO_PASSWORD, SESSION_SECONDS, create_session_token,
    is_logged_in, password_is_correct, require_team, using_demo_password,
)
from database import get_connection, init_db, row_to_dict, seed_demo_data
from schemas import (
    Bug, BugCreate, BugUpdate, LoginRequest, Priority, ReportReceipt, Status,
    StructureRequest, StructureResult, UserReport,
)

# Fields stored as JSON text in the database (see database.py).
JSON_FIELDS = {"steps", "labels"}

# Folder holding the website files (HTML, CSS, JavaScript).
STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once when the server starts: make sure the table exists,
    # and add example bugs if it's empty.
    init_db()
    seed_demo_data()
    yield


# The FastAPI "app" object. Every route (URL) we build gets attached to it.
app = FastAPI(title="BugLens", lifespan=lifespan)

# Routes for team members only. Every route added to this router runs
# require_team first, which rejects anyone who isn't logged in (401).
team = APIRouter(dependencies=[Depends(require_team)])


# ---------- Website pages ----------
# Home: a welcome page where people choose "Report a problem" or "Team login".
@app.get("/", include_in_schema=False)
def homepage():
    return FileResponse(STATIC_DIR / "welcome.html")


# The public page where users report problems. No login needed.
@app.get("/report", include_in_schema=False)
def report_page():
    return FileResponse(STATIC_DIR / "report.html")


# The team login page. Already logged in? Go straight to the dashboard.
@app.get("/login", include_in_schema=False)
def login_page(request: Request):
    if is_logged_in(request):
        return RedirectResponse("/team")
    return FileResponse(STATIC_DIR / "login.html")


# The team dashboard. Not logged in? Go to the login page first.
@app.get("/team", include_in_schema=False)
def team_dashboard(request: Request):
    if not is_logged_in(request):
        return RedirectResponse("/login")
    return FileResponse(STATIC_DIR / "index.html")


# Any address starting with /static/ is served straight from the static folder
# (that's how the pages load style.css and the .js files).
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# A "health check" route: visiting /api/health returns a small JSON response.
# It's a quick way to confirm the server is running.
@app.get("/api/health")
def health():
    return {"status": "ok", "app": "BugLens"}


# ---------- Login / logout ----------
@app.post("/api/login")
def login(credentials: LoginRequest, request: Request, response: Response):
    if not password_is_correct(credentials.password):
        raise HTTPException(status_code=401, detail="Wrong password. Please try again.")

    # Hosting sites like Render handle HTTPS in front of the app and pass on
    # the original scheme in this header.
    is_https = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
    response.set_cookie(
        COOKIE_NAME,
        create_session_token(),
        max_age=SESSION_SECONDS,
        httponly=True,    # JavaScript can't read it, so a malicious script can't steal it
        samesite="lax",   # not sent along with requests started by other websites
        secure=is_https,  # only sent over HTTPS when the site uses HTTPS
    )
    return {"ok": True}


@app.post("/api/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME)
    return {"ok": True}


@app.get("/api/auth/status")
def auth_status(request: Request):
    # The demo password is only revealed while the public demo password is in use.
    return {
        "logged_in": is_logged_in(request),
        "demo_password": DEMO_PASSWORD if using_demo_password() else None,
    }


# ---------- AI: messy report -> structured ticket (team only) ----------
# This only returns a suggestion. Nothing is saved until the person reviews it
# in the form and clicks Save, so a human always checks the AI's work.
@team.post("/api/ai/structure", response_model=StructureResult)
def ai_structure(request: StructureRequest):
    try:
        return structure_report(request.raw_report)
    except AIError as e:
        raise HTTPException(status_code=503, detail=str(e))


# ---------- CREATE ----------
def insert_bug(bug: BugCreate) -> int:
    """Save a bug to the database and return its new id. Used by the dashboard and the report page."""
    data = bug.model_dump()
    for field in JSON_FIELDS:
        data[field] = json.dumps(data[field])

    columns = ", ".join(data.keys())
    placeholders = ", ".join("?" for _ in data)  # "?" = safe value slots (prevents SQL injection)
    with get_connection() as conn:
        cursor = conn.execute(
            f"INSERT INTO bugs ({columns}) VALUES ({placeholders})",
            list(data.values()),
        )
        return cursor.lastrowid


@team.post("/api/bugs", response_model=Bug, status_code=201)
def create_bug(bug: BugCreate):
    return get_bug(insert_bug(bug))


# ---------- USER REPORTS (from the public /report page, no login) ----------
@app.post("/api/reports", response_model=ReportReceipt, status_code=201)
def submit_report(report: UserReport):
    raw = report.description
    try:
        ticket = structure_report(raw)
        fields = ticket.model_dump(exclude={"source"})
    except AIError:
        # Never lose a user's report: if the AI fails, save it untidied for a person to sort out.
        fields = {"title": raw[:80], "labels": ["needs-triage"]}

    # Tag it so the team can tell which bugs came straight from users.
    fields["labels"] = [*fields.get("labels", []), "user-report"]
    new_id = insert_bug(BugCreate(raw_report=raw, **fields))

    # Users only get a reference number back, not the internal ticket details.
    return {"id": new_id}


# ---------- READ (list, with optional filters) ----------
@team.get("/api/bugs", response_model=list[Bug])
def list_bugs(
    status: Optional[Status] = None,
    priority: Optional[Priority] = None,
    q: Optional[str] = None,
):
    sql = "SELECT * FROM bugs WHERE 1=1"
    params = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    if priority:
        sql += " AND priority = ?"
        params.append(priority)
    if q:
        sql += " AND (title LIKE ? OR raw_report LIKE ? OR labels LIKE ?)"
        params += [f"%{q}%"] * 3
    sql += " ORDER BY id DESC"

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [row_to_dict(r) for r in rows]


# ---------- READ (one bug) ----------
@team.get("/api/bugs/{bug_id}", response_model=Bug)
def get_bug(bug_id: int):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM bugs WHERE id = ?", (bug_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Bug #{bug_id} not found")
    return row_to_dict(row)


# ---------- UPDATE ----------
@team.patch("/api/bugs/{bug_id}", response_model=Bug)
def update_bug(bug_id: int, changes: BugUpdate):
    # exclude_unset: only the fields the client actually sent.
    data = changes.model_dump(exclude_unset=True)
    if not data:
        return get_bug(bug_id)
    for field in JSON_FIELDS & data.keys():
        data[field] = json.dumps(data[field])

    set_clause = ", ".join(f"{col} = ?" for col in data)
    with get_connection() as conn:
        cursor = conn.execute(
            f"UPDATE bugs SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
            [*data.values(), bug_id],
        )
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail=f"Bug #{bug_id} not found")
    return get_bug(bug_id)


# ---------- DELETE ----------
@team.delete("/api/bugs/{bug_id}", status_code=204)
def delete_bug(bug_id: int):
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM bugs WHERE id = ?", (bug_id,))
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail=f"Bug #{bug_id} not found")


# Attach all the team-only routes to the app (this must come after they're defined).
app.include_router(team)
