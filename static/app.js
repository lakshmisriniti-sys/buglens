// ---------- Setup ----------
const API = "/api/bugs";
const $ = (selector) => document.querySelector(selector);

const STATUS_LABELS = {
  open: "Open",
  in_progress: "In progress",
  resolved: "Resolved",
  closed: "Closed",
};

// The bugs currently on screen, by id, so clicking a row can find its data.
let bugsById = new Map();
// Which bug the form is editing (null = creating a new one).
let editingId = null;


// ---------- Helpers ----------

// Escape text before putting it into HTML, so a bug titled "<script>…"
// shows up as text instead of running as code (prevents XSS attacks).
function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

// Call our FastAPI backend and turn errors into readable messages.
async function api(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  // 401 = not logged in (or the login expired): send them to the login page.
  if (res.status === 401) {
    location.href = "/login";
    throw new Error("Please log in again.");
  }
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") message = body.detail;
      else if (Array.isArray(body.detail)) {
        message = body.detail.map((d) => `${d.loc.at(-1)}: ${d.msg}`).join(", ");
      }
    } catch {}
    throw new Error(message);
  }
  return res.status === 204 ? null : res.json();
}

// SQLite stores times in UTC like "2026-10-07 14:03:00". Show "Oct 7".
function formatDate(value) {
  const date = new Date(value.replace(" ", "T") + "Z");
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

let toastTimer;
function toast(message, isError = false) {
  const el = $("#toast");
  el.textContent = message;
  el.className = "show" + (isError ? " error" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.className = ""), 2500);
}


// ---------- Loading and showing bugs ----------

async function loadBugs() {
  const params = new URLSearchParams();
  const q = $("#search").value.trim();
  const status = $("#filter-status").value;
  const priority = $("#filter-priority").value;
  if (q) params.set("q", q);
  if (status) params.set("status", status);
  if (priority) params.set("priority", priority);

  try {
    // Two requests at once: the filtered list, and all bugs for the counts.
    const [bugs, allBugs] = await Promise.all([api(`${API}?${params}`), api(API)]);
    renderStats(allBugs);
    renderList(bugs, Boolean(q || status || priority));
  } catch (err) {
    toast(err.message, true);
  }
}

function renderStats(allBugs) {
  for (const status of Object.keys(STATUS_LABELS)) {
    const count = allBugs.filter((b) => b.status === status).length;
    $(`#stat-${status}`).textContent = count;
  }
}

function renderList(bugs, filtersActive) {
  bugsById = new Map(bugs.map((b) => [b.id, b]));
  const rows = $("#bug-rows");
  const empty = $("#empty");

  if (bugs.length === 0) {
    rows.innerHTML = "";
    empty.hidden = false;
    empty.textContent = filtersActive
      ? "No bugs match these filters."
      : "No bugs yet. Click “+ New bug” to add the first one.";
    return;
  }

  empty.hidden = true;
  rows.innerHTML = bugs.map((bug) => `
    <tr data-id="${bug.id}">
      <td class="id">#${bug.id}</td>
      <td>
        <div class="title">${escapeHtml(bug.title)}</div>
        ${bug.labels.length ? `<div class="labels">${bug.labels
          .map((l) => `<span class="label">${escapeHtml(l)}</span>`).join("")}</div>` : ""}
      </td>
      <td><span class="badge p-${bug.priority}">${bug.priority}</span></td>
      <td>
        <select class="status-select s-${bug.status}" data-id="${bug.id}" aria-label="Status">
          ${Object.entries(STATUS_LABELS).map(([value, label]) =>
            `<option value="${value}" ${value === bug.status ? "selected" : ""}>${label}</option>`
          ).join("")}
        </select>
      </td>
      <td class="hide-sm">${bug.assignee ? escapeHtml(bug.assignee) : '<span class="muted">Unassigned</span>'}</td>
      <td class="hide-sm muted">${formatDate(bug.updated_at)}</td>
    </tr>
  `).join("");
}


// ---------- Create / edit form ----------

// Get a form input by its name. (We use form.elements because `form.title`
// would return the form's own built-in title property, not our input.)
const field = (name) => $("#bug-form").elements[name];

function openEditor(bug = null) {
  const form = $("#bug-form");
  form.reset();
  editingId = bug ? bug.id : null;

  $("#editor-title").textContent = bug ? `Edit bug #${bug.id}` : "New bug";
  $("#delete-bug").hidden = !bug;
  // The original report is kept as a record, so it can't be changed after creation.
  field("raw_report").readOnly = Boolean(bug);
  // The AI button is only for new bugs.
  $("#ai-row").hidden = Boolean(bug);
  $("#ai-note").hidden = true;

  if (bug) {
    for (const name of ["title", "raw_report", "priority", "status", "environment",
                        "assignee", "expected", "actual"]) {
      field(name).value = bug[name];
    }
    field("steps").value = bug.steps.join("\n");
    field("labels").value = bug.labels.join(", ");
  }

  $("#editor").showModal();
}

function closeEditor() {
  $("#editor").close();
}

// Read the form into the shape our API expects.
function readForm() {
  const data = {
    title: field("title").value.trim(),
    priority: field("priority").value,
    status: field("status").value,
    environment: field("environment").value.trim(),
    assignee: field("assignee").value.trim(),
    expected: field("expected").value.trim(),
    actual: field("actual").value.trim(),
    // One step per line -> list of steps.
    steps: field("steps").value.split("\n").map((s) => s.trim()).filter(Boolean),
    // "auth, Chrome" -> ["auth", "chrome"]
    labels: field("labels").value.split(",").map((l) => l.trim().toLowerCase()).filter(Boolean),
  };
  if (editingId === null) data.raw_report = field("raw_report").value.trim();
  return data;
}

async function saveBug(event) {
  event.preventDefault(); // stop the browser's default page reload
  const data = readForm();
  try {
    if (editingId === null) {
      const bug = await api(API, { method: "POST", body: JSON.stringify(data) });
      toast(`Bug #${bug.id} created`);
    } else {
      await api(`${API}/${editingId}`, { method: "PATCH", body: JSON.stringify(data) });
      toast(`Bug #${editingId} updated`);
    }
    closeEditor();
    loadBugs();
  } catch (err) {
    toast(err.message, true);
  }
}

async function deleteBug() {
  if (!confirm(`Delete bug #${editingId}? This can't be undone.`)) return;
  try {
    await api(`${API}/${editingId}`, { method: "DELETE" });
    toast(`Bug #${editingId} deleted`);
    closeEditor();
    loadBugs();
  } catch (err) {
    toast(err.message, true);
  }
}


// ---------- AI: turn the messy report into a structured ticket ----------

async function generateWithAI() {
  const rawReport = field("raw_report").value.trim();
  if (!rawReport) {
    toast("Paste a bug report first", true);
    field("raw_report").focus();
    return;
  }

  const button = $("#ai-generate");
  button.disabled = true;
  button.textContent = "✨ Thinking…";
  try {
    const ticket = await api("/api/ai/structure", {
      method: "POST",
      body: JSON.stringify({ raw_report: rawReport }),
    });

    // Fill the form with the AI's suggestion.
    for (const name of ["title", "priority", "environment", "expected", "actual"]) {
      field(name).value = ticket[name];
    }
    field("steps").value = ticket.steps.join("\n");
    field("labels").value = ticket.labels.join(", ");

    // Flash the filled fields so it's clear what changed.
    for (const name of ["title", "priority", "environment", "steps", "expected", "actual", "labels"]) {
      const el = field(name);
      el.classList.remove("ai-filled");
      void el.offsetWidth; // restart the animation
      el.classList.add("ai-filled");
    }
    // "demo" = filled by keyword rules because no API key is set.
    const isDemo = ticket.source === "demo";
    $("#ai-note").hidden = !isDemo;
    toast(isDemo ? "Demo mode: filled in by rules. Review it, then Save."
                 : "AI filled in the ticket. Review it, then Save.");
  } catch (err) {
    toast(err.message, true);
  } finally {
    button.disabled = false;
    button.textContent = "✨ Generate with AI";
  }
}


// ---------- Quick status change from the table ----------

async function changeStatus(select) {
  const id = Number(select.dataset.id);
  try {
    await api(`${API}/${id}`, { method: "PATCH", body: JSON.stringify({ status: select.value }) });
    toast(`Bug #${id} → ${STATUS_LABELS[select.value]}`);
    loadBugs();
  } catch (err) {
    toast(err.message, true);
  }
}


// ---------- Wire up buttons and inputs ----------

$("#new-bug").addEventListener("click", () => openEditor());
$("#close-editor").addEventListener("click", closeEditor);
$("#cancel-editor").addEventListener("click", closeEditor);
$("#bug-form").addEventListener("submit", saveBug);
$("#delete-bug").addEventListener("click", deleteBug);
$("#ai-generate").addEventListener("click", generateWithAI);
$("#logout").addEventListener("click", async () => {
  await fetch("/api/logout", { method: "POST" });
  location.href = "/";
});

// Click a row to edit it (but not when clicking the status dropdown).
$("#bug-rows").addEventListener("click", (event) => {
  if (event.target.closest(".status-select")) return;
  const row = event.target.closest("tr");
  if (row) openEditor(bugsById.get(Number(row.dataset.id)));
});
$("#bug-rows").addEventListener("change", (event) => {
  if (event.target.matches(".status-select")) changeStatus(event.target);
});

// Filters reload the list. Search waits until you pause typing (250 ms).
let searchTimer;
$("#search").addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(loadBugs, 250);
});
$("#filter-status").addEventListener("change", loadBugs);
$("#filter-priority").addEventListener("change", loadBugs);

// When you come back to this tab (e.g. after sending a report from the user page),
// refresh the list so new bugs show up without reloading.
window.addEventListener("focus", loadBugs);

loadBugs();
