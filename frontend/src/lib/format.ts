const usd = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function money(cents: number): string {
  return usd.format(cents / 100);
}

export function moneyFromAmount(amount: number): string {
  return usd.format(amount);
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}%`;
}

export function formatSignedPercent(value: number | null | undefined): string {
  const base = formatPercent(value);
  return base === "—" ? base : `${base} pts`;
}

export function pnlTypeLabel(pnlType: string | null | undefined): string {
  if (!pnlType) return "Unclassified";
  const map: Record<string, string> = {
    revenue: "Revenue",
    cogs: "COGS",
    payroll: "Payroll",
    operating_expense: "Operating Expense",
    non_pnl: "Non-P&L",
  };
  return map[pnlType] ?? pnlType;
}

export function sourceLabel(source: string | null | undefined): string {
  if (!source) return "—";
  const map: Record<string, string> = { rule: "Rule", llm: "LLM", manual: "Manual" };
  return map[source] ?? source;
}

const REVIEW_SOURCE_LABELS: Record<string, string> = {
  LOW_CONFIDENCE: "Low confidence",
  ACCOUNTING_JUDGMENT: "Accounting judgment",
  UNUSUAL_TRANSACTION: "Unusual amount",
  DATA_INCONSISTENCY: "Data inconsistency",
  HUMAN_REVIEW: "Human review",
};

export function reviewSourceLabel(source: string): string {
  return REVIEW_SOURCE_LABELS[source] ?? source.replace(/_/g, " ").toLowerCase();
}

export function reviewSourceTone(source: string): { badge: string; dot: string } {
  const tones: Record<string, { badge: string; dot: string }> = {
    LOW_CONFIDENCE: {
      badge: "bg-amber-50 text-amber-700 border-amber-200",
      dot: "bg-amber-400",
    },
    ACCOUNTING_JUDGMENT: {
      badge: "bg-violet-50 text-violet-700 border-violet-200",
      dot: "bg-violet-400",
    },
    UNUSUAL_TRANSACTION: {
      badge: "bg-orange-50 text-orange-700 border-orange-200",
      dot: "bg-orange-400",
    },
    DATA_INCONSISTENCY: {
      badge: "bg-rose-50 text-rose-700 border-rose-200",
      dot: "bg-rose-400",
    },
    HUMAN_REVIEW: {
      badge: "bg-sky-50 text-sky-700 border-sky-200",
      dot: "bg-sky-400",
    },
  };
  return tones[source] ?? { badge: "bg-slate-50 text-slate-600 border-slate-200", dot: "bg-slate-400" };
}

export function monthLabel(month: string): string {
  const [y, m] = month.split("-").map(Number);
  const date = new Date(y, (m ?? 1) - 1, 1);
  return date.toLocaleDateString("en-US", { month: "long", year: "numeric" });
}

export function monthShortLabel(month: string): string {
  if (!month) return "";
  const [y, m] = month.split("-").map(Number);
  if (Number.isNaN(y) || Number.isNaN(m)) return "";
  const date = new Date(y, m - 1, 1);
  return date.toLocaleDateString("en-US", { month: "short", year: "numeric" });
}