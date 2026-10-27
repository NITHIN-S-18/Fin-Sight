import React from "react";
import {
  Car,
  Clapperboard,
  Coffee,
  CreditCard,
  Film,
  Fuel,
  Heart,
  Landmark,
  Laptop,
  Layers,
  ShoppingBag,
  ShoppingCart,
  Tv,
  Utensils,
  Wallet,
  Zap,
} from "lucide-react";
import { motion, useReducedMotion } from "motion/react";

export function CategoryBadge({
  category,
  className = "",
}: {
  category: string;
  className?: string;
}) {
  const cat = (category || "General").toLowerCase().trim();

  let Icon = Layers;
  let style = "bg-slate-500/10 text-slate-300 border-slate-500/20";

  if (cat.includes("transport") || cat.includes("fuel") || cat.includes("cab") || cat.includes("travel")) {
    Icon = Car;
    style = "bg-sky-500/10 text-sky-400 border-sky-500/20";
  } else if (cat.includes("entertain") || cat.includes("movie") || cat.includes("ott")) {
    Icon = Clapperboard;
    style = "bg-purple-500/10 text-purple-400 border-purple-500/20";
  } else if (cat.includes("grocer") || cat.includes("market")) {
    Icon = ShoppingCart;
    style = "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
  } else if (cat.includes("food") || cat.includes("dining") || cat.includes("restaurant") || cat.includes("beverage")) {
    Icon = Utensils;
    style = "bg-amber-500/10 text-amber-400 border-amber-500/20";
  } else if (cat.includes("shop") || cat.includes("cloth") || cat.includes("apparel") || cat.includes("retail")) {
    Icon = ShoppingBag;
    style = "bg-fuchsia-500/10 text-fuchsia-400 border-fuchsia-500/20";
  } else if (cat.includes("income") || cat.includes("salary")) {
    Icon = Landmark;
    style = "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
  } else if (cat.includes("software") || cat.includes("cloud") || cat.includes("tech") || cat.includes("saas")) {
    Icon = Laptop;
    style = "bg-indigo-500/10 text-indigo-400 border-indigo-500/20";
  } else if (cat.includes("finance") || cat.includes("loan") || cat.includes("emi") || cat.includes("bank") || cat.includes("card")) {
    Icon = CreditCard;
    style = "bg-teal-500/10 text-teal-400 border-teal-500/20";
  } else if (cat.includes("util") || cat.includes("bill") || cat.includes("power")) {
    Icon = Zap;
    style = "bg-cyan-500/10 text-cyan-400 border-cyan-500/20";
  } else if (cat.includes("health") || cat.includes("med")) {
    Icon = Heart;
    style = "bg-rose-500/10 text-rose-400 border-rose-500/20";
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium border ${style} ${className}`}
    >
      <Icon size={12} className="shrink-0" />
      <span className="truncate">{category || "Uncategorized"}</span>
    </span>
  );
}

export function TypeBadge({
  type,
  className = "",
}: {
  type: string;
  className?: string;
}) {
  const t = (type || "").toLowerCase().trim();

  let style = "bg-blue-500/10 text-blue-400 border-blue-500/20";
  let label = type || "Purchase";

  if (t === "income") {
    style = "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
    label = "Income";
  } else if (t === "emi") {
    style = "bg-indigo-500/10 text-indigo-400 border-indigo-500/20";
    label = "EMI";
  } else if (t === "bnpl") {
    style = "bg-amber-500/10 text-amber-400 border-amber-500/20";
    label = "BNPL";
  } else if (t === "subscription") {
    style = "bg-purple-500/10 text-purple-400 border-purple-500/20";
    label = "Subscription";
  } else if (t === "expense" || t === "purchase") {
    style = "bg-blue-500/10 text-blue-400 border-blue-500/20";
    label = "Purchase";
  }

  return (
    <span
      className={`inline-flex items-center justify-center px-2.5 py-0.5 rounded-md text-xs font-medium border ${style} ${className}`}
    >
      {label}
    </span>
  );
}

export function MiniSparkline({
  color,
  trend = "up",
  className = "",
}: {
  color: "rose" | "emerald" | "purple" | "amber" | "blue";
  trend?: "up" | "down" | "flat";
  className?: string;
}) {
  const reduceMotion = useReducedMotion();

  const colorHex = {
    rose: "#f43f5e",
    emerald: "#10b981",
    purple: "#a855f7",
    amber: "#f59e0b",
    blue: "#3b82f6",
  }[color];

  // SVG wave paths matching the screenshots
  const paths = {
    rose: "M 4 20 Q 20 28, 36 14 T 68 8 T 96 16",
    emerald: "M 4 22 Q 22 28, 42 12 T 72 16 T 96 6",
    purple: "M 4 24 Q 24 10, 48 22 T 76 6 T 96 14",
    amber: "M 4 18 Q 24 8, 46 20 T 74 12 T 96 10",
    blue: "M 4 22 Q 26 12, 50 20 T 78 8 T 96 12",
  };

  const d = paths[color];

  return (
    <div className={`w-24 h-9 overflow-visible ${className}`} aria-hidden="true">
      <svg viewBox="0 0 100 32" className="w-full h-full overflow-visible">
        <defs>
          <filter id={`glow-${color}`} x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="0" stdDeviation="2" floodColor={colorHex} floodOpacity="0.4" />
          </filter>
        </defs>
        <motion.path
          d={d}
          fill="none"
          stroke={colorHex}
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          filter={`url(#glow-${color})`}
          initial={reduceMotion ? undefined : { pathLength: 0, opacity: 0 }}
          animate={{ pathLength: 1, opacity: 1 }}
          transition={{ duration: 1.1, ease: [0.22, 1, 0.36, 1] }}
        />
      </svg>
    </div>
  );
}

export function MiniBarChart({ className = "" }: { className?: string }) {
  const reduceMotion = useReducedMotion();
  const heights = [35, 55, 75, 100]; // 4 ascending bars as seen in screenshot

  return (
    <div className={`flex items-end gap-1.5 h-8 px-1 ${className}`} aria-hidden="true">
      {heights.map((h, i) => (
        <motion.div
          key={i}
          className="w-1.5 rounded-full bg-emerald-400"
          style={{ height: `${h}%` }}
          initial={reduceMotion ? undefined : { scaleY: 0 }}
          animate={{ scaleY: 1 }}
          transition={{ duration: 0.5, delay: i * 0.1, ease: [0.22, 1, 0.36, 1] }}
        />
      ))}
    </div>
  );
}

export function ContributionRing({
  percentage,
  color,
  size = 48,
  stroke = 4,
}: {
  percentage: number;
  color: "blue" | "amber" | "purple" | "emerald";
  size?: number;
  stroke?: number;
}) {
  const reduceMotion = useReducedMotion();
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.min(Math.max(percentage, 0), 100);
  const offset = circumference * (1 - clamped / 100);

  const colorHex = {
    blue: "#38bdf8",
    amber: "#fbbf24",
    purple: "#c084fc",
    emerald: "#34d399",
  }[color];

  return (
    <div
      className="relative shrink-0 flex items-center justify-center select-none"
      style={{ width: size, height: size }}
      role="img"
      aria-label={`${Math.round(percentage)}%`}
    >
      <svg width={size} height={size} className="-rotate-90">
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
          stroke={colorHex}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={reduceMotion ? undefined : { strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1, ease: [0.22, 1, 0.36, 1] }}
        />
      </svg>
      <span className="absolute font-mono text-[11px] font-bold text-white tracking-tight">
        {Math.round(clamped)}%
      </span>
    </div>
  );
}
