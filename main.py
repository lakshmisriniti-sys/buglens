import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ai import AIError, structure_report
from database import get_connection, init_db, row_to_dict, seed_demo_data
from schemas import (
    Bug, BugCreate, BugUpdate, Priority, ReportReceipt, Status,
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


# ---------- Website ----------
# Visiting the home address (/) shows the dashboard page.
@app.get("/", include_in_schema=False)
def homepage():
    return FileResponse(STATIC_DIR / "index.html")


# The public page where users report problems.
@app.get("/report", include_in_schema=False)
def report_page():
    return FileResponse(STATIC_DIR / "report.html")


# Any address starting with /static/ is served straight from the static folder
# (that's how the page loads style.css and app.js).
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# A "health check" route: visiting /api/health returns a small JSON response.
# It's a quick way to confirm the server is running.
@app.get("/api/health")
def health():
    return {"status": "ok", "app": "BugLens"}


# ---------- AI: messy report -> structured ticket ----------
# This only returns a suggestion. Nothing is saved until the person reviews it
# in the form and clicks Save, so a human always checks the AI's work.
@app.post("/api/ai/structure", response_model=StructureResult)
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


@app.post("/api/bugs", response_model=Bug, status_code=201)
def create_bug(bug: BugCreate):
    return get_bug(insert_bug(bug))


# ---------- USER REPORTS (from the public /report page) ----------
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
@app.get("/api/bugs", response_model=list[Bug])
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
@app.get("/api/bugs/{bug_id}", response_model=Bug)
def get_bug(bug_id: int):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM bugs WHERE id = ?", (bug_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Bug #{bug_id} not found")
    return row_to_dict(row)


# ---------- UPDATE ----------
@app.patch("/api/bugs/{bug_id}", response_model=Bug)
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
@app.delete("/api/bugs/{bug_id}", status_code=204)
def delete_bug(bug_id: int):
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM bugs WHERE id = ?", (bug_id,))
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail=f"Bug #{bug_id} not found")
