import {
  CommitmentSnapshotResponse,
  DashboardResponse,
  HistoricalDashboardResponse,
} from "../api/client";

export interface AlertItem {
  id: string;
  title: string;
  badgeText: string;
  badgeTone: "danger" | "warning" | "info" | "success";
  description: string;
  iconType: "netflix" | "insurance" | "calendar" | "alert";
  amount?: number;
  dueDate?: string;
}

export interface AttentionInsight {
  id: string;
  title: string;
  description: string;
  category: "subscriptions" | "usage" | "savings" | "risk";
  tone: "amber" | "purple" | "cyan" | "rose";
  actionTarget?: "commitments" | "intelligence" | "what-if" | "assistant";
  assistantPrompt?: string;
}

export interface ExpenseTrendBar {
  month: string;
  amount: number;
  formattedAmount: string;
  heightPercent: number;
}

export interface CommitmentCategory {
  key: string;
  label: string;
  amount: number;
  pct: number;
  count?: number;
  color: string;
}

export interface ExposureTrendPoint {
  month: string;
  label: string;
  exposure: number;
  commitments: number;
  income: number;
}

export interface ExposureTrendData {
  points: ExposureTrendPoint[];
  latestExposure: number;
  previousExposure: number | null;
  vsPreviousMonth: number | null;
  sixMonthAverage: number | null;
  vsSixMonthAverage: number | null;
  isAvailable: boolean;
  timeframeLabel: string;
}

// ─────────────────────────────────────────────────────────────
// DATA ADAPTERS (Prioritizes real authoritative backend values)
// ─────────────────────────────────────────────────────────────

/**
 * Resolves upcoming alerts from authenticated backend data.
 */
export function resolveUpcomingAlerts(dashboard: DashboardResponse): AlertItem[] {
  const alerts: AlertItem[] = [];

  if (dashboard.upcoming_commitments && dashboard.upcoming_commitments.length > 0) {
    for (const item of dashboard.upcoming_commitments) {
      if (!item.title) continue;
      const d = item.expected_date ? new Date(item.expected_date) : null;
      let badgeText = "Upcoming";
      let badgeTone: "danger" | "warning" | "info" = "info";

      if (d && !isNaN(d.getTime())) {
        const diffDays = Math.ceil((d.getTime() - Date.now()) / (1000 * 60 * 60 * 24));
        if (diffDays <= 2) {
          badgeText = `In ${Math.max(1, diffDays)} day${diffDays === 1 ? "" : "s"}`;
          badgeTone = "danger";
        } else if (diffDays <= 7) {
          badgeText = `In ${diffDays} days`;
          badgeTone = "warning";
        } else {
          badgeText = item.expected_date || "Upcoming";
          badgeTone = "info";
        }
      }

      alerts.push({
        id: `backend-${item.title}-${item.expected_date || "due"}`,
        title: item.title,
        badgeText,
        badgeTone,
        description: `₹${Math.round(item.amount).toLocaleString("en-IN")}${item.expected_date ? ` • ${item.expected_date}` : ""}`,
        iconType: item.title.toLowerCase().includes("lic") || item.title.toLowerCase().includes("insurance")
          ? "insurance"
          : "calendar",
        amount: item.amount,
        dueDate: item.expected_date || undefined,
      });
    }
  }

  return alerts.slice(0, 2);
}

/**
 * Resolves "What needs your attention" insights dynamically
 * adapting backend values whenever available.
 */
export function resolveAttentionInsights(dashboard: DashboardResponse): AttentionInsight[] {
  const subCost = dashboard.subscription_highlights?.monthly_cost;
  const subCount = dashboard.subscription_highlights?.active_count || 0;
  const emiBurden = dashboard.emi_highlights?.monthly_burden;
  const exposureScore = dashboard.exposure_card?.exposure_score || 0;
  const healthLabel = dashboard.financial_health_card?.financial_health_label?.toLowerCase() || "";
  const riskLevel = dashboard.financial_health_card?.risk_level?.toLowerCase() || "";

  return [
    {
      id: "attention-sub-spend",
      title: subCost && subCost > 0 ? "High Subscription Spending" : "Subscription Overhead",
      description: subCost && subCost > 0
        ? `You're spending ₹${Math.round(subCost).toLocaleString("en-IN")}/month on subscriptions.`
        : "No active subscription overhead detected.",
      category: "subscriptions",
      tone: subCost && subCost > 0 ? "amber" : "cyan",
      actionTarget: "commitments",
      assistantPrompt: "How can I optimize my subscription commitments?",
    },
    {
      id: "attention-sub-activity",
      title: subCount > 0 ? "Active Recurring Commitments" : "Recurring Commitments Monitored",
      description: subCount > 0
        ? `${subCount} active recurring subscription${subCount > 1 ? "s" : ""} detected in your ledger.`
        : "No active subscription overhead detected in your ledger.",
      category: "usage",
      tone: subCount > 0 ? "purple" : "cyan",
      actionTarget: "commitments",
      assistantPrompt: "Show me subscriptions with low usage or recurring value.",
    },
    {
      id: "attention-savings",
      title: "Savings Goal Feasible",
      description: "Evaluate realistic financial goals against your projected cash flow.",
      category: "savings",
      tone: "cyan",
      actionTarget: "what-if",
      assistantPrompt: "Calculate my savings trajectory with ₹5,000 extra monthly buffer.",
    },
    {
      id: "attention-risk",
      title: exposureScore > 40 || riskLevel.includes("high") ? "Elevated Exposure Risk" : "Commitments Within Capacity",
      description: emiBurden && emiBurden > 0
        ? `Fixed obligations account for ₹${Math.round(emiBurden).toLocaleString("en-IN")}/month of recurring outflows.`
        : `Your financial exposure is rated ${dashboard.exposure_card?.exposure_band || "healthy"}.`,
      category: "risk",
      tone: exposureScore > 40 ? "rose" : "cyan",
      actionTarget: "intelligence",
      assistantPrompt: `Explain my risk factors (${riskLevel || healthLabel || "exposure"}).`,
    },
  ];
}

const CATEGORY_PALETTE: Record<string, string> = {
  emi: "#8B5CF6", // Purple
  loan: "#8B5CF6", // Purple
  bnpl: "#F59E0B", // Amber
  subscription: "#06B6D4", // Cyan
  subscriptions: "#06B6D4", // Cyan
  rent: "#EC4899", // Rose
  insurance: "#3B82F6", // Blue
  utility: "#10B981", // Emerald
  utilities: "#10B981", // Emerald
  bills: "#10B981", // Emerald
  other: "#6366F1", // Indigo
};

function formatCategoryLabel(key: string): string {
  const normalized = key.trim().toLowerCase();
  if (normalized === "emi") return "EMIs";
  if (normalized === "loan") return "Loans";
  if (normalized === "bnpl") return "BNPL";
  if (normalized === "subscription" || normalized === "subscriptions") return "Subscriptions";
  if (normalized === "rent") return "Rent";
  if (normalized === "insurance") return "Insurance";
  if (normalized === "utility" || normalized === "utilities") return "Utilities";
  return key.charAt(0).toUpperCase() + key.slice(1);
}

/**
 * Resolves commitment categories supporting generic recurring commitments
 * (EMIs, BNPL, Subscriptions, Rent, Insurance, Utilities, etc.)
 * using the Unified Commitment Engine.
 */
export function resolveCommitmentMix(
  dashboard: DashboardResponse,
  commitmentSnapshot?: CommitmentSnapshotResponse | null
): CommitmentCategory[] {
  // 1. Try authoritative Unified Commitment Engine snapshot
  if (commitmentSnapshot && commitmentSnapshot.breakdown_by_category) {
    const breakdown = commitmentSnapshot.breakdown_by_category;
    const total = commitmentSnapshot.total_monthly_commitments > 0
      ? commitmentSnapshot.total_monthly_commitments
      : dashboard.exposure_card?.monthly_total_commitments || 0;

    const items = commitmentSnapshot.commitment_items || [];
    const countByCategory = new Map<string, number>();
    for (const item of items) {
      const cat = item.category.trim().toLowerCase();
      countByCategory.set(cat, (countByCategory.get(cat) || 0) + 1);
    }

    const categories: CommitmentCategory[] = [];
    for (const [key, amount] of Object.entries(breakdown)) {
      if (amount <= 0) continue;
      const normalizedKey = key.trim().toLowerCase();
      // Never classify salary or income as a commitment
      if (normalizedKey === "income" || normalizedKey === "salary") continue;

      const pct = total > 0 ? (amount / total) * 100 : 0;
      const color = CATEGORY_PALETTE[normalizedKey] || "#6366F1";
      const count = countByCategory.get(normalizedKey) || 0;

      categories.push({
        key: normalizedKey,
        label: formatCategoryLabel(key),
        amount,
        pct,
        count,
        color,
      });
    }

    if (categories.length > 0) {
      // Sort by amount descending
      categories.sort((a, b) => b.amount - a.amount);

      // Reconcile rounded amounts to guarantee sum(round(cat.amount)) === Math.round(total)
      const targetTotal = Math.round(total);
      if (targetTotal > 0) {
        const roundedSum = categories.reduce((sum, c) => sum + Math.round(c.amount), 0);
        const discrepancy = targetTotal - roundedSum;
        if (discrepancy !== 0) {
          // Adjust category whose fractional part contributed most to the rounding drift
          const sortedByDrift = [...categories].sort((a, b) => {
            const driftA = Math.round(a.amount) - a.amount;
            const driftB = Math.round(b.amount) - b.amount;
            return discrepancy < 0 ? driftB - driftA : driftA - driftB;
          });
          const catToAdjust = sortedByDrift[0];
          if (catToAdjust) {
            catToAdjust.amount = Math.round(catToAdjust.amount) + discrepancy;
          }
        }
      }

      return categories;
    }
  }

  // 2. Fallback to dashboard summary breakdown
  const cs = dashboard.commitment_summary;
  const emiAmount = cs?.emis?.monthly_amount ?? 0;
  const subAmount = cs?.subscriptions?.monthly_amount ?? 0;
  const bnplAmount = cs?.bnpl?.monthly_amount ?? 0;
  const total = dashboard.exposure_card?.monthly_total_commitments ?? (emiAmount + subAmount + bnplAmount);

  if (total > 0) {
    const list: CommitmentCategory[] = [];

    if (emiAmount > 0) {
      list.push({
        key: "emi",
        label: "EMIs",
        amount: emiAmount,
        pct: total > 0 ? (emiAmount / total) * 100 : 0,
        count: cs?.emis?.active_commitments,
        color: "#8B5CF6",
      });
    }

    if (bnplAmount > 0) {
      list.push({
        key: "bnpl",
        label: "BNPL",
        amount: bnplAmount,
        pct: total > 0 ? (bnplAmount / total) * 100 : 0,
        count: cs?.bnpl?.active_commitments,
        color: "#F59E0B",
      });
    }

    if (subAmount > 0) {
      list.push({
        key: "subscriptions",
        label: "Subscriptions",
        amount: subAmount,
        pct: total > 0 ? (subAmount / total) * 100 : 0,
        count: cs?.subscriptions?.active_commitments,
        color: "#06B6D4",
      });
    }

    if (list.length > 0) return list;
  }

  return [];
}

/**
 * Resolves Exposure Trend data points for the 12-month line chart
 * from historical backend points.
 */
export function resolveExposureTrend(
  history: HistoricalDashboardResponse | null,
  fallbackCapacity?: number
): ExposureTrendData {
  if (!history?.points || history.points.length < 3) {
    return {
      points: [],
      latestExposure: 0,
      previousExposure: null,
      vsPreviousMonth: null,
      sixMonthAverage: null,
      vsSixMonthAverage: null,
      isAvailable: false,
      timeframeLabel: "Last 12 months",
    };
  }

  // Take up to the last 12 points
  const rawPoints = history.points.slice(-12);
  const points: ExposureTrendPoint[] = [];

  for (const pt of rawPoints) {
    const date = new Date(`${pt.month}-01T00:00:00`);
    const label = !isNaN(date.getTime())
      ? date.toLocaleDateString("en-IN", { month: "short" })
      : pt.month;

    let exposureVal = pt.exposure;
    if (exposureVal == null || isNaN(exposureVal)) {
      const cap = pt.income > 0 ? pt.income : (fallbackCapacity || 0);
      exposureVal = cap > 0 ? (pt.commitments / cap) * 100 : 0;
    }

    points.push({
      month: pt.month,
      label,
      exposure: Math.round(exposureVal * 100) / 100,
      commitments: pt.commitments,
      income: pt.income,
    });
  }

  if (points.length < 3) {
    return {
      points: [],
      latestExposure: 0,
      previousExposure: null,
      vsPreviousMonth: null,
      sixMonthAverage: null,
      vsSixMonthAverage: null,
      isAvailable: false,
      timeframeLabel: "Last 12 months",
    };
  }

  const latest = points[points.length - 1];
  const previous = points.length >= 2 ? points[points.length - 2] : null;
  const vsPreviousMonth = previous ? Math.round((latest.exposure - previous.exposure) * 100) / 100 : null;

  const last6 = points.slice(-6);
  const sixMonthAverage = last6.length > 0
    ? Math.round((last6.reduce((acc, p) => acc + p.exposure, 0) / last6.length) * 100) / 100
    : null;
  const vsSixMonthAverage = sixMonthAverage !== null
    ? Math.round((latest.exposure - sixMonthAverage) * 100) / 100
    : null;

  return {
    points,
    latestExposure: latest.exposure,
    previousExposure: previous ? previous.exposure : null,
    vsPreviousMonth,
    sixMonthAverage,
    vsSixMonthAverage,
    isAvailable: true,
    timeframeLabel: `Last ${points.length} months`,
  };
}

/**
 * Resolves expense trend bars from historical backend data if present.
 */
export function resolveExpenseTrend(
  history: HistoricalDashboardResponse | null
): ExpenseTrendBar[] {
  if (history?.points && history.points.length >= 3) {
    const last6 = history.points.slice(-6);
    const maxVal = Math.max(...last6.map((p) => p.spending || p.commitments || 1), 1);

    return last6.map((p) => {
      const val = p.spending || p.commitments || 0;
      const date = new Date(`${p.month}-01T00:00:00`);
      const monthLabel = !isNaN(date.getTime())
        ? date.toLocaleDateString("en-IN", { month: "short" })
        : p.month;
      const formatted = val >= 1000 ? `₹${Math.round(val / 1000)}K` : `₹${Math.round(val)}`;

      return {
        month: monthLabel,
        amount: val,
        formattedAmount: formatted,
        heightPercent: Math.max(15, Math.min(100, Math.round((val / maxVal) * 100))),
      };
    });
  }

  return [];
}
