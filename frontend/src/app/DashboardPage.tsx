import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { motion, AnimatePresence, useInView, useReducedMotion } from "motion/react";
import {
  AlertTriangle,
  ArrowRight,
  ArrowUpRight,
  BarChart2,
  Bell,
  Calendar,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CreditCard,
  Edit2,
  Info,
  Landmark,
  MessageCircle,
  PieChart,
  RefreshCw,
  Shield,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Upload,
  Wallet,
  X,
} from "lucide-react";
import { EditIncomeModal } from "./components/EditIncomeModal";
import {
  ApiError,
  AuthenticatedUser,
  CashFlowForecastResponse,
  CommitmentSnapshotResponse,
  DashboardOnboardingResponse,
  DashboardResponse,
  HistoricalDashboardResponse,
  commitmentApi,
  dashboardApi,
  forecastApi,
  getStoredAccessToken,
} from "../api/client";
import {
  AlertItem,
  AttentionInsight,
  CommitmentCategory,
  ExposureTrendData,
} from "./dashboardDataAdapters";
import {
  NormalizedDashboardSnapshot,
  normalizeDashboardSnapshot,
} from "./dashboardSnapshotAdapter";

type AppPage = "dashboard" | "transactions" | "commitments" | "intelligence" | "what-if" | "assistant" | "settings";

interface DashboardPageProps {
  onNavigate: (page: AppPage) => void;
  onAskAssistant: (q?: string) => void;
  user: AuthenticatedUser;
  onUnauthorized: () => void;
  onUpload?: () => void;
}

const EASE = [0.22, 1, 0.36, 1] as const;

function money(value: number) {
  const rounded = Math.round(value);
  if (rounded < 0) {
    return `-₹${Math.abs(rounded).toLocaleString("en-IN")}`;
  }
  return `₹${rounded.toLocaleString("en-IN")}`;
}

function moneyAnimated(value: number) {
  if (value < 0) {
    return `-₹${Math.abs(value).toLocaleString("en-IN")}`;
  }
  return `₹${value.toLocaleString("en-IN")}`;
}

function exposureBandColor(band: string) {
  const b = (band || "").toLowerCase();
  if (b.includes("low") || b.includes("minimal")) return "#10B981";
  if (b.includes("moderate") || b.includes("medium")) return "#F59E0B";
  return "#EF4444";
}

function riskColor(risk: string) {
  const r = (risk || "").toLowerCase();
  if (r.includes("low") || r.includes("minimal")) return "#10B981";
  if (r.includes("medium") || r.includes("moderate")) return "#F59E0B";
  return "#EF4444";
}

function recommendationAction(type: string): { label: string; nav?: AppPage; ask?: string } {
  const t = (type || "").toLowerCase();
  if (t.includes("subscription")) return { label: "Review subscriptions", nav: "commitments" };
  if (t.includes("emi")) return { label: "Review EMIs", nav: "commitments" };
  if (t.includes("bnpl")) return { label: "Review BNPL", nav: "commitments" };
  if (t.includes("maintain") || t.includes("discipline")) {
    return { label: "Keep it up", ask: "How do I maintain my financial resilience?" };
  }
  if (t.includes("forecast") || t.includes("stability") || t.includes("buffer")) {
    return { label: "Study the outlook", ask: "What should I watch out for in the coming months?" };
  }
  return { label: "Ask FinSight", ask: `Tell me more about the ${type} recommendation.` };
}

// ─────────────────────────────────────────────────────────────
// Animated Counter
// ─────────────────────────────────────────────────────────────
function AnimatedNumber({
  value,
  startOn,
  format = (n: number) => n.toLocaleString("en-IN"),
  className,
}: {
  value: number;
  startOn: boolean;
  format?: (n: number) => string;
  className?: string;
}) {
  const reduce = useReducedMotion();
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    if (reduce || !startOn) {
      setDisplay(reduce ? value : 0);
      return;
    }
    const start = performance.now();
    const duration = 900;
    let raf = 0;
    const tick = (now: number) => {
      const p = Math.min((now - start) / duration, 1);
      setDisplay(Math.round(value * (1 - Math.pow(1 - p, 3))));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, startOn, reduce]);

  return <span className={className}>{format(display)}</span>;
}

// ─────────────────────────────────────────────────────────────
// Reveal Animation Wrapper
// ─────────────────────────────────────────────────────────────
function Reveal({
  children,
  delay = 0,
  className,
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
}) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={reduce ? undefined : { opacity: 0, y: 16 }}
      whileInView={reduce ? undefined : { opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "0px 0px -40px 0px" }}
      transition={{ duration: 0.5, delay, ease: EASE }}
    >
      {children}
    </motion.div>
  );
}

// ─────────────────────────────────────────────────────────────
// Financial Health Radial Gauge
// ─────────────────────────────────────────────────────────────
function HealthRadialGauge({
  score,
  label,
  exposureScore,
  riskLevel,
}: {
  score: number;
  label: string;
  exposureScore: number;
  riskLevel: string;
}) {
  const reduce = useReducedMotion();
  const size = 156;
  const stroke = 12;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.min(Math.max(score, 0), 100);
  const offset = circumference * (1 - clamped / 100);
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  const badgeColor = riskColor(riskLevel);

  return (
    <div ref={ref} className="flex flex-col sm:flex-row items-center gap-5 sm:gap-6 w-full">
      {/* Gauge Circle */}
      <div
        className="relative shrink-0 flex items-center justify-center"
        style={{ width: size, height: size }}
        role="img"
        aria-label={`Financial health score: ${Math.round(score)} out of 100`}
      >
        <svg width={size} height={size} className="-rotate-90">
          <defs>
            <linearGradient id="healthGradient" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#10B981" />
              <stop offset="100%" stopColor="#06B6D4" />
            </linearGradient>
          </defs>
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="rgba(255, 255, 255, 0.08)"
            strokeWidth={stroke}
          />
          <motion.circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="url(#healthGradient)"
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={circumference}
            initial={reduce ? undefined : { strokeDashoffset: circumference }}
            animate={inView ? { strokeDashoffset: offset } : {}}
            transition={{ duration: 1.15, ease: EASE }}
          />
        </svg>

        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none text-center">
          <span className="font-sans text-3xl sm:text-[38px] font-bold text-white leading-none tracking-tight">
            <AnimatedNumber value={Math.round(score)} startOn={inView} />
          </span>
          <span className="mt-1 text-[11px] font-mono text-slate-400 tracking-wider">
            / 100
          </span>
        </div>
      </div>

      {/* Details & Benchmarks */}
      <div className="text-center sm:text-left flex-1 min-w-0">
        <h3 className="text-xl sm:text-2xl font-bold tracking-tight text-emerald-400 capitalize">
          {label}
        </h3>
        <p className="mt-1 text-xs text-slate-400 leading-relaxed">
          Exposure score is{" "}
          <span className="text-slate-200 font-mono font-medium">
            {exposureScore.toFixed(2)}%
          </span>
          .
        </p>

        {/* Risk Badge */}
        <div className="mt-2.5 flex items-center justify-center sm:justify-start">
          <span
            className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-mono uppercase tracking-wider font-semibold border"
            style={{
              borderColor: `${badgeColor}35`,
              backgroundColor: `${badgeColor}15`,
              color: badgeColor,
            }}
          >
            <span className="h-1.5 w-1.5 rounded-full animate-pulse" style={{ backgroundColor: badgeColor }} />
            {riskLevel.toUpperCase()} RISK
          </span>
        </div>

        {/* Peer Benchmarks */}
        <div className="mt-4 pt-3 border-t border-white/[0.08] flex flex-wrap items-center justify-center sm:justify-start gap-x-4 gap-y-1.5 text-xs">
          <div className="flex items-center gap-1 text-slate-400 font-medium shrink-0">
            <TrendingUp size={13} />
            <span>Deterministic 6-factor model</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Monthly Commitment Mix Donut (Unified Commitment Engine)
// ─────────────────────────────────────────────────────────────
function CommitmentMixDonut({
  categories,
  total,
}: {
  categories: CommitmentCategory[];
  total: number;
}) {
  const size = 156;
  const stroke = 20;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const cx = size / 2;
  const cy = size / 2;
  const reduce = useReducedMotion();
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  const [hoverKey, setHoverKey] = useState<string | null>(null);

  const visible = categories.filter((c) => c.pct > 0);
  let acc = 0;

  return (
    <div ref={ref} className="flex flex-col sm:flex-row items-center gap-5 sm:gap-6 w-full">
      {/* Donut SVG */}
      <div
        className="relative shrink-0 flex items-center justify-center"
        style={{ width: size, height: size }}
        role="img"
        aria-label="Monthly commitment mix breakdown"
      >
        <svg width={size} height={size} className="-rotate-90">
          <circle
            cx={cx}
            cy={cy}
            r={radius}
            fill="none"
            stroke="rgba(255, 255, 255, 0.08)"
            strokeWidth={stroke}
          />
          {visible.map((cat, i) => {
            const len = (cat.pct / 100) * circumference;
            const dashOffset = acc * circumference * -1;
            acc += cat.pct / 100;
            const dimmed = hoverKey !== null && hoverKey !== cat.key;
            return (
              <motion.circle
                key={cat.key}
                cx={cx}
                cy={cy}
                r={radius}
                fill="none"
                stroke={cat.color}
                strokeWidth={stroke}
                strokeDasharray={`${len} ${circumference - len}`}
                strokeDashoffset={dashOffset}
                initial={reduce ? undefined : { opacity: 0 }}
                animate={{ opacity: dimmed ? 0.3 : 1 }}
                transition={{ duration: 0.5, delay: 0.15 + i * 0.08, ease: EASE }}
              />
            );
          })}
        </svg>

        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none px-2 text-center">
          <span className="font-mono text-base sm:text-lg font-bold text-white leading-tight">
            <AnimatedNumber value={Math.round(total)} startOn={inView} format={moneyAnimated} />
          </span>
          <span className="mt-0.5 text-[8.5px] font-mono uppercase tracking-wider text-slate-400">
            / month
          </span>
        </div>
      </div>

      {/* Legend list */}
      {categories.length === 0 ? (
        <div className="flex-1 w-full text-center sm:text-left py-2">
          <p className="text-xs font-medium text-slate-300">No active recurring commitments</p>
          <p className="text-[11px] text-slate-400 mt-1 leading-relaxed">
            All your spending is currently discretionary. You can track subscriptions, EMIs, or bills from Recurring Payments.
          </p>
        </div>
      ) : (
        <div className="flex-1 w-full space-y-1.5 min-w-0">
          {categories.map((cat) => {
            const dimmed = hoverKey !== null && hoverKey !== cat.key;
            return (
              <div
                key={cat.key}
                onMouseEnter={() => setHoverKey(cat.key)}
                onMouseLeave={() => setHoverKey(null)}
                className={`flex items-center justify-between gap-2 rounded-xl px-2.5 py-1.5 transition-colors cursor-pointer ${
                  hoverKey === cat.key ? "bg-white/[0.08]" : "hover:bg-white/[0.04]"
                }`}
              >
                <div className="flex items-center gap-2 min-w-0">
                  <span
                    className="h-2.5 w-2.5 shrink-0 rounded-full transition-opacity"
                    style={{ backgroundColor: cat.color, opacity: dimmed ? 0.35 : 1 }}
                  />
                  <span className="truncate text-xs font-medium text-slate-200">
                    {cat.label}
                    {cat.count !== undefined && cat.count > 0 && (
                      <span className="ml-1 text-[10px] text-slate-400">({cat.count})</span>
                    )}
                  </span>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="font-mono text-xs font-semibold text-white">
                    {money(cat.amount)}
                  </span>
                  <span className="rounded-full bg-white/[0.06] px-1.5 py-0.5 font-mono text-[10px] text-slate-400 border border-white/[0.08]">
                    {Math.round(cat.pct)}%
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// FINANCIAL EXPOSURE CARD (Left Column — Reference Image Design)
// ─────────────────────────────────────────────────────────────
function FinancialExposureCard({
  exposureScore,
  exposureBand,
  commitments,
  remainingCapacity,
  monthlyCapacity,
}: {
  exposureScore: number;
  exposureBand: string;
  commitments: number;
  remainingCapacity: number;
  monthlyCapacity: number;
}) {
  const reduce = useReducedMotion();
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });

  const size = 168;
  const stroke = 14;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const clampedExposure = Math.min(Math.max(exposureScore, 0), 100);
  const strokeOffset = circumference * (1 - clampedExposure / 100);

  const committedPct = exposureScore;
  const remainingPct = Math.max(0, 100 - exposureScore);

  // Determine active risk band
  let activeBandIndex = 1; // default low
  if (exposureScore <= 0) activeBandIndex = 0;
  else if (exposureScore <= 40) activeBandIndex = 1;
  else if (exposureScore <= 100) activeBandIndex = 2;
  else if (exposureScore <= 120) activeBandIndex = 3;
  else activeBandIndex = 4;

  const riskBands = [
    { label: "Minimal", range: "0%", color: "#10B981" },
    { label: "Low", range: ">0% – 40%", color: "#10B981" },
    { label: "Moderate", range: ">40% – 100%", color: "#F59E0B" },
    { label: "High", range: ">100% – 120%", color: "#F97316" },
    { label: "Critical", range: ">120%", color: "#EF4444" },
  ];

  const isHealthy = exposureScore <= 40;
  const isModerate = exposureScore > 40 && exposureScore <= 100;

  return (
    <div
      ref={ref}
      className="rounded-2xl border border-white/[0.08] bg-[#0d1322]/80 backdrop-blur-md p-6 shadow-sm flex flex-col justify-between"
    >
      <div>
        {/* Header */}
        <div className="flex items-start justify-between gap-4 mb-6">
          <div>
            <h2 className="text-xl font-bold text-white tracking-tight">
              Financial Exposure
            </h2>
            <p className="mt-1 text-xs text-slate-400">
              How much of your financial capacity is committed to recurring payments
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span className="hidden sm:inline-flex items-center rounded-full bg-indigo-500/10 border border-indigo-500/20 px-2.5 py-1 text-[11px] font-medium text-indigo-300">
              Based on recurring commitments
            </span>
            <span className="p-1 rounded-full text-slate-400 hover:text-white transition-colors" title="Headline Exposure reflects your full forward-looking recurring commitment portfolio (Rent, EMIs, BNPL, Subscriptions, Insurance, Mobile) relative to observed monthly capacity.">
              <Info size={16} />
            </span>
          </div>
        </div>

        {/* Main Content: Donut Gauge (Left) + Status & 3 Metrics (Right) */}
        <div className="flex flex-col sm:flex-row items-center sm:items-start gap-6 mb-6">
          {/* Left: Donut Gauge */}
          <div
            className="relative shrink-0 flex items-center justify-center"
            style={{ width: size, height: size }}
          >
            <svg width={size} height={size} className="-rotate-90">
              <defs>
                <linearGradient id="exposureDonutGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#06B6D4" />
                  <stop offset="100%" stopColor="#14B8A6" />
                </linearGradient>
              </defs>
              <circle
                cx={size / 2}
                cy={size / 2}
                r={radius}
                fill="none"
                stroke="rgba(255, 255, 255, 0.08)"
                strokeWidth={stroke}
              />
              <motion.circle
                cx={size / 2}
                cy={size / 2}
                r={radius}
                fill="none"
                stroke="url(#exposureDonutGradient)"
                strokeWidth={stroke}
                strokeLinecap="round"
                strokeDasharray={circumference}
                initial={reduce ? undefined : { strokeDashoffset: circumference }}
                animate={inView ? { strokeDashoffset: strokeOffset } : {}}
                transition={{ duration: 1.15, ease: EASE }}
              />
            </svg>

            <div className="absolute inset-0 flex flex-col items-center justify-center text-center pointer-events-none px-2">
              <span className="font-mono text-2xl sm:text-[28px] font-bold text-white tracking-tight leading-none">
                {exposureScore.toFixed(2)}%
              </span>
              <span className="mt-1 text-xs text-slate-400 font-medium">
                Exposed
              </span>
              <div className="mt-2">
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/15 border border-emerald-500/25 px-2.5 py-0.5 text-[10px] font-medium text-emerald-400">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                  {exposureBand} Exposure
                </span>
              </div>
            </div>
          </div>

          {/* Right: Shield Banner + 3 Metrics */}
          <div className="flex-1 w-full min-w-0 space-y-4">
            {/* Shield Banner */}
            <div className="rounded-xl border border-emerald-500/20 bg-emerald-950/20 p-3.5 flex items-start gap-3">
              <div className="p-1 rounded-lg text-emerald-400 shrink-0 mt-0.5">
                <Shield size={18} />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-emerald-300 leading-tight">
                  {isHealthy
                    ? "Your exposure is within a healthy range."
                    : isModerate
                    ? "Your exposure is moderate."
                    : "Your exposure is elevated."}
                </p>
                <p className="mt-0.5 text-xs text-slate-300 leading-relaxed">
                  {exposureScore.toFixed(2)}% of your monthly capacity is committed.
                </p>
              </div>
            </div>

            {/* 3 Metrics Row */}
            <div className="grid grid-cols-3 gap-2 pt-1">
              {/* Metric 1: Committed */}
              <div>
                <p className="font-mono text-lg sm:text-xl font-bold text-white tracking-tight">
                  {money(commitments)}
                </p>
                <div className="flex items-center gap-1.5 mt-1">
                  <span className="h-2 w-2 rounded-full bg-purple-400 shrink-0" />
                  <span className="text-[11px] text-slate-400 truncate">Committed per month</span>
                </div>
              </div>

              {/* Metric 2: Remaining capacity */}
              <div>
                <p className="font-mono text-lg sm:text-xl font-bold text-white tracking-tight">
                  {money(remainingCapacity)}
                </p>
                <div className="flex items-center gap-1.5 mt-1">
                  <span className="h-2 w-2 rounded-full bg-emerald-400 shrink-0" />
                  <span className="text-[11px] text-slate-400 truncate">Remaining capacity</span>
                </div>
              </div>

              {/* Metric 3: Monthly capacity */}
              <div>
                <p className="font-mono text-lg sm:text-xl font-bold text-white tracking-tight">
                  {money(monthlyCapacity)}
                </p>
                <div className="flex items-center gap-1.5 mt-1">
                  <span className="h-2 w-2 rounded-full bg-slate-400 shrink-0" />
                  <span className="text-[11px] text-slate-400 truncate">Monthly capacity</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Capacity Progress Bar */}
        <div className="space-y-1.5 mb-6">
          <div className="w-full h-3 rounded-full bg-white/[0.08] overflow-hidden flex">
            <motion.div
              className="h-full bg-gradient-to-r from-indigo-500 via-indigo-400 to-purple-400 rounded-full"
              initial={reduce ? undefined : { width: 0 }}
              animate={inView ? { width: `${Math.min(100, Math.max(0, committedPct))}%` } : {}}
              transition={{ duration: 0.9, ease: EASE }}
            />
          </div>
          <div className="flex items-center justify-between text-xs font-mono text-slate-400 px-0.5">
            <span>{committedPct.toFixed(2)}% committed</span>
            <span>{remainingPct.toFixed(2)}% remaining</span>
          </div>
        </div>

        {/* Exposure Risk Levels Strip */}
        <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
          <p className="text-[11px] font-mono uppercase tracking-wider text-slate-400 mb-2">
            Exposure Risk Levels
          </p>
          <div className="grid grid-cols-5 gap-1.5 sm:gap-2">
            {riskBands.map((band, idx) => {
              const isActive = idx === activeBandIndex;
              return (
                <div
                  key={band.label}
                  className={`rounded-lg p-2 transition-all flex flex-col items-center text-center relative ${
                    isActive
                      ? "border border-emerald-500/60 bg-emerald-500/10 shadow-[0_0_12px_rgba(16,185,129,0.2)] ring-1 ring-emerald-500/30"
                      : "border border-white/[0.04] bg-white/[0.01]"
                  }`}
                >
                  <div
                    className="w-full h-0.5 rounded-full mb-1.5"
                    style={{ backgroundColor: band.color, opacity: isActive ? 1 : 0.4 }}
                  />
                  <span
                    className={`font-mono text-[10px] leading-tight ${
                      isActive ? "text-emerald-300 font-bold" : "text-slate-400"
                    }`}
                  >
                    {band.range}
                  </span>
                  <span
                    className={`text-[10px] sm:text-[11px] mt-0.5 ${
                      isActive ? "text-white font-semibold" : "text-slate-400"
                    }`}
                  >
                    {band.label}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// EXPOSURE TREND CARD (Right Column — Reference Image Design)
// ─────────────────────────────────────────────────────────────
function ExposureTrendCard({
  trendData,
}: {
  trendData: ExposureTrendData;
}) {
  const reduce = useReducedMotion();
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  const [hoveredPoint, setHoveredPoint] = useState<number | null>(null);

  const hasData = trendData.isAvailable && trendData.points.length >= 3;

  // Chart dimensions
  const svgWidth = 540;
  const svgHeight = 200;
  const padLeft = 45;
  const padRight = 35;
  const padTop = 32;
  const padBottom = 28;

  const chartW = svgWidth - padLeft - padRight;
  const chartH = svgHeight - padTop - padBottom;

  const maxVal = Math.max(60, Math.ceil(Math.max(...(trendData.points.map((p) => p.exposure) || [0]), 10) / 10) * 10);
  const yTicks = [0, 10, 20, 30, 40, 50, 60];

  const points = trendData.points;
  const n = points.length;

  // Coordinates
  const coords = points.map((p, i) => {
    const x = padLeft + (i / Math.max(n - 1, 1)) * chartW;
    const y = padTop + chartH - (p.exposure / maxVal) * chartH;
    return { x, y, ...p };
  });

  // Build smooth curve path
  let pathD = "";
  if (coords.length > 0) {
    pathD = `M ${coords[0].x} ${coords[0].y}`;
    for (let i = 0; i < coords.length - 1; i++) {
      const curr = coords[i];
      const next = coords[i + 1];
      const cpX1 = curr.x + (next.x - curr.x) / 2;
      const cpY1 = curr.y;
      const cpX2 = curr.x + (next.x - curr.x) / 2;
      const cpY2 = next.y;
      pathD += ` C ${cpX1} ${cpY1}, ${cpX2} ${cpY2}, ${next.x} ${next.y}`;
    }
  }

  // Area path below line
  let areaD = "";
  if (coords.length > 0) {
    const lastCoord = coords[coords.length - 1];
    areaD = `${pathD} L ${lastCoord.x} ${padTop + chartH} L ${coords[0].x} ${padTop + chartH} Z`;
  }

  const latestCoord = coords.length > 0 ? coords[coords.length - 1] : null;

  const vsPrev = trendData.vsPreviousMonth;
  const vsAvg = trendData.vsSixMonthAverage;

  return (
    <div
      ref={ref}
      className="rounded-2xl border border-white/[0.08] bg-[#0d1322]/80 backdrop-blur-md p-6 shadow-sm flex flex-col justify-between"
    >
      <div>
        {/* Header */}
        <div className="flex items-start justify-between gap-4 mb-4">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-bold text-white tracking-tight">
                Exposure Trend
              </h2>
              <span className="p-1 rounded-full text-slate-400 hover:text-white transition-colors" title="Monthly historical exposure measures actual realized recurring debits observed in that specific calendar month divided by that month's income. In contrast, Headline Exposure reflects your complete forward-looking commitment portfolio against average financial capacity.">
                <Info size={15} />
              </span>
            </div>
            <p className="mt-1 text-xs text-slate-400">
              Realized monthly recurring debits vs. income over time
            </p>
          </div>
          <div className="flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs font-medium text-slate-300">
            <span>{trendData.timeframeLabel}</span>
            <ChevronDown size={14} className="text-slate-400" />
          </div>
        </div>

        {/* Chart Area */}
        {hasData ? (
          <div className="w-full relative pt-2">
            <svg
              viewBox={`0 0 ${svgWidth} ${svgHeight}`}
              className="w-full h-48 overflow-visible"
            >
              <defs>
                <linearGradient id="trendAreaGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                  <stop offset="0%" stopColor="#818CF8" stopOpacity="0.35" />
                  <stop offset="100%" stopColor="#818CF8" stopOpacity="0.0" />
                </linearGradient>
                <linearGradient id="trendLineGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#818CF8" />
                  <stop offset="50%" stopColor="#A78BFA" />
                  <stop offset="100%" stopColor="#C084FC" />
                </linearGradient>
              </defs>

              {/* Y Grid lines and labels */}
              {yTicks.map((val) => {
                const y = padTop + chartH - (val / maxVal) * chartH;
                return (
                  <g key={val}>
                    <line
                      x1={padLeft}
                      y1={y}
                      x2={padLeft + chartW}
                      y2={y}
                      stroke="rgba(255, 255, 255, 0.05)"
                      strokeDasharray="2 3"
                    />
                    <text
                      x={padLeft - 8}
                      y={y + 3.5}
                      textAnchor="end"
                      fill="#64748B"
                      fontSize="10"
                      className="font-mono"
                    >
                      {val}%
                    </text>
                  </g>
                );
              })}

              {/* Area gradient fill */}
              {areaD && (
                <path d={areaD} fill="url(#trendAreaGradient)" />
              )}

              {/* Dotted vertical guide line for latest point */}
              {latestCoord && (
                <line
                  x1={latestCoord.x}
                  y1={latestCoord.y}
                  x2={latestCoord.x}
                  y2={padTop + chartH}
                  stroke="#818CF8"
                  strokeDasharray="3 3"
                  opacity="0.75"
                />
              )}

              {/* Main curve */}
              {pathD && (
                <motion.path
                  d={pathD}
                  fill="none"
                  stroke="url(#trendLineGradient)"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  initial={reduce ? undefined : { pathLength: 0 }}
                  animate={inView ? { pathLength: 1 } : {}}
                  transition={{ duration: 1.1, ease: EASE }}
                />
              )}

              {/* Points circles with hover */}
              {coords.map((c, i) => {
                const isLatest = i === coords.length - 1;
                const isHovered = hoveredPoint === i;
                return (
                  <g key={c.month}>
                    <circle
                      cx={c.x}
                      cy={c.y}
                      r={isLatest ? 5.5 : isHovered ? 4.5 : 3}
                      fill={isLatest || isHovered ? "#FFFFFF" : "#818CF8"}
                      stroke={isLatest ? "#8B5CF6" : isHovered ? "#C084FC" : "none"}
                      strokeWidth={isLatest || isHovered ? 3 : 0}
                      className={isLatest ? "drop-shadow-[0_0_8px_rgba(139,92,246,0.8)] cursor-pointer" : "cursor-pointer"}
                      onMouseEnter={() => setHoveredPoint(i)}
                      onMouseLeave={() => setHoveredPoint(null)}
                    />
                    {isHovered && !isLatest && (
                      <g transform={`translate(${c.x}, ${c.y - 22})`}>
                        <rect
                          x="-22"
                          y="-8"
                          width="44"
                          height="16"
                          rx="8"
                          fill="#1E293B"
                          stroke="#818CF8"
                          strokeWidth="1"
                        />
                        <text
                          x="0"
                          y="3"
                          textAnchor="middle"
                          fill="#FFFFFF"
                          fontSize="9"
                          fontWeight="bold"
                          className="font-mono"
                        >
                          {c.exposure.toFixed(1)}%
                        </text>
                      </g>
                    )}
                  </g>
                );
              })}

              {/* Floating Badge above latest point */}
              {latestCoord && (
                <g transform={`translate(${latestCoord.x}, ${latestCoord.y - 28})`}>
                  <rect
                    x="-24"
                    y="-9"
                    width="48"
                    height="18"
                    rx="9"
                    fill="#6366F1"
                    className="shadow-lg drop-shadow-[0_2px_8px_rgba(99,102,241,0.5)]"
                  />
                  <text
                    x="0"
                    y="3.5"
                    textAnchor="middle"
                    fill="#FFFFFF"
                    fontSize="10"
                    fontWeight="bold"
                    className="font-mono"
                  >
                    {latestCoord.exposure.toFixed(2)}%
                  </text>
                </g>
              )}

              {/* X Axis Month Labels */}
              {coords.map((c) => (
                <text
                  key={c.month}
                  x={c.x}
                  y={padTop + chartH + 16}
                  textAnchor="middle"
                  fill="#94A3B8"
                  fontSize="10"
                  className="font-medium"
                >
                  {c.label}
                </text>
              ))}
            </svg>
          </div>
        ) : (
          <div className="h-48 rounded-xl border border-white/[0.06] bg-white/[0.02] flex flex-col items-center justify-center p-6 text-center">
            <BarChart2 size={28} className="text-slate-400 mb-2" />
            <p className="text-sm font-semibold text-white">Historical exposure trend unavailable</p>
            <p className="mt-1 text-xs text-slate-400 max-w-sm">
              More transaction history is required to display your monthly exposure trend.
            </p>
          </div>
        )}

        {/* Bottom 2 Stat Cards */}
        {hasData && (
          <div className="grid grid-cols-2 gap-3 mt-4 pt-3 border-t border-white/[0.06]">
            {/* Stat 1: vs. previous month */}
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3 flex items-center gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white/[0.04] border border-white/[0.08] text-indigo-400">
                {vsPrev !== null && vsPrev < 0 ? (
                  <TrendingDown size={18} className="text-emerald-400" />
                ) : (
                  <TrendingUp size={18} className="text-indigo-400" />
                )}
              </div>
              <div className="min-w-0">
                <p className="font-mono text-base font-bold text-white tracking-tight leading-tight">
                  {vsPrev !== null ? `${vsPrev >= 0 ? "+" : ""}${vsPrev.toFixed(2)}%` : "—"}
                </p>
                <p className="text-[11px] text-slate-400 truncate mt-0.5">vs. previous month</p>
              </div>
            </div>

            {/* Stat 2: vs. 6-month average */}
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3 flex items-center gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white/[0.04] border border-white/[0.08] text-purple-400">
                <BarChart2 size={18} />
              </div>
              <div className="min-w-0">
                <p className="font-mono text-base font-bold text-white tracking-tight leading-tight">
                  {vsAvg !== null ? `${vsAvg >= 0 ? "+" : ""}${vsAvg.toFixed(1)}%` : "—"}
                </p>
                <p className="text-[11px] text-slate-400 truncate mt-0.5">vs. 6-month average</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Loading Skeleton State
// ─────────────────────────────────────────────────────────────
function LoadingState() {
  return (
    <div className="w-full max-w-[1520px] mx-auto px-5 sm:px-8 lg:px-10 xl:px-12 py-8 space-y-8 animate-pulse select-none">
      <div className="space-y-3">
        <div className="h-4 w-32 rounded-md bg-white/[0.08]" />
        <div className="h-10 w-96 max-w-full rounded-xl bg-white/[0.12]" />
        <div className="h-4 w-[460px] max-w-full rounded-md bg-white/[0.08]" />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <div className="h-32 rounded-2xl bg-white/[0.05] border border-white/[0.08]" />
        <div className="h-32 rounded-2xl bg-white/[0.05] border border-white/[0.08]" />
        <div className="h-32 rounded-2xl bg-white/[0.05] border border-white/[0.08]" />
        <div className="h-32 rounded-2xl bg-white/[0.05] border border-white/[0.08]" />
      </div>

      <div className="h-24 rounded-2xl bg-white/[0.05] border border-white/[0.08]" />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="h-80 rounded-2xl bg-white/[0.05] border border-white/[0.08]" />
        <div className="h-80 rounded-2xl bg-white/[0.05] border border-white/[0.08]" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="h-64 rounded-2xl bg-white/[0.05] border border-white/[0.08]" />
        <div className="h-64 rounded-2xl bg-white/[0.05] border border-white/[0.08]" />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="h-28 rounded-2xl bg-white/[0.05] border border-white/[0.08]" />
        <div className="h-28 rounded-2xl bg-white/[0.05] border border-white/[0.08]" />
        <div className="h-28 rounded-2xl bg-white/[0.05] border border-white/[0.08]" />
        <div className="h-28 rounded-2xl bg-white/[0.05] border border-white/[0.08]" />
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Error State
// ─────────────────────────────────────────────────────────────
function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="min-h-[70vh] flex items-center justify-center px-6">
      <div className="max-w-md text-center p-8 rounded-3xl border border-white/10 bg-[#0d1322]/80 backdrop-blur-md shadow-2xl">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-rose-500/10 text-rose-400 border border-rose-500/20">
          <AlertTriangle size={22} />
        </div>
        <h2 className="mt-5 text-xl font-bold text-white">Dashboard unavailable</h2>
        <p className="mt-2 text-sm leading-relaxed text-slate-400">{message}</p>
        <button
          onClick={onRetry}
          className="mt-6 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/[0.06] hover:bg-white/[0.12] px-5 py-2.5 text-sm font-medium text-white transition-all shadow-sm"
        >
          <RefreshCw size={14} />
          Try again
        </button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Onboarding State
// ─────────────────────────────────────────────────────────────
function OnboardingState({
  response,
  onUpload,
  onNavigate,
}: {
  response: DashboardOnboardingResponse;
  onUpload?: () => void;
  onNavigate: (page: AppPage) => void;
}) {
  const reduce = useReducedMotion();
  return (
    <div className="min-h-[70vh] flex items-center justify-center px-6">
      <motion.div
        className="max-w-md text-center p-8 rounded-3xl border border-white/10 bg-[#0d1322]/80 backdrop-blur-md shadow-2xl"
        initial={reduce ? undefined : { opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: EASE }}
      >
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-500/15 border border-indigo-500/25 text-indigo-400">
          <Upload size={24} />
        </div>
        <h2 className="mt-5 text-2xl font-bold text-white">
          Your dashboard is ready when you are
        </h2>
        <p className="mt-3 text-sm leading-relaxed text-slate-400">{response.message}</p>
        <button
          onClick={() => (onUpload ? onUpload() : onNavigate("settings"))}
          className="mt-7 inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 px-5 py-2.5 text-sm font-medium text-white transition-all shadow-lg shadow-indigo-600/30"
        >
          Upload transactions
          <ArrowRight size={14} />
        </button>
      </motion.div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Main Dashboard Page Component
// ─────────────────────────────────────────────────────────────
export function DashboardPage({
  onNavigate,
  onAskAssistant,
  user,
  onUnauthorized,
  onUpload,
}: DashboardPageProps) {
  const [response, setResponse] = useState<DashboardResponse | DashboardOnboardingResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [retryCount, setRetryCount] = useState(0);
  const [recIndex, setRecIndex] = useState(0);
  const [viewAllRecs, setViewAllRecs] = useState(false);
  const [alertsModalOpen, setAlertsModalOpen] = useState(false);
  const [isIncomeModalOpen, setIsIncomeModalOpen] = useState(false);
  const [history, setHistory] = useState<HistoricalDashboardResponse | null>(null);
  const [commitmentSnapshot, setCommitmentSnapshot] = useState<CommitmentSnapshotResponse | null>(null);
  const [forecast, setForecast] = useState<CashFlowForecastResponse | null>(null);

  useEffect(() => {
    const token = getStoredAccessToken();
    if (!token || !user.financial_user_id) {
      onUnauthorized();
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);

    Promise.allSettled([
      dashboardApi.get(user.financial_user_id, token),
      dashboardApi.history(token),
      commitmentApi.snapshot(token),
      forecastApi.cashFlow(user.financial_user_id, token),
    ]).then(([dashResult, histResult, commitResult, forecastResult]) => {
      if (cancelled) return;

      if (dashResult.status === "fulfilled") {
        setResponse(dashResult.value);
      } else {
        const err = dashResult.reason;
        if (err instanceof ApiError && err.status === 401) onUnauthorized();
        else setError(err instanceof ApiError ? err.message : "Unable to load your dashboard.");
      }

      if (histResult.status === "fulfilled") {
        setHistory(histResult.value);
      }
      if (commitResult.status === "fulfilled") {
        setCommitmentSnapshot(commitResult.value);
      }
      if (forecastResult.status === "fulfilled") {
        setForecast(forecastResult.value);
      }
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });

    return () => {
      cancelled = true;
    };
  }, [user.financial_user_id, onUnauthorized, retryCount]);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={() => setRetryCount((n) => n + 1)} />;
  if (!response) return null;
  if ("onboarding_required" in response)
    return <OnboardingState response={response} onUpload={onUpload} onNavigate={onNavigate} />;

  // ─────────────────────────────────────────────────────────────
  // SINGLE NORMALIZED SOURCE OF TRUTH FOR THIS DASHBOARD
  // ─────────────────────────────────────────────────────────────
  const snapshot: NormalizedDashboardSnapshot = normalizeDashboardSnapshot(
    response,
    history,
    commitmentSnapshot,
    forecast
  );

  const bandColor = exposureBandColor(snapshot.exposureBand);

  // Reporting period string
  const monthYearStr = history?.points?.length
    ? (() => {
        const first = history.points[0].month;
        const last = history.points[history.points.length - 1].month;
        const format = (value: string) =>
          new Date(`${value}-01T00:00:00`).toLocaleDateString("en-IN", {
            month: "short",
            year: "numeric",
          });
        return first === last ? format(first) : `${format(first)} – ${format(last)}`;
      })()
    : "Observed transaction history";

  const currentHour = new Date().getHours();
  const greeting = currentHour < 12 ? "Good morning," : currentHour < 17 ? "Good afternoon," : "Good evening,";

  const recommendations = snapshot.recommendations;
  const currentRec = recommendations[recIndex % Math.max(recommendations.length, 1)];

  return (
    <div className="w-full max-w-[1520px] mx-auto px-5 sm:px-8 lg:px-10 xl:px-12 py-7 sm:py-8 space-y-8 sm:space-y-9 pb-16">
      {/* ─────────────────────────────────────────────────────────────
          1. HERO FINANCIAL SUMMARY
      ───────────────────────────────────────────────────────────── */}
      <Reveal className="pt-1">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6 pb-2">
          {/* Left: Greeting & Overall Financial Status */}
          <div className="min-w-0 max-w-2xl">
            <p className="text-sm font-medium text-slate-400">{greeting}</p>
            <h1 className="mt-1 text-3xl sm:text-4xl lg:text-[42px] font-bold text-white tracking-tight leading-[1.15]">
              Your finances are rated{" "}
              <span className="bg-gradient-to-r from-purple-400 via-fuchsia-400 to-indigo-400 bg-clip-text text-transparent capitalize">
                {snapshot.financialHealthLabel.toLowerCase()}.
              </span>
            </h1>
            <p className="mt-2.5 text-sm sm:text-base text-slate-400 leading-relaxed">
              {snapshot.heroStatement}
            </p>

            {/* Badges / Quick Action */}
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <span
                className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium border"
                style={{
                  borderColor: `${bandColor}40`,
                  backgroundColor: `${bandColor}15`,
                  color: bandColor,
                }}
              >
                <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: bandColor }} />
                {snapshot.exposureBand} exposure
              </span>

              <button
                onClick={() => onAskAssistant("Explain my financial status and exposure")}
                className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-slate-900/80 hover:bg-slate-850 hover:border-indigo-500/40 px-3.5 py-1 text-xs font-medium text-slate-200 transition-all shadow-sm"
              >
                <MessageCircle size={13} className="text-indigo-400" />
                <span>Ask FinSight</span>
              </button>
            </div>
          </div>

          {/* Right: Decorative Wave + Slogan + Snapshot */}
          <div className="hidden lg:flex items-center gap-8 shrink-0">
            {/* Glowing Decorative Wave */}
            <div className="relative w-44 h-14" aria-hidden="true">
              <svg viewBox="0 0 176 56" fill="none" className="w-full h-full text-indigo-400/60 drop-shadow-[0_0_10px_rgba(129,140,248,0.3)]">
                <defs>
                  <linearGradient id="waveGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="#818CF8" />
                    <stop offset="50%" stopColor="#C084FC" />
                    <stop offset="100%" stopColor="#38BDF8" />
                  </linearGradient>
                </defs>
                <path
                  d="M2 38 C 40 46, 60 12, 100 18 S 140 38, 174 14"
                  stroke="url(#waveGradient)"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                />
                <circle cx="100" cy="18" r="4" fill="#C084FC" className="animate-pulse" />
              </svg>
            </div>

            {/* Slogan */}
            <div className="text-right border-r border-white/10 pr-6">
              <p className="font-serif italic text-xs leading-snug text-slate-400/80">
                Smarter<br />Money<br />Brighter<br />Tomorrow
              </p>
            </div>

            {/* Reporting Period */}
            <div className="text-right">
              <p className="text-sm font-semibold text-white tracking-tight">{monthYearStr}</p>
              <p className="text-[11px] text-slate-400 font-medium">Your financial snapshot</p>
            </div>
          </div>
        </div>
      </Reveal>

      {/* ─────────────────────────────────────────────────────────────
          2. KEY FINANCIAL METRIC CARDS (4 CARDS)
      ───────────────────────────────────────────────────────────── */}
      <Reveal delay={0.06}>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-5">
          {/* 1. Monthly Income */}
          <div className="rounded-2xl border border-white/[0.08] bg-[#0d1322]/80 backdrop-blur-md p-5 shadow-sm hover:border-white/15 hover:shadow-lg transition-all duration-200 flex items-start gap-3.5">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20">
              <Wallet size={20} />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-1">
                <span className="text-xs font-medium text-slate-400 truncate">Monthly Income</span>
                <div className="flex items-center gap-1.5 shrink-0">
                  <span
                    className={`px-1.5 py-0.5 rounded-full text-[10px] font-mono font-medium shrink-0 border ${
                      snapshot.incomeSource === "Manual"
                        ? "bg-purple-500/15 text-purple-400 border-purple-500/25"
                        : snapshot.incomeSource === "Estimated"
                        ? "bg-amber-500/15 text-amber-400 border-amber-500/25"
                        : "bg-emerald-500/15 text-emerald-400 border-emerald-500/25"
                    }`}
                  >
                    {snapshot.incomeSource || "Observed"}
                  </span>
                  <button
                    type="button"
                    onClick={() => setIsIncomeModalOpen(true)}
                    className="p-1 rounded-md text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
                    title="Edit Income Configuration"
                    aria-label="Edit Income Configuration"
                  >
                    <Edit2 size={12} />
                  </button>
                </div>
              </div>
              <p className="mt-1 text-2xl font-bold text-white font-mono tracking-tight">
                <AnimatedNumber
                  value={Math.round(snapshot.monthlyIncome)}
                  startOn={true}
                  format={moneyAnimated}
                />
              </p>
              <div className="flex items-center justify-between mt-1 gap-1">
                <p
                  className="text-[11px] text-slate-400/90 truncate cursor-help"
                  title="Observed historical average monthly inflows across ledger (distinct from forward-looking Model 1 forecast)"
                >
                  {snapshot.incomeSource === "Manual"
                    ? "Configured salary"
                    : "Avg. monthly income"}
                </p>
                <button
                  type="button"
                  onClick={() => setIsIncomeModalOpen(true)}
                  className="text-[10px] text-blue-400 hover:text-blue-300 font-medium shrink-0 transition-colors hover:underline"
                >
                  Configure
                </button>
              </div>
            </div>
          </div>

          {/* 2. Recurring Commitments */}
          <div className="rounded-2xl border border-white/[0.08] bg-[#0d1322]/80 backdrop-blur-md p-5 shadow-sm hover:border-white/15 hover:shadow-lg transition-all duration-200 flex items-start gap-3.5">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-purple-500/10 text-purple-400 border border-purple-500/20">
              <ArrowUpRight size={21} />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-1">
                <span className="text-xs font-medium text-slate-400 truncate">Recurring Commitments</span>
                <span className="bg-purple-500/15 text-purple-400 border border-purple-500/25 px-1.5 py-0.5 rounded-full text-[10px] font-mono font-medium shrink-0">
                  {snapshot.exposurePercent.toFixed(2)}%
                </span>
              </div>
              <p className="mt-1 text-2xl font-bold text-white font-mono tracking-tight">
                <AnimatedNumber
                  value={Math.round(snapshot.recurringCommitments)}
                  startOn={true}
                  format={moneyAnimated}
                />
              </p>
              <p className="mt-1 text-[11px] text-slate-400/90 truncate">
                {snapshot.exposurePercent.toFixed(2)}% of capacity committed
              </p>
            </div>
          </div>

          {/* 3. Variable Expenses (Model 1 Forecast) */}
          <div className="rounded-2xl border border-white/[0.08] bg-[#0d1322]/80 backdrop-blur-md p-5 shadow-sm hover:border-white/15 hover:shadow-lg transition-all duration-200 flex items-start gap-3.5">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20">
              <CreditCard size={20} />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-1">
                <span className="text-xs font-medium text-slate-400 truncate">Variable Expenses</span>
                <span className="bg-amber-500/15 text-amber-400 border border-amber-500/25 px-1.5 py-0.5 rounded-full text-[10px] font-mono font-medium shrink-0">
                  {snapshot.variableExpenses !== null ? `${snapshot.variableExpensesPct}%` : "Unavailable"}
                </span>
              </div>
              {snapshot.variableExpenses !== null ? (
                <p className="mt-1 text-2xl font-bold text-white font-mono tracking-tight">
                  <AnimatedNumber
                    value={Math.round(snapshot.variableExpenses)}
                    startOn={true}
                    format={moneyAnimated}
                  />
                </p>
              ) : (
                <p className="mt-1 text-base font-semibold text-slate-400 font-sans tracking-tight">
                  Not available
                </p>
              )}
              <p className="mt-1 text-[11px] text-slate-400/90 truncate">
                Forecasted monthly spending
              </p>
            </div>
          </div>

          {/* 4. Available Balance (Authoritative: Income - Commitments - Variable) */}
          <div className="rounded-2xl border border-white/[0.08] bg-[#0d1322]/80 backdrop-blur-md p-5 shadow-sm hover:border-white/15 hover:shadow-lg transition-all duration-200 flex items-start gap-3.5">
            <div
              className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border ${
                snapshot.isShortfall
                  ? "bg-rose-500/10 text-rose-400 border-rose-500/20"
                  : "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
              }`}
            >
              <Landmark size={20} />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-1">
                <span className="text-xs font-medium text-slate-400 truncate">Available Balance</span>
                <span
                  className={`px-1.5 py-0.5 rounded-full text-[10px] font-mono font-medium shrink-0 border ${
                    snapshot.isShortfall
                      ? "bg-rose-500/15 text-rose-400 border-rose-500/25"
                      : "bg-emerald-500/15 text-emerald-400 border-emerald-500/25"
                  }`}
                >
                  {snapshot.isShortfall ? "Shortfall" : `${Math.round((snapshot.availableBalance / snapshot.monthlyIncome) * 100)}%`}
                </span>
              </div>
              <p
                className={`mt-1 text-2xl font-bold font-mono tracking-tight ${
                  snapshot.isShortfall ? "text-rose-400" : "text-white"
                }`}
              >
                <AnimatedNumber
                  value={Math.round(snapshot.availableBalance)}
                  startOn={true}
                  format={moneyAnimated}
                />
              </p>
              <p className="mt-1 text-[11px] text-slate-400/90 truncate">
                {snapshot.isShortfall ? "Projected monthly deficit" : "Free to use this month"}
              </p>
            </div>
          </div>
        </div>
      </Reveal>

      {/* ─────────────────────────────────────────────────────────────
          3. UPCOMING ALERTS BANNER
      ───────────────────────────────────────────────────────────── */}
      <Reveal delay={0.1}>
        <div className="rounded-2xl border border-white/[0.08] bg-[#0d1322]/80 backdrop-blur-md p-4 sm:p-5 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3 shrink-0">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400">
              <Bell size={18} />
            </div>
            <div>
              <p className="text-sm font-semibold text-white leading-tight">
                {snapshot.upcomingAlerts.length} upcoming alerts
              </p>
              <p className="text-xs text-slate-400 leading-tight mt-0.5">
                Stay ahead of your payments and trial conversions.
              </p>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 flex-1 max-w-3xl">
            {snapshot.upcomingAlerts.map((alert) => (
              <div
                key={alert.id}
                className="flex-1 rounded-xl bg-white/[0.03] border border-white/[0.06] p-3 flex items-center gap-3 transition-colors hover:bg-white/[0.06]"
              >
                <div className="h-8 w-8 rounded-lg flex items-center justify-center shrink-0 bg-slate-800 border border-white/10">
                  {alert.iconType === "netflix" ? (
                    <span className="font-bold text-xs text-rose-500">N</span>
                  ) : alert.iconType === "insurance" ? (
                    <Shield size={16} className="text-blue-400" />
                  ) : (
                    <Calendar size={16} className="text-indigo-400" />
                  )}
                </div>

                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <p className="text-xs font-semibold text-white truncate leading-tight">
                      {alert.title}
                    </p>
                    <span
                      className={`text-[9.5px] font-mono px-1.5 py-0.2 rounded-full border shrink-0 ${
                        alert.badgeTone === "danger"
                          ? "bg-rose-500/15 border-rose-500/25 text-rose-400"
                          : alert.badgeTone === "warning"
                          ? "bg-amber-500/15 border-amber-500/25 text-amber-400"
                          : "bg-blue-500/15 border-blue-500/25 text-blue-400"
                      }`}
                    >
                      {alert.badgeText}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400 truncate mt-0.5 leading-tight">
                    {alert.description}
                  </p>
                </div>
              </div>
            ))}
          </div>

          <button
            onClick={() => setAlertsModalOpen(true)}
            className="text-xs font-semibold text-indigo-400 hover:text-indigo-300 flex items-center gap-1.5 shrink-0 transition-colors self-end md:self-center"
          >
            <span>View all alerts</span>
            <ArrowRight size={13} />
          </button>
        </div>
      </Reveal>

      {/* ─────────────────────────────────────────────────────────────
          4. NEW 2-COLUMN SECTION: FINANCIAL EXPOSURE & EXPOSURE TREND
             (From Reference Image media_1791470503377.png)
      ───────────────────────────────────────────────────────────── */}
      <Reveal delay={0.14}>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 sm:gap-6">
          {/* Left: Financial Exposure Card */}
          <FinancialExposureCard
            exposureScore={snapshot.exposurePercent}
            exposureBand={snapshot.exposureBand}
            commitments={snapshot.recurringCommitments}
            remainingCapacity={snapshot.remainingCapacity}
            monthlyCapacity={snapshot.monthlyIncome}
          />

          {/* Right: Exposure Trend Card */}
          <ExposureTrendCard trendData={snapshot.exposureTrend} />
        </div>
      </Reveal>

      {/* ─────────────────────────────────────────────────────────────
          5. MIDDLE SECTION: FINANCIAL HEALTH & COMMITMENT MIX
      ───────────────────────────────────────────────────────────── */}
      <Reveal delay={0.18}>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 sm:gap-6">
          {/* Card 1: Financial Health */}
          <div className="rounded-2xl border border-white/[0.08] bg-[#0d1322]/80 backdrop-blur-md p-6 shadow-sm hover:border-white/15 transition-all flex flex-col justify-between">
            <div>
              <div className="flex items-start justify-between gap-4 mb-5">
                <div>
                  <h2 className="text-xl font-bold text-white tracking-tight">
                    Financial Health
                  </h2>
                  <p className="mt-1 text-xs text-slate-400">
                    Comprehensive 6-factor assessment of your financial resilience
                  </p>
                </div>
                <BarChart2 size={16} className="text-slate-400 shrink-0 mt-0.5" />
              </div>

              <div className="pt-2">
                <HealthRadialGauge
                  score={snapshot.financialHealthScore}
                  label={snapshot.financialHealthLabel}
                  exposureScore={snapshot.exposurePercent}
                  riskLevel={snapshot.riskLevel}
                />
              </div>
            </div>
          </div>

          {/* Card 2: Monthly Commitment Mix */}
          <div className="rounded-2xl border border-white/[0.08] bg-[#0d1322]/80 backdrop-blur-md p-6 shadow-sm hover:border-white/15 transition-all flex flex-col justify-between">
            <div>
              <div className="flex items-start justify-between gap-4 mb-5">
                <div>
                  <h2 className="text-xl font-bold text-white tracking-tight">
                    Monthly Commitment Mix
                  </h2>
                  <p className="mt-1 text-xs text-slate-400">
                    {snapshot.commitmentMix.total > 0
                      ? `Where your ${money(snapshot.commitmentMix.total)} goes each month`
                      : "No recurring financial obligations detected"}
                  </p>
                </div>
                <PieChart size={16} className="text-slate-400 shrink-0 mt-0.5" />
              </div>

              <div className="pt-2">
                <CommitmentMixDonut
                  categories={snapshot.commitmentMix.categories}
                  total={snapshot.commitmentMix.total}
                />
              </div>
            </div>
          </div>
        </div>
      </Reveal>

      {/* ─────────────────────────────────────────────────────────────
          6. WHAT NEEDS YOUR ATTENTION
      ───────────────────────────────────────────────────────────── */}
      <Reveal delay={0.22}>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-white tracking-tight">
                What needs your attention
              </h2>
              <p className="mt-1 text-xs text-slate-400">
                Key actionable insights from your financial data
              </p>
            </div>
            <button
              onClick={() => onNavigate("commitments")}
              className="text-xs font-semibold text-indigo-400 hover:text-indigo-300 flex items-center gap-1.5 transition-colors"
            >
              <span>View all ({snapshot.attentionInsights.length})</span>
              <ArrowRight size={13} />
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {snapshot.attentionInsights.map((item) => (
              <div
                key={item.id}
                onClick={() => {
                  if (item.actionTarget) onNavigate(item.actionTarget);
                  else if (item.assistantPrompt) onAskAssistant(item.assistantPrompt);
                }}
                className="rounded-2xl border border-white/[0.08] bg-[#0d1322]/80 backdrop-blur-md p-4 shadow-sm hover:border-white/20 hover:shadow-md transition-all cursor-pointer group flex items-start gap-3.5"
              >
                <div
                  className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border ${
                    item.tone === "amber"
                      ? "bg-amber-500/10 border-amber-500/25 text-amber-400"
                      : item.tone === "purple"
                      ? "bg-purple-500/10 border-purple-500/25 text-purple-400"
                      : item.tone === "cyan"
                      ? "bg-cyan-500/10 border-cyan-500/25 text-cyan-400"
                      : "bg-rose-500/10 border-rose-500/25 text-rose-400"
                  }`}
                >
                  {item.category === "subscriptions" ? (
                    <RefreshCw size={17} />
                  ) : item.category === "usage" ? (
                    <BarChart2 size={17} />
                  ) : item.category === "savings" ? (
                    <Sparkles size={17} />
                  ) : (
                    <AlertTriangle size={17} />
                  )}
                </div>

                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-1">
                    <p className="text-xs font-semibold text-white group-hover:text-indigo-300 transition-colors truncate">
                      {item.title}
                    </p>
                    <ArrowRight
                      size={13}
                      className="text-slate-400 group-hover:text-white group-hover:translate-x-0.5 transition-all shrink-0"
                    />
                  </div>
                  <p className="mt-1 text-[11px] text-slate-400 leading-relaxed line-clamp-2">
                    {item.description}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </Reveal>

      {/* ─────────────────────────────────────────────────────────────
          7. FINANCIAL RECOMMENDATIONS (FINSIGHT RECOMMENDS)
      ───────────────────────────────────────────────────────────── */}
      {recommendations.length > 0 && (
        <Reveal delay={0.26}>
          <div className="rounded-2xl border border-white/[0.08] bg-[#0d1322]/80 backdrop-blur-md p-6 shadow-sm">
            <div className="flex items-start justify-between gap-4 mb-4">
              <div>
                <h2 className="text-lg font-bold text-white tracking-tight">
                  FinSight recommends
                </h2>
                <p className="mt-1 text-xs text-slate-400">
                  Personalised actions to strengthen your financial resilience
                </p>
              </div>

              <button
                onClick={() => setViewAllRecs(!viewAllRecs)}
                className="text-xs font-semibold text-indigo-400 hover:text-indigo-300 transition-colors shrink-0 flex items-center gap-1.5"
              >
                {viewAllRecs ? (
                  <>
                    <X size={13} />
                    <span>Collapse</span>
                  </>
                ) : (
                  <>
                    <span>View all ({recommendations.length})</span>
                    <ArrowRight size={12} />
                  </>
                )}
              </button>
            </div>

            {viewAllRecs ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 pt-2">
                {recommendations.map((rec, idx) => {
                  const action = recommendationAction(rec.recommendation_type);
                  return (
                    <div
                      key={`${rec.recommendation_type}-${idx}`}
                      className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4 flex flex-col justify-between hover:border-white/15 transition-all"
                    >
                      <div>
                        <div className="flex items-center justify-between gap-2 mb-2">
                          <span className="rounded-full bg-indigo-500/10 px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider font-semibold text-indigo-400 border border-indigo-500/20">
                            {rec.recommendation_type}
                          </span>
                          {rec.priority && (
                            <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400">
                              {rec.priority} priority
                            </span>
                          )}
                        </div>
                        <p className="text-sm font-semibold text-white leading-snug">
                          {rec.message}
                        </p>
                        <p className="mt-1.5 text-xs text-slate-400 leading-relaxed line-clamp-3">
                          {rec.reason}
                        </p>
                      </div>

                      <div className="mt-4 pt-3 border-t border-white/[0.08] flex items-center justify-between gap-2">
                        {rec.estimated_monthly_saving !== null && rec.estimated_monthly_saving > 0 ? (
                          <span className="font-mono text-xs font-semibold text-emerald-400">
                            ≈ {money(rec.estimated_monthly_saving)} / mo
                          </span>
                        ) : (
                          <span />
                        )}
                        <button
                          onClick={() => (action.nav ? onNavigate(action.nav) : onAskAssistant(action.ask))}
                          className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-400 hover:text-indigo-300 transition-colors"
                        >
                          <span>{action.label}</span>
                          <ArrowRight size={12} />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : currentRec ? (
              <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4 sm:p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="rounded-full bg-indigo-500/10 px-2.5 py-0.5 text-[10px] font-mono uppercase tracking-wider font-semibold text-indigo-400 border border-indigo-500/20">
                      {currentRec.recommendation_type}
                    </span>
                    {currentRec.priority && (
                      <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400">
                        {currentRec.priority} priority
                      </span>
                    )}
                    {currentRec.estimated_monthly_saving !== null && currentRec.estimated_monthly_saving > 0 && (
                      <span className="font-mono text-xs font-semibold text-emerald-400 ml-2">
                        ≈ {money(currentRec.estimated_monthly_saving)} / mo savings
                      </span>
                    )}
                  </div>
                  <p className="text-base font-semibold text-white leading-snug">
                    {currentRec.message}
                  </p>
                  <p className="mt-1 text-xs text-slate-400 leading-relaxed max-w-3xl">
                    {currentRec.reason}
                  </p>
                </div>

                <div className="flex items-center gap-3 shrink-0">
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => setRecIndex((i) => (i - 1 + recommendations.length) % recommendations.length)}
                      aria-label="Previous recommendation"
                      disabled={recommendations.length <= 1}
                      className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/[0.08] disabled:opacity-30 disabled:pointer-events-none transition-colors"
                    >
                      <ChevronLeft size={16} />
                    </button>
                    <button
                      onClick={() => setRecIndex((i) => (i + 1) % recommendations.length)}
                      aria-label="Next recommendation"
                      disabled={recommendations.length <= 1}
                      className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/[0.08] disabled:opacity-30 disabled:pointer-events-none transition-colors"
                    >
                      <ChevronRight size={16} />
                    </button>
                  </div>

                  {(() => {
                    const action = recommendationAction(currentRec.recommendation_type);
                    return (
                      <button
                        onClick={() => (action.nav ? onNavigate(action.nav) : onAskAssistant(action.ask))}
                        className="inline-flex items-center gap-1.5 rounded-full bg-indigo-600 hover:bg-indigo-500 px-4 py-2 text-xs font-semibold text-white transition-all shadow-md shadow-indigo-600/30"
                      >
                        <span>{action.label}</span>
                        <ArrowRight size={13} />
                      </button>
                    );
                  })()}
                </div>
              </div>
            ) : null}
          </div>
        </Reveal>
      )}

      {/* ─────────────────────────────────────────────────────────────
          8. MODAL: ALL ALERTS
      ───────────────────────────────────────────────────────────── */}
      <AnimatePresence>
        {alertsModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ duration: 0.2 }}
              className="w-full max-w-lg rounded-2xl sm:rounded-3xl border border-white/10 bg-[#0d1322] p-4 sm:p-6 shadow-2xl relative max-h-[90vh] flex flex-col"
            >
              <div className="flex items-center justify-between pb-4 border-b border-white/[0.08]">
                <div className="flex items-center gap-2.5">
                  <Bell size={18} className="text-rose-400" />
                  <h3 className="text-base font-bold text-white">Upcoming Alerts & Commitments</h3>
                </div>
                <button
                  onClick={() => setAlertsModalOpen(false)}
                  className="p-1.5 rounded-xl text-slate-400 hover:text-white hover:bg-white/[0.08] transition-colors"
                  aria-label="Close alerts dialog"
                >
                  <X size={16} />
                </button>
              </div>

              <div className="py-4 space-y-3 max-h-[60vh] overflow-y-auto flex-1 min-h-0">
                {snapshot.upcomingAlerts.map((alert) => (
                  <div
                    key={alert.id}
                    className="p-3.5 rounded-2xl bg-white/[0.03] border border-white/[0.06] flex items-center justify-between gap-3"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-semibold text-white">{alert.title}</p>
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-rose-500/15 border border-rose-500/25 text-rose-400">
                          {alert.badgeText}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-slate-400">{alert.description}</p>
                    </div>
                    {alert.amount && (
                      <span className="font-mono text-sm font-bold text-white shrink-0">
                        {money(alert.amount)}
                      </span>
                    )}
                  </div>
                ))}
              </div>

              <div className="pt-3 border-t border-white/[0.08] flex items-center justify-end">
                <button
                  onClick={() => {
                    setAlertsModalOpen(false);
                    onNavigate("commitments");
                  }}
                  className="inline-flex items-center gap-1.5 rounded-full bg-indigo-600 hover:bg-indigo-500 px-4 py-2 text-xs font-semibold text-white transition-all shadow-md shadow-indigo-600/30"
                >
                  <span>Manage Recurring Payments</span>
                  <ArrowRight size={13} />
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Edit Income Configuration Modal */}
      <EditIncomeModal
        isOpen={isIncomeModalOpen}
        onClose={() => setIsIncomeModalOpen(false)}
        onSuccess={() => {
          setRetryCount((prev) => prev + 1);
        }}
        currentIncome={snapshot.monthlyIncome}
        currentMode={snapshot.incomeMode}
        currentSource={snapshot.incomeSource}
        manualIncomeValue={snapshot.manualMonthlyIncome}
        expectedIncomeValue={snapshot.expectedMonthlyIncome}
        token={getStoredAccessToken() || ""}
      />
    </div>
  );
}
