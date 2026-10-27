import React, { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence, useReducedMotion } from "motion/react";
import {
  Activity,
  AlertTriangle,
  ArrowDown,
  ArrowRight,
  ArrowUp,
  Brain,
  CheckCircle2,
  Clock,
  Coins,
  CreditCard,
  Gauge,
  Heart,
  HelpCircle,
  Info,
  Layers,
  Lightbulb,
  Loader2,
  Percent,
  Play,
  RotateCcw,
  Shield,
  ShieldAlert,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  TrendingUp,
  Zap,
} from "lucide-react";
import {
  ApiError,
  AuthenticatedUser,
  commitmentApi,
  ExposureResponse,
  getStoredAccessToken,
  simulatorApi,
} from "../api/client";
import type { SimulationResponse } from "../api/client";

interface WhatIfPageProps {
  onAskAssistant: (q?: string) => void;
  user: AuthenticatedUser;
  onUnauthorized: () => void;
}

type CommitmentType = "emi" | "bnpl" | "subscription" | "other";

interface SimulationOutput {
  currentHealth: number;
  projectedHealth: number;
  currentHealthLabel: string;
  projectedHealthLabel: string;
  currentExposure: number;
  projectedExposure: number;
  currentMonthly: number;
  projectedMonthly: number;
  currentAvailable: number;
  projectedAvailable: number;
  monthlyCapacity: number;
  monthlyDeficit: number;
  addedAmount: number;
  commitmentType: CommitmentType;
  durationMonths?: number;
  backendResponse: SimulationResponse;
}

function formatMoney(amount: number): string {
  return `₹${Math.round(amount).toLocaleString("en-IN")}`;
}

export function WhatIfPage({ onAskAssistant, user, onUnauthorized }: WhatIfPageProps) {
  const reduceMotion = useReducedMotion();

  // Baseline user data from backend
  const [exposure, setExposure] = useState<ExposureResponse | null>(null);
  const [loadingInitial, setLoadingInitial] = useState(true);
  const [initialError, setInitialError] = useState<string | null>(null);

  // Scenario inputs — General Financial Commitment
  const [commitmentType, setCommitmentType] = useState<CommitmentType>("emi");
  const [amountInput, setAmountInput] = useState<string>("5000");
  const [durationMonths, setDurationMonths] = useState<number>(24);

  // Simulation state
  const [isSimulating, setIsSimulating] = useState(false);
  const [result, setResult] = useState<SimulationOutput | null>(null);
  const [simulationError, setSimulationError] = useState<string | null>(null);

  // Fetch baseline exposure on load
  useEffect(() => {
    const token = getStoredAccessToken();
    if (!token || !user.financial_user_id) {
      onUnauthorized();
      return;
    }

    setLoadingInitial(true);
    setInitialError(null);

    commitmentApi
      .exposure(user.financial_user_id, token)
      .then((res) => {
        setExposure(res);
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          onUnauthorized();
        } else {
          setInitialError(err instanceof ApiError ? err.message : "Unable to load financial position.");
        }
      })
      .finally(() => setLoadingInitial(false));
  }, [user.financial_user_id, onUnauthorized]);

  // Current real baseline values
  const currentMonthly = exposure?.current_financial_status.monthly_total_commitments ?? 0;
  const currentExposurePct = exposure?.current_financial_status.exposure_score ?? 0;
  const currentAvailable = exposure?.current_financial_status.available_monthly_capacity ?? 0;
  const monthlyCapacity = exposure?.current_financial_status.monthly_financial_capacity ?? 0;

  // Breakdown for charts & baseline card
  const subCost = exposure?.current_financial_status.monthly_subscription_commitment ?? 0;
  const emiCost = exposure?.current_financial_status.monthly_emi_commitment ?? 0;
  const bnplCost = exposure?.current_financial_status.monthly_bnpl_commitment ?? 0;

  // Handle commitment type change: adjust default duration and clear stale result
  const handleCommitmentTypeChange = (type: CommitmentType) => {
    setCommitmentType(type);
    setResult(null);
    setSimulationError(null);
    if (type === "bnpl") {
      setDurationMonths(6);
    } else if (type === "emi") {
      setDurationMonths(24);
    } else if (type === "other") {
      setDurationMonths(12);
    }
  };

  // Handle amount change: clear stale result
  const handleAmountChange = (val: string) => {
    setAmountInput(val);
    if (result) setResult(null);
    if (simulationError) setSimulationError(null);
  };

  // Handle duration change: clear stale result
  const handleDurationChange = (months: number) => {
    setDurationMonths(months);
    if (result) setResult(null);
    if (simulationError) setSimulationError(null);
  };

  // Quick Preset Handlers
  const handleQuickPreset = (amount: number, months: number | undefined, type: CommitmentType) => {
    setCommitmentType(type);
    setAmountInput(String(amount));
    if (months) setDurationMonths(months);
    setResult(null);
    setSimulationError(null);
  };

  // Run real Digital Twin simulation
  async function handleRunSimulation() {
    const addedAmount = parseFloat(amountInput) || 0;
    if (addedAmount <= 0) {
      setSimulationError("Please enter a commitment amount greater than ₹0.");
      return;
    }

    setIsSimulating(true);
    setSimulationError(null);

    const token = getStoredAccessToken();
    if (!token) {
      onUnauthorized();
      setIsSimulating(false);
      return;
    }

    try {
      let backendScenarioType = "new_emi";
      let parameters: Record<string, unknown> = {};

      if (commitmentType === "subscription") {
        backendScenarioType = "add_subscription";
        parameters = { monthly_cost: addedAmount, name: "New Subscription" };
      } else if (commitmentType === "bnpl") {
        backendScenarioType = "add_bnpl";
        parameters = { monthly_installment: addedAmount, name: "New BNPL", installments: durationMonths };
      } else if (commitmentType === "other") {
        backendScenarioType = "add_other";
        parameters = { monthly_amount: addedAmount, name: "New Obligation", duration_months: durationMonths };
      } else {
        backendScenarioType = "new_emi";
        parameters = { monthly_emi: addedAmount, name: "New EMI", duration: durationMonths };
      }

      const backendResponse = await simulatorApi.simulate(
        { scenario_type: backendScenarioType, parameters },
        token,
      );

      const baselineCap = backendResponse.monthly_capacity ?? monthlyCapacity;
      const deficit = backendResponse.monthly_deficit ?? Math.max(0, backendResponse.projected_commitments - baselineCap);

      setResult({
        currentHealth: Math.round(backendResponse.change.health.baseline),
        projectedHealth: Math.round(backendResponse.change.health.projected),
        currentHealthLabel: backendResponse.baseline_health,
        projectedHealthLabel: backendResponse.projected_health,
        currentExposure: backendResponse.baseline_exposure,
        projectedExposure: backendResponse.projected_exposure,
        currentMonthly: backendResponse.baseline_commitments,
        projectedMonthly: backendResponse.projected_commitments,
        currentAvailable: currentAvailable,
        projectedAvailable: backendResponse.available_capacity,
        monthlyCapacity: baselineCap,
        monthlyDeficit: deficit,
        addedAmount,
        commitmentType,
        durationMonths: commitmentType !== "subscription" ? durationMonths : undefined,
        backendResponse,
      });
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        onUnauthorized();
      } else {
        setSimulationError(err instanceof ApiError ? err.message : "Unable to run the simulation.");
      }
    } finally {
      setIsSimulating(false);
    }
  }

  const commitmentLabel =
    commitmentType === "emi"
      ? "EMI"
      : commitmentType === "bnpl"
      ? "BNPL"
      : commitmentType === "subscription"
      ? "Subscription"
      : "Commitment";

  const numAmount = parseFloat(amountInput) || 0;
  const totalTenureAmount = commitmentType !== "subscription" && durationMonths > 0 ? numAmount * durationMonths : null;

  if (loadingInitial) {
    return (
      <div className="min-h-[calc(100vh-64px)] flex items-center justify-center p-6 bg-[#090e1c]">
        <div className="flex flex-col items-center gap-3 p-8 rounded-2xl bg-[#0f172a]/80 border border-white/10 shadow-2xl">
          <Loader2 size={24} className="text-indigo-400 animate-spin" />
          <p className="text-sm font-medium text-slate-300">Loading your financial baseline...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-full bg-[#090e1c] text-slate-100 p-4 sm:p-6 lg:p-8 space-y-6 max-w-[1600px] mx-auto">
      {/* ─────────────────────────────────────────────────────────────
          HEADER
      ───────────────────────────────────────────────────────────── */}
      <motion.div
        initial={reduceMotion ? undefined : { opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="flex flex-col lg:flex-row lg:items-center justify-between gap-4"
      >
        <div>
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold uppercase tracking-wider bg-indigo-500/10 text-indigo-400 border border-indigo-500/25 mb-2">
            PLAN AHEAD
          </span>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
            What-If Simulator
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            See how a new financial commitment affects your health and exposure — before you commit.
          </p>
        </div>

        {/* Tip Box on Top Right */}
        <div className="max-w-md p-3.5 rounded-2xl bg-[#0f172a]/80 border border-white/[0.08] shadow-lg flex items-start gap-3">
          <div className="w-7 h-7 rounded-xl bg-amber-500/15 text-amber-400 flex items-center justify-center shrink-0 mt-0.5">
            <Lightbulb size={15} />
          </div>
          <p className="text-xs text-slate-300 leading-relaxed">
            Try different EMI, BNPL, or subscription amounts to see how it impacts your financial health based on your
            actual transaction history.
          </p>
        </div>
      </motion.div>

      {/* ─────────────────────────────────────────────────────────────
          BASELINE INFORMATION BANNER (Truthful User Financial Anchor)
      ───────────────────────────────────────────────────────────── */}
      {(initialError || simulationError) && (
        <div
          role="alert"
          className="p-4 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-sm text-rose-200"
        >
          {simulationError ?? initialError}
        </div>
      )}
      <motion.div
        initial={reduceMotion ? undefined : { opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.05 }}
        className="p-4 rounded-2xl bg-[#0f172a]/80 border border-white/[0.08] shadow-lg flex flex-wrap items-center justify-between gap-4"
      >
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center">
            <Layers size={16} />
          </div>
          <div>
            <span className="text-xs font-semibold text-white block">Current Financial Position</span>
            <span className="text-[11px] text-slate-400">
              Grounded in {user.email}&apos;s verified records
            </span>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-4 sm:gap-6 text-xs">
          <div>
            <div className="flex items-center gap-1">
              <span className="text-slate-400 block text-[10px] uppercase font-mono">Monthly Capacity</span>
              <span className={`text-[9px] font-mono px-1 rounded border ${
                exposure?.current_financial_status.income_source === "Manual"
                  ? "bg-purple-500/15 text-purple-400 border-purple-500/25"
                  : "bg-emerald-500/15 text-emerald-400 border-emerald-500/25"
              }`}>
                {exposure?.current_financial_status.income_source || "Observed"}
              </span>
            </div>
            <span className="font-mono font-bold text-slate-200">{formatMoney(monthlyCapacity)}</span>
          </div>
          {exposure?.current_financial_status.expected_monthly_income && exposure.current_financial_status.expected_monthly_income > 0 && (
            <div>
              <span className="text-purple-400/90 block text-[10px] uppercase font-mono">Expected Salary</span>
              <span className="font-mono font-bold text-purple-300">
                {formatMoney(exposure.current_financial_status.expected_monthly_income)}
              </span>
            </div>
          )}
          <div className="hidden sm:block w-px h-6 bg-white/10" />
          <div>
            <span className="text-slate-400 block text-[10px] uppercase font-mono">Monthly Commitments</span>
            <span className="font-mono font-bold text-white">{formatMoney(currentMonthly)}</span>
          </div>
          <div>
            <span className="text-slate-400 block text-[10px] uppercase font-mono">Existing EMIs</span>
            <span className="font-mono font-semibold text-blue-400">{formatMoney(emiCost)}</span>
          </div>
          <div>
            <span className="text-slate-400 block text-[10px] uppercase font-mono">BNPL Plans</span>
            <span className="font-mono font-semibold text-amber-400">{formatMoney(bnplCost)}</span>
          </div>
          <div>
            <span className="text-slate-400 block text-[10px] uppercase font-mono">Subscriptions</span>
            <span className="font-mono font-semibold text-purple-400">{formatMoney(subCost)}</span>
          </div>
          <div className="hidden sm:block w-px h-6 bg-white/10" />
          <div>
            <span className="text-slate-400 block text-[10px] uppercase font-mono">Available Capacity</span>
            <span className="font-mono font-bold text-emerald-400">{formatMoney(currentAvailable)}</span>
          </div>
          <div>
            <span className="text-slate-400 block text-[10px] uppercase font-mono">Current Exposure</span>
            <span className="font-mono font-bold text-slate-200">{currentExposurePct.toFixed(1)}%</span>
          </div>
        </div>
      </motion.div>

      {/* ─────────────────────────────────────────────────────────────
          MAIN TWO-PANEL WORKSPACE
      ───────────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-[440px_1fr] xl:grid-cols-[480px_1fr] gap-6 items-start">
        {/* LEFT PANEL: 1. Configure Your Scenario */}
        <motion.div
          initial={reduceMotion ? undefined : { opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.1 }}
          className="p-6 rounded-2xl bg-[#0f172a]/85 backdrop-blur-md border border-white/[0.08] shadow-xl shadow-black/20 space-y-6"
        >
          {/* Step Header */}
          <div className="flex items-center gap-2.5 pb-4 border-b border-white/[0.06]">
            <span className="w-6 h-6 rounded-full bg-indigo-600/30 text-indigo-400 font-mono text-xs font-bold flex items-center justify-center">
              1.
            </span>
            <div>
              <h2 className="text-sm font-bold text-white">Configure Your Scenario</h2>
              <p className="text-[11px] text-slate-400">
                Adjust details of your proposed financial commitment.
              </p>
            </div>
          </div>

          {/* Commitment Type Selector: EMI, BNPL, Subscription, Other */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-300">Commitment Type</label>
            <div className="grid grid-cols-2 min-[400px]:grid-cols-4 gap-1.5 p-1 rounded-xl bg-[#090e1c] border border-white/[0.06]">
              {[
                { id: "emi" as const, label: "EMI" },
                { id: "bnpl" as const, label: "BNPL" },
                { id: "subscription" as const, label: "Subscription" },
                { id: "other" as const, label: "Other" },
              ].map((t) => (
                <button
                  key={t.id}
                  onClick={() => handleCommitmentTypeChange(t.id)}
                  className={`py-2 px-1 text-center text-xs font-semibold rounded-lg transition-all cursor-pointer ${
                    commitmentType === t.id
                      ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/30"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          {/* Dynamic Amount Input */}
          <div className="space-y-2">
            <label className="text-xs font-medium text-slate-300">
              New {commitmentLabel} amount (₹/month)
            </label>
            <div className="relative">
              <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 font-mono text-sm">
                ₹
              </span>
              <input
                type="number"
                min="100"
                step="500"
                value={amountInput}
                onChange={(e) => handleAmountChange(e.target.value)}
                placeholder="5000"
                className="w-full pl-9 pr-4 py-2.5 rounded-xl bg-[#090e1c] border border-white/10 text-sm font-mono text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500/60 focus:ring-1 focus:ring-indigo-500/50 transition-all"
              />
            </div>
          </div>

          {/* Duration Selector (Only for commitments with tenures: EMI, BNPL, Other) */}
          {commitmentType !== "subscription" ? (
            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-300">
                Duration {commitmentType === "bnpl" ? "(Installments)" : "(Tenure)"}
              </label>
              <div className="grid grid-cols-4 sm:grid-cols-5 gap-2">
                {(commitmentType === "bnpl"
                  ? [3, 6, 9, 12]
                  : commitmentType === "other"
                  ? [6, 12, 18, 24, 36]
                  : [12, 24, 36, 48, 60]
                ).map((months) => {
                  const active = durationMonths === months;
                  return (
                    <button
                      key={months}
                      onClick={() => handleDurationChange(months)}
                      className={`py-2 px-1 text-center rounded-xl text-xs font-medium transition-all cursor-pointer ${
                        active
                          ? "bg-indigo-600 text-white font-semibold shadow-md shadow-indigo-600/30"
                          : "bg-[#090e1c] hover:bg-white/[0.05] text-slate-400 hover:text-slate-200 border border-white/[0.06]"
                      }`}
                    >
                      {months} mo
                    </button>
                  );
                })}
              </div>
            </div>
          ) : (
            /* Subscriptions Notice: recurring without fixed duration */
            <div className="p-3 rounded-xl bg-purple-500/[0.08] border border-purple-500/20 text-[11px] text-purple-300 flex items-start gap-2">
              <Info size={14} className="text-purple-400 shrink-0 mt-0.5" />
              <span>
                Subscriptions are ongoing recurring commitments that persist month-to-month without a fixed tenure.
              </span>
            </div>
          )}

          {/* Cumulative Tenure Preview */}
          {totalTenureAmount !== null && totalTenureAmount > 0 && (
            <div className="p-3 rounded-xl bg-slate-900/60 border border-white/[0.06] flex items-center justify-between text-xs">
              <span className="text-slate-400">Total Commitment across {durationMonths} mo:</span>
              <span className="font-mono font-bold text-indigo-300">{formatMoney(totalTenureAmount)}</span>
            </div>
          )}

          {/* Informational grounded notice */}
          <div className="p-3.5 rounded-xl bg-indigo-500/[0.07] border border-indigo-500/20 flex items-start gap-2.5">
            <Info size={15} className="text-indigo-400 shrink-0 mt-0.5" />
            <p className="text-[11px] text-slate-300 leading-relaxed">
              This simulation uses your actual income, expenses, and existing commitments from your uploaded
              transaction history.
            </p>
          </div>

          {/* Run Simulation Action Button */}
          <button
            onClick={handleRunSimulation}
            disabled={isSimulating || !amountInput || parseFloat(amountInput) <= 0}
            className="w-full py-3 rounded-xl bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 disabled:opacity-50 text-white font-semibold text-xs shadow-lg shadow-indigo-600/30 flex items-center justify-center gap-2 transition-all active:scale-[0.98] cursor-pointer"
          >
            {isSimulating ? (
              <>
                <Loader2 size={14} className="animate-spin" />
                <span>Simulating Digital Twin...</span>
              </>
            ) : (
              <>
                <Play size={13} className="fill-current" />
                <span>Run Simulation</span>
              </>
            )}
          </button>

          {/* Quick Examples Section */}
          <div className="space-y-3 pt-2">
            <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Quick Examples
            </h4>
            <p className="text-[11px] text-slate-500">Try these common commitments</p>

            <div className="space-y-2">
              {[
                {
                  icon: CarIcon,
                  title: "Car Loan (EMI)",
                  subtitle: "₹15,000 × 60mo",
                  amount: 15000,
                  months: 60,
                  type: "emi" as const,
                },
                {
                  icon: ShoppingBag,
                  title: "Phone (BNPL)",
                  subtitle: "₹4,000 × 6mo",
                  amount: 4000,
                  months: 6,
                  type: "bnpl" as const,
                },
                {
                  icon: CreditCard,
                  title: "Cloud Software (Sub)",
                  subtitle: "₹1,200/mo ongoing",
                  amount: 1200,
                  months: undefined,
                  type: "subscription" as const,
                },
                {
                  icon: HomeLoanIcon,
                  title: "Personal Loan",
                  subtitle: "₹10,000 × 36mo",
                  amount: 10000,
                  months: 36,
                  type: "emi" as const,
                },
              ].map((ex) => (
                <div
                  key={ex.title}
                  className="p-3 rounded-xl bg-[#090e1c] border border-white/[0.06] hover:border-white/15 flex items-center justify-between transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-indigo-500/10 text-indigo-400 flex items-center justify-center">
                      <ex.icon size={15} />
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-white">{ex.title}</p>
                      <p className="text-[11px] font-mono text-slate-400">{ex.subtitle}</p>
                    </div>
                  </div>

                  <button
                    onClick={() => handleQuickPreset(ex.amount, ex.months, ex.type)}
                    className="px-3 py-1.5 rounded-lg bg-white/[0.06] hover:bg-indigo-600/30 hover:text-indigo-300 text-xs text-slate-300 transition-colors cursor-pointer"
                  >
                    Try
                  </button>
                </div>
              ))}
            </div>
          </div>
        </motion.div>

        {/* RIGHT PANEL: 2. Projected Impact */}
        <motion.div
          initial={reduceMotion ? undefined : { opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.2 }}
          className="p-6 rounded-2xl bg-[#0f172a]/85 backdrop-blur-md border border-white/[0.08] shadow-xl shadow-black/20 space-y-6"
        >
          {/* Header */}
          <div className="flex items-center justify-between pb-4 border-b border-white/[0.06]">
            <div className="flex items-center gap-2.5">
              <span className="w-6 h-6 rounded-full bg-indigo-600/30 text-indigo-400 font-mono text-xs font-bold flex items-center justify-center">
                2.
              </span>
              <div>
                <h2 className="text-sm font-bold text-white">Projected Impact</h2>
                <p className="text-[11px] text-slate-400">
                  See how this commitment changes your financial position.
                </p>
              </div>
            </div>

            {result && (
              <button
                onClick={() => setResult(null)}
                className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-white cursor-pointer transition-colors"
              >
                <RotateCcw size={12} />
                <span>Reset</span>
              </button>
            )}
          </div>

          {/* Empty State before simulation */}
          {!result ? (
            <div className="py-24 px-6 text-center space-y-3">
              <div className="w-14 h-14 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 mx-auto flex items-center justify-center">
                <Gauge size={26} />
              </div>
              <h3 className="text-base font-semibold text-white">Configure a scenario</h3>
              <p className="text-xs text-slate-400 max-w-sm mx-auto leading-relaxed">
                Enter a commitment amount and type on the left, then click &ldquo;Run Simulation&rdquo;
                to calculate live health and exposure deltas.
              </p>
            </div>
          ) : (
            <div className="space-y-6">
              {/* 4 Comparison Metric Cards */}
              <div className="grid grid-cols-2 xl:grid-cols-4 gap-3.5">
                {/* 1. Health Score */}
                <div className="p-4 rounded-xl bg-[#090e1c] border border-white/[0.06] space-y-2">
                  <div className="flex items-center gap-1.5 text-[11px] text-slate-400">
                    <Heart size={13} className="text-rose-400" />
                    <span>Health Score</span>
                  </div>
                  <div className="flex items-baseline gap-2 font-mono">
                    <span className="text-lg font-bold text-slate-200">{result.currentHealth}</span>
                    <span className="text-slate-500">→</span>
                    <span
                      className={`text-lg font-bold ${
                        result.projectedHealth >= 80
                          ? "text-emerald-400"
                          : result.projectedHealth >= 65
                          ? "text-blue-400"
                          : result.projectedHealth >= 45
                          ? "text-amber-400"
                          : "text-rose-400"
                      }`}
                    >
                      {result.projectedHealth}
                    </span>
                  </div>
                  <p className="text-[10px] text-slate-400 flex items-center gap-1">
                    <span>{result.currentHealthLabel}</span>
                    <span>→</span>
                    <span className="font-medium text-slate-300">{result.projectedHealthLabel}</span>
                  </p>
                </div>

                {/* 2. Exposure */}
                <div className="p-4 rounded-xl bg-[#090e1c] border border-white/[0.06] space-y-2">
                  <div className="flex items-center gap-1.5 text-[11px] text-slate-400">
                    <Clock size={13} className="text-amber-400" />
                    <span>Exposure</span>
                  </div>
                  <div className="flex items-baseline gap-2 font-mono">
                    <span className="text-lg font-bold text-slate-200">{result.currentExposure.toFixed(1)}%</span>
                    <span className="text-slate-500">→</span>
                    <span
                      className={`text-lg font-bold ${
                        result.projectedExposure <= 35
                          ? "text-emerald-400"
                          : result.projectedExposure <= 55
                          ? "text-amber-400"
                          : "text-rose-400"
                      }`}
                    >
                      {result.projectedExposure.toFixed(1)}%
                    </span>
                  </div>
                  <p className="text-[10px] text-slate-400">
                    +{Math.max(0, result.projectedExposure - result.currentExposure).toFixed(1)}% of capacity
                  </p>
                </div>

                {/* 3. Monthly Commitments */}
                <div className="p-4 rounded-xl bg-[#090e1c] border border-white/[0.06] space-y-2">
                  <div className="flex items-center gap-1.5 text-[11px] text-slate-400">
                    <Coins size={13} className="text-indigo-400" />
                    <span>Monthly Commitments</span>
                  </div>
                  <div className="flex flex-col font-mono">
                    <div className="flex items-baseline gap-1 text-xs text-slate-400">
                      <span>{formatMoney(result.currentMonthly)}</span>
                      <span className="text-slate-500">→</span>
                    </div>
                    <span className="text-base font-bold text-white">
                      {formatMoney(result.projectedMonthly)}
                    </span>
                  </div>
                  <p className="text-[10px] text-slate-400 font-mono">
                    +{formatMoney(result.addedAmount)}/mo
                  </p>
                </div>

                {/* 4. Available Capacity */}
                <div className="p-4 rounded-xl bg-[#090e1c] border border-white/[0.06] space-y-2">
                  <div className="flex items-center gap-1.5 text-[11px] text-slate-400">
                    <Gauge size={13} className="text-emerald-400" />
                    <span>Available Capacity</span>
                  </div>
                  <div className="flex flex-col font-mono">
                    <div className="flex items-baseline gap-1 text-xs text-slate-400">
                      <span>{formatMoney(result.currentAvailable)}</span>
                      <span className="text-slate-500">→</span>
                    </div>
                    <span
                      className={`text-base font-bold ${
                        result.projectedAvailable > 0 ? "text-emerald-400" : "text-rose-400"
                      }`}
                    >
                      {formatMoney(result.projectedAvailable)}
                    </span>
                  </div>
                  <p className="text-[10px] text-slate-400">
                    {result.monthlyDeficit > 0 ? `Deficit: ${formatMoney(result.monthlyDeficit)}` : "Uncommitted buffer"}
                  </p>
                </div>
              </div>

              {/* Monthly Commitments Comparison Chart */}
              <div className="p-5 rounded-xl bg-[#090e1c] border border-white/[0.06] space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <h3 className="text-xs font-bold text-white">Monthly Commitments Comparison</h3>
                    <p className="text-[11px] text-slate-400">
                      Current commitments vs. with proposed {result.commitmentType.toUpperCase()}
                    </p>
                  </div>

                  {/* Chart Legend */}
                  <div className="flex flex-wrap items-center gap-3 text-[10px] text-slate-400">
                    <span className="flex items-center gap-1">
                      <span className="w-2 h-2 rounded bg-indigo-500" />
                      New {result.commitmentType.toUpperCase()} ({formatMoney(result.addedAmount)})
                    </span>
                    {subCost > 0 && (
                      <span className="flex items-center gap-1">
                        <span className="w-2 h-2 rounded bg-purple-500" />
                        Subscriptions ({formatMoney(subCost)})
                      </span>
                    )}
                    {bnplCost > 0 && (
                      <span className="flex items-center gap-1">
                        <span className="w-2 h-2 rounded bg-amber-500" />
                        BNPL ({formatMoney(bnplCost)})
                      </span>
                    )}
                    {emiCost > 0 && (
                      <span className="flex items-center gap-1">
                        <span className="w-2 h-2 rounded bg-blue-500" />
                        Existing EMIs ({formatMoney(emiCost)})
                      </span>
                    )}
                  </div>
                </div>

                {/* SVG Visual Bars with Proportional Heights */}
                <div className="pt-2">
                  {(() => {
                    const maxScale = Math.max(result.projectedMonthly, result.currentMonthly, 1);
                    const currentBarHeightPct = Math.max(15, (result.currentMonthly / maxScale) * 100);
                    const projectedBarHeightPct = Math.max(15, (result.projectedMonthly / maxScale) * 100);

                    // Sub-components as percentage of their respective bar
                    const currentTotal = result.currentMonthly || 1;
                    const projTotal = result.projectedMonthly || 1;

                    return (
                      <div className="grid grid-cols-2 gap-8 max-w-md mx-auto items-end h-52 px-4 border-b border-white/10 pb-2">
                        {/* Current Bar */}
                        <div className="flex flex-col items-center gap-2 h-full justify-end">
                          <span className="text-xs font-mono font-bold text-slate-200">
                            {formatMoney(result.currentMonthly)}
                          </span>
                          <div
                            style={{ height: `${currentBarHeightPct}%` }}
                            className="w-20 rounded-t-lg overflow-hidden flex flex-col justify-end bg-slate-800 transition-all duration-300"
                          >
                            {/* Subscriptions */}
                            {subCost > 0 && (
                              <div
                                style={{ height: `${(subCost / currentTotal) * 100}%` }}
                                className="w-full bg-purple-500"
                                title={`Subscriptions: ${formatMoney(subCost)}`}
                              />
                            )}
                            {/* BNPL */}
                            {bnplCost > 0 && (
                              <div
                                style={{ height: `${(bnplCost / currentTotal) * 100}%` }}
                                className="w-full bg-amber-500"
                                title={`BNPL: ${formatMoney(bnplCost)}`}
                              />
                            )}
                            {/* Existing EMIs */}
                            {emiCost > 0 && (
                              <div
                                style={{ height: `${(emiCost / currentTotal) * 100}%` }}
                                className="w-full bg-blue-500"
                                title={`Existing EMIs: ${formatMoney(emiCost)}`}
                              />
                            )}
                          </div>
                          <span className="text-[11px] font-medium text-slate-400">Current</span>
                        </div>

                        {/* With New Commitment Bar */}
                        <div className="flex flex-col items-center gap-2 h-full justify-end">
                          <span className="text-xs font-mono font-bold text-indigo-400">
                            {formatMoney(result.projectedMonthly)}
                          </span>
                          <div
                            style={{ height: `${projectedBarHeightPct}%` }}
                            className="w-20 rounded-t-lg overflow-hidden flex flex-col justify-end bg-slate-800 border-2 border-indigo-500/50 shadow-[0_0_15px_rgba(99,102,241,0.25)] transition-all duration-300"
                          >
                            {/* New Commitment Added */}
                            <div
                              style={{ height: `${(result.addedAmount / projTotal) * 100}%` }}
                              className="w-full bg-indigo-500 animate-pulse"
                              title={`New Commitment: ${formatMoney(result.addedAmount)}`}
                            />
                            {/* Subscriptions */}
                            {subCost > 0 && (
                              <div
                                style={{ height: `${(subCost / projTotal) * 100}%` }}
                                className="w-full bg-purple-500"
                                title={`Subscriptions: ${formatMoney(subCost)}`}
                              />
                            )}
                            {/* BNPL */}
                            {bnplCost > 0 && (
                              <div
                                style={{ height: `${(bnplCost / projTotal) * 100}%` }}
                                className="w-full bg-amber-500"
                                title={`BNPL: ${formatMoney(bnplCost)}`}
                              />
                            )}
                            {/* Existing EMIs */}
                            {emiCost > 0 && (
                              <div
                                style={{ height: `${(emiCost / projTotal) * 100}%` }}
                                className="w-full bg-blue-500"
                                title={`Existing EMIs: ${formatMoney(emiCost)}`}
                              />
                            )}
                          </div>
                          <span className="text-[11px] font-medium text-indigo-300">
                            With New {result.commitmentType.toUpperCase()}
                          </span>
                        </div>
                      </div>
                    );
                  })()}
                </div>
              </div>

              {/* Key Insights */}
              <div className="p-5 rounded-xl bg-[#090e1c] border border-white/[0.06] space-y-3">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-indigo-400" />
                  <h3 className="text-xs font-bold text-white">Key Insights</h3>
                </div>

                <div className="space-y-2.5 text-xs text-slate-300">
                  {/* Health Score Insight */}
                  <div className="flex items-start gap-2.5">
                    <Heart size={14} className="text-rose-400 shrink-0 mt-0.5" />
                    <p className="leading-relaxed">
                      {result.currentHealth > result.projectedHealth ? (
                        <>
                          Your health score is projected to adjust by{" "}
                          <span className="font-semibold text-rose-400">
                            -{result.currentHealth - result.projectedHealth} points
                          </span>{" "}
                          (from {result.currentHealth} to {result.projectedHealth})
                          {result.currentHealthLabel === result.projectedHealthLabel ? (
                            <>
                              , remaining in the{" "}
                              <span className="font-semibold text-slate-200">{result.projectedHealthLabel}</span> range.
                            </>
                          ) : (
                            <>
                              , shifting from {result.currentHealthLabel} to the{" "}
                              <span className="font-semibold text-amber-300">{result.projectedHealthLabel}</span> range.
                            </>
                          )}
                        </>
                      ) : result.currentHealth < result.projectedHealth ? (
                        <>
                          Your health score is projected to improve by{" "}
                          <span className="font-semibold text-emerald-400">
                            +{result.projectedHealth - result.currentHealth} points
                          </span>{" "}
                          (from {result.currentHealth} to {result.projectedHealth}), reaching the{" "}
                          <span className="font-semibold text-slate-200">{result.projectedHealthLabel}</span> range.
                        </>
                      ) : (
                        <>
                          Your health score will remain stable at{" "}
                          <span className="font-semibold text-slate-200">{result.currentHealth}</span> in the{" "}
                          <span className="font-semibold text-slate-200">{result.projectedHealthLabel}</span> range.
                        </>
                      )}
                    </p>
                  </div>

                  {/* Exposure Insight */}
                  <div className="flex items-start gap-2.5">
                    <Clock size={14} className="text-amber-400 shrink-0 mt-0.5" />
                    <p className="leading-relaxed">
                      Your exposure will increase from{" "}
                      <span className="font-mono text-slate-200">{result.currentExposure.toFixed(1)}%</span> to{" "}
                      <span className="font-mono text-amber-400 font-semibold">{result.projectedExposure.toFixed(1)}%</span> of
                      your monthly financial capacity ({formatMoney(result.monthlyCapacity)}).
                    </p>
                  </div>

                  {/* Capacity Insight */}
                  <div className="flex items-start gap-2.5">
                    <CheckCircle2 size={14} className="text-emerald-400 shrink-0 mt-0.5" />
                    <p className="leading-relaxed">
                      {result.projectedAvailable > 0 ? (
                        <>
                          You will still retain{" "}
                          <span className="font-mono font-semibold text-emerald-400">
                            {formatMoney(result.projectedAvailable)}
                          </span>{" "}
                          in uncommitted capacity buffer each month.
                        </>
                      ) : (
                        <>
                          This commitment will exceed your monthly financial capacity by{" "}
                          <span className="font-mono font-semibold text-rose-400">
                            {formatMoney(result.monthlyDeficit)}
                          </span>
                          , leaving no uncommitted capacity buffer.
                        </>
                      )}
                    </p>
                  </div>

                  {/* Tenure / Cumulative Insight */}
                  {result.durationMonths && (
                    <div className="flex items-start gap-2.5">
                      <Coins size={14} className="text-indigo-400 shrink-0 mt-0.5" />
                      <p className="leading-relaxed">
                        Over the full {result.durationMonths}-month tenure, your cumulative commitment will total{" "}
                        <span className="font-mono font-semibold text-indigo-300">
                          {formatMoney(result.addedAmount * result.durationMonths)}
                        </span>
                        .
                      </p>
                    </div>
                  )}

                  {/* FinSight Advice */}
                  {result.backendResponse.recommendation && (
                    <div className="flex items-start gap-2.5 pt-1 border-t border-white/[0.04]">
                      <Sparkles size={14} className="text-indigo-400 shrink-0 mt-0.5" />
                      <p className="leading-relaxed text-indigo-300 font-medium">
                        FinSight Advice: {result.backendResponse.recommendation}
                      </p>
                    </div>
                  )}

                  {/* Risk Interpretation */}
                  {result.backendResponse.risk_interpretation && (
                    <div className="flex items-start gap-2.5 pt-1 border-t border-white/[0.04]">
                      <ShieldAlert size={14} className="text-amber-400 shrink-0 mt-0.5" />
                      <p className="leading-relaxed text-slate-300">
                        {result.backendResponse.risk_interpretation}
                      </p>
                    </div>
                  )}

                  <div className="flex items-start gap-2.5 pt-1 text-slate-500 text-[11px]">
                    <Info size={13} className="shrink-0 mt-0.5" />
                    <p>
                      This simulation is grounded in your verified financial data. Variable expenses and unplanned costs
                      may affect net monthly savings.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </motion.div>
      </div>
    </div>
  );
}

// Quick icons
function CarIcon(props: { size?: number }) {
  return (
    <svg width={props.size || 16} height={props.size || 16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.4 2.9A3.7 3.7 0 0 0 2 12v4c0 .6.4 1 1 1h2" />
      <circle cx="7" cy="17" r="2" />
      <path d="M9 17h6" />
      <circle cx="17" cy="17" r="2" />
    </svg>
  );
}

function HomeLoanIcon(props: { size?: number }) {
  return (
    <svg width={props.size || 16} height={props.size || 16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
      <polyline points="9 22 9 12 15 12 15 22" />
    </svg>
  );
}
