import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, CardHeader } from "../components/Card";
import ImportCard from "../components/ImportCard";
import { KpiCard, MonthSelector, StateBadge } from "../components/ui";
import { api, API_BASE } from "../lib/api";
import { monthLabel, money } from "../lib/format";
import type { DashboardData } from "../lib/types";

function AmountTooltip({ active, payload }: { active?: boolean; payload?: { name: string; value: number }[] }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-slate-900 text-white text-xs rounded-lg px-3 py-2 shadow-lg">
      {payload.map((p) => (
        <div key={p.name} className="flex justify-between gap-4">
          <span className="text-slate-300">{p.name}</span>
          <span className="font-medium tabular-nums">{money(p.value)}</span>
        </div>
      ))}
    </div>
  );
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [month, setMonth] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    api
      .dashboard(month || undefined)
      .then((d) => {
        setData(d);
        setMonth((cur) => cur || d.selected_month || "");
      })
      .catch((e: Error) => setError(e.message));
  }, [month, reload]);

  function onImported() {
    setMonth("");
    setReload((r) => r + 1);
  }

  const months = useMemo(() => (data?.months ?? []).map((m) => m.month), [data]);
  const trend = useMemo(
    () =>
      data?.trend.map((t) => ({
        name: t.month,
        Revenue: t.revenue_cents,
        "Gross profit": t.gross_profit_cents,
        "Operating profit": t.operating_profit_cents,
      })) ?? [],
    [data],
  );
  const expenseMix = useMemo(
    () =>
      data?.expense_mix.map((e) => ({
        name: e.category_name,
        amount: Math.abs(e.amount),
        bucket: e.bucket,
      })) ?? [],
    [data],
  );

  const overview = data?.overview;
  const isEmpty = (data?.stats.total_transactions ?? 0) === 0;

  const kpis =
    overview?.lines
      ? {
          revenue: { cents: overview.lines["revenue"] ?? 0, hint: "Food, beverage, catering, delivery" },
          grossProfit: { cents: overview.lines["gross_profit"] ?? 0, hint: "Revenue less COGS" },
          operatingProfit: { cents: overview.lines["operating_profit"] ?? 0, hint: "After payroll and operating expenses" },
          netCash: { cents: overview.net_cash_cents ?? 0, hint: "Net of refunds and payouts" },
          pendingReview: { cents: (overview.pending_review_count ?? 0) * 100, hint: "Need a reviewer decision" },
        }
      : undefined;

  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 text-red-700 px-4 py-6 text-sm">
        Failed to load dashboard: {error}
        <div className="mt-2 text-red-500 text-xs">
          API base: <code className="bg-red-100 px-1 rounded">{API_BASE || "(same-origin)"}</code>
        </div>
        <div className="mt-2 text-red-500 text-xs">
          Is the backend running? Start it with <code className="bg-red-100 px-1 rounded">docker compose up -d backend</code>.
        </div>
      </div>
    );
  }

  if (!data) return <div className="text-sm text-slate-500 py-10">Loading dashboard…</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Dashboard</h1>
          <p className="text-sm text-slate-500">NYC Restaurant Co. · {data.selected_month ? monthLabel(data.selected_month) : ""}</p>
        </div>
        <MonthSelector months={months} value={month} onChange={setMonth} />
      </div>

      <section className="rounded-2xl border border-indigo-100 bg-white shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-100 flex items-start justify-between gap-4">
          <div>
            <div className="text-xs font-medium uppercase tracking-wide text-indigo-600">AI-Native Financial Review</div>
            <p className="text-sm text-slate-600 mt-1 max-w-2xl">
              One controlled pipeline: the AI adds judgement only where deterministic rules are uncertain, the engine
              remains the sole source of truth for every number, and humans clear anything that is unusual or ambiguous.
            </p>
          </div>
          <Link to="/how-it-works" className="shrink-0 text-xs text-indigo-600 hover:underline pt-4">
            How it works →
          </Link>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 divide-y md:divide-y-0 md:divide-x divide-slate-100">
          <div className="px-5 py-4">
            <div className="flex items-center gap-2">
              <span className="w-6 h-6 rounded-lg bg-violet-100 text-violet-700 flex items-center justify-center text-sm">✦</span>
              <span className="text-sm font-semibold text-slate-800">AI-Powered</span>
            </div>
            <p className="text-[13px] text-slate-600 mt-1.5 leading-relaxed">
              Where rules are unclear, Groq classifies transactions and answers the analyst chat. The AI only reasons over
              retrieved data — it never modifies or overrides engine numbers.
            </p>
          </div>
          <div className="px-5 py-4">
            <div className="flex items-center gap-2">
              <span className="w-6 h-6 rounded-lg bg-emerald-100 text-emerald-700 flex items-center justify-center text-sm">▤</span>
              <span className="text-sm font-semibold text-slate-800">Deterministic Engine</span>
            </div>
            <p className="text-[13px] text-slate-600 mt-1.5 leading-relaxed">
              Every total lives as integer cents in PostgreSQL. P&amp;L, variance and drill-downs are pure Python —
              identical output on every run, auditable transaction by transaction.
            </p>
          </div>
          <div className="px-5 py-4">
            <div className="flex items-center gap-2">
              <span className="w-6 h-6 rounded-lg bg-amber-100 text-amber-700 flex items-center justify-center text-sm">⛁</span>
              <span className="text-sm font-semibold text-slate-800">Human-in-the-loop</span>
            </div>
            <p className="text-[13px] text-slate-600 mt-1.5 leading-relaxed">
              Low-confidence, judgment-heavy, unusual or inconsistent items land in the{" "}
              <Link to="/review-queue" className="text-indigo-600 hover:underline">Review Queue</Link> until a reviewer
              approves, reclassifies or excludes them — decisions are fully audited.
            </p>
          </div>
        </div>
        <div className="px-5 py-3 border-t border-slate-100 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-slate-500">
          <span className="font-medium uppercase tracking-wide text-slate-400">Pipeline</span>
          {["Ingestion & validation", "Deterministic rule classification", "AI assist where unclear", "Review Queue", "Deterministic P&L engine", "Variance & AI Analyst", "Verified reporting"].map((s, i) => (
            <span key={s} className="flex items-center gap-2">
              {i > 0 ? <span className="text-slate-300">→</span> : null}
              <span className="rounded-full bg-slate-100 px-2 py-0.5">{s}</span>
            </span>
          ))}
        </div>
      </section>

      <ImportCard onImported={onImported} />

      {isEmpty ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-6 py-12 text-center">
          <div className="text-sm font-medium text-slate-700">No transactions in the database yet</div>
          <div className="text-xs text-slate-500 mt-1 max-w-lg mx-auto">
            Drop a workbook above (or use "Load sample dataset") to populate the dashboard, P&amp;L, variance analysis
            and the review queue.
          </div>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 xl:grid-cols-5 gap-4">
        <KpiCard label="Revenue" cents={kpis?.revenue?.cents ?? 0} hint={kpis?.revenue?.hint} />
        <KpiCard label="Gross Profit" cents={kpis?.grossProfit.cents ?? 0} hint={kpis?.grossProfit.hint} />
        <KpiCard label="Operating Profit" cents={kpis?.operatingProfit.cents ?? 0} hint={kpis?.operatingProfit.hint} />
        <KpiCard label="Net Cash Flow" cents={kpis?.netCash?.cents ?? 0} hint={kpis?.netCash?.hint} />
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm px-5 py-4 flex flex-col justify-center">
          <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Pending Reviews</div>
          <div className="mt-1.5 flex items-center gap-2">
            <span className="text-2xl font-semibold tabular-nums text-slate-900">{data.stats.pending_review}</span>
            <StateBadge state="pending" />
          </div>
          <div className="mt-0.5 text-xs text-slate-400">of {data.stats.total_transactions} transactions</div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-5 gap-4">
        <Card className="xl:col-span-3">
          <CardHeader title="Monthly trend" subtitle="Revenue, gross profit and operating profit across loaded months" />
          <div className="h-72 px-3 py-4">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trend} margin={{ top: 5, right: 20, bottom: 0, left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="name" tick={{ fontSize: 12 }} tickFormatter={(v: string) => monthLabel(v).slice(0, 3)} />
                <YAxis tick={{ fontSize: 12 }} tickFormatter={(v: number) => `$${Math.round(v / 1000)}k`} width={70} />
                <Tooltip content={<AmountTooltip />} />
                <Line type="monotone" dataKey="Revenue" stroke="#10b981" strokeWidth={2} dot={{ r: 3 }} />
                <Line type="monotone" dataKey="Gross profit" stroke="#6366f1" strokeWidth={2} dot={{ r: 3 }} />
                <Line type="monotone" dataKey="Operating profit" stroke="#f59e0b" strokeWidth={2} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card className="xl:col-span-2">
          <CardHeader
            title={`Expense mix · ${monthLabel(month)}`}
            subtitle="Payroll and operating expenses by category"
            right={
              <Link to="/variance" className="text-xs text-indigo-600 hover:underline">
                variance →
              </Link>
            }
          />
          <div className="h-72 px-4 py-4">
            {expenseMix.length === 0 ? (
              <div className="text-sm text-slate-400">No expenses for this month.</div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={expenseMix} layout="vertical" margin={{ top: 0, right: 20, bottom: 0, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
                  <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(v: number) => `$${Math.round(v / 1000)}k`} />
                  <YAxis type="category" dataKey="name" width={150} tick={{ fontSize: 11 }} />
                  <Tooltip content={<AmountTooltip />} />
                  <Bar dataKey="amount" fill="#6366f1" radius={[0, 4, 4, 0]} barSize={14} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm px-5 py-4">
          <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Transactions</div>
          <div className="mt-1.5 text-2xl font-semibold tabular-nums text-slate-900">{data.stats.total_transactions}</div>
          <div className="mt-0.5 text-xs text-slate-400">in the dataset</div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm px-5 py-4">
          <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Categories in use</div>
          <div className="mt-1.5 text-2xl font-semibold tabular-nums text-slate-900">{data.stats.categories_in_use}</div>
          <div className="mt-0.5 text-xs text-slate-400">with classified transactions</div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm px-5 py-4">
          <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Review queue</div>
          <div className="mt-1.5 text-2xl font-semibold tabular-nums text-slate-900">{data.stats.pending_review}</div>
          <Link to="/review-queue" className="mt-0.5 text-xs text-indigo-600 hover:underline inline-block">
            Resolve classification flags →
          </Link>
        </div>
        </div>
        </>
      )}
    </div>
  );
}