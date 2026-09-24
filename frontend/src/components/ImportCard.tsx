import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Card, CardHeader } from "./Card";
import { api } from "../lib/api";
import type { IngestRowProblem, IngestSummary } from "../lib/types";

const ACCEPT = ".xlsx,.xlsm,.csv";
const MAX_BYTES = 5 * 1024 * 1024;

type Status = "idle" | "loading" | "success" | "error";

export default function ImportCard({ onImported }: { onImported?: () => void }) {
  const fileInput = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [summary, setSummary] = useState<IngestSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);

  function run(fn: () => Promise<IngestSummary>, label: string) {
    setStatus("loading");
    setError(null);
    setSummary(null);
    fn()
      .then((s) => {
        setSummary(s);
        setStatus("success");
        onImported?.();
      })
      .catch((e: Error) => {
        setError(e.message ?? `${label} failed.`);
        setStatus("error");
      });
  }

  function onFile(file: File | undefined | null) {
    if (!file || status === "loading") return;
    if (!/\.(xlsx|xlsm|csv)$/i.test(file.name)) {
      setError("Please choose an .xlsx, .xlsm or .csv file.");
      setStatus("error");
      return;
    }
    if (file.size > MAX_BYTES) {
      setError("File is larger than the 5 MB upload limit.");
      setStatus("error");
      return;
    }
    run(() => api.ingest(file), "Upload failed.");
    if (fileInput.current) fileInput.current.value = "";
  }

  function onLoadSample() {
    run(() => api.ingestSample(), "Loading sample dataset failed.");
  }

  const problemGroups: { label: string; problems: IngestRowProblem[] }[] = [];
  if (summary?.problems?.length) {
    const byType = new Map<string, IngestRowProblem[]>();
    for (const p of summary.problems) {
      const list = byType.get(p.error_type) ?? [];
      list.push(p);
      byType.set(p.error_type, list);
    }
    for (const [type, problems] of byType) {
      problemGroups.push({ label: type, problems });
    }
  }

  const disabled = status === "loading";

  return (
    <Card>
      <CardHeader
        title="Import dataset"
        subtitle="Upload your own transactions (.xlsx / .xlsm / .csv, max 5 MB) or load the bundled sample dataset in one click."
      />
      <div className="px-5 py-4 space-y-4">
        <div
          role="button"
          tabIndex={0}
          aria-disabled={disabled}
          onClick={() => !disabled && fileInput.current?.click()}
          onKeyDown={(e) => {
            if ((e.key === "Enter" || e.key === " ") && !disabled) fileInput.current?.click();
          }}
          onDragOver={(e) => {
            e.preventDefault();
            if (!disabled) setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            onFile(e.dataTransfer.files?.[0]);
          }}
          className={`rounded-xl border-2 border-dashed px-6 py-6 text-center cursor-pointer transition-colors ${
            dragOver ? "border-indigo-400 bg-indigo-50" : "border-slate-300 hover:border-indigo-300"
          } ${disabled ? "opacity-60 pointer-events-none" : ""}`}
        >
          <input
            ref={fileInput}
            type="file"
            accept={ACCEPT}
            className="hidden"
            onChange={(e) => onFile(e.target.files?.[0])}
          />
          <div className="text-sm font-medium text-slate-700">Drag &amp; drop your file here, or click to browse</div>
          <div className="text-xs text-slate-400 mt-1">Downloads work too — a second import never duplicates transactions.</div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            disabled={disabled}
            onClick={() => fileInput.current?.click()}
            className="bg-indigo-600 text-white text-sm font-medium rounded-lg px-4 py-2 hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Choose file…
          </button>
          <button
            type="button"
            disabled={disabled}
            onClick={onLoadSample}
            className="text-sm font-medium rounded-lg px-4 py-2 border border-slate-300 text-slate-700 hover:border-indigo-300 hover:text-indigo-600 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Load sample dataset
          </button>
          {disabled ? (
            <span className="text-xs text-slate-500 animate-pulse">Importing – validating, classifying and flagging items…</span>
          ) : null}
        </div>

        {status === "error" && error ? (
          <div className="rounded-lg border border-red-200 bg-red-50 text-red-700 text-sm px-4 py-3">{error}</div>
        ) : null}

        {status === "success" && summary ? (
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 text-emerald-900 text-sm">
            <div className="px-4 py-3 border-b border-emerald-100">
              <div className="font-semibold flex items-center gap-2">
                <span className="w-5 h-5 rounded-full bg-emerald-600 text-white flex items-center justify-center text-xs">✓</span>
                Import complete
              </div>
              <div className="text-xs text-emerald-700 mt-0.5 truncate">{summary.filename}</div>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 divide-x divide-emerald-100 text-center">
              <div className="px-3 py-3">
                <div className="text-lg font-semibold tabular-nums">{summary.rows_read}</div>
                <div className="text-[11px] uppercase tracking-wide text-emerald-600">rows read</div>
              </div>
              <div className="px-3 py-3">
                <div className="text-lg font-semibold tabular-nums">{summary.rows_inserted}</div>
                <div className="text-[11px] uppercase tracking-wide text-emerald-600">inserted</div>
              </div>
              <div className="px-3 py-3">
                <div className="text-lg font-semibold tabular-nums">{summary.rows_duplicate_skipped}</div>
                <div className="text-[11px] uppercase tracking-wide text-emerald-600">duplicates</div>
              </div>
              <div className="px-3 py-3">
                <div className="text-lg font-semibold tabular-nums">{summary.rows_failed}</div>
                <div className="text-[11px] uppercase tracking-wide text-emerald-600">failed</div>
              </div>
            </div>
            <div className="px-4 py-3 border-t border-emerald-100 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs">
              <span className="text-emerald-800">
                {summary.review_queue_count > 0
                  ? `${summary.review_queue_count} item${summary.review_queue_count === 1 ? "" : "s"} flagged for review.`
                  : "No items flagged for review."}
              </span>
              <Link to="/review-queue" className="text-indigo-600 hover:underline font-medium">
                Open review queue →
              </Link>
              <Link to="/transactions" className="text-indigo-600 hover:underline font-medium">
                View transactions →
              </Link>
            </div>
            {problemGroups.length > 0 ? (
              <div className="px-4 py-3 border-t border-emerald-100">
                <div className="text-[11px] font-medium uppercase tracking-wide text-emerald-600 mb-2">Row problems</div>
                <div className="space-y-2 max-h-48 overflow-auto">
                  {problemGroups.map(({ label, problems }) => (
                    <div key={label}>
                      <div className="text-xs font-semibold text-emerald-800">{label}</div>
                      <ul className="text-xs text-emerald-700 space-y-0.5">
                        {problems.map((p, i) => (
                          <li key={i}>
                            <span className="tabular-nums font-medium">#{p.row_number}</span> {p.transaction_id ? `<${p.transaction_id}> ` : ""}
                            {p.message}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </Card>
  );
}