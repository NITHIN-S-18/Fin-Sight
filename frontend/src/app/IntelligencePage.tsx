import React, { useEffect, useMemo, useRef, useState } from "react";
import { motion, AnimatePresence, useReducedMotion } from "motion/react";
import {
  AlertTriangle,
  ArrowRight,
  ArrowUp,
  ArrowUpRight,
  Calendar,
  Check,
  CheckCircle2,
  ChevronRight,
  Clock,
  Compass,
  CreditCard,
  DollarSign,
  HelpCircle,
  Info,
  Layers,
  Lightbulb,
  LineChart,
  Loader2,
  MessageCircle,
  PieChart,
  Plus,
  Repeat,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Target,
  Trash2,
  TrendingDown,
  TrendingUp,
  Wallet,
  X,
  Zap,
} from "lucide-react";
import {
  ApiError,
  AuthenticatedUser,
  BatchCancellationSimulationResponse,
  commitmentApi,
  dashboardApi,
  ExposureResponse,
  forecastApi,
  goalsApi,
  FinancialGoalResponse,
  FinancialShortfallResponse,
  getStoredAccessToken,
  shortfallApi,
  userTransactionApi,
} from "../api/client";

interface IntelligencePageProps {
  onAskAssistant: (q?: string) => void;
  user: AuthenticatedUser;
  onUnauthorized: () => void;
}

type SectionKey = "cash_flow" | "goals" | "subscriptions" | "shortfall";
type HistoryPoint = { month: string; income: number; spending: number; commitments: number; exposure: number | null; financial_health: number | null; available_capacity: number | null };
type GoalFeasibilityItem = {
  id: string;
  title: string;
  targetAmount: number;
  currentSaved: number;
  targetDate: string;
  months: number;
  requiredMonthlySaving: number;
  expectedMonthlySaving: number;
  additionalMonthlyNeeded: number;
  plannedMonthlyContribution: number | null;
  plannedRemaining: number | null;
  planGap: number | null;
  status: "Achievable" | "Needs adjustment";
  category: string;
  isUserAdded?: boolean;
  isForecastAvailable: boolean;
  availabilityStatus: string;
  explanation: string;
  discretionaryAdjustments?: { category: string; currentMonthly: number; suggestedReduction: number; remainingGap: number | null; evidence: string }[];
};
type SubscriptionEngagementStatus = "Active" | "Moderate" | "Under-utilized" | "Insufficient data";

type SubscriptionItem = {
  id: string;
  name: string;
  category: string;
  monthlyAmount: number;
  transactionSignal: string;
  engagementStatus: SubscriptionEngagementStatus;
  nextBillingDate: string;
};

function mapEngagementStatus(status?: string | null): SubscriptionEngagementStatus {
  if (!status) return "Insufficient data";
  const normalized = status.toUpperCase().trim();
  if (normalized === "UNDER_UTILIZED") return "Under-utilized";
  if (normalized === "MODERATE") return "Moderate";
  if (normalized === "ACTIVE") return "Active";
  return "Insufficient data";
}

function mapGoal(goal: FinancialGoalResponse) : GoalFeasibilityItem {
  const isAvailable = goal.availability_status === "available" && goal.expected_monthly_saving !== null;
  const hasPlan = goal.planned_monthly_contribution !== null && goal.planned_monthly_contribution !== undefined;
  const plannedAmt = hasPlan ? (goal.planned_monthly_contribution ?? 0) : 0;
  const planCovers = hasPlan && plannedAmt >= (goal.required_monthly_saving ?? 0);
  const isAchievable = planCovers || Boolean(goal.goal_feasible);
  return {
    id: String(goal.id),
    title: goal.goal_name || "Savings Goal",
    targetAmount: goal.goal_amount,
    currentSaved: 0,
    targetDate: `${goal.goal_months} months`,
    months: goal.goal_months,
    requiredMonthlySaving: goal.required_monthly_saving ?? 0,
    expectedMonthlySaving: goal.expected_monthly_saving ?? 0,
    additionalMonthlyNeeded: goal.additional_monthly_saving_required ?? 0,
    plannedMonthlyContribution: goal.planned_monthly_contribution,
    plannedRemaining: goal.money_remaining_after_planned_contribution,
    planGap: goal.remaining_goal_savings_gap_after_plan,
    status: isAchievable ? "Achievable" : "Needs adjustment",
    category: "Personal",
    isUserAdded: true,
    isForecastAvailable: isAvailable,
    availabilityStatus: goal.availability_status,
    explanation: goal.explanation,
    discretionaryAdjustments: goal.suggested_category_adjustments.map((item) => ({
      category: item.category as "Dining" | "Shopping" | "Entertainment" | "Travel",
      currentMonthly: item.current_expected_spending,
      suggestedReduction: item.suggested_reduction,
      remainingGap: item.remaining_goal_savings_gap,
      evidence: item.evidence,
    })),
  };
}

function money(amount: number): string {
  return `₹${Math.round(amount).toLocaleString("en-IN")}`;
}

function parseGoalAmount(value: string): number | null {
  const normalized = value.replace(/,/g, "").trim();
  if (!/^\d+(?:\.\d{1,2})?$/.test(normalized)) return null;
  const amount = Number(normalized);
  return Number.isFinite(amount) && amount > 0 ? amount : null;
}

export function IntelligencePage({ onAskAssistant, user, onUnauthorized }: IntelligencePageProps) {
  const reduce = useReducedMotion();
  const [loading, setLoading] = useState(true);
  const [empty, setEmpty] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exposureData, setExposureData] = useState<ExposureResponse | null>(null);
  const [forecastData, setForecastData] = useState<Awaited<ReturnType<typeof forecastApi.cashFlow>> | null>(null);
  const [historyData, setHistoryData] = useState<{ points: HistoryPoint[] } | null>(null);
  const [shortfallData, setShortfallData] = useState<FinancialShortfallResponse | null>(null);
  const [shortfallError, setShortfallError] = useState<string | null>(null);

  // Active navigation tab
  const [activeTab, setActiveTab] = useState<SectionKey>("cash_flow");

  // Model 2: Financial Goals loaded from the authenticated backend.
  const [goalsList, setGoalsList] = useState<GoalFeasibilityItem[]>([]);
  const [goalsLoading, setGoalsLoading] = useState(true);
  const [goalsError, setGoalsError] = useState<string | null>(null);
  const [goalsReloadKey, setGoalsReloadKey] = useState(0);
  const [goalSaving, setGoalSaving] = useState(false);
  const [goalFormError, setGoalFormError] = useState<string | null>(null);
  const [goalSuccess, setGoalSuccess] = useState<string | null>(null);

  // Model 2: Selected Goal for detailed preview
  const [selectedGoalId, setSelectedGoalId] = useState<string>("");
  const [goalPlanInputs, setGoalPlanInputs] = useState<Record<string, string>>({});
  const [selectedCategoryAdjustments, setSelectedCategoryAdjustments] = useState<Record<string, string[]>>({});
  const [selectedGoalSubIds, setSelectedGoalSubIds] = useState<Record<string, string[]>>({});
  const [savingPlanGoalId, setSavingPlanGoalId] = useState<string | null>(null);

  // Model 2: Add Goal Modal State
  const [addGoalModalOpen, setAddGoalModalOpen] = useState(false);
  const [newGoalTitle, setNewGoalTitle] = useState("");
  const [newGoalAmount, setNewGoalAmount] = useState("");
  const [newGoalCategory, setNewGoalCategory] = useState("Work & Tech");
  const [newGoalMonths, setNewGoalMonths] = useState<number>(12);
  const [newGoalCustomDate, setNewGoalCustomDate] = useState("");
  const [goalPreview, setGoalPreview] = useState<Awaited<ReturnType<typeof goalsApi.evaluate>> | null>(null);

  // Model 3: Selected Subscriptions to simulate cancellation (starts with zero selected)
  const [cancelledSubIds, setCancelledSubIds] = useState<string[]>([]);
  const [subscriptions, setSubscriptions] = useState<SubscriptionItem[]>([]);
  const [subscriptionsError, setSubscriptionsError] = useState<string | null>(null);
  const [batchSimulation, setBatchSimulation] = useState<BatchCancellationSimulationResponse | null>(null);

  // Section references for smooth scrolling
  const cashFlowRef = useRef<HTMLDivElement>(null);
  const goalsRef = useRef<HTMLDivElement>(null);
  const subsRef = useRef<HTMLDivElement>(null);
  const shortfallRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const token = getStoredAccessToken();
    if (!token || !user.financial_user_id) {
      onUnauthorized();
      return;
    }

    setLoading(true);
    setError(null);

    Promise.allSettled([
      userTransactionApi.list(user.financial_user_id, token),
      commitmentApi.exposure(user.financial_user_id, token),
      forecastApi.cashFlow(user.financial_user_id, token),
      commitmentApi.recurringPayments(token, { status: "active" }),
      goalsApi.list(token),
      shortfallApi.get(user.financial_user_id, token),
      dashboardApi.history(token),
    ])
      .then(([txRes, expRes, forecastRes, recurringRes, goalsRes, shortfallRes, historyRes]) => {
        const results = [txRes, expRes, forecastRes, recurringRes, goalsRes, shortfallRes, historyRes];
        if (results.some((result) =>
          result.status === "rejected" &&
          result.reason instanceof ApiError &&
          result.reason.status === 401
        )) {
          onUnauthorized();
          return;
        }

        if (txRes.status === "fulfilled" && txRes.value.length === 0) {
          setEmpty(true);
          return;
        }

        if (expRes.status === "fulfilled") {
          setExposureData(expRes.value);
        }
        if (forecastRes.status === "fulfilled") setForecastData(forecastRes.value);
        if (recurringRes.status === "fulfilled") {
          const subs = recurringRes.value.items
            .filter((item) => item.category.toLowerCase() === "subscription")
            .map((item) => ({
              id: String(item.id),
              name: item.name,
              category: item.category,
              monthlyAmount: item.monthly_equivalent_amount,
              transactionSignal: item.transactional_engagement_explanation ?? "Payment history is insufficient to evaluate transactional engagement.",
              engagementStatus: mapEngagementStatus(item.transactional_engagement_status),
              nextBillingDate: item.next_expected_date ?? "Not available",
            }));
          setSubscriptions(subs);
          setSubscriptionsError(null);
          // Preserve valid user selections if already made; otherwise start with zero selected subscriptions
          setCancelledSubIds((prev) => prev.filter((id) => subs.some((s) => s.id === id)));
        } else {
          setSubscriptions([]);
          setSubscriptionsError("Unable to load active subscriptions. Please try again.");
          setCancelledSubIds([]);
        }
        if (goalsRes.status === "fulfilled") {
          const mapped = goalsRes.value.items.map(mapGoal);
          setGoalsList(mapped);
          setSelectedGoalId((current) => mapped.some((goal) => goal.id === current) ? current : (mapped[0]?.id ?? ""));
          setGoalsError(null);
        } else {
          setGoalsList([]);
          setSelectedGoalId("");
          setGoalsError("Unable to load your saved goals. Please try again.");
        }
        setGoalsLoading(false);
        if (shortfallRes.status === "fulfilled") {
          setShortfallData(shortfallRes.value);
          setShortfallError(null);
        } else {
          setShortfallData(null);
          setShortfallError("Unable to load shortfall prediction. Please try again.");
        }
        if (historyRes.status === "fulfilled") setHistoryData(historyRes.value);
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) onUnauthorized();
        else setError("Unable to load financial intelligence.");
      })
      .finally(() => setLoading(false));
  }, [user.financial_user_id, onUnauthorized, goalsReloadKey]);

  // Jump to section handler
  const scrollToSection = (key: SectionKey) => {
    setActiveTab(key);
    const refMap: Record<SectionKey, React.RefObject<HTMLDivElement>> = {
      cash_flow: cashFlowRef,
      goals: goalsRef,
      subscriptions: subsRef,
      shortfall: shortfallRef,
    };
    const target = refMap[key]?.current;
    if (target) {
      target.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
    }
  };

  // Derive cash values, prioritizing real user capacity/commitments
  const cashValues = useMemo(() => ({
    income: forecastData?.expected_income ?? 0,
    committed: forecastData?.expected_committed_expenses ?? 0,
    variable: forecastData?.expected_variable_expenses ?? 0,
    netCash: forecastData?.expected_net_cash ?? 0,
  }), [forecastData]);

  useEffect(() => {
    const token = getStoredAccessToken();
    if (!token) {
      setBatchSimulation(null);
      return;
    }
    commitmentApi.simulateBatchCancellation(token, {
      recurring_payment_ids: cancelledSubIds.map(Number),
      goal_id: selectedGoalId ? Number(selectedGoalId) : undefined,
    })
      .then(setBatchSimulation)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) onUnauthorized();
        else setBatchSimulation(null);
      });
  }, [cancelledSubIds, selectedGoalId, onUnauthorized]);

  // Cancellation results come from the authoritative backend Model 3 batch simulation endpoint.
  const subSimulation = useMemo(() => {
    const monthlySaving = batchSimulation?.monthly_savings ?? 0;
    const annualSaving = batchSimulation?.annual_potential_savings ?? 0;
    const currentCommitments = batchSimulation?.current_total_monthly_commitments
      ?? exposureData?.current_financial_status?.monthly_total_commitments
      ?? 0;
    const updatedCommitments = batchSimulation?.projected_total_monthly_commitments ?? currentCommitments;
    const updatedNetCash = batchSimulation?.projected_available_cash ?? cashValues.netCash;
    const goalImpact = batchSimulation?.goal_impact ?? null;

    return {
      selectedCount: cancelledSubIds.length,
      monthlySaving,
      annualSaving,
      currentCommitments,
      updatedCommitments,
      updatedNetCash,
      goalImpact,
    };
  }, [batchSimulation, cancelledSubIds.length, cashValues.netCash, exposureData]);

  const toggleSubCancellation = (id: string) => {
    setCancelledSubIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  useEffect(() => {
    const token = getStoredAccessToken();
    const amount = parseGoalAmount(newGoalAmount);
    if (!token || !addGoalModalOpen || amount === null) {
      setGoalPreview(null);
      return;
    }
    void goalsApi.evaluate({ goal_amount: amount, timeframe_months: newGoalMonths }, token)
      .then(setGoalPreview)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) onUnauthorized();
        else setGoalPreview(null);
      });
  }, [addGoalModalOpen, newGoalAmount, newGoalMonths, onUnauthorized]);

  // Model 2: Live preview for Add Goal modal
  const livePreview = useMemo(() => {
    const amt = parseGoalAmount(newGoalAmount) ?? 0;
    return {
      amt,
      req: goalPreview?.required_monthly_saving ?? 0,
      exp: goalPreview?.expected_monthly_saving ?? 0,
      addl: goalPreview?.additional_monthly_saving_required ?? 0,
      achievable: goalPreview?.goal_feasible ?? false,
      months: goalPreview?.goal_months ?? newGoalMonths,
    };
  }, [goalPreview, newGoalAmount, newGoalMonths]);

  // Model 2: Add Goal submit handler
  const handleAddGoalSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const title = newGoalTitle.trim();
    const cleanAmount = parseGoalAmount(newGoalAmount);
    if (!title) {
      setGoalFormError("Enter a meaningful goal name.");
      return;
    }
    if (cleanAmount === null) {
      setGoalFormError("Enter a positive target amount.");
      return;
    }

    let months = newGoalMonths;
    let targetDateStr = "";

    if (newGoalCustomDate) {
      const parts = newGoalCustomDate.split("-");
      if (parts.length === 2) {
        const year = parseInt(parts[0], 10);
        const month = parseInt(parts[1], 10) - 1;
        const targetD = new Date(year, month, 1);
        const now = new Date();
        months = Math.max(
          1,
          (targetD.getFullYear() - now.getFullYear()) * 12 + (targetD.getMonth() - now.getMonth())
        );
        targetDateStr = targetD.toLocaleDateString("en-US", { month: "long", year: "numeric" });
      }
    }

    if (!targetDateStr) {
      const targetD = new Date();
      targetD.setMonth(targetD.getMonth() + months);
      targetDateStr = targetD.toLocaleDateString("en-US", { month: "long", year: "numeric" });
    }

    if (!Number.isInteger(months) || months < 1 || months > 600) {
      setGoalFormError("Choose a valid timeframe between 1 and 600 months.");
      return;
    }
    const token = getStoredAccessToken();
    if (!token) return onUnauthorized();
    setGoalSaving(true);
    setGoalFormError(null);
    try {
      await goalsApi.create({ goal_name: title, goal_amount: cleanAmount, timeframe_months: months }, token);
      const refreshed = await goalsApi.list(token);
      const mapped = refreshed.items.map(mapGoal);
      setGoalsList(mapped);
      setSelectedGoalId(mapped[0]?.id ?? "");
      setGoalSuccess(`Saved “${title}”.`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) onUnauthorized();
      else setGoalFormError(err instanceof Error ? err.message : "Unable to save the goal.");
      return;
    } finally {
      setGoalSaving(false);
    }

    // Reset and close modal
    setNewGoalTitle("");
    setNewGoalAmount("");
    setNewGoalCustomDate("");
    setNewGoalMonths(12);
    setAddGoalModalOpen(false);
  };

  const handleDeleteUserGoal = async (id: string) => {
    const goal = goalsList.find((item) => item.id === id);
    if (!window.confirm(`Delete ${goal?.title ?? "this goal"}?`)) return;
    const token = getStoredAccessToken();
    if (!token) return onUnauthorized();
    try {
      await goalsApi.deactivate(Number(id), token);
      const refreshed = await goalsApi.list(token);
      const nextList = refreshed.items.map(mapGoal);
      setGoalsList(nextList);
      if (selectedGoalId === id) setSelectedGoalId(nextList[0]?.id ?? "");
      setGoalSuccess("Goal deleted.");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) onUnauthorized();
      else setGoalsError(err instanceof Error ? err.message : "Unable to delete the goal.");
    }
  };

  const saveMonthlyPlan = async (goal: GoalFeasibilityItem, value: string) => {
    if (!goal.isForecastAvailable || goal.expectedMonthlySaving === null) {
      setGoalsError("A monthly savings plan requires an available cash-flow forecast.");
      return;
    }
    const contribution = parseGoalAmount(value);
    if (contribution === null && value.trim() !== "0") {
      setGoalsError("Enter a valid non-negative monthly contribution.");
      return;
    }
    const safeContribution = contribution ?? 0;
    if (safeContribution > Math.max(goal.expectedMonthlySaving, 0)) {
      setGoalsError(`Planned contribution cannot exceed available net-cash capacity (${money(goal.expectedMonthlySaving)}).`);
      return;
    }
    if (goal.expectedMonthlySaving <= 0 && safeContribution > 0) {
      setGoalsError("Cannot allocate a monthly savings plan when net-cash capacity is zero or negative.");
      return;
    }
    const token = getStoredAccessToken();
    if (!token) return onUnauthorized();
    setSavingPlanGoalId(goal.id);
    setGoalsError(null);
    try {
      const updated = await goalsApi.update(Number(goal.id), { planned_monthly_contribution: safeContribution }, token);
      const mapped = mapGoal(updated);
      setGoalsList((current) => current.map((item) => item.id === mapped.id ? mapped : item));
      setGoalPlanInputs((prev) => ({ ...prev, [goal.id]: String(contribution ?? 0) }));
      setGoalSuccess(`Monthly savings plan saved for “${goal.title}”.`);
      setTimeout(() => setGoalSuccess(null), 4000);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) onUnauthorized();
      else setGoalsError(err instanceof Error ? err.message : "Unable to update the monthly savings plan.");
    } finally {
      setSavingPlanGoalId(null);
    }
  };

  if (loading) {
    return (
      <div className="min-h-[70vh] flex items-center justify-center p-6">
        <div className="flex flex-col items-center gap-3">
          <Loader2 size={24} className="text-indigo-400 animate-spin" />
          <p className="text-sm font-medium text-slate-400">Loading Financial Intelligence…</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-[70vh] flex items-center justify-center p-6">
        <div className="max-w-md w-full p-8 rounded-2xl bg-[#0d1322] border border-rose-500/20 text-center space-y-4">
          <div className="w-12 h-12 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 mx-auto flex items-center justify-center">
            <AlertTriangle size={20} />
          </div>
          <h2 className="text-base font-bold text-white">Intelligence Unavailable</h2>
          <p className="text-xs text-slate-400">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition-all"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (empty) {
    return (
      <div className="min-h-[70vh] flex items-center justify-center p-6">
        <div className="max-w-md w-full p-8 rounded-2xl bg-[#0d1322] border border-white/10 text-center space-y-4">
          <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 mx-auto flex items-center justify-center">
            <Info size={20} />
          </div>
          <h2 className="text-lg font-bold text-white">Upload Statements for Intelligence</h2>
          <p className="text-xs text-slate-400 leading-relaxed">
            Financial intelligence requires transaction history to project upcoming cash flow, test goal feasibility, review subscriptions, and detect shortfall risks.
          </p>
        </div>
      </div>
    );
  }

  const selectedGoal =
    goalsList.find((g) => g.id === selectedGoalId) ||
    goalsList[0] || {
      id: "",
      title: "No active goals",
      targetAmount: 0,
      currentSaved: 0,
      targetDate: "Unavailable",
      months: 12,
      requiredMonthlySaving: 0,
      expectedMonthlySaving: 0,
      additionalMonthlyNeeded: 0,
      plannedMonthlyContribution: null,
      plannedRemaining: null,
      planGap: null,
      status: "Needs adjustment" as const,
      category: "Unavailable",
      isForecastAvailable: true,
      availabilityStatus: "available",
      explanation: "",
      discretionaryAdjustments: [],
    };

  return (
    <div className="min-h-full bg-[#070b14] text-slate-100 pb-24 selection:bg-indigo-500/30 selection:text-white">
      <div className="w-full max-w-[1400px] mx-auto px-5 sm:px-8 lg:px-10 py-6 sm:py-8 space-y-8">
        {/* ─────────────────────────────────────────────────────────────
            TOP SECTION: COMPACT TITLE & SUBTITLE
        ───────────────────────────────────────────────────────────── */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/[0.08] pb-5">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
              Financial Intelligence
            </h1>
            <p className="mt-1 text-xs sm:text-sm text-slate-400 leading-normal">
              Understand your upcoming cash flow, goals, recurring commitments and financial risk.
            </p>
          </div>

          <button
            onClick={() => onAskAssistant("Synthesize my financial intelligence outlook across cash flow, goals, and recurring commitments.")}
            className="inline-flex items-center gap-1.5 self-start sm:self-center px-3.5 py-1.5 rounded-full border border-white/10 bg-white/[0.04] hover:bg-white/[0.08] text-xs font-medium text-slate-200 transition-colors"
          >
            <MessageCircle size={13} className="text-indigo-400" />
            <span>Ask FinSight</span>
          </button>
        </div>

        {/* ─────────────────────────────────────────────────────────────
            MODEL NAVIGATION: SUBTLE & COMPACT SEGMENTED CONTROL
        ───────────────────────────────────────────────────────────── */}
        <div className="sticky top-0 z-20 bg-[#070b14]/90 backdrop-blur-md py-2 border-b border-white/[0.06]">
          <div className="flex items-center gap-1.5 overflow-x-auto scrollbar-none">
            {[
              { key: "cash_flow" as const, label: "Cash Flow", sub: "How much will I have?" },
              { key: "goals" as const, label: "Goals", sub: "Can I achieve my goal?" },
              { key: "subscriptions" as const, label: "Subscriptions", sub: "What could I save?" },
              { key: "shortfall" as const, label: "Shortfall", sub: "Will I run short?" },
            ].map((item) => {
              const active = activeTab === item.key;
              return (
                <button
                  key={item.key}
                  onClick={() => scrollToSection(item.key)}
                  className={`px-3.5 py-2 rounded-xl text-xs transition-all flex items-center gap-2 shrink-0 ${
                    active
                      ? "bg-white/[0.12] text-white border border-white/20 font-semibold shadow-sm"
                      : "text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]"
                  }`}
                >
                  <span>{item.label}</span>
                  <span className="hidden md:inline text-[10px] text-slate-400 font-normal">
                    · {item.sub}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* ─────────────────────────────────────────────────────────────
            SECTION 1: CASH FLOW FORECASTING
            "How much money will I likely have next month?"
        ───────────────────────────────────────────────────────────── */}
        <section ref={cashFlowRef} className="scroll-mt-16 space-y-6">
          {/* Section Header with stylized accent */}
          <div className="relative">
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-mono uppercase tracking-wider text-indigo-400 font-semibold">
                01 · CASH FLOW
              </span>
            </div>
            <div className="flex items-baseline gap-2.5 mt-0.5">
              <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
                Cash Flow <span className="bg-gradient-to-r from-indigo-400 to-sky-400 bg-clip-text text-transparent">Forecasting</span>
              </h2>
            </div>
            <p className="text-xs sm:text-sm text-slate-400 mt-0.5">
              How much money will I likely have next month?
            </p>

            {/* Decorative top-right wave glow */}
            <div className="pointer-events-none absolute -top-4 right-0 w-72 h-20 opacity-30 hidden md:block overflow-hidden">
              <svg viewBox="0 0 300 80" fill="none" className="w-full h-full stroke-indigo-500/40">
                <path d="M0 60 C 80 10, 160 80, 240 30 C 270 12, 290 25, 300 20" strokeWidth="2" strokeLinecap="round" />
                <path d="M0 70 C 90 25, 170 85, 250 40 C 280 22, 295 30, 300 28" strokeWidth="1" strokeDasharray="3 3" />
              </svg>
            </div>
          </div>

          {/* 4 Top KPI Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5 sm:gap-4">
            {/* Card 1: Expected Income */}
            <div className="relative overflow-hidden rounded-2xl border border-white/[0.08] bg-[#0c1220]/90 p-4 sm:p-5 flex flex-col justify-between hover:border-white/[0.14] transition-all">
              <div>
                <div className="flex items-center justify-between">
                  <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center">
                    <ArrowUp size={16} />
                  </div>
                  <span className="text-[11px] font-medium text-slate-400">Expected Income</span>
                </div>
                <div className="mt-3.5 flex items-baseline justify-between gap-2">
                  <p className="font-mono text-2xl sm:text-[26px] font-bold tracking-tight text-emerald-400">
                    {money(cashValues.income)}
                  </p>
                  {/* Subtle decorative sparkline wave */}
                  <svg className="w-16 h-7 text-emerald-400 shrink-0" viewBox="0 0 64 28" fill="none">
                    <path d="M2 20 C 14 22, 24 16, 34 12 C 44 8, 52 4, 62 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                  </svg>
                </div>
              </div>
              <p className="mt-3 text-[11px] text-slate-400">Primary recurring income</p>
            </div>

            {/* Card 2: Expected Committed Expenses */}
            <div className="relative overflow-hidden rounded-2xl border border-white/[0.08] bg-[#0c1220]/90 p-4 sm:p-5 flex flex-col justify-between hover:border-white/[0.14] transition-all">
              <div>
                <div className="flex items-center justify-between">
                  <div className="w-8 h-8 rounded-lg bg-purple-500/10 border border-purple-500/20 text-purple-400 flex items-center justify-center">
                    <Layers size={16} />
                  </div>
                  <span className="text-[11px] font-medium text-slate-400">Expected Committed Expenses</span>
                </div>
                <div className="mt-3.5 flex items-baseline justify-between gap-2">
                  <p className="font-mono text-2xl sm:text-[26px] font-bold tracking-tight text-purple-300">
                    {money(cashValues.committed)}
                  </p>
                  {/* Subtle decorative sparkline wave */}
                  <svg className="w-16 h-7 text-purple-400 shrink-0" viewBox="0 0 64 28" fill="none">
                    <path d="M2 18 C 16 22, 26 14, 38 18 C 48 22, 54 10, 62 8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                  </svg>
                </div>
              </div>
              <p className="mt-3 text-[11px] text-slate-400">EMIs, rent, subscriptions</p>
            </div>

            {/* Card 3: Expected Variable Expenses */}
            <div className="relative overflow-hidden rounded-2xl border border-white/[0.08] bg-[#0c1220]/90 p-4 sm:p-5 flex flex-col justify-between hover:border-white/[0.14] transition-all">
              <div>
                <div className="flex items-center justify-between">
                  <div className="w-8 h-8 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 flex items-center justify-center">
                    <CreditCard size={16} />
                  </div>
                  <span className="text-[11px] font-medium text-slate-400">Expected Variable Expenses</span>
                </div>
                <div className="mt-3.5 flex items-baseline justify-between gap-2">
                  <p className="font-mono text-2xl sm:text-[26px] font-bold tracking-tight text-amber-400">
                    {money(cashValues.variable)}
                  </p>
                  {/* Subtle decorative sparkline wave */}
                  <svg className="w-16 h-7 text-amber-400 shrink-0" viewBox="0 0 64 28" fill="none">
                    <path d="M2 22 C 16 20, 24 10, 36 12 C 48 14, 54 8, 62 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                  </svg>
                </div>
              </div>
              <p className="mt-3 text-[11px] text-slate-400">Groceries, dining, shopping, leisure</p>
            </div>

            {/* Card 4: Expected Net Cash */}
            <div className="relative overflow-hidden rounded-2xl border border-cyan-500/30 bg-gradient-to-br from-cyan-950/20 via-[#0c1220] to-[#0c1220] p-4 sm:p-5 flex flex-col justify-between hover:border-cyan-500/40 transition-all shadow-[0_0_24px_rgba(6,182,212,0.06)]">
              <div>
                <div className="flex items-center justify-between">
                  <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 flex items-center justify-center">
                    <LineChart size={16} />
                  </div>
                  <span className="text-[11px] font-medium text-cyan-300">Expected Net Cash</span>
                </div>
                <div className="mt-3.5 flex items-baseline justify-between gap-2">
                  <p className="font-mono text-2xl sm:text-[26px] font-bold tracking-tight text-cyan-400">
                    {money(cashValues.netCash)}
                  </p>
                  {/* Subtle decorative sparkline wave */}
                  <svg className="w-16 h-7 text-cyan-400 shrink-0" viewBox="0 0 64 28" fill="none">
                    <path d="M2 24 C 14 18, 28 20, 42 12 C 50 8, 56 6, 62 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                  </svg>
                </div>
              </div>
              <p className="mt-3 text-[11px] text-cyan-400 font-medium">Projected monthly buffer</p>
            </div>
          </div>

          {/* Main 2-Column Section: 6-Month Chart (Left) + Next Month Outlook (Right) */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-stretch">
            {/* Left: 6-Month Cash Flow Horizon Chart */}
            <div className="lg:col-span-8 rounded-2xl border border-white/[0.08] bg-[#0c1220]/90 p-5 sm:p-6 flex flex-col justify-between space-y-4">
              {/* Chart Header + Legend */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-white/[0.06]">
                <div>
                  <h3 className="text-sm sm:text-base font-bold text-white tracking-tight">
                    6-Month Cash Flow Horizon
                  </h3>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Past actuals compared to projected net balance
                  </p>
                </div>

                <div className="flex items-center gap-4 text-xs">
                  <div className="flex items-center gap-1.5 text-slate-300">
                    <span className="w-2.5 h-2.5 rounded-full bg-emerald-400" />
                    <span>Income</span>
                  </div>
                  <div className="flex items-center gap-1.5 text-slate-300">
                    <span className="w-2.5 h-2.5 rounded-full bg-purple-500" />
                    <span>Total Expenses</span>
                  </div>
                  <div className="flex items-center gap-1.5 text-slate-300">
                    <span className="w-3 h-0.5 bg-white" />
                    <span className="w-1.5 h-1.5 rounded-full bg-white -ml-2" />
                    <span className="ml-1">Net Cash</span>
                  </div>
                </div>
              </div>

              {/* Chart Body with SVG Coordinate Grid */}
              {(() => {
                // Map actual historical months (up to 5) + 1 forecast month if available
                const rawHist = (historyData?.points && historyData.points.length > 0)
                  ? historyData.points.slice(-5)
                  : [];

                const histPoints = rawHist.map((pt) => {
                  const dateObj = new Date(pt.month + "-01");
                  const monthLabel = !isNaN(dateObj.getTime())
                    ? dateObj.toLocaleDateString("en-US", { month: "short", year: "numeric" })
                    : pt.month;
                  // Authoritative total expenses = commitments + spending
                  const totalExpenses = (pt.commitments || 0) + (pt.spending || 0);
                  return {
                    month: pt.month,
                    label: monthLabel,
                    income: pt.income || 0,
                    totalExpenses: totalExpenses,
                    isForecast: false,
                  };
                });

                let forecastCol = null;
                if (forecastData?.forecast_available && forecastData?.forecast_month) {
                  const forecastMonthDate = new Date(forecastData.forecast_month + "-01");
                  const forecastLabel = !isNaN(forecastMonthDate.getTime())
                    ? forecastMonthDate.toLocaleDateString("en-US", { month: "short", year: "numeric" })
                    : forecastData.forecast_month;

                  const forecastIncome = forecastData.expected_income ?? (cashValues.income > 0 ? cashValues.income : 0);
                  const forecastTotalExpenses = forecastData.expected_total_expenses ?? ((cashValues.committed || 0) + (cashValues.variable || 0));

                  forecastCol = {
                    month: forecastData.forecast_month,
                    label: forecastLabel,
                    income: forecastIncome,
                    totalExpenses: forecastTotalExpenses,
                    isForecast: true,
                  };
                }

                const chartCols = forecastCol ? [...histPoints, forecastCol] : histPoints;

                if (chartCols.length === 0) {
                  return (
                    <div className="h-64 rounded-xl border border-white/[0.06] bg-white/[0.02] flex flex-col items-center justify-center p-6 text-center">
                      <LineChart size={28} className="text-slate-400 mb-2" />
                      <p className="text-sm font-semibold text-white">Cash flow horizon unavailable</p>
                      <p className="mt-1 text-xs text-slate-400 max-w-sm">
                        More transaction history is required to display your cash flow horizon and projections.
                      </p>
                    </div>
                  );
                }

                // Dynamically calculate Y-axis scale based on real financial values
                const allValues: number[] = [];
                chartCols.forEach((col) => {
                  allValues.push(col.income);
                  allValues.push(col.totalExpenses);
                  allValues.push(col.income - col.totalExpenses);
                });

                const rawMin = Math.min(0, ...allValues);
                const rawMax = Math.max(100000, ...allValues);

                // Round bounds nicely to standard 40k or appropriate magnitude steps
                const step = rawMax > 1000000 ? 500000 : rawMax > 400000 ? 100000 : 40000;
                const yMax = Math.ceil(rawMax / step) * step;
                const yMin = rawMin < 0 ? Math.floor(rawMin / step) * step : 0;
                const yRange = yMax - yMin;

                // Generate 4-5 evenly distributed tick marks from yMax down to yMin
                const numTicks = 5;
                const tickStep = (yMax - yMin) / (numTicks - 1);
                const yTicks = Array.from({ length: numTicks }, (_, i) => Math.round(yMax - i * tickStep));

                // Coordinate mapping for SVG (width 600, height 220)
                const chartSvgWidth = 600;
                const chartSvgHeight = 220;
                const padLeft = 70;
                const padRight = 30;
                const padTop = 15;
                const padBottom = 25;
                const plotWidth = chartSvgWidth - padLeft - padRight;
                const plotHeight = chartSvgHeight - padTop - padBottom;

                const getY = (val: number) => {
                  const clamped = Math.max(yMin, Math.min(yMax, val));
                  const ratio = (clamped - yMin) / yRange;
                  return padTop + plotHeight * (1 - ratio);
                };

                const getColCenterX = (index: number) => {
                  const step = plotWidth / chartCols.length;
                  return padLeft + step * index + step / 2;
                };

                // Compute Net Cash line coordinates
                const netPoints = chartCols.map((col, idx) => {
                  const netVal = col.income - col.totalExpenses;
                  return {
                    x: getColCenterX(idx),
                    y: getY(netVal),
                    val: netVal,
                  };
                });

                const linePath = netPoints.reduce((acc, pt, idx) => {
                  return idx === 0 ? `M ${pt.x} ${pt.y}` : `${acc} L ${pt.x} ${pt.y}`;
                }, "");

                const formatTick = (val: number) => {
                  if (val === 0) return "₹0";
                  const absVal = Math.abs(val);
                  const prefix = val < 0 ? "-₹" : "₹";
                  if (absVal >= 100000) {
                    const lk = absVal / 100000;
                    return `${prefix}${lk % 1 === 0 ? lk : lk.toFixed(1)}L`;
                  }
                  return `${prefix}${(absVal / 1000).toLocaleString("en-IN")}k`;
                };

                return (
                  <div className="relative w-full pt-2">
                    {/* SVG Chart Layer */}
                    <svg
                      viewBox={`0 0 ${chartSvgWidth} ${chartSvgHeight}`}
                      className="w-full h-52 sm:h-60 overflow-visible"
                    >
                      {/* Grid Lines & Y-Axis Labels */}
                      {yTicks.map((tick) => {
                        const yPos = getY(tick);
                        const isZero = tick === 0;
                        return (
                          <g key={tick}>
                            <text
                              x={padLeft - 10}
                              y={yPos + 4}
                              textAnchor="end"
                              className="fill-slate-500 font-mono text-[10px]"
                            >
                              {formatTick(tick)}
                            </text>
                            <line
                              x1={padLeft}
                              y1={yPos}
                              x2={chartSvgWidth - padRight}
                              y2={yPos}
                              stroke={isZero ? "rgba(255,255,255,0.18)" : "rgba(255,255,255,0.05)"}
                              strokeDasharray={isZero ? undefined : "3 3"}
                              strokeWidth={isZero ? 1.2 : 1}
                            />
                          </g>
                        );
                      })}

                      {/* Forecast Column Highlight Container */}
                      {chartCols[chartCols.length - 1]?.isForecast && (() => {
                        const fIndex = chartCols.length - 1;
                        const colWidth = plotWidth / chartCols.length;
                        const colLeft = padLeft + colWidth * fIndex + 2;
                        return (
                          <g>
                            {/* Glowing rounded container for forecast */}
                            <rect
                              x={colLeft}
                              y={padTop - 5}
                              width={colWidth - 4}
                              height={plotHeight + 35}
                              rx={10}
                              fill="rgba(56, 189, 248, 0.05)"
                              stroke="rgba(56, 189, 248, 0.2)"
                              strokeWidth={1}
                            />
                            {/* "Forecast" Pill Badge at the top of the container */}
                            <g transform={`translate(${colLeft + (colWidth - 4) / 2 - 26}, ${padTop + 2})`}>
                              <rect
                                width={52}
                                height={18}
                                rx={9}
                                fill="rgba(30, 41, 59, 0.9)"
                                stroke="rgba(56, 189, 248, 0.3)"
                                strokeWidth={1}
                              />
                              <text
                                x={26}
                                y={12}
                                textAnchor="middle"
                                className="fill-sky-300 font-sans font-medium text-[9px]"
                              >
                                Forecast
                              </text>
                            </g>
                          </g>
                        );
                      })()}

                      {/* Dual Bars for Each Month */}
                      {chartCols.map((col, idx) => {
                        const centerX = getColCenterX(idx);
                        const barWidth = 14;
                        const barGap = 3;
                        const yZero = getY(0);

                        // Inflow (Emerald) bar
                        const incomeY = getY(col.income);
                        const incomeHeight = Math.max(2, yZero - incomeY);
                        const incomeX = centerX - barWidth - barGap / 2;

                        // Outflow (Purple) bar
                        const expenseY = getY(col.totalExpenses);
                        const expenseHeight = Math.max(2, yZero - expenseY);
                        const expenseX = centerX + barGap / 2;

                        return (
                          <g key={col.month}>
                            {/* Income Bar (Emerald with glow) */}
                            <rect
                              x={incomeX}
                              y={incomeY}
                              width={barWidth}
                              height={incomeHeight}
                              rx={2}
                              fill="#10b981"
                              opacity={0.9}
                            />
                            {/* Expense Bar (Purple) */}
                            <rect
                              x={expenseX}
                              y={expenseY}
                              width={barWidth}
                              height={expenseHeight}
                              rx={2}
                              fill="#a855f7"
                              opacity={col.isForecast ? 0.95 : 0.8}
                            />
                          </g>
                        );
                      })}

                      {/* Net Cash Connecting Line (White with subtle shadow) */}
                      <path
                        d={linePath}
                        fill="none"
                        stroke="#ffffff"
                        strokeWidth={2.5}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />

                      {/* Net Cash Data Points (White dots) */}
                      {netPoints.map((pt, idx) => (
                        <circle
                          key={idx}
                          cx={pt.x}
                          cy={pt.y}
                          r={idx === netPoints.length - 1 ? 4.5 : 3.5}
                          fill="#ffffff"
                          stroke={idx === netPoints.length - 1 ? "#38bdf8" : "#0c1220"}
                          strokeWidth={2}
                        />
                      ))}
                    </svg>

                    {/* Month Labels & Subtitles underneath */}
                    <div
                      className="grid pt-2 text-center"
                      style={{
                        gridTemplateColumns: `repeat(${chartCols.length}, minmax(0, 1fr))`,
                        paddingLeft: "11%",
                        paddingRight: "5%",
                      }}
                    >
                      {chartCols.map((col) => (
                        <div key={col.month} className="flex flex-col items-center">
                          <span className={`text-[11px] font-medium ${col.isForecast ? "text-sky-300 font-semibold" : "text-slate-300"}`}>
                            {col.label}
                          </span>
                          <span className={`text-[10px] ${col.isForecast ? "text-sky-400 font-medium" : "text-slate-500"}`}>
                            {col.isForecast ? "Forecast" : "Actual"}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })()}
            </div>

            {/* Right: Next Month Outlook Panel */}
            <div className="lg:col-span-4 rounded-2xl border border-white/[0.08] bg-[#0c1220]/90 p-5 sm:p-6 flex flex-col justify-between space-y-4">
              <div>
                <h3 className="text-sm sm:text-base font-bold text-white tracking-tight">
                  Next Month Outlook
                </h3>
                <p className="mt-2 text-xs text-slate-300 leading-relaxed">
                  Based on your recent income, spending and recurring commitments, your expected net cash for next month is{" "}
                  <strong className="text-cyan-400 font-mono font-bold">
                    {money(cashValues.netCash)}
                  </strong>.
                </p>

                {/* Driver summary header */}
                <h4 className="mt-5 text-xs font-semibold text-slate-200">
                  What changes this?
                </h4>

                {/* 3 Driver Rows */}
                <div className="mt-3 space-y-2.5">
                  {/* Driver 1: Income trend */}
                  <div className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.06] flex items-center justify-between gap-3 hover:border-white/10 transition-all">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center shrink-0">
                        <ArrowUp size={15} />
                      </div>
                      <div className="min-w-0">
                        <p className="text-xs font-semibold text-white truncate">Income trend</p>
                        <p className="text-[11px] text-slate-400 truncate">Authoritative Model 1 forecast</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0">
                      <span className="font-mono text-xs font-bold text-slate-100">
                        {money(cashValues.income)}
                      </span>
                      <ChevronRight size={14} className="text-slate-500" />
                    </div>
                  </div>

                  {/* Driver 2: Recurring commitments */}
                  <div className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.06] flex items-center justify-between gap-3 hover:border-white/10 transition-all">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-8 h-8 rounded-lg bg-purple-500/10 border border-purple-500/20 text-purple-400 flex items-center justify-center shrink-0">
                        <Layers size={15} />
                      </div>
                      <div className="min-w-0">
                        <p className="text-xs font-semibold text-white truncate">Recurring commitments</p>
                        <p className="text-[11px] text-slate-400 truncate">From active EMIs, subscriptions, bills</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0">
                      <span className="font-mono text-xs font-bold text-slate-100">
                        {money(cashValues.committed)}
                      </span>
                      <ChevronRight size={14} className="text-slate-500" />
                    </div>
                  </div>

                  {/* Driver 3: Variable spending */}
                  <div className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.06] flex items-center justify-between gap-3 hover:border-white/10 transition-all">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-8 h-8 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 flex items-center justify-center shrink-0">
                        <CreditCard size={15} />
                      </div>
                      <div className="min-w-0">
                        <p className="text-xs font-semibold text-white truncate">Variable spending</p>
                        <p className="text-[11px] text-slate-400 truncate">Expected discretionary expenses</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0">
                      <span className="font-mono text-xs font-bold text-slate-100">
                        {money(cashValues.variable)}
                      </span>
                      <ChevronRight size={14} className="text-slate-500" />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Key Takeaway Banner */}
          <div className="rounded-2xl border border-amber-500/20 bg-gradient-to-r from-amber-500/10 via-[#0c1220] to-[#0c1220] p-4 sm:p-5 flex items-start sm:items-center gap-3.5">
            <div className="w-9 h-9 rounded-xl bg-amber-500/20 border border-amber-500/30 text-amber-400 flex items-center justify-center shrink-0 mt-0.5 sm:mt-0 shadow-[0_0_12px_rgba(245,158,11,0.2)]">
              <Lightbulb size={18} />
            </div>
            <div className="min-w-0">
              <span className="text-xs font-bold text-amber-300 uppercase tracking-wide">
                Key Takeaway
              </span>
              <p className="text-xs sm:text-[13px] text-slate-300 mt-0.5 leading-relaxed">
                You are expected to have{" "}
                <strong className="text-cyan-400 font-mono font-bold">{money(cashValues.netCash)}</strong> as
                net cash next month, assuming your income and spending patterns remain similar to recent months.
              </p>
            </div>
          </div>
        </section>

        {/* ─────────────────────────────────────────────────────────────
            SECTION 2: GOAL FEASIBILITY
            "Can I realistically achieve my financial goal?"
        ───────────────────────────────────────────────────────────── */}
        <section ref={goalsRef} className="scroll-mt-16 space-y-5">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-mono uppercase tracking-wider text-purple-400 font-semibold">
                02 · Goal Feasibility
              </span>
            </div>
            <h2 className="text-xl sm:text-2xl font-bold text-white tracking-tight mt-0.5">
              Goal Feasibility
            </h2>
            <p className="text-xs sm:text-sm text-slate-400 mt-0.5">
              Can I realistically achieve my financial goal?
            </p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
            {/* Goal Cards List (Left 5 Cols on lg, 4 on xl, sticky for balanced vertical parity) */}
            <div className="lg:col-span-5 xl:col-span-4 space-y-3 lg:sticky lg:top-24">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <span className="text-xs font-semibold text-slate-300">Select Goal to Inspect</span>
                  {goalsList.length > 0 && (
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded-full bg-white/[0.05] border border-white/[0.08] text-slate-400 font-medium">
                      {goalsList.length}
                    </span>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => setAddGoalModalOpen(true)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-purple-600/20 hover:bg-purple-600/30 border border-purple-500/30 text-purple-300 hover:text-white text-xs font-semibold transition-all shadow-sm"
                >
                  <Plus size={13} />
                  <span>Add Goal</span>
                </button>
              </div>

              {goalSuccess && <p role="status" className="text-xs text-emerald-400">{goalSuccess}</p>}
              {goalsError ? (
                <div role="alert" className="rounded-xl border border-rose-500/20 bg-rose-500/10 p-4 text-xs text-rose-300 space-y-3">
                  <p>{goalsError}</p>
                  <button type="button" onClick={() => setGoalsReloadKey((value) => value + 1)} className="rounded-lg border border-rose-400/30 px-3 py-1.5 font-semibold text-rose-200 hover:bg-rose-500/10">Retry</button>
                </div>
              ) : goalsLoading ? (
                <div className="rounded-2xl border border-white/[0.08] bg-[#0d1322]/80 p-5 text-xs text-slate-400">Loading saved goals…</div>
              ) : goalsList.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-white/15 bg-[#0d1322]/60 p-5 text-sm text-slate-400">
                  No saved goals yet. Add a goal to evaluate it against your forecast.
                </div>
              ) : goalsList.map((g) => {
                const isSelected = g.id === selectedGoal.id;

                return (
                  <div
                    key={g.id}
                    onClick={() => setSelectedGoalId(g.id)}
                    className={`p-3.5 sm:p-4 rounded-2xl border cursor-pointer transition-all ${
                      isSelected
                        ? "bg-purple-950/25 border-purple-500/50 shadow-sm ring-1 ring-purple-500/30"
                        : "bg-[#0d1322]/80 border-white/[0.08] hover:border-white/20"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="text-sm font-bold text-white tracking-tight truncate">{g.title}</span>
                        {g.isUserAdded && (
                          <span className="text-[9px] uppercase tracking-wider font-mono px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-semibold shrink-0">
                            Custom
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0">
                        <span
                          className={`text-[10px] font-mono px-2 py-0.5 rounded-full border font-semibold ${
                            g.status === "Achievable"
                              ? "bg-emerald-500/15 border-emerald-500/25 text-emerald-400"
                              : g.plannedMonthlyContribution !== null && (g.plannedMonthlyContribution ?? 0) > 0
                              ? "bg-cyan-500/15 border-cyan-500/25 text-cyan-300"
                              : "bg-amber-500/15 border-amber-500/25 text-amber-400"
                          }`}
                        >
                          {g.status === "Achievable"
                            ? (g.plannedMonthlyContribution !== null && (g.plannedMonthlyContribution ?? 0) >= g.requiredMonthlySaving ? "Funded" : "Achievable")
                            : g.plannedMonthlyContribution !== null && (g.plannedMonthlyContribution ?? 0) > 0
                            ? "Plan Active"
                            : "Needs Plan"}
                        </span>
                        {g.isUserAdded && (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDeleteUserGoal(g.id);
                            }}
                            className="p-1 rounded hover:bg-rose-500/20 text-slate-400 hover:text-rose-400 transition-colors"
                            title="Delete goal"
                          >
                            <Trash2 size={13} />
                          </button>
                        )}
                      </div>
                    </div>

                    <div className="mt-2 flex items-center justify-between text-xs text-slate-400 font-mono">
                      <span>Target: {money(g.targetAmount)}</span>
                      <span>Timeframe: {g.targetDate}</span>
                    </div>

                    <div className="mt-2.5 pt-2.5 border-t border-white/[0.06] grid grid-cols-2 gap-2 text-[11px] font-mono">
                      <div>
                        <span className="text-slate-400 block text-[10px]">Required saving</span>
                        <span className="text-white font-semibold">{money(g.requiredMonthlySaving)}/mo</span>
                      </div>
                      <div>
                        <span className="text-slate-400 block text-[10px]">Net-cash capacity</span>
                        <span className="text-emerald-400 font-semibold">{money(g.expectedMonthlySaving)}/mo</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Goal Breakdown & Feasibility Result (Right 7 Cols on lg, 8 on xl) */}
            <div className="lg:col-span-7 xl:col-span-8 rounded-2xl border border-white/[0.08] bg-[#0d1322]/80 p-5 sm:p-6 space-y-5">
              {goalsError ? (
                <div className="py-12 text-center text-sm text-rose-300">
                  Saved goals are unavailable. Retry loading them to continue.
                </div>
              ) : !goalsLoading && goalsList.length === 0 ? (
                <div className="py-12 text-center text-sm text-slate-400">
                  Select “Add Goal” to create your first saved goal.
                </div>
              ) : (() => {
                // Interactive Plan computations for selectedGoal
                const isBaselineAchievable = selectedGoal.status === "Achievable" || (
                  selectedGoal.expectedMonthlySaving > 0 &&
                  selectedGoal.expectedMonthlySaving >= selectedGoal.requiredMonthlySaving
                );
                const defaultBaselineContribution = isBaselineAchievable
                  ? selectedGoal.requiredMonthlySaving
                  : Math.max(selectedGoal.expectedMonthlySaving, 0);

                const currentPlanDraft = goalPlanInputs[selectedGoal.id] !== undefined
                  ? goalPlanInputs[selectedGoal.id]
                  : (selectedGoal.plannedMonthlyContribution !== null && selectedGoal.plannedMonthlyContribution !== undefined
                    ? String(selectedGoal.plannedMonthlyContribution)
                    : "");
                const hasUserPlanInput = currentPlanDraft.trim() !== "";
                const hasPersistedPlan = selectedGoal.plannedMonthlyContribution !== null && selectedGoal.plannedMonthlyContribution !== undefined;

                const effectivePlanContribution = hasUserPlanInput
                  ? Number(currentPlanDraft.replace(/,/g, ""))
                  : (hasPersistedPlan ? (selectedGoal.plannedMonthlyContribution ?? 0) : defaultBaselineContribution);

                const userPlannedContribution = Math.min(
                  Math.max(Number.isFinite(effectivePlanContribution) ? effectivePlanContribution : 0, 0),
                  Math.max(selectedGoal.expectedMonthlySaving, 0)
                );
                const remainingCapacityAfterPlan = Math.max(selectedGoal.expectedMonthlySaving - userPlannedContribution, 0);
                const remainingGapAfterPlan = Math.max(selectedGoal.requiredMonthlySaving - userPlannedContribution, 0);

                // Category Adjustments selections
                const activeCategories = selectedCategoryAdjustments[selectedGoal.id] ?? (
                  selectedGoal.discretionaryAdjustments?.filter((a) => a.suggestedReduction > 0).map((a) => a.category) ?? []
                );
                const activeCategorySavings = (selectedGoal.discretionaryAdjustments ?? [])
                  .filter((a) => activeCategories.includes(a.category))
                  .reduce((sum, a) => sum + a.suggestedReduction, 0);

                // Subscription Review Candidates from Model 3 (Eligible only)
                const candidateSubs = subscriptions.filter(
                  (s) => s.engagementStatus === "Under-utilized" || s.engagementStatus === "Moderate"
                );
                const activeGoalSubIds = selectedGoalSubIds[selectedGoal.id] ?? (
                  candidateSubs.filter((s) => s.engagementStatus === "Under-utilized").map((s) => s.id)
                );
                const activeSubscriptionSavings = candidateSubs
                  .filter((s) => activeGoalSubIds.includes(s.id))
                  .reduce((sum, s) => sum + s.monthlyAmount, 0);

                // Combined Plan calculations
                const totalCombinedMonthlySavings = Math.round(
                  userPlannedContribution + activeCategorySavings + activeSubscriptionSavings
                );
                const isCombinedFeasible = totalCombinedMonthlySavings >= selectedGoal.requiredMonthlySaving;
                const combinedRemainingGap = Math.max(selectedGoal.requiredMonthlySaving - totalCombinedMonthlySavings, 0);
                const combinedSurplus = Math.max(totalCombinedMonthlySavings - selectedGoal.requiredMonthlySaving, 0);
                const projectedMonths = totalCombinedMonthlySavings > 0
                  ? Math.ceil(selectedGoal.targetAmount / totalCombinedMonthlySavings)
                  : null;

                return (
                  <>
                    {/* Header */}
                    <div className="flex items-center justify-between pb-3 border-b border-white/[0.06]">
                      <div>
                        <h3 className="text-base font-bold text-white flex items-center gap-2">
                          <Target size={18} className="text-purple-400" />
                          <span>{selectedGoal.title}</span>
                        </h3>
                        <p className="text-xs text-slate-400 mt-0.5">
                          Target: {money(selectedGoal.targetAmount)} in {selectedGoal.targetDate}
                        </p>
                      </div>
                      {/* Status Badge reflecting actual persisted goal and plan state */}
                      {(() => {
                        const hasPersistedPlan = selectedGoal.plannedMonthlyContribution !== null && selectedGoal.plannedMonthlyContribution > 0;
                        const planCovers = hasPersistedPlan && (selectedGoal.plannedMonthlyContribution ?? 0) >= selectedGoal.requiredMonthlySaving;
                        const hasRemainingGap = remainingGapAfterPlan > 0;

                        if (isCombinedFeasible && (activeCategorySavings > 0 || activeSubscriptionSavings > 0)) {
                          return (
                            <span className="text-xs font-mono font-bold px-3 py-1 rounded-full border bg-emerald-500/15 border-emerald-500/30 text-emerald-400">
                              Achievable with Combined Plan
                            </span>
                          );
                        }
                        if (planCovers) {
                          return (
                            <span className="text-xs font-mono font-bold px-3 py-1 rounded-full border bg-emerald-500/15 border-emerald-500/30 text-emerald-400">
                              Fully Funded via Savings Plan
                            </span>
                          );
                        }
                        if (selectedGoal.status === "Achievable" && !hasPersistedPlan) {
                          return (
                            <span className="text-xs font-mono font-bold px-3 py-1 rounded-full border bg-emerald-500/15 border-emerald-500/30 text-emerald-400">
                              Achievable on Current Cash Flow
                            </span>
                          );
                        }
                        if (hasPersistedPlan) {
                          return (
                            <span className="text-xs font-mono font-bold px-3 py-1 rounded-full border bg-cyan-500/15 border-cyan-500/30 text-cyan-300">
                              {hasRemainingGap ? `Plan Active · ${money(remainingGapAfterPlan)} Gap` : "Plan Active · Fully Covered"}
                            </span>
                          );
                        }
                        return (
                          <span className="text-xs font-mono font-bold px-3 py-1 rounded-full border bg-amber-500/15 border-amber-500/30 text-amber-400">
                            Needs Spending Plan
                          </span>
                        );
                      })()}
                    </div>

                    {/* Required vs Expected Numbers Grid */}
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                      <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.06]">
                        <span className="text-[11px] text-slate-400 block">Required monthly saving</span>
                        <p className="mt-1 font-mono text-base font-bold text-white">
                          {money(selectedGoal.requiredMonthlySaving)} / mo
                        </p>
                        <span className="text-[10px] text-slate-500 block mt-0.5">
                          Target ÷ {selectedGoal.targetDate}
                        </span>
                      </div>

                      <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.06]">
                        <span className="text-[11px] text-slate-400 block">Expected net-cash capacity</span>
                        <p className={`mt-1 font-mono text-base font-bold ${selectedGoal.isForecastAvailable ? "text-emerald-400" : "text-amber-400"}`}>
                          {selectedGoal.isForecastAvailable ? `${money(selectedGoal.expectedMonthlySaving)} / mo` : "Unavailable"}
                        </p>
                        <span className="text-[10px] text-slate-500 block mt-0.5">
                          {selectedGoal.isForecastAvailable ? "Model 1 net cash forecast" : (selectedGoal.explanation || "Forecast data pending")}
                        </span>
                      </div>

                      <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.06]">
                        <span className="text-[11px] text-slate-400 block">Baseline cash-flow gap</span>
                        <p className="mt-1 font-mono text-base font-bold text-amber-300">
                          {selectedGoal.additionalMonthlyNeeded > 0
                            ? `${money(selectedGoal.additionalMonthlyNeeded)} / mo`
                            : "₹0 (Fully covered)"}
                        </p>
                        <span className="text-[10px] text-slate-500 block mt-0.5">
                          {selectedGoal.additionalMonthlyNeeded > 0 ? "Exceeds current net cash" : "Zero gap"}
                        </span>
                      </div>
                    </div>

                    {/* Interactive 1: Your Monthly Savings Plan */}
                    <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/[0.03] p-4 sm:p-5 space-y-3.5">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                        <div>
                          <div className="flex items-center gap-1.5">
                            <Wallet size={15} className="text-cyan-400" />
                            <h4 className="text-sm font-bold text-white">Your Monthly Savings Plan</h4>
                          </div>
                          <p className="mt-0.5 text-xs text-slate-400">
                            {selectedGoal.isForecastAvailable
                              ? `Allocate from your expected net-cash capacity (${money(selectedGoal.expectedMonthlySaving)}/mo):`
                              : "Requires an available cash-flow forecast to set a monthly plan."}
                          </p>
                        </div>
                        {selectedGoal.plannedMonthlyContribution !== null ? (
                          <span className="text-[11px] font-mono px-2.5 py-0.5 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 self-start sm:self-auto">
                            Active: {money(selectedGoal.plannedMonthlyContribution)}/mo
                          </span>
                        ) : isBaselineAchievable ? (
                          <span className="text-[11px] font-mono px-2.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 self-start sm:self-auto">
                            Baseline Allocated: {money(userPlannedContribution)}/mo
                          </span>
                        ) : null}
                      </div>

                      {!selectedGoal.isForecastAvailable ? (
                        <div className="rounded-lg border border-amber-500/20 bg-amber-500/10 p-3 text-xs text-amber-200">
                          {selectedGoal.explanation || "Cash flow forecast is currently unavailable. A verified forecast is required before setting a monthly savings plan."}
                        </div>
                      ) : (
                        <>
                          {/* Quick Presets */}
                          <div className="flex flex-wrap items-center gap-2 pt-0.5">
                            <span className="text-[11px] text-slate-400 mr-1">Presets:</span>
                            {[0.25, 0.5, 0.75, 1.0].map((pct) => {
                              const val = Math.max(Math.round(selectedGoal.expectedMonthlySaving * pct), 0);
                              const isCurrent = userPlannedContribution === val;
                              const disabled = selectedGoal.expectedMonthlySaving <= 0;
                              return (
                                <button
                                  key={pct}
                                  type="button"
                                  disabled={disabled}
                                  onClick={() => {
                                    setGoalPlanInputs((prev) => ({ ...prev, [selectedGoal.id]: String(val) }));
                                    void saveMonthlyPlan(selectedGoal, String(val));
                                  }}
                                  className={`px-2.5 py-1 rounded-lg text-xs font-mono font-medium border transition-all ${
                                    isCurrent
                                      ? "bg-cyan-500/20 border-cyan-400 text-white font-semibold shadow-sm"
                                      : disabled
                                      ? "bg-white/[0.01] border-white/5 text-slate-600 cursor-not-allowed"
                                      : "bg-white/[0.03] border-white/10 text-slate-300 hover:border-cyan-400/40 hover:text-white"
                                  }`}
                                >
                                  {pct * 100}% ({money(val)})
                                </button>
                              );
                            })}
                          </div>

                      {/* Input + Action */}
                      <div className="grid grid-cols-1 sm:grid-cols-12 gap-3 items-end pt-1">
                        <label className="sm:col-span-8 space-y-1.5">
                          <span className="text-xs text-slate-300">Custom planned contribution:</span>
                          <div className="relative">
                            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 font-mono text-xs">₹</span>
                            <input
                              type="number"
                              min="0"
                              max={Math.max(selectedGoal.expectedMonthlySaving, 0)}
                              step="500"
                              value={currentPlanDraft}
                              onChange={(e) => {
                                const val = e.target.value;
                                setGoalPlanInputs((prev) => ({ ...prev, [selectedGoal.id]: val }));
                              }}
                              placeholder={isBaselineAchievable ? `Baseline: ${money(defaultBaselineContribution)} (or customize)` : `Up to ${money(selectedGoal.expectedMonthlySaving)}`}
                              className="w-full rounded-lg border border-white/10 bg-white/[0.04] pl-7 pr-3 py-2 font-mono text-xs text-white placeholder-slate-500 focus:border-cyan-400/60 focus:outline-none"
                              aria-label="Planned monthly savings contribution"
                            />
                          </div>
                        </label>
                        <div className="sm:col-span-4">
                          <button
                            type="button"
                            disabled={savingPlanGoalId === selectedGoal.id}
                            onClick={() => void saveMonthlyPlan(selectedGoal, currentPlanDraft || String(userPlannedContribution))}
                            className="w-full inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-400/40 text-cyan-200 hover:text-white text-xs font-semibold transition-all disabled:opacity-50"
                          >
                            {savingPlanGoalId === selectedGoal.id ? (
                              <>
                                <Loader2 size={13} className="animate-spin" />
                                <span>Saving…</span>
                              </>
                            ) : (
                              <>
                                <Check size={13} />
                                <span>Save Plan</span>
                              </>
                            )}
                          </button>
                        </div>
                      </div>

                      {/* Plan Impact Metrics */}
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1 text-xs">
                        <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-3">
                          <span className="block text-slate-400 text-[11px]">Remaining net-cash buffer</span>
                          <span className="mt-1 block font-mono font-semibold text-emerald-400">
                            {money(remainingCapacityAfterPlan)} available
                          </span>
                          <span className="mt-0.5 block text-[10px] text-slate-500">
                            Left over after your planned savings
                          </span>
                        </div>
                        <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-3">
                          <span className="block text-slate-400 text-[11px]">Remaining goal gap after plan</span>
                          <span className="mt-1 block font-mono font-semibold text-amber-300">
                            {remainingGapAfterPlan > 0 ? `${money(remainingGapAfterPlan)} / mo` : "₹0 (Fully covered by plan)"}
                          </span>
                          <span className="mt-0.5 block text-[10px] text-slate-500">
                            {remainingGapAfterPlan > 0 ? "Can be covered by discretionary trimming below" : "No further adjustments required"}
                          </span>
                        </div>
                      </div>
                    </>
                  )}
                </div>

                    {/* Interactive 2: Spending Adjustment Opportunities (Discretionary Variable) */}
                    <div className="space-y-3 pt-1">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Sparkles size={14} className="text-purple-400" />
                          <span className="text-xs font-bold text-white uppercase tracking-wider">
                            Spending Adjustment Opportunities
                          </span>
                        </div>
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-purple-500/10 border border-purple-500/25 text-purple-300">
                          Model 1 Variable Forecast
                        </span>
                      </div>
                      <p className="text-xs text-slate-400">
                        Targeted reductions in discretionary categories only. Essential expenses (Food, Groceries, Healthcare, Rent, EMIs) are protected.
                      </p>

                      <div className="space-y-2.5">
                        {selectedGoal.discretionaryAdjustments?.map((adj) => {
                          const isIncluded = activeCategories.includes(adj.category);
                          return (
                            <div
                              key={adj.category}
                              className={`p-3 rounded-xl border transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs ${
                                isIncluded
                                  ? "bg-purple-950/20 border-purple-500/40 shadow-sm"
                                  : "bg-white/[0.02] border-white/[0.06] opacity-75 hover:opacity-100"
                              }`}
                            >
                              <div className="flex items-start gap-3 min-w-0">
                                <input
                                  type="checkbox"
                                  id={`cat-adj-${selectedGoal.id}-${adj.category}`}
                                  checked={isIncluded}
                                  onChange={() => {
                                    setSelectedCategoryAdjustments((prev) => {
                                      const current = prev[selectedGoal.id] ?? (
                                        selectedGoal.discretionaryAdjustments?.filter((a) => a.suggestedReduction > 0).map((a) => a.category) ?? []
                                      );
                                      const next = current.includes(adj.category)
                                        ? current.filter((c) => c !== adj.category)
                                        : [...current, adj.category];
                                      return { ...prev, [selectedGoal.id]: next };
                                    });
                                  }}
                                  className="mt-0.5 h-4 w-4 rounded border-white/20 bg-slate-900 text-purple-500 focus:ring-0 cursor-pointer shrink-0"
                                />
                                <div className="min-w-0">
                                  <label
                                    htmlFor={`cat-adj-${selectedGoal.id}-${adj.category}`}
                                    className="font-semibold text-white cursor-pointer hover:text-purple-300 flex items-center gap-2"
                                  >
                                    <span>{adj.category}</span>
                                    <span className="text-[9px] uppercase tracking-wider font-mono px-1.5 py-0.2 rounded bg-purple-500/20 text-purple-300 font-semibold">
                                      Discretionary
                                    </span>
                                  </label>
                                  <p className="text-[11px] text-slate-400 mt-0.5 leading-relaxed">{adj.evidence}</p>
                                  <p className="text-[11px] text-slate-500 mt-1 font-mono">
                                    Current forecast: {money(adj.currentMonthly)}/mo · Baseline preserved: {money(adj.currentMonthly - adj.suggestedReduction)}/mo
                                  </p>
                                </div>
                              </div>
                              <div className="shrink-0 text-left sm:text-right pl-7 sm:pl-0">
                                {adj.suggestedReduction > 0 ? (
                                  <div>
                                    <span className={`font-mono text-xs font-bold ${isIncluded ? "text-purple-300" : "text-slate-400"}`}>
                                      Trim {money(adj.suggestedReduction)}/mo
                                    </span>
                                    <span className="block text-[10px] text-slate-500">
                                      {isIncluded ? "Applied to plan" : "Excluded from plan"}
                                    </span>
                                  </div>
                                ) : (
                                  <span className="text-emerald-400 text-xs font-medium">
                                    No change required
                                  </span>
                                )}
                              </div>
                            </div>
                          );
                        })}
                        {selectedGoal.discretionaryAdjustments?.length === 0 && (
                          <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3 text-xs text-slate-400 flex items-center gap-2">
                            <Info size={14} className="text-slate-400 shrink-0" />
                            <span>No safe category-level adjustment is needed or available. Current cash flow fully supports this goal.</span>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Interactive 3: Subscription Review Opportunities (Model 3 Integration) */}
                    <div className="space-y-3 pt-1">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Layers size={14} className="text-cyan-400" />
                          <span className="text-xs font-bold text-white uppercase tracking-wider">
                            Subscription Review Opportunities
                          </span>
                        </div>
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-cyan-500/10 border border-cyan-500/25 text-cyan-300">
                          Model 3 Intelligence
                        </span>
                      </div>
                      <p className="text-xs text-slate-400">
                        Review recurring commitments with low or under-utilized engagement to free up additional monthly cash without touching core living expenses:
                      </p>

                      <div className="space-y-2.5">
                        {candidateSubs.map((sub) => {
                          const isIncluded = activeGoalSubIds.includes(sub.id);
                          const isUnderutilized = sub.engagementStatus === "Under-utilized";
                          return (
                            <div
                              key={sub.id}
                              className={`p-3 rounded-xl border transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs ${
                                isIncluded
                                  ? "bg-cyan-950/20 border-cyan-500/40 shadow-sm"
                                  : "bg-white/[0.02] border-white/[0.06] opacity-75 hover:opacity-100"
                              }`}
                            >
                              <div className="flex items-start gap-3 min-w-0">
                                <input
                                  type="checkbox"
                                  id={`sub-adj-${selectedGoal.id}-${sub.id}`}
                                  checked={isIncluded}
                                  onChange={() => {
                                    setSelectedGoalSubIds((prev) => {
                                      const current = prev[selectedGoal.id] ?? (
                                        candidateSubs.filter((s) => s.engagementStatus === "Under-utilized").map((s) => s.id)
                                      );
                                      const next = current.includes(sub.id)
                                        ? current.filter((id) => id !== sub.id)
                                        : [...current, sub.id];
                                      return { ...prev, [selectedGoal.id]: next };
                                    });
                                  }}
                                  className="mt-0.5 h-4 w-4 rounded border-white/20 bg-slate-900 text-cyan-500 focus:ring-0 cursor-pointer shrink-0"
                                />
                                <div className="min-w-0">
                                  <label
                                    htmlFor={`sub-adj-${selectedGoal.id}-${sub.id}`}
                                    className="font-semibold text-white cursor-pointer hover:text-cyan-300 flex items-center gap-2"
                                  >
                                    <span>{sub.name}</span>
                                    <span
                                      className={`text-[9.5px] font-mono px-2 py-0.2 rounded-full border ${
                                        isUnderutilized
                                          ? "bg-amber-500/15 border-amber-500/25 text-amber-400"
                                          : "bg-blue-500/15 border-blue-500/25 text-blue-400"
                                      }`}
                                    >
                                      {sub.engagementStatus}
                                    </span>
                                  </label>
                                  <p className="text-[11px] text-slate-400 mt-0.5 leading-relaxed">{sub.transactionSignal}</p>
                                </div>
                              </div>
                              <div className="shrink-0 text-left sm:text-right pl-7 sm:pl-0">
                                <span className={`font-mono text-xs font-bold ${isIncluded ? "text-cyan-300" : "text-slate-400"}`}>
                                  Save {money(sub.monthlyAmount)}/mo
                                </span>
                                <span className="block text-[10px] text-slate-500">
                                  {isIncluded ? "Included in plan" : "Keep active"}
                                </span>
                              </div>
                            </div>
                          );
                        })}
                        {candidateSubs.length === 0 && (
                          <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3 text-xs text-slate-400 flex items-center gap-2">
                            <Info size={14} className="text-slate-400 shrink-0" />
                            <span>No under-utilized subscriptions detected for review.</span>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Interactive 4: Combined Feasibility Plan Summary */}
                    <div className={`rounded-xl border p-4 sm:p-5 space-y-4 ${
                      isCombinedFeasible
                        ? "bg-gradient-to-br from-emerald-950/20 via-[#0d1322] to-emerald-950/10 border-emerald-500/30"
                        : "bg-gradient-to-br from-amber-950/20 via-[#0d1322] to-amber-950/10 border-amber-500/30"
                    }`}>
                      <div className="flex items-center justify-between pb-3 border-b border-white/[0.08]">
                        <div className="flex items-center gap-2">
                          {isCombinedFeasible ? (
                            <CheckCircle2 size={18} className="text-emerald-400" />
                          ) : (
                            <AlertTriangle size={18} className="text-amber-400" />
                          )}
                          <div>
                            <h4 className="text-sm font-bold text-white">Combined Feasibility Plan Summary</h4>
                            <p className="text-[11px] text-slate-400 mt-0.2">
                              Unified synthesis of your planned contribution, category adjustments & subscriptions
                            </p>
                          </div>
                        </div>
                        <span className={`text-[10px] font-mono uppercase tracking-wider font-bold px-2.5 py-0.5 rounded-full border ${
                          isCombinedFeasible
                            ? "bg-emerald-500/15 border-emerald-500/30 text-emerald-400"
                            : "bg-amber-500/15 border-amber-500/30 text-amber-400"
                        }`}>
                          {isCombinedFeasible ? "Feasible Plan" : "Gap Remaining"}
                        </span>
                      </div>

                      {/* 3 Lever Stack breakdown */}
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 text-xs">
                        <div className="p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.06]">
                          <div className="flex items-center justify-between">
                            <span className="text-[10px] text-slate-400 block">1. Planned Contribution</span>
                            {!hasPersistedPlan && !hasUserPlanInput && isBaselineAchievable && (
                              <span className="text-[9px] font-mono text-emerald-400 font-medium">Baseline</span>
                            )}
                          </div>
                          <span className="font-mono text-xs font-bold text-white block mt-0.5">
                            {money(userPlannedContribution)}/mo
                          </span>
                        </div>
                        <div className="p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.06]">
                          <span className="text-[10px] text-slate-400 block">2. Category Reductions</span>
                          <span className="font-mono text-xs font-bold text-purple-300 block mt-0.5">
                            + {money(activeCategorySavings)}/mo
                          </span>
                        </div>
                        <div className="p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.06]">
                          <span className="text-[10px] text-slate-400 block">3. Subscription Savings</span>
                          <span className="font-mono text-xs font-bold text-cyan-300 block mt-0.5">
                            + {money(activeSubscriptionSavings)}/mo
                          </span>
                        </div>
                      </div>

                      {/* Total Monthly Plan vs Target */}
                      <div className="pt-2 border-t border-white/[0.06] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                        <div>
                          <span className="text-xs text-slate-400">Total Monthly Savings Generated:</span>
                          <div className="flex items-baseline gap-2 mt-0.5">
                            <span className="font-mono text-lg font-bold text-white">
                              {money(totalCombinedMonthlySavings)} / mo
                            </span>
                            <span className="text-xs text-slate-500">
                              (Target: {money(selectedGoal.requiredMonthlySaving)}/mo)
                            </span>
                          </div>
                        </div>

                        <div className="text-left sm:text-right">
                          {isCombinedFeasible ? (
                            <div>
                              <span className="text-xs font-semibold text-emerald-400 block">
                                Surplus: +{money(combinedSurplus)} / mo
                              </span>
                              <span className="text-[11px] text-slate-400 block mt-0.5">
                                Goal achievable in {projectedMonths ?? selectedGoal.months} months
                              </span>
                            </div>
                          ) : (
                            <div>
                              <span className="text-xs font-semibold text-amber-300 block">
                                Shortfall: -{money(combinedRemainingGap)} / mo
                              </span>
                              <span className="text-[11px] text-slate-400 block mt-0.5">
                                Extend timeline to {projectedMonths ?? selectedGoal.months + 3} months to achieve
                              </span>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </>
                );
              })()}
            </div>
          </div>
        </section>

        {/* ─────────────────────────────────────────────────────────────
            SECTION 3: SUBSCRIPTION INTELLIGENCE
            "Which subscriptions appear under-utilized, and what could I save by cancelling them?"
        ───────────────────────────────────────────────────────────── */}
        <section ref={subsRef} className="scroll-mt-16 space-y-5">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-mono uppercase tracking-wider text-cyan-400 font-semibold">
                03 · Subscriptions
              </span>
            </div>
            <h2 className="text-xl sm:text-2xl font-bold text-white tracking-tight mt-0.5">
              Subscription Intelligence
            </h2>
            <p className="text-xs sm:text-sm text-slate-400 mt-0.5">
              Which subscriptions appear under-utilized, and what could I save by cancelling them?
            </p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
            {/* Subscriptions List with Checkboxes (Left 7 Cols) */}
            <div className="lg:col-span-7 rounded-2xl border border-white/[0.08] bg-[#0d1322]/80 overflow-hidden">
              <div className="p-4 border-b border-white/[0.06] flex items-center justify-between text-xs">
                <span className="font-bold text-white">Detected Subscriptions</span>
                <div className="flex items-center gap-3">
                  {cancelledSubIds.length > 0 && (
                    <button
                      type="button"
                      onClick={() => setCancelledSubIds([])}
                      className="text-[11px] font-mono text-cyan-400 hover:text-cyan-300 transition-colors underline cursor-pointer"
                    >
                      Clear all ({cancelledSubIds.length})
                    </button>
                  )}
                  <span className="text-slate-400 font-mono">Select to simulate cancellation</span>
                </div>
              </div>

              <div className="divide-y divide-white/[0.06]">
                {subscriptions.map((sub) => {
                  const isChecked = cancelledSubIds.includes(sub.id);
                  const isUnderutilized = sub.engagementStatus === "Under-utilized";
                  const isModerate = sub.engagementStatus === "Moderate";
                  const isActive = sub.engagementStatus === "Active";

                  return (
                    <div
                      key={sub.id}
                      className={`p-4 transition-colors flex items-center justify-between gap-3 ${
                        isChecked ? "bg-cyan-500/[0.04]" : "hover:bg-white/[0.02]"
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <input
                          type="checkbox"
                          id={`check-${sub.id}`}
                          checked={isChecked}
                          onChange={() => toggleSubCancellation(sub.id)}
                          className="h-4 w-4 rounded border-white/20 bg-slate-900 text-cyan-500 focus:ring-0 cursor-pointer"
                        />
                        <div>
                          <div className="flex items-center gap-2">
                            <label
                              htmlFor={`check-${sub.id}`}
                              className="text-sm font-semibold text-white cursor-pointer hover:text-cyan-300"
                            >
                              {sub.name}
                            </label>
                            <span
                              className={`text-[9.5px] font-mono px-2 py-0.2 rounded-full border ${
                                isUnderutilized
                                  ? "bg-amber-500/15 border-amber-500/25 text-amber-400"
                                  : isModerate
                                  ? "bg-blue-500/15 border-blue-500/25 text-blue-400"
                                  : isActive
                                  ? "bg-emerald-500/15 border-emerald-500/25 text-emerald-400"
                                  : "bg-slate-500/15 border-slate-500/25 text-slate-400"
                              }`}
                            >
                              {sub.engagementStatus}
                            </span>
                          </div>
                          <p className="text-[11px] text-slate-400 mt-0.5">
                            {sub.transactionSignal}
                          </p>
                        </div>
                      </div>

                      <div className="text-right shrink-0">
                        <p className="font-mono text-sm font-bold text-white">
                          {money(sub.monthlyAmount)}
                        </p>
                        <p className="text-[10px] text-slate-400 font-mono">per month</p>
                      </div>
                    </div>
                  );
                })}
                {subscriptionsError ? (
                  <div className="p-8 text-center text-xs text-rose-400 font-mono">
                    {subscriptionsError}
                  </div>
                ) : subscriptions.length === 0 ? (
                  <div className="p-8 text-center text-xs text-slate-400 font-mono">
                    No active subscriptions detected.
                  </div>
                ) : null}
              </div>
            </div>

            {/* Simulate Cancellation Preview Card (Right 5 Cols) */}
            <div className="lg:col-span-5 rounded-2xl border border-cyan-500/30 bg-[#0d1322]/80 p-5 sm:p-6 space-y-4">
              <div>
                <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                  Simulate Cancellation Impact
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  {subSimulation.selectedCount > 0
                    ? `Review the projected effect of removing ${subSimulation.selectedCount} selected subscription${subSimulation.selectedCount === 1 ? "" : "s"}.`
                    : "Select subscriptions on the left to simulate cancellation impact."}
                </p>
              </div>

              <div className="space-y-3 pt-2">
                <div className="flex justify-between items-center text-xs pb-2 border-b border-white/[0.06]">
                  <span className="text-slate-400">Current monthly commitments:</span>
                  <span className="font-mono text-white font-semibold">{money(subSimulation.currentCommitments)} / mo</span>
                </div>

                <div className="flex justify-between items-center text-xs pb-2 border-b border-white/[0.06]">
                  <span className="text-slate-400">After cancellation:</span>
                  <span className="font-mono text-white font-semibold">{money(subSimulation.updatedCommitments)} / mo</span>
                </div>

                <div className="flex justify-between items-center text-xs pb-2 border-b border-white/[0.06]">
                  <span className="text-slate-400">Monthly savings:</span>
                  <span className="font-mono text-emerald-400 font-bold">
                    {subSimulation.monthlySaving > 0 ? `+${money(subSimulation.monthlySaving)} / mo` : "₹0 / mo"}
                  </span>
                </div>

                <div className="flex justify-between items-center text-xs pb-2 border-b border-white/[0.06]">
                  <span className="text-slate-400">Annual potential savings:</span>
                  <span className="font-mono text-cyan-300 font-bold">
                    {subSimulation.annualSaving > 0 ? `+${money(subSimulation.annualSaving)} / year` : "₹0 / year"}
                  </span>
                </div>
              </div>

              {/* How it affects available cash / goal feasibility */}
              <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.06] text-xs space-y-1">
                <span className="font-semibold text-white">Impact on Financial Goals:</span>
                <p className="text-slate-300 leading-relaxed text-[11px]">
                  {subSimulation.goalImpact && subSimulation.monthlySaving > 0 ? (
                    <>
                      Saving <strong className="text-cyan-300 font-mono font-semibold">{money(subSimulation.monthlySaving)}/mo</strong>{" "}
                      increases your expected net cash to{" "}
                      <strong className="text-white font-mono font-semibold">{money(subSimulation.updatedNetCash)}/mo</strong>
                      {subSimulation.goalImpact.gap_closed_percent !== null && subSimulation.goalImpact.gap_closed_percent > 0 ? (
                        <>, closing <span className="text-emerald-400 font-semibold">{subSimulation.goalImpact.gap_closed_percent.toFixed(0)}%</span> of the gap</>
                      ) : null}
                      {subSimulation.goalImpact.goal_name ? ` for your ${subSimulation.goalImpact.goal_name} goal.` : "."}
                    </>
                  ) : subSimulation.monthlySaving > 0 ? (
                    <>
                      Saving <strong className="text-cyan-300 font-mono font-semibold">{money(subSimulation.monthlySaving)}/mo</strong> increases your expected net cash to <strong className="text-white font-mono font-semibold">{money(subSimulation.updatedNetCash)}/mo</strong>.
                    </>
                  ) : (
                    "Select subscriptions on the left to simulate cancellation impact on your monthly commitments and savings goals."
                  )}
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* ─────────────────────────────────────────────────────────────
            SECTION 4: SHORTFALL PREDICTION
            "Am I likely to run short of money next month?"
        ───────────────────────────────────────────────────────────── */}
        <section ref={shortfallRef} className="scroll-mt-16 space-y-5">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-mono uppercase tracking-wider text-rose-400 font-semibold">
                04 · Shortfall
              </span>
            </div>
            <h2 className="text-xl sm:text-2xl font-bold text-white tracking-tight mt-0.5">
              Shortfall Prediction
            </h2>
            <p className="text-xs sm:text-sm text-slate-400 mt-0.5">
              Am I likely to run short of money next month?
            </p>
          </div>

          {shortfallError ? (
            <div className="rounded-2xl border border-rose-500/30 bg-[#0d1322]/80 p-6 text-center text-xs font-mono text-rose-400">
              {shortfallError}
            </div>
          ) : !shortfallData?.available ? (
            <div className="rounded-2xl border border-white/[0.08] bg-[#0d1322]/80 p-6 sm:p-8 space-y-3">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-slate-500/10 border border-slate-500/20 text-slate-400 flex items-center justify-center">
                  <HelpCircle size={20} />
                </div>
                <div>
                  <span className="text-xs text-slate-400">Shortfall Risk Assessment</span>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-lg font-bold text-white">Unavailable</span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-slate-500/15 border border-slate-500/25 text-slate-400 font-semibold">
                      INSUFFICIENT HISTORY
                    </span>
                  </div>
                </div>
              </div>
              <p className="text-xs text-slate-400 max-w-2xl leading-relaxed">
                Shortfall risk prediction requires at least 6 months of observed transaction history to evaluate temporal income trends, recurring commitments, and cash-flow volatility.
              </p>
            </div>
          ) : (() => {
            const isHigh = shortfallData.shortfall_risk === "HIGH";
            const isModerate = shortfallData.shortfall_risk === "MODERATE";

            const riskTitle = isHigh ? "High Risk" : isModerate ? "Moderate Risk" : "Low Risk";
            const riskBadgeText = isHigh ? "MAY RUN SHORT" : isModerate ? "MODERATE RISK" : "LOWER SHORTFALL RISK";
            const riskBadgeClass = isHigh
              ? "bg-rose-500/15 border-rose-500/30 text-rose-400"
              : isModerate
              ? "bg-amber-500/15 border-amber-500/30 text-amber-400"
              : "bg-emerald-500/15 border-emerald-500/30 text-emerald-400";
            const riskIconBg = isHigh
              ? "bg-rose-500/10 border-rose-500/20 text-rose-400"
              : isModerate
              ? "bg-amber-500/10 border-amber-500/20 text-amber-400"
              : "bg-emerald-500/10 border-emerald-500/20 text-emerald-400";

            // Forecasted Income, Expenses, and Net Cash from authoritative backend
            const expIncome = shortfallData.expected_income ?? forecastData?.expected_income ?? null;
            const expExpenses = shortfallData.expected_total_expenses ?? forecastData?.expected_total_expenses ?? null;
            const rawExpNetCash = shortfallData.expected_net_cash ?? forecastData?.expected_net_cash ?? null;
            // Reconcile displayed integer net cash with displayed rounded income and expenses to maintain exact card arithmetic
            const expNetCash = expIncome !== null && expExpenses !== null
              ? Math.round(expIncome) - Math.round(expExpenses)
              : rawExpNetCash;

            const explanation = shortfallData.risk_explanation || (isHigh
              ? (expNetCash !== null && expNetCash > 0
                  ? "Model 4 identifies high shortfall vulnerability next month. While Model 1 projects positive baseline net cash, historical spending volatility and commitment burden leave minimal resilience against unexpected outflows."
                  : "Model 4 predicts a high likelihood of cash shortfall next month, based on historical net cash deficits and expense pressure.")
              : isModerate
              ? (expNetCash !== null && expNetCash > 0
                  ? "Model 4 predicts moderate shortfall risk next month. While projected net cash remains positive, spending fluctuations or recurring obligations could tighten available reserves."
                  : "Model 4 predicts moderate shortfall risk next month, indicating potential cash-flow tightening under variable spending fluctuations.")
              : "Model 4 predicts a low likelihood that you will experience a cash shortfall next month, based on your historical cash-flow patterns.");

            // Bar proportions
            const maxVal = Math.max(expIncome ?? 0, expExpenses ?? 0, 1);
            const incomePct = expIncome !== null ? Math.min(Math.max((expIncome / maxVal) * 100, 6), 100) : 0;
            const expensesPct = expExpenses !== null ? Math.min(Math.max((expExpenses / maxVal) * 100, 6), 100) : 0;

            // Difference for alert box (reconciled with displayed rounded amounts)
            const hasBothAmounts = expIncome !== null && expExpenses !== null;
            const expensesExceedIncome = hasBothAmounts && Math.round(expExpenses) > Math.round(expIncome);
            const expDiff = hasBothAmounts ? Math.abs(Math.round(expExpenses) - Math.round(expIncome)) : 0;

            // Map contributing factors with backend-calculated severities when available
            const factorMeta: Record<string, { title: string; defaultDesc: string; icon: typeof TrendingDown }> = {
              "declining historical income trend": {
                title: "Declining Income Trend",
                defaultDesc: "Your average monthly income has trended downward across recent months.",
                icon: TrendingDown,
              },
              "low historical cash buffer": {
                title: "Low Cash Buffer",
                defaultDesc: "Historical cash buffer is low or negative relative to monthly spending.",
                icon: Wallet,
              },
              "recent expense increase": {
                title: "Expense Increase",
                defaultDesc: "Monthly variable or commitment spending trended upward in recent months.",
                icon: CreditCard,
              },
              "high recurring commitment burden": {
                title: "High Commitments",
                defaultDesc: "A high share of monthly income is committed to recurring contractual obligations.",
                icon: Layers,
              },
              "high variable-spending volatility": {
                title: "Spending Volatility",
                defaultDesc: "Discretionary and variable outflows fluctuate significantly month-to-month.",
                icon: AlertTriangle,
              },
              "historical cash-flow pattern is comparatively stable": {
                title: "Stable Pattern",
                defaultDesc: "Historical cash-flow patterns demonstrate broad stability across observed months.",
                icon: ShieldCheck,
              },
            };

            const severityStyles: Record<"HIGH" | "MEDIUM" | "LOW", { badgeClass: string; iconClass: string }> = {
              HIGH: {
                badgeClass: "bg-rose-500/15 border-rose-500/30 text-rose-400",
                iconClass: "bg-rose-500/10 border-rose-500/20 text-rose-400",
              },
              MEDIUM: {
                badgeClass: "bg-amber-500/15 border-amber-500/30 text-amber-400",
                iconClass: "bg-amber-500/10 border-amber-500/20 text-amber-400",
              },
              LOW: {
                badgeClass: "bg-emerald-500/15 border-emerald-500/30 text-emerald-400",
                iconClass: "bg-emerald-500/10 border-emerald-500/20 text-emerald-400",
              },
            };

            const factors = shortfallData.factor_details && shortfallData.factor_details.length > 0
              ? shortfallData.factor_details.map((detail) => {
                  const key = detail.factor.toLowerCase().trim();
                  const meta = factorMeta[key] || {
                    title: detail.factor.charAt(0).toUpperCase() + detail.factor.slice(1),
                    defaultDesc: detail.description,
                    icon: AlertTriangle,
                  };
                  const sev = (detail.severity?.toUpperCase() || "MEDIUM") as "HIGH" | "MEDIUM" | "LOW";
                  const style = severityStyles[sev] || severityStyles.MEDIUM;
                  return {
                    key: detail.factor,
                    title: meta.title,
                    desc: detail.description || meta.defaultDesc,
                    badge: sev as "HIGH" | "MEDIUM" | "LOW" | null,
                    badgeClass: style.badgeClass,
                    icon: meta.icon,
                    iconClass: style.iconClass,
                  };
                })
              : (shortfallData.contributing_factors ?? []).map((f) => {
                  const key = f.toLowerCase().trim();
                  const meta = factorMeta[key] || {
                    title: f.charAt(0).toUpperCase() + f.slice(1),
                    defaultDesc: f,
                    icon: AlertTriangle,
                  };
                  return {
                    key: f,
                    title: meta.title,
                    desc: meta.defaultDesc,
                    badge: null as "HIGH" | "MEDIUM" | "LOW" | null,
                    badgeClass: "",
                    icon: meta.icon,
                    iconClass: "bg-slate-500/10 border-slate-500/20 text-slate-300",
                  };
                });

            return (
              <div className="space-y-6">
                {/* Top Row: Main Risk Assessment Card + Projected Income vs Expenses */}
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
                  {/* Left: Main Risk Assessment Card (7 cols) */}
                  <div className="lg:col-span-7 rounded-2xl border border-white/[0.08] bg-[#0d1322]/80 p-5 sm:p-6 flex flex-col justify-between space-y-5">
                    <div className="grid grid-cols-1 md:grid-cols-12 gap-5 items-start">
                      {/* Left Sub-Column: Icon, Risk Title, Badge, Model Explanation */}
                      <div className="md:col-span-7 space-y-3">
                        <div className="flex items-center gap-3">
                          <div className={`w-12 h-12 rounded-2xl border flex items-center justify-center shrink-0 ${riskIconBg}`}>
                            {isHigh || isModerate ? <AlertTriangle size={24} /> : <ShieldCheck size={24} />}
                          </div>
                          <div>
                            <span className="text-xs text-slate-400 font-medium">Next Month Shortfall Risk</span>
                            <div className="flex items-center gap-2.5 mt-0.5">
                              <h3 className={`text-xl font-bold tracking-tight ${isHigh ? "text-rose-400" : isModerate ? "text-amber-400" : "text-emerald-400"}`}>
                                {riskTitle}
                              </h3>
                              <span className={`text-[10px] font-mono px-2.5 py-0.5 rounded-full border font-bold tracking-wide ${riskBadgeClass}`}>
                                {riskBadgeText}
                              </span>
                            </div>
                          </div>
                        </div>

                        <p className="text-xs text-slate-300 leading-relaxed pt-1">
                          {explanation}
                        </p>
                      </div>

                      {/* Right Sub-Column: Prediction Period & Expected Net Cash */}
                      <div className="md:col-span-5 space-y-3">
                        {/* Prediction Period */}
                        <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.06] space-y-1">
                          <div className="flex items-center justify-between text-[11px] text-slate-400">
                            <span className="flex items-center gap-1.5 font-medium">
                              <Calendar size={13} className="text-slate-400" />
                              <span>Prediction Period</span>
                            </span>
                            <Info size={12} className="text-slate-500" />
                          </div>
                          <p className="font-semibold text-white text-xs pt-0.5">
                            Next 1 Month
                          </p>
                        </div>

                        {/* Expected Net Cash — Next Month */}
                        <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.06] space-y-1">
                          <div className="flex items-center justify-between text-[11px] text-slate-400">
                            <span className="font-medium">
                              {expNetCash !== null && expNetCash < 0
                                ? "Estimated Shortfall — Next Month"
                                : "Expected Net Cash — Next Month"}
                            </span>
                            <Info size={12} className="text-slate-500" />
                          </div>
                          <p className={`font-mono text-base font-bold pt-0.5 ${
                            expNetCash !== null && expNetCash < 0
                              ? "text-rose-400"
                              : expNetCash !== null
                              ? "text-emerald-400"
                              : "text-slate-400"
                          }`}>
                            {expNetCash !== null
                              ? expNetCash < 0
                                ? money(Math.abs(expNetCash))
                                : `+${money(expNetCash)}`
                              : "Unavailable"}
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Right: Projected Income vs Expenses (Next Month) (5 cols) */}
                  <div className="lg:col-span-5 rounded-2xl border border-white/[0.08] bg-[#0d1322]/80 p-5 sm:p-6 flex flex-col justify-between space-y-4">
                    <div>
                      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 pb-2">
                        <h4 className="text-xs font-bold text-white tracking-wide">
                          Projected Income vs Expenses (Next Month)
                        </h4>
                        <div className="flex items-center flex-wrap gap-x-3 gap-y-1 text-[10px] text-slate-400 font-mono">
                          <span className="flex items-center gap-1.5 shrink-0">
                            <span className="w-2 h-2 rounded-full bg-sky-500 inline-block shrink-0" />
                            <span>Expected Income</span>
                          </span>
                          <span className="flex items-center gap-1.5 shrink-0">
                            <span className="w-2 h-2 rounded-full bg-purple-500 inline-block shrink-0" />
                            <span>Expected Expenses</span>
                          </span>
                        </div>
                      </div>

                      {/* Visual Bars Comparison */}
                      <div className="space-y-3 pt-3">
                        {/* Expected Income Bar */}
                        <div className="flex items-center justify-between gap-3 text-xs">
                          <span className="text-slate-300 w-28 shrink-0">Expected Income</span>
                          <div className="flex-1 h-3.5 bg-white/[0.04] rounded-full overflow-hidden p-0.5 border border-white/[0.05]">
                            <div
                              className="h-full bg-gradient-to-r from-sky-600 to-sky-400 rounded-full transition-all duration-500"
                              style={{ width: `${incomePct}%` }}
                            />
                          </div>
                          <span className="font-mono font-bold text-white text-right w-20 shrink-0">
                            {expIncome !== null ? money(expIncome) : "—"}
                          </span>
                        </div>

                        {/* Expected Expenses Bar */}
                        <div className="flex items-center justify-between gap-3 text-xs">
                          <span className="text-slate-300 w-28 shrink-0">Expected Expenses</span>
                          <div className="flex-1 h-3.5 bg-white/[0.04] rounded-full overflow-hidden p-0.5 border border-white/[0.05]">
                            <div
                              className="h-full bg-gradient-to-r from-purple-600 to-purple-400 rounded-full transition-all duration-500"
                              style={{ width: `${expensesPct}%` }}
                            />
                          </div>
                          <span className="font-mono font-bold text-white text-right w-20 shrink-0">
                            {expExpenses !== null ? money(expExpenses) : "—"}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Alert / Comparison Message Box */}
                    <div className={`p-3.5 rounded-xl border text-xs flex items-start gap-2.5 ${
                      expensesExceedIncome
                        ? "bg-rose-500/10 border-rose-500/20 text-rose-300"
                        : isHigh
                        ? "bg-amber-500/10 border-amber-500/20 text-amber-300"
                        : "bg-emerald-500/10 border-emerald-500/20 text-emerald-300"
                    }`}>
                      {expensesExceedIncome ? (
                        <AlertTriangle size={15} className="text-rose-400 shrink-0 mt-0.5" />
                      ) : isHigh ? (
                        <AlertTriangle size={15} className="text-amber-400 shrink-0 mt-0.5" />
                      ) : (
                        <ShieldCheck size={15} className="text-emerald-400 shrink-0 mt-0.5" />
                      )}
                      <p className="leading-relaxed text-[11px]">
                        {expensesExceedIncome ? (
                          <>
                            Your expected expenses are about <strong className="font-mono font-bold text-rose-400">{money(expDiff)}</strong> higher than your expected income next month.
                          </>
                        ) : hasBothAmounts && isHigh ? (
                          <>
                            Expected income covers forecast expenses (<strong className="font-mono font-bold text-emerald-400">+{money(expDiff)}</strong> surplus), but Model 4 detects elevated shortfall risk based on historical spending volatility and income continuity.
                          </>
                        ) : hasBothAmounts ? (
                          <>
                            Expected income covers expected expenses by about <strong className="font-mono font-bold text-emerald-400">{money(expDiff)}</strong> next month.
                          </>
                        ) : (
                          "Income and expense forecasts are unavailable due to insufficient history."
                        )}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Bottom Row: Key Factors Influencing This Prediction + What You Can Do */}
                <div className="space-y-3">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-white tracking-wide">
                    <span>Key Factors Influencing This Prediction</span>
                    <Info size={13} className="text-slate-400" />
                  </div>

                  <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-stretch">
                    {/* Factors Grid (8 cols) */}
                    <div
                      className={`lg:col-span-8 grid gap-3.5 ${
                        factors.length === 1
                          ? "grid-cols-1"
                          : factors.length === 2
                          ? "grid-cols-1 sm:grid-cols-2"
                          : "grid-cols-1 sm:grid-cols-2 xl:grid-cols-3"
                      }`}
                    >
                      {factors.map((factor) => {
                        const IconComponent = factor.icon;
                        return (
                          <div
                            key={factor.key}
                            className="p-3.5 sm:p-4 rounded-2xl border border-white/[0.08] bg-[#0d1322]/80 flex flex-col gap-2.5 h-auto"
                          >
                            <div className="flex items-start justify-between gap-2">
                              <div className={`w-8 h-8 sm:w-9 sm:h-9 rounded-xl border flex items-center justify-center shrink-0 ${factor.iconClass}`}>
                                <IconComponent size={17} />
                              </div>
                              {factor.badge && (
                                <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded font-bold uppercase tracking-wider ${factor.badgeClass}`}>
                                  {factor.badge}
                                </span>
                              )}
                            </div>

                            <div className="space-y-1">
                              <h5 className="text-xs font-bold text-white tracking-tight">{factor.title}</h5>
                              <p className="text-[11px] text-slate-400 leading-relaxed">
                                {factor.desc}
                              </p>
                            </div>
                          </div>
                        );
                      })}
                      {factors.length === 0 && (
                        <div className="col-span-full p-6 text-center text-xs text-slate-400 font-mono rounded-2xl border border-white/[0.06] bg-[#0d1322]/40">
                          No adverse historical cash-flow factors identified.
                        </div>
                      )}
                    </div>

                    {/* What You Can Do Guidance Card (4 cols) */}
                    <div className="lg:col-span-4 rounded-2xl border border-emerald-500/20 bg-[#0d1322]/80 p-4 sm:p-5 flex flex-col justify-between space-y-3">
                      <div className="flex items-center gap-2.5">
                        <div className="w-7 h-7 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center shrink-0">
                          <Lightbulb size={16} />
                        </div>
                        <h4 className="text-xs font-bold text-white">What You Can Do</h4>
                      </div>

                      <ul className="space-y-1.5 text-[11px] text-slate-300">
                        <li className="flex items-start gap-1.5">
                          <span className="text-emerald-400 leading-none mt-0.5">•</span>
                          <span>Review and reduce non-essential spending.</span>
                        </li>
                        <li className="flex items-start gap-1.5">
                          <span className="text-emerald-400 leading-none mt-0.5">•</span>
                          <span>Consider increasing your emergency fund.</span>
                        </li>
                        <li className="flex items-start gap-1.5">
                          <span className="text-emerald-400 leading-none mt-0.5">•</span>
                          <span>Explore ways to increase your income.</span>
                        </li>
                        <li className="flex items-start gap-1.5">
                          <span className="text-emerald-400 leading-none mt-0.5">•</span>
                          <span>
                            <button
                              type="button"
                              onClick={() => scrollToSection("goals")}
                              className="text-cyan-400 hover:text-cyan-300 underline font-medium text-left cursor-pointer"
                            >
                              Use the Goal Feasibility tool to test adjustments.
                            </button>
                          </span>
                        </li>
                      </ul>
                    </div>
                  </div>
                </div>
              </div>
            );
          })()}
        </section>

        {/* ─────────────────────────────────────────────────────────────
            MODAL: ADD FINANCIAL GOAL (MODEL 2)
        ───────────────────────────────────────────────────────────── */}
        <AnimatePresence>
          {addGoalModalOpen && (
            <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                onClick={() => setAddGoalModalOpen(false)}
                className="fixed inset-0 bg-black/75 backdrop-blur-sm"
              />

              <motion.div
                initial={{ opacity: 0, scale: 0.95, y: 10 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95, y: 10 }}
                transition={{ duration: 0.15 }}
                className="relative w-full max-w-lg rounded-2xl bg-[#0d1322] border border-white/10 p-4 sm:p-6 shadow-2xl shadow-purple-950/30 z-10 space-y-4 sm:space-y-5 max-h-[90vh] overflow-y-auto"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="text-lg font-bold text-white">Add Financial Goal</h3>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Evaluate feasibility against your expected monthly net cash flow ({money(cashValues.netCash)}/mo).
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setAddGoalModalOpen(false)}
                    className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
                  >
                    <X size={18} />
                  </button>
                </div>

                  <form onSubmit={handleAddGoalSubmit} className="space-y-4">
                    {goalFormError && <p role="alert" className="rounded-xl border border-rose-500/20 bg-rose-500/10 p-3 text-xs text-rose-300">{goalFormError}</p>}
                  {/* Goal Name */}
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-300">
                      Goal Name
                    </label>
                    <input
                      type="text"
                      required
                      placeholder="e.g. New Laptop, Emergency Fund, Summer Trip"
                      value={newGoalTitle}
                      onChange={(e) => { setNewGoalTitle(e.target.value); setGoalFormError(null); }}
                      className="w-full rounded-xl bg-white/[0.04] border border-white/10 px-3.5 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-purple-500/60 focus:ring-1 focus:ring-purple-500/60 transition-colors"
                    />
                  </div>

                  {/* Target Amount */}
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-300">
                      Target Amount (₹)
                    </label>
                    <div className="relative">
                      <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-sm font-mono text-slate-400">
                        ₹
                      </span>
                      <input
                        type="text"
                        required
                        placeholder="80,000"
                        value={newGoalAmount}
                      onChange={(e) => { setNewGoalAmount(e.target.value); setGoalFormError(null); }}
                        className="w-full rounded-xl bg-white/[0.04] border border-white/10 pl-8 pr-3.5 py-2.5 text-sm text-white font-mono placeholder-slate-500 focus:outline-none focus:border-purple-500/60 focus:ring-1 focus:ring-purple-500/60 transition-colors"
                      />
                    </div>
                  </div>

                  {/* Target Timeframe / Date */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-semibold text-slate-300">
                        Target Timeframe
                      </label>
                      <span className="text-[11px] text-slate-400 font-mono">
                        {livePreview.months} month{livePreview.months === 1 ? "" : "s"}
                      </span>
                    </div>

                    {/* Quick Month Chips */}
                    <div className="grid grid-cols-4 gap-2">
                      {[6, 12, 18, 24].map((m) => (
                        <button
                          key={m}
                          type="button"
                          onClick={() => {
                            setNewGoalMonths(m);
                            setNewGoalCustomDate("");
                          }}
                          className={`py-2 rounded-xl text-xs font-semibold transition-all border ${
                            newGoalMonths === m && !newGoalCustomDate
                              ? "bg-purple-600/20 border-purple-500/60 text-purple-200"
                              : "bg-white/[0.02] border-white/10 text-slate-400 hover:text-slate-200 hover:bg-white/[0.06]"
                          }`}
                        >
                          {m} Mo
                        </button>
                      ))}
                    </div>

                    {/* Or Custom Target Date */}
                    <div className="pt-1">
                      <div className="flex items-center gap-2 text-xs text-slate-400 mb-1">
                        <span>Or pick specific month & year:</span>
                      </div>
                      <input
                        type="month"
                        value={newGoalCustomDate}
                        onChange={(e) => setNewGoalCustomDate(e.target.value)}
                        className="w-full rounded-xl bg-white/[0.04] border border-white/10 px-3.5 py-2 text-xs text-slate-200 focus:outline-none focus:border-purple-500/60 transition-colors"
                      />
                    </div>
                  </div>

                  {/* Live Feasibility Evaluation Box */}
                  {livePreview.amt > 0 && (
                    <div className="p-3.5 rounded-xl bg-white/[0.02] border border-purple-500/20 space-y-2 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="text-slate-400">Required monthly saving:</span>
                        <span className="font-mono font-bold text-white">
                          {money(livePreview.req)} / mo
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-slate-400">Expected monthly net cash:</span>
                        <span className="font-mono font-semibold text-emerald-400">
                          +{money(cashValues.netCash)} / mo
                        </span>
                      </div>
                      <div className="pt-2 border-t border-white/[0.06] flex items-center justify-between">
                        <span className="text-slate-400">Feasibility evaluation:</span>
                        <span
                          className={`text-[11px] font-mono font-bold px-2 py-0.5 rounded-full border ${
                            livePreview.achievable
                              ? "bg-emerald-500/15 border-emerald-500/25 text-emerald-400"
                              : "bg-amber-500/15 border-amber-500/25 text-amber-400"
                          }`}
                        >
                          {livePreview.achievable
                            ? "✓ Achievable"
                            : `Needs +${money(livePreview.addl)}/mo adjustment`}
                        </span>
                      </div>
                    </div>
                  )}

                  {/* Form Buttons */}
                  <div className="flex items-center justify-end gap-3 pt-2">
                    <button
                      type="button"
                      onClick={() => setAddGoalModalOpen(false)}
                      className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white hover:bg-white/[0.04] transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={goalSaving}
                      className="px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 disabled:cursor-not-allowed disabled:opacity-60 text-white text-xs font-semibold shadow-lg shadow-purple-600/20 transition-all flex items-center gap-1.5"
                    >
                      <Plus size={14} />
                      <span>{goalSaving ? "Saving…" : "Add Goal"}</span>
                    </button>
                  </div>
                </form>
              </motion.div>
            </div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
