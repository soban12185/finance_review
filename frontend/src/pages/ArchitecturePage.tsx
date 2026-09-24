import { Link } from "react-router-dom";
import { Card, CardHeader } from "../components/Card";
import { VerificationBadge } from "../components/ui";

const PIPELINE = [
  {
    title: "Ingest workbook",
    body: "Raw Excel rows are validated, normalized and deduplicated into PostgreSQL as integer cents.",
    kind: "deterministic",
  },
  {
    title: "Rule classification",
    body: "Deterministic rules match description + counterparty + method to a category chart. Most rows resolve here.",
    kind: "deterministic",
  },
  {
    title: "AI assist",
    body: "Only when rules are unclear (below confidence threshold) does Groq propose a category as structured JSON, on the backend.",
    kind: "ai",
  },
  {
    title: "Review queue",
    body: "Low-confidence, judgment-heavy, unusual or inconsistent items are held for a human reviewer, who decides with full audit trail.",
    kind: "human",
  },
  {
    title: "P&L engine",
    body: "Monthly statements, net cash and line crosstabs are computed in pure Python from the classified rows.",
    kind: "deterministic",
  },
  {
    title: "Variance engine",
    body: "Materiality math and driver attribution produce traceable movements, each tied to the exact transactions behind it.",
    kind: "deterministic",
  },
  {
    title: "AI Analyst",
    body: "Answers questions by calling read-only tools: SQL retrieves rows, the engine computes, then the LLM explains with cited evidence.",
    kind: "ai",
  },
  {
    title: "Verified reporting",
    body: "Every screen shows sources, confidence, review status and evidence so each number can be traced to its transactions.",
    kind: "human",
  },
] as const;

const PILLARS = [
  {
    icon: "✦",
    title: "AI (Groq)",
    accent: "bg-violet-100 text-violet-700",
    ring: "border-violet-200",
    body: "A hosted LLM assists classification and writes analyst narratives. Strictly read-only: it never sets totals, never modifies records, and only reasons over data the controlled tools returned.",
  },
  {
    icon: "▤",
    title: "Deterministic (Python engine)",
    accent: "bg-emerald-100 text-emerald-700",
    ring: "border-emerald-200",
    body: "The financial engine — monthly P&L, drill-downs, variance, materiality, drivers — is pure integer-cents arithmetic with no randomness. Re-running over the same data yields identical output every time.",
  },
  {
    icon: "▦",
    title: "Retrieval (PostgreSQL + SQL)",
    accent: "bg-sky-100 text-sky-700",
    ring: "border-sky-200",
    body: "All structured financial data lives in PostgreSQL. The analyst reaches it only through validated, schema-bound tool functions — never free-form database access — so every query is auditable.",
  },
  {
    icon: "⛁",
    title: "Human (Review Queue)",
    accent: "bg-amber-100 text-amber-700",
    ring: "border-amber-200",
    body: "Uncertainty is surfaced, not hidden. Transactions that fail automated checks wait for a reviewer, and each approve / reclassify / exclude decision is recorded with audit events.",
  },
];

const KIND_STYLE: Record<string, { label: string; cls: string }> = {
  deterministic: { label: "deterministic", cls: "bg-emerald-50 text-emerald-700 ring-emerald-200" },
  ai: { label: "AI", cls: "bg-violet-50 text-violet-700 ring-violet-200" },
  human: { label: "human", cls: "bg-amber-50 text-amber-700 ring-amber-200" },
};

const AI_WHERE = [
  "Classification only when deterministic rules are unclear (confidence < threshold).",
  "AI Analyst: selecting tools, composing the answer text, interpreting drivers.",
  "Structured JSON passthrough — no free text is trusted as numbers.",
];
const NOT_AI = [
  "Every dollar amount, P&L line and variance percentage (pure engine math).",
  "Transaction storage, dedupe, date handling and category membership.",
  "Review decisions and audit trails (created by reviewers, not the LLM).",
  "Materiality thresholds and driver attribution.",
];

export default function ArchitecturePage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">How It Works · AI-Native Architecture</h1>
          <p className="text-sm text-slate-500">
            What computes the truth, what reasons about it, and how outputs are kept verifiable.
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <VerificationBadge label="Every number is deterministic" tone="emerald" />
          <VerificationBadge label="AI is read-only" tone="indigo" />
        </div>
      </div>

      <Card>
        <CardHeader
          title="Processing pipeline"
          subtitle="Raw transactions workbook → verifiable financial intelligence, end to end"
        />
        <div className="px-5 py-5 grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
          {PIPELINE.map((step, i) => {
            const kind = KIND_STYLE[step.kind];
            return (
              <div key={step.title} className="relative rounded-xl border border-slate-200 p-4 flex flex-col gap-2">
                <span className="text-[10px] font-medium uppercase tracking-wide text-slate-400">Step {i + 1}</span>
                <div className="flex items-center justify-between gap-2">
                  <div className="text-sm font-semibold text-slate-800">{step.title}</div>
                  <span className={`shrink-0 inline-flex px-1.5 py-px rounded text-[10px] font-medium ring-1 ring-inset ${kind.cls}`}>
                    {kind.label}
                  </span>
                </div>
                <p className="text-[13px] text-slate-600 leading-relaxed">{step.body}</p>
              </div>
            );
          })}
        </div>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        {PILLARS.map((p) => (
          <div key={p.title} className={`bg-white rounded-xl border ${p.ring} shadow-sm px-5 py-4`}>
            <div className="flex items-center gap-2">
              <span className={`w-7 h-7 rounded-lg ${p.accent} flex items-center justify-center text-sm`}>{p.icon}</span>
              <span className="text-sm font-semibold text-slate-800">{p.title}</span>
            </div>
            <p className="text-[13px] text-slate-600 mt-2 leading-relaxed">{p.body}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <Card>
          <CardHeader title="Where AI is used" subtitle="Judgement and explanation — never authority over numbers" />
          <ul className="px-5 py-4 space-y-2 text-[13px] text-slate-700">
            {AI_WHERE.map((t) => (
              <li key={t} className="flex gap-2">
                <span className="text-violet-500 mt-px">✦</span>
                <span>{t}</span>
              </li>
            ))}
          </ul>
        </Card>
        <Card>
          <CardHeader title="Where AI is NOT used" subtitle="The source of truth stays deterministic" />
          <ul className="px-5 py-4 space-y-2 text-[13px] text-slate-700">
            {NOT_AI.map((t) => (
              <li key={t} className="flex gap-2">
                <span className="text-emerald-500 mt-px">▤</span>
                <span>{t}</span>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card>
        <CardHeader title="Why there is no vector search / RAG" subtitle="A deliberate architectural choice" />
        <div className="px-5 py-4 text-[13px] text-slate-600 space-y-2">
          <p>
            This data is fully structured: every figure lives in PostgreSQL with a deterministic schema. Semantic search
            over embeddings (Qdrant, Pinecone, FAISS, Chroma) would add retrieval noise to a system that must return{" "}
            <em>the same</em> number every time. Instead of RAG, the analyst uses validated SQL tool functions that return
            exactly the rows and engine-computed totals the question needs.
          </p>
          <p>
            If the data were unstructured (contracts, invoices as free text), an embedding index would become relevant —
            it is explicitly out of scope here, not an omission.
          </p>
        </div>
      </Card>

      <Card>
        <CardHeader title="How outputs are verified" subtitle="Trace any number back to its source transactions" />
        <div className="px-5 py-4 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3 text-[13px] text-slate-600">
          <div className="rounded-lg border border-slate-200 p-3">
            <div className="text-xs font-semibold text-slate-800 mb-1">Hybrid classification</div>
            Each transaction shows its source (Rule / AI / Manual), confidence %, and review flag.
          </div>
          <div className="rounded-lg border border-slate-200 p-3">
            <div className="text-xs font-semibold text-slate-800 mb-1">Review trail</div>
            Review Queue items show why they were flagged and every decision is audited.{" "}
            <Link to="/review-queue" className="text-indigo-600 hover:underline">Open →</Link>
          </div>
          <div className="rounded-lg border border-slate-200 p-3">
            <div className="text-xs font-semibold text-slate-800 mb-1">Drill-downs</div>
            Every P&L line decomposes to its transactions; variance drivers reference the exact transactions behind a move.
          </div>
          <div className="rounded-lg border border-slate-200 p-3">
            <div className="text-xs font-semibold text-slate-800 mb-1">Analyst evidence</div>
            Every answer lists the tools used, months analyzed and the transaction IDs that back it.{" "}
            <Link to="/analyst" className="text-indigo-600 hover:underline">Try it →</Link>
          </div>
        </div>
      </Card>
    </div>
  );
}