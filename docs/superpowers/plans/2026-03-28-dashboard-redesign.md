# Dashboard Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the weekly report dashboard frontend from light theme to dark professional with fixed sidebar navigation, keeping all Jinja2 logic and data bindings intact.

**Architecture:** In-place rewrite of CSS variables, HTML structure (add sidebar wrapper), and Chart.js config within existing Jinja2 templates. No backend changes. Each template is modified independently.

**Tech Stack:** HTML/CSS (inline), Chart.js 4.4.0 + chartjs-plugin-datalabels (CDN), Jinja2 templates, Google Fonts Inter

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `report/templates/dashboard.html` | Rewrite | Main dashboard: sidebar, dark theme, KPIs, charts, tabs, tables |
| `report/templates/login.html` | Modify | Align to new dark palette |
| `report/templates/forgot_password.html` | Modify | Align to new dark palette |
| `report/templates/reset_password.html` | Modify | Align to new dark palette |
| `report/templates/change_password.html` | Modify | Align to new dark palette |
| `report/templates/chamados_solicitante.html` | Rewrite | Sidebar layout + dark theme + breadcrumb |
| `report/templates/chamados_servico.html` | Rewrite | Sidebar layout + dark theme + breadcrumb |
| `report/templates/chamados_atendente.html` | Rewrite | Sidebar layout + dark theme + breadcrumb |

---

### Task 1: Rewrite dashboard.html CSS variables and base layout (sidebar + header)

**Files:**
- Modify: `/opt/weekly-report/report/templates/dashboard.html:1-237`

This task replaces the `:root` CSS variables, adds sidebar CSS, rewrites the body layout to use CSS Grid with sidebar + main area, and updates the header. All Jinja2 template logic below the `</style>` and `<body>` up to the first tab-content remains the same structurally — only the wrapping HTML changes.

- [ ] **Step 1: Replace CSS :root variables and add sidebar + layout styles**

Replace lines 10-227 (the entire `<style>` block content) in `dashboard.html` with:

```html
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0/dist/chartjs-plugin-datalabels.min.js"></script>
    <style>
        :root {
            --bg-body: #0d1117;
            --bg-main: #161b22;
            --bg-card: #1c2128;
            --bg-card-hover: #21262d;
            --border: #30363d;
            --text: #e6edf3;
            --text-muted: #7d8590;
            --accent: #2563eb;
            --accent-hover: #3b82f6;
            --accent-soft: rgba(37,99,235,0.1);
            --green: #2ea043;
            --green-soft: rgba(46,160,67,0.15);
            --red: #f85149;
            --red-soft: rgba(248,81,73,0.15);
            --yellow: #d29922;
            --yellow-soft: rgba(210,153,34,0.15);
            --orange: #e65100;
            --sidebar-w: 220px;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
            background: var(--bg-main);
            color: var(--text);
            min-height: 100vh;
            -webkit-font-smoothing: antialiased;
        }

        /* === Layout: Sidebar + Main === */
        .app-layout {
            display: grid;
            grid-template-columns: var(--sidebar-w) 1fr;
            min-height: 100vh;
        }
        .sidebar {
            background: var(--bg-body);
            border-right: 1px solid var(--border);
            padding: 24px 0;
            position: fixed;
            top: 0;
            left: 0;
            width: var(--sidebar-w);
            height: 100vh;
            overflow-y: auto;
            z-index: 100;
        }
        .sidebar-logo {
            padding: 0 20px 20px;
            border-bottom: 1px solid var(--border);
            margin-bottom: 12px;
        }
        .sidebar-logo h2 {
            font-size: 1.1rem;
            font-weight: 700;
            color: var(--text);
            letter-spacing: -0.3px;
        }
        .sidebar-logo span {
            font-size: 0.72rem;
            color: var(--text-muted);
            display: block;
            margin-top: 2px;
        }
        .sidebar-nav { list-style: none; padding: 0 8px; }
        .sidebar-nav li { margin-bottom: 2px; }
        .sidebar-nav a, .sidebar-nav button {
            display: flex;
            align-items: center;
            gap: 10px;
            width: 100%;
            padding: 9px 12px;
            border-radius: 6px;
            border: none;
            background: transparent;
            color: var(--text-muted);
            font-size: 0.85rem;
            font-weight: 500;
            font-family: inherit;
            cursor: pointer;
            text-decoration: none;
            transition: background 0.15s, color 0.15s;
            border-left: 3px solid transparent;
        }
        .sidebar-nav a:hover, .sidebar-nav button:hover {
            background: var(--accent-soft);
            color: var(--text);
        }
        .sidebar-nav .active {
            background: var(--accent-soft);
            color: var(--text);
            border-left-color: var(--accent);
        }
        .sidebar-nav .nav-icon { font-size: 1rem; width: 20px; text-align: center; }
        .sidebar-sep {
            height: 1px;
            background: var(--border);
            margin: 10px 20px;
        }
        .sidebar-footer {
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            padding: 12px 20px;
            border-top: 1px solid var(--border);
        }
        .sidebar-footer a {
            display: block;
            color: var(--text-muted);
            font-size: 0.78rem;
            text-decoration: none;
            transition: color 0.15s;
        }
        .sidebar-footer a:hover { color: var(--red); }

        .main-area {
            margin-left: var(--sidebar-w);
            min-height: 100vh;
        }

        /* === Header === */
        .header {
            background: var(--bg-body);
            border-bottom: 1px solid var(--border);
            padding: 18px 32px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .header h1 { font-size: 1.15rem; font-weight: 600; color: var(--text); }
        .header .subtitle { color: var(--text-muted); font-size: 0.78rem; font-weight: 400; }
        .btn-logout {
            padding: 6px 14px;
            border-radius: 6px;
            border: 1px solid var(--border);
            background: transparent;
            color: var(--text-muted);
            font-size: 0.78rem;
            font-weight: 500;
            cursor: pointer;
            text-decoration: none;
            transition: border-color 0.15s, color 0.15s;
        }
        .btn-logout:hover { border-color: var(--accent); color: var(--accent); }

        .container { max-width: 1400px; margin: 0 auto; padding: 24px 32px; }

        /* === KPI Cards === */
        .kpi-grid {
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 14px;
            margin-bottom: 24px;
        }
        .kpi-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 18px 16px;
            transition: background 0.15s;
        }
        .kpi-card:hover { background: var(--bg-card-hover); }
        .kpi-card .label { color: var(--text-muted); font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.8px; font-weight: 600; }
        .kpi-card .value { font-size: 2rem; font-weight: 700; margin: 6px 0 2px; letter-spacing: -0.5px; color: var(--text); }
        .kpi-card .meta { font-size: 0.72rem; color: var(--text-muted); font-weight: 400; }
        .kpi-card .value.green { color: var(--green); }
        .kpi-card .value.red { color: var(--red); }
        .kpi-card .value.yellow { color: var(--yellow); }
        .kpi-card .value.blue { color: var(--accent); }

        /* === Sections / Cards === */
        .section {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 22px 24px;
            margin-bottom: 20px;
        }
        .section h2 {
            font-size: 0.95rem;
            font-weight: 600;
            color: var(--text);
            margin-bottom: 14px;
            padding-bottom: 10px;
            border-bottom: 1px solid var(--border);
        }

        /* === Tables === */
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 9px 12px; text-align: left; border-bottom: 1px solid var(--border); }
        th {
            color: var(--text-muted); font-size: 0.68rem; text-transform: uppercase;
            letter-spacing: 0.5px; font-weight: 700; background: var(--bg-main);
            position: sticky; top: 0;
        }
        td { font-size: 0.85rem; }
        tr:nth-child(even) td { background: var(--bg-card); }
        tr:nth-child(odd) td { background: var(--bg-main); }
        tr:hover td { background: var(--bg-card-hover); transition: background 0.1s; }
        tr:last-child td { border-bottom: none; }
        .cost-value { font-weight: 600; font-variant-numeric: tabular-nums; }

        /* === Charts === */
        .charts-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 20px;
        }
        .chart-container { position: relative; height: 280px; }
        .chart-card-title {
            font-size: 0.82rem;
            font-weight: 600;
            color: var(--text);
            margin-bottom: 4px;
        }
        .chart-card-subtitle {
            font-size: 0.72rem;
            color: var(--text-muted);
            margin-bottom: 12px;
        }

        /* === Status Badges === */
        .badge {
            display: inline-flex; align-items: center; gap: 5px;
            font-size: 0.75rem; font-weight: 500;
        }
        .badge::before {
            content: ''; display: inline-block;
            width: 8px; height: 8px; border-radius: 50%;
        }
        .badge.ok, .badge.fechado { color: var(--green); }
        .badge.ok::before, .badge.fechado::before { background: var(--green); }
        .badge.fail, .badge.aberto { color: var(--accent); }
        .badge.fail::before, .badge.aberto::before { background: var(--accent); }
        .badge.warn, .badge.pendente { color: var(--yellow); }
        .badge.warn::before, .badge.pendente::before { background: var(--yellow); }

        .updated { color: var(--text-muted); font-size: 0.75rem; margin-bottom: 14px; text-align: right; }

        /* === Sub Tabs (inside sections) === */
        .subtabs {
            display: flex;
            gap: 32px;
            margin-bottom: 20px;
            border-bottom: 1px solid var(--border);
        }
        .subtab-btn {
            padding: 8px 0;
            background: transparent;
            border: none;
            color: var(--text-muted);
            font-size: 0.78rem;
            font-weight: 600;
            cursor: pointer;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 2px solid transparent;
            margin-bottom: -1px;
            transition: color 0.2s, border-color 0.2s;
            font-family: inherit;
        }
        .subtab-btn:hover { color: var(--text); }
        .subtab-btn.active { color: var(--text); border-bottom-color: var(--accent); }
        .subtab-content { display: none; }
        .subtab-content.active { display: block; }

        /* Hidden: main tab-content toggled by sidebar */
        .tab-content { display: none; }
        .tab-content.active { display: block; }

        /* === Monday project cards === */
        .board-section { margin-bottom: 24px; }
        .board-section h3 { font-size: 0.92rem; margin-bottom: 12px; color: var(--accent); font-weight: 600; }
        .project-table td.status-cell { white-space: nowrap; }
        .status-dot {
            display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px;
        }
        .status-dot.done { background: var(--green); }
        .status-dot.progress { background: var(--accent); }
        .status-dot.stopped { background: var(--red); }
        .status-dot.backlog { background: var(--yellow); }
        .status-dot.other { background: var(--text-muted); }
        .subitem-bar {
            display: inline-block; height: 5px; border-radius: 3px; background: var(--border); min-width: 60px; overflow: hidden;
        }
        .subitem-bar-fill { display: block; height: 100%; border-radius: 3px; background: var(--green); }
        .subitem-text { font-size: 0.72rem; color: var(--text-muted); margin-left: 6px; }

        /* === Buttons === */
        .btn-primary {
            display: inline-block;
            background: var(--accent);
            color: #fff;
            text-decoration: none;
            padding: 8px 20px;
            border-radius: 6px;
            font-weight: 600;
            font-size: 0.8rem;
            font-family: inherit;
            transition: background 0.15s;
            letter-spacing: 0.2px;
        }
        .btn-primary:hover { background: var(--accent-hover); }
        .btn-ghost {
            display: inline-block;
            border: 1px solid var(--border);
            color: var(--text-muted);
            text-decoration: none;
            padding: 6px 14px;
            border-radius: 6px;
            font-weight: 500;
            font-size: 0.78rem;
            font-family: inherit;
            cursor: pointer;
            background: transparent;
            transition: border-color 0.15s, color 0.15s;
        }
        .btn-ghost:hover { border-color: var(--accent); color: var(--accent); }

        /* === Search Box === */
        .search-box {
            padding: 8px 14px;
            border-radius: 6px;
            border: 1px solid var(--border);
            background: var(--bg-card);
            color: var(--text);
            font-size: 0.85rem;
            font-family: inherit;
            width: 300px;
            margin-bottom: 14px;
            outline: none;
            transition: border-color 0.15s;
        }
        .search-box::placeholder { color: var(--text-muted); }
        .search-box:focus { border-color: var(--accent); }

        .ticket-link { color: var(--accent); text-decoration: none; font-weight: 600; }
        .ticket-link:hover { color: var(--accent-hover); }

        /* === Breadcrumb === */
        .breadcrumb { color: var(--text-muted); font-size: 0.82rem; margin-bottom: 18px; }
        .breadcrumb a { color: var(--text-muted); text-decoration: none; transition: color 0.15s; }
        .breadcrumb a:hover { color: var(--accent); }
        .breadcrumb .sep { margin: 0 6px; }
        .breadcrumb .current { color: var(--text); }

        /* === Mobile hamburger === */
        .hamburger {
            display: none;
            background: transparent;
            border: none;
            color: var(--text);
            font-size: 1.4rem;
            cursor: pointer;
            padding: 4px 8px;
        }
        .sidebar-overlay {
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,0.5);
            z-index: 99;
        }
        .sidebar-overlay.active { display: block; }
        .sidebar-close {
            display: none;
            position: absolute;
            top: 12px;
            right: 12px;
            background: transparent;
            border: none;
            color: var(--text-muted);
            font-size: 1.2rem;
            cursor: pointer;
        }

        /* === Responsive === */
        @media (max-width: 1200px) {
            .kpi-grid { grid-template-columns: repeat(3, 1fr); }
        }
        @media (max-width: 992px) {
            .app-layout { grid-template-columns: 1fr; }
            .main-area { margin-left: 0; }
            .sidebar {
                transform: translateX(-100%);
                transition: transform 0.2s;
            }
            .sidebar.open { transform: translateX(0); }
            .hamburger { display: block; }
            .sidebar-close { display: block; }
            .kpi-grid { grid-template-columns: repeat(2, 1fr); }
            .charts-grid { grid-template-columns: 1fr; }
        }
        @media (max-width: 768px) {
            .kpi-grid { grid-template-columns: repeat(2, 1fr); }
            .container { padding: 16px; }
            .header { padding: 14px 16px; }
            .search-box { width: 100%; }
        }
    </style>
```

- [ ] **Step 2: Replace the header + body opening with sidebar layout**

Replace the old `<body>` through `<div class="container">` (lines 229-239) with the new sidebar + main area wrapper. The sidebar contains navigation links that trigger tab switching via JS (replacing the old top tabs):

```html
<body>

<div class="sidebar-overlay" id="sidebarOverlay"></div>

<div class="app-layout">

<!-- Sidebar -->
<nav class="sidebar" id="sidebar">
    <button class="sidebar-close" id="sidebarClose">&times;</button>
    <div class="sidebar-logo">
        <h2>Surf Telecom</h2>
        <span>Relatorio Semanal</span>
    </div>
    <ul class="sidebar-nav">
        <li><button class="active" data-tab="cloud"><span class="nav-icon">&#9729;</span> Cloud</button></li>
        <li><button data-tab="ti"><span class="nav-icon">&#9881;</span> TI Corporativo</button></li>
        <li><button data-tab="seguranca"><span class="nav-icon">&#9888;</span> Seguranca</button></li>
        {% if otrs_daily_queues %}<li><button data-tab="diario"><span class="nav-icon">&#128197;</span> Diario (D-1)</button></li>{% endif %}
    </ul>
    <div class="sidebar-footer">
        <a href="/dashboard/logout">Sair</a>
    </div>
</nav>

<!-- Main Content -->
<div class="main-area">
    <div class="header">
        <div style="display: flex; align-items: center; gap: 12px;">
            <button class="hamburger" id="hamburgerBtn">&#9776;</button>
            <div>
                <h1>{{ current_section_title|default('Cloud') }}</h1>
                <div class="subtitle">Periodo: {{ otrs.period.start }} a {{ otrs.period.end }}</div>
            </div>
        </div>
        <div class="subtitle">Gerado em {{ generated_at }}</div>
    </div>

    <div class="container">
```

Note: The `current_section_title` won't exist as a Jinja2 variable. The header title will be updated dynamically by the tab-switching JS. So we use a static default:

```html
            <div>
                <h1 id="sectionTitle">Cloud</h1>
                <div class="subtitle">Periodo: {{ otrs.period.start }} a {{ otrs.period.end }}</div>
            </div>
```

- [ ] **Step 3: Remove the old `.tabs` div**

Delete the old top tabs block (the `<div class="tabs">...</div>` around lines 243-248) since navigation is now in the sidebar. Keep all `tab-content` divs and subtabs exactly as they are — the sidebar JS will toggle them.

- [ ] **Step 4: Close the new layout wrappers at bottom of file**

At the end of the file (before `<script>`), after `</div>{# /container #}`, add the closing tags for main-area and app-layout:

```html
</div>{# /container #}
</div>{# /main-area #}
</div>{# /app-layout #}
```

- [ ] **Step 5: Verify the template renders**

Run:
```bash
cd /opt/weekly-report && python3 -c "
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('report/templates'))
t = env.get_template('dashboard.html')
# Render with minimal mock data to check syntax
html = t.render(
    otrs={'period': {'start': '2026-03-20', 'end': '2026-03-27'}},
    otrs_queues=[], otrs_daily_queues=[], monday_boards=[],
    clouds=[], dollar_rate=5.5, total_cloud_cost_brl=0,
    history=[], generated_at='2026-03-28 11:00'
)
print('OK - rendered', len(html), 'chars')
"
```
Expected: `OK - rendered XXXX chars` (no Jinja2 errors)

- [ ] **Step 6: Commit**

```bash
cd /opt/weekly-report
git add report/templates/dashboard.html
git commit -m "feat: rewrite dashboard CSS to dark theme with sidebar layout"
```

---

### Task 2: Rewrite dashboard.html JavaScript (tab switching + Chart.js dark theme + datalabels)

**Files:**
- Modify: `/opt/weekly-report/report/templates/dashboard.html:1082-1236` (the `<script>` block)

- [ ] **Step 1: Replace the entire `<script>` block**

Replace everything from `<script>` (line 1082) to `</script>` (before `</body>`) with the new JavaScript that handles:
1. Sidebar navigation (replaces old tab-btn click handlers)
2. Sub-tab switching (same logic, dark colors)
3. Chart.js with dark theme colors, custom tooltips, animations, datalabels
4. Mobile hamburger toggle

```html
<script>
// === Register datalabels plugin ===
Chart.register(ChartDataLabels);

// === Chart.js global defaults (dark theme) ===
Chart.defaults.color = '#7d8590';
Chart.defaults.font.family = "'Inter', 'Segoe UI', system-ui, sans-serif";
Chart.defaults.font.size = 11;
Chart.defaults.plugins.datalabels = { display: false }; // off by default, enable per chart
Chart.defaults.animation = { duration: 800, easing: 'easeOutQuart' };

const DARK = {
    grid: 'rgba(48,54,61,0.5)',
    tick: '#7d8590',
    tooltipBg: '#1c2128',
    tooltipBorder: '#30363d',
    palette: ['#2563eb','#3b82f6','#60a5fa','#93c5fd','#2ea043','#d29922','#f85149','#7c3aed','#0891b2','#db2777','#65a30d','#ea580c','#6366f1','#14b8a6','#f59e0b'],
};

// Custom tooltip styling
const darkTooltip = {
    backgroundColor: DARK.tooltipBg,
    borderColor: DARK.tooltipBorder,
    borderWidth: 1,
    titleColor: '#e6edf3',
    bodyColor: '#e6edf3',
    cornerRadius: 6,
    padding: 10,
    titleFont: { weight: '600' },
    bodyFont: { size: 12 },
    boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
};

const darkScales = {
    x: { ticks: { color: DARK.tick }, grid: { color: DARK.grid } },
    y: { ticks: { color: DARK.tick }, grid: { color: DARK.grid } },
};

const darkChartOpts = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: { labels: { color: DARK.tick, font: { family: "'Inter'", size: 11 }, usePointStyle: true, padding: 12 } },
        tooltip: darkTooltip,
        datalabels: { display: false },
    },
    scales: darkScales,
};

// === Sidebar tab switching ===
const sectionTitles = { cloud: 'Cloud', ti: 'TI Corporativo', seguranca: 'Seguranca', diario: 'Diario (D-1)' };
document.querySelectorAll('.sidebar-nav button[data-tab]').forEach(btn => {
    btn.addEventListener('click', function() {
        document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
        document.querySelectorAll('.sidebar-nav button').forEach(el => el.classList.remove('active'));
        const tabId = 'tab-' + this.dataset.tab;
        const tabEl = document.getElementById(tabId);
        if (tabEl) tabEl.classList.add('active');
        this.classList.add('active');
        const titleEl = document.getElementById('sectionTitle');
        if (titleEl) titleEl.textContent = sectionTitles[this.dataset.tab] || this.dataset.tab;
        // Close mobile sidebar
        document.getElementById('sidebar').classList.remove('open');
        document.getElementById('sidebarOverlay').classList.remove('active');
    });
});

// === Sub-tab switching ===
document.querySelectorAll('.subtab-btn').forEach(btn => {
    btn.addEventListener('click', function() {
        const group = this.closest('.subtabs').dataset.group;
        document.querySelectorAll('.subtab-content[data-group="' + group + '"]').forEach(el => el.classList.remove('active'));
        this.closest('.subtabs').querySelectorAll('.subtab-btn').forEach(el => el.classList.remove('active'));
        document.getElementById('subtab-' + this.dataset.subtab).classList.add('active');
        this.classList.add('active');
    });
});

// === Mobile hamburger ===
document.getElementById('hamburgerBtn').addEventListener('click', function() {
    document.getElementById('sidebar').classList.add('open');
    document.getElementById('sidebarOverlay').classList.add('active');
});
document.getElementById('sidebarOverlay').addEventListener('click', function() {
    document.getElementById('sidebar').classList.remove('open');
    this.classList.remove('active');
});
document.getElementById('sidebarClose').addEventListener('click', function() {
    document.getElementById('sidebar').classList.remove('open');
    document.getElementById('sidebarOverlay').classList.remove('active');
});

// === Helper: create horizontal bar chart ===
function createHBar(canvasId, items, nameKey) {
    const el = document.getElementById(canvasId);
    if (!el || !items.length) return;
    new Chart(el, {
        type: 'bar',
        data: {
            labels: items.map(r => { const n = r[nameKey || 'name']; return n.length > 25 ? n.substring(0,25) + '...' : n; }),
            datasets: [{
                label: 'Chamados', data: items.map(r => r.count),
                backgroundColor: items.map((_, i) => DARK.palette[i % DARK.palette.length]),
                borderRadius: 4,
            }]
        },
        options: {
            ...darkChartOpts, indexAxis: 'y',
            plugins: {
                ...darkChartOpts.plugins,
                legend: { display: false },
                datalabels: { display: true, anchor: 'end', align: 'end', color: '#e6edf3', font: { weight: '600', size: 11 } },
            },
            scales: {
                x: { ticks: { color: DARK.tick, stepSize: 1 }, grid: { color: DARK.grid } },
                y: { ticks: { color: DARK.tick, font: { size: 11 } }, grid: { display: false } },
            },
        },
    });
}

// === Helper: create doughnut chart ===
function createDoughnut(canvasId, items, labelKey) {
    const el = document.getElementById(canvasId);
    if (!el || !items.length) return;
    new Chart(el, {
        type: 'doughnut',
        data: {
            labels: items.map(s => s[labelKey || 'service']),
            datasets: [{
                data: items.map(s => s.count),
                backgroundColor: items.map((_, i) => DARK.palette[i % DARK.palette.length]),
                borderWidth: 2, borderColor: '#1c2128',
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
                legend: { position: 'right', labels: { color: DARK.tick, font: { size: 11 }, padding: 8, usePointStyle: true } },
                tooltip: darkTooltip,
                datalabels: { display: true, color: '#e6edf3', font: { weight: '600', size: 11 }, formatter: (v, ctx) => { const total = ctx.dataset.data.reduce((a,b) => a+b, 0); return ((v/total)*100).toFixed(0) + '%'; } },
            },
        },
    });
}

// --- Chamados TI: graficos ---
{% set ns_ti_js = namespace(queue=none) %}
{% for q in otrs_queues %}{% if q.queue_name == 'TI' %}{% set ns_ti_js.queue = q %}{% endif %}{% endfor %}
{% set ti_queue_js = ns_ti_js.queue %}
{% if ti_queue_js and ti_queue_js.top_requesters %}
(function() {
    createHBar('topRequestersChart', {{ ti_queue_js.top_requesters | tojson }}, 'name');
    createDoughnut('serviceBreakdownChart', {{ ti_queue_js.service_breakdown | tojson }}, 'service');
    {% if ti_queue_js.owner_breakdown %}
    createHBar('ownerBreakdownChartTI', {{ ti_queue_js.owner_breakdown | tojson }}, 'name');
    {% endif %}
})();
{% endif %}

// --- Chamados CLOUD: graficos ---
{% set ns_cloud_js = namespace(queue=none) %}
{% for q in otrs_queues %}{% if q.queue_name == 'CLOUD' %}{% set ns_cloud_js.queue = q %}{% endif %}{% endfor %}
{% set cloud_queue_js = ns_cloud_js.queue %}
{% if cloud_queue_js and cloud_queue_js.top_requesters %}
(function() {
    createHBar('topRequestersChartCloud', {{ cloud_queue_js.top_requesters | tojson }}, 'name');
    createDoughnut('serviceBreakdownChartCloud', {{ cloud_queue_js.service_breakdown | tojson }}, 'service');
    {% if cloud_queue_js.owner_breakdown %}
    createHBar('ownerBreakdownChartCloud', {{ cloud_queue_js.owner_breakdown | tojson }}, 'name');
    {% endif %}
})();
{% endif %}

// --- Diario D-1: graficos ---
{% if otrs_daily_queues %}
(function() {
    const dailyQueues = {{ otrs_daily_queues | tojson }};
    dailyQueues.forEach(function(dq) {
        const qName = dq.queue_name;
        createHBar('topRequestersDaily_' + qName, dq.top_requesters || [], 'name');
        createDoughnut('serviceDaily_' + qName, dq.service_breakdown || [], 'service');
        createHBar('ownerDaily_' + qName, dq.owner_breakdown || [], 'name');
    });
})();
{% endif %}

// --- Historico ---
{% if history|length >= 1 %}
const historyData = {{ history | tojson }};
const labels = historyData.map(h => h.period ? h.period.end || h.date : h.date);
const queueNames = {{ otrs_queues | map(attribute='queue_name') | list | tojson }};

function getQueueHistory(queueName) {
    return historyData.map(h => {
        if (h.queues && h.queues[queueName]) return h.queues[queueName];
        if (queueName === queueNames[0]) return { opened: h.opened || 0, closed: h.closed || 0, backlog: h.backlog || 0, pct_first_response: h.pct_first_response || null, pct_resolution: h.pct_resolution || null };
        return { opened: 0, closed: 0, backlog: 0, pct_first_response: null, pct_resolution: null };
    });
}

queueNames.forEach(qName => {
    const qData = getQueueHistory(qName);
    const ticketsEl = document.getElementById('ticketsChart_' + qName);
    const slaEl = document.getElementById('slaChart_' + qName);
    if (ticketsEl) {
        new Chart(ticketsEl, { type: 'bar', data: { labels: labels, datasets: [
            { label: 'Abertos', data: qData.map(d => d.opened), backgroundColor: '#2563eb', borderRadius: 3 },
            { label: 'Fechados', data: qData.map(d => d.closed), backgroundColor: '#2ea043', borderRadius: 3 },
            { label: 'Backlog', data: qData.map(d => d.backlog), backgroundColor: '#e65100', type: 'line', borderColor: '#e65100', fill: false, tension: 0.35, pointRadius: 3 },
        ] }, options: { ...darkChartOpts, plugins: { ...darkChartOpts.plugins, datalabels: { display: true, anchor: 'end', align: 'end', color: '#e6edf3', font: { size: 10 }, formatter: v => v > 0 ? v : '' } } } });
    }
    if (slaEl) {
        new Chart(slaEl, { type: 'line', data: { labels: labels, datasets: [
            { label: '1a Resposta (%) ', data: qData.map(d => d.pct_first_response), borderColor: '#2563eb', backgroundColor: 'rgba(37,99,235,0.08)', fill: true, tension: 0.35, pointRadius: 4, pointBackgroundColor: '#2563eb' },
            { label: 'Resolucao (%)', data: qData.map(d => d.pct_resolution), borderColor: '#e65100', backgroundColor: 'rgba(230,81,0,0.08)', fill: true, tension: 0.35, pointRadius: 4, pointBackgroundColor: '#e65100' },
            { label: 'Meta (90%)', data: qData.map(() => 90), borderColor: '#2ea043', borderDash: [5,5], pointRadius: 0 },
        ] }, options: { ...darkChartOpts, scales: { ...darkChartOpts.scales, y: { ...darkChartOpts.scales.y, min: 0, max: 100, ticks: { ...darkChartOpts.scales.y.ticks, callback: v => v + '%' } } } } });
    }
});

// Cost history chart with gradient fill
const providers = [...new Set(historyData.flatMap(h => Object.keys(h.cloud_costs || {})))];
const chartColors = { 'AWS': '#e65100', 'OCI': '#f85149', 'Golden Cloud': '#d29922' };
const costEl = document.getElementById('costChart');
if (costEl) {
    new Chart(costEl, { type: 'line', data: { labels: labels, datasets: providers.map(p => ({
        label: p,
        data: historyData.map(h => (h.cloud_costs || {})[p] || 0),
        borderColor: chartColors[p] || '#2563eb',
        backgroundColor: (chartColors[p] || '#2563eb') + '15',
        fill: true,
        tension: 0.35,
        pointRadius: 4,
        pointBackgroundColor: chartColors[p] || '#2563eb',
    })) }, options: darkChartOpts });
}
{% endif %}
</script>
```

- [ ] **Step 2: Verify template renders with JS**

Run:
```bash
cd /opt/weekly-report && python3 -c "
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('report/templates'))
t = env.get_template('dashboard.html')
html = t.render(
    otrs={'period': {'start': '2026-03-20', 'end': '2026-03-27'}},
    otrs_queues=[], otrs_daily_queues=[], monday_boards=[],
    clouds=[], dollar_rate=5.5, total_cloud_cost_brl=0,
    history=[], generated_at='2026-03-28 11:00'
)
print('OK - rendered', len(html), 'chars')
assert 'ChartDataLabels' in html
assert 'sidebar' in html
assert 'DARK' in html
print('All assertions passed')
"
```
Expected: OK with all assertions

- [ ] **Step 3: Commit**

```bash
cd /opt/weekly-report
git add report/templates/dashboard.html
git commit -m "feat: rewrite dashboard JS for sidebar nav, dark Chart.js theme, datalabels"
```

---

### Task 3: Update login pages to aligned dark palette

**Files:**
- Modify: `/opt/weekly-report/report/templates/login.html`
- Modify: `/opt/weekly-report/report/templates/forgot_password.html`
- Modify: `/opt/weekly-report/report/templates/reset_password.html`
- Modify: `/opt/weekly-report/report/templates/change_password.html`

All four login-related pages need their CSS `:root` variables updated and Inter font added.

- [ ] **Step 1: Update login.html**

Replace the `:root` block and add Inter font:

```html
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - Surf Telecom</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #0d1117;
            --card: #1c2128;
            --border: #30363d;
            --text: #e6edf3;
            --text-muted: #7d8590;
            --accent: #2563eb;
            --accent-hover: #3b82f6;
            --red: #f85149;
            --green: #2ea043;
        }
```

Update `body` font-family to `'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif`.

Update `.login-card` border-radius from `16px` to `8px`.

Update `.form-group input` border-radius from `10px` to `6px`, background to `var(--bg)`.

Update `.btn` border-radius from `10px` to `6px`, add `transition: background 0.15s;` and `btn:hover { background: var(--accent-hover); }` instead of opacity.

- [ ] **Step 2: Update forgot_password.html**

Same `:root` variable changes. Same Inter font addition. Same border-radius updates (card `8px`, inputs `6px`, button `6px`).

- [ ] **Step 3: Update reset_password.html**

Same changes as above.

- [ ] **Step 4: Update change_password.html**

Same changes. Also update `--yellow: #eab308` to `--yellow: #d29922` to match the dashboard palette.

- [ ] **Step 5: Verify all login templates render**

```bash
cd /opt/weekly-report && python3 -c "
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('report/templates'))
for name in ['login.html', 'forgot_password.html', 'reset_password.html', 'change_password.html']:
    t = env.get_template(name)
    html = t.render(error=None, success=None, user='test', token='abc', first_login=False, expired=False)
    assert '--bg: #0d1117' in html, f'{name} missing new palette'
    assert 'Inter' in html, f'{name} missing Inter font'
    print(f'{name}: OK ({len(html)} chars)')
"
```

- [ ] **Step 6: Commit**

```bash
cd /opt/weekly-report
git add report/templates/login.html report/templates/forgot_password.html report/templates/reset_password.html report/templates/change_password.html
git commit -m "feat: align login pages to dark professional palette with Inter font"
```

---

### Task 4: Rewrite detail pages (solicitante, servico, atendente) with sidebar layout

**Files:**
- Modify: `/opt/weekly-report/report/templates/chamados_solicitante.html`
- Modify: `/opt/weekly-report/report/templates/chamados_servico.html`
- Modify: `/opt/weekly-report/report/templates/chamados_atendente.html`

All three detail pages need the same treatment: new dark palette, sidebar layout, breadcrumb navigation replacing "Voltar" button, and dark-themed tables.

- [ ] **Step 1: Rewrite chamados_solicitante.html**

Replace the entire file with the dark theme version. Key changes:
- Same `:root` variables as dashboard.html
- Add sidebar (same as dashboard but with no active nav item, just links)
- Replace gradient header with flat dark header
- Replace "Voltar ao Dashboard" button with breadcrumb
- Dark table styling (alternating rows with `--bg-main` / `--bg-card`)
- Badge styling using dot + text (no background)
- Search box with dark styling

The complete template structure:

```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chamados — {{ customer_name }}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        /* Same :root as dashboard */
        :root {
            --bg-body: #0d1117; --bg-main: #161b22; --bg-card: #1c2128;
            --bg-card-hover: #21262d; --border: #30363d; --text: #e6edf3;
            --text-muted: #7d8590; --accent: #2563eb; --accent-hover: #3b82f6;
            --accent-soft: rgba(37,99,235,0.1); --green: #2ea043; --red: #f85149;
            --yellow: #d29922; --sidebar-w: 220px;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Inter','Segoe UI',system-ui,sans-serif; background: var(--bg-main); color: var(--text); min-height: 100vh; -webkit-font-smoothing: antialiased; }
        .app-layout { display: grid; grid-template-columns: var(--sidebar-w) 1fr; min-height: 100vh; }
        .sidebar { background: var(--bg-body); border-right: 1px solid var(--border); padding: 24px 0; position: fixed; top: 0; left: 0; width: var(--sidebar-w); height: 100vh; overflow-y: auto; z-index: 100; }
        .sidebar-logo { padding: 0 20px 20px; border-bottom: 1px solid var(--border); margin-bottom: 12px; }
        .sidebar-logo h2 { font-size: 1.1rem; font-weight: 700; color: var(--text); }
        .sidebar-logo span { font-size: 0.72rem; color: var(--text-muted); display: block; margin-top: 2px; }
        .sidebar-nav { list-style: none; padding: 0 8px; }
        .sidebar-nav li { margin-bottom: 2px; }
        .sidebar-nav a { display: flex; align-items: center; gap: 10px; width: 100%; padding: 9px 12px; border-radius: 6px; color: var(--text-muted); font-size: 0.85rem; font-weight: 500; text-decoration: none; transition: background 0.15s, color 0.15s; border-left: 3px solid transparent; }
        .sidebar-nav a:hover { background: var(--accent-soft); color: var(--text); }
        .sidebar-footer { position: absolute; bottom: 0; left: 0; right: 0; padding: 12px 20px; border-top: 1px solid var(--border); }
        .sidebar-footer a { color: var(--text-muted); font-size: 0.78rem; text-decoration: none; } .sidebar-footer a:hover { color: var(--red); }
        .main-area { margin-left: var(--sidebar-w); min-height: 100vh; }
        .header { background: var(--bg-body); border-bottom: 1px solid var(--border); padding: 18px 32px; }
        .header h1 { font-size: 1.15rem; font-weight: 600; color: var(--text); }
        .header .subtitle { color: var(--text-muted); font-size: 0.78rem; }
        .container { max-width: 1400px; margin: 0 auto; padding: 24px 32px; }
        .breadcrumb { color: var(--text-muted); font-size: 0.82rem; margin-bottom: 18px; }
        .breadcrumb a { color: var(--text-muted); text-decoration: none; } .breadcrumb a:hover { color: var(--accent); }
        .breadcrumb .sep { margin: 0 6px; } .breadcrumb .current { color: var(--text); }
        .kpi-grid { display: grid; grid-template-columns: repeat(3,1fr); gap: 14px; margin-bottom: 24px; }
        .kpi-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px; padding: 18px 16px; }
        .kpi-card:hover { background: var(--bg-card-hover); }
        .kpi-card .label { color: var(--text-muted); font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.8px; font-weight: 600; }
        .kpi-card .value { font-size: 2rem; font-weight: 700; margin: 6px 0 2px; color: var(--text); }
        .kpi-card .value.green { color: var(--green); } .kpi-card .value.red { color: var(--red); }
        .kpi-card .value.yellow { color: var(--yellow); } .kpi-card .value.blue { color: var(--accent); }
        .section { background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px; padding: 22px 24px; margin-bottom: 20px; }
        .section h2 { font-size: 0.95rem; font-weight: 600; margin-bottom: 14px; padding-bottom: 10px; border-bottom: 1px solid var(--border); }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 9px 12px; text-align: left; border-bottom: 1px solid var(--border); }
        th { color: var(--text-muted); font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 700; background: var(--bg-main); position: sticky; top: 0; }
        td { font-size: 0.85rem; }
        tr:nth-child(even) td { background: var(--bg-card); }
        tr:nth-child(odd) td { background: var(--bg-main); }
        tr:hover td { background: var(--bg-card-hover); transition: background 0.1s; }
        tr:last-child td { border-bottom: none; }
        .badge { display: inline-flex; align-items: center; gap: 5px; font-size: 0.75rem; font-weight: 500; }
        .badge::before { content: ''; display: inline-block; width: 8px; height: 8px; border-radius: 50%; }
        .badge.aberto { color: var(--accent); } .badge.aberto::before { background: var(--accent); }
        .badge.fechado { color: var(--green); } .badge.fechado::before { background: var(--green); }
        .badge.pendente { color: var(--yellow); } .badge.pendente::before { background: var(--yellow); }
        .search-box { padding: 8px 14px; border-radius: 6px; border: 1px solid var(--border); background: var(--bg-card); color: var(--text); font-size: 0.85rem; font-family: inherit; width: 300px; margin-bottom: 14px; outline: none; }
        .search-box::placeholder { color: var(--text-muted); } .search-box:focus { border-color: var(--accent); }
        .ticket-link { color: var(--accent); text-decoration: none; font-weight: 600; } .ticket-link:hover { color: var(--accent-hover); }
        @media (max-width: 992px) { .app-layout { grid-template-columns: 1fr; } .main-area { margin-left: 0; } .sidebar { display: none; } .kpi-grid { grid-template-columns: repeat(2,1fr); } }
        @media (max-width: 768px) { .container { padding: 16px; } .header { padding: 14px 16px; } .search-box { width: 100%; } }
    </style>
</head>
<body>
<div class="app-layout">
<nav class="sidebar">
    <div class="sidebar-logo"><h2>Surf Telecom</h2><span>Relatorio Semanal</span></div>
    <ul class="sidebar-nav">
        <li><a href="/dashboard"><span style="width:20px;text-align:center;">&#9729;</span> Cloud</a></li>
    </ul>
    <div class="sidebar-footer"><a href="/dashboard/logout">Sair</a></div>
</nav>
<div class="main-area">
    <div class="header">
        <h1>Chamados — {{ customer_name }}</h1>
        <div class="subtitle">Fila: {{ queue_name }} | Relatorio Semanal</div>
    </div>
    <div class="container">
        <div class="breadcrumb">
            <a href="/dashboard">Dashboard</a><span class="sep">/</span>Fila {{ queue_name }}<span class="sep">/</span><span class="current">Solicitante: {{ customer_name }}</span>
        </div>
        <!-- REST OF BODY CONTENT IS IDENTICAL (KPIs + tables) -->
```

The KPIs and tables section (lines 167-252 in the original) stay exactly the same — no changes to Jinja2 logic, just wrapped in the new layout. Close with:

```html
    </div><!-- /container -->
</div><!-- /main-area -->
</div><!-- /app-layout -->
<script>
function filterTable(input, tableId) {
    const filter = input.value.toLowerCase();
    const rows = document.getElementById(tableId).querySelectorAll('tbody tr');
    rows.forEach(row => { row.style.display = row.textContent.toLowerCase().includes(filter) ? '' : 'none'; });
}
</script>
</body>
</html>
```

- [ ] **Step 2: Rewrite chamados_servico.html**

Same changes as solicitante. Different variables:
- Title: `Chamados — {{ service_name }}`
- Breadcrumb: `Dashboard / Fila {{ queue_name }} / {{ service_name }}`
- Table column: "Solicitante" instead of "Servico"

- [ ] **Step 3: Rewrite chamados_atendente.html**

Same changes. Different variables:
- Title: `Atendente — {{ owner_name }}`
- Breadcrumb: `Dashboard / Fila {{ queue_name }} / Atendente: {{ owner_name }}`
- Table columns: Solicitante + Servico

- [ ] **Step 4: Verify all detail templates render**

```bash
cd /opt/weekly-report && python3 -c "
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('report/templates'))
for name, ctx in [
    ('chamados_solicitante.html', {'customer_name':'Test','queue_name':'CLOUD','total':5,'abertos':[],'fechados':[],'otrs_panel_url':'http://otrs'}),
    ('chamados_servico.html', {'service_name':'EC2','queue_name':'CLOUD','total':3,'abertos':[],'fechados':[],'otrs_panel_url':'http://otrs'}),
    ('chamados_atendente.html', {'owner_name':'Admin','queue_name':'TI','total':2,'abertos':[],'fechados':[],'otrs_panel_url':'http://otrs'}),
]:
    t = env.get_template(name)
    html = t.render(**ctx)
    assert '--bg-body: #0d1117' in html, f'{name} missing new palette'
    assert 'sidebar' in html, f'{name} missing sidebar'
    assert 'breadcrumb' in html, f'{name} missing breadcrumb'
    print(f'{name}: OK ({len(html)} chars)')
"
```

- [ ] **Step 5: Commit**

```bash
cd /opt/weekly-report
git add report/templates/chamados_solicitante.html report/templates/chamados_servico.html report/templates/chamados_atendente.html
git commit -m "feat: rewrite detail pages with dark theme and sidebar layout"
```

---

### Task 5: Final visual QA pass and inline style cleanup

**Files:**
- Modify: `/opt/weekly-report/report/templates/dashboard.html` (cleanup inline styles)

The original dashboard.html has many inline `style=""` attributes (e.g., `style="margin-bottom: 20px;"`, `style="text-align: right;"`). Most of these still work fine with the dark theme. This task does a sweep to:

1. Ensure all hardcoded colors in inline styles are updated to dark theme vars
2. Replace `#ffffff` border-color references with `var(--border)`
3. Ensure the accent-light banner in the Diario tab uses dark-compatible colors

- [ ] **Step 1: Fix the Diario D-1 info banner**

In the dashboard.html Diario section, find:
```html
<div class="section" style="margin-bottom: 20px; background: var(--accent-light); border-color: var(--accent);">
    <p style="color: var(--accent); font-weight: 600; font-size: 0.88rem;">
```

Replace with:
```html
<div class="section" style="margin-bottom: 20px; background: var(--accent-soft); border-color: var(--accent);">
    <p style="color: var(--accent-hover); font-weight: 600; font-size: 0.88rem;">
```

- [ ] **Step 2: Fix doughnut chart border color**

In the JS, doughnut charts use `borderColor: '#ffffff'` in the old code. The new helper function already uses `'#1c2128'` (matches card background). Verify this is correct in the createDoughnut helper.

- [ ] **Step 3: Fix inline cost section styling**

In the Custos Cloud section, find any `style="color: var(--accent);"` for links and ensure they use `--accent` (which is now `#2563eb`). Also check the "Total Geral" card border-color uses `var(--accent)`.

- [ ] **Step 4: Run the full report generation to verify end-to-end**

```bash
cd /opt/weekly-report
source venv/bin/activate
python3 main.py --dry-run 2>&1 | head -20
```

If `--dry-run` generates the dashboard HTML, check it was written and open it to verify the dark theme renders correctly.

- [ ] **Step 5: Commit**

```bash
cd /opt/weekly-report
git add report/templates/dashboard.html
git commit -m "fix: update inline styles for dark theme compatibility"
```

---

### Task 6: Verify responsive behavior and final check

**Files:**
- All modified templates (read-only verification)

- [ ] **Step 1: Check all templates render without errors**

```bash
cd /opt/weekly-report && python3 -c "
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('report/templates'))

# Dashboard with realistic mock data
t = env.get_template('dashboard.html')
html = t.render(
    otrs={'period': {'start': '2026-03-20', 'end': '2026-03-27'}},
    otrs_queues=[{
        'queue_name': 'CLOUD', 'opened': 10, 'closed': 8, 'backlog': 5,
        'first_response_target': 24, 'resolution_target': 72,
        'pct_first_response': 85.0, 'pct_resolution': 90.0,
        'top_requesters': [{'name': 'User A', 'count': 3}],
        'service_breakdown': [{'service': 'EC2', 'count': 5}],
        'owner_breakdown': [{'name': 'Admin', 'count': 7}],
    }],
    otrs_daily_queues=[],
    monday_boards=[],
    clouds=[{'provider': 'AWS', 'currency': 'USD', 'total_cost': 1000, 'total_cost_brl': 5500, 'period': {'start': '2026-03-01', 'end': '2026-03-27'}}],
    dollar_rate=5.5, total_cloud_cost_brl=5500,
    history=[], generated_at='2026-03-28 11:00'
)
assert 'sidebar' in html
assert '--bg-body: #0d1117' in html
assert 'ChartDataLabels' in html
print(f'dashboard.html: OK ({len(html)} chars)')

# Login pages
for name in ['login.html', 'forgot_password.html', 'reset_password.html', 'change_password.html']:
    t = env.get_template(name)
    html = t.render(error=None, success=None, user='test', token='abc', first_login=False, expired=False)
    print(f'{name}: OK ({len(html)} chars)')

# Detail pages
for name, ctx in [
    ('chamados_solicitante.html', {'customer_name':'Test','queue_name':'CLOUD','total':5,'abertos':[],'fechados':[],'otrs_panel_url':'http://otrs'}),
    ('chamados_servico.html', {'service_name':'EC2','queue_name':'CLOUD','total':3,'abertos':[],'fechados':[],'otrs_panel_url':'http://otrs'}),
    ('chamados_atendente.html', {'owner_name':'Admin','queue_name':'TI','total':2,'abertos':[],'fechados':[],'otrs_panel_url':'http://otrs'}),
]:
    t = env.get_template(name)
    html = t.render(**ctx)
    print(f'{name}: OK ({len(html)} chars)')

print('ALL TEMPLATES RENDER SUCCESSFULLY')
"
```
Expected: All templates render without errors.

- [ ] **Step 2: Verify CSS responsive breakpoints are present**

```bash
cd /opt/weekly-report && grep -c '@media' report/templates/dashboard.html
```
Expected: 3 (for 1200px, 992px, 768px breakpoints)

- [ ] **Step 3: Restart the API server to serve updated templates**

```bash
sudo systemctl restart weekly-report-api
```

Verify: `curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/dashboard/login`
Expected: `200`
