export type PnlType = "revenue" | "cogs" | "payroll" | "operating_expense" | "non_pnl";

export interface Classification {
  category_code: string;
  category_name: string;
  subcategory: string;
  pnl_type: PnlType | null;
  accounting_treatment: string;
  is_contra: boolean;
  confidence: number;
  requires_review: boolean;
  review_status: string | null;
  source: string;
  reasoning: string;
  version: number;
}

export interface Transaction {
  id: number;
  transaction_id: string;
  date: string;
  description: string;
  counterparty: string;
  amount_cents: number;
  amount: number;
  method: string;
  raw_amount: string;
  status: string;
  classification: Classification;
}

export interface TransactionPage {
  total: number;
  limit: number;
  offset: number;
  transactions: Transaction[];
}

export interface ReviewItem {
  id: number;
  transaction_id: string;
  date: string;
  description: string;
  counterparty: string;
  amount_cents: number;
  amount: number;
  method: string;
  status: string;
  current_classification: Classification | null;
  submitted: {
    category_code: string | null;
    category_name: string | null;
    pnl_type: string | null;
    accounting_treatment: string | null;
    confidence: number | null;
    source: string | null;
    reasoning: string | null;
  };
  decided: {
    category_code: string | null;
    category_name: string | null;
    pnl_type: string | null;
    accounting_treatment: string | null;
    confidence: number | null;
  } | null;
  review_sources: string[];
  review_reasons: string[];
  suggested_action: string;
  note: string;
  reviewed_by: string | null;
  reviewer_decision: string;
  created_at: string | null;
  reviewed_at: string | null;
  resolved_at: string | null;
}

export interface ReviewList {
  total: number;
  items: ReviewItem[];
}

export interface Category {
  code: string;
  name: string;
  subcategory: string;
  pnl_type: string;
  accounting_treatment: string;
  is_contra: boolean;
  description: string;
}

export interface PnlLine {
  line: string;
  label: string;
  amount_cents: number;
  amount: number;
  transaction_count: number;
  is_computed: boolean;
  categories: {
    category_code: string;
    category_name: string;
    amount_cents: number;
    amount: number;
    transaction_count: number;
  }[];
}

export interface PnlReport {
  month: string;
  transaction_count: number;
  net_cash_cents: number;
  net_cash: number;
  pending_review_count: number;
  lines: Record<string, PnlLine>;
}

export interface PnlDrilldown {
  month: string;
  line: string;
  label: string;
  amount_cents: number;
  amount: number;
  computed: boolean;
  components: { line: string; label: string; amount_cents: number; amount: number }[];
  transactions: {
    transaction_id: string;
    date: string;
    description: string;
    counterparty: string;
    amount_cents: number;
    amount: number;
    method: string;
    category: string | null;
    category_code: string | null;
  }[];
}

export interface VarianceLine {
  line: string;
  label: string;
  previous_cents: number;
  current_cents: number;
  previous: number;
  current: number;
  absolute_cents: number;
  absolute: number;
  percent: number | null;
  material: boolean;
}

export interface VarianceReport {
  month_a: string;
  month_b: string;
  materiality: { percent: number | null; abs_cents: number | null };
  lines: VarianceLine[];
}

export interface VarianceDriver {
  category: string;
  previous_cents: number;
  current_cents: number;
  previous: number;
  current: number;
  absolute_cents: number;
  absolute: number;
  percent: number | null;
  material: boolean;
  contribution_percent: number;
  transaction_count: number;
  transactions: {
    transaction_id: string;
    date: string;
    description: string;
    counterparty: string;
    amount_cents: number;
    amount: number;
  }[];
}

export interface VarianceDriverReport {
  month_a: string;
  month_b: string;
  line: string;
  label: string;
  line_variance_cents: number;
  drivers: VarianceDriver[];
}

export interface DashboardData {
  selected_month: string | null;
  months: { month: string; transaction_count: number; net_cash_cents: number }[];
  overview: {
    month: string;
    lines: Record<string, number>;
    amounts: Record<string, number>;
    transaction_count: number;
    net_cash_cents: number;
    net_cash: number;
    pending_review_count: number;
  } | null;
  trend: {
    month: string;
    revenue_cents: number;
    cogs_cents: number;
    gross_profit_cents: number;
    operating_profit_cents: number;
    payroll_cents: number;
    operating_expenses_cents: number;
  }[];
  expense_mix: {
    category_code: string;
    category_name: string;
    amount_cents: number;
    amount: number;
    bucket: string;
  }[];
  stats: {
    total_transactions: number;
    pending_review: number;
    categories_in_use: number;
  };
}

export interface ToolCallRecord {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
  result: unknown;
  error: string | null;
}

export interface AnalystEvidence {
  months: string[];
  transaction_ids: string[];
  transactions_returned: number;
}

export interface AnalystResponse {
  answer: string;
  model: string;
  tool_calls: ToolCallRecord[];
  error: string | null;
  stopped_prematurely?: boolean;
  tools_used?: string[];
  evidence?: AnalystEvidence;
  pipeline?: string[];
}