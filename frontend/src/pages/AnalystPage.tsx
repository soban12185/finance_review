import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { Card } from "../components/Card";
import Markdown from "../components/Markdown";
import { VerificationBadge } from "../components/ui";
import { api } from "../lib/api";
import { money, monthLabel } from "../lib/format";
import type { AnalystEvidence, AnalystResponse, ToolCallRecord } from "../lib/types";

interface Message {
  role: "user" | "assistant";
  content: string;
  response?: AnalystResponse;
}

const SUGGESTIONS = [
  "Why did operating profit change between February and March?",
  "What was our gross profit in March?",
  "What drove the revenue variance in March?",
  "Show me the biggest food inventory purchases this quarter.",
  "How many transactions are still pending review?",
];

type ToolStage = "retrieval" | "deterministic";

const TOOL_META: Record<string, { stage: ToolStage; label: string }> = {
  get_monthly_pnl: { stage: "deterministic", label: "Monthly P&L" },
  compare_months: { stage: "deterministic", label: "Month-over-month compare" },
  get_variance: { stage: "deterministic", label: "Variance" },
  get_variance_drivers: { stage: "deterministic", label: "Variance drivers" },
  get_category_total: { stage: "deterministic", label: "Category total" },
  get_transactions: { stage: "retrieval", label: "Transaction retrieval" },
  get_transaction: { stage: "retrieval", label: "Transaction detail" },
  get_review_items: { stage: "retrieval", label: "Review queue" },
  search_transactions: { stage: "retrieval", label: "Transaction search" },
};

function stageOf(name: string): ToolStage {
  return TOOL_META[name]?.stage ?? "retrieval";
}

function StageBadge({ stage }: { stage: ToolStage }) {
  return stage === "deterministic" ? (
    <span className="inline-flex items-center px-1.5 py-px rounded text-[10px] font-medium bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-200">
      deterministic calc
    </span>
  ) : (
    <span className="inline-flex items-center px-1.5 py-px rounded text-[10px] font-medium bg-sky-50 text-sky-700 ring-1 ring-inset ring-sky-200">
      SQL retrieval
    </span>
  );
}

function FlowStep({ label, active, children }: { label: string; active?: boolean; children?: ReactNode }) {
  return (
    <div className="flex items-center gap-1.5 shrink-0">
      <div
        className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs ring-1 ring-inset ${
          active ? "bg-indigo-50 text-indigo-700 ring-indigo-200 font-medium" : "bg-slate-50 text-slate-600 ring-slate-200"
        }`}
      >
        {label}
      </div>
      {children}
    </div>
  );
}

function PipelineStrip({ response }: { response: AnalystResponse }) {
  const stages = response.pipeline ?? [];
  if (!stages.length) return null;
  return (
    <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
      <FlowStep label="Question" />
      <span className="text-slate-300">→</span>
      <FlowStep label="Tool selection">
        <div className="flex flex-wrap gap-1 max-w-xs">
          {(response.tools_used ?? []).map((t) => (
            <span key={t} className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-mono bg-indigo-50 text-indigo-700 ring-1 ring-inset ring-indigo-200">
              {TOOL_META[t]?.label ?? t}
            </span>
          ))}
        </div>
      </FlowStep>
      <span className="text-slate-300">→</span>
      <FlowStep label={stages.includes("deterministic") ? "Deterministic calculation" : "SQL data retrieval"} active />
      <span className="text-slate-300">→</span>
      <FlowStep label="Evidence" />
      <span className="text-slate-300">→</span>
      <FlowStep label="AI explanation" />
    </div>
  );
}

function EvidencePanel({ evidence }: { evidence: AnalystEvidence }) {
  const navigate = useNavigate();
  const chips = (items: string[]) => (items.length > 7 ? [...items.slice(0, 7), `+${items.length - 7} more`] : items);
  return (
    <div className="rounded-lg border border-indigo-100 bg-indigo-50/40">
      <div className="flex items-center justify-between px-3 py-2 border-b border-indigo-100/70">
        <span className="text-[11px] font-medium uppercase tracking-wide text-indigo-700">Evidence used</span>
        <span className="text-[11px] text-slate-500">
          {evidence.transactions_returned > 0 ? `${evidence.transactions_returned} transaction(s) retrieved` : "No transactions retrieved"}
        </span>
      </div>
      <div className="px-3 py-2 space-y-2">
        {evidence.months?.length ? (
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[11px] text-slate-500 w-16 shrink-0">Months</span>
            {chips(evidence.months).map((m) => (
              <span key={m} className="rounded bg-white px-1.5 py-0.5 text-[11px] text-slate-700 ring-1 ring-inset ring-slate-200">
                {monthLabel(m)}
              </span>
            ))}
          </div>
        ) : null}
        {evidence.transaction_ids?.length ? (
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[11px] text-slate-500 w-16 shrink-0">Transactions</span>
            {chips(evidence.transaction_ids).map((t) =>
              t.startsWith("+") ? (
                <span key={t} className="rounded bg-white px-1.5 py-0.5 text-[11px] text-slate-400">
                  {t}
                </span>
              ) : (
                <button
                  key={t}
                  onClick={() => navigate(`/transactions?search=${t}`)}
                  title="Open this transaction in the Transactions page"
                  className="rounded bg-white px-1.5 py-0.5 text-[11px] font-mono text-indigo-700 ring-1 ring-inset ring-indigo-200 hover:bg-indigo-100"
                >
                  {t}
                </button>
              ),
            )}
          </div>
        ) : null}
        <p className="text-[11px] text-slate-500 pt-1 border-t border-indigo-100/70">
          Evidence is collected only from the tool output actually retrieved in this conversation — never inferred. Every
          number shown here was computed by the backend engine (integer cents).
        </p>
      </div>
    </div>
  );
}

function ToolCallCard({ tc }: { tc: ToolCallRecord }) {
  return (
    <div className="rounded-lg border border-slate-200 overflow-hidden">
      <div className="flex items-center justify-between gap-2 bg-slate-50 px-3 py-2">
        <div className="flex items-center gap-2 min-w-0">
          <StageBadge stage={tc.error ? "retrieval" : stageOf(tc.name)} />
          <span className={`font-mono text-xs truncate ${tc.error ? "text-red-600" : "text-indigo-700"}`}>{tc.name}</span>
          {TOOL_META[tc.name]?.label ? <span className="text-[11px] text-slate-500 hidden sm:inline">{TOOL_META[tc.name].label}</span> : null}
        </div>
        <span className="text-[10px] text-slate-400 font-mono">{JSON.stringify(tc.arguments)}</span>
      </div>
      {tc.error ? (
        <div className="px-3 py-2 text-xs text-red-600 bg-red-50">⛔ {tc.error}</div>
      ) : (
        <ToolResultBody result={tc.result} />
      )}
    </div>
  );
}

function ToolResultBody({ result }: { result: unknown }) {
  const r = (result ?? {}) as Record<string, unknown> & {
    lines?: Record<string, { label?: string; amount_cents?: number; amount?: number }>;
    net_cash_cents?: number;
    transactions?: unknown[];
    items?: unknown[];
    transaction?: Record<string, unknown> | null;
    found?: boolean;
    drivers?: unknown[];
  };

  if (r.lines) {
    const order = ["revenue", "cogs", "gross_profit", "payroll", "operating_expenses", "operating_profit"];
    return (
      <div className="px-3 py-2 space-y-1">
        {order.map((l) => {
          const lt = r.lines?.[l];
          if (!lt) return null;
          return (
            <div key={l} className="flex items-center justify-between text-xs">
              <span className="text-slate-500">{l.replace(/_/g, " ")}</span>
              <span className="tabular-nums font-medium text-slate-800">
                {money(lt.amount_cents ?? Math.round((lt.amount ?? 0) * 100))}
              </span>
            </div>
          );
        })}
        {r.net_cash_cents !== undefined ? (
          <div className="flex items-center justify-between text-xs border-t border-slate-100 mt-1 pt-1">
            <span className="text-slate-500">Net cash</span>
            <span className="tabular-nums font-medium text-slate-800">{money(r.net_cash_cents)}</span>
          </div>
        ) : null}
      </div>
    );
  }

  const txns = r.transactions ?? r.items;
  if (Array.isArray(txns)) {
    return <TransactionRows rows={txns} totalMatching={r.transactions ? txns.length : undefined} />;
  }

  if (Array.isArray(r.drivers)) {
    return (
      <div className="px-3 py-2 space-y-1">
        {r.drivers.slice(0, 8).map((d, i) => {
          const dr = d as Record<string, unknown>;
          return (
            <div key={i} className="flex items-center justify-between text-xs">
              <span className="text-slate-500">{String(dr.category_name ?? dr.category_code ?? "driver")}</span>
              <span className="tabular-nums font-medium text-slate-800">{money(Number(dr.absolute_cents) || 0)}</span>
            </div>
          );
        })}
        {r.drivers.length > 8 ? <div className="text-[11px] text-slate-400">+{r.drivers.length - 8} more drivers</div> : null}
      </div>
    );
  }

  if (r.transaction) {
    const t = r.transaction as Record<string, unknown>;
    return (
      <div className="px-3 py-2 text-xs space-y-0.5">
        <div className="flex justify-between"><span className="text-slate-500">{String(t.transaction_id)}</span><span className="font-medium">{money(Number(t.amount_cents) || 0)}</span></div>
        <div className="text-slate-600 truncate">{String(t.description ?? "")} · {String(t.counterparty ?? "")} · {String(t.category ?? "")}</div>
      </div>
    );
  }

  if (r.found === false) {
    return <div className="px-3 py-2 text-xs text-slate-500">Transaction not found. The analyst was told this and asked to retry or clarify.</div>;
  }

  const text = JSON.stringify(r, null, 1).slice(0, 1600);
  return text && text !== "{}" ? (
    <pre className="px-3 py-2 text-xs text-slate-500 whitespace-pre-wrap max-h-48 overflow-y-auto">{text}</pre>
  ) : (
    <div className="px-3 py-2 text-xs text-slate-500">Empty result.</div>
  );
}

function TransactionRows({ rows, totalMatching }: { rows: unknown[]; totalMatching?: number }) {
  const navigate = useNavigate();
  const visible = rows.slice(0, 5);
  return (
    <div className="px-3 py-2 space-y-1">
      {visible.map((row) => {
        const t = row as Record<string, unknown>;
        return (
          <button
            key={String(t.transaction_id)}
            onClick={() => navigate(`/transactions?search=${String(t.transaction_id)}`)}
            title="Open this transaction in the Transactions page"
            className="w-full flex items-center justify-between gap-2 text-xs hover:bg-indigo-50 rounded px-1 -mx-1"
          >
            <span className="flex items-center gap-2 min-w-0">
              <span className="font-mono text-[11px] text-indigo-700 shrink-0">{String(t.transaction_id)}</span>
              <span className="text-slate-600 truncate">{String(t.description ?? "")}</span>
            </span>
            <span className="tabular-nums font-medium text-slate-800 shrink-0">{money(Number(t.amount_cents) || 0)}</span>
          </button>
        );
      })}
      {rows.length > 5 ? <div className="text-[11px] text-slate-400">+{rows.length - 5} more of {totalMatching ?? rows.length} returned</div> : null}
      {rows.length === 0 ? <div className="text-xs text-slate-500">No matching rows returned.</div> : null}
    </div>
  );
}

export default function AnalystPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [health, setHealth] = useState<{ configured: boolean; model: string } | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.analystHealth().then(setHealth).catch(() => undefined);
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  const ask = async (question: string) => {
    const q = question.trim();
    if (!q || busy) return;
    const history: { role: string; content: string }[] = messages.flatMap((m) =>
      m.role === "assistant" && m.response
        ? [
            { role: "user", content: m.content },
            { role: "assistant", content: m.response.answer },
          ]
        : m.role === "user"
          ? [{ role: "user", content: m.content }]
          : [],
    );
    setMessages((cur) => [...cur, { role: "user", content: q }]);
    setInput("");
    setBusy(true);
    try {
      const resp = await api.analystChat(q, history);
      setMessages((cur) => [...cur, { role: "assistant", content: resp.answer, response: resp }]);
    } catch (e) {
      setMessages((cur) => [...cur, { role: "assistant", content: `Request failed: ${(e as Error).message}` }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-5">
        <h1 className="text-xl font-semibold text-slate-900">AI Financial Analyst</h1>
        <p className="text-sm text-slate-500">
          Retrieves data through controlled tools, reasons only over what they return, then cites its evidence. The LLM
          writes the words — the backend computes every number.
        </p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          {health ? (
            <div className="inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs ring-1 ring-inset ring-slate-200 bg-white">
              <span className={`w-2 h-2 rounded-full ${health.configured ? "bg-emerald-500" : "bg-amber-400"}`} />
              {health.configured ? (
                <span className="text-emerald-700">LLM connected ({health.model})</span>
              ) : (
                <span className="text-amber-700">LLM not configured (set GROQ_API_KEY) — the rest of the app still works</span>
              )}
            </div>
          ) : null}
          <VerificationBadge label="Deterministic engine is the number source" tone="emerald" />
          <VerificationBadge label="Read-only tools" />
        </div>
      </div>

      <Card>
        <div className="h-[520px] overflow-y-auto px-5 py-4 space-y-4">
          {messages.length === 0 ? (
            <div>
              <p className="text-sm text-slate-500 mb-3">Try one of these:</p>
              <div className="flex flex-wrap gap-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => ask(s)}
                    className="rounded-full border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-600 hover:border-indigo-400 hover:text-indigo-700"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((m, i) =>
              m.role === "user" ? (
                <div key={i} className="flex justify-end">
                  <div className="max-w-[75%] rounded-2xl rounded-br-md bg-indigo-600 text-white px-4 py-2.5 text-sm">{m.content}</div>
                </div>
              ) : (
                <div key={i} className="space-y-2">
                  {m.response?.pipeline?.length ? (
                    <div className="max-w-[94%]">
                      <PipelineStrip response={m.response} />
                    </div>
                  ) : null}
                  <div className="max-w-[88%] rounded-2xl rounded-bl-md bg-white px-4 py-2.5 ring-1 ring-slate-200 shadow-sm">
                    <Markdown>{m.content}</Markdown>
                  </div>
                  {m.response?.evidence && (m.response.evidence.months?.length || m.response.evidence.transaction_ids?.length) ? (
                    <div className="max-w-[90%]">
                      <EvidencePanel evidence={m.response.evidence} />
                    </div>
                  ) : null}
                  {m.response?.tool_calls?.length ? (
                    <div className="max-w-[90%] space-y-2 pl-2">
                      <div className="text-[11px] uppercase tracking-wide text-slate-400">Tool evidence (raw retrieval detail)</div>
                      {m.response.tool_calls.map((tc, j) => (
                        <ToolCallCard key={j} tc={tc} />
                      ))}
                    </div>
                  ) : null}
                  {m.response?.error ? (
                    <div className="max-w-[85%] rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-700">
                      {m.response.error}
                    </div>
                  ) : null}
                </div>
              ),
            )
          )}
          {busy ? (
            <div className="flex items-center gap-2 text-xs text-slate-400">
              <span className="w-3 h-3 border-2 border-slate-300 border-t-indigo-600 rounded-full animate-spin" />
              Selecting tools, retrieving from PostgreSQL, and computing through the engine…
            </div>
          ) : null}
          <div ref={bottomRef} />
        </div>
        <div className="flex items-center gap-2 border-t border-slate-100 px-4 py-3">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") ask(input);
            }}
            placeholder="Ask about the P&L, variance, transactions, or review queue…"
            className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
          <button
            onClick={() => ask(input)}
            disabled={busy || !input.trim()}
            className="rounded-lg bg-slate-900 hover:bg-slate-800 text-white text-sm font-medium px-4 py-2 disabled:opacity-40"
          >
            Ask
          </button>
        </div>
      </Card>

      <p className="text-xs text-slate-400 mt-3">
        Every tool result shown above was produced by the backend from classified transaction data (integer cents). The LLM
        only shapes the wording and selects which tools to call; it never computes or invents figures.
      </p>
    </div>
  );
}