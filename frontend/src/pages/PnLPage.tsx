import { useCallback, useEffect, useState } from "react";
import { Card, CardHeader } from "../components/Card";
import { KpiCard, MonthSelector, VerificationBadge } from "../components/ui";
import { api } from "../lib/api";
import { money, monthLabel } from "../lib/format";
import type { PnlDrilldown, PnlReport } from "../lib/types";

export default function PnLPage() {
  const [months, setMonths] = useState<string[]>([]);
  const [month, setMonth] = useState("");
  const [report, setReport] = useState<PnlReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [drill, setDrill] = useState<PnlDrilldown | null>(null);

  useEffect(() => {
    api.months().then(setMonths).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (months.length && !month) setMonth(months[months.length - 1]);
  }, [months, month]);

  useEffect(() => {
    if (!month) return;
    api
      .pnl(month)
      .then(setReport)
      .catch((e: Error) => setError(e.message));
  }, [month]);

  const lines = report?.lines ?? {};
  const order = ["revenue", "cogs", "gross_profit", "payroll", "operating_expenses", "operating_profit"];
  const computed = new Set(["gross_profit", "operating_profit"]);

  const openDrill = useCallback(async (line: string) => {
    if (!month || computed.has(line)) return;
    try {
      setDrill(await api.drilldown(month, line));
    } catch {
      setDrill(null);
    }
  }, [month, computed]);

  const revenue = lines["revenue"]?.amount_cents ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Profit &amp; Loss</h1>
          <p className="text-sm text-slate-500">Deterministic P&amp;L built from classified transactions</p>
          <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <VerificationBadge label="Integer-cent engine" tone="emerald" />
            <span>Every figure and drill-down is computed deterministically from classified rows — no AI involvement.</span>
          </div>
        </div>
        <MonthSelector months={months} value={month} onChange={setMonth} />
      </div>

      {error ? <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-3">{error}</div> : null}

      {report ? (
        <>
          <div className="grid grid-cols-3 gap-4">
            <KpiCard label="Gross profit margin" cents={(lines["gross_profit"]?.amount_cents ?? 0) * (10000 / Math.max(1, Math.abs(revenue)))} hint="Gross ÷ revenue (%)" />
            <KpiCard label="Operating margin" cents={(lines["operating_profit"]?.amount_cents ?? 0) * (10000 / Math.max(1, Math.abs(revenue)))} hint="Operating ÷ revenue (%)" />
            <KpiCard label="Net cash flow" cents={report.net_cash_cents} hint="All signed transaction activity" />
          </div>

          <Card>
            <CardHeader
              title={`P&L statement · ${monthLabel(month)}`}
              subtitle="Computed lines are derived; click a sourced line to drill down into transactions"
            />
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wide text-slate-500 border-b border-slate-100">
                  <th className="px-5 py-3 font-medium">Line</th>
                  <th className="px-3 py-3 font-medium text-right">Amount</th>
                  <th className="px-3 py-3 font-medium text-right">Transactions</th>
                  <th className="px-5 py-3 font-medium text-right">Categories</th>
                </tr>
              </thead>
              <tbody>
                {order.map((line) => {
                  const lt = lines[line];
                  if (!lt) return null;
                  const isComputed = computed.has(line);
                  const isTotal = line === "gross_profit" || line === "operating_profit";
                  return (
                    <tr
                      key={line}
                      className={`border-b border-slate-50 ${isTotal ? "bg-slate-50" : "hover:bg-slate-50 cursor-pointer"}`}
                      onClick={() => openDrill(line)}
                    >
                      <td className="px-5 py-2.5">
                        <div className={`font-medium ${isComputed ? "text-slate-900" : "text-slate-700"}`}>
                          {lt.label}
                          {isComputed ? <span className="ml-2 text-[10px] uppercase text-slate-400 ring-1 ring-slate-200 rounded px-1 py-px">computed</span> : null}
                        </div>
                        {isComputed ? <div className="text-[11px] text-slate-400 mt-0.5">derived from the lines above</div> : null}
                      </td>
                      <td className={`px-3 py-2.5 text-right tabular-nums font-semibold ${lt.amount_cents < 0 ? "text-red-600" : "text-slate-900"}`}>
                        {money(lt.amount_cents)}
                      </td>
                      <td className="px-3 py-2.5 text-right tabular-nums text-slate-500">{lt.transaction_count}</td>
                      <td className="px-5 py-2.5 text-right text-slate-500">{lt.categories.length}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </Card>

          <Card>
            <CardHeader title="Line breakdown" subtitle={`Where each amount comes from in ${monthLabel(month)}`} />
            <div className="px-5 py-4 grid grid-cols-1 lg:grid-cols-2 gap-4">
              {order.map((line) => {
                const lt = lines[line];
                if (!lt || computed.has(line)) return null;
                return (
                  <div key={line} className="rounded-lg border border-slate-200 p-4">
                    <div className="flex items-center justify-between">
                      <div className="text-sm font-medium text-slate-800">{lt.label}</div>
                      <div className="text-sm font-semibold tabular-nums">{money(lt.amount_cents)}</div>
                    </div>
                    <div className="mt-2 space-y-1">
                      {lt.categories.map((c) => (
                        <div key={c.category_code} className="flex items-center justify-between text-xs text-slate-600">
                          <span>{c.category_name}</span>
                          <span className="tabular-nums">{money(c.amount_cents)}</span>
                        </div>
                      ))}
                      {lt.categories.length === 0 ? <div className="text-xs text-slate-400">No direct transactions.</div> : null}
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>
        </>
      ) : null}

      {drill ? (
        <div className="fixed inset-0 z-10" onClick={() => setDrill(null)}>
          <div className="absolute inset-0 bg-slate-900/40" />
          <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[720px] max-h-[80vh] bg-white rounded-xl shadow-2xl overflow-hidden flex flex-col" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
              <div>
                <div className="text-base font-semibold text-slate-900">{drill.label}</div>
                <div className="text-xs text-slate-500">
                  {monthLabel(drill.month)} · {money(drill.amount_cents)}
                </div>
              </div>
              <button onClick={() => setDrill(null)} className="text-slate-400 hover:text-slate-600 text-xl leading-none px-1">×</button>
            </div>
            {drill.computed && drill.components.length ? (
              <div className="px-5 py-3 border-b border-slate-100 text-xs">
                {drill.components.map((c) => (
                  <span key={c.line} className="mr-3 text-slate-600">
                    {c.label}: <span className="tabular-nums font-medium">{money(c.amount_cents)}</span>
                  </span>
                ))}
              </div>
            ) : null}
            <div className="overflow-y-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wide text-slate-500 border-b border-slate-100">
                    <th className="px-5 py-2.5 font-medium">Date</th>
                    <th className="px-3 py-2.5 font-medium">ID</th>
                    <th className="px-3 py-2.5 font-medium">Description</th>
                    <th className="px-3 py-2.5 font-medium">Counterparty</th>
                    <th className="px-5 py-2.5 font-medium text-right">Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {(drill.transactions ?? []).map((t) => (
                    <tr key={t.transaction_id} className="border-b border-slate-50">
                      <td className="px-5 py-2 text-slate-600 tabular-nums whitespace-nowrap">{t.date}</td>
                      <td className="px-3 py-2 font-mono text-xs text-slate-500">{t.transaction_id}</td>
                      <td className="px-3 py-2 text-slate-800">{t.description}</td>
                      <td className="px-3 py-2 text-slate-600">{t.counterparty}</td>
                      <td className={`px-5 py-2 text-right tabular-nums font-medium ${t.amount_cents < 0 ? "text-red-600" : "text-slate-900"}`}>
                        {money(t.amount_cents)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}