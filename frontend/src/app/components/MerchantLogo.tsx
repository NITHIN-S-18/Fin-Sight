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
  Package,
  Play,
  Receipt,
  ShoppingBag,
  ShoppingCart,
  Tv,
  Utensils,
  Wallet,
  Zap,
} from "lucide-react";

interface MerchantLogoProps {
  name: string;
  category?: string | null;
  size?: "sm" | "md" | "lg";
  className?: string;
}

export function MerchantLogo({
  name,
  category,
  size = "md",
  className = "",
}: MerchantLogoProps) {
  const n = (name || "").toLowerCase().trim();
  const cat = (category || "").toLowerCase().trim();

  const sizeClasses = {
    sm: "w-7 h-7 text-xs rounded-lg",
    md: "w-9 h-9 text-xs rounded-xl",
    lg: "w-11 h-11 text-sm rounded-xl",
  }[size];

  const iconSizes = {
    sm: 13,
    md: 16,
    lg: 20,
  }[size];

  // Specific brand checks
  if (n.includes("bajaj")) {
    return (
      <div
        className={`${sizeClasses} bg-[#1d4ed8] text-white font-serif font-black flex items-center justify-center shrink-0 shadow-sm border border-blue-400/20 select-none ${className}`}
        title={name}
      >
        <span className="text-base leading-none">B</span>
      </div>
    );
  }

  if (n.includes("kreditbee") || n.includes("kredit bee")) {
    return (
      <div
        className={`${sizeClasses} bg-[#facc15] text-[#1e1b4b] font-mono font-black flex items-center justify-center shrink-0 shadow-sm border border-yellow-300/30 select-none ${className}`}
        title={name}
      >
        <svg
          viewBox="0 0 24 24"
          className="w-5 h-5 fill-current"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z" />
        </svg>
      </div>
    );
  }

  if (n.includes("sbi") || n.includes("state bank")) {
    return (
      <div
        className={`${sizeClasses} bg-[#0284c7] text-white flex items-center justify-center shrink-0 shadow-sm border border-sky-400/20 select-none ${className}`}
        title={name}
      >
        <div className="relative w-4 h-4 rounded-full border-2 border-white flex items-center justify-center">
          <div className="w-1.5 h-2 bg-[#0284c7] absolute bottom-[-2px] left-1/2 -translate-x-1/2" />
        </div>
      </div>
    );
  }

  if (n.includes("hdfc")) {
    return (
      <div
        className={`${sizeClasses} bg-[#991b1b] text-white flex items-center justify-center shrink-0 shadow-sm border border-red-500/20 select-none ${className}`}
        title={name}
      >
        <div className="w-4 h-4 border-2 border-white flex items-center justify-center p-0.5">
          <div className="w-1.5 h-1.5 bg-[#1d4ed8]" />
        </div>
      </div>
    );
  }

  if (n.includes("amazon pay") || (n.includes("amazon") && n.includes("later"))) {
    return (
      <div
        className={`${sizeClasses} bg-[#ea580c] text-white flex items-center justify-center shrink-0 shadow-sm border border-orange-400/20 select-none ${className}`}
        title={name}
      >
        <ShoppingCart size={iconSizes} className="text-white" />
      </div>
    );
  }

  if (n.includes("prime") || n.includes("amazon prime")) {
    return (
      <div
        className={`${sizeClasses} bg-[#0284c7] text-white font-sans font-bold flex items-center justify-center shrink-0 shadow-sm border border-sky-400/20 select-none ${className}`}
        title={name}
      >
        <span className="text-[10px] tracking-tighter lowercase font-extrabold">prime</span>
      </div>
    );
  }

  if (n.includes("adobe")) {
    return (
      <div
        className={`${sizeClasses} bg-[#dc2626] text-white font-black flex items-center justify-center shrink-0 shadow-sm border border-red-500/20 select-none ${className}`}
        title={name}
      >
        <span className="text-sm font-sans tracking-tight">A</span>
      </div>
    );
  }

  if (n.includes("netflix")) {
    return (
      <div
        className={`${sizeClasses} bg-[#18181b] text-[#e50914] font-black flex items-center justify-center shrink-0 shadow-sm border border-white/10 select-none ${className}`}
        title={name}
      >
        <span className="text-sm font-sans font-black tracking-tight">N</span>
      </div>
    );
  }

  if (n.includes("youtube")) {
    return (
      <div
        className={`${sizeClasses} bg-[#dc2626] text-white flex items-center justify-center shrink-0 shadow-sm border border-red-500/20 select-none ${className}`}
        title={name}
      >
        <Play size={iconSizes} className="fill-white translate-x-0.5" />
      </div>
    );
  }

  if (n.includes("google") || n.includes("google one")) {
    return (
      <div
        className={`${sizeClasses} bg-white text-slate-900 font-black flex items-center justify-center shrink-0 shadow-sm border border-slate-300 select-none ${className}`}
        title={name}
      >
        <span className="text-sm font-sans font-black bg-gradient-to-r from-blue-500 via-red-500 to-amber-500 bg-clip-text text-transparent">
          1
        </span>
      </div>
    );
  }

  if (n.includes("indian oil") || n.includes("indianoil") || n.includes("fuel")) {
    return (
      <div
        className={`${sizeClasses} bg-[#ea580c] text-white flex items-center justify-center shrink-0 shadow-sm border border-orange-400/20 select-none ${className}`}
        title={name}
      >
        <Fuel size={iconSizes} />
      </div>
    );
  }

  if (n.includes("bookmyshow") || n.includes("movie") || n.includes("cinema")) {
    return (
      <div
        className={`${sizeClasses} bg-[#e11d48] text-white flex items-center justify-center shrink-0 shadow-sm border border-rose-400/20 select-none ${className}`}
        title={name}
      >
        <Clapperboard size={iconSizes} />
      </div>
    );
  }

  if (n.includes("reliance") || n.includes("reliance fresh")) {
    return (
      <div
        className={`${sizeClasses} bg-[#059669] text-white flex items-center justify-center shrink-0 shadow-sm border border-emerald-400/20 select-none ${className}`}
        title={name}
      >
        <ShoppingCart size={iconSizes} />
      </div>
    );
  }

  if (n.includes("myntra")) {
    return (
      <div
        className={`${sizeClasses} bg-[#db2777] text-white font-black flex items-center justify-center shrink-0 shadow-sm border border-pink-400/20 select-none ${className}`}
        title={name}
      >
        <span className="text-sm font-sans font-black">M</span>
      </div>
    );
  }

  if (n.includes("dmart") || n.includes("d-mart")) {
    return (
      <div
        className={`${sizeClasses} bg-[#16a34a] text-white font-bold flex items-center justify-center shrink-0 shadow-sm border border-green-500/20 select-none ${className}`}
        title={name}
      >
        <span className="text-sm font-sans font-black">D</span>
      </div>
    );
  }

  if (n.includes("bigbasket") || n.includes("big basket")) {
    return (
      <div
        className={`${sizeClasses} bg-[#65a30d] text-white font-bold flex items-center justify-center shrink-0 shadow-sm border border-lime-400/20 select-none ${className}`}
        title={name}
      >
        <span className="text-xs font-sans font-black lowercase">bb</span>
      </div>
    );
  }

  if (n.includes("coffee") || n.includes("ccd") || n.includes("starbucks")) {
    return (
      <div
        className={`${sizeClasses} bg-[#78350f] text-amber-200 flex items-center justify-center shrink-0 shadow-sm border border-amber-600/30 select-none ${className}`}
        title={name}
      >
        <Coffee size={iconSizes} />
      </div>
    );
  }

  if (n.includes("ola") || n.includes("uber")) {
    return (
      <div
        className={`${sizeClasses} bg-[#09090b] text-white flex items-center justify-center shrink-0 shadow-sm border border-white/10 select-none ${className}`}
        title={name}
      >
        <Car size={iconSizes} className="text-white" />
      </div>
    );
  }

  if (n.includes("salary") || n.includes("payroll")) {
    return (
      <div
        className={`${sizeClasses} bg-[#10b981] text-white flex items-center justify-center shrink-0 shadow-sm border border-emerald-400/20 select-none ${className}`}
        title={name}
      >
        <Landmark size={iconSizes} />
      </div>
    );
  }

  if (n.includes("flipkart")) {
    return (
      <div
        className={`${sizeClasses} bg-[#2563eb] text-yellow-300 font-black flex items-center justify-center shrink-0 shadow-sm border border-blue-400/20 select-none ${className}`}
        title={name}
      >
        <span className="text-sm font-sans font-black italic">f</span>
      </div>
    );
  }

  if (n.includes("swiggy")) {
    return (
      <div
        className={`${sizeClasses} bg-[#f97316] text-white flex items-center justify-center shrink-0 shadow-sm border border-orange-400/20 select-none ${className}`}
        title={name}
      >
        <Utensils size={iconSizes} />
      </div>
    );
  }

  if (n.includes("zomato")) {
    return (
      <div
        className={`${sizeClasses} bg-[#dc2626] text-white font-black flex items-center justify-center shrink-0 shadow-sm border border-red-500/20 select-none ${className}`}
        title={name}
      >
        <span className="text-xs font-sans font-black italic">zomato</span>
      </div>
    );
  }

  if (n.includes("spotify")) {
    return (
      <div
        className={`${sizeClasses} bg-[#10b981] text-black flex items-center justify-center shrink-0 shadow-sm border border-emerald-400/20 select-none ${className}`}
        title={name}
      >
        <Film size={iconSizes} />
      </div>
    );
  }

  if (n.includes("apple")) {
    return (
      <div
        className={`${sizeClasses} bg-[#1e293b] text-white flex items-center justify-center shrink-0 shadow-sm border border-white/10 select-none ${className}`}
        title={name}
      >
        <Laptop size={iconSizes} />
      </div>
    );
  }

  // Category based fallback
  if (cat.includes("transport") || cat.includes("fuel") || cat.includes("cab") || cat.includes("ride")) {
    return (
      <div className={`${sizeClasses} bg-sky-500/15 text-sky-400 border border-sky-500/20 flex items-center justify-center shrink-0 select-none ${className}`}>
        <Car size={iconSizes} />
      </div>
    );
  }

  if (cat.includes("entertain") || cat.includes("movie") || cat.includes("ott") || cat.includes("video")) {
    return (
      <div className={`${sizeClasses} bg-purple-500/15 text-purple-400 border border-purple-500/20 flex items-center justify-center shrink-0 select-none ${className}`}>
        <Tv size={iconSizes} />
      </div>
    );
  }

  if (cat.includes("grocer") || cat.includes("supermarket")) {
    return (
      <div className={`${sizeClasses} bg-emerald-500/15 text-emerald-400 border border-emerald-500/20 flex items-center justify-center shrink-0 select-none ${className}`}>
        <ShoppingCart size={iconSizes} />
      </div>
    );
  }

  if (cat.includes("food") || cat.includes("dining") || cat.includes("restaurant")) {
    return (
      <div className={`${sizeClasses} bg-amber-500/15 text-amber-400 border border-amber-500/20 flex items-center justify-center shrink-0 select-none ${className}`}>
        <Utensils size={iconSizes} />
      </div>
    );
  }

  if (cat.includes("shop") || cat.includes("apparel") || cat.includes("cloth")) {
    return (
      <div className={`${sizeClasses} bg-fuchsia-500/15 text-fuchsia-400 border border-fuchsia-500/20 flex items-center justify-center shrink-0 select-none ${className}`}>
        <ShoppingBag size={iconSizes} />
      </div>
    );
  }

  if (cat.includes("income") || cat.includes("salary")) {
    return (
      <div className={`${sizeClasses} bg-emerald-500/15 text-emerald-400 border border-emerald-500/20 flex items-center justify-center shrink-0 select-none ${className}`}>
        <Landmark size={iconSizes} />
      </div>
    );
  }

  if (cat.includes("software") || cat.includes("cloud") || cat.includes("tech")) {
    return (
      <div className={`${sizeClasses} bg-indigo-500/15 text-indigo-400 border border-indigo-500/20 flex items-center justify-center shrink-0 select-none ${className}`}>
        <Laptop size={iconSizes} />
      </div>
    );
  }

  if (cat.includes("finance") || cat.includes("loan") || cat.includes("emi") || cat.includes("bank")) {
    return (
      <div className={`${sizeClasses} bg-blue-500/15 text-blue-400 border border-blue-500/20 flex items-center justify-center shrink-0 select-none ${className}`}>
        <CreditCard size={iconSizes} />
      </div>
    );
  }

  // Default initial avatar with smooth hash-based colors
  const initials = (name || "TX")
    .replace(/[^a-zA-Z0-9]/g, " ")
    .trim()
    .split(/\s+/)
    .map((w) => w[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase() || "T";

  const colorPalettes = [
    "bg-indigo-500/15 text-indigo-400 border-indigo-500/20",
    "bg-sky-500/15 text-sky-400 border-sky-500/20",
    "bg-emerald-500/15 text-emerald-400 border-emerald-500/20",
    "bg-purple-500/15 text-purple-400 border-purple-500/20",
    "bg-amber-500/15 text-amber-400 border-amber-500/20",
    "bg-rose-500/15 text-rose-400 border-rose-500/20",
  ];

  let hash = 0;
  for (let i = 0; i < (name || "").length; i++) {
    hash = (hash + name.charCodeAt(i)) % colorPalettes.length;
  }
  const colorClass = colorPalettes[hash];

  return (
    <div
      className={`${sizeClasses} ${colorClass} border font-semibold flex items-center justify-center shrink-0 select-none ${className}`}
      title={name}
    >
      <span className="font-mono text-xs font-bold leading-none">{initials}</span>
    </div>
  );
}
