import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { Card } from "../components/Card";
import { PnlTypeBadge, SourceBadge, StateBadge } from "../components/ui";
import { api } from "../lib/api";
import { money, monthLabel, sourceLabel } from "../lib/format";
import type { Transaction, TransactionPage } from "../lib/types";

const PAGE_SIZE = 50;

export default function TransactionsPage() {
  const [searchParams] = useSearchParams();
  const [data, setData] = useState<TransactionPage | null>(null);
  const [meta, setMeta] = useState<{ months: string[]; categories: { category_code: string; category_name: string; count: number }[]; methods: string[] }>({ months: [], categories: [], methods: [] });
  const [filters, setFilters] = useState({
    month: "",
    category: "",
    pnl_type: "",
    review_status: "",
    search: searchParams.get("search") ?? "",
    method: "",
  });
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Transaction | null>(null);

  useEffect(() => {
    api.meta().then(setMeta).catch(() => undefined);
  }, []);

  useEffect(() => {
    api
      .transactions({ ...filters, limit: PAGE_SIZE, offset })
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, [filters, offset]);

  const set = useCallback((key: keyof typeof filters, value: string) => {
    setOffset(0);
    setFilters((f) => ({ ...f, [key]: value }));
  }, []);

  const openDetail = useCallback((t: Transaction) => setSelected(t), []);

  const total = data?.total ?? 0;
  const pages = useMemo(() => Math.max(1, Math.ceil(total / PAGE_SIZE)), [total]);
  const pageIndex = Math.floor(offset / PAGE_SIZE);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Transactions</h1>
        <p className="text-sm text-slate-500">
          {total.toLocaleString()} classified transactions · hybrid pipeline — deterministic rules first, LLM only when rules are unclear
        </p>
      </div>

      <Card>
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3 px-5 py-4 border-b border-slate-100">
          <input
            value={filters.search}
            onChange={(e) => set("search", e.target.value)}
            placeholder="Search description / counterparty"
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
          <select value={filters.month} onChange={(e) => set("month", e.target.value)} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm">
            <option value="">All months</option>
            {meta.months.map((m) => (
              <option key={m} value={m}>
                {monthLabel(m)}
              </option>
            ))}
          </select>
          <select value={filters.category} onChange={(e) => set("category", e.target.value)} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm">
            <option value="">All categories</option>
            {meta.categories.map((c) => (
              <option key={c.category_code} value={c.category_code}>
                {c.category_name} ({c.count})
              </option>
            ))}
          </select>
          <select value={filters.pnl_type} onChange={(e) => set("pnl_type", e.target.value)} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm">
            <option value="">All P&L types</option>
            <option value="revenue">Revenue</option>
            <option value="cogs">COGS</option>
            <option value="payroll">Payroll</option>
            <option value="operating_expense">Operating expense</option>
            <option value="non_pnl">Non-P&L</option>
          </select>
          <select value={filters.review_status} onChange={(e) => set("review_status", e.target.value)} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm">
            <option value="">Any review status</option>
            <option value="none">None</option>
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
            <option value="corrected">Corrected</option>
            <option value="marked_non_pnl">Marked non-P&L</option>
          </select>
          <select value={filters.method} onChange={(e) => set("method", e.target.value)} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm">
            <option value="">All methods</option>
            {meta.methods.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-slate-500 border-b border-slate-100">
                <th className="px-5 py-3 font-medium">Date</th>
                <th className="px-3 py-3 font-medium">Transaction ID</th>
                <th className="px-3 py-3 font-medium">Description</th>
                <th className="px-3 py-3 font-medium">Counterparty</th>
                <th className="px-3 py-3 font-medium">Amount</th>
                <th className="px-3 py-3 font-medium">Category</th>
                <th className="px-3 py-3 font-medium">Confidence</th>
                <th className="px-5 py-3 font-medium text-right">Status</th>
              </tr>
            </thead>
            <tbody>
              {(data?.transactions ?? []).map((t) => (
                <tr
                  key={t.id}
                  onClick={() => openDetail(t)}
                  className="border-b border-slate-50 hover:bg-slate-50 cursor-pointer"
                >
                  <td className="px-5 py-2.5 text-slate-600 tabular-nums whitespace-nowrap">{t.date.slice(0, 10)}</td>
                  <td className="px-3 py-2.5 font-mono text-xs text-slate-500">{t.transaction_id}</td>
                  <td className="px-3 py-2.5 max-w-xs truncate text-slate-800">{t.description}</td>
                  <td className="px-3 py-2.5 text-slate-600">{t.counterparty}</td>
                  <td className={`px-3 py-2.5 tabular-nums font-medium ${t.amount_cents < 0 ? "text-red-600" : "text-slate-900"}`}>
                    {money(t.amount_cents)}
                  </td>
                  <td className="px-3 py-2.5">
                    <div className="flex flex-col gap-0.5">
                      <span className="text-slate-800">{t.classification?.category_name ?? "unclassified"}</span>
                      <span className="flex items-center gap-1">
                        <PnlTypeBadge type={t.classification?.pnl_type} />
                        <SourceBadge source={t.classification?.source} />
                      </span>
                    </div>
                  </td>
                  <td className="px-3 py-2.5 tabular-nums text-slate-600">
                    <div className="flex flex-col gap-0.5">
                      <span>{t.classification ? `${Math.round(t.classification.confidence * 100)}%` : "—"}</span>
                      {t.classification?.requires_review ? (
                        <span className="text-[10px] text-orange-600">review flagged</span>
                      ) : null}
                    </div>
                  </td>
                  <td className="px-5 py-2.5 text-right">
                    <StateBadge state={t.classification?.review_status ?? "none"} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between px-5 py-3 border-t border-slate-100 text-sm text-slate-500">
          <span>
            Showing {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total.toLocaleString()}
          </span>
          <div className="flex items-center gap-2">
            <button
              disabled={pageIndex === 0}
              onClick={() => setOffset((offset) => Math.max(0, offset - PAGE_SIZE))}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs disabled:opacity-40 hover:bg-slate-50"
            >
              ← Prev
            </button>
            <span className="text-xs">
              Page {pageIndex + 1} / {pages}
            </span>
            <button
              disabled={offset + PAGE_SIZE >= total}
              onClick={() => setOffset((offset) => offset + PAGE_SIZE)}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs disabled:opacity-40 hover:bg-slate-50"
            >
              Next →
            </button>
          </div>
        </div>
        {error ? <div className="px-5 py-2 text-xs text-red-600">{error}</div> : null}
      </Card>

      {selected ? (
        <div className="fixed inset-0 z-10" onClick={() => setSelected(null)}>
          <div className="absolute inset-0 bg-slate-900/40" />
          <div
            className="absolute right-0 inset-y-0 w-[480px] bg-white shadow-2xl overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <TransactionDetail txn={selected} onClose={() => setSelected(null)} />
          </div>
        </div>
      ) : null}
    </div>
  );
}

function TransactionDetail({ txn, onClose }: { txn: Transaction; onClose: () => void }) {
  const [detail, setDetail] = useState<{ review_items: unknown[] } | null>(null);
  useEffect(() => {
    api
      .transaction(txn.transaction_id)
      .then((d: unknown) => setDetail(d as { review_items: unknown[] }))
      .catch(() => undefined);
  }, [txn.transaction_id]);

  const c = txn.classification;

  return (
    <div>
      <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 sticky top-0 bg-white">
        <div>
          <div className="font-mono text-xs text-slate-500">{txn.transaction_id}</div>
          <div className="text-base font-semibold text-slate-900">{txn.description}</div>
        </div>
        <button onClick={onClose} className="text-slate-400 hover:text-slate-600 text-xl leading-none px-1">
          ×
        </button>
      </div>
      <div className="px-5 py-4 space-y-5">
        <div className="grid grid-cols-2 gap-3 text-sm">
          <Meta label="Date" value={txn.date} />
          <Meta label="Counterparty" value={txn.counterparty} />
          <Meta label="Method" value={txn.method} />
          <Meta label="Raw amount" value={txn.raw_amount} />
          <Meta label="Amount" value={money(txn.amount_cents)} />
          <Meta label="Review status" node={<StateBadge state={c?.review_status ?? "none"} />} />
        </div>

        <div>
          <div className="text-xs font-medium uppercase tracking-wide text-slate-500 mb-2">Classification</div>
          {c ? (
            <div className="rounded-xl border border-slate-200 divide-y divide-slate-100">
              <Row k="Category" v={`${c.category_name} (${c.category_code})`} />
              <Row k="P&L type" v={<PnlTypeBadge type={c.pnl_type} />} />
              <Row k="Accounting treatment" v={c.accounting_treatment} />
              <Row
                k="Confidence"
                v={`${Math.round(c.confidence * 100)}%${c.confidence < 0.92 ? " · flagged for review" : ""}`}
              />
              <Row k="Source" v={sourceLabel(c.source)} />
              <Row k="Version" v={String(c.version)} />
              <div className="px-4 py-3">
                <div className="text-xs text-slate-400 mb-1">Reasoning</div>
                <div className="text-sm text-slate-700">{c.reasoning}</div>
              </div>
            </div>
          ) : (
            <div className="text-sm text-slate-400">Not classified.</div>
          )}
        </div>

        <div>
          <div className="text-xs font-medium uppercase tracking-wide text-slate-500 mb-2">Raw record</div>
          <pre className="text-xs bg-slate-50 rounded-lg p-3 text-slate-600 overflow-x-auto">
            {JSON.stringify(
              {
                transaction_id: txn.transaction_id,
                date: txn.date,
                description: txn.description,
                counterparty: txn.counterparty,
                amount: txn.raw_amount,
                method: txn.method,
              },
              null,
              2,
            )}
          </pre>
        </div>

        {detail?.review_items?.length ? (
          <div>
            <div className="text-xs font-medium uppercase tracking-wide text-slate-500 mb-2">Review history</div>
            <div className="text-xs text-slate-600">{detail.review_items.length} review event(s)</div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function Meta({ label, value, node }: { label: string; value?: string; node?: ReactNode }) {
  return (
    <div>
      <div className="text-xs text-slate-400">{label}</div>
      {value !== undefined ? <div className="text-slate-800">{value}</div> : node}
    </div>
  );
}

function Row({ k, v }: { k: string; v: ReactNode }) {
  return (
    <div className="px-4 py-2.5 flex items-center justify-between">
      <span className="text-xs text-slate-400">{k}</span>
      <span className="text-sm text-slate-800">{v}</span>
    </div>
  );
}