import { useCallback, useEffect, useMemo, useState } from "react";
import { Card, CardHeader } from "../components/Card";
import { PnlTypeBadge, StateBadge } from "../components/ui";
import { api } from "../lib/api";
import { money, pnlTypeLabel, reviewSourceLabel, reviewSourceTone, sourceLabel } from "../lib/format";
import type { Category, ReviewItem } from "../lib/types";

const TABS = [
  { key: "pending", label: "Pending" },
  { key: "approved", label: "Approved" },
  { key: "corrected", label: "Corrected" },
  { key: "marked_non_pnl", label: "Non-P&L" },
];

export default function ReviewQueuePage() {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [total, setTotal] = useState(0);
  const [tab, setTab] = useState("pending");
  const [categories, setCategories] = useState<Category[]>([]);
  const [nonPnl, setNonPnl] = useState<{ code: string; name: string }[]>([]);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    api.categories().then(setCategories).catch(() => undefined);
    api.nonPnlCategories().then(setNonPnl).catch(() => undefined);
  }, []);

  useEffect(() => {
    api
      .reviews(tab === "pending" ? undefined : tab)
      .then((d) => {
        setItems(d.items);
        setTotal(d.total);
      })
      .catch((e: Error) => setError(e.message));
  }, [tab, refresh]);

  const rerun = useCallback(() => setRefresh((n) => n + 1), []);

  const pnlOptions = useMemo(() => categories.filter((c) => c.pnl_type !== "non_pnl"), [categories]);

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Review Queue</h1>
          <p className="text-sm text-slate-500">
            Low confidence, judgment, unusual or inconsistent transactions surface here with the exact reason they were
            flagged, and P&L figures only update once a decision is made
          </p>
        </div>
        <div className="flex items-center gap-1 bg-white rounded-lg border border-slate-200 p-1 text-sm">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-3 py-1.5 rounded-md ${tab === t.key ? "bg-slate-900 text-white" : "text-slate-500 hover:text-slate-800"}`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {error ? <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-3">{error}</div> : null}

      <Card>
        <CardHeader title={`${total} review item(s)`} subtitle={`Viewing: ${tab === "pending" ? "all statuses below" : TABS.find((t) => t.key === tab)?.label}`} />
        <div className="divide-y divide-slate-100">
          {items.length === 0 ? (
            <div className="px-5 py-12 text-center text-sm text-slate-400">
              Nothing here. Flagged transactions appear when confidence is low or the item is non-P&L.
            </div>
          ) : (
            items.map((it) => (
              <ReviewRow
                key={it.id}
                item={it}
                pnlOptions={pnlOptions}
                nonPnl={nonPnl}
                busy={busyId === it.id}
                onBusy={(b) => setBusyId(b ? it.id : null)}
                onDone={rerun}
              />
            ))
          )}
        </div>
      </Card>

      {tab === "pending" ? (
        <div className="text-xs text-slate-400">
          Pending tab shows items of any status until a decision has been made on all items from the dataset. Switch tabs to
          see resolved decisions.
        </div>
      ) : null}
    </div>
  );
}

function ReviewRow({
  item,
  pnlOptions,
  nonPnl,
  busy,
  onBusy,
  onDone,
}: {
  item: ReviewItem;
  pnlOptions: Category[];
  nonPnl: { code: string; name: string }[];
  busy: boolean;
  onBusy: (b: boolean) => void;
  onDone: () => void;
}) {
  const [mode, setMode] = useState<"" | "reclassify" | "nonpnl">("");
  const [categoryCode, setCategoryCode] = useState("");
  const [note, setNote] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    if (!item.decided && mode !== "") {
      setCategoryCode(item.submitted.category_code ?? "");
    }
  }, [mode, item]);

  const run = async (action: string, payload: { category_code?: string }) => {
    setActionError(null);
    onBusy(true);
    try {
      await api.resolveReview(item.id, { action, note: note || undefined, actor: "Reviewer (demo)", ...payload });
      onDone();
    } catch (e) {
      setActionError((e as Error).message);
      onBusy(false);
    }
  };

  const isPending = item.status === "pending";

  return (
    <div className="px-5 py-4">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <StateBadge state={item.status} />
            <span className="font-mono text-xs text-slate-500">{item.transaction_id}</span>
            <span className="text-xs text-slate-400 tabular-nums">{item.date.slice(0, 10)}</span>
          </div>
          <div className="mt-1 text-sm font-medium text-slate-800">{item.description}</div>
          <div className="text-xs text-slate-500">
            {item.counterparty} · {item.method}
          </div>
        </div>
        <div className="text-right shrink-0">
          <div className={`text-base font-semibold tabular-nums ${item.amount_cents < 0 ? "text-red-600" : "text-slate-900"}`}>
            {money(item.amount_cents)}
          </div>
          <div className="text-xs text-slate-400 mt-0.5">flagged at {Math.round((item.submitted.confidence ?? 0) * 100)}%</div>
        </div>
      </div>

      <div className="mt-3 flex items-center gap-6 text-xs">
        <div className="flex items-center gap-1.5">
          <span className="text-slate-400">Submitted:</span>
          <span className="font-medium text-slate-700">{item.submitted.category_name ?? "—"}</span>
          <PnlTypeBadge type={item.submitted.pnl_type} />
          <span className="text-slate-400">({sourceLabel(item.submitted.source)})</span>
        </div>
        {item.current_classification ? (
          <div className="flex items-center gap-1.5">
            <span className="text-slate-400">Current:</span>
            <span className="font-medium text-slate-700">{item.current_classification.category_name}</span>
          </div>
        ) : null}
      </div>

      {item.submitted.reasoning ? (
        <div className="mt-2 text-xs text-slate-500 bg-slate-50 rounded-lg px-3 py-2">{item.submitted.reasoning}</div>
      ) : null}

      {item.review_sources.length > 0 ? (
        <div className="mt-2 rounded-lg border border-slate-200 bg-white px-3 py-2.5">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Why it was flagged</div>
          <ul className="mt-1.5 space-y-1.5">
            {item.review_sources.map((src) => {
              const idx = item.review_sources.indexOf(src);
              const tone = reviewSourceTone(src);
              return (
                <li key={src} className="flex items-start gap-2 text-xs text-slate-600">
                  <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${tone.dot}`} />
                  <span className={`shrink-0 rounded border px-1.5 py-px text-[10px] font-medium ${tone.badge}`}>
                    {reviewSourceLabel(src)}
                  </span>
                  <span>{item.review_reasons[idx] ?? src}</span>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}

      {item.suggested_action === "mark_non_pnl" ? (
        <div className="mt-2 text-xs text-violet-700">
          System suggests confirming this belongs outside the P&L (balance sheet / financing / equity).
        </div>
      ) : null}

      {item.decided ? (
        <div className="mt-3 flex items-center gap-2 rounded-lg bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
          Resolved by {item.reviewed_by ?? "system"} →
          <span className="font-medium">{item.decided.category_name}</span>
          <PnlTypeBadge type={item.decided.pnl_type} />
          {item.note ? <span className="text-emerald-600">· “{item.note}”</span> : null}
          {item.resolved_at ? (
            <span className="text-emerald-500 tabular-nums">{item.resolved_at.slice(0, 16).replace("T", " at ")}</span>
          ) : null}
        </div>
      ) : null}

      {actionError ? <div className="mt-2 text-xs text-red-600">{actionError}</div> : null}

      {isPending && !busy ? (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button
            onClick={() => run("approve", {})}
            className="rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-medium px-3 py-1.5"
          >
            Approve
          </button>
          <button
            onClick={() => setMode(mode === "reclassify" ? "" : "reclassify")}
            className="rounded-lg border border-slate-300 hover:bg-slate-50 text-xs font-medium px-3 py-1.5 text-slate-700"
          >
            Reclassify
          </button>
          <button
            onClick={() => setMode(mode === "nonpnl" ? "" : "nonpnl")}
            className="rounded-lg border border-slate-300 hover:bg-slate-50 text-xs font-medium px-3 py-1.5 text-slate-700"
          >
            Mark non-P&L
          </button>
        </div>
      ) : null}

      {isPending && busy ? <div className="mt-3 text-xs text-slate-400">Applying…</div> : null}

      {isPending && !busy && mode ? (
        <div className="mt-3 rounded-lg border border-indigo-100 bg-indigo-50/60 p-3 space-y-2">
          <div className="text-xs font-medium text-indigo-800">
            {mode === "reclassify" ? "Reclassify this transaction" : "Assign a non-P&L category"}
          </div>
          <select
            value={categoryCode}
            onChange={(e) => setCategoryCode(e.target.value)}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs w-full max-w-sm"
          >
            <option value="">Choose a category…</option>
            {(mode === "reclassify" ? pnlOptions : nonPnl).map((c) => (
              <option key={c.code} value={c.code}>
                {c.name} {mode === "reclassify" ? `· ${pnlTypeLabel((c as Category).pnl_type)}` : `· ${(c as { name: string }).name}`}
              </option>
            ))}
          </select>
          <div className="flex items-center gap-2">
            <input
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Optional note for the audit trail"
              className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs flex-1 max-w-sm"
            />
            <button
              disabled={!categoryCode}
              onClick={() =>
                run(mode === "reclassify" ? "change_classification" : "mark_non_pnl", { category_code: categoryCode })
              }
              className="rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-medium px-3 py-1.5 disabled:opacity-40"
            >
              Apply
            </button>
            <button onClick={() => setMode("")} className="text-xs text-slate-500 hover:text-slate-700">
              Cancel
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}