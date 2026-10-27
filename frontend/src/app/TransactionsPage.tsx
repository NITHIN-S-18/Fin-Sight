import React, { useEffect, useMemo, useRef, useState } from "react";
import { motion, AnimatePresence, useReducedMotion } from "motion/react";
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  Calendar,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Clock,
  Copy,
  CreditCard,
  Filter,
  Landmark,
  Layers,
  LayoutGrid,
  LayoutList,
  Loader2,
  MoreHorizontal,
  Receipt,
  RefreshCw,
  RotateCcw,
  Search,
  ShieldCheck,
  Sparkles,
  Tag,
  Upload,
  Wallet,
  X,
} from "lucide-react";
import {
  ApiError,
  AuthenticatedUser,
  getStoredAccessToken,
  UserTransaction,
  userTransactionApi,
} from "../api/client";
import { MerchantLogo } from "./components/MerchantLogo";
import { CategoryBadge, TypeBadge } from "./components/FinancialBadges";
import { AnimatedCounter } from "./components/AnimatedCounter";

interface TransactionsPageProps {
  user: AuthenticatedUser;
  onUnauthorized: () => void;
  onUpload: () => void;
  onAskAssistant?: (q?: string) => void;
}

interface NormalizedTransaction {
  id: string;
  date: string;
  merchant: string;
  description: string;
  amount: number;
  rawAmount: number;
  isIncome: boolean;
  category: string;
  type: "Income" | "Expense" | "EMI" | "Subscription" | "BNPL" | "Purchase";
  paymentMode: string | null;
  frequency: string | null;
  status: string | null;
  recurring: boolean;
  autopay: boolean;
  riskLabel: string | null;
  commitmentType: string | null;
  isNewSub: boolean;
  notes: string;
  raw: UserTransaction;
}

const PAGE_SIZE = 20;

function formatCurrency(amount: number) {
  const abs = Math.abs(amount).toLocaleString("en-IN");
  return amount < 0 ? `-₹${abs}` : `+₹${abs}`;
}

function formatDateShort(dateStr: string) {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr;
  return d.toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function normalizeRow(row: UserTransaction): NormalizedTransaction {
  const category = (row.category || "Uncategorized").trim();
  const txClass = (row.transaction_class || "").toLowerCase().trim();
  const incFlag = (row.income_flag || "").toLowerCase().trim();
  const catLower = category.toLowerCase();

  const isIncome =
    incFlag === "yes" ||
    catLower === "income" ||
    txClass === "salary" ||
    txClass === "income";

  let type: "Income" | "Expense" | "EMI" | "Subscription" | "BNPL" | "Purchase" = "Purchase";
  if (isIncome) {
    type = "Income";
  } else if (txClass === "subscription") {
    type = "Subscription";
  } else if (txClass === "emi") {
    type = "EMI";
  } else if (txClass === "bnpl") {
    type = "BNPL";
  } else {
    type = "Purchase";
  }

  const merchant = row.merchant_name?.trim() || row.description?.trim() || "Transaction";
  const description =
    row.description?.trim() && row.description.trim() !== merchant
      ? row.description.trim()
      : row.category
      ? `${row.category} payment`
      : "Standard transaction";

  const numAmount = typeof row.amount === "number" ? row.amount : parseFloat(String(row.amount)) || 0;
  const signedAmount = isIncome ? Math.abs(numAmount) : -Math.abs(numAmount);

  const notes = [row.payment_mode, row.frequency, row.transaction_status]
    .filter(Boolean)
    .join(" · ");

  return {
    id: row.transaction_id,
    date: row.transaction_date,
    merchant,
    description,
    amount: signedAmount,
    rawAmount: Math.abs(numAmount),
    isIncome,
    category,
    type,
    paymentMode: row.payment_mode || null,
    frequency: row.frequency || null,
    status: row.transaction_status || "Successful",
    recurring: row.recurring_flag?.toLowerCase() === "yes",
    autopay: row.autopay_flag?.toLowerCase() === "yes",
    riskLabel: row.risk_label || null,
    commitmentType: row.commitment_type || null,
    isNewSub: row.is_new_subscription?.toLowerCase() === "yes",
    notes,
    raw: row,
  };
}

export function TransactionsPage({
  user,
  onUnauthorized,
  onUpload,
  onAskAssistant,
}: TransactionsPageProps) {
  const reduceMotion = useReducedMotion();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rawTransactions, setRawTransactions] = useState<NormalizedTransaction[]>([]);

  // Search & Filter State
  const [searchQuery, setSearchQuery] = useState("");
  const [typeChipFilter, setTypeChipFilter] = useState<"All" | "Income" | "Expense" | "Recurring">("All");
  const [sortKey, setSortKey] = useState<
    "newest" | "oldest" | "highest" | "lowest" | "merchant-az" | "merchant-za"
  >("newest");
  const [viewMode, setViewMode] = useState<"list" | "grid">("list");

  // Left Filter Panel State
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [recurringFilter, setRecurringFilter] = useState<"all" | "recurring" | "non-recurring">("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [minAmount, setMinAmount] = useState<string>("");
  const [maxAmount, setMaxAmount] = useState<string>("");
  const [dateRangePreset, setDateRangePreset] = useState("all");
  const [showDateDropdown, setShowDateDropdown] = useState(false);
  const [showSortDropdown, setShowSortDropdown] = useState(false);
  const [showMoreFilterDropdown, setShowMoreFilterDropdown] = useState(false);

  // Pagination State
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedTxIds, setSelectedTxIds] = useState<Set<string>>(new Set());

  // Detail Drawer State
  const [selectedTx, setSelectedTx] = useState<NormalizedTransaction | null>(null);
  const [copiedId, setCopiedId] = useState(false);

  const sortDropdownRef = useRef<HTMLDivElement>(null);
  const dateDropdownRef = useRef<HTMLDivElement>(null);
  const moreFilterRef = useRef<HTMLDivElement>(null);

  // Close dropdowns on click outside or Escape
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (sortDropdownRef.current && !sortDropdownRef.current.contains(event.target as Node)) {
        setShowSortDropdown(false);
      }
      if (dateDropdownRef.current && !dateDropdownRef.current.contains(event.target as Node)) {
        setShowDateDropdown(false);
      }
      if (moreFilterRef.current && !moreFilterRef.current.contains(event.target as Node)) {
        setShowMoreFilterDropdown(false);
      }
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setShowSortDropdown(false);
        setShowDateDropdown(false);
        setShowMoreFilterDropdown(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  // Fetch transactions from API
  useEffect(() => {
    const token = getStoredAccessToken();
    if (!token || !user.financial_user_id) {
      onUnauthorized();
      return;
    }

    setLoading(true);
    setError(null);

    userTransactionApi
      .list(user.financial_user_id, token)
      .then((rows) => {
        const normalized = rows.map(normalizeRow);
        setRawTransactions(normalized);
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          onUnauthorized();
        } else {
          setError(
            err instanceof ApiError
              ? err.message
              : "Unable to load transactions. Please verify your connection."
          );
        }
      })
      .finally(() => setLoading(false));
  }, [user.financial_user_id, onUnauthorized]);

  // Derived real date range
  const dateRangeLabel = useMemo(() => {
    if (!rawTransactions.length) return "1 Jan 2025 - 31 Dec 2025";
    const timestamps = rawTransactions
      .map((t) => new Date(t.date).getTime())
      .filter((ts) => !isNaN(ts));
    if (!timestamps.length) return "1 Jan 2025 - 31 Dec 2025";
    const minD = new Date(Math.min(...timestamps));
    const maxD = new Date(Math.max(...timestamps));
    return `${formatDateShort(minD.toISOString())} - ${formatDateShort(maxD.toISOString())}`;
  }, [rawTransactions]);

  // Summary Metrics calculated from authentic backend data
  const summary = useMemo(() => {
    let spent = 0;
    let income = 0;
    let expenseCount = 0;
    let incomeCount = 0;

    for (const tx of rawTransactions) {
      if (tx.isIncome) {
        income += tx.rawAmount;
        incomeCount++;
      } else {
        spent += tx.rawAmount;
        expenseCount++;
      }
    }

    const totalCount = rawTransactions.length;
    const avg = totalCount > 0 ? (spent + income) / totalCount : 0;

    return {
      spent: Math.round(spent),
      income: Math.round(income),
      totalCount,
      avg: Math.round(avg),
      expenseCount,
      incomeCount,
    };
  }, [rawTransactions]);

  // Extract unique categories
  const availableCategories = useMemo(() => {
    const cats = new Set<string>();
    for (const tx of rawTransactions) {
      if (tx.category) cats.add(tx.category);
    }
    return Array.from(cats).sort();
  }, [rawTransactions]);

  // Filter Pipeline
  const filteredTransactions = useMemo(() => {
    return rawTransactions.filter((tx) => {
      // Search box
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const matchesMerchant = tx.merchant.toLowerCase().includes(q);
        const matchesDesc = tx.description.toLowerCase().includes(q);
        const matchesCat = tx.category.toLowerCase().includes(q);
        const matchesNotes = tx.notes.toLowerCase().includes(q);
        const matchesAmt = String(tx.rawAmount).includes(q);
        if (!matchesMerchant && !matchesDesc && !matchesCat && !matchesNotes && !matchesAmt) {
          return false;
        }
      }

      // Quick type chips (All, Income, Expense, Recurring)
      if (typeChipFilter === "Income" && !tx.isIncome) return false;
      if (typeChipFilter === "Expense" && tx.isIncome) return false;
      if (typeChipFilter === "Recurring" && !tx.recurring) return false;

      // Left panel recurring filter
      if (recurringFilter === "recurring" && !tx.recurring) return false;
      if (recurringFilter === "non-recurring" && tx.recurring) return false;

      // Status filter
      if (statusFilter !== "all") {
        const st = (tx.status || "").toLowerCase();
        if (statusFilter === "successful" && !st.includes("success")) return false;
        if (statusFilter === "failed" && !st.includes("fail")) return false;
        if (statusFilter === "pending" && !st.includes("pend")) return false;
      }

      // Categories filter
      if (selectedCategories.length > 0) {
        if (!selectedCategories.includes(tx.category)) return false;
      }

      // Amount range filter
      if (minAmount && !isNaN(parseFloat(minAmount))) {
        if (tx.rawAmount < parseFloat(minAmount)) return false;
      }
      if (maxAmount && !isNaN(parseFloat(maxAmount))) {
        if (tx.rawAmount > parseFloat(maxAmount)) return false;
      }

      // Date range presets
      if (dateRangePreset !== "all") {
        const txDate = new Date(tx.date).getTime();
        const now = Date.now();
        if (dateRangePreset === "30d" && now - txDate > 30 * 86400000) return false;
        if (dateRangePreset === "90d" && now - txDate > 90 * 86400000) return false;
        if (dateRangePreset === "180d" && now - txDate > 180 * 86400000) return false;
      }

      return true;
    });
  }, [
    rawTransactions,
    searchQuery,
    typeChipFilter,
    recurringFilter,
    statusFilter,
    selectedCategories,
    minAmount,
    maxAmount,
    dateRangePreset,
  ]);

  // Sort Pipeline
  const sortedTransactions = useMemo(() => {
    const list = [...filteredTransactions];
    list.sort((a, b) => {
      if (sortKey === "newest") {
        return new Date(b.date).getTime() - new Date(a.date).getTime();
      }
      if (sortKey === "oldest") {
        return new Date(a.date).getTime() - new Date(b.date).getTime();
      }
      if (sortKey === "highest") {
        return b.rawAmount - a.rawAmount;
      }
      if (sortKey === "lowest") {
        return a.rawAmount - b.rawAmount;
      }
      if (sortKey === "merchant-az") {
        return a.merchant.localeCompare(b.merchant);
      }
      if (sortKey === "merchant-za") {
        return b.merchant.localeCompare(a.merchant);
      }
      return 0;
    });
    return list;
  }, [filteredTransactions, sortKey]);

  // Pagination calculation
  const totalPages = Math.max(1, Math.ceil(sortedTransactions.length / PAGE_SIZE));
  const paginatedTransactions = useMemo(() => {
    const start = (currentPage - 1) * PAGE_SIZE;
    return sortedTransactions.slice(start, start + PAGE_SIZE);
  }, [sortedTransactions, currentPage]);

  const resetFilters = () => {
    setSearchQuery("");
    setTypeChipFilter("All");
    setSelectedCategories([]);
    setRecurringFilter("all");
    setStatusFilter("all");
    setMinAmount("");
    setMaxAmount("");
    setDateRangePreset("all");
    setCurrentPage(1);
    setSelectedTxIds(new Set());
  };

  const handleCopyId = (id: string) => {
    navigator.clipboard.writeText(id);
    setCopiedId(true);
    setTimeout(() => setCopiedId(false), 2000);
  };

  const toggleSelectAll = () => {
    if (selectedTxIds.size === paginatedTransactions.length && paginatedTransactions.length > 0) {
      setSelectedTxIds(new Set());
    } else {
      setSelectedTxIds(new Set(paginatedTransactions.map((t) => t.id)));
    }
  };

  const toggleSelectTx = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const next = new Set(selectedTxIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelectedTxIds(next);
  };

  if (loading) {
    return (
      <div className="min-h-[70vh] flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="w-8 h-8 text-indigo-500 animate-spin" />
          <p className="text-sm font-medium text-slate-400">Loading your transactions…</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-[70vh] flex items-center justify-center px-4">
        <div className="max-w-md w-full p-8 rounded-3xl bg-[#0d1322]/90 border border-white/10 shadow-2xl text-center">
          <div className="w-12 h-12 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-400 mx-auto flex items-center justify-center mb-4">
            <AlertTriangle size={24} />
          </div>
          <h2 className="text-lg font-bold text-white mb-2">Transactions Unavailable</h2>
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
    <div className="w-full max-w-[1520px] mx-auto px-5 sm:px-8 lg:px-10 xl:px-12 py-7 sm:py-8 space-y-7 pb-16">
      {/* ─────────────────────────────────────────────────────────────
          1. TRANSACTIONS HEADER
      ───────────────────────────────────────────────────────────── */}
      <motion.div
        initial={reduceMotion ? undefined : { opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
        className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"
      >
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
            Transactions
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Your complete financial activity in one place.
          </p>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          {/* Date Range Dropdown */}
          <div ref={dateDropdownRef} className="relative">
            <button
              onClick={() => setShowDateDropdown((v) => !v)}
              className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-[#0d1322]/80 hover:bg-[#1e293b]/80 border border-white/[0.08] hover:border-white/20 text-xs font-medium text-slate-300 transition-all shadow-sm"
              aria-haspopup="true"
              aria-expanded={showDateDropdown}
            >
              <Calendar size={13} className="text-indigo-400" />
              <span>{dateRangeLabel}</span>
              <ChevronDown size={13} className="text-slate-500" />
            </button>

            {showDateDropdown && (
              <div className="absolute right-0 top-full mt-2 w-56 rounded-2xl bg-[#0d1322] border border-white/15 shadow-2xl p-1.5 z-50 text-xs space-y-0.5">
                {[
                  { id: "all", label: "All Recorded Time" },
                  { id: "30d", label: "Last 30 Days" },
                  { id: "90d", label: "Last 90 Days" },
                  { id: "180d", label: "Last 6 Months" },
                ].map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => {
                      setDateRangePreset(item.id);
                      setShowDateDropdown(false);
                      setCurrentPage(1);
                    }}
                    className={`w-full text-left px-3 py-2 rounded-xl transition-colors flex items-center justify-between text-xs ${
                      dateRangePreset === item.id
                        ? "bg-indigo-600/20 text-indigo-300 font-semibold"
                        : "text-slate-300 hover:bg-white/[0.06] hover:text-white"
                    }`}
                  >
                    <span>{item.label}</span>
                    {dateRangePreset === item.id && <Check size={13} className="text-indigo-400 shrink-0" />}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Upload More Data Button */}
          <button
            onClick={onUpload}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 text-white text-xs font-semibold shadow-md shadow-indigo-600/25 transition-all"
          >
            <Upload size={13} />
            <span>Upload more data</span>
          </button>
        </div>
      </motion.div>

      {/* ─────────────────────────────────────────────────────────────
          2. SUMMARY CARDS (4 CARDS)
      ───────────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-5">
        {/* Card 1: Total Outflow */}
        <motion.div
          initial={reduceMotion ? undefined : { opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.05 }}
          className="rounded-2xl border border-white/[0.08] bg-[#0d1322]/80 backdrop-blur-md p-5 shadow-sm hover:border-white/15 hover:shadow-lg transition-all duration-200 relative overflow-hidden"
        >
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center text-rose-400 shrink-0">
                <ArrowDown size={18} />
              </div>
              <div>
                <p className="text-xs font-medium text-slate-400">Total Outflow</p>
                <p className="font-mono text-xl sm:text-2xl font-bold text-white tracking-tight mt-0.5">
                  <AnimatedCounter value={summary.spent} prefix="₹" />
                </p>
              </div>
            </div>

            {/* Sparkline curve */}
            <div className="w-16 h-8 shrink-0" aria-hidden="true">
              <svg viewBox="0 0 64 32" fill="none" className="w-full h-full text-rose-500/70">
                <path
                  d="M2 24 C 18 10, 36 28, 62 6"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              </svg>
            </div>
          </div>

          <div className="mt-3.5 flex items-center justify-between text-xs">
            <span className="text-slate-400">
              {summary.expenseCount.toLocaleString("en-IN")} debit transactions
            </span>
            <span className="bg-rose-500/15 text-rose-400 border border-rose-500/25 px-1.5 py-0.2 rounded-full text-[10px] font-mono font-medium">
              ↑ 12%
            </span>
          </div>
        </motion.div>

        {/* Card 2: Total Inflow */}
        <motion.div
          initial={reduceMotion ? undefined : { opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.1 }}
          className="rounded-2xl border border-white/[0.08] bg-[#0d1322]/80 backdrop-blur-md p-5 shadow-sm hover:border-white/15 hover:shadow-lg transition-all duration-200 relative overflow-hidden"
        >
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 shrink-0">
                <ArrowUp size={18} />
              </div>
              <div>
                <p className="text-xs font-medium text-slate-400">Total Inflow</p>
                <p className="font-mono text-xl sm:text-2xl font-bold text-white tracking-tight mt-0.5">
                  <AnimatedCounter value={summary.income} prefix="₹" />
                </p>
              </div>
            </div>

            {/* Sparkline curve */}
            <div className="w-16 h-8 shrink-0" aria-hidden="true">
              <svg viewBox="0 0 64 32" fill="none" className="w-full h-full text-emerald-500/70">
                <path
                  d="M2 28 C 22 24, 38 8, 62 4"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              </svg>
            </div>
          </div>

          <div className="mt-3.5 flex items-center justify-between text-xs">
            <span className="text-slate-400">
              {summary.incomeCount.toLocaleString("en-IN")} credit transactions
            </span>
            <span className="bg-emerald-500/15 text-emerald-400 border border-emerald-500/25 px-1.5 py-0.2 rounded-full text-[10px] font-mono font-medium">
              ↑ 8%
            </span>
          </div>
        </motion.div>

        {/* Card 3: Total Transactions */}
        <motion.div
          initial={reduceMotion ? undefined : { opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.15 }}
          className="rounded-2xl border border-white/[0.08] bg-[#0d1322]/80 backdrop-blur-md p-5 shadow-sm hover:border-white/15 hover:shadow-lg transition-all duration-200 relative overflow-hidden"
        >
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400 shrink-0">
                <Layers size={18} />
              </div>
              <div>
                <p className="text-xs font-medium text-slate-400">Total Transactions</p>
                <p className="font-mono text-xl sm:text-2xl font-bold text-white tracking-tight mt-0.5">
                  <AnimatedCounter value={summary.totalCount} />
                </p>
              </div>
            </div>

            {/* Sparkline curve */}
            <div className="w-16 h-8 shrink-0" aria-hidden="true">
              <svg viewBox="0 0 64 32" fill="none" className="w-full h-full text-purple-500/70">
                <path
                  d="M2 20 C 16 12, 42 26, 62 8"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              </svg>
            </div>
          </div>

          <div className="mt-3.5 flex items-center justify-between text-xs">
            <span className="text-slate-400">Recorded transactions</span>
            <span className="bg-purple-500/15 text-purple-400 border border-purple-500/25 px-1.5 py-0.2 rounded-full text-[10px] font-mono font-medium">
              ↑ 5%
            </span>
          </div>
        </motion.div>

        {/* Card 4: Average Transaction */}
        <motion.div
          initial={reduceMotion ? undefined : { opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.2 }}
          className="rounded-2xl border border-white/[0.08] bg-[#0d1322]/80 backdrop-blur-md p-5 shadow-sm hover:border-white/15 hover:shadow-lg transition-all duration-200 relative overflow-hidden"
        >
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 shrink-0">
                <Receipt size={18} />
              </div>
              <div>
                <p className="text-xs font-medium text-slate-400">Average Transaction</p>
                <p className="font-mono text-xl sm:text-2xl font-bold text-white tracking-tight mt-0.5">
                  <AnimatedCounter value={summary.avg} prefix="₹" />
                </p>
              </div>
            </div>

            {/* Sparkline curve */}
            <div className="w-16 h-8 shrink-0" aria-hidden="true">
              <svg viewBox="0 0 64 32" fill="none" className="w-full h-full text-amber-500/70">
                <path
                  d="M2 18 C 20 22, 40 10, 62 14"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              </svg>
            </div>
          </div>

          <div className="mt-3.5 flex items-center justify-between text-xs">
            <span className="text-slate-400">Average transaction amount</span>
            <span className="bg-amber-500/15 text-amber-400 border border-amber-500/25 px-1.5 py-0.2 rounded-full text-[10px] font-mono font-medium">
              ↑ 3%
            </span>
          </div>
        </motion.div>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          3. FILTER & SEARCH TOOLBAR
      ───────────────────────────────────────────────────────────── */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        {/* Search Input */}
        <div className="relative flex-1 max-w-full lg:max-w-md">
          <Search size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setCurrentPage(1);
            }}
            placeholder="Search transactions... (merchant, category, amount, etc.)"
            className="w-full pl-9 pr-8 py-2 rounded-xl bg-[#0d1322]/80 border border-white/10 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500/70 transition-all"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white"
            >
              <X size={12} />
            </button>
          )}
        </div>

        {/* Quick Filter Chips: All, Income, Expense, Recurring */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 lg:pb-0 scrollbar-none">
          {(["All", "Income", "Expense", "Recurring"] as const).map((chip) => {
            const active = typeChipFilter === chip;
            return (
              <button
                key={chip}
                onClick={() => {
                  setTypeChipFilter(chip);
                  setCurrentPage(1);
                }}
                className={`px-4 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-all ${
                  active
                    ? "bg-[#4f46e5] text-white shadow-md shadow-indigo-600/30"
                    : "text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]"
                }`}
              >
                {chip}
              </button>
            );
          })}
        </div>

        {/* More Filter, Sort & View Mode */}
        <div className="flex items-center gap-3 shrink-0">
          {/* More Filters Dropdown */}
          <div ref={moreFilterRef} className="relative">
            <button
              type="button"
              onClick={() => setShowMoreFilterDropdown((v) => !v)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-[#0d1322]/80 border border-white/10 hover:border-white/20 text-xs text-slate-300 transition-colors"
            >
              <Filter size={12} className="text-indigo-400" />
              <span>More</span>
              <ChevronDown size={11} className="text-slate-500" />
            </button>

            {showMoreFilterDropdown && (
              <div className="absolute right-0 top-full mt-2 w-56 rounded-2xl bg-[#0d1322] border border-white/15 shadow-2xl p-3 z-50 text-xs space-y-3">
                <div>
                  <p className="font-semibold text-slate-300 mb-1.5">Transaction Type</p>
                  <div className="space-y-1">
                    {(["all", "recurring", "non-recurring"] as const).map((mode) => (
                      <button
                        key={mode}
                        onClick={() => {
                          setRecurringFilter(mode);
                          setShowMoreFilterDropdown(false);
                          setCurrentPage(1);
                        }}
                        className={`w-full text-left px-2 py-1 rounded-lg capitalize text-xs ${
                          recurringFilter === mode ? "bg-indigo-600/20 text-indigo-300" : "text-slate-400 hover:bg-white/[0.04]"
                        }`}
                      >
                        {mode.replace("-", " ")}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Sort By Dropdown */}
          <div ref={sortDropdownRef} className="relative">
            <button
              type="button"
              onClick={() => setShowSortDropdown((v) => !v)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-[#0d1322]/80 border border-white/10 hover:border-white/20 text-xs text-slate-300 transition-colors"
              aria-haspopup="true"
              aria-expanded={showSortDropdown}
            >
              <ArrowUpDown size={12} className="text-indigo-400" />
              <span>Sort by:</span>
              <span className="font-semibold text-white capitalize">
                {sortKey === "newest"
                  ? "Newest First"
                  : sortKey === "oldest"
                  ? "Oldest First"
                  : sortKey === "highest"
                  ? "Highest Amount"
                  : sortKey === "lowest"
                  ? "Lowest Amount"
                  : "Alphabetical"}
              </span>
              <ChevronDown size={11} className="text-slate-500" />
            </button>

            {showSortDropdown && (
              <div className="absolute right-0 top-full mt-2 w-52 rounded-2xl bg-[#0d1322] border border-white/15 shadow-2xl p-1.5 z-50 text-xs space-y-0.5">
                {[
                  { id: "newest", label: "Newest First" },
                  { id: "oldest", label: "Oldest First" },
                  { id: "highest", label: "Highest Amount" },
                  { id: "lowest", label: "Lowest Amount" },
                  { id: "merchant-az", label: "Merchant A–Z" },
                  { id: "merchant-za", label: "Merchant Z–A" },
                ].map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => {
                      setSortKey(s.id as typeof sortKey);
                      setShowSortDropdown(false);
                      setCurrentPage(1);
                    }}
                    className={`w-full text-left px-3 py-2 rounded-xl transition-colors flex items-center justify-between text-xs ${
                      sortKey === s.id
                        ? "bg-indigo-600/20 text-indigo-300 font-semibold"
                        : "text-slate-300 hover:bg-white/[0.06] hover:text-white"
                    }`}
                  >
                    <span>{s.label}</span>
                    {sortKey === s.id && <Check size={13} className="text-indigo-400 shrink-0" />}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* View mode toggle */}
          <div className="flex items-center rounded-xl border border-white/10 bg-[#0d1322]/80 p-0.5">
            <button
              onClick={() => setViewMode("list")}
              className={`p-1.5 rounded-lg transition-colors ${
                viewMode === "list" ? "bg-[#1e293b] text-white" : "text-slate-500 hover:text-slate-300"
              }`}
              title="List view"
            >
              <LayoutList size={13} />
            </button>
            <button
              onClick={() => setViewMode("grid")}
              className={`p-1.5 rounded-lg transition-colors ${
                viewMode === "grid" ? "bg-[#1e293b] text-white" : "text-slate-500 hover:text-slate-300"
              }`}
              title="Grid view"
            >
              <LayoutGrid size={13} />
            </button>
          </div>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          4. MAIN 2-COLUMN LAYOUT: FILTERS PANEL + TRANSACTIONS TABLE
      ───────────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-6 items-start">
        {/* Left Filters Panel */}
        <div className="rounded-2xl border border-white/[0.08] bg-[#0d1322]/80 backdrop-blur-md p-5 space-y-5">
          {/* Header & Reset */}
          <div className="flex items-center justify-between pb-3 border-b border-white/[0.06]">
            <span className="text-sm font-semibold text-white">Filters</span>
            <button
              onClick={resetFilters}
              className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1 transition-colors"
            >
              <RotateCcw size={11} />
              <span>Reset</span>
            </button>
          </div>

          {/* Section 1: Date Range */}
          <div className="space-y-1.5">
            <span className="text-xs font-medium text-slate-400 flex items-center gap-1.5">
              <Calendar size={13} className="text-indigo-400" />
              <span>Date Range</span>
            </span>
            <div className="p-2.5 rounded-xl bg-white/[0.03] border border-white/[0.08] text-xs text-slate-300 flex items-center justify-between">
              <span className="truncate">{dateRangeLabel}</span>
              <ChevronDown size={12} className="text-slate-500 shrink-0" />
            </div>
          </div>

          {/* Section 2: Amount Range */}
          <div className="space-y-1.5">
            <span className="text-xs font-medium text-slate-400 flex items-center gap-1.5">
              <Wallet size={13} className="text-indigo-400" />
              <span>Amount Range</span>
            </span>
            <div className="grid grid-cols-2 gap-2">
              <div className="relative">
                <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-xs text-slate-500 font-mono">₹</span>
                <input
                  type="number"
                  placeholder="Min"
                  value={minAmount}
                  onChange={(e) => {
                    setMinAmount(e.target.value);
                    setCurrentPage(1);
                  }}
                  className="w-full pl-6 pr-2 py-1.5 rounded-xl bg-white/[0.03] border border-white/[0.08] text-xs text-white placeholder-slate-600 focus:outline-none focus:border-indigo-500 font-mono"
                />
              </div>
              <div className="relative">
                <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-xs text-slate-500 font-mono">₹</span>
                <input
                  type="number"
                  placeholder="Max"
                  value={maxAmount}
                  onChange={(e) => {
                    setMaxAmount(e.target.value);
                    setCurrentPage(1);
                  }}
                  className="w-full pl-6 pr-2 py-1.5 rounded-xl bg-white/[0.03] border border-white/[0.08] text-white placeholder-slate-600 focus:outline-none focus:border-indigo-500 font-mono"
                />
              </div>
            </div>
          </div>

          {/* Section 3: Transaction Type */}
          <div className="space-y-2">
            <span className="text-xs font-medium text-slate-400 flex items-center gap-1.5">
              <Layers size={13} className="text-indigo-400" />
              <span>Transaction Type</span>
            </span>
            <div className="flex flex-wrap gap-1.5">
              {(["All", "Income", "Expense"] as const).map((label) => (
                <button
                  key={label}
                  onClick={() => {
                    setTypeChipFilter(label === "All" ? "All" : label === "Income" ? "Income" : "Expense");
                    setCurrentPage(1);
                  }}
                  className={`px-3 py-1 rounded-lg text-xs font-medium border transition-colors ${
                    typeChipFilter === label
                      ? "bg-indigo-600/30 border-indigo-500 text-white"
                      : "bg-white/[0.03] border-white/[0.08] text-slate-400 hover:text-slate-200"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>

            {/* Recurring toggle pills */}
            <div className="flex items-center gap-1.5 pt-1">
              <button
                onClick={() => {
                  setRecurringFilter(recurringFilter === "recurring" ? "all" : "recurring");
                  setCurrentPage(1);
                }}
                className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors ${
                  recurringFilter === "recurring"
                    ? "bg-purple-600/30 border-purple-500 text-purple-300"
                    : "bg-white/[0.03] border-white/[0.08] text-slate-400 hover:text-slate-200"
                }`}
              >
                <RefreshCw size={11} />
                <span>Recurring</span>
              </button>

              <button
                onClick={() => {
                  setRecurringFilter(recurringFilter === "non-recurring" ? "all" : "non-recurring");
                  setCurrentPage(1);
                }}
                className={`px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors ${
                  recurringFilter === "non-recurring"
                    ? "bg-indigo-600/30 border-indigo-500 text-white"
                    : "bg-white/[0.03] border-white/[0.08] text-slate-400 hover:text-slate-200"
                }`}
              >
                <span>Non-recurring</span>
              </button>
            </div>
          </div>

          {/* Section 4: Categories */}
          <div className="space-y-2">
            <span className="text-xs font-medium text-slate-400 flex items-center gap-1.5">
              <Tag size={13} className="text-indigo-400" />
              <span>Categories</span>
            </span>
            <div className="space-y-1 max-h-40 overflow-y-auto pr-1">
              {availableCategories.slice(0, 10).map((cat) => {
                const checked = selectedCategories.includes(cat);
                return (
                  <label
                    key={cat}
                    className="flex items-center gap-2 px-2 py-1 rounded-lg hover:bg-white/[0.04] cursor-pointer text-xs text-slate-300"
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => {
                        setSelectedCategories((prev) =>
                          checked ? prev.filter((c) => c !== cat) : [...prev, cat]
                        );
                        setCurrentPage(1);
                      }}
                      className="rounded border-slate-700 bg-slate-900 text-indigo-600 w-3.5 h-3.5"
                    />
                    <span className="truncate">{cat}</span>
                  </label>
                );
              })}
            </div>
          </div>

          {/* Section 5: Transaction Status */}
          <div className="space-y-1.5 pt-1 border-t border-white/[0.06]">
            <span className="text-xs font-medium text-slate-400 flex items-center gap-1.5">
              <ShieldCheck size={13} className="text-indigo-400" />
              <span>Transaction Status</span>
            </span>
            <div className="flex flex-wrap gap-1.5">
              {(["all", "successful", "failed", "pending"] as const).map((st) => (
                <button
                  key={st}
                  onClick={() => {
                    setStatusFilter(st);
                    setCurrentPage(1);
                  }}
                  className={`px-2.5 py-1 rounded-lg text-xs capitalize border transition-colors ${
                    statusFilter === st
                      ? "bg-indigo-600/30 border-indigo-500 text-white"
                      : "bg-white/[0.03] border-white/[0.08] text-slate-400 hover:text-slate-200"
                  }`}
                >
                  {st}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Right Table Container */}
        <div className="rounded-2xl border border-white/[0.08] bg-[#0d1322]/80 backdrop-blur-md overflow-hidden shadow-xl">
          {paginatedTransactions.length === 0 ? (
            <div className="py-20 px-6 text-center space-y-3">
              <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 mx-auto flex items-center justify-center">
                <Search size={22} />
              </div>
              <h3 className="text-base font-semibold text-white">No transactions match your filters</h3>
              <p className="text-xs text-slate-400 max-w-sm mx-auto">
                Try adjusting your search criteria, clearing selected categories, or resetting filters.
              </p>
              <button
                onClick={resetFilters}
                className="mt-2 px-4 py-2 rounded-xl bg-[#1e293b] hover:bg-indigo-600/20 border border-white/10 text-xs font-medium text-slate-200 transition-colors"
              >
                Reset All Filters
              </button>
            </div>
          ) : viewMode === "list" ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-white/[0.06] text-[11px] font-semibold text-slate-400 uppercase tracking-wider bg-white/[0.02]">
                    <th className="py-3.5 pl-4 pr-2 w-10">
                      <input
                        type="checkbox"
                        checked={selectedTxIds.size === paginatedTransactions.length && paginatedTransactions.length > 0}
                        onChange={toggleSelectAll}
                        className="rounded border-slate-700 bg-slate-900 text-indigo-600 w-3.5 h-3.5"
                      />
                    </th>
                    <th className="py-3.5 px-3 whitespace-nowrap">
                      <div className="flex items-center gap-1 cursor-pointer" onClick={() => setSortKey(sortKey === "newest" ? "oldest" : "newest")}>
                        <span>Date</span>
                        <ArrowUpDown size={11} className="text-slate-500" />
                      </div>
                    </th>
                    <th className="py-3.5 px-4 min-w-[220px]">Description</th>
                    <th className="py-3.5 px-3">Category</th>
                    <th className="py-3.5 px-3">Type</th>
                    <th className="py-3.5 px-4 text-right">Amount</th>
                    <th className="py-3.5 px-3">Status</th>
                    <th className="py-3.5 pr-4 text-right w-12">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.04]">
                  {paginatedTransactions.map((tx) => {
                    const isSelected = selectedTxIds.has(tx.id);
                    return (
                      <tr
                        key={tx.id}
                        onClick={() => setSelectedTx(tx)}
                        className={`group hover:bg-white/[0.03] transition-colors cursor-pointer ${
                          isSelected ? "bg-indigo-600/10" : ""
                        }`}
                      >
                        {/* Checkbox */}
                        <td className="py-3.5 pl-4 pr-2" onClick={(e) => toggleSelectTx(tx.id, e)}>
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => {}}
                            className="rounded border-slate-700 bg-slate-900 text-indigo-600 w-3.5 h-3.5"
                          />
                        </td>

                        {/* Date */}
                        <td className="py-3.5 px-3 font-mono text-xs text-slate-400 whitespace-nowrap">
                          {formatDateShort(tx.date)}
                        </td>

                        {/* Description & Merchant */}
                        <td className="py-3.5 px-4">
                          <div className="flex items-center gap-3">
                            <MerchantLogo name={tx.merchant} category={tx.category} size="md" />
                            <div className="min-w-0 max-w-[240px] xl:max-w-[320px]">
                              <p className="text-xs sm:text-sm font-semibold text-white truncate group-hover:text-indigo-300 transition-colors">
                                {tx.merchant}
                              </p>
                              <p className="text-[11px] text-slate-400 truncate mt-0.5">
                                {tx.description}
                              </p>
                            </div>
                          </div>
                        </td>

                        {/* Category */}
                        <td className="py-3.5 px-3 whitespace-nowrap">
                          <CategoryBadge category={tx.category} />
                        </td>

                        {/* Type & Recurring indicator */}
                        <td className="py-3.5 px-3 whitespace-nowrap">
                          {tx.recurring ? (
                            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-purple-500/10 text-purple-400 border border-purple-500/20">
                              <RefreshCw size={11} />
                              <span>Recurring</span>
                            </span>
                          ) : (
                            <TypeBadge type={tx.type} />
                          )}
                        </td>

                        {/* Amount */}
                        <td className="py-3.5 px-4 text-right font-mono text-xs sm:text-sm font-bold whitespace-nowrap">
                          <span className={tx.isIncome ? "text-emerald-400" : "text-rose-400"}>
                            {formatCurrency(tx.amount)}
                          </span>
                        </td>

                        {/* Status */}
                        <td className="py-3.5 px-3 whitespace-nowrap">
                          <span className="inline-flex items-center gap-1.5 text-xs text-emerald-400 font-medium">
                            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                            <span>Successful</span>
                          </span>
                        </td>

                        {/* Actions */}
                        <td className="py-3.5 pr-4 text-right" onClick={(e) => e.stopPropagation()}>
                          <button
                            onClick={() => setSelectedTx(tx)}
                            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-white/[0.08] transition-colors"
                            aria-label="Transaction details"
                          >
                            <MoreHorizontal size={14} />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            /* Grid View */
            <div className="p-4 grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
              {paginatedTransactions.map((tx) => (
                <div
                  key={tx.id}
                  onClick={() => setSelectedTx(tx)}
                  className="rounded-2xl border border-white/[0.08] bg-white/[0.02] hover:bg-white/[0.05] p-4 transition-all cursor-pointer group"
                >
                  <div className="flex items-center justify-between mb-3">
                    <MerchantLogo name={tx.merchant} category={tx.category} size="md" />
                    <span className="font-mono text-xs text-slate-400">{formatDateShort(tx.date)}</span>
                  </div>
                  <p className="font-semibold text-sm text-white group-hover:text-indigo-300 transition-colors truncate">
                    {tx.merchant}
                  </p>
                  <p className="text-xs text-slate-400 truncate mt-0.5">{tx.description}</p>
                  <div className="mt-3 pt-3 border-t border-white/[0.06] flex items-center justify-between">
                    <CategoryBadge category={tx.category} />
                    <span className={`font-mono text-sm font-bold ${tx.isIncome ? "text-emerald-400" : "text-rose-400"}`}>
                      {formatCurrency(tx.amount)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Pagination Footer matching reference screenshot */}
          <div className="px-5 py-4 border-t border-white/[0.06] flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-slate-400">
            <span>
              Showing {(currentPage - 1) * PAGE_SIZE + 1}–{Math.min(currentPage * PAGE_SIZE, sortedTransactions.length)} of {sortedTransactions.length.toLocaleString("en-IN")} transactions
            </span>

            <div className="flex items-center gap-1.5">
              <button
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={currentPage === 1}
                className="p-1.5 rounded-lg border border-white/10 text-slate-400 hover:text-white hover:bg-white/[0.06] disabled:opacity-30 disabled:pointer-events-none transition-colors"
                aria-label="Previous page"
              >
                <ChevronLeft size={14} />
              </button>

              {/* Page numbers */}
              {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                const pageNum = i + 1;
                const active = currentPage === pageNum;
                return (
                  <button
                    key={pageNum}
                    onClick={() => setCurrentPage(pageNum)}
                    className={`w-7 h-7 rounded-lg text-xs font-mono font-medium transition-colors ${
                      active
                        ? "bg-[#4f46e5] text-white shadow-sm"
                        : "text-slate-400 hover:text-white hover:bg-white/[0.06]"
                    }`}
                  >
                    {pageNum}
                  </button>
                );
              })}

              {totalPages > 5 && (
                <>
                  <span className="px-1 text-slate-600">…</span>
                  <button
                    onClick={() => setCurrentPage(totalPages)}
                    className={`w-7 h-7 rounded-lg text-xs font-mono font-medium transition-colors ${
                      currentPage === totalPages
                        ? "bg-[#4f46e5] text-white"
                        : "text-slate-400 hover:text-white hover:bg-white/[0.06]"
                    }`}
                  >
                    {totalPages}
                  </button>
                </>
              )}

              <button
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
                className="p-1.5 rounded-lg border border-white/10 text-slate-400 hover:text-white hover:bg-white/[0.06] disabled:opacity-30 disabled:pointer-events-none transition-colors"
                aria-label="Next page"
              >
                <ChevronRight size={14} />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          5. TRANSACTION DETAIL DRAWER
      ───────────────────────────────────────────────────────────── */}
      <AnimatePresence>
        {selectedTx && (
          <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm">
            <motion.div
              initial={{ x: "100%" }}
              animate={{ x: 0 }}
              exit={{ x: "100%" }}
              transition={{ duration: 0.25 }}
              className="w-full max-w-md h-full bg-[#0d1322] border-l border-white/10 p-4 sm:p-6 shadow-2xl flex flex-col justify-between overflow-y-auto"
            >
              <div>
                <div className="flex items-center justify-between pb-4 border-b border-white/[0.08]">
                  <h3 className="text-base font-bold text-white">Transaction Details</h3>
                  <button
                    onClick={() => setSelectedTx(null)}
                    className="p-1.5 rounded-xl text-slate-400 hover:text-white hover:bg-white/[0.08] transition-colors"
                  >
                    <X size={16} />
                  </button>
                </div>

                <div className="pt-6 text-center space-y-2">
                  <div className="mx-auto flex justify-center">
                    <MerchantLogo name={selectedTx.merchant} category={selectedTx.category} size="lg" />
                  </div>
                  <h4 className="text-lg font-bold text-white">{selectedTx.merchant}</h4>
                  <p className={`font-mono text-2xl font-bold ${selectedTx.isIncome ? "text-emerald-400" : "text-rose-400"}`}>
                    {formatCurrency(selectedTx.amount)}
                  </p>
                  <p className="text-xs text-slate-400">{selectedTx.description}</p>
                </div>

                <div className="mt-6 space-y-3 p-4 rounded-2xl bg-white/[0.03] border border-white/[0.06] text-xs">
                  <div className="flex justify-between py-1 border-b border-white/[0.04]">
                    <span className="text-slate-400">Date</span>
                    <span className="font-mono text-white">{formatDateShort(selectedTx.date)}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-white/[0.04]">
                    <span className="text-slate-400">Category</span>
                    <CategoryBadge category={selectedTx.category} />
                  </div>
                  <div className="flex justify-between py-1 border-b border-white/[0.04]">
                    <span className="text-slate-400">Recurring Status</span>
                    <span className="text-white">
                      {selectedTx.recurring ? "↻ Recurring commitment" : "One-off transaction"}
                    </span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-white/[0.04]">
                    <span className="text-slate-400">Payment Status</span>
                    <span className="text-emerald-400 font-medium">● Successful</span>
                  </div>
                  <div className="flex justify-between py-1">
                    <span className="text-slate-400">Transaction ID</span>
                    <div className="flex items-center gap-1.5">
                      <span className="font-mono text-slate-300 truncate max-w-[140px]">{selectedTx.id}</span>
                      <button onClick={() => handleCopyId(selectedTx.id)} className="text-indigo-400 hover:text-white">
                        {copiedId ? <Check size={12} /> : <Copy size={12} />}
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              <div className="pt-6 border-t border-white/[0.08] space-y-2">
                {onAskAssistant && (
                  <button
                    onClick={() => {
                      onAskAssistant(`Explain this transaction from ${selectedTx.merchant} for ${formatCurrency(selectedTx.amount)}`);
                      setSelectedTx(null);
                    }}
                    className="w-full flex items-center justify-center gap-2 py-2.5 rounded-full bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-md transition-all"
                  >
                    <Sparkles size={13} />
                    <span>Ask FinSight about this</span>
                  </button>
                )}
                <button
                  onClick={() => setSelectedTx(null)}
                  className="w-full py-2.5 rounded-full bg-white/[0.06] hover:bg-white/[0.1] text-slate-300 text-xs font-medium transition-all"
                >
                  Close
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
