import { monthLabel, money } from "../lib/format";

export function KpiCard({
  label,
  cents,
  hint,
}: {
  label: string;
  cents: number;
  hint?: string;
  positiveIsGood?: boolean;
}) {
  const negative = cents < 0;
  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm px-5 py-4">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`mt-1.5 text-2xl font-semibold tabular-nums ${negative ? "text-red-600" : "text-slate-900"}`}>
        {money(cents)}
      </div>
      {hint ? <div className="mt-0.5 text-xs text-slate-400">{hint}</div> : null}
    </div>
  );
}

export function MonthSelector({
  months,
  value,
  onChange,
}: {
  months: string[];
  value: string;
  onChange: (m: string) => void;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
    >
      {months.map((m) => (
        <option key={m} value={m}>
          {monthLabel(m)}
        </option>
      ))}
    </select>
  );
}

export function MonthPairSelector({
  months,
  valueA,
  valueB,
  onChangeA,
  onChangeB,
}: {
  months: string[];
  valueA: string;
  valueB: string;
  onChangeA: (m: string) => void;
  onChangeB: (m: string) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <MonthSelector months={months} value={valueA} onChange={onChangeA} />
      <span className="text-slate-400 text-sm">vs</span>
      <MonthSelector months={months} value={valueB} onChange={onChangeB} />
    </div>
  );
}

export function SourceBadge({ source, className = "" }: { source: string | null | undefined; className?: string }) {
  const s = source ?? "none";
  const label = s === "llm" || s === "ai" ? "AI" : s === "manual" ? "Manual" : s === "rule" ? "Rule" : s === "none" ? "Unclassified" : s;
  const color =
    s === "llm" || s === "ai"
      ? "bg-violet-50 text-violet-700 ring-violet-200"
      : s === "manual"
        ? "bg-sky-50 text-sky-700 ring-sky-200"
        : s === "rule"
          ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
          : "bg-slate-100 text-slate-500 ring-slate-200";
  return (
    <span className={`inline-flex items-center px-1.5 py-px rounded text-[10px] font-medium ring-1 ring-inset ${color} ${className}`}>
      {label}
    </span>
  );
}

export function VerificationBadge({ label, tone = "slate", className = "" }: { label: string; tone?: "slate" | "emerald" | "indigo" | "amber"; className?: string }) {
  const tones = {
    slate: "bg-slate-50 text-slate-600 ring-slate-200",
    emerald: "bg-emerald-50 text-emerald-700 ring-emerald-200",
    indigo: "bg-indigo-50 text-indigo-700 ring-indigo-200",
    amber: "bg-amber-50 text-amber-700 ring-amber-200",
  };
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${tones[tone]} ${className}`}>
      <span className="w-1.5 h-1.5 rounded-full bg-current opacity-70" />
      {label}
    </span>
  );
}

export function StateBadge({ state, className = "" }: { state: string; className?: string }) {
  const color =
    state === "approved"
      ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
      : state === "corrected" || state === "mark_non_pnl" || state === "marked_non_pnl"
        ? "bg-amber-50 text-amber-700 ring-amber-200"
        : state === "pending" || state === "needs_review"
          ? "bg-orange-50 text-orange-700 ring-orange-200"
          : "bg-slate-100 text-slate-600 ring-slate-200";
  const label = state === "mark_non_pnl" ? "non-P&L" : state.replace("_", " ");
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ring-1 ring-inset ${color} ${className}`}
    >
      {label}
    </span>
  );
}

export function PnlTypeBadge({ type }: { type: string | null | undefined }) {
  if (!type) return <span className="text-xs text-slate-400">unclassified</span>;
  const color =
    type === "revenue"
      ? "bg-emerald-50 text-emerald-700"
      : type === "cogs" || type === "payroll" || type === "operating_expense"
        ? "bg-sky-50 text-sky-700"
        : "bg-violet-50 text-violet-700";
  const label =
    type === "revenue"
      ? "Revenue"
      : type === "cogs"
        ? "COGS"
        : type === "payroll"
          ? "Payroll"
          : type === "operating_expense"
            ? "OpEx"
            : "Non-P&L";
  return <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${color}`}>{label}</span>;
}