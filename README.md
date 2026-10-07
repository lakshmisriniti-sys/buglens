# 🐛 BugLens

**Turning messy user feedback into actionable engineering tickets.**

Users report bugs like *"the login thing doesn't work sometimes and I get kicked out."*
Developers need a title, priority, environment, reproduction steps, and expected vs. actual behaviour.
BugLens bridges that gap: paste a messy report, and it becomes a structured ticket on a team dashboard.

> **Live demo:** <https://buglens-jwmd.onrender.com>
> Choose **Report a problem** (user side) or **Team login** (team dashboard, demo password: `demo123`).
>
> Free hosting: the first visit after a quiet spell can take up to a minute to wake up, and the demo data resets periodically. The live demo runs in demo mode (rule-based, no API key).

```text
Messy user report  →  AI / rule-based processing  →  Structured ticket  →  Team dashboard
```

---

## Screenshots

**Team dashboard**: track, filter, search and update bugs

![Team dashboard](docs/dashboard.jpg)

**✨ Generate with AI**: a messy report becomes a structured ticket, reviewed by a person before saving

![Generating a ticket](docs/generate-ticket.jpg)

**User report page**: users describe problems in their own words

![User report page](docs/report-page.jpg)

---

## Features

- **Two sides, one app**: a welcome page leads users to *Report a problem* and team members to a password-protected dashboard
- **Team login**: signed, HttpOnly session cookies; every team API route is protected on the server, not just hidden in the UI
- **Bug dashboard**: create, view, edit and delete bugs; status counts at a glance
- **Search and filters**: by status, by priority, and live search across titles, reports and labels
- **✨ AI ticket generation**: turns a messy report into title, priority, environment, steps, expected/actual and labels, using the Claude API with structured outputs
- **Demo mode fallback**: without an API key, a keyword-based rule engine fills in the ticket instead, so anyone can try the feature for free
- **Human in the loop**: AI output only fills the form; a person reviews it before saving
- **Public report page** (`/report`): users submit problems in plain language; reports are auto-structured, tagged `user-report`, and appear on the dashboard
- **Quick status changes** straight from the table
- **Dark mode** and **mobile-friendly** layout

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI, Uvicorn, Pydantic |
| Database | SQLite (raw SQL with parameterised queries) |
| Frontend | HTML, CSS, vanilla JavaScript (no build step) |
| AI | Anthropic Claude API (structured outputs) + rule-based fallback |
| Deployment | Docker, Render |

## How it works

```text
Browser (HTML/CSS/JS)
   │  fetch() JSON requests (+ session cookie for the team)
   ▼
Uvicorn (web server)  ──►  FastAPI app (main.py)
                              ├── /api/login, /api/logout   team session cookie (auth.py)
                              ├── /api/reports              public user reports
                              └── team only (401 without login):
                                  ├── /api/bugs             CRUD, filters, search  ──►  SQLite (database.py)
                                  └── /api/ai/structure     messy report → ticket  ──►  Claude API (ai.py)
                                                                                       or rules (rules.py)
```

### Pages

| Page | Who | Description |
|---|---|---|
| `/` | Everyone | Welcome page: choose *Report a problem* or *Team login* |
| `/report` | Everyone | Users describe a problem in their own words |
| `/login` | Team | Team password |
| `/team` | Team (logged in) | Bug dashboard |

### API endpoints

| Method | Endpoint | Access | Description |
|---|---|---|---|
| `POST` | `/api/reports` | Public | Submit a user report (structured and saved automatically) |
| `POST` | `/api/login` | Public | Log in with the team password (sets a session cookie) |
| `POST` | `/api/logout` | Public | Log out |
| `GET` | `/api/health` | Public | Health check |
| `GET` | `/api/bugs` | Team | List bugs. Optional `?status=`, `?priority=`, `?q=` |
| `POST` | `/api/bugs` | Team | Create a bug |
| `GET` | `/api/bugs/{id}` | Team | Get one bug |
| `PATCH` | `/api/bugs/{id}` | Team | Update some fields of a bug |
| `DELETE` | `/api/bugs/{id}` | Team | Delete a bug |
| `POST` | `/api/ai/structure` | Team | Turn a messy report into a suggested ticket (not saved) |

Interactive API docs are generated automatically at **`/docs`**.

## Design decisions

- **Structured outputs:** the AI must reply in an exact schema (a Pydantic model), so responses never need fragile text parsing.
- **Graceful fallback:** with no API key, a rule engine produces the same ticket shape, and the UI clearly labels it as demo mode.
- **User reports are never lost:** if AI processing fails, the report is still saved, tagged `needs-triage`.
- **Prompt-injection aware:** the AI is told to treat report text as data, never as instructions.
- **Authentication on the server:** team routes are grouped behind a FastAPI dependency, so the API itself rejects requests without a valid session, not just the UI. Sessions are HMAC-signed tokens in HttpOnly, SameSite cookies, and passwords are compared in constant time.
- **Security basics:** parameterised SQL queries (prevents SQL injection), HTML escaping on the frontend (prevents XSS), and server-side validation that doesn't rely on the browser.
- **Minimal data exposure:** the public report page only returns a reference number, never internal ticket details.

## Run it locally

**Requirements:** Python 3.11+

```bash
git clone https://github.com/lakshmisriniti-sys/buglens.git
cd buglens
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
uvicorn main:app --reload
```

Open <http://127.0.0.1:8000> and choose **Report a problem** or **Team login** (default password: `demo123`).
Example bugs are added automatically when the database is empty.

**Optional settings** (copy `.env.example` to `.env`):
- `ANTHROPIC_API_KEY`: your [Anthropic API key](https://console.anthropic.com) for real AI. Without it, BugLens runs in demo mode.
- `TEAM_PASSWORD`: use your own team password instead of the public demo one.
- `SECRET_KEY`: a fixed key for signing logins, so sessions survive server restarts.

### Run with Docker

```bash
docker build -t buglens .
docker run -p 8000:8000 buglens
```

## Project structure

```text
buglens/
├── main.py           # FastAPI app: routes for pages, login, bugs, AI and user reports
├── auth.py           # Team password check and signed session cookies
├── database.py       # SQLite setup, example data, row conversion
├── schemas.py        # Pydantic models: what valid data looks like
├── ai.py             # Claude API integration (falls back to rules.py)
├── rules.py          # Demo mode: keyword-based ticket generation
├── static/
│   ├── welcome.html  # Home: choose user or team
│   ├── login.html    # Team login page
│   ├── login.js      # Login behaviour
│   ├── index.html    # Team dashboard
│   ├── app.js        # Dashboard behaviour
│   ├── report.html   # Public "Report a problem" page
│   ├── report.js     # Report page behaviour
│   └── style.css     # Shared styles (light/dark, mobile)
├── Dockerfile
└── requirements.txt
```

## Limitations and next steps

- **One shared team password:** there are no individual accounts yet. Next: per-person accounts with hashed passwords, roles, and assignees picked from real team members.
- **No rate limiting** on the public report page or the login form. Next: limit attempts per IP address, or add a CAPTCHA.
- **SQLite on free hosting resets** on restart. Next: a hosted database such as PostgreSQL.
- **Duplicate detection:** flag new reports that look like existing bugs, using text similarity or embeddings.
