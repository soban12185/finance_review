import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Card, CardHeader } from "../components/Card";
import { MonthSelector, VerificationBadge } from "../components/ui";
import { api } from "../lib/api";
import { formatPercent, money, monthLabel } from "../lib/format";
import type { VarianceDriverReport, VarianceReport } from "../lib/types";

export default function VariancePage() {
  const [searchParams] = useSearchParams();
  const urlMonth = (searchParams.get("month") ?? "").trim();
  const [months, setMonths] = useState<string[]>([]);
  const [monthA, setMonthA] = useState("");
  const [monthB, setMonthB] = useState("");
  const [report, setReport] = useState<VarianceReport | null>(null);
  const [drivers, setDrivers] = useState<Record<string, VarianceDriverReport>>({});
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    api.months().then(setMonths).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!months.length) return;
    if (months.includes(urlMonth)) {
      const a = months[Math.max(0, months.indexOf(urlMonth) - 1)] || urlMonth;
      setMonthA(a);
      setMonthB(urlMonth);
      return;
    }
    if (months.length >= 2) {
      setMonthA(months[months.length - 2]);
      setMonthB(months[months.length - 1]);
    } else {
      setMonthA(months[0]);
      setMonthB(months[0]);
    }
  }, [months, urlMonth]);

  useEffect(() => {
    if (!monthA || !monthB) return;
    api
      .variance(monthA, monthB)
      .then(setReport)
      .catch((e: Error) => setError(e.message));
  }, [monthA, monthB]);

  const loadDrivers = useCallback(
    async (line: string) => {
      try {
        const d = await api.varianceDrivers(monthA, monthB, line);
        setDrivers((cur) => ({ ...cur, [line]: d }));
        setExpanded((cur) => (cur === line ? null : line));
      } catch {
        setExpanded(null);
      }
    },
    [monthA, monthB],
  );

  const sortedLines = useMemo(
    () => (report ? [...report.lines].sort((a, b) => Math.abs(b.absolute_cents) - Math.abs(a.absolute_cents)) : []),
    [report],
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Variance Analysis</h1>
          <p className="text-sm text-slate-500">Month-over-month movements with materiality flags</p>
          <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <VerificationBadge label="Deterministic engine" tone="emerald" />
            <span>
              All movements are computed by the integer-cent engine; AI may only explain them.{" "}
              <Link to="/analyst" className="text-indigo-600 hover:underline">
                Ask the AI Analyst for the story →
              </Link>
            </span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <MonthSelector months={months} value={monthA} onChange={setMonthA} />
          <span className="text-slate-400 text-sm">vs</span>
          <MonthSelector months={months} value={monthB} onChange={setMonthB} />
        </div>
      </div>

      {error ? <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-3">{error}</div> : null}

      {report ? (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {sortedLines.slice(0, 4).map((l) => (
              <SummaryCard key={l.line} line={l} monthA={monthA} monthB={monthB} onClick={() => loadDrivers(l.line)} />
            ))}
          </div>

          <Card>
            <CardHeader
              title="Movement by P&L line"
              subtitle={`${monthLabel(monthA)} vs ${monthLabel(monthB)} · material when ≥${report.materiality?.percent ?? 10}% or ≥$${((report.materiality?.abs_cents ?? 50000) / 100).toLocaleString()}`}
            />
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wide text-slate-500 border-b border-slate-100">
                    <th className="px-5 py-3 font-medium">Line</th>
                    <th className="px-3 py-3 font-medium text-right">{monthLabel(monthA)}</th>
                    <th className="px-3 py-3 font-medium text-right">{monthLabel(monthB)}</th>
                    <th className="px-3 py-3 font-medium text-right">Δ amount</th>
                    <th className="px-3 py-3 font-medium text-right">Δ %</th>
                    <th className="px-5 py-3 font-medium text-right">Material</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedLines.map((l) => (
                    <tr
                      key={l.line}
                      onClick={() => loadDrivers(l.line)}
                      className="border-b border-slate-50 hover:bg-slate-50 cursor-pointer"
                    >
                      <td className="px-5 py-2.5 font-medium text-slate-800">{l.label}</td>
                      <td className="px-3 py-2.5 text-right tabular-nums text-slate-600">{money(l.previous_cents)}</td>
                      <td className="px-3 py-2.5 text-right tabular-nums text-slate-900 font-medium">{money(l.current_cents)}</td>
                      <td className={`px-3 py-2.5 text-right tabular-nums font-semibold ${l.absolute_cents < 0 ? "text-red-600" : "text-emerald-600"}`}>
                        {money(l.absolute_cents)}
                      </td>
                      <td className={`px-3 py-2.5 text-right tabular-nums ${l.percent === null ? "text-slate-400" : l.percent >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                        {formatPercent(l.percent)}
                      </td>
                      <td className="px-5 py-2.5 text-right">
                        {l.material ? (
                          <span className="inline-flex px-2 py-0.5 rounded-full text-xs font-medium bg-orange-50 text-orange-700 ring-1 ring-inset ring-orange-200">
                            material
                          </span>
                        ) : (
                          <span className="text-xs text-slate-400">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {expanded && drivers[expanded] ? (
            <DriverSection report={drivers[expanded]} monthA={monthA} monthB={monthB} onClose={() => setExpanded(null)} />
          ) : null}
        </>
      ) : (
        <div className="text-sm text-slate-500 py-10">Select two months to compare.</div>
      )}
    </div>
  );
}

function SummaryCard({
  line,
  monthA,
  monthB,
  onClick,
}: {
  line: { line: string; label: string; absolute_cents: number; percent: number | null; material: boolean };
  monthA: string;
  monthB: string;
  onClick: () => void;
}) {
  const pos = line.absolute_cents >= 0;
  return (
    <button
      onClick={onClick}
      className={`bg-white rounded-xl border shadow-sm px-5 py-4 text-left transition-transform hover:-translate-y-0.5 ${
        line.material ? "border-orange-200" : "border-slate-200"
      }`}
    >
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{line.label}</div>
      <div className={`mt-1 text-xl font-semibold tabular-nums ${pos ? "text-emerald-600" : "text-red-600"}`}>
        {pos ? "+" : ""}{money(line.absolute_cents)}
      </div>
      <div className="mt-1 text-xs">
        <span className="text-slate-500">{formatPercent(line.percent)}</span>
        {line.material ? (
          <span className="ml-2 inline-flex px-1.5 py-px rounded text-[10px] font-medium bg-orange-100 text-orange-700">material</span>
        ) : null}
      </div>
      <div className="text-[11px] text-slate-400 mt-1">
        {monthA.slice(0, 7)} → {monthB.slice(0, 7)} (click for drivers)
      </div>
    </button>
  );
}

function DriverSection({
  report,
  monthA,
  monthB,
  onClose,
}: {
  report: VarianceDriverReport;
  monthA: string;
  monthB: string;
  onClose: () => void;
}) {
  return (
    <Card>
      <CardHeader
        title={`Drivers · ${report.label}`}
        subtitle={`${monthLabel(monthA)} vs ${monthLabel(monthB)} · line moved ${money(report.line_variance_cents)}`}
        right={
          <button onClick={onClose} className="text-xs text-slate-400 hover:text-slate-600">
            collapse ↑
          </button>
        }
      />
      <div className="divide-y divide-slate-100">
        {report.drivers.length === 0 ? (
          <div className="px-5 py-8 text-center text-sm text-slate-400">No driver-level change detected for this line.</div>
        ) : (
          report.drivers.map((d) => (
            <div key={d.category} className="px-5 py-4">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-sm font-medium text-slate-800">{d.category}</div>
                  <div className="text-xs text-slate-400 mt-0.5 tabular-nums">
                    {money(d.previous_cents)} → {money(d.current_cents)}
                    {d.percent !== null ? ` · ${formatPercent(d.percent)}` : ""}
                  </div>
                </div>
                <div className="text-right">
                  <div className={`text-sm font-semibold tabular-nums ${d.absolute_cents < 0 ? "text-red-600" : "text-emerald-600"}`}>
                    {money(d.absolute_cents)}
                  </div>
                  <div className="text-xs text-slate-400">{d.contribution_percent.toFixed(1)}% of line move</div>
                </div>
              </div>
              {d.transactions.length ? (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {d.transactions.map((t) => (
                    <span
                      key={t.transaction_id}
                      title={`${t.description} · ${t.counterparty} · ${money(t.amount_cents)}`}
                      className="inline-flex items-center gap-1 rounded bg-slate-100 px-2 py-0.5 text-[11px] font-mono text-slate-600"
                    >
                      {t.transaction_id}
                      <span className="text-slate-400 tabular-nums">{money(t.amount_cents)}</span>
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
          ))
        )}
      </div>
      <div className="px-5 py-2.5 border-t border-slate-100 text-[11px] text-slate-400">
        Drivers are traceable: the transaction IDs above are the exact records behind each category movement, pulled from the
        deterministic engine.
      </div>
    </Card>
  );
}