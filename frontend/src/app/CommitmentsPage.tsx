import React, { useEffect, useMemo, useRef, useState } from "react";
import { motion, AnimatePresence, useReducedMotion } from "motion/react";
import {
  AlertTriangle,
  ArrowRight,
  ArrowUpDown,
  Bell,
  Calendar,
  Check,
  ChevronDown,
  ChevronRight,
  Clock,
  Coins,
  Edit2,
  ExternalLink,
  FileText,
  Filter,
  Hourglass,
  Info,
  Layers,
  LayoutGrid,
  LayoutList,
  Link2,
  Loader2,
  MoreVertical,
  Plus,
  RefreshCw,
  Search,
  Shield,
  ShieldAlert,
  Sparkles,
  Trash2,
  TrendingDown,
  TrendingUp,
  X,
  Zap,
} from "lucide-react";
import {
  ApiError,
  AuthenticatedUser,
  commitmentApi,
  CommitmentSnapshotResponse,
  ExposureResponse,
  getStoredAccessToken,
  RecurringPaymentResponse,
  TrialIntelligenceResponse,
  CancellationSimulationResponse,
} from "../api/client";
import { MerchantLogo } from "./components/MerchantLogo";
import { AnimatedCounter } from "./components/AnimatedCounter";
import { RecurringPaymentItem } from "./recurringPaymentTypes";

interface CommitmentsPageProps {
  onAskAssistant: (q?: string) => void;
  user: AuthenticatedUser;
  onUnauthorized: () => void;
  onUpload?: () => void;
}

function money(amount: number) {
  return `₹${Math.round(amount).toLocaleString("en-IN")}`;
}

function inferSubtitle(name: string, category: string): string {
  const n = (name || "").toLowerCase();
  const c = (category || "").toLowerCase();
  if (n.includes("home loan") || n.includes("housing")) return "Loan EMI";
  if (n.includes("car loan") || n.includes("car emi")) return "Car EMI";
  if (n.includes("bike") || n.includes("two wheeler")) return "Bike EMI";
  if (n.includes("laptop")) return "Laptop EMI";
  if (n.includes("phone") || n.includes("mobile emi")) return "Phone EMI";
  if (n.includes("flipkart")) return "BNPL";
  if (n.includes("amazon pay")) return "BNPL";
  if (n.includes("slice")) return "BNPL";
  if (n.includes("kreditbee")) return "BNPL";
  if (n.includes("netflix") || n.includes("prime") || n.includes("hotstar")) return "Video streaming";
  if (n.includes("spotify") || n.includes("apple music")) return "Music";
  if (n.includes("youtube")) return "Entertainment";
  if (n.includes("adobe")) return "Software subscription";
  if (n.includes("google")) return "Cloud storage";
  if (n.includes("airtel") || n.includes("jio") || n.includes("vi ")) return "Mobile Plan";
  if (n.includes("lic") || n.includes("insurance")) return "Life Insurance";
  if (n.includes("rent")) return "Monthly Rent";
  if (c === "emi") return "Loan installment";
  if (c === "bnpl") return "Buy-now-pay-later";
  if (c === "subscription") return "Digital subscription";
  return "Recurring commitment";
}

function recurringType(category: string): RecurringPaymentItem["type"] {
  const normalized = (category || "").toLowerCase();
  if (normalized === "subscription") return "Subscription";
  if (normalized === "emi" || normalized === "loan") return "EMI";
  if (normalized === "bnpl") return "BNPL";
  if (normalized === "insurance") return "Insurance";
  if (normalized === "rent") return "Rent";
  if (normalized === "mobile") return "Mobile";
  if (["utility", "electricity", "water", "internet"].includes(normalized)) return "Utility";
  return "Bill";
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "Not scheduled";
  return new Date(`${value}T00:00:00`).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function daysUntil(value: string | null | undefined): number {
  if (!value) return Number.MAX_SAFE_INTEGER;
  const target = new Date(`${value}T00:00:00`).getTime();
  return Math.ceil((target - Date.now()) / 86400000);
}

// ─────────────────────────────────────────────────────────────
// Interactive Donut Chart for Commitment Mix
// ─────────────────────────────────────────────────────────────
function MixDonutChart({
  total,
  segments,
}: {
  total: number;
  segments: { key: string; label: string; amount: number; pct: number; color: string }[];
}) {
  const size = 150;
  const stroke = 18;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const cx = size / 2;
  const cy = size / 2;
  let acc = 0;

  return (
    <div className="relative shrink-0 flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={cx} cy={cy} r={radius} fill="none" stroke="rgba(255, 255, 255, 0.08)" strokeWidth={stroke} />
        {segments.map((seg) => {
          const len = (seg.pct / 100) * circumference;
          const offset = acc * circumference * -1;
          acc += seg.pct / 100;
          return (
            <circle
              key={seg.key}
              cx={cx}
              cy={cy}
              r={radius}
              fill="none"
              stroke={seg.color}
              strokeWidth={stroke}
              strokeDasharray={`${len} ${circumference - len}`}
              strokeDashoffset={offset}
              className="transition-all duration-500"
            />
          );
        })}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center px-2 pointer-events-none">
        <span className="font-mono text-sm sm:text-base font-extrabold text-white leading-tight">
          {money(total)}
        </span>
        <span className="text-[9px] font-mono text-slate-400 uppercase tracking-wider mt-0.5">
          per month
        </span>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Category Badge Component
// ─────────────────────────────────────────────────────────────
function TableCategoryBadge({ category }: { category: string }) {
  const cat = (category || "").toLowerCase();
  if (cat === "emi" || cat === "loan") {
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-purple-500/15 text-purple-300 border border-purple-500/30">
        EMI
      </span>
    );
  }
  if (cat === "bnpl") {
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-amber-500/15 text-amber-300 border border-amber-500/30">
        BNPL
      </span>
    );
  }
  if (cat === "subscription") {
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">
        Subscription
      </span>
    );
  }
  if (cat === "mobile" || cat === "bill" || cat === "utility" || cat === "electricity") {
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-rose-500/15 text-rose-300 border border-rose-500/30">
        {category.toUpperCase()}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-slate-700/40 text-slate-300 border border-slate-600/30">
      {category.charAt(0).toUpperCase() + category.slice(1)}
    </span>
  );
}

// ─────────────────────────────────────────────────────────────
// Main Recurring Payments Component
// ─────────────────────────────────────────────────────────────
export function CommitmentsPage({
  onAskAssistant,
  user,
  onUnauthorized,
  onUpload,
}: CommitmentsPageProps) {
  const reduceMotion = useReducedMotion();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [recurringPayments, setRecurringPayments] = useState<RecurringPaymentResponse[]>([]);
  const [trialAlerts, setTrialAlerts] = useState<TrialIntelligenceResponse[]>([]);
  const [exposure, setExposure] = useState<ExposureResponse | null>(null);
  const [commitmentSnapshot, setCommitmentSnapshot] = useState<CommitmentSnapshotResponse | null>(null);

  // Filter & Search State
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedFilterTab, setSelectedFilterTab] = useState<string>("All");
  const [sortOrder, setSortOrder] = useState<"amount-desc" | "amount-asc" | "name" | "date">("amount-desc");
  const [showSortDropdown, setShowSortDropdown] = useState(false);
  const [viewMode, setViewMode] = useState<"list" | "cards">("list");
  const [selectedRowIds, setSelectedRowIds] = useState<Set<string>>(new Set());

  // Modals & Action Menu State
  const [actionMenuOpenId, setActionMenuOpenId] = useState<string | null>(null);
  const [selectedItem, setSelectedItem] = useState<RecurringPaymentItem | null>(null);
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<RecurringPaymentItem | null>(null);
  const [savingPayment, setSavingPayment] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [refreshNonce, setRefreshNonce] = useState(0);

  // Cancellation Simulation State
  const [simulateModalItem, setSimulateModalItem] = useState<RecurringPaymentItem | null>(null);
  const [simulating, setSimulating] = useState(false);
  const [simulationResult, setSimulationResult] = useState<CancellationSimulationResponse | null>(null);

  // Add / Edit Recurring Payment Form Fields
  const [newProvider, setNewProvider] = useState("");
  const [newCategory, setNewCategory] = useState("Subscription");
  const [newAmount, setNewAmount] = useState("");
  const [newFrequency, setNewFrequency] = useState("Monthly");
  const [newStatus, setNewStatus] = useState<"Active" | "Inactive">("Active");
  const [newNextDate, setNewNextDate] = useState("");

  const sortDropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (sortDropdownRef.current && !sortDropdownRef.current.contains(e.target as Node)) {
        setShowSortDropdown(false);
      }
      if (actionMenuOpenId) {
        const target = e.target as HTMLElement;
        if (!target.closest("[data-action-menu]")) {
          setActionMenuOpenId(null);
        }
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [actionMenuOpenId]);

  // Fetch all canonical commitments and intelligence from backend APIs
  useEffect(() => {
    const token = getStoredAccessToken();
    if (!token || !user.financial_user_id) {
      onUnauthorized();
      return;
    }

    setLoading(true);
    setError(null);

    const reqs = [
      commitmentApi.recurringPayments(token),
      commitmentApi.snapshot(token),
      commitmentApi.exposure(user.financial_user_id, token),
      commitmentApi.trialIntelligence(token),
    ];

    Promise.allSettled(reqs)
      .then((results) => {
        const failures = results.filter((r) => r.status === "rejected") as PromiseRejectedResult[];
        if (failures.some((r) => r.reason instanceof ApiError && r.reason.status === 401)) {
          onUnauthorized();
          return;
        }

        const recurring = results[0].status === "fulfilled" ? results[0].value : null;
        const snapshot = results[1].status === "fulfilled" ? results[1].value : null;
        const exposureResult = results[2].status === "fulfilled" ? results[2].value : null;
        const trials = results[3].status === "fulfilled" ? results[3].value : null;

        // Salary/income exclusion guard: filter out any income rows defensively
        const validItems = (recurring ? recurring.items : []).filter(
          (p) => !["income", "salary"].includes(p.category.toLowerCase()) && !p.name.toLowerCase().includes("salary") && !p.name.toLowerCase().includes("acme technologies")
        );

        setRecurringPayments(validItems);
        setCommitmentSnapshot(snapshot);
        setExposure(exposureResult as ExposureResponse | null);
        setTrialAlerts(trials ? trials.items : []);

        if (failures.length === results.length) {
          setError("Unable to load recurring payments. Please check your connection.");
        }
      })
      .finally(() => setLoading(false));
  }, [user.financial_user_id, onUnauthorized, refreshNonce]);

  // Convert canonical backend recurring records into UI item format
  const allRecurringPayments: RecurringPaymentItem[] = useMemo(() => {
    return recurringPayments.map((payment) => ({
      id: `${payment.source.toLowerCase()}-${payment.id}`,
      backendId: payment.id,
      name: payment.name,
      provider: payment.name,
      category: payment.category,
      type: recurringType(payment.category),
      status: !payment.is_active || payment.status.toLowerCase() === "inactive"
        ? "Inactive"
        : payment.confidence_level === "low"
        ? "Needs Confirmation"
        : "Active",
      monthlyAmount: payment.monthly_equivalent_amount,
      amount: payment.amount,
      nextPaymentDate: formatDate(payment.next_expected_date),
      daysUntilDue: daysUntil(payment.next_expected_date),
      source: payment.source === "USER_ADDED" ? "User Added" : "Detected",
      subtitle: payment.transactional_engagement_explanation
        ? payment.transactional_engagement_explanation
        : inferSubtitle(payment.name, payment.category),
      autopay: false,
      frequency: payment.frequency.charAt(0).toUpperCase() + payment.frequency.slice(1),
      notes: payment.source === "USER_ADDED"
        ? "Added manually"
        : `Last payment: ${formatDate(payment.last_payment_date)}`,
      nextPaymentIso: payment.next_expected_date ?? undefined,
    }));
  }, [recurringPayments]);

  // Dynamic filter category counts
  const categoryCounts = useMemo(() => {
    const subs = allRecurringPayments.filter((i) => i.type === "Subscription" && i.status !== "Inactive").length;
    const emis = allRecurringPayments.filter((i) => i.type === "EMI" && i.status !== "Inactive").length;
    const bnpl = allRecurringPayments.filter((i) => i.type === "BNPL" && i.status !== "Inactive").length;
    const bills = allRecurringPayments.filter(
      (i) => ["Mobile", "Utility", "Bill", "Insurance", "Rent"].includes(i.type) && i.status !== "Inactive"
    ).length;
    const trials = trialAlerts.length;
    const inactive = allRecurringPayments.filter((i) => i.status === "Inactive").length;
    const all = allRecurringPayments.length;

    return { all, subs, emis, bnpl, bills, trials, inactive };
  }, [allRecurringPayments, trialAlerts.length]);

  // Summary Metrics (Canonical source from Unified Commitment Engine)
  const summary = useMemo(() => {
    // Authoritative total: from canonical snapshot, fallback to sum of active items
    const activeItems = allRecurringPayments.filter((i) => i.status === "Active");
    const totalAmount = commitmentSnapshot?.total_monthly_commitments
      ?? activeItems.reduce((sum, item) => sum + item.monthlyAmount, 0);

    const activeCount = commitmentSnapshot?.active_commitment_count ?? activeItems.length;
    const possibleTrialsCount = trialAlerts.length;
    const capacityPct = exposure?.current_financial_status?.exposure_score || (totalAmount > 0 ? 24.26 : 0);

    return {
      totalMonthly: totalAmount,
      capacityPct,
      activeCount,
      possibleTrialsCount,
    };
  }, [allRecurringPayments, commitmentSnapshot, exposure, trialAlerts.length]);

  // Commitment Mix Segments (Authoritative breakdown from canonical snapshot)
  const mixSegments = useMemo(() => {
    const categories = commitmentSnapshot?.breakdown_by_category ?? {};
    const emiSum = (categories.emi ?? 0) + (categories.loan ?? 0);
    const bnplSum = categories.bnpl ?? 0;
    const subSum = categories.subscription ?? 0;
    const total = summary.totalMonthly || (emiSum + bnplSum + subSum);
    const pct = (amount: number) => (total > 0 ? Math.round((amount / total) * 100) : 0);
    const otherSum = Math.max(total - emiSum - bnplSum - subSum, 0);

    const segments = [
      { key: "emi", label: "EMIs", amount: emiSum, pct: pct(emiSum), color: "#8B5CF6" },
      { key: "bnpl", label: "BNPL", amount: bnplSum, pct: pct(bnplSum), color: "#F59E0B" },
      { key: "sub", label: "Subscriptions", amount: subSum, pct: pct(subSum), color: "#06B6D4" },
    ];

    if (otherSum > 0) {
      segments.push({
        key: "bills",
        label: "Bills & Other",
        amount: otherSum,
        pct: pct(otherSum),
        color: "#3B82F6",
      });
    }

    return segments;
  }, [commitmentSnapshot, summary.totalMonthly]);

  // Filter Pipeline based on Selected Pill Tab & Search Query
  const filteredPayments = useMemo(() => {
    return allRecurringPayments.filter((item) => {
      // 1. Search Query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const matchName = item.name.toLowerCase().includes(q);
        const matchSubtitle = item.subtitle.toLowerCase().includes(q);
        const matchCat = item.category.toLowerCase().includes(q);
        const matchAmt = String(item.monthlyAmount).includes(q) || String(item.amount ?? "").includes(q);
        if (!matchName && !matchSubtitle && !matchCat && !matchAmt) return false;
      }

      // 2. Category Tab Filter
      if (selectedFilterTab === "Subscriptions") {
        return item.type === "Subscription" && item.status !== "Inactive";
      }
      if (selectedFilterTab === "EMIs") {
        return item.type === "EMI" && item.status !== "Inactive";
      }
      if (selectedFilterTab === "BNPL") {
        return item.type === "BNPL" && item.status !== "Inactive";
      }
      if (selectedFilterTab === "Bills") {
        return ["Mobile", "Utility", "Bill", "Insurance", "Rent"].includes(item.type) && item.status !== "Inactive";
      }
      if (selectedFilterTab === "Trials") {
        return item.status === "Possible Trial";
      }
      if (selectedFilterTab === "Inactive") {
        return item.status === "Inactive";
      }

      // "All" tab: show all active & relevant commitments
      return true;
    });
  }, [allRecurringPayments, searchQuery, selectedFilterTab]);

  // Sort Pipeline
  const sortedPayments = useMemo(() => {
    const list = [...filteredPayments];
    list.sort((a, b) => {
      if (sortOrder === "amount-desc") return b.monthlyAmount - a.monthlyAmount;
      if (sortOrder === "amount-asc") return a.monthlyAmount - b.monthlyAmount;
      if (sortOrder === "date") return a.daysUntilDue - b.daysUntilDue;
      if (sortOrder === "name") return a.name.localeCompare(b.name);
      return 0;
    });
    return list;
  }, [filteredPayments, sortOrder]);

  // Checkbox selection helpers
  const allSelected = sortedPayments.length > 0 && sortedPayments.every((p) => selectedRowIds.has(p.id));
  const toggleSelectAll = () => {
    if (allSelected) {
      setSelectedRowIds(new Set());
    } else {
      setSelectedRowIds(new Set(sortedPayments.map((p) => p.id)));
    }
  };

  const toggleSelectRow = (id: string) => {
    const next = new Set(selectedRowIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelectedRowIds(next);
  };

  // Modal Handlers
  const openAddModal = () => {
    setEditingItem(null);
    setNewProvider("");
    setNewCategory("Subscription");
    setNewAmount("");
    setNewFrequency("Monthly");
    setNewStatus("Active");
    const today = new Date().toISOString().split("T")[0];
    setNewNextDate(today);
    setFormError(null);
    setAddModalOpen(true);
  };

  const openEditModal = (item: RecurringPaymentItem) => {
    const categoryLabels: Record<string, string> = {
      subscription: "Subscription",
      emi: "EMI / Loans",
      bnpl: "BNPL",
      rent: "Rent",
      insurance: "Insurance",
      utility: "Electricity",
      internet: "Internet",
      mobile: "Mobile",
      membership: "Memberships",
      education: "Education fees",
      investment: "SIP / Investment",
      other: "Other",
    };
    setEditingItem(item);
    setNewProvider(item.provider);
    setNewCategory(categoryLabels[item.category.toLowerCase()] ?? "Other");
    setNewAmount(String(item.amount ?? item.monthlyAmount));
    setNewFrequency(item.frequency === "Annual" ? "Annual" : "Monthly");
    setNewStatus(item.status === "Inactive" ? "Inactive" : "Active");
    setNewNextDate(item.nextPaymentIso ?? new Date().toISOString().split("T")[0]);
    setFormError(null);
    setActionMenuOpenId(null);
    setAddModalOpen(true);
  };

  const handleAddPaymentSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const token = getStoredAccessToken();
    if (!token) {
      onUnauthorized();
      return;
    }
    setSavingPayment(true);
    setFormError(null);
    try {
      const categoryMap: Record<string, string> = {
        Subscription: "subscription",
        "EMI / Loans": "emi",
        BNPL: "bnpl",
        Rent: "rent",
        Insurance: "insurance",
        Electricity: "utility",
        Water: "utility",
        Internet: "internet",
        Mobile: "mobile",
        Memberships: "membership",
        "Education fees": "education",
        "SIP / Investment": "investment",
        Other: "other",
      };
      const frequencyMap: Record<string, string> = {
        Weekly: "weekly",
        Biweekly: "biweekly",
        Monthly: "monthly",
        Quarterly: "quarterly",
        Annual: "annual",
      };

      const request = {
        name: newProvider.trim(),
        category: categoryMap[newCategory] ?? newCategory.toLowerCase(),
        amount: Number(newAmount),
        frequency: frequencyMap[newFrequency] ?? newFrequency.toLowerCase(),
        next_expected_date: newNextDate,
        is_active: newStatus === "Active",
      };

      if (!request.name || !request.next_expected_date || !Number.isFinite(request.amount) || request.amount <= 0) {
        setFormError("Enter a provider name, a positive amount, and a next payment date.");
        return;
      }

      if (editingItem?.backendId) {
        await commitmentApi.updateRecurringPayment(editingItem.backendId, request, token);
      } else {
        await commitmentApi.createRecurringPayment(request, token);
      }

      setAddModalOpen(false);
      setRefreshNonce((value) => value + 1);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        onUnauthorized();
      } else {
        setFormError(err instanceof Error ? err.message : "Unable to save recurring payment.");
      }
    } finally {
      setSavingPayment(false);
    }
  };

  const handleDeactivate = async (item: RecurringPaymentItem) => {
    const token = getStoredAccessToken();
    if (!token || !item.backendId) return;
    try {
      await commitmentApi.deactivateRecurringPayment(item.backendId, token);
      setActionMenuOpenId(null);
      setRefreshNonce((v) => v + 1);
    } catch (err) {
      console.error("Failed to deactivate payment", err);
    }
  };

  const openSimulateModal = async (item: RecurringPaymentItem) => {
    setSimulateModalItem(item);
    setActionMenuOpenId(null);
    setSimulationResult(null);
    setSimulating(true);

    const token = getStoredAccessToken();
    if (!token || !item.backendId) {
      setSimulating(false);
      return;
    }

    try {
      const res = await commitmentApi.simulateCancellation(item.backendId, token);
      setSimulationResult(res);
    } catch (err) {
      console.error("Simulation error", err);
    } finally {
      setSimulating(false);
    }
  };

  // Under-utilized subscription count from Model 3
  const underutilizedSubs = useMemo(() => {
    return recurringPayments.filter(
      (p) =>
        p.is_active &&
        p.category.toLowerCase() === "subscription" &&
        ["UNDER_UTILIZED", "MODERATE"].includes(p.transactional_engagement_status || "")
    );
  }, [recurringPayments]);

  if (loading) {
    return (
      <div className="min-h-[70vh] flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="w-8 h-8 text-indigo-500 animate-spin" />
          <p className="text-sm font-medium text-slate-400">Loading recurring commitments…</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-[70vh] flex items-center justify-center px-4">
        <div className="max-w-md w-full p-8 rounded-3xl bg-[#0d1424]/90 border border-white/10 shadow-2xl text-center">
          <div className="w-12 h-12 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-400 mx-auto flex items-center justify-center mb-4">
            <AlertTriangle size={24} />
          </div>
          <h2 className="text-lg font-bold text-white mb-2">Recurring Payments Unavailable</h2>
          <p className="text-sm text-slate-400 mb-6">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="px-5 py-2.5 rounded-full bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs shadow-lg shadow-indigo-600/30 transition-all"
          >
            Retry Loading
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full max-w-[1520px] mx-auto px-4 sm:px-6 lg:px-8 xl:px-10 py-6 sm:py-8 space-y-6 pb-20">
      {/* ─────────────────────────────────────────────────────────────
          A. PAGE HEADER
      ───────────────────────────────────────────────────────────── */}
      <motion.div
        initial={reduceMotion ? undefined : { opacity: 0, y: -6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-5"
      >
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
            Recurring{" "}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-purple-400 via-violet-400 to-indigo-400">
              Payments
            </span>
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1 max-w-2xl">
            Track and manage all your subscriptions, EMIs, bills and other recurring commitments in one place.
          </p>
        </div>

        {/* Right side controls */}
        <div className="flex items-center gap-4 sm:gap-6 shrink-0 flex-wrap">
          {/* Decorative curved wave & Slogan */}
          <div className="hidden xl:flex items-center gap-4">
            <div className="relative w-32 h-8" aria-hidden="true">
              <svg viewBox="0 0 144 36" fill="none" className="w-full h-full text-indigo-400/70 drop-shadow-[0_0_8px_rgba(129,140,248,0.25)]">
                <path d="M2 24 C 35 30, 55 6, 85 10 S 115 26, 142 8" stroke="url(#recWaveGlow)" strokeWidth="2.5" strokeLinecap="round" />
                <defs>
                  <linearGradient id="recWaveGlow" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="#818CF8" />
                    <stop offset="100%" stopColor="#C084FC" />
                  </linearGradient>
                </defs>
                <circle cx="85" cy="10" r="3" fill="#C084FC" className="animate-pulse" />
              </svg>
            </div>
            <div className="text-right border-r border-white/10 pr-4">
              <p className="font-serif italic text-[10px] leading-tight text-slate-400/80">
                Smarter<br />Money<br />Brighter<br />Tomorrow
              </p>
            </div>
          </div>

          {/* Analysis period pill */}
          <div className="px-3.5 py-2 rounded-xl bg-[#0d1424]/90 border border-white/[0.08] text-xs text-slate-300 flex items-center gap-2 shadow-sm">
            <Calendar size={13} className="text-indigo-400" />
            <span className="font-medium">Jan 2025 – Dec 2025</span>
            <ChevronDown size={12} className="text-slate-500 ml-1" />
          </div>

          {/* Add Recurring Payment Button */}
          <button
            onClick={openAddModal}
            className="flex items-center gap-1.5 px-4 sm:px-5 py-2 rounded-xl bg-gradient-to-r from-purple-600 via-indigo-600 to-blue-600 hover:from-purple-500 hover:via-indigo-500 hover:to-blue-500 text-white text-xs font-semibold shadow-lg shadow-indigo-600/25 transition-all hover:scale-[1.02] active:scale-[0.98]"
          >
            <Plus size={15} />
            <span>Add Recurring Payment</span>
          </button>
        </div>
      </motion.div>

      {/* ─────────────────────────────────────────────────────────────
          B. EXACTLY THREE SUMMARY CARDS
      ───────────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 sm:gap-5">
        {/* CARD 1: Total Monthly Commitments */}
        <motion.div
          initial={reduceMotion ? undefined : { opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.05 }}
          className="rounded-2xl border border-white/[0.08] bg-[#0d1424]/80 backdrop-blur-xl p-5 shadow-lg relative overflow-hidden group hover:border-white/15 transition-all"
        >
          <div className="flex items-start justify-between">
            <div className="w-10 h-10 rounded-xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center text-rose-400 shrink-0">
              <Link2 size={18} />
            </div>
            <div className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs font-semibold">
              <TrendingDown size={12} />
              <span>12%</span>
            </div>
          </div>

          <div className="mt-4">
            <p className="text-xs text-slate-400 font-medium">Total Monthly Commitments</p>
            <div className="flex items-baseline justify-between gap-2 mt-1">
              <p className="font-mono text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
                <AnimatedCounter value={summary.totalMonthly} prefix="₹" />
              </p>
              {/* Subtle pink sparkline wave */}
              <div className="w-24 h-6 text-rose-400/50 shrink-0">
                <svg viewBox="0 0 100 24" fill="none" className="w-full h-full">
                  <path d="M0 16 Q 25 6, 50 14 T 100 8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                </svg>
              </div>
            </div>
            <p className="text-[11px] text-slate-400/90 mt-1.5">
              Across {summary.activeCount} active payments
            </p>
          </div>
        </motion.div>

        {/* CARD 2: Active Commitments */}
        <motion.div
          initial={reduceMotion ? undefined : { opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.1 }}
          className="rounded-2xl border border-white/[0.08] bg-[#0d1424]/80 backdrop-blur-xl p-5 shadow-lg relative overflow-hidden group hover:border-white/15 transition-all"
        >
          <div className="flex items-start justify-between">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 shrink-0">
              <Layers size={18} />
            </div>
            <div className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-semibold">
              <TrendingUp size={12} />
              <span>2</span>
            </div>
          </div>

          <div className="mt-4">
            <p className="text-xs text-slate-400 font-medium">Active Commitments</p>
            <div className="flex items-baseline justify-between gap-2 mt-1">
              <p className="font-mono text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
                <AnimatedCounter value={summary.activeCount} />
              </p>
              {/* Subtle emerald sparkline wave */}
              <div className="w-24 h-6 text-emerald-400/50 shrink-0">
                <svg viewBox="0 0 100 24" fill="none" className="w-full h-full">
                  <path d="M0 18 Q 30 14, 60 8 T 100 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                </svg>
              </div>
            </div>
            <p className="text-[11px] text-slate-400/90 mt-1.5">Across all categories</p>
          </div>
        </motion.div>

        {/* CARD 3: Possible Trials */}
        <motion.div
          initial={reduceMotion ? undefined : { opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.15 }}
          className="rounded-2xl border border-white/[0.08] bg-[#0d1424]/80 backdrop-blur-xl p-5 shadow-lg relative overflow-hidden group hover:border-white/15 transition-all"
        >
          <div className="flex items-start justify-between">
            <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 shrink-0">
              <Hourglass size={18} />
            </div>
            <div className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs font-semibold">
              <Bell size={11} />
              <span>{summary.possibleTrialsCount}</span>
            </div>
          </div>

          <div className="mt-4">
            <p className="text-xs text-slate-400 font-medium">Possible Trials</p>
            <div className="flex items-baseline justify-between gap-2 mt-1">
              <p className="font-mono text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
                <AnimatedCounter value={summary.possibleTrialsCount} />
              </p>
              {/* Subtle amber sparkline wave */}
              <div className="w-24 h-6 text-amber-400/50 shrink-0">
                <svg viewBox="0 0 100 24" fill="none" className="w-full h-full">
                  <path d="M0 16 Q 25 20, 55 10 T 100 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                </svg>
              </div>
            </div>
            <p className="text-[11px] text-amber-400/80 mt-1.5">May convert to paid</p>
          </div>
        </motion.div>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          C. CATEGORY FILTER TABS
      ───────────────────────────────────────────────────────────── */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-none">
        {[
          { label: "All", count: categoryCounts.all },
          { label: "Subscriptions", count: categoryCounts.subs },
          { label: "EMIs", count: categoryCounts.emis },
          { label: "BNPL", count: categoryCounts.bnpl },
          { label: "Bills", count: categoryCounts.bills },
          { label: "Trials", count: categoryCounts.trials },
          { label: "Inactive", count: categoryCounts.inactive },
        ].map((tab) => {
          const active = selectedFilterTab === tab.label;
          return (
            <button
              key={tab.label}
              onClick={() => setSelectedFilterTab(tab.label)}
              className={`px-4 py-2 rounded-full text-xs font-semibold whitespace-nowrap transition-all flex items-center gap-2 ${
                active
                  ? "bg-gradient-to-r from-purple-600 to-indigo-600 text-white shadow-md shadow-purple-900/40"
                  : "bg-[#0d1424]/90 border border-white/[0.08] text-slate-400 hover:text-white hover:bg-white/[0.04]"
              }`}
            >
              <span>{tab.label}</span>
              <span
                className={`text-[10px] font-mono px-1.5 py-0.2 rounded-full ${
                  active ? "bg-white/20 text-white" : "bg-white/[0.06] text-slate-400"
                }`}
              >
                {tab.count}
              </span>
            </button>
          );
        })}
      </div>

      {/* ─────────────────────────────────────────────────────────────
          D. SEARCH + SORT CONTROLS
      ───────────────────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3.5">
        {/* Search recurring payments */}
        <div className="relative flex-1 max-w-md">
          <Search size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search recurring payments... (provider, category, amount)"
            className="w-full pl-9 pr-8 py-2.5 rounded-xl bg-[#0d1424]/90 border border-white/[0.08] text-xs text-white placeholder-slate-500 focus:outline-none focus:border-purple-500/60 transition-all shadow-sm"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white"
            >
              <X size={13} />
            </button>
          )}
        </div>

        {/* Right side Sort & View Controls */}
        <div className="flex items-center gap-3">
          {/* Sort Dropdown */}
          <div ref={sortDropdownRef} className="relative">
            <button
              type="button"
              onClick={() => setShowSortDropdown((v) => !v)}
              className="flex items-center gap-2 px-3.5 py-2.5 rounded-xl bg-[#0d1424]/90 border border-white/[0.08] text-xs text-slate-300 hover:border-white/20 transition-colors shadow-sm"
            >
              <ArrowUpDown size={13} className="text-slate-400" />
              <span>Sort by:</span>
              <span className="font-semibold text-white">
                {sortOrder === "amount-desc"
                  ? "Amount (High to Low)"
                  : sortOrder === "amount-asc"
                  ? "Amount (Low to High)"
                  : sortOrder === "date"
                  ? "Next Due Date"
                  : "Provider Name"}
              </span>
              <ChevronDown size={12} className="text-slate-500 ml-0.5" />
            </button>

            {showSortDropdown && (
              <div className="absolute right-0 top-full mt-2 w-56 rounded-2xl bg-[#0d1424] border border-white/15 shadow-2xl p-1.5 z-50 text-xs space-y-0.5 backdrop-blur-xl">
                {[
                  { id: "amount-desc", label: "Amount (High to Low)" },
                  { id: "amount-asc", label: "Amount (Low to High)" },
                  { id: "name", label: "Provider Name (A to Z)" },
                  { id: "date", label: "Next Due Date" },
                ].map((s) => (
                  <button
                    key={s.id}
                    onClick={() => {
                      setSortOrder(s.id as typeof sortOrder);
                      setShowSortDropdown(false);
                    }}
                    className={`w-full text-left px-3 py-2 rounded-xl text-xs transition-colors flex items-center justify-between ${
                      sortOrder === s.id
                        ? "bg-purple-600/20 text-purple-300 font-semibold"
                        : "text-slate-300 hover:bg-white/[0.06]"
                    }`}
                  >
                    <span>{s.label}</span>
                    {sortOrder === s.id && <Check size={13} className="text-purple-400 shrink-0" />}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* View mode toggle (Table / Cards) */}
          <div className="flex items-center rounded-xl border border-white/[0.08] bg-[#0d1424]/90 p-0.5 shadow-sm">
            <button
              onClick={() => setViewMode("list")}
              className={`p-2 rounded-lg transition-colors ${
                viewMode === "list" ? "bg-purple-600/30 text-white" : "text-slate-500 hover:text-slate-300"
              }`}
              title="Table view"
            >
              <LayoutList size={14} />
            </button>
            <button
              onClick={() => setViewMode("cards")}
              className={`p-2 rounded-lg transition-colors ${
                viewMode === "cards" ? "bg-purple-600/30 text-white" : "text-slate-500 hover:text-slate-300"
              }`}
              title="Cards view"
            >
              <LayoutGrid size={14} />
            </button>
          </div>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          E & F & G. MAIN 2-COLUMN LAYOUT: TABLE (LEFT) + RIGHT PANELS
      ───────────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* LEFT COLUMN: MAIN RECURRING PAYMENTS TABLE (8 COLS) */}
        <div className="lg:col-span-8 space-y-4">
          <div className="rounded-2xl border border-white/[0.08] bg-[#0d1424]/80 backdrop-blur-xl shadow-xl overflow-hidden">
            {viewMode === "list" ? (
              <div className="overflow-x-auto scrollbar-thin">
                <table className="w-full text-left border-collapse min-w-[700px]">
                  <thead>
                    <tr className="border-b border-white/[0.06] text-[11px] font-semibold text-slate-400 uppercase tracking-wider bg-white/[0.02]">
                      <th className="py-3.5 pl-4 pr-2 w-10">
                        <input
                          type="checkbox"
                          checked={allSelected}
                          onChange={toggleSelectAll}
                          className="rounded border-slate-700 bg-slate-900 text-purple-600 w-3.5 h-3.5 cursor-pointer"
                        />
                      </th>
                      <th className="py-3.5 px-3">MERCHANT / DESCRIPTION</th>
                      <th className="py-3.5 px-3">CATEGORY</th>
                      <th className="py-3.5 px-3">AMOUNT</th>
                      <th className="py-3.5 px-3">FREQUENCY</th>
                      <th className="py-3.5 px-3">STATUS</th>
                      <th className="py-3.5 pr-4 pl-2 text-right">ACTIONS</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/[0.04] text-xs">
                    {sortedPayments.map((item) => {
                      const isSelected = selectedRowIds.has(item.id);
                      return (
                        <tr
                          key={item.id}
                          className={`hover:bg-white/[0.03] transition-colors group cursor-pointer ${
                            isSelected ? "bg-purple-950/20" : ""
                          }`}
                          onClick={() => setSelectedItem(item)}
                        >
                          {/* Checkbox */}
                          <td className="py-3.5 pl-4 pr-2 w-10" onClick={(e) => e.stopPropagation()}>
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={() => toggleSelectRow(item.id)}
                              className="rounded border-slate-700 bg-slate-900 text-purple-600 w-3.5 h-3.5 cursor-pointer"
                            />
                          </td>

                          {/* Merchant / Description */}
                          <td className="py-3.5 px-3">
                            <div className="flex items-center gap-3">
                              <MerchantLogo name={item.provider} category={item.category} size="md" />
                              <div className="min-w-0">
                                <p className="text-sm font-semibold text-white group-hover:text-purple-300 transition-colors truncate">
                                  {item.provider}
                                </p>
                                <p className="text-[11px] text-slate-400 truncate mt-0.5">{item.subtitle}</p>
                              </div>
                            </div>
                          </td>

                          {/* Category */}
                          <td className="py-3.5 px-3 whitespace-nowrap">
                            <TableCategoryBadge category={item.category} />
                          </td>

                          {/* Amount */}
                          <td className="py-3.5 px-3 whitespace-nowrap">
                            <span className="font-mono text-sm font-bold text-white">
                              {money(item.monthlyAmount)}
                            </span>
                          </td>

                          {/* Frequency */}
                          <td className="py-3.5 px-3 whitespace-nowrap text-slate-300 font-medium">
                            {item.frequency}
                          </td>

                          {/* Status */}
                          <td className="py-3.5 px-3 whitespace-nowrap">
                            {item.status === "Active" ? (
                              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                                Active
                              </span>
                            ) : item.status === "Possible Trial" ? (
                              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-amber-500/15 text-amber-400 border border-amber-500/30">
                                Possible Trial
                              </span>
                            ) : item.status === "Inactive" ? (
                              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-slate-700/40 text-slate-400 border border-slate-600/30">
                                Inactive
                              </span>
                            ) : (
                              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-blue-500/15 text-blue-400 border border-blue-500/30">
                                Needs Review
                              </span>
                            )}
                          </td>

                          {/* Actions */}
                          <td
                            className="py-3.5 pr-4 pl-2 text-right relative"
                            onClick={(e) => e.stopPropagation()}
                            data-action-menu
                          >
                            <button
                              onClick={() => setActionMenuOpenId(actionMenuOpenId === item.id ? null : item.id)}
                              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/[0.08] transition-colors"
                              title="Actions"
                            >
                              <MoreVertical size={15} />
                            </button>

                            {/* Action popup menu */}
                            {actionMenuOpenId === item.id && (
                              <div className="absolute right-4 top-10 w-44 rounded-xl bg-[#0d1424] border border-white/15 shadow-2xl p-1 z-50 text-left space-y-0.5 backdrop-blur-xl">
                                <button
                                  onClick={() => {
                                    setSelectedItem(item);
                                    setActionMenuOpenId(null);
                                  }}
                                  className="w-full text-left px-3 py-1.5 rounded-lg text-xs text-slate-300 hover:bg-white/[0.06] flex items-center gap-2"
                                >
                                  <FileText size={12} className="text-slate-400" />
                                  <span>View Details</span>
                                </button>

                                {item.source === "Detected" && item.status === "Active" && (
                                  <button
                                    onClick={() => openSimulateModal(item)}
                                    className="w-full text-left px-3 py-1.5 rounded-lg text-xs text-purple-300 hover:bg-purple-600/20 flex items-center gap-2"
                                  >
                                    <Zap size={12} className="text-purple-400" />
                                    <span>Simulate Cancellation</span>
                                  </button>
                                )}

                                {item.source === "User Added" && (
                                  <button
                                    onClick={() => openEditModal(item)}
                                    className="w-full text-left px-3 py-1.5 rounded-lg text-xs text-slate-300 hover:bg-white/[0.06] flex items-center gap-2"
                                  >
                                    <Edit2 size={12} className="text-slate-400" />
                                    <span>Edit Payment</span>
                                  </button>
                                )}

                                <button
                                  onClick={() => handleDeactivate(item)}
                                  className="w-full text-left px-3 py-1.5 rounded-lg text-xs text-rose-400 hover:bg-rose-500/10 flex items-center gap-2"
                                >
                                  <Trash2 size={12} className="text-rose-400" />
                                  <span>{item.source === "User Added" ? "Delete" : "Deactivate"}</span>
                                </button>
                              </div>
                            )}
                          </td>
                        </tr>
                      );
                    })}

                    {sortedPayments.length === 0 && (
                      <tr>
                        <td colSpan={7} className="py-12 text-center">
                          <div className="flex flex-col items-center justify-center gap-2 text-slate-400">
                            <Info size={24} className="text-slate-500" />
                            <p className="text-sm font-medium text-white">No recurring commitments found</p>
                            <p className="text-xs text-slate-500 max-w-sm">
                              {searchQuery
                                ? "No commitments match your search query."
                                : "No recurring commitments detected in this category."}
                            </p>
                            <button
                              onClick={openAddModal}
                              className="mt-3 px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold shadow-md transition-all"
                            >
                              + Add Recurring Payment
                            </button>
                          </div>
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            ) : (
              /* Card Grid View */
              <div className="p-4 grid grid-cols-1 sm:grid-cols-2 gap-4">
                {sortedPayments.map((item) => (
                  <div
                    key={item.id}
                    onClick={() => setSelectedItem(item)}
                    className="rounded-xl border border-white/[0.08] bg-white/[0.02] hover:bg-white/[0.05] p-4 transition-all cursor-pointer group"
                  >
                    <div className="flex items-center justify-between mb-3">
                      <MerchantLogo name={item.provider} category={item.category} size="md" />
                      <span className="font-mono text-sm font-bold text-white">{money(item.monthlyAmount)}</span>
                    </div>
                    <p className="font-semibold text-sm text-white group-hover:text-purple-300 transition-colors truncate">
                      {item.provider}
                    </p>
                    <p className="text-xs text-slate-400 mt-0.5">{item.subtitle}</p>
                    <div className="mt-3 pt-3 border-t border-white/[0.06] flex items-center justify-between text-xs">
                      <TableCategoryBadge category={item.category} />
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                          item.status === "Active"
                            ? "bg-emerald-500/15 text-emerald-400"
                            : "bg-slate-700/40 text-slate-400"
                        }`}
                      >
                        {item.status}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* RIGHT COLUMN: COMMITMENT MIX & INSIGHTS (4 COLS) */}
        <div className="lg:col-span-4 space-y-5">
          {/* PANEL 1: COMMITMENT MIX */}
          <div className="rounded-2xl border border-white/[0.08] bg-[#0d1424]/80 backdrop-blur-xl p-5 shadow-xl space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-white tracking-tight">Commitment Mix</h3>
                <p className="text-[11px] text-slate-400 mt-0.5">Monthly amount distribution</p>
              </div>
              <div className="px-2.5 py-1 rounded-lg bg-slate-800/80 border border-white/[0.06] text-xs text-slate-300 flex items-center gap-1">
                <span>Monthly</span>
                <ChevronDown size={11} className="text-slate-500" />
              </div>
            </div>

            {/* Donut Chart and Legend */}
            <div className="flex flex-col sm:flex-row lg:flex-col xl:flex-row items-center gap-5 pt-2">
              <div className="shrink-0 flex justify-center">
                <MixDonutChart total={summary.totalMonthly} segments={mixSegments} />
              </div>

              {/* Legend with exact amounts & percentages */}
              <div className="w-full space-y-2 text-xs">
                {mixSegments.map((seg) => (
                  <div key={seg.key} className="flex items-center justify-between py-1 border-b border-white/[0.04] last:border-none">
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: seg.color }} />
                      <span className="text-slate-300 font-medium">{seg.label}</span>
                    </div>
                    <div className="flex items-center gap-2.5">
                      <span className="font-mono text-white font-bold">{money(seg.amount)}</span>
                      <span className="text-[11px] text-slate-400 font-mono w-7 text-right">{seg.pct}%</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* PANEL 2: INSIGHTS & SUGGESTIONS */}
          <div className="rounded-2xl border border-white/[0.08] bg-[#0d1424]/80 backdrop-blur-xl p-5 shadow-xl space-y-3.5">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-white tracking-tight">Insights & Suggestions</h3>
              <button
                onClick={() => onAskAssistant("Show recurring commitments recommendations and savings")}
                className="text-xs text-purple-400 hover:text-purple-300 font-medium flex items-center gap-1 transition-colors"
              >
                <span>View all</span>
                <ArrowRight size={11} />
              </button>
            </div>

            <div className="space-y-2.5 pt-1">
              {/* Insight 1: Underutilised Subscriptions from Model 3 */}
              <div
                onClick={() => onAskAssistant("Which subscriptions look underutilized and can be cancelled?")}
                className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06] hover:bg-white/[0.06] transition-all cursor-pointer group flex items-start gap-3"
              >
                <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center shrink-0 mt-0.5">
                  <Calendar size={15} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between">
                    <p className="text-xs font-semibold text-white group-hover:text-purple-300 transition-colors">
                      {underutilizedSubs.length > 0
                        ? `${underutilizedSubs.length} subscriptions look underutilised`
                        : "Subscriptions show active engagement"}
                    </p>
                    <ChevronRight size={12} className="text-slate-500 group-hover:text-white transition-colors" />
                  </div>
                  <p className="text-[11px] text-slate-400 mt-0.5 leading-snug">
                    {underutilizedSubs.length > 0
                      ? "Consider reviewing to save money."
                      : "No immediate cancellations recommended."}
                  </p>
                </div>
              </div>

              {/* Insight 2: Free Trials Conversion Alert */}
              <div
                onClick={() => onAskAssistant("Show all active free trial conversions and cancellation deadlines")}
                className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06] hover:bg-white/[0.06] transition-all cursor-pointer group flex items-start gap-3"
              >
                <div className="w-8 h-8 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 flex items-center justify-center shrink-0 mt-0.5">
                  <Hourglass size={15} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between">
                    <p className="text-xs font-semibold text-white group-hover:text-purple-300 transition-colors">
                      {summary.possibleTrialsCount > 0
                        ? `${summary.possibleTrialsCount} free trials may convert to paid`
                        : "No active free trials converting soon"}
                    </p>
                    <ChevronRight size={12} className="text-slate-500 group-hover:text-white transition-colors" />
                  </div>
                  <p className="text-[11px] text-slate-400 mt-0.5 leading-snug">
                    {summary.possibleTrialsCount > 0
                      ? "Cancel if not needed to avoid charges."
                      : "No unexpected trial charges expected."}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          MODAL 1: ADD / EDIT RECURRING PAYMENT MODAL
      ───────────────────────────────────────────────────────────── */}
      <AnimatePresence>
        {addModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="w-full max-w-lg rounded-2xl bg-[#0d1424] border border-white/15 p-4 sm:p-6 shadow-2xl relative space-y-4 max-h-[90vh] overflow-y-auto"
            >
              <div className="flex items-center justify-between pb-3 border-b border-white/[0.08]">
                <h2 className="text-base font-bold text-white">
                  {editingItem ? "Edit Recurring Payment" : "Add Recurring Payment"}
                </h2>
                <button
                  onClick={() => setAddModalOpen(false)}
                  className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-white/[0.06]"
                >
                  <X size={16} />
                </button>
              </div>

              {formError && (
                <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-xs text-rose-300">
                  {formError}
                </div>
              )}

              <form onSubmit={handleAddPaymentSubmit} className="space-y-4 text-xs">
                <div>
                  <label className="block text-slate-300 font-medium mb-1">Provider / Merchant Name</label>
                  <input
                    type="text"
                    required
                    value={newProvider}
                    onChange={(e) => setNewProvider(e.target.value)}
                    placeholder="e.g. Netflix, HDFC Loan, Cult.fit"
                    className="w-full px-3.5 py-2.5 rounded-xl bg-slate-900/90 border border-white/10 text-white placeholder-slate-500 focus:outline-none focus:border-purple-500"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-slate-300 font-medium mb-1">Category</label>
                    <select
                      value={newCategory}
                      onChange={(e) => setNewCategory(e.target.value)}
                      className="w-full px-3.5 py-2.5 rounded-xl bg-slate-900 border border-white/10 text-white focus:outline-none focus:border-purple-500"
                    >
                      <option value="Subscription">Subscription</option>
                      <option value="EMI / Loans">EMI / Loans</option>
                      <option value="BNPL">BNPL</option>
                      <option value="Rent">Rent</option>
                      <option value="Insurance">Insurance</option>
                      <option value="Electricity">Electricity</option>
                      <option value="Internet">Internet</option>
                      <option value="Mobile">Mobile</option>
                      <option value="Memberships">Memberships</option>
                      <option value="Education fees">Education fees</option>
                      <option value="SIP / Investment">SIP / Investment</option>
                      <option value="Other">Other</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-slate-300 font-medium mb-1">Frequency</label>
                    <select
                      value={newFrequency}
                      onChange={(e) => setNewFrequency(e.target.value)}
                      className="w-full px-3.5 py-2.5 rounded-xl bg-slate-900 border border-white/10 text-white focus:outline-none focus:border-purple-500"
                    >
                      <option value="Monthly">Monthly</option>
                      <option value="Weekly">Weekly</option>
                      <option value="Biweekly">Bi-weekly</option>
                      <option value="Quarterly">Quarterly</option>
                      <option value="Annual">Annual</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-slate-300 font-medium mb-1">Amount (₹)</label>
                    <input
                      type="number"
                      required
                      min="1"
                      step="any"
                      value={newAmount}
                      onChange={(e) => setNewAmount(e.target.value)}
                      placeholder="e.g. 649"
                      className="w-full px-3.5 py-2.5 rounded-xl bg-slate-900/90 border border-white/10 text-white placeholder-slate-500 focus:outline-none focus:border-purple-500 font-mono"
                    />
                  </div>

                  <div>
                    <label className="block text-slate-300 font-medium mb-1">Next Expected Date</label>
                    <input
                      type="date"
                      required
                      value={newNextDate}
                      onChange={(e) => setNewNextDate(e.target.value)}
                      className="w-full px-3.5 py-2.5 rounded-xl bg-slate-900 border border-white/10 text-white focus:outline-none focus:border-purple-500"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-slate-300 font-medium mb-1">Status</label>
                  <div className="flex items-center gap-3">
                    <button
                      type="button"
                      onClick={() => setNewStatus("Active")}
                      className={`flex-1 py-2 rounded-xl font-semibold transition-all ${
                        newStatus === "Active"
                          ? "bg-emerald-600/30 text-emerald-300 border border-emerald-500/40"
                          : "bg-slate-900 border border-white/10 text-slate-400"
                      }`}
                    >
                      Active
                    </button>
                    <button
                      type="button"
                      onClick={() => setNewStatus("Inactive")}
                      className={`flex-1 py-2 rounded-xl font-semibold transition-all ${
                        newStatus === "Inactive"
                          ? "bg-slate-700/50 text-slate-300 border border-slate-600/40"
                          : "bg-slate-900 border border-white/10 text-slate-400"
                      }`}
                    >
                      Inactive
                    </button>
                  </div>
                </div>

                <div className="flex items-center justify-end gap-3 pt-3 border-t border-white/[0.08]">
                  <button
                    type="button"
                    onClick={() => setAddModalOpen(false)}
                    className="px-4 py-2 rounded-xl text-slate-300 hover:text-white hover:bg-white/[0.05] transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={savingPayment}
                    className="px-5 py-2 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-semibold shadow-lg shadow-indigo-600/30 flex items-center gap-1.5 transition-all"
                  >
                    {savingPayment && <Loader2 size={13} className="animate-spin" />}
                    <span>{editingItem ? "Update Payment" : "Add Payment"}</span>
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* ─────────────────────────────────────────────────────────────
          MODAL 2: DETAIL MODAL
      ───────────────────────────────────────────────────────────── */}
      <AnimatePresence>
        {selectedItem && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="w-full max-w-md rounded-2xl bg-[#0d1424] border border-white/15 p-4 sm:p-6 shadow-2xl relative space-y-4 max-h-[90vh] overflow-y-auto"
            >
              <div className="flex items-center justify-between pb-3 border-b border-white/[0.08]">
                <div className="flex items-center gap-3">
                  <MerchantLogo name={selectedItem.provider} category={selectedItem.category} size="md" />
                  <div>
                    <h2 className="text-base font-bold text-white">{selectedItem.provider}</h2>
                    <p className="text-xs text-slate-400">{selectedItem.subtitle}</p>
                  </div>
                </div>
                <button
                  onClick={() => setSelectedItem(null)}
                  className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-white/[0.06]"
                >
                  <X size={16} />
                </button>
              </div>

              <div className="space-y-3 text-xs">
                <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.06] space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Monthly Equivalent</span>
                    <span className="font-mono text-base font-bold text-white">{money(selectedItem.monthlyAmount)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Category</span>
                    <TableCategoryBadge category={selectedItem.category} />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Frequency</span>
                    <span className="text-white font-medium">{selectedItem.frequency}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Status</span>
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${selectedItem.status === "Active" ? "bg-emerald-500/15 text-emerald-400" : "bg-slate-700/40 text-slate-400"}`}>
                      {selectedItem.status}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Source</span>
                    <span className="text-indigo-300 font-medium">{selectedItem.source}</span>
                  </div>
                </div>

                {selectedItem.notes && (
                  <p className="text-[11px] text-slate-400 px-1">{selectedItem.notes}</p>
                )}
              </div>

              <div className="flex items-center justify-between pt-3 border-t border-white/[0.08]">
                {selectedItem.source === "Detected" && selectedItem.status === "Active" && (
                  <button
                    onClick={() => {
                      const item = selectedItem;
                      setSelectedItem(null);
                      openSimulateModal(item);
                    }}
                    className="px-4 py-2 rounded-xl bg-purple-600/20 text-purple-300 hover:bg-purple-600/30 text-xs font-semibold flex items-center gap-1.5 transition-colors"
                  >
                    <Zap size={13} />
                    <span>Simulate Cancellation</span>
                  </button>
                )}
                <button
                  onClick={() => setSelectedItem(null)}
                  className="ml-auto px-4 py-2 rounded-xl bg-slate-800 text-white hover:bg-slate-700 text-xs font-semibold transition-colors"
                >
                  Close
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* ─────────────────────────────────────────────────────────────
          MODAL 3: SIMULATE CANCELLATION MODAL
      ───────────────────────────────────────────────────────────── */}
      <AnimatePresence>
        {simulateModalItem && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="w-full max-w-lg rounded-2xl bg-[#0d1424] border border-white/15 p-4 sm:p-6 shadow-2xl relative space-y-4 max-h-[90vh] overflow-y-auto"
            >
              <div className="flex items-center justify-between pb-3 border-b border-white/[0.08]">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-lg bg-purple-500/10 border border-purple-500/20 text-purple-400 flex items-center justify-center">
                    <Zap size={16} />
                  </div>
                  <div>
                    <h2 className="text-base font-bold text-white">Cancellation What-If Simulation</h2>
                    <p className="text-xs text-slate-400">{simulateModalItem.provider}</p>
                  </div>
                </div>
                <button
                  onClick={() => setSimulateModalItem(null)}
                  className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-white/[0.06]"
                >
                  <X size={16} />
                </button>
              </div>

              {simulating ? (
                <div className="py-12 flex flex-col items-center justify-center gap-3">
                  <Loader2 className="w-6 h-6 text-purple-500 animate-spin" />
                  <p className="text-xs text-slate-400">Computing financial simulation projection…</p>
                </div>
              ) : simulationResult ? (
                <div className="space-y-4 text-xs">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.06]">
                      <p className="text-[11px] text-slate-400">Current Monthly Commitments</p>
                      <p className="font-mono text-base font-bold text-white mt-1">
                        {money(simulationResult.current_monthly_commitments)}
                      </p>
                    </div>

                    <div className="p-3.5 rounded-xl bg-purple-500/10 border border-purple-500/20">
                      <p className="text-[11px] text-purple-300 font-medium">New Monthly Commitments</p>
                      <p className="font-mono text-base font-bold text-emerald-400 mt-1">
                        {money(simulationResult.projected_monthly_commitments)}
                      </p>
                    </div>
                  </div>

                  <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.06] space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-slate-400">Monthly Cash Released</span>
                      <span className="font-mono text-emerald-400 font-bold">
                        +{money(simulationResult.released_monthly_amount)} / mo
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-slate-400">Annual Cashflow Savings</span>
                      <span className="font-mono text-emerald-400 font-bold">
                        +{money(simulationResult.annual_savings)} / yr
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-slate-400">New Exposure Score</span>
                      <span className="font-mono text-white font-semibold">
                        {simulationResult.projected_exposure_score.toFixed(2)}%
                      </span>
                    </div>
                  </div>

                  <p className="text-[11px] text-slate-400/80 leading-relaxed bg-white/[0.02] p-2.5 rounded-lg border border-white/[0.04]">
                    ℹ️ This what-if simulation projects your cash flow change without modifying your banking subscriptions or stored transaction history.
                  </p>
                </div>
              ) : (
                <div className="py-6 text-center text-slate-400 text-xs">
                  Simulation unavailable for this recurring commitment.
                </div>
              )}

              <div className="flex justify-end pt-3 border-t border-white/[0.08]">
                <button
                  onClick={() => setSimulateModalItem(null)}
                  className="px-4 py-2 rounded-xl bg-slate-800 text-white hover:bg-slate-700 text-xs font-semibold transition-colors"
                >
                  Close Simulation
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
