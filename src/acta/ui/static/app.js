// ── Constants ──────────────────────────────────────────────
const THEME_STORAGE_KEY = "acta-ui-theme";

const ENTRY_TYPES = [
    "intent", "decision", "experiment", "result",
    "todo", "blocker", "commit_summary", "session_summary", "cost_update"
];

const TYPE_ICONS = {
    intent:          "🎯",
    decision:        "⚖️",
    experiment:      "🧪",
    result:          "📊",
    todo:            "☐",
    blocker:         "🚧",
    commit_summary:  "📝",
    session_summary: "📋",
    cost_update:     "💰",
};

const TAB_TITLES = {
    timeline:    "Timeline",
    costs:       "Token Usage",
    "open-items": "Open Items",
};

// ── State ──────────────────────────────────────────────────
const state = {
    projectId:   null,
    timeframe:   "today",
    activeTab:   "timeline",
    activeTypes: new Set(ENTRY_TYPES),
    entries:     [],
    summary:     null,
    costs:       null,
    openItems:   [],
};

// ── API ────────────────────────────────────────────────────
async function fetchJSON(url) {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${url}`);
    return res.json();
}

async function loadProjects() {
    const projects = await fetchJSON("/api/projects");
    const sel = document.getElementById("project-select");
    sel.innerHTML = '<option value="">Select project…</option>';
    projects.forEach(p => {
        const opt = document.createElement("option");
        opt.value = p.id;
        opt.textContent = p.name;
        sel.appendChild(opt);
    });
    // Auto-select if only one project
    if (projects.length === 1) {
        sel.value = projects[0].id;
        state.projectId = projects[0].id;
        await refresh();
    }
}

async function loadEntries() {
    if (!state.projectId) return;
    state.entries = await fetchJSON(
        `/api/entries?project_id=${state.projectId}&timeframe=${state.timeframe}&limit=200`
    );
    renderEntries();
}

async function loadSummary() {
    if (!state.projectId) return;
    state.summary = await fetchJSON(
        `/api/summary?project_id=${state.projectId}&timeframe=${state.timeframe}`
    );
    renderStatPills();
}

async function loadCosts() {
    if (!state.projectId) return;
    state.costs = await fetchJSON(
        `/api/costs?project_id=${state.projectId}&timeframe=${state.timeframe}`
    );
    renderCosts();
}

async function loadOpenItems() {
    if (!state.projectId) return;
    state.openItems = await fetchJSON(`/api/open-items?project_id=${state.projectId}`);
    renderOpenItems();
    updateOpenItemsBadge();
}

async function refresh() {
    await Promise.all([loadEntries(), loadSummary(), loadCosts(), loadOpenItems()]);
}

// ── Render: Stat Pills ─────────────────────────────────────
function renderStatPills() {
    const s = state.summary;
    if (!s) return;
    const el = document.getElementById("stat-pills");
    const pills = [
        { value: s.total_entries,     label: "entries" },
        { value: s.open_items_count,  label: "open" },
        { value: s.decisions.length,  label: "decisions" },
    ];
    if (s.total_tokens_in + s.total_tokens_out > 0) {
        const total = (s.total_tokens_in + s.total_tokens_out).toLocaleString();
        pills.push({ value: total, label: "tokens" });
    }
    el.innerHTML = pills.map(p => `
        <div class="stat-pill">
            <span class="pill-value">${p.value}</span>
            <span class="pill-label">${p.label}</span>
        </div>
    `).join("");
}

// ── Render: Timeline ───────────────────────────────────────
function renderEntries() {
    const el = document.getElementById("entries-list");
    const filtered = state.entries.filter(e => state.activeTypes.has(e.entry_type));

    if (!state.projectId) {
        el.innerHTML = '<p class="empty-state">Select a project to view the timeline.</p>';
        return;
    }
    if (filtered.length === 0) {
        el.innerHTML = '<p class="empty-state">No entries match the current filters.</p>';
        return;
    }

    let html = "";
    let lastSession = null;

    for (const e of filtered) {
        if (e.session_id && e.session_id !== lastSession) {
            lastSession = e.session_id;
            html += `<div class="session-divider">Session · ${e.session_id.slice(0, 10)}</div>`;
        }

        const time = e.created_at
            ? new Date(e.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
            : "";
        const icon = TYPE_ICONS[e.entry_type] || "•";
        const model = e.metadata?.model ? `<span class="entry-model">${e.metadata.model}</span>` : "";
        const resolved = e.resolved
            ? `<span class="entry-resolved-tag">✓ resolved</span>` : "";
        const details = e.details
            ? `<div class="entry-details">${escHtml(e.details)}</div>` : "";

        html += `
        <div class="entry">
            <div class="entry-avatar t-${e.entry_type}">${icon}</div>
            <div class="entry-body">
                <div class="entry-header">
                    <span class="entry-badge t-${e.entry_type}">${e.entry_type.replace("_", " ")}</span>
                    <span class="entry-time">${time}</span>
                    ${model}
                    ${resolved}
                </div>
                <div class="entry-summary">${escHtml(e.summary)}</div>
                ${details}
            </div>
        </div>`;
    }

    el.innerHTML = html;
}

// ── Render: Costs ──────────────────────────────────────────
function renderCosts() {
    const c = state.costs;
    if (!c) return;

    // Overview stats
    const overviewEl = document.getElementById("cost-overview");
    if (!c.total_tokens) {
        overviewEl.innerHTML = "";
    } else {
        overviewEl.innerHTML = `
            <div class="cost-stat">
                <div class="cs-value">${fmtTokens(c.total_tokens)}</div>
                <div class="cs-label">Total Tokens</div>
                <div class="cs-sub">${fmtTokens(c.total_tokens_in)} in · ${fmtTokens(c.total_tokens_out)} out</div>
            </div>
            <div class="cost-stat">
                <div class="cs-value">${c.by_model.length}</div>
                <div class="cs-label">Models Used</div>
                <div class="cs-sub">${c.by_model.map(m => m.model.split("/").pop()).join(", ") || "—"}</div>
            </div>
            <div class="cost-stat">
                <div class="cs-value">${c.by_session.length}</div>
                <div class="cs-label">Sessions</div>
                <div class="cs-sub">with recorded usage</div>
            </div>
        `;
    }

    // By model
    const modelEl = document.getElementById("cost-by-model");
    if (!c.by_model.length) {
        modelEl.innerHTML = '<p class="empty-state">No cost data yet. Call <code>acta_record_cost</code> to track usage.</p>';
    } else {
        const maxTokens = Math.max(...c.by_model.map(m => m.total_tokens), 1);
        modelEl.innerHTML = c.by_model.map(m => {
            const pct = Math.round((m.total_tokens / maxTokens) * 100);
            return `
            <div class="cost-row">
                <div class="cost-bar-wrap"><div class="cost-bar-fill" style="width:${pct}%"></div></div>
                <div class="cost-row-label">${escHtml(m.model)}</div>
                <div class="cost-row-meta">
                    ${fmtTokens(m.total_tokens)} tokens<br>
                    <span style="color:var(--text-subtle)">${m.calls} call${m.calls !== 1 ? "s" : ""}</span>
                </div>
            </div>`;
        }).join("");
    }

    // By session
    const sessionEl = document.getElementById("cost-by-session");
    if (!c.by_session.length) {
        sessionEl.innerHTML = '<p class="empty-state">No session cost data yet.</p>';
    } else {
        const maxTokens = Math.max(...c.by_session.map(s => s.total_tokens), 1);
        sessionEl.innerHTML = c.by_session.map(s => {
            const pct = Math.round((s.total_tokens / maxTokens) * 100);
            const ts = s.started_at
                ? new Date(s.started_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })
                : "unknown";
            return `
            <div class="cost-row">
                <div class="cost-bar-wrap"><div class="cost-bar-fill" style="width:${pct}%"></div></div>
                <div class="cost-row-label">${s.session_id ? s.session_id.slice(0, 10) : "—"}</div>
                <div class="cost-row-meta">
                    ${fmtTokens(s.total_tokens)} tokens<br>
                    <span style="color:var(--text-subtle)">${ts}</span>
                </div>
            </div>`;
        }).join("");
    }
}

// ── Render: Open Items ─────────────────────────────────────
function renderOpenItems() {
    const el = document.getElementById("open-items-list");
    if (!state.openItems.length) {
        el.innerHTML = '<p class="empty-state">No open items. All clear.</p>';
        return;
    }
    el.innerHTML = state.openItems.map(item => {
        const icon = TYPE_ICONS[item.entry_type] || "•";
        const ts = item.created_at
            ? new Date(item.created_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })
            : "";
        const details = item.details
            ? `<div class="entry-details" style="margin-top:6px">${escHtml(item.details)}</div>` : "";
        return `
        <div class="open-item">
            <div class="entry-avatar t-${item.entry_type}" style="width:28px;height:28px;border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:13px;flex-shrink:0">${icon}</div>
            <div class="open-item-body">
                <div class="entry-header" style="margin-bottom:3px">
                    <span class="entry-badge t-${item.entry_type}">${item.entry_type}</span>
                </div>
                <div class="open-item-summary">${escHtml(item.summary)}</div>
                ${details}
                <div class="open-item-meta">${ts}</div>
            </div>
        </div>`;
    }).join("");
}

function updateOpenItemsBadge() {
    const badge = document.getElementById("open-items-badge");
    const count = state.openItems.length;
    if (count > 0) {
        badge.textContent = count;
        badge.style.display = "inline";
    } else {
        badge.style.display = "none";
    }
}

// ── Filter chips ───────────────────────────────────────────
function initFilters() {
    const container = document.getElementById("filter-bar");
    ENTRY_TYPES.forEach(t => {
        const chip = document.createElement("span");
        chip.className = "filter-chip active";
        chip.innerHTML = `<span class="dot dot-${t}"></span>${t.replace(/_/g, " ")}`;
        chip.addEventListener("click", () => {
            if (state.activeTypes.has(t)) {
                state.activeTypes.delete(t);
                chip.classList.remove("active");
            } else {
                state.activeTypes.add(t);
                chip.classList.add("active");
            }
            renderEntries();
        });
        container.appendChild(chip);
    });
}

// ── Tab switching ──────────────────────────────────────────
function switchTab(tabId) {
    state.activeTab = tabId;

    document.querySelectorAll(".nav-item").forEach(el => {
        el.classList.toggle("active", el.dataset.tab === tabId);
    });

    document.querySelectorAll(".tab-panel").forEach(el => {
        el.classList.toggle("active", el.id === `tab-${tabId}`);
    });

    document.getElementById("page-title").textContent = TAB_TITLES[tabId] || tabId;
}

// ── Helpers ────────────────────────────────────────────────
function escHtml(str) {
    const d = document.createElement("div");
    d.textContent = str;
    return d.innerHTML;
}

function fmtTokens(n) {
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
    if (n >= 1_000)     return (n / 1_000).toFixed(1) + "K";
    return String(n);
}

// ── Event wiring ───────────────────────────────────────────
document.getElementById("project-select").addEventListener("change", e => {
    state.projectId = e.target.value || null;
    refresh();
});

document.getElementById("timeframe-select").addEventListener("change", e => {
    state.timeframe = e.target.value;
    refresh();
});

document.querySelectorAll(".nav-item").forEach(el => {
    el.addEventListener("click", e => {
        e.preventDefault();
        switchTab(el.dataset.tab);
    });
});

// ── Theme (dark default, optional light) ───────────────────
function getStoredTheme() {
    try {
        return localStorage.getItem(THEME_STORAGE_KEY);
    } catch {
        return null;
    }
}

function applyTheme(mode, persist) {
    const root = document.documentElement;
    if (mode === "light") {
        root.setAttribute("data-theme", "light");
    } else {
        root.removeAttribute("data-theme");
    }
    syncThemeToggle(mode);
    if (!persist) return;
    try {
        if (mode === "light") {
            localStorage.setItem(THEME_STORAGE_KEY, "light");
        } else {
            localStorage.removeItem(THEME_STORAGE_KEY);
        }
    } catch {
        /* ignore */
    }
}

function syncThemeToggle(mode) {
    const btn = document.getElementById("theme-toggle");
    if (!btn) return;
    const isLight = mode === "light";
    btn.textContent = isLight ? "🌙" : "☀️";
    btn.setAttribute("aria-label", isLight ? "Switch to dark mode" : "Switch to light mode");
    btn.setAttribute("title", isLight ? "Dark mode" : "Light mode");
}

function initTheme() {
    const stored = getStoredTheme();
    const mode = stored === "light" ? "light" : "dark";
    applyTheme(mode, false);
    document.getElementById("theme-toggle")?.addEventListener("click", () => {
        const next = document.documentElement.getAttribute("data-theme") === "light" ? "dark" : "light";
        applyTheme(next, true);
    });
}

// ── Boot ───────────────────────────────────────────────────
initTheme();
initFilters();
loadProjects();
setInterval(() => { if (state.projectId) refresh(); }, 10000);
