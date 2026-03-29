# React Frontend Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Jinja2 dashboard with the Lovable React SPA, connecting it to real data via a JSON API served by Flask, preserving existing authentication.

**Architecture:** Flask continues handling auth (login/logout/reset). A new `/dashboard/api/report-data` endpoint reads the latest `report-data.json` file written by `main.py` on each cron run. The React build is output to `/var/www/html/dashboard/` and served by Flask as static files behind `login_required`. The React app fetches `/dashboard/api/report-data` on load and replaces all mock data.

**Tech Stack:** Python/Flask (backend), React 18 + TypeScript + Vite + Tailwind + shadcn/ui + Recharts (frontend), nginx reverse proxy (unchanged)

---

## File Structure

### Backend (Python — `/opt/weekly-report/`)

| File | Action | Responsibility |
|------|--------|---------------|
| `main.py` | Modify | After generating report, save `data/report-data.json` |
| `api_server.py` | Modify | Add `/dashboard/api/report-data` endpoint; serve React build as SPA |
| `report/generator.py` | Modify | Return `report_data` dict (already does), add JSON export method |

### Frontend (React — `/home/ubuntu/weekly-report-hub/`)

| File | Action | Responsibility |
|------|--------|---------------|
| `src/hooks/useReportData.ts` | Create | Custom hook to fetch `/dashboard/api/report-data` |
| `src/types/report.ts` | Create | TypeScript interfaces matching backend JSON schema |
| `src/data/mockData.ts` | Modify | Export as fallback only; all components use live data |
| `src/App.tsx` | Modify | Set `basename="/dashboard"` on BrowserRouter |
| `src/pages/Dashboard.tsx` | Modify | Use `useReportData` hook, pass data to tabs |
| `src/pages/Login.tsx` | Modify | POST to `/dashboard/login` (real Flask auth) |
| `src/components/dashboard/CloudTab.tsx` | Modify | Accept props from live data |
| `src/components/dashboard/GenericQueueTab.tsx` | Modify | Accept props from live data |
| `src/components/dashboard/TicketsChart.tsx` | Modify | Accept data as props |
| `src/components/dashboard/SlaChart.tsx` | Modify | Accept data as props |
| `src/components/dashboard/Sidebar.tsx` | Modify | Logout hits `/dashboard/logout` |
| `vite.config.ts` | Modify | Set `base: "/dashboard/"`, output to `/var/www/html/dashboard/` |

### Infrastructure

| File | Action | Responsibility |
|------|--------|---------------|
| `deploy.sh` | Create | Build React + copy to serve dir + restart Flask |

---

## Task 1: Install Node.js on the server

**Files:** None (system-level)

- [ ] **Step 1: Install Node.js 20 LTS via NodeSource**

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs
```

- [ ] **Step 2: Verify installation**

Run: `node --version && npm --version`
Expected: `v20.x.x` and `10.x.x`

---

## Task 2: Backend — Save report-data.json from main.py

**Files:**
- Modify: `main.py:276-287` (after `generator.generate()`)
- Modify: `report/generator.py` (add `save_report_json` method)

- [ ] **Step 1: Add JSON export to generator.py**

After the `generate()` method in `report/generator.py`, add a static method:

```python
@staticmethod
def save_report_json(report_data: dict, output_path: str):
    """Salva dados do relatório como JSON para o frontend React."""
    import copy
    data = copy.deepcopy(report_data)
    # Remove campos não serializáveis ou desnecessários
    for key in list(data.keys()):
        if key == "history":
            # Mantém só últimas 12 semanas para o frontend
            data[key] = data[key][-12:]
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2, default=str)
```

- [ ] **Step 2: Call save_report_json from main.py**

In `main.py`, after the `generator.generate()` call (line ~282), add:

```python
# Salva JSON para o frontend React
report_json_path = "/opt/weekly-report/data/report-data.json"
generator.save_report_json(result["report_data"], report_json_path)
logger.info("Report JSON: %s", report_json_path)
```

- [ ] **Step 3: Test by running main.py**

```bash
cd /opt/weekly-report && source venv/bin/activate
python main.py --dry-run --skip-otrs 2>&1 | tail -5
cat data/report-data.json | python3 -c "import sys,json; d=json.load(sys.stdin); print(list(d.keys()))"
```

Expected: File created with keys like `generated_at`, `otrs`, `clouds`, `cloud_details`, `total_cloud_cost_brl`, `dollar_rate`, `monday_boards`, `otrs_queues`, `deltas`, `history`, `monthly_costs`.

- [ ] **Step 4: Commit**

```bash
git add main.py report/generator.py
git commit -m "feat: export report-data.json for React frontend"
```

---

## Task 3: Backend — Add API endpoint and SPA serving

**Files:**
- Modify: `api_server.py`

- [ ] **Step 1: Add `/dashboard/api/report-data` endpoint**

Add after the `golden_cloud_options()` function in `api_server.py`:

```python
REPORT_DATA_FILE = "/opt/weekly-report/data/report-data.json"

@app.route("/dashboard/api/report-data")
@login_required
def report_data_api():
    """Serve dados do relatório para o frontend React."""
    if not os.path.exists(REPORT_DATA_FILE):
        return jsonify({"error": "Dados ainda não gerados. Execute main.py primeiro."}), 404
    with open(REPORT_DATA_FILE) as f:
        data = json.load(f)
    return jsonify(data)
```

- [ ] **Step 2: Modify dashboard route to serve React SPA**

Replace the existing `dashboard()` route with:

```python
@app.route("/dashboard/")
@app.route("/dashboard")
@login_required
def dashboard():
    """Serve o React SPA (index.html)."""
    index_path = os.path.join(DASHBOARD_DIR, "index.html")
    if os.path.exists(index_path):
        return send_from_directory(DASHBOARD_DIR, "index.html")
    return (
        "<h1>Dashboard ainda não foi gerado.</h1><p>Execute o build do frontend.</p>",
        404,
    )


@app.route("/dashboard/assets/<path:filename>")
@login_required
def dashboard_assets(filename):
    """Serve assets do React build (JS, CSS, imagens)."""
    assets_dir = os.path.join(DASHBOARD_DIR, "assets")
    return send_from_directory(assets_dir, filename)
```

- [ ] **Step 3: Test the API endpoint**

```bash
# Restart the service
sudo systemctl restart weekly-report-api

# Login and test (grab session cookie)
curl -c /tmp/cookies.txt -d "username=carlos&password=YOURPASS" http://127.0.0.1:8080/dashboard/login
curl -b /tmp/cookies.txt http://127.0.0.1:8080/dashboard/api/report-data | python3 -m json.tool | head -20
```

Expected: JSON output with report data.

- [ ] **Step 4: Commit**

```bash
git add api_server.py
git commit -m "feat: add /api/report-data endpoint and SPA serving for React frontend"
```

---

## Task 4: Frontend — TypeScript types and data hook

**Files:**
- Create: `src/types/report.ts`
- Create: `src/hooks/useReportData.ts`

- [ ] **Step 1: Create TypeScript interfaces**

Create `src/types/report.ts`:

```typescript
export interface OtrsQueue {
  queue_name: string;
  period: { start: string; end: string };
  opened: number;
  closed: number;
  backlog: number;
  avg_first_response_hours: number | null;
  avg_resolution_hours: number | null;
  pct_first_response: number | null;
  pct_resolution: number | null;
  first_response_target: number;
  resolution_target: number;
  tickets: OtrsTicket[];
  top_requesters?: { customer: string; count: number }[];
  service_breakdown?: { service: string; count: number }[];
  owner_breakdown?: { owner: string; total: number; closed: number; open: number }[];
}

export interface OtrsTicket {
  ticket_id: number;
  title: string;
  state: string;
  owner: string;
  customer: string;
  service: string;
  created: string;
}

export interface CloudCost {
  provider: string;
  period: { start: string; end: string };
  currency: string;
  total_cost: number;
  total_cost_brl: number;
  top_services: { service: string; cost: number }[];
  accounts?: { account_name: string; cost: number }[];
}

export interface MondayProject {
  name: string;
  status: string;
  progress: number;
  owner: string;
  deadline: string;
}

export interface MondayBoard {
  board_name: string;
  category: string;
  total_projects: number;
  status_summary: Record<string, number>;
  items: MondayProject[];
}

export interface MonthlyCost {
  month: string;
  cost: number;
  currency: string;
}

export interface HistoryEntry {
  date: string;
  period: { start: string; end: string };
  cloud_costs: Record<string, number>;
  cloud_details?: Record<string, {
    total_cost: number;
    currency: string;
    total_cost_brl: number;
    top_services?: { service: string; cost: number }[];
    accounts?: { name: string; cost: number }[];
  }>;
  queues: Record<string, {
    opened: number;
    closed: number;
    backlog: number;
    pct_first_response: number | null;
    pct_resolution: number | null;
  }>;
}

export interface Deltas {
  [key: string]: { current: number; previous: number; pct: number };
}

export interface ReportData {
  generated_at: string;
  otrs: OtrsQueue;
  clouds: CloudCost[];
  cloud_details: Record<string, {
    total_cost: number;
    currency: string;
    total_cost_brl: number;
    top_services?: { service: string; cost: number }[];
    accounts?: { account_name: string; cost: number }[];
  }>;
  total_cloud_cost_brl: number;
  dollar_rate: number;
  dashboard_url: string;
  monday_boards: MondayBoard[];
  otrs_queues: OtrsQueue[];
  otrs_daily_queues: OtrsQueue[];
  monthly_costs: Record<string, MonthlyCost[]>;
  deltas: Deltas;
  history: HistoryEntry[];
}
```

- [ ] **Step 2: Create useReportData hook**

Create `src/hooks/useReportData.ts`:

```typescript
import { useQuery } from "@tanstack/react-query";
import type { ReportData } from "@/types/report";

async function fetchReportData(): Promise<ReportData> {
  const resp = await fetch("/dashboard/api/report-data", {
    credentials: "include",
  });
  if (resp.status === 401 || resp.redirected) {
    window.location.href = "/dashboard/login";
    throw new Error("Unauthorized");
  }
  if (!resp.ok) {
    throw new Error(`Erro ao carregar dados: ${resp.status}`);
  }
  return resp.json();
}

export function useReportData() {
  return useQuery<ReportData>({
    queryKey: ["report-data"],
    queryFn: fetchReportData,
    staleTime: 5 * 60 * 1000, // 5 minutos
    retry: 1,
  });
}
```

- [ ] **Step 3: Commit**

```bash
git add src/types/report.ts src/hooks/useReportData.ts
git commit -m "feat: add TypeScript types and useReportData hook"
```

---

## Task 5: Frontend — Configure Vite for /dashboard/ base path

**Files:**
- Modify: `vite.config.ts`
- Modify: `src/App.tsx`

- [ ] **Step 1: Update vite.config.ts**

Replace the entire file:

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";

export default defineConfig({
  base: "/dashboard/",
  build: {
    outDir: "dist",
    sourcemap: false,
  },
  server: {
    host: "::",
    port: 3000,
    proxy: {
      "/dashboard/api": "http://127.0.0.1:8080",
      "/dashboard/login": "http://127.0.0.1:8080",
      "/dashboard/logout": "http://127.0.0.1:8080",
    },
  },
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
```

- [ ] **Step 2: Update App.tsx with basename**

Replace `src/App.tsx`:

```typescript
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import Dashboard from "./pages/Dashboard.tsx";
import NotFound from "./pages/NotFound.tsx";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter basename="/dashboard">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
```

Note: Login/logout pages are handled by Flask (server-rendered). The React app only handles the dashboard SPA. The `/` and `/dashboard/login` routes are served by Flask; only `/dashboard/` (after login) loads the React app.

- [ ] **Step 3: Commit**

```bash
git add vite.config.ts src/App.tsx
git commit -m "feat: configure Vite base=/dashboard/ and remove client-side login route"
```

---

## Task 6: Frontend — Wire Dashboard.tsx to live data

**Files:**
- Modify: `src/pages/Dashboard.tsx`

- [ ] **Step 1: Rewrite Dashboard.tsx to use useReportData**

Replace `src/pages/Dashboard.tsx`:

```typescript
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Sidebar from "@/components/dashboard/Sidebar";
import CloudTab from "@/components/dashboard/CloudTab";
import GenericQueueTab from "@/components/dashboard/GenericQueueTab";
import { useReportData } from "@/hooks/useReportData";
import type { ReportData, OtrsQueue } from "@/types/report";

const tabTitles: Record<string, string> = {
  cloud: "Cloud",
  ti: "TI Corporativo",
  seguranca: "Seguranca",
};

function findQueue(data: ReportData, name: string): OtrsQueue | undefined {
  return data.otrs_queues.find((q) => q.queue_name === name);
}

function queueToKpi(q: OtrsQueue) {
  return {
    opened: q.opened,
    closed: q.closed,
    backlog: q.backlog,
    firstResponse: q.pct_first_response ?? 0,
    resolution: q.pct_resolution ?? 0,
    firstResponseTarget: q.first_response_target,
    resolutionTarget: q.resolution_target,
  };
}

const Dashboard = () => {
  const [activeTab, setActiveTab] = useState("cloud");
  const { data, isLoading, error } = useReportData();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-muted-foreground text-sm">Carregando dados...</div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-destructive text-sm">
          Erro ao carregar dados. <button onClick={() => window.location.reload()} className="underline">Tentar novamente</button>
        </div>
      </div>
    );
  }

  const period = data.otrs?.period ?? { start: "", end: "" };

  return (
    <div className="min-h-screen bg-background">
      <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />

      <div className="lg:pl-60">
        <header className="bg-card border-b border-border px-6 lg:px-8 py-5 flex items-center gap-4">
          <div className="pl-10 lg:pl-0">
            <h1 className="text-lg font-bold text-foreground tracking-tight">
              {tabTitles[activeTab] ?? activeTab}
            </h1>
            <p className="text-muted-foreground text-xs mt-0.5">
              {period.start} a {period.end}
            </p>
          </div>
          <div className="ml-auto text-muted-foreground text-xs hidden sm:block">
            Gerado em {data.generated_at}
          </div>
        </header>

        <main className="max-w-[1400px] mx-auto px-4 lg:px-8 py-6">
          <AnimatePresence mode="wait">
            <motion.div
              key={activeTab}
              initial={{ opacity: 0, x: 12 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -12 }}
              transition={{ duration: 0.25 }}
            >
              {activeTab === "cloud" && (
                <CloudTab data={data} />
              )}
              {activeTab === "ti" && (
                <GenericQueueTab
                  queue={findQueue(data, "TI")}
                  deltas={data.deltas}
                  history={data.history}
                  queueName="TI"
                  mondayBoards={data.monday_boards.filter((b) => b.category === "ti")}
                />
              )}
              {activeTab === "seguranca" && (
                <GenericQueueTab
                  queue={findQueue(data, "SEGURANCA")}
                  deltas={data.deltas}
                  history={data.history}
                  queueName="SEGURANCA"
                  mondayBoards={data.monday_boards.filter((b) => b.category === "seguranca")}
                />
              )}
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
};

export default Dashboard;
```

- [ ] **Step 2: Commit**

```bash
git add src/pages/Dashboard.tsx
git commit -m "feat: wire Dashboard to useReportData hook with loading/error states"
```

---

## Task 7: Frontend — Rewrite CloudTab to use live data

**Files:**
- Modify: `src/components/dashboard/CloudTab.tsx`
- Modify: `src/components/dashboard/TicketsChart.tsx`
- Modify: `src/components/dashboard/SlaChart.tsx`

- [ ] **Step 1: Rewrite CloudTab.tsx**

Replace `src/components/dashboard/CloudTab.tsx`:

```typescript
import { useState } from "react";
import SubTabs from "./SubTabs";
import KpiCard from "./KpiCard";
import TicketsChart from "./TicketsChart";
import SlaChart from "./SlaChart";
import DataTable from "./DataTable";
import StatusBadge from "./StatusBadge";
import type { ReportData, OtrsQueue } from "@/types/report";

interface CloudTabProps {
  data: ReportData;
}

const cloudSubTabs = [
  { id: "chamados", label: "Chamados Cloud" },
  { id: "custos", label: "Custos Cloud" },
  { id: "projetos", label: "Projetos" },
];

const CloudTab = ({ data }: CloudTabProps) => {
  const [subTab, setSubTab] = useState("chamados");

  const queue = data.otrs_queues.find((q) => q.queue_name === "CLOUD");
  const deltas = data.deltas;

  // History for charts (extract CLOUD queue from each history entry)
  const ticketHistory = data.history.map((h) => ({
    week: h.date?.split(" ")[0] ?? "",
    opened: h.queues?.CLOUD?.opened ?? 0,
    closed: h.queues?.CLOUD?.closed ?? 0,
  }));

  const slaHistory = data.history.map((h) => ({
    week: h.date?.split(" ")[0] ?? "",
    firstResponse: h.queues?.CLOUD?.pct_first_response ?? 0,
    resolution: h.queues?.CLOUD?.pct_resolution ?? 0,
  }));

  const mondayBoards = data.monday_boards.filter((b) => b.category === "cloud");

  return (
    <div>
      <SubTabs tabs={cloudSubTabs} active={subTab} onChange={setSubTab} />

      {subTab === "chamados" && queue && (
        <div className="space-y-5">
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
            <KpiCard label="Abertos" value={queue.opened} delta={deltas.CLOUD_opened?.pct} color="primary" index={0} />
            <KpiCard label="Fechados" value={queue.closed} delta={deltas.CLOUD_closed?.pct} color="success" index={1} />
            <KpiCard label="Backlog" value={queue.backlog} delta={deltas.CLOUD_backlog?.pct} color={queue.backlog > 20 ? "destructive" : queue.backlog > 10 ? "warning" : "success"} index={2} />
            <KpiCard
              label={`1a Resposta <= ${queue.first_response_target}h`}
              value={queue.pct_first_response != null ? `${queue.pct_first_response.toFixed(0)}%` : "N/A"}
              color={queue.pct_first_response != null && queue.pct_first_response >= 90 ? "success" : "warning"}
              meta="meta: 90%"
              index={3}
            />
            <KpiCard
              label={`Resolucao <= ${queue.resolution_target}h`}
              value={queue.pct_resolution != null ? `${queue.pct_resolution.toFixed(0)}%` : "N/A"}
              color={queue.pct_resolution != null && queue.pct_resolution >= 90 ? "success" : "warning"}
              meta="meta: 90%"
              index={4}
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <TicketsChart data={ticketHistory} />
            <SlaChart data={slaHistory} />
          </div>

          {queue.top_requesters && queue.top_requesters.length > 0 && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              <DataTable
                title="Top Solicitantes da Semana"
                columns={[
                  { key: "customer", label: "Solicitante", render: (v: string) => <span className="text-primary font-semibold">{v}</span> },
                  { key: "count", label: "Chamados", align: "right" },
                ]}
                data={queue.top_requesters}
              />
              {queue.service_breakdown && (
                <DataTable
                  title="Chamados por Servico"
                  columns={[
                    { key: "service", label: "Servico", render: (v: string) => <span className="text-primary font-semibold">{v || "Sem Servico"}</span> },
                    { key: "count", label: "Chamados", align: "right" },
                  ]}
                  data={queue.service_breakdown}
                />
              )}
            </div>
          )}

          {queue.owner_breakdown && queue.owner_breakdown.length > 0 && (
            <DataTable
              title="Chamados por Atendente"
              columns={[
                { key: "owner", label: "Atendente", render: (v: string) => <span className="font-semibold">{v || "Nao Atribuido"}</span> },
                { key: "total", label: "Total", align: "right" },
                { key: "closed", label: "Fechados", align: "right", render: (v: number) => <span className="text-success">{v}</span> },
                { key: "open", label: "Abertos", align: "right", render: (v: number) => <span className="text-primary">{v}</span> },
              ]}
              data={queue.owner_breakdown}
            />
          )}
        </div>
      )}

      {subTab === "custos" && (
        <div className="space-y-5">
          {/* KPI cards: total por provider */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {data.clouds.map((c, i) => (
              <KpiCard
                key={c.provider}
                label={c.provider}
                value={`R$ ${c.total_cost_brl.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`}
                delta={deltas[`cost_${c.provider}`]?.pct}
                color="primary"
                index={i}
              />
            ))}
            <KpiCard
              label="Total"
              value={`R$ ${data.total_cloud_cost_brl.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`}
              delta={deltas.cost_total?.pct}
              color="success"
              index={data.clouds.length}
              meta={`USD 1 = R$ ${data.dollar_rate.toFixed(2)}`}
            />
          </div>

          {/* Top services per provider */}
          {data.clouds.map((c) => (
            c.top_services && c.top_services.length > 0 && (
              <DataTable
                key={c.provider}
                title={`${c.provider} — Top Servicos`}
                columns={[
                  { key: "service", label: "Servico", render: (v: string) => <span className="font-semibold">{v}</span> },
                  { key: "cost", label: `Custo (${c.currency})`, align: "right", render: (v: number) => v.toLocaleString("pt-BR", { minimumFractionDigits: 2 }) },
                ]}
                data={c.top_services}
              />
            )
          ))}

          {/* Monthly history */}
          {Object.keys(data.monthly_costs).length > 0 && (
            <DataTable
              title="Historico Mensal (ultimos 3 meses)"
              columns={[
                { key: "provider", label: "Provider", render: (v: string) => <span className="font-semibold">{v}</span> },
                ...(() => {
                  const allMonths = new Set<string>();
                  Object.values(data.monthly_costs).forEach((months) =>
                    months.forEach((m) => allMonths.add(m.month))
                  );
                  return [...allMonths].sort().map((month) => ({
                    key: month,
                    label: month,
                    align: "right" as const,
                    render: (v: string) => v ?? "—",
                  }));
                })(),
              ]}
              data={Object.entries(data.monthly_costs).map(([provider, months]) => {
                const row: Record<string, string> = { provider };
                months.forEach((m) => {
                  row[m.month] = `${m.currency} ${m.cost.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`;
                });
                return row;
              })}
            />
          )}
        </div>
      )}

      {subTab === "projetos" && (
        <div className="space-y-5">
          {mondayBoards.map((board) => (
            <DataTable
              key={board.board_name}
              title={board.board_name}
              columns={[
                { key: "name", label: "Projeto", render: (v: string) => <span className="font-semibold">{v}</span> },
                {
                  key: "status",
                  label: "Status",
                  render: (v: string) => {
                    const statusMap: Record<string, "done" | "progress" | "backlog" | "stopped"> = {
                      "Feito": "done", "Concluido": "done", "Done": "done",
                      "Em andamento": "progress", "Trabalhando nisso": "progress", "Working on it": "progress",
                      "Parado": "stopped", "Stuck": "stopped",
                    };
                    return <StatusBadge status={statusMap[v] ?? "backlog"} label={v} />;
                  },
                },
                {
                  key: "progress",
                  label: "Progresso",
                  align: "right",
                  render: (v: number) => (
                    <div className="flex items-center gap-2 justify-end">
                      <div className="w-16 h-1.5 bg-muted rounded-full overflow-hidden">
                        <div className="h-full bg-primary rounded-full" style={{ width: `${v ?? 0}%` }} />
                      </div>
                      <span className="text-xs tabular-nums">{v ?? 0}%</span>
                    </div>
                  ),
                },
                { key: "owner", label: "Responsavel" },
                { key: "deadline", label: "Prazo", align: "right" },
              ]}
              data={board.items}
            />
          ))}
          {mondayBoards.length === 0 && (
            <div className="bg-card border border-border rounded-lg p-8 text-center">
              <p className="text-muted-foreground text-sm">Nenhum projeto Cloud no Monday.com.</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default CloudTab;
```

- [ ] **Step 2: Update TicketsChart to accept data as props**

Replace `src/components/dashboard/TicketsChart.tsx`:

```typescript
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";

interface TicketsChartProps {
  data: { week: string; opened: number; closed: number }[];
}

const TicketsChart = ({ data }: TicketsChartProps) => (
  <div className="bg-card border border-border rounded-lg p-5">
    <h3 className="text-sm font-semibold text-foreground mb-4 pb-3 border-b border-border">
      Chamados — Historico Semanal
    </h3>
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} barGap={4}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(220 13% 20%)" />
          <XAxis dataKey="week" tick={{ fill: "hsl(215 15% 53%)", fontSize: 12 }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: "hsl(215 15% 53%)", fontSize: 12 }} axisLine={false} tickLine={false} />
          <Tooltip
            contentStyle={{
              backgroundColor: "hsl(220 16% 13%)",
              border: "1px solid hsl(220 13% 20%)",
              borderRadius: "8px",
              fontSize: "13px",
            }}
            labelStyle={{ color: "hsl(210 40% 93%)" }}
          />
          <Legend wrapperStyle={{ fontSize: "12px" }} />
          <Bar dataKey="opened" name="Abertos" fill="hsl(221 83% 53%)" radius={[4, 4, 0, 0]} />
          <Bar dataKey="closed" name="Fechados" fill="hsl(142 71% 45%)" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  </div>
);

export default TicketsChart;
```

- [ ] **Step 3: Update SlaChart to accept data as props**

Replace `src/components/dashboard/SlaChart.tsx`:

```typescript
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, ReferenceLine } from "recharts";

interface SlaChartProps {
  data: { week: string; firstResponse: number; resolution: number }[];
}

const SlaChart = ({ data }: SlaChartProps) => (
  <div className="bg-card border border-border rounded-lg p-5">
    <h3 className="text-sm font-semibold text-foreground mb-4 pb-3 border-b border-border">
      SLA — % Dentro da Meta
    </h3>
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(220 13% 20%)" />
          <XAxis dataKey="week" tick={{ fill: "hsl(215 15% 53%)", fontSize: 12 }} axisLine={false} tickLine={false} />
          <YAxis domain={[70, 100]} tick={{ fill: "hsl(215 15% 53%)", fontSize: 12 }} axisLine={false} tickLine={false} />
          <Tooltip
            contentStyle={{
              backgroundColor: "hsl(220 16% 13%)",
              border: "1px solid hsl(220 13% 20%)",
              borderRadius: "8px",
              fontSize: "13px",
            }}
            labelStyle={{ color: "hsl(210 40% 93%)" }}
            formatter={(value: number) => [`${value}%`, ""]}
          />
          <Legend wrapperStyle={{ fontSize: "12px" }} />
          <ReferenceLine y={90} stroke="hsl(38 92% 50%)" strokeDasharray="6 3" label={{ value: "Meta 90%", fill: "hsl(38 92% 50%)", fontSize: 11, position: "insideTopRight" }} />
          <Line type="monotone" dataKey="firstResponse" name="1a Resposta" stroke="hsl(221 83% 53%)" strokeWidth={2} dot={{ r: 4 }} activeDot={{ r: 6 }} />
          <Line type="monotone" dataKey="resolution" name="Resolucao" stroke="hsl(142 71% 45%)" strokeWidth={2} dot={{ r: 4 }} activeDot={{ r: 6 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  </div>
);

export default SlaChart;
```

- [ ] **Step 4: Commit**

```bash
git add src/components/dashboard/CloudTab.tsx src/components/dashboard/TicketsChart.tsx src/components/dashboard/SlaChart.tsx
git commit -m "feat: wire CloudTab, TicketsChart, SlaChart to live data props"
```

---

## Task 8: Frontend — Rewrite GenericQueueTab for live data

**Files:**
- Modify: `src/components/dashboard/GenericQueueTab.tsx`

- [ ] **Step 1: Rewrite GenericQueueTab.tsx**

Replace `src/components/dashboard/GenericQueueTab.tsx`:

```typescript
import KpiCard from "./KpiCard";
import TicketsChart from "./TicketsChart";
import SlaChart from "./SlaChart";
import DataTable from "./DataTable";
import StatusBadge from "./StatusBadge";
import type { OtrsQueue, Deltas, HistoryEntry, MondayBoard } from "@/types/report";

interface GenericQueueTabProps {
  queue?: OtrsQueue;
  deltas: Deltas;
  history: HistoryEntry[];
  queueName: string;
  mondayBoards: MondayBoard[];
}

const GenericQueueTab = ({ queue, deltas, history, queueName, mondayBoards }: GenericQueueTabProps) => {
  if (!queue) {
    return (
      <div className="bg-card border border-border rounded-lg p-8 text-center">
        <p className="text-muted-foreground text-sm">Dados da fila {queueName} nao disponiveis.</p>
      </div>
    );
  }

  const ticketHistory = history.map((h) => ({
    week: h.date?.split(" ")[0] ?? "",
    opened: h.queues?.[queueName]?.opened ?? 0,
    closed: h.queues?.[queueName]?.closed ?? 0,
  }));

  const slaHistory = history.map((h) => ({
    week: h.date?.split(" ")[0] ?? "",
    firstResponse: h.queues?.[queueName]?.pct_first_response ?? 0,
    resolution: h.queues?.[queueName]?.pct_resolution ?? 0,
  }));

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
        <KpiCard label="Abertos" value={queue.opened} delta={deltas[`${queueName}_opened`]?.pct} color="primary" index={0} />
        <KpiCard label="Fechados" value={queue.closed} delta={deltas[`${queueName}_closed`]?.pct} color="success" index={1} />
        <KpiCard label="Backlog" value={queue.backlog} delta={deltas[`${queueName}_backlog`]?.pct} color={queue.backlog > 20 ? "destructive" : queue.backlog > 10 ? "warning" : "success"} index={2} />
        <KpiCard
          label={`1a Resposta <= ${queue.first_response_target}h`}
          value={queue.pct_first_response != null ? `${queue.pct_first_response.toFixed(0)}%` : "N/A"}
          color={queue.pct_first_response != null && queue.pct_first_response >= 90 ? "success" : "warning"}
          meta="meta: 90%"
          index={3}
        />
        <KpiCard
          label={`Resolucao <= ${queue.resolution_target}h`}
          value={queue.pct_resolution != null ? `${queue.pct_resolution.toFixed(0)}%` : "N/A"}
          color={queue.pct_resolution != null && queue.pct_resolution >= 90 ? "success" : "warning"}
          meta="meta: 90%"
          index={4}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <TicketsChart data={ticketHistory} />
        <SlaChart data={slaHistory} />
      </div>

      {queue.top_requesters && queue.top_requesters.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <DataTable
            title="Top Solicitantes da Semana"
            columns={[
              { key: "customer", label: "Solicitante", render: (v: string) => <span className="text-primary font-semibold">{v}</span> },
              { key: "count", label: "Chamados", align: "right" },
            ]}
            data={queue.top_requesters}
          />
          {queue.service_breakdown && (
            <DataTable
              title="Chamados por Servico"
              columns={[
                { key: "service", label: "Servico", render: (v: string) => <span className="text-primary font-semibold">{v || "Sem Servico"}</span> },
                { key: "count", label: "Chamados", align: "right" },
              ]}
              data={queue.service_breakdown}
            />
          )}
        </div>
      )}

      {queue.owner_breakdown && queue.owner_breakdown.length > 0 && (
        <DataTable
          title="Chamados por Atendente"
          columns={[
            { key: "owner", label: "Atendente", render: (v: string) => <span className="font-semibold">{v || "Nao Atribuido"}</span> },
            { key: "total", label: "Total", align: "right" },
            { key: "closed", label: "Fechados", align: "right", render: (v: number) => <span className="text-success">{v}</span> },
            { key: "open", label: "Abertos", align: "right", render: (v: number) => <span className="text-primary">{v}</span> },
          ]}
          data={queue.owner_breakdown}
        />
      )}

      {/* Monday.com boards for this queue */}
      {mondayBoards.map((board) => (
        <DataTable
          key={board.board_name}
          title={board.board_name}
          columns={[
            { key: "name", label: "Projeto", render: (v: string) => <span className="font-semibold">{v}</span> },
            {
              key: "status",
              label: "Status",
              render: (v: string) => {
                const statusMap: Record<string, "done" | "progress" | "backlog" | "stopped"> = {
                  "Feito": "done", "Concluido": "done", "Done": "done",
                  "Em andamento": "progress", "Trabalhando nisso": "progress", "Working on it": "progress",
                  "Parado": "stopped", "Stuck": "stopped",
                };
                return <StatusBadge status={statusMap[v] ?? "backlog"} label={v} />;
              },
            },
            {
              key: "progress",
              label: "Progresso",
              align: "right",
              render: (v: number) => (
                <div className="flex items-center gap-2 justify-end">
                  <div className="w-16 h-1.5 bg-muted rounded-full overflow-hidden">
                    <div className="h-full bg-primary rounded-full" style={{ width: `${v ?? 0}%` }} />
                  </div>
                  <span className="text-xs tabular-nums">{v ?? 0}%</span>
                </div>
              ),
            },
            { key: "owner", label: "Responsavel" },
            { key: "deadline", label: "Prazo", align: "right" },
          ]}
          data={board.items}
        />
      ))}
    </div>
  );
};

export default GenericQueueTab;
```

- [ ] **Step 2: Commit**

```bash
git add src/components/dashboard/GenericQueueTab.tsx
git commit -m "feat: wire GenericQueueTab to live data with queue-specific history"
```

---

## Task 9: Frontend — Update Sidebar logout

**Files:**
- Modify: `src/components/dashboard/Sidebar.tsx`

- [ ] **Step 1: Update the logout button to hit Flask**

In `src/components/dashboard/Sidebar.tsx`, replace the logout button (line 86-89):

```typescript
        <div className="p-3 border-t border-sidebar-border">
          <a
            href="/dashboard/logout"
            className="flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-all w-full"
          >
            <LogOut className="w-4 h-4" />
            Sair
          </a>
        </div>
```

- [ ] **Step 2: Commit**

```bash
git add src/components/dashboard/Sidebar.tsx
git commit -m "feat: wire Sidebar logout to Flask /dashboard/logout"
```

---

## Task 10: Frontend — Clean up unused mock data

**Files:**
- Modify: `src/data/mockData.ts`
- Delete: `src/pages/Login.tsx` (Flask handles login)
- Delete: `src/pages/Index.tsx` (not needed — Flask redirects to dashboard)

- [ ] **Step 1: Remove mockData.ts**

Delete `src/data/mockData.ts` — all data comes from the API now.

- [ ] **Step 2: Delete Login.tsx and Index.tsx**

These pages are handled by Flask server-side. The React SPA only handles `/dashboard/` routes.

- [ ] **Step 3: Commit**

```bash
git rm src/data/mockData.ts src/pages/Login.tsx src/pages/Index.tsx
git commit -m "chore: remove mock data and client-side login/index pages (handled by Flask)"
```

---

## Task 11: Build and deploy

**Files:**
- Create: `deploy.sh` (in `/home/ubuntu/weekly-report-hub/`)

- [ ] **Step 1: Create deploy.sh**

Create `/home/ubuntu/weekly-report-hub/deploy.sh`:

```bash
#!/bin/bash
set -euo pipefail

REPO_DIR="/home/ubuntu/weekly-report-hub"
OUTPUT_DIR="/var/www/html/dashboard"

echo "=== Building React frontend ==="
cd "$REPO_DIR"
npm ci
npm run build

echo "=== Deploying to $OUTPUT_DIR ==="
# Keep the Flask static dir and old data, replace only React build
sudo rm -rf "$OUTPUT_DIR/assets" "$OUTPUT_DIR/index.html" "$OUTPUT_DIR/favicon.ico"
sudo cp -r dist/* "$OUTPUT_DIR/"

echo "=== Restarting Flask ==="
sudo systemctl restart weekly-report-api

echo "=== Done ==="
echo "Dashboard available at: http://cloudteam.surf.com.br/dashboard"
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x /home/ubuntu/weekly-report-hub/deploy.sh
```

- [ ] **Step 3: Install dependencies and build**

```bash
cd /home/ubuntu/weekly-report-hub
npm install
npm run build
```

Expected: `dist/` directory created with `index.html` and `assets/` folder.

- [ ] **Step 4: Deploy**

```bash
cd /home/ubuntu/weekly-report-hub && ./deploy.sh
```

- [ ] **Step 5: Generate report data**

```bash
cd /opt/weekly-report && source venv/bin/activate
python main.py --dry-run --skip-otrs
```

Expected: `data/report-data.json` created.

- [ ] **Step 6: Test end-to-end**

```bash
# Should redirect to login
curl -I http://127.0.0.1:8080/dashboard/

# Login and access dashboard
curl -c /tmp/cookies.txt -d "username=carlos&password=YOURPASS" -L http://127.0.0.1:8080/dashboard/login
curl -b /tmp/cookies.txt http://127.0.0.1:8080/dashboard/ | head -5

# Should return React HTML with /dashboard/ base
# API should return JSON
curl -b /tmp/cookies.txt http://127.0.0.1:8080/dashboard/api/report-data | python3 -m json.tool | head -10
```

- [ ] **Step 7: Commit deploy script**

```bash
git add deploy.sh
git commit -m "feat: add deploy.sh build & deploy script"
```

---

## Task 12: Push both repos to GitHub

- [ ] **Step 1: Push backend changes**

```bash
cd /opt/weekly-report
git push origin master
```

- [ ] **Step 2: Push frontend changes**

```bash
cd /home/ubuntu/weekly-report-hub
git push origin main
```
