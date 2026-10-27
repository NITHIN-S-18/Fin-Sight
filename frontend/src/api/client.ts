const DEFAULT_API_BASE_URL = "http://localhost:8000/api/v1";
const ACCESS_TOKEN_KEY = "finsight-access-token";

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  display_name?: string;
}

export interface VerifyOtpRequest {
  email: string;
  otp: string;
}

export interface VerifyOtpResponse {
  reset_token: string;
  message: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface AuthenticatedUser {
  id: number;
  email: string;
  created_at: string;
  updated_at: string;
  financial_user_id: string | null;
  display_name: string | null;
  avatar_url?: string | null;
}

export interface ApiErrorBody {
  detail?: string | { message?: string; errors?: string[] };
  message?: string;
}

export interface ImportRecord {
  id: number;
  file_name: string;
  uploaded_at: string;
  transaction_start_date: string | null;
  transaction_end_date: string | null;
  transaction_count: number;
  status: string;
  error_message: string | null;
}

export interface SampleTransactionItem {
  transaction_date: string;
  merchant_name: string | null;
  description: string | null;
  amount: number;
  direction: string;
  category: string | null;
  transaction_class: string | null;
}

export interface ImportPreviewResponse {
  file_type: "csv" | "pdf";
  file_name: string;
  total_candidate_rows: number;
  valid_rows_count: number;
  invalid_rows_count: number;
  ambiguous_rows_count: number;
  estimated_duplicate_count: number;
  date_range_start: string | null;
  date_range_end: string | null;
  total_credits: number;
  total_debits: number;
  detected_mappings: Record<string, string>;
  unmapped_columns: string[];
  sample_transactions: SampleTransactionItem[];
  validation_errors: string[];
  preview_token: string | null;
}

export interface TransactionUploadResponse {
  import_record: ImportRecord;
  accepted_count: number;
  duplicate_count: number;
  rejected_count: number;
  validation_errors: string[];
  reconciliation_status?: string;
}

export interface FinancialSummary {
  total_transactions: number;
  start_date: string | null;
  end_date: string | null;
  last_analyzed: string | null;
  file_name: string | null;
}

export interface UserTransaction {
  transaction_id: string;
  user_id: string;
  transaction_date: string;
  merchant_name: string | null;
  description: string | null;
  amount: number;
  category: string | null;
  transaction_class: string | null;
  payment_mode: string | null;
  frequency: string | null;
  income_flag: string | null;
  recurring_flag: string | null;
  autopay_flag: string | null;
  risk_label: string | null;
  transaction_status: string | null;
  is_new_subscription: string | null;
  merchant_type: string | null;
  commitment_type: string | null;
}

export interface DashboardUserProfile {
  user_id: string;
  persona: string | null;
  income_type: string | null;
  monthly_financial_capacity: number | null;
  age_group: string | null;
  city: string | null;
  financial_profile: unknown | null;
}

export interface DashboardHealthCard {
  financial_health_score: number;
  financial_health_label: string;
  risk_level: string;
  rationale: string[];
}

export interface DashboardExposureCard {
  exposure_score: number;
  exposure_band: string;
  monthly_total_commitments: number;
  monthly_financial_capacity: number;
  available_monthly_capacity: number;
  explanation: string;
  income_source?: "Observed" | "Estimated" | "Manual" | string;
  income_mode?: "auto" | "manual" | "expected" | string;
  expected_monthly_income?: number | null;
  manual_monthly_income?: number | null;
}

export interface DashboardCommitmentLargest {
  commitment_name: string;
  monthly_amount: number;
}

export interface DashboardCommitmentBucket {
  active_commitments: number;
  mandatory_commitments: number;
  optional_commitments: number;
  monthly_amount: number;
  percentage_contribution: number;
  largest_commitment: DashboardCommitmentLargest | null;
  largest_optional_commitment: DashboardCommitmentLargest | null;
}

export interface DashboardCommitmentSummary {
  subscriptions: DashboardCommitmentBucket;
  emis: DashboardCommitmentBucket;
  bnpl: DashboardCommitmentBucket;
}

export interface DashboardSubscriptionHighlights {
  active_count: number;
  monthly_cost: number;
  most_expensive: { merchant_name: string; monthly_estimated_cost: number } | null;
  autopay_coverage_percent: number;
  new_subscriptions_count: number;
  trial_conversions_count: number;
}

export interface DashboardEmiHighlights {
  active_count: number;
  monthly_burden: number;
  highest_emi: { merchant_name: string; monthly_emi_amount: number } | null;
  autopay_coverage_percent: number;
  payment_success_rate: number;
  loan_types: string[];
}

export interface DashboardBnplHighlights {
  active_providers_count: number;
  monthly_burden: number;
  highest_provider_exposure: { provider_name: string; monthly_bnpl_commitment: number } | null;
  autopay_coverage_percent: number;
  payment_success_rate: number;
  active_providers: string[];
}

export interface DashboardRecommendation {
  recommendation_type: string;
  priority: string;
  impact_score: number;
  message: string;
  reason: string;
  expected_benefit: string;
  action_required: string;
  estimated_effort: string;
  estimated_monthly_saving: number | null;
  estimated_annual_saving: number | null;
  estimated_exposure_reduction: number | null;
  financial_benefit: string | null;
}

export interface DashboardUpcomingCommitment {
  title: string;
  expected_date: string | null;
  amount: number;
  source: string;
  type: string;
}

export interface DashboardAlert {
  alert_type: string;
  message: string;
  source: string;
}

export interface DashboardQuickStats {
  total_commitments_count: number;
  monthly_commitments_total: number;
  financial_capacity: number;
  available_capacity: number;
  available_capacity_percentage: number;
  overall_payment_success_rate: number;
  overall_autopay_coverage: number;
}

export interface DashboardMetadata {
  generated_at: string;
  execution_time_seconds: number;
  data_sources: string[];
  api_version: string;
}

export interface DashboardOnboardingResponse {
  user_profile: DashboardUserProfile;
  onboarding_required: true;
  message: string;
  metadata: DashboardMetadata;
}

export interface DashboardCashFlowForecast {
  forecast_month: string;
  forecast_available: boolean;
  availability_status: string;
  history_months_available: number;
  expected_variable_expenses: number | null;
  expected_income: number | null;
  expected_total_expenses: number | null;
  available_balance: number | null;
}

export interface DashboardResponse {
  user_profile: DashboardUserProfile;
  financial_health_card: DashboardHealthCard;
  exposure_card: DashboardExposureCard;
  commitment_summary: DashboardCommitmentSummary;
  subscription_highlights: DashboardSubscriptionHighlights;
  emi_highlights: DashboardEmiHighlights;
  bnpl_highlights: DashboardBnplHighlights;
  top_recommendations: DashboardRecommendation[];
  upcoming_commitments: DashboardUpcomingCommitment[];
  dashboard_alerts: DashboardAlert[];
  quick_statistics: DashboardQuickStats;
  cash_flow_forecast?: DashboardCashFlowForecast | null;
  metadata: DashboardMetadata;
}

export interface HistoricalMetricPoint {
  month: string;
  income: number;
  spending: number;
  commitments: number;
  exposure: number | null;
  financial_health: number | null;
  available_capacity: number | null;
}

export interface HistoricalDashboardResponse {
  user_id: string;
  points: HistoricalMetricPoint[];
  metric_basis: string;
}

export interface SubscriptionResponse {
  subscription_summary: { subscription_count: number; monthly_subscription_cost: number; most_expensive_subscription: { merchant_name: string; monthly_estimated_cost: number } | null };
  active_subscriptions: { merchant_name: string; latest_subscription_date: string; number_of_payments: number; average_subscription_amount: number; autopay_enabled: boolean; recurring_frequency: string; transaction_status_summary: { failed_transactions: number } }[];
}

export interface EmiResponse {
  emi_summary: { active_emi_count: number; monthly_emi_burden: number; highest_emi: { merchant_name: string; monthly_emi_amount: number } | null };
  active_emis: { merchant_name: string; latest_emi_date: string; monthly_emi_amount: number; autopay_enabled: boolean; payment_frequency: string; loan_type: string; transaction_status_summary: { failed_transactions: number } }[];
}

export interface BnplResponse {
  bnpl_summary: { active_provider_count: number; monthly_bnpl_burden: number; highest_provider_exposure: { provider_name: string; monthly_bnpl_commitment: number } | null };
  active_bnpl_accounts: { provider_name: string; latest_transaction_date: string; monthly_bnpl_commitment: number; autopay_enabled: boolean; payment_frequency: string; number_of_installments: number; transaction_status_summary: { failed_transactions: number } }[];
}

export interface CashFlowForecastResponse {
  user_id: string;
  forecast_month: string;
  forecast_available: boolean;
  availability_status: string;
  history_months_available: number;
  expected_income: number | null;
  expected_committed_expenses: number | null;
  expected_variable_expenses: number | null;
  expected_total_expenses: number | null;
  expected_net_cash: number | null;
  selected_baselines: Record<string, string>;
  evaluation: Record<string, {
    mae: number;
    rmse: number;
    r2: number;
    median_absolute_error: number;
    percentile_90_absolute_error: number;
    improvement_over_baseline_percent: number | null;
  }>;
  split_metadata: Record<string, unknown>;
  generated_at: string;
}

export interface GoalCategoryAdjustment {
  category: string;
  current_expected_spending: number;
  observed_monthly_spending: number | null;
  spending_basis: string;
  maximum_supported_reduction: number | null;
  suggested_reduction: number;
  adjusted_spending: number;
  reduction_percent: number;
  remaining_category_spending: number;
  remaining_goal_savings_gap: number | null;
  evidence: string;
  protected: boolean;
}

export interface GoalEvaluation {
  user_id: string;
  goal_amount: number;
  goal_months: number;
  required_monthly_saving: number | null;
  expected_monthly_saving: number | null;
  additional_monthly_saving_required: number | null;
  goal_feasible: boolean | null;
  variable_spending_adjustment_required: number | null;
  suggested_category_adjustments: GoalCategoryAdjustment[];
  projected_variable_expenses_after_adjustment: number | null;
  projected_monthly_saving_after_adjustment: number | null;
  remaining_money_after_goal_saving: number | null;
  explanation: string;
  model_version: string;
  availability_status: string;
  evaluation_metadata: Record<string, unknown>;
  planned_monthly_contribution: number | null;
  money_remaining_after_planned_contribution: number | null;
  remaining_goal_savings_gap_after_plan: number | null;
}

export interface FinancialGoalResponse extends GoalEvaluation {
  id: number;
  goal_name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ShortfallFactorDetail {
  factor: string;
  severity: "HIGH" | "MEDIUM" | "LOW";
  description: string;
}

export interface FinancialShortfallResponse {
  user_id: string;
  available: boolean;
  model_version: string;
  prediction: string;
  shortfall_risk: "LOW" | "MODERATE" | "HIGH";
  next_month_horizon: string;
  expected_net_cash: number | null;
  expected_income: number | null;
  expected_total_expenses: number | null;
  contributing_factors: string[];
  factor_details?: ShortfallFactorDetail[];
  risk_explanation?: string | null;
  recommended_actions: string[];
  availability_status: string;
}

export interface RecurringPaymentResponse {
  id: number;
  name: string;
  category: string;
  amount: number;
  frequency: string;
  monthly_equivalent_amount: number;
  last_payment_date: string | null;
  next_expected_date: string | null;
  status: string;
  confidence: number;
  confidence_level: string;
  source: "DETECTED" | "USER_ADDED";
  is_active: boolean;
  supporting_transaction_ids: string[];
  evidence: Record<string, unknown>;
  transactional_engagement_status?: "ACTIVE" | "MODERATE" | "UNDER_UTILIZED" | string | null;
  transactional_engagement_explanation?: string | null;
}

export interface CancellationSimulationResponse {
  recurring_payment_id: number;
  subscription_name: string;
  current_monthly_subscription_commitment: number;
  projected_monthly_subscription_commitment: number;
  current_total_monthly_commitments: number;
  projected_total_monthly_commitments: number;
  current_monthly_expenses: number | null;
  projected_monthly_expenses: number | null;
  current_available_cash: number | null;
  projected_available_cash: number | null;
  additional_monthly_savings: number;
  annual_potential_savings: number;
  current_goal_feasible: boolean | null;
  projected_goal_feasible: boolean | null;
  cancellation_applied: boolean;
  explanation: string;
}


export interface SelectedSubscriptionDetail {
  id: number;
  name: string;
  category: string;
  frequency: string;
  original_amount: number;
  monthly_equivalent_amount: number;
  engagement_status?: string | null;
}

export interface GoalImpactDetail {
  goal_id: number | null;
  goal_name: string | null;
  target_amount: number | null;
  timeframe_months: number | null;
  required_monthly_saving: number | null;
  current_available_cash: number | null;
  projected_available_cash: number | null;
  current_gap: number | null;
  projected_gap: number | null;
  gap_closed_percent: number | null;
  current_goal_feasible: boolean | null;
  projected_goal_feasible: boolean | null;
  explanation: string;
}

export interface BatchCancellationSimulationResponse {
  selected_count: number;
  selected_subscriptions: SelectedSubscriptionDetail[];
  current_total_monthly_commitments: number;
  projected_total_monthly_commitments: number;
  current_monthly_subscription_commitment: number;
  projected_monthly_subscription_commitment: number;
  monthly_savings: number;
  annual_potential_savings: number;
  current_available_cash: number | null;
  projected_available_cash: number | null;
  goal_impact: GoalImpactDetail | null;
  cancellation_applied: boolean;
  explanation: string;
}

export interface RecurringPaymentListResponse {
  items: RecurringPaymentResponse[];
  total: number;
}

export interface TrialIntelligenceResponse {
  id: number;
  merchant_name: string;
  authorization_transaction_id: string;
  authorization_amount: number;
  authorization_date: string;
  detected_state: "authorization_hold" | "possible_trial" | "possible_conversion" | "confirmed_recurring" | "dismissed";
  confidence: number;
  evidence: Record<string, unknown>;
  possible_conversion_date: string | null;
  related_recurring_payment_id: number | null;
  detected_at: string;
  updated_at: string;
  alert_sent_in_app: boolean;
  alert_sent_email: boolean;
  email_alert_scheduled_for: string | null;
  email_alert_sent_at: string | null;
  status: string;
  days_until_possible_conversion: number | null;
}

export interface CommitmentSnapshotResponse {
  total_monthly_commitments: number;
  active_commitment_count: number;
  breakdown_by_category: Record<string, number>;
  breakdown_by_source: Record<string, number>;
  detected_commitment_count: number;
  user_added_commitment_count: number;
  high_confidence_detected_count: number;
  excluded_low_confidence_count: number;
  excluded_inactive_count: number;
  excluded_trial_count: number;
  commitment_items: {
    id: number;
    name: string;
    category: string;
    amount: number;
    frequency: string;
    monthly_equivalent_amount: number;
    source: "DETECTED" | "USER_ADDED";
    confidence: number;
    confidence_level: string;
    status: string;
    next_payment_date: string | null;
    last_payment_date: string | null;
  }[];
}

export interface TrialIntelligenceListResponse {
  items: TrialIntelligenceResponse[];
  total: number;
}

export interface ExposureResponse {
  current_financial_status: {
    monthly_total_commitments: number;
    monthly_financial_capacity: number;
    available_monthly_capacity: number;
    exposure_score: number;
    monthly_subscription_commitment: number;
    monthly_emi_commitment: number;
    monthly_bnpl_commitment: number;
    income_source?: "Observed" | "Estimated" | "Manual" | string;
    income_mode?: "auto" | "manual" | "expected" | string;
    expected_monthly_income?: number | null;
    manual_monthly_income?: number | null;
  };
  financial_health: { financial_health_score: number; financial_health_label: string };
  exposure_summary: { exposure_band: string; explanation: string };
}

export interface SimulationRequest {
  scenario_type: string;
  parameters: Record<string, unknown>;
}

export interface SimulationMetric {
  baseline: number;
  projected: number;
  change: number;
}

export interface SimulationResponse {
  user_id: string;
  scenario_type: string;
  baseline_health: string;
  projected_health: string;
  baseline_exposure: number;
  projected_exposure: number;
  baseline_commitments: number;
  projected_commitments: number;
  available_capacity: number;
  change: {
    commitments: SimulationMetric;
    exposure: SimulationMetric;
    health: SimulationMetric;
  };
  risk_interpretation: string;
  recommendation: string;
  applied_changes: Record<string, unknown>;
  monthly_capacity?: number | null;
  monthly_deficit?: number;
}

export interface IntelligenceInsight {
  prediction: string | number | boolean;
  confidence: number | null;
  explanation: string;
  recommendation: string;
  supporting_factors: string[];
}

export interface FinancialIntelligenceResponse {
  user_id: string;
  distress: { prediction: string; confidence: number | null; insight: IntelligenceInsight };
  exposure_forecast: { future_exposure: number; confidence: number | null; insight: IntelligenceInsight };
  persona: { cluster: number | string; persona_name: string; confidence: number | null; insight: IntelligenceInsight };
  anomaly: { anomaly: boolean; score: number; confidence: number | null; insight: IntelligenceInsight };
  fused_confidence: number;
  generated_at: string;
}

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL).replace(/\/$/, "");

function getErrorMessage(body: ApiErrorBody | null, status: number): string {
  if (typeof body?.detail === "string") return body.detail;
  if (body?.detail && typeof body.detail === "object") {
    if (body.detail.message) return body.detail.message;
    if (body.detail.errors?.length) return body.detail.errors.join(" ");
  }
  if (body?.message) return body.message;
  if (status === 401) return "Your session is invalid or has expired.";
  if (status >= 500) return "The backend is temporarily unavailable. Please try again.";
  return "The request could not be completed.";
}

interface CacheEntry<T> {
  data: T;
  timestamp: number;
}

const apiCache = new Map<string, CacheEntry<unknown>>();
const pendingRequests = new Map<string, Promise<unknown>>();
const DEFAULT_CACHE_TTL_MS = 120_000; // 2 minutes

export function clearApiCache(pattern?: string | RegExp): void {
  if (!pattern) {
    apiCache.clear();
    return;
  }
  for (const key of apiCache.keys()) {
    if (typeof pattern === "string" ? key.includes(pattern) : pattern.test(key)) {
      apiCache.delete(key);
    }
  }
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
  token?: string,
): Promise<T> {
  const method = (options.method ?? "GET").toUpperCase();
  const isGet = method === "GET";
  const cacheKey = `${token ?? "anon"}:${path}`;

  if (isGet) {
    const cached = apiCache.get(cacheKey);
    if (cached && Date.now() - cached.timestamp < DEFAULT_CACHE_TTL_MS) {
      return cached.data as T;
    }
    const pending = pendingRequests.get(cacheKey);
    if (pending) {
      return pending as Promise<T>;
    }
  }

  const fetchPromise = (async () => {
    const headers = new Headers(options.headers);
    if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    if (token) headers.set("Authorization", `Bearer ${token}`);

    let response: Response;
    try {
      response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
    } catch {
      throw new ApiError("Unable to reach the FinSight backend. Please check that it is running.", 0);
    }

    const contentType = response.headers.get("content-type") ?? "";
    const body = contentType.includes("application/json") ? ((await response.json()) as ApiErrorBody | T) : null;
    if (!response.ok) {
      throw new ApiError(getErrorMessage(body as ApiErrorBody | null, response.status), response.status);
    }

    if (isGet) {
      apiCache.set(cacheKey, { data: body, timestamp: Date.now() });
    } else {
      clearApiCache();
    }

    return body as T;
  })();

  if (isGet) {
    pendingRequests.set(cacheKey, fetchPromise);
    try {
      return await fetchPromise;
    } finally {
      pendingRequests.delete(cacheKey);
    }
  }

  return fetchPromise;
}

export function getAvatarUrl(avatarPath: string | null | undefined): string | null {
  if (!avatarPath) return null;
  if (avatarPath.startsWith("http://") || avatarPath.startsWith("https://") || avatarPath.startsWith("data:")) {
    return avatarPath;
  }
  const cleanPath = avatarPath.startsWith("/") ? avatarPath : `/${avatarPath}`;
  // If backend path already starts with /api/v1, use the API_BASE_URL's origin or prefix
  if (cleanPath.startsWith("/api/v1/")) {
    const origin = API_BASE_URL.replace(/\/api\/v1\/?$/, "");
    return `${origin}${cleanPath}`;
  }
  return `${API_BASE_URL}${cleanPath}`;
}

export const authApi = {
  register(request: RegisterRequest) {
    return apiRequest<AuthenticatedUser>("/auth/register", {
      method: "POST",
      body: JSON.stringify(request),
    });
  },
  login(request: LoginRequest) {
    return apiRequest<LoginResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(request),
    });
  },
  me(token: string) {
    return apiRequest<AuthenticatedUser>("/auth/me", {}, token);
  },
  updateProfile(request: { display_name: string }, token: string) {
    return apiRequest<AuthenticatedUser>("/auth/me", {
      method: "PATCH",
      body: JSON.stringify(request),
    }, token);
  },
  uploadAvatar(file: File, token: string) {
    const formData = new FormData();
    formData.append("file", file);
    return apiRequest<AuthenticatedUser>("/auth/avatar", {
      method: "POST",
      body: formData,
    }, token);
  },
  deleteAvatar(token: string) {
    return apiRequest<AuthenticatedUser>("/auth/avatar", {
      method: "DELETE",
    }, token);
  },
  changePassword(request: { current_password: string; new_password: string }, token: string) {
    return apiRequest<void>("/auth/change-password", {
      method: "POST",
      body: JSON.stringify(request),
    }, token);
  },
  forgotPassword(request: { email: string }) {
    return apiRequest<{ message: string }>("/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify(request),
    });
  },
  verifyOtp(request: { email: string; otp: string }) {
    return apiRequest<{ reset_token: string; message: string }>("/auth/verify-otp", {
      method: "POST",
      body: JSON.stringify(request),
    });
  },
  resendOtp(request: { email: string }) {
    return apiRequest<{ message: string }>("/auth/resend-otp", {
      method: "POST",
      body: JSON.stringify(request),
    });
  },
  resetPassword(request: { token: string; new_password: string }) {
    return apiRequest<{ message: string }>("/auth/reset-password", {
      method: "POST",
      body: JSON.stringify(request),
    });
  },
  async exportData(token: string, format: "csv" | "json" | "pdf" = "json"): Promise<{ blob: Blob; filename?: string }> {
    let response: Response;
    try {
      response = await fetch(`${API_BASE_URL}/auth/export?format=${format}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
    } catch (networkErr) {
      if (import.meta.env.DEV) {
        console.error(
          `[FinSight Export] Network error while requesting ${format.toUpperCase()} export:`,
          networkErr instanceof Error ? networkErr.message : String(networkErr)
        );
      }
      throw new ApiError("Unable to reach the FinSight backend. Please check your network connection.", 0);
    }

    if (!response.ok) {
      let message = "Unable to export data.";
      try {
        const body = (await response.json()) as ApiErrorBody;
        message = getErrorMessage(body, response.status);
      } catch {
        if (response.status === 401) {
          message = "Your session is invalid or has expired.";
        } else if (response.status === 403) {
          message = "You do not have permission to export this data.";
        } else if (response.status === 404) {
          message = "Export service or user records not found.";
        } else if (response.status >= 500) {
          message = "The server encountered an error while generating your export. Please try again.";
        } else {
          message = `Export failed with status code ${response.status}.`;
        }
      }
      if (import.meta.env.DEV) {
        console.error(
          `[FinSight Export] Backend export failed with HTTP ${response.status}:`,
          message
        );
      }
      throw new ApiError(message, response.status);
    }
    const disposition = response.headers.get("content-disposition");
    let filename: string | undefined;
    if (disposition) {
      const match = disposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
      if (match && match[1]) {
        filename = match[1].replace(/['"]/g, "").trim();
      }
    }
    const blob = await response.blob();
    return { blob, filename };
  },
  async exportTransactions(token: string): Promise<Blob> {
    const { blob } = await authApi.exportData(token, "csv");
    return blob;
  },
};

export const transactionApi = {
  preview(file: File, token: string) {
    const formData = new FormData();
    formData.append("file", file);
    return apiRequest<ImportPreviewResponse>("/transactions/preview", {
      method: "POST",
      body: formData,
    }, token);
  },
  confirm(previewToken: string, token: string) {
    return apiRequest<TransactionUploadResponse>("/transactions/confirm", {
      method: "POST",
      body: JSON.stringify({ preview_token: previewToken }),
    }, token);
  },
  upload(file: File, token: string) {
    const formData = new FormData();
    formData.append("file", file);
    return apiRequest<TransactionUploadResponse>("/transactions/upload", {
      method: "POST",
      body: formData,
    }, token);
  },
  imports(token: string) {
    return apiRequest<ImportRecord[]>("/transactions/imports", {}, token);
  },
  summary(token: string) {
    return apiRequest<FinancialSummary>("/transactions/summary", {}, token);
  },
};

export const dashboardApi = {
  get(financialUserId: string, token: string) {
    return apiRequest<DashboardResponse | DashboardOnboardingResponse>(`/dashboard/${encodeURIComponent(financialUserId)}`, {}, token);
  },
  history(token: string) {
    return apiRequest<HistoricalDashboardResponse>("/dashboard/history", {}, token);
  },
};

export const userTransactionApi = {
  list(financialUserId: string, token: string) {
    return apiRequest<UserTransaction[]>(`/dataset/user/${encodeURIComponent(financialUserId)}/transactions`, {}, token);
  },
};

export const commitmentApi = {
  snapshot(token: string) {
    return apiRequest<CommitmentSnapshotResponse>("/commitments", {}, token);
  },
  recurringPayments(token: string, filters?: { category?: string; confidence_level?: string; status?: string }) {
    const params = new URLSearchParams();
    if (filters?.category) params.set("category", filters.category);
    if (filters?.confidence_level) params.set("confidence_level", filters.confidence_level);
    if (filters?.status) params.set("status", filters.status);
    const query = params.toString();
    return apiRequest<RecurringPaymentListResponse>(`/recurring-payments${query ? `?${query}` : ""}`, {}, token);
  },
  createRecurringPayment(request: {
    name: string;
    category: string;
    amount: number;
    frequency: string;
    next_expected_date: string;
    is_active?: boolean;
  }, token: string) {
    return apiRequest<RecurringPaymentResponse>("/recurring-payments", {
      method: "POST",
      body: JSON.stringify(request),
    }, token);
  },
  updateRecurringPayment(id: number, request: Record<string, unknown>, token: string) {
    return apiRequest<RecurringPaymentResponse>(`/recurring-payments/${id}`, {
      method: "PATCH",
      body: JSON.stringify(request),
    }, token);
  },
  deactivateRecurringPayment(id: number, token: string) {
    return apiRequest<RecurringPaymentResponse>(`/recurring-payments/${id}`, {
      method: "DELETE",
    }, token);
  },
  simulateCancellation(id: number, token: string, request: { goal_amount?: number; timeframe_months?: number } = {}) {
    return apiRequest<CancellationSimulationResponse>(`/recurring-payments/${id}/simulate-cancellation`, {
      method: "POST",
      body: JSON.stringify(request),
    }, token);
  },
  simulateBatchCancellation(token: string, request: { recurring_payment_ids: number[]; goal_id?: number; goal_amount?: number; timeframe_months?: number }) {
    return apiRequest<BatchCancellationSimulationResponse>('/recurring-payments/simulate-cancellation', {
      method: 'POST',
      body: JSON.stringify(request),
    }, token);
  },
  trialIntelligence(token: string) {
    return apiRequest<TrialIntelligenceListResponse>("/trial-intelligence", {}, token);
  },
  subscriptions(financialUserId: string, token: string) { return apiRequest<SubscriptionResponse>(`/subscriptions/${encodeURIComponent(financialUserId)}`, {}, token); },
  emis(financialUserId: string, token: string) { return apiRequest<EmiResponse>(`/emis/${encodeURIComponent(financialUserId)}`, {}, token); },
  bnpl(financialUserId: string, token: string) { return apiRequest<BnplResponse>(`/bnpl/${encodeURIComponent(financialUserId)}`, {}, token); },
  exposure(financialUserId: string, token: string) { return apiRequest<ExposureResponse>(`/exposure/${encodeURIComponent(financialUserId)}`, {}, token); },
};

export const intelligenceApi = {
  get(financialUserId: string, token: string) {
    return apiRequest<FinancialIntelligenceResponse>(`/ml/intelligence/${encodeURIComponent(financialUserId)}`, {}, token);
  },
};

export const forecastApi = {
  cashFlow(userId: string, token: string) {
    return apiRequest<CashFlowForecastResponse>(
      `/forecast/cash-flow/${encodeURIComponent(userId)}`,
      {},
      token,
    );
  },
};

export const goalsApi = {
  list(token: string) {
    return apiRequest<{ items: FinancialGoalResponse[] }>("/goals", {}, token);
  },
  evaluate(request: { goal_amount: number; timeframe_months: number }, token: string) {
    return apiRequest<GoalEvaluation>("/goals/feasibility", {
      method: "POST",
      body: JSON.stringify(request),
    }, token);
  },
  create(request: { goal_name: string; goal_amount: number; timeframe_months: number }, token: string) {
    return apiRequest<FinancialGoalResponse>("/goals", {
      method: "POST",
      body: JSON.stringify(request),
    }, token);
  },
  update(id: number, request: { goal_name?: string; goal_amount?: number; timeframe_months?: number; planned_monthly_contribution?: number }, token: string) {
    return apiRequest<FinancialGoalResponse>(`/goals/${id}`, {
      method: "PATCH",
      body: JSON.stringify(request),
    }, token);
  },
  deactivate(id: number, token: string) {
    return apiRequest<FinancialGoalResponse>(`/goals/${id}`, { method: "DELETE" }, token);
  },
};

export const shortfallApi = {
  get(financialUserId: string, token: string) {
    return apiRequest<FinancialShortfallResponse>(
      `/ml/shortfall/${encodeURIComponent(financialUserId)}`,
      {},
      token,
    );
  },
};

export const simulatorApi = {
  simulate(request: SimulationRequest, token: string) {
    return apiRequest<SimulationResponse>(
      "/simulator/simulate",
      {
        method: "POST",
        body: JSON.stringify(request),
      },
      token,
    );
  },
};

export interface CopilotQueryRequest {
  question: string;
  scenario_parameters?: Record<string, unknown> | null;
}

export interface CopilotResponse {
  intent: string;
  recommendation: string;
  confidence: number;
  confidence_level: string;
  summary: string;
  supporting_factors: string[];
  simulation_available: boolean;
  suggested_next_action: string;
  metadata: Record<string, unknown>;
}

export interface CopilotOpportunity {
  opportunity_id: string;
  title: string;
  priority: string;
  description: string;
  expected_benefit: string;
  estimated_monthly_savings: number;
}

export interface CopilotSuggestionsResponse {
  user_id: string;
  primary_archetype: string;
  opportunities: CopilotOpportunity[];
  summary: string;
  generated_at: string;
}

export const copilotApi = {
  query(request: CopilotQueryRequest, token: string) {
    return apiRequest<CopilotResponse>(
      "/copilot/query",
      {
        method: "POST",
        body: JSON.stringify(request),
      },
      token
    );
  },
  suggestions(financialUserId: string, token: string) {
    return apiRequest<CopilotSuggestionsResponse>(
      `/copilot/suggestions/${encodeURIComponent(financialUserId)}`,
      {},
      token
    );
  },
  async chat(request: AssistantChatRequest, token: string): Promise<AssistantChatResponse> {
    const raw = await apiRequest<AssistantChatResponse>(
      "/copilot/chat",
      {
        method: "POST",
        body: JSON.stringify(request),
      },
      token
    );
    const msgText = raw.text || raw.response || "";
    const tools =
      raw.tools_invoked ||
      (raw.tool_calls ? raw.tool_calls.map((t) => t.tool || "").filter(Boolean) : []);
    const latency =
      raw.latency_ms ?? (typeof raw.metadata?.latency_ms === "number" ? raw.metadata.latency_ms : 0);
    const modelName =
      raw.model ||
      (typeof raw.metadata?.generated_by === "string" ? raw.metadata.generated_by : "gemini-3.8-flash");
    return {
      ...raw,
      text: msgText,
      response: msgText,
      tools_invoked: tools,
      latency_ms: latency,
      model: modelName,
    };
  },
  listConversations(token: string) {
    return apiRequest<ConversationResponse[]>(
      "/copilot/conversations",
      {},
      token
    );
  },
  createConversation(title: string | undefined, token: string) {
    return apiRequest<ConversationResponse>(
      "/copilot/conversations",
      {
        method: "POST",
        body: JSON.stringify({ title }),
      },
      token
    );
  },
  async getConversation(id: string, token: string): Promise<ConversationDetailResponse> {
    const raw = await apiRequest<ConversationDetailResponse>(
      `/copilot/conversations/${encodeURIComponent(id)}`,
      {},
      token
    );
    const rawMessages = Array.isArray(raw?.messages) ? raw.messages : [];
    const messages = rawMessages.map((m) => {
      const msgText = m.text || m.content || "";
      const senderVal = (m.sender || m.role || "user") as "user" | "assistant";
      return {
        ...m,
        sender: senderVal,
        role: senderVal,
        text: msgText,
        content: msgText,
      };
    });
    return {
      ...raw,
      messages,
    };
  },
  deleteConversation(id: string, token: string) {
    return apiRequest<{ status: string; id: string }>(
      `/copilot/conversations/${encodeURIComponent(id)}`,
      {
        method: "DELETE",
      },
      token
    );
  },
  renameConversation(id: string, title: string, token: string) {
    return apiRequest<ConversationResponse>(
      `/copilot/conversations/${encodeURIComponent(id)}`,
      {
        method: "PATCH",
        body: JSON.stringify({ title }),
      },
      token
    );
  },
  analyzeDocument(file: File, token: string) {
    const formData = new FormData();
    formData.append("file", file);
    return apiRequest<DocumentAnalyzeResponse>(
      "/copilot/documents/analyze",
      {
        method: "POST",
        body: formData,
      },
      token
    );
  },
};

export interface AssistantChatRequest {
  message: string;
  conversation_id?: string | null;
  document_context?: string | null;
}

export interface AssistantChatResponse {
  conversation_id: string;
  message_id: string;
  text?: string;
  response: string;
  intent?: string;
  domain?: string;
  tool_calls?: Array<{ tool?: string; [key: string]: unknown }>;
  tools_invoked?: string[];
  factors?: string[];
  recommendation?: string | null;
  action?: string | null;
  metadata?: Record<string, unknown>;
  latency_ms?: number;
  model?: string;
  created_at?: string;
}

export interface ConversationResponse {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  preview: string;
}

export interface ConversationMessageResponse {
  id: string;
  conversation_id?: string;
  sender?: "user" | "assistant" | string;
  role?: "user" | "assistant" | "system" | string;
  text?: string;
  content?: string;
  intent?: string | null;
  tool_calls?: Array<Record<string, unknown>>;
  tools_invoked?: string[] | null;
  metadata?: Record<string, unknown>;
  created_at: string;
}

export interface ConversationDetailResponse {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: ConversationMessageResponse[];
}

export interface DocumentAnalyzeResponse {
  filename: string;
  text_preview: string;
  char_count: number;
  document_text: string;
}

export function getStoredAccessToken(): string | null {
  return sessionStorage.getItem(ACCESS_TOKEN_KEY);
}

export function storeAccessToken(token: string): void {
  sessionStorage.setItem(ACCESS_TOKEN_KEY, token);
}

export function clearStoredAccessToken(): void {
  sessionStorage.removeItem(ACCESS_TOKEN_KEY);
  clearApiCache();
}

export type IncomeMode = "auto" | "manual" | "expected";
export type IncomeSourceLabel = "Observed" | "Estimated" | "Manual";

export interface IncomeConfigurationResponse {
  user_id: string;
  income_mode: IncomeMode;
  manual_monthly_income: number | null;
  expected_monthly_income: number | null;
  effective_date: string | null;
  effective_monthly_income: number;
  income_source_label: IncomeSourceLabel;
  auto_detected_income: number;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface IncomeConfigurationUpdateRequest {
  income_mode: IncomeMode;
  manual_monthly_income?: number | null;
  expected_monthly_income?: number | null;
  effective_date?: string | null;
}

export const incomeApi = {
  getConfig(token: string) {
    return apiRequest<IncomeConfigurationResponse>("/income/config", {}, token);
  },
  updateConfig(request: IncomeConfigurationUpdateRequest, token: string) {
    clearApiCache();
    return apiRequest<IncomeConfigurationResponse>(
      "/income/config",
      {
        method: "PUT",
        body: JSON.stringify(request),
      },
      token
    );
  },
};
