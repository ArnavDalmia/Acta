const API = "";
const ENTRY_TYPES = [
    "intent", "decision", "experiment", "result",
    "todo", "blocker", "commit_summary", "session_summary", "cost_update"
];
const TYPE_ICONS = {
    intent: "\u{1F3AF}", decision: "\u2696\uFE0F", experiment: "\u{1F9EA}",
    result: "\u{1F4CA}", todo: "\u2610", blocker: "\u{1F6A7}",
    commit_summary: "\u{1F4DD}", session_summary: "\u{1F4CB}", cost_update: "\u{1F4B0}"
};

let state = {
    projectId: null,
    timeframe: "today",
    activeTypes: new Set(ENTRY_TYPES),
    entries: [],
};

async function fetchJSON(url) {
    const res = await fetch(API + url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
}

async function loadProjects() {
    const projects = await fetchJSON("/api/projects");
    const sel = document.getElementById("project-select");
    sel.innerHTML = '<option value="">Select project...</option>';
    for (const p of projects) {
        const opt = document.createElement("option");
        opt.value = p.id;
        opt.textContent = p.name;
        sel.appendChild(opt);
    }
}

async function loadEntries() {
    if (!state.projectId) return;
    const entries = await fetchJSON(
        `/api/entries?project_id=${state.projectId}&timeframe=${state.timeframe}&limit=100`
    );
    state.entries = entries;
    renderEntries();
}

async function loadSummary() {
    if (!state.projectId) return;
    const summary = await fetchJSON(
        `/api/summary?project_id=${state.projectId}&timeframe=${state.timeframe}`
    );
    renderSummary(summary);
}

async function loadOpenItems() {
    if (!state.projectId) return;
    const items = await fetchJSON(`/api/open-items?project_id=${state.projectId}`);
    renderOpenItems(items);
}

function renderSummary(s) {
    const el = document.getElementById("summary-content");
    if (s.total_entries === 0) {
        el.innerHTML = '<p class="muted">No entries in this timeframe.</p>';
        return;
    }
    let html = `
        <div class="summary-stat"><div class="value">${s.total_entries}</div><div class="label">Entries</div></div>
        <div class="summary-stat"><div class="value">${s.open_items_count}</div><div class="label">Open Items</div></div>
        <div class="summary-stat"><div class="value">${s.decisions.length}</div><div class="label">Decisions</div></div>
    `;
    if (s.total_tokens_in > 0 || s.total_tokens_out > 0) {
        const total = (s.total_tokens_in + s.total_tokens_out).toLocaleString();
        html += `<div class="summary-stat"><div class="value">${total}</div><div class="label">Tokens</div></div>`;
    }
    el.innerHTML = html;
}

function renderEntries() {
    const el = document.getElementById("entries-list");
    const filtered = state.entries.filter(e => state.activeTypes.has(e.entry_type));

    if (filtered.length === 0) {
        el.innerHTML = '<p class="muted">No entries match filters.</p>';
        return;
    }

    let html = "";
    let lastSession = null;

    for (const e of filtered) {
        if (e.session_id && e.session_id !== lastSession) {
            lastSession = e.session_id;
            html += `<div class="session-break">Session ${e.session_id.slice(0, 8)}</div>`;
        }

        const time = e.created_at ? new Date(e.created_at).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"}) : "";
        const icon = TYPE_ICONS[e.entry_type] || "\u2022";
        const resolved = e.resolved ? '<span class="entry-resolved">RESOLVED</span>' : "";
        const details = e.details ? `<div class="entry-details">${escapeHtml(e.details)}</div>` : "";

        html += `
            <div class="entry">
                <div class="entry-icon type-${e.entry_type}">${icon}</div>
                <div class="entry-body">
                    <div class="entry-header">
                        <span class="entry-type type-${e.entry_type}">${e.entry_type}</span>
                        <span class="entry-time">${time}</span>
                        ${resolved}
                    </div>
                    <div class="entry-summary">${escapeHtml(e.summary)}</div>
                    ${details}
                </div>
            </div>
        `;
    }
    el.innerHTML = html;
}

function renderOpenItems(items) {
    const el = document.getElementById("open-items-list");
    if (items.length === 0) {
        el.innerHTML = '<p class="muted">No open items.</p>';
        return;
    }
    let html = "";
    for (const item of items) {
        const icon = TYPE_ICONS[item.entry_type] || "\u2022";
        html += `
            <div class="open-item">
                <span class="entry-type type-${item.entry_type}">${icon} ${item.entry_type}</span>
                <span>${escapeHtml(item.summary)}</span>
            </div>
        `;
    }
    el.innerHTML = html;
}

function initFilters() {
    const container = document.getElementById("type-filters");
    for (const t of ENTRY_TYPES) {
        const chip = document.createElement("span");
        chip.className = "filter-chip active";
        chip.dataset.type = t;
        chip.innerHTML = `<span class="dot dot-${t}"></span>${t.replace("_", " ")}`;
        chip.addEventListener("click", () => toggleFilter(t, chip));
        container.appendChild(chip);
    }
}

function toggleFilter(type, chip) {
    if (state.activeTypes.has(type)) {
        state.activeTypes.delete(type);
        chip.classList.remove("active");
    } else {
        state.activeTypes.add(type);
        chip.classList.add("active");
    }
    renderEntries();
}

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

async function refresh() {
    await Promise.all([loadEntries(), loadSummary(), loadOpenItems()]);
}

document.getElementById("project-select").addEventListener("change", (e) => {
    state.projectId = e.target.value || null;
    refresh();
});

document.getElementById("timeframe-select").addEventListener("change", (e) => {
    state.timeframe = e.target.value;
    refresh();
});

initFilters();
loadProjects();

setInterval(() => { if (state.projectId) refresh(); }, 10000);
