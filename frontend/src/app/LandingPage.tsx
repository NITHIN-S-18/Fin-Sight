import React, { useEffect, useState } from "react";
import { motion, AnimatePresence, useReducedMotion } from "motion/react";
import {
  ArrowRight,
  Play,
  Bell,
  Sparkles,
  Sliders,
  Calendar,
  CreditCard,
  Wallet,
  TrendingUp,
  BarChart3,
  PieChart,
  Shield,
  ShieldCheck,
  CheckCircle2,
  Sun,
  Moon,
  X,
  ChevronDown,
  Layers,
  Lock,
  Menu,
  Activity,
  FileText,
  Bot,
  ExternalLink,
  Info,
  Clock,
  Home,
  Smartphone,
  ChevronRight,
} from "lucide-react";
import { FinSightLogo } from "./components/FinSightLogo";

export type Theme = "light" | "dark" | "system";

export interface LandingPageProps {
  onLogin: () => void;
  onRegister: () => void;
  theme: Theme;
  onThemeChange: (t: Theme) => void;
}

type OverlayId =
  | null
  | "how-it-works"
  | "intelligence"
  | "what-if"
  | "assistant"
  | "security"
  | "demo"
  | "subscriptions"
  | "emis"
  | "bnpl";

export function LandingPage({
  onLogin,
  onRegister,
  theme,
  onThemeChange,
}: LandingPageProps) {
  const reduceMotion = useReducedMotion();
  const [activeOverlay, setActiveOverlay] = useState<OverlayId>(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [intelligenceTab, setIntelligenceTab] = useState<"subscriptions" | "emis" | "bnpl" | "exposure">("subscriptions");
  const [demoStep, setDemoStep] = useState(0);

  const isDarkActive =
    theme === "dark" ||
    (theme === "system" &&
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-color-scheme: dark)").matches);

  // Close overlays with Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setActiveOverlay(null);
        setMobileMenuOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Prevent background body scroll when an overlay is open
  useEffect(() => {
    if (activeOverlay) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [activeOverlay]);

  const openOverlay = (id: OverlayId) => {
    if (id === "subscriptions") {
      setIntelligenceTab("subscriptions");
      setActiveOverlay("intelligence");
    } else if (id === "emis") {
      setIntelligenceTab("emis");
      setActiveOverlay("intelligence");
    } else if (id === "bnpl") {
      setIntelligenceTab("bnpl");
      setActiveOverlay("intelligence");
    } else {
      setActiveOverlay(id);
    }
    setMobileMenuOpen(false);
  };

  return (
    <div className="relative min-h-screen w-full bg-[#060811] text-slate-100 flex flex-col overflow-x-hidden selection:bg-indigo-500/30 selection:text-indigo-200">
      
      {/* ═════════════════════════════════════════════════════════════
          HERO SECTION (BALANCED TWO-COLUMN VIEWPORT COMPLIANT ON DESKTOP)
      ═════════════════════════════════════════════════════════════ */}
      <section className="relative min-h-screen lg:h-screen lg:max-h-screen w-full flex flex-col justify-between overflow-hidden">
        
        {/* ─────────────────────────────────────────────────────────────
            CINEMATIC BACKGROUND: REFINED PLANETARY HORIZON & AMBIENT DEPTH
        ───────────────────────────────────────────────────────────── */}
        <div aria-hidden="true" className="pointer-events-none absolute inset-0 z-0 overflow-hidden">
          {/* Deep Space Foundation Base */}
          <div className="absolute inset-0 bg-[#060811]" />

          {/* Left Side Subtle Indigo Wash */}
          <div className="absolute top-[20%] -left-20 w-[500px] h-[500px] rounded-full bg-[radial-gradient(circle_at_center,_rgba(79,70,229,0.07)_0%,_transparent_65%)] blur-[120px]" />

          {/* Right Side Breathing Blue-Violet Atmospheric Nebula */}
          <motion.div
            animate={reduceMotion ? undefined : { opacity: [0.75, 0.95, 0.75] }}
            transition={{ duration: 9, repeat: Infinity, ease: "easeInOut" }}
            className="absolute top-[8%] right-[2%] sm:right-[6%] lg:right-[8%] w-[520px] sm:w-[650px] lg:w-[750px] h-[480px] sm:h-[580px] lg:h-[680px] rounded-full bg-[radial-gradient(ellipse_at_center,_rgba(30,58,138,0.25)_0%,_rgba(14,165,233,0.12)_35%,_rgba(99,102,241,0.06)_55%,_transparent_75%)] blur-[95px]"
          />

          {/* Sparse, Subtle Ambient Dust Particles */}
          {[
            { x: "14%", y: "20%", size: 1.5, opacity: 0.35 },
            { x: "32%", y: "15%", size: 1.2, opacity: 0.25 },
            { x: "68%", y: "18%", size: 2.0, opacity: 0.4 },
            { x: "82%", y: "24%", size: 1.5, opacity: 0.3 },
            { x: "22%", y: "78%", size: 1.2, opacity: 0.2 },
            { x: "78%", y: "68%", size: 1.5, opacity: 0.25 },
          ].map((star, idx) => (
            <div
              key={idx}
              className="absolute rounded-full bg-cyan-200"
              style={{
                left: star.x,
                top: star.y,
                width: `${star.size}px`,
                height: `${star.size}px`,
                opacity: star.opacity,
                boxShadow: `0 0 4px rgba(56, 189, 248, 0.6)`,
              }}
            />
          ))}

          {/* Atmospheric Celestial Horizon Rim behind Dashboard */}
          <div className="absolute top-[2%] sm:top-[0%] right-[-2%] sm:right-[3%] lg:right-[5%] w-[480px] sm:w-[600px] lg:w-[680px] h-[360px] sm:h-[440px] lg:h-[480px] opacity-80">
            <svg viewBox="0 0 700 500" className="w-full h-full overflow-visible">
              <defs>
                <linearGradient id="horizonGlowRefined" x1="0%" y1="100%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#0284c7" stopOpacity="0" />
                  <stop offset="35%" stopColor="#0ea5e9" stopOpacity="0.5" />
                  <stop offset="65%" stopColor="#38bdf8" stopOpacity="0.85" />
                  <stop offset="85%" stopColor="#818cf8" stopOpacity="0.6" />
                  <stop offset="100%" stopColor="#6366f1" stopOpacity="0" />
                </linearGradient>
                <filter id="softHorizonBlur" x="-30%" y="-30%" width="160%" height="160%">
                  <feGaussianBlur stdDeviation="14" />
                </filter>
                <filter id="crispHorizonGlow" x="-20%" y="-20%" width="140%" height="140%">
                  <feGaussianBlur stdDeviation="3" />
                </filter>
              </defs>

              {/* Soft diffused atmospheric glow arc */}
              <path
                d="M 110 440 Q 360 170 670 210"
                fill="none"
                stroke="url(#horizonGlowRefined)"
                strokeWidth="26"
                filter="url(#softHorizonBlur)"
                opacity="0.45"
              />

              {/* Elegant luminous curved planetary horizon rim */}
              <path
                d="M 110 440 Q 360 170 670 210"
                fill="none"
                stroke="url(#horizonGlowRefined)"
                strokeWidth="3.2"
                filter="url(#crispHorizonGlow)"
                opacity="0.85"
              />

              {/* Specular hairline crest highlight */}
              <path
                d="M 160 410 Q 360 174 630 212"
                fill="none"
                stroke="#e0f2fe"
                strokeWidth="1.2"
                opacity="0.7"
              />
            </svg>
          </div>

          {/* Refined Understated Pedestal & Ground Reflection beneath Dashboard */}
          <div className="absolute bottom-[2%] right-[1%] sm:right-[5%] lg:right-[7%] w-[460px] sm:w-[580px] lg:w-[680px] h-20 opacity-80">
            <svg viewBox="0 0 680 80" className="w-full h-full overflow-visible">
              <defs>
                <linearGradient id="pedestalCyanLine" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#0ea5e9" stopOpacity="0" />
                  <stop offset="25%" stopColor="#38bdf8" stopOpacity="0.45" />
                  <stop offset="50%" stopColor="#7dd3fc" stopOpacity="0.95" />
                  <stop offset="75%" stopColor="#38bdf8" stopOpacity="0.45" />
                  <stop offset="100%" stopColor="#0ea5e9" stopOpacity="0" />
                </linearGradient>
                <filter id="pedestalBlur" x="-20%" y="-50%" width="140%" height="200%">
                  <feGaussianBlur stdDeviation="7" />
                </filter>
              </defs>
              {/* Diffuse Cyan Ground Glow */}
              <ellipse cx="340" cy="40" rx="260" ry="12" fill="#0284c7" opacity="0.14" filter="url(#pedestalBlur)" />
              {/* Crisp Horizon Reflection Line */}
              <line x1="80" y1="38" x2="600" y2="38" stroke="url(#pedestalCyanLine)" strokeWidth="1.6" opacity="0.8" />
              {/* Specular Center Highlight */}
              <line x1="220" y1="38" x2="460" y2="38" stroke="#ffffff" strokeWidth="1.2" opacity="0.6" />
            </svg>
          </div>
        </div>

        {/* ─────────────────────────────────────────────────────────────
            TOP NAVIGATION BAR
        ───────────────────────────────────────────────────────────── */}
        <motion.header
          initial={reduceMotion ? false : { opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: "easeOut" }}
          className="relative z-40 w-full shrink-0 h-16 sm:h-20 px-4 sm:px-8 lg:px-12 flex items-center justify-between border-b border-white/[0.04] backdrop-blur-sm"
        >
          {/* Brand Logo */}
          <div className="flex items-center gap-1.5 cursor-pointer" onClick={() => setActiveOverlay(null)}>
            <FinSightLogo variant="full" size="md" showSparkle={false} />
            <span className="text-indigo-400 font-bold text-lg leading-none -ml-1">+</span>
          </div>

          {/* Desktop Navigation Links */}
          <nav className="hidden md:flex items-center gap-6 lg:gap-8 text-sm font-medium text-slate-300">
            <button
              type="button"
              onClick={() => openOverlay("how-it-works")}
              className="hover:text-white transition-colors duration-150 cursor-pointer focus-visible:outline-none focus-visible:text-white"
            >
              How It Works
            </button>
            <button
              type="button"
              onClick={() => {
                setIntelligenceTab("subscriptions");
                openOverlay("intelligence");
              }}
              className="hover:text-white transition-colors duration-150 cursor-pointer focus-visible:outline-none focus-visible:text-white"
            >
              Intelligence
            </button>
            <button
              type="button"
              onClick={() => openOverlay("what-if")}
              className="hover:text-white transition-colors duration-150 cursor-pointer focus-visible:outline-none focus-visible:text-white"
            >
              What-If
            </button>
            <button
              type="button"
              onClick={() => openOverlay("assistant")}
              className="hover:text-white transition-colors duration-150 cursor-pointer focus-visible:outline-none focus-visible:text-white"
            >
              Assistant
            </button>
            <button
              type="button"
              onClick={() => openOverlay("security")}
              className="hover:text-white transition-colors duration-150 cursor-pointer focus-visible:outline-none focus-visible:text-white"
            >
              Security
            </button>
          </nav>

          {/* Action Controls & Auth CTAs */}
          <div className="hidden md:flex items-center gap-3">
            {/* Theme Toggle Pill */}
            <button
              type="button"
              onClick={() => onThemeChange(isDarkActive ? "light" : "dark")}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-full border border-white/10 bg-white/[0.03] hover:bg-white/[0.08] text-slate-300 hover:text-white transition-all cursor-pointer"
              aria-label="Toggle visual theme"
              title="Toggle theme"
            >
              <Sun size={13} className={!isDarkActive ? "text-amber-500" : "text-slate-400"} />
              <Moon size={13} className={isDarkActive ? "text-indigo-400" : "text-slate-400"} />
            </button>

            {/* Sign In Button */}
            <button
              type="button"
              onClick={onLogin}
              className="px-4 py-2 rounded-xl border border-white/15 bg-white/[0.03] hover:bg-white/[0.08] hover:border-white/25 text-white font-medium text-xs sm:text-sm transition-all cursor-pointer"
            >
              Sign In
            </button>

            {/* Get Started Button */}
            <motion.button
              whileHover={reduceMotion ? {} : { scale: 1.02 }}
              whileTap={reduceMotion ? {} : { scale: 0.98 }}
              type="button"
              onClick={onRegister}
              className="px-4.5 py-2 rounded-xl bg-gradient-to-r from-indigo-500 to-indigo-600 hover:from-indigo-600 hover:to-indigo-700 text-white font-medium text-xs sm:text-sm shadow-[0_0_20px_rgba(99,102,241,0.35)] hover:shadow-[0_0_25px_rgba(99,102,241,0.5)] flex items-center gap-1.5 transition-all cursor-pointer"
            >
              Get Started
              <ArrowRight size={14} />
            </motion.button>
          </div>

          {/* Mobile Hamburger Button */}
          <button
            type="button"
            onClick={() => setMobileMenuOpen((prev) => !prev)}
            className="md:hidden p-2 rounded-lg border border-white/10 bg-white/5 text-slate-300 hover:text-white focus:outline-none"
            aria-label="Toggle navigation menu"
          >
            {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </motion.header>

        {/* Mobile Drawer Menu */}
        <AnimatePresence>
          {mobileMenuOpen && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="md:hidden z-50 absolute top-16 left-0 w-full bg-[#0b101e]/98 border-b border-white/10 backdrop-blur-2xl p-6 space-y-4 shadow-2xl"
            >
              <div className="flex flex-col space-y-3 font-medium text-sm text-slate-200">
                <button
                  type="button"
                  onClick={() => openOverlay("how-it-works")}
                  className="text-left py-1.5 hover:text-white"
                >
                  How It Works
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setIntelligenceTab("subscriptions");
                    openOverlay("intelligence");
                  }}
                  className="text-left py-1.5 hover:text-white"
                >
                  Intelligence
                </button>
                <button
                  type="button"
                  onClick={() => openOverlay("what-if")}
                  className="text-left py-1.5 hover:text-white"
                >
                  What-If Simulator
                </button>
                <button
                  type="button"
                  onClick={() => openOverlay("assistant")}
                  className="text-left py-1.5 hover:text-white"
                >
                  Financial Assistant
                </button>
                <button
                  type="button"
                  onClick={() => openOverlay("security")}
                  className="text-left py-1.5 hover:text-white"
                >
                  Security & Privacy
                </button>
              </div>

              <div className="pt-3 border-t border-white/10 flex items-center justify-between text-xs text-slate-300">
                <span>Visual Theme</span>
                <button
                  type="button"
                  onClick={() => onThemeChange(isDarkActive ? "light" : "dark")}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-white/10 bg-white/[0.04] text-slate-200"
                >
                  {isDarkActive ? <Moon size={13} className="text-indigo-400" /> : <Sun size={13} className="text-amber-500" />}
                  <span>{isDarkActive ? "Dark Mode" : "Light Mode"}</span>
                </button>
              </div>

              <div className="pt-3 border-t border-white/10 flex items-center gap-3">
                <button
                  type="button"
                  onClick={onLogin}
                  className="flex-1 py-2.5 rounded-xl border border-white/15 bg-white/5 text-white font-medium text-sm text-center"
                >
                  Sign In
                </button>
                <button
                  type="button"
                  onClick={onRegister}
                  className="flex-1 py-2.5 rounded-xl bg-gradient-to-r from-indigo-500 to-indigo-600 text-white font-medium text-sm text-center shadow-md"
                >
                  Get Started
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ─────────────────────────────────────────────────────────────
            HERO MAIN VIEWPORT CONTENT (BALANCED TWO-COLUMN COMPOSITION)
        ───────────────────────────────────────────────────────────── */}
        <div className="relative z-10 flex-1 flex items-center px-4 sm:px-8 lg:px-12 py-6 lg:py-0 overflow-visible lg:overflow-hidden">
          <div className="w-full max-w-[1440px] mx-auto grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-6 xl:gap-8 items-center">
            
            {/* ── LEFT COLUMN: HERO HEADLINE & ACTIONS ── */}
            <div className="lg:col-span-5 xl:col-span-5 flex flex-col justify-center space-y-5 lg:space-y-6 z-20">
              {/* Pill Label */}
              <motion.div
                initial={reduceMotion ? false : { opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: 0.1, ease: "easeOut" }}
                className="inline-flex items-center gap-2 self-start px-3.5 py-1.5 rounded-full border border-indigo-500/30 bg-indigo-500/10 backdrop-blur-md"
              >
                <BarChart3 size={13} className="text-indigo-400 shrink-0" />
                <span className="text-xs font-medium tracking-wide text-indigo-300">
                  Financial Exposure Intelligence
                </span>
              </motion.div>

              {/* Headline */}
              <motion.h1
                initial={reduceMotion ? false : { opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.55, delay: 0.18, ease: "easeOut" }}
                className="text-3xl sm:text-4xl lg:text-[42px] xl:text-[48px] 2xl:text-[52px] font-extrabold tracking-tight leading-[1.1] text-white"
              >
                <span className="block text-white">See beyond</span>
                <span className="block text-white">your balance.</span>
                <span className="block bg-gradient-to-r from-[#818cf8] via-[#a855f7] to-[#38bdf8] bg-clip-text text-transparent">
                  Discover what's
                </span>
                <span className="block bg-gradient-to-r from-[#818cf8] via-[#a855f7] to-[#38bdf8] bg-clip-text text-transparent">
                  really committed.
                </span>
              </motion.h1>

              {/* Supporting Subtext */}
              <motion.p
                initial={reduceMotion ? false : { opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: 0.28, ease: "easeOut" }}
                className="text-sm sm:text-base lg:text-[15px] xl:text-base text-slate-400 leading-relaxed max-w-lg"
              >
                Turn your transaction history into clear insights — subscriptions, EMIs, BNPL, and your true financial exposure.
              </motion.p>

              {/* Call To Action Buttons */}
              <motion.div
                initial={reduceMotion ? false : { opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: 0.36, ease: "easeOut" }}
                className="flex flex-wrap items-center gap-3.5 pt-1"
              >
                <motion.button
                  whileHover={reduceMotion ? {} : { scale: 1.02, y: -2 }}
                  whileTap={reduceMotion ? {} : { scale: 0.98 }}
                  type="button"
                  onClick={onRegister}
                  className="group px-6 py-3.5 rounded-xl bg-gradient-to-r from-indigo-500 via-indigo-600 to-blue-600 hover:from-indigo-600 hover:to-blue-700 text-white font-semibold text-sm shadow-[0_8px_25px_rgba(99,102,241,0.4)] hover:shadow-[0_8px_32px_rgba(99,102,241,0.6)] flex items-center gap-2 transition-all cursor-pointer"
                >
                  <span>Get Started with FinSight</span>
                  <ArrowRight size={15} className="group-hover:translate-x-1 transition-transform" />
                </motion.button>

                <motion.button
                  whileHover={reduceMotion ? {} : { scale: 1.02 }}
                  whileTap={reduceMotion ? {} : { scale: 0.98 }}
                  type="button"
                  onClick={() => openOverlay("demo")}
                  className="px-5 py-3.5 rounded-xl border border-white/15 bg-white/[0.04] hover:bg-white/[0.09] hover:border-white/25 text-white font-semibold text-sm flex items-center gap-2.5 transition-all cursor-pointer"
                >
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-indigo-500/20 text-indigo-300">
                    <Play size={10} className="fill-current ml-0.5" />
                  </span>
                  Watch Demo
                </motion.button>
              </motion.div>

              {/* Four Compact Feature Shortcuts */}
              <motion.div
                initial={reduceMotion ? false : { opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: 0.44, ease: "easeOut" }}
                className="grid grid-cols-4 gap-2 pt-4 sm:pt-6 border-t border-white/[0.06] max-w-lg"
              >
                {/* Shortcut 1: Subscription Detection */}
                <button
                  type="button"
                  onClick={() => openOverlay("subscriptions")}
                  className="group flex flex-col items-center sm:items-start text-center sm:text-left transition-transform hover:-translate-y-0.5 cursor-pointer focus:outline-none"
                >
                  <div className="h-9 w-9 rounded-full bg-purple-500/15 border border-purple-500/30 flex items-center justify-center text-purple-400 group-hover:bg-purple-500/25 group-hover:border-purple-400 transition-colors mb-2">
                    <Calendar size={15} />
                  </div>
                  <span className="text-[11px] font-medium text-slate-300 leading-tight group-hover:text-white transition-colors">
                    Subscription<br />Detection
                  </span>
                </button>

                {/* Shortcut 2: EMI Tracking */}
                <button
                  type="button"
                  onClick={() => openOverlay("emis")}
                  className="group flex flex-col items-center sm:items-start text-center sm:text-left transition-transform hover:-translate-y-0.5 cursor-pointer focus:outline-none"
                >
                  <div className="h-9 w-9 rounded-full bg-blue-500/15 border border-blue-500/30 flex items-center justify-center text-blue-400 group-hover:bg-blue-500/25 group-hover:border-blue-400 transition-colors mb-2">
                    <CreditCard size={15} />
                  </div>
                  <span className="text-[11px] font-medium text-slate-300 leading-tight group-hover:text-white transition-colors">
                    EMI<br />Tracking
                  </span>
                </button>

                {/* Shortcut 3: BNPL Analysis */}
                <button
                  type="button"
                  onClick={() => openOverlay("bnpl")}
                  className="group flex flex-col items-center sm:items-start text-center sm:text-left transition-transform hover:-translate-y-0.5 cursor-pointer focus:outline-none"
                >
                  <div className="h-9 w-9 rounded-full bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-400 group-hover:bg-amber-500/25 group-hover:border-amber-400 transition-colors mb-2">
                    <Wallet size={15} />
                  </div>
                  <span className="text-[11px] font-medium text-slate-300 leading-tight group-hover:text-white transition-colors">
                    BNPL<br />Analysis
                  </span>
                </button>

                {/* Shortcut 4: What-If Scenarios */}
                <button
                  type="button"
                  onClick={() => openOverlay("what-if")}
                  className="group flex flex-col items-center sm:items-start text-center sm:text-left transition-transform hover:-translate-y-0.5 cursor-pointer focus:outline-none"
                >
                  <div className="h-9 w-9 rounded-full bg-teal-500/15 border border-teal-500/30 flex items-center justify-center text-teal-400 group-hover:bg-teal-500/25 group-hover:border-teal-400 transition-colors mb-2">
                    <TrendingUp size={15} />
                  </div>
                  <span className="text-[11px] font-medium text-slate-300 leading-tight group-hover:text-white transition-colors">
                    What-If<br />Scenarios
                  </span>
                </button>
              </motion.div>
            </div>

            {/* ── RIGHT COLUMN: 3D FINANCIAL DASHBOARD VISUALIZATION ── */}
            <div className="lg:col-span-7 xl:col-span-7 relative flex items-center justify-center pt-8 pb-10 lg:py-0">
              
              {/* 3D Dashboard Container with Entrance Animation */}
              <motion.div
                initial={reduceMotion ? false : { opacity: 0, scale: 0.96, y: 20 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                transition={{ duration: 0.7, delay: 0.3, ease: [0.16, 1, 0.3, 1] }}
                className="relative z-10 w-full max-w-[560px] xl:max-w-[640px] 2xl:max-w-[680px] transition-transform duration-500"
                style={{
                  perspective: "1000px",
                }}
              >
                {/* Floating Tablet Shell with 3D tilt */}
                <div
                  className="relative rounded-[20px] sm:rounded-[24px] p-2 sm:p-2.5 bg-[#0e1424]/95 border border-white/20 shadow-[0_20px_50px_rgba(0,0,0,0.85),0_0_30px_rgba(56,189,248,0.12)] transition-transform duration-700 hover:rotate-0"
                  style={{
                    transform: reduceMotion ? "none" : (typeof window !== "undefined" && window.innerWidth < 640 ? "none" : "rotateY(-5deg) rotateX(2.5deg)"),
                    transformStyle: "preserve-3d",
                  }}
                >
                  {/* Tablet Display Screen */}
                  <div className="rounded-[16px] sm:rounded-[18px] bg-[#0b101e] border border-white/[0.08] p-3 sm:p-4 flex gap-3 sm:gap-4 overflow-hidden">
                    
                    {/* Left Mini-Sidebar inside Dashboard */}
                    <div className="hidden sm:flex flex-col justify-between w-28 shrink-0 border-r border-white/[0.06] pr-3 select-none">
                      <div className="space-y-4">
                        {/* Dashboard Brand */}
                        <div className="flex items-center gap-1">
                          <FinSightLogo variant="mark" size="sm" />
                          <span className="text-[12px] font-bold text-white tracking-tight">FinSight<span className="text-indigo-400">+</span></span>
                        </div>

                        {/* Mini Nav Items */}
                        <div className="space-y-1 text-[11px] font-medium text-slate-400">
                          <div className="flex items-center gap-2 px-2 py-1.5 rounded-lg bg-indigo-600/30 text-white border border-indigo-500/40">
                            <BarChart3 size={12} className="text-indigo-400" />
                            <span>Dashboard</span>
                          </div>
                          <div className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:text-slate-200 cursor-pointer">
                            <Calendar size={12} className="text-slate-400" />
                            <span>Subscriptions</span>
                          </div>
                          <div className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:text-slate-200 cursor-pointer">
                            <CreditCard size={12} className="text-slate-400" />
                            <span>EMIs</span>
                          </div>
                          <div className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:text-slate-200 cursor-pointer">
                            <Wallet size={12} className="text-slate-400" />
                            <span>BNPL</span>
                          </div>
                          <div className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:text-slate-200 cursor-pointer">
                            <Sliders size={12} className="text-slate-400" />
                            <span>What-If</span>
                          </div>
                          <div className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:text-slate-200 cursor-pointer">
                            <Bot size={12} className="text-slate-400" />
                            <span>Assistant</span>
                          </div>
                        </div>
                      </div>

                      <div className="pt-2 border-t border-white/[0.06] text-[9px] text-slate-400 flex items-center gap-1">
                        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                        Live Engine
                      </div>
                    </div>

                    {/* Main Screen Content */}
                    <div className="flex-1 min-w-0 space-y-3">
                      {/* Top Dashboard Header */}
                      <div className="flex items-center justify-between pb-1 border-b border-white/[0.04]">
                        <div>
                          <p className="text-[10px] text-slate-400">Good morning,</p>
                          <h2 className="text-xs sm:text-sm font-bold text-white tracking-tight">
                            Here's your financial overview
                          </h2>
                        </div>
                        <div className="flex items-center gap-1 px-2 py-1 rounded-md bg-white/[0.04] border border-white/[0.08] text-[10px] text-slate-300">
                          <Calendar size={10} className="text-slate-400" />
                          <span>Jan 2025 - Mar 2025</span>
                          <ChevronDown size={10} className="text-slate-400 ml-0.5" />
                        </div>
                      </div>

                      {/* Top Row of 3 Metric Cards */}
                      <div className="grid grid-cols-3 gap-2">
                        {/* Metric 1: Financial Exposure */}
                        <div className="rounded-xl bg-[#0f172a]/70 border border-white/[0.06] p-2.5 flex flex-col justify-between">
                          <div className="flex items-center justify-between">
                            <span className="text-[10px] font-medium text-slate-400">Financial Exposure</span>
                            <span className="text-[8px] font-semibold px-1 py-0.2 rounded bg-rose-500/20 text-rose-400 border border-rose-500/30">
                              + High
                            </span>
                          </div>
                          <div className="my-1">
                            <span className="text-base sm:text-lg font-bold text-white">62%</span>
                          </div>
                          {/* Red Progress Bar */}
                          <div className="h-1 w-full bg-slate-800 rounded-full overflow-hidden">
                            <div className="h-full bg-rose-500 rounded-full" style={{ width: "62%" }} />
                          </div>
                        </div>

                        {/* Metric 2: Monthly Commitments */}
                        <div className="rounded-xl bg-[#0f172a]/70 border border-white/[0.06] p-2.5 flex flex-col justify-between">
                          <div className="flex items-center justify-between">
                            <span className="text-[10px] font-medium text-slate-400">Monthly Commitments</span>
                            <span className="text-[8px] font-semibold px-1 py-0.2 rounded bg-emerald-500/20 text-emerald-400">
                              ↑ 12%
                            </span>
                          </div>
                          <div className="my-1">
                            <span className="text-base sm:text-lg font-bold text-white">₹42,800</span>
                          </div>
                          {/* Mini Bar Chart */}
                          <div className="flex items-end gap-1 h-3 pt-0.5">
                            {[35, 45, 60, 40, 75, 50, 90, 70, 85, 65].map((h, i) => (
                              <div
                                key={i}
                                className="flex-1 bg-cyan-400/80 rounded-t-sm"
                                style={{ height: `${h}%` }}
                              />
                            ))}
                          </div>
                        </div>

                        {/* Metric 3: Available Capacity */}
                        <div className="rounded-xl bg-[#0f172a]/70 border border-white/[0.06] p-2.5 flex flex-col justify-between">
                          <div className="flex items-center justify-between">
                            <span className="text-[10px] font-medium text-slate-400">Available Capacity</span>
                            <span className="text-[8px] font-semibold px-1 py-0.2 rounded bg-emerald-500/20 text-emerald-400">
                              ↑ 5%
                            </span>
                          </div>
                          <div className="flex items-center justify-between my-0.5">
                            <span className="text-base sm:text-lg font-bold text-white">₹27,200</span>
                            {/* Mini Circular Gauge */}
                            <div className="relative h-6 w-6 shrink-0">
                              <svg viewBox="0 0 36 36" className="w-full h-full -rotate-90">
                                <circle cx="18" cy="18" r="14" fill="none" stroke="#1e293b" strokeWidth="4" />
                                <circle
                                  cx="18"
                                  cy="18"
                                  r="14"
                                  fill="none"
                                  stroke="#2dd4bf"
                                  strokeWidth="4"
                                  strokeDasharray="87.96"
                                  strokeDashoffset="54.5"
                                  strokeLinecap="round"
                                />
                              </svg>
                            </div>
                          </div>
                          <div className="text-[8px] text-slate-400">Safe margin: ₹6,500</div>
                        </div>
                      </div>

                      {/* Bottom Row of 2 Detail Cards */}
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                        
                        {/* Card A: Top Commitments List */}
                        <div className="rounded-xl bg-[#0f172a]/70 border border-white/[0.06] p-2.5">
                          <div className="flex items-center justify-between mb-2">
                            <h3 className="text-[11px] font-semibold text-slate-300">Top Commitments</h3>
                            <span className="text-[9px] text-indigo-400 font-medium">5 active</span>
                          </div>
                          <div className="space-y-1.5">
                            {/* Item 1: Netflix */}
                            <div className="flex items-center justify-between text-[10px]">
                              <div className="flex items-center gap-1.5">
                                <span className="h-4.5 w-4.5 rounded bg-red-600 flex items-center justify-center font-bold text-white text-[9px]">
                                  N
                                </span>
                                <span className="text-slate-200 font-medium">Netflix</span>
                              </div>
                              <span className="text-slate-300 font-semibold">₹649 <span className="text-[8px] text-slate-400 font-normal">/mo</span></span>
                            </div>

                            {/* Item 2: Amazon Prime */}
                            <div className="flex items-center justify-between text-[10px]">
                              <div className="flex items-center gap-1.5">
                                <span className="h-4.5 w-4.5 rounded bg-sky-600 flex items-center justify-center text-white text-[9px]">
                                  📦
                                </span>
                                <span className="text-slate-200 font-medium">Amazon Prime</span>
                              </div>
                              <span className="text-slate-300 font-semibold">₹1,499 <span className="text-[8px] text-slate-400 font-normal">/mo</span></span>
                            </div>

                            {/* Item 3: Home Loan EMI */}
                            <div className="flex items-center justify-between text-[10px]">
                              <div className="flex items-center gap-1.5">
                                <span className="h-4.5 w-4.5 rounded bg-amber-600/80 flex items-center justify-center text-white text-[9px]">
                                  <Home size={9} />
                                </span>
                                <span className="text-slate-200 font-medium">Home Loan EMI</span>
                              </div>
                              <span className="text-slate-300 font-semibold">₹12,500 <span className="text-[8px] text-slate-400 font-normal">/mo</span></span>
                            </div>

                            {/* Item 4: iPhone EMI */}
                            <div className="flex items-center justify-between text-[10px]">
                              <div className="flex items-center gap-1.5">
                                <span className="h-4.5 w-4.5 rounded bg-slate-700 flex items-center justify-center text-white text-[9px]">
                                  <Smartphone size={9} />
                                </span>
                                <span className="text-slate-200 font-medium">iPhone EMI</span>
                              </div>
                              <span className="text-slate-300 font-semibold">₹4,299 <span className="text-[8px] text-slate-400 font-normal">/mo</span></span>
                            </div>

                            {/* Item 5: Zomato Pro */}
                            <div className="flex items-center justify-between text-[10px]">
                              <div className="flex items-center gap-1.5">
                                <span className="h-4.5 w-4.5 rounded bg-rose-600 flex items-center justify-center font-bold text-white text-[9px]">
                                  Z
                                </span>
                                <span className="text-slate-200 font-medium">Zomato Pro</span>
                              </div>
                              <span className="text-slate-300 font-semibold">₹299 <span className="text-[8px] text-slate-400 font-normal">/mo</span></span>
                            </div>
                          </div>
                        </div>

                        {/* Card B: Exposure Breakdown Donut Chart */}
                        <div className="rounded-xl bg-[#0f172a]/70 border border-white/[0.06] p-2.5 flex flex-col justify-between">
                          <h3 className="text-[11px] font-semibold text-slate-300 mb-1">Exposure Breakdown</h3>
                          
                          <div className="flex items-center justify-around py-1">
                            {/* Donut Chart SVG */}
                            <div className="relative h-20 w-20 shrink-0">
                              <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
                                <circle cx="50" cy="50" r="36" fill="none" stroke="#1e293b" strokeWidth="13" />
                                <circle
                                  cx="50"
                                  cy="50"
                                  r="36"
                                  fill="none"
                                  stroke="#3b82f6"
                                  strokeWidth="13"
                                  strokeDasharray="85.95 226.19"
                                  strokeDashoffset="0"
                                />
                                <circle
                                  cx="50"
                                  cy="50"
                                  r="36"
                                  fill="none"
                                  stroke="#06b6d4"
                                  strokeWidth="13"
                                  strokeDasharray="49.76 226.19"
                                  strokeDashoffset="-85.95"
                                />
                                <circle
                                  cx="50"
                                  cy="50"
                                  r="36"
                                  fill="none"
                                  stroke="#f43f5e"
                                  strokeWidth="13"
                                  strokeDasharray="33.93 226.19"
                                  strokeDashoffset="-135.71"
                                />
                                <circle
                                  cx="50"
                                  cy="50"
                                  r="36"
                                  fill="none"
                                  stroke="#a855f7"
                                  strokeWidth="13"
                                  strokeDasharray="56.55 226.19"
                                  strokeDashoffset="-169.64"
                                />
                              </svg>
                              <div className="absolute inset-0 flex flex-col items-center justify-center">
                                <span className="text-xs font-bold text-white leading-none">62%</span>
                                <span className="text-[7px] text-slate-400 font-medium">total</span>
                              </div>
                            </div>

                            {/* Legend */}
                            <div className="space-y-1 text-[9px]">
                              <div className="flex items-center gap-1.5">
                                <span className="h-1.5 w-1.5 rounded-full bg-[#3b82f6]" />
                                <span className="text-slate-300">EMIs</span>
                                <span className="text-slate-400 font-medium ml-auto">38%</span>
                              </div>
                              <div className="flex items-center gap-1.5">
                                <span className="h-1.5 w-1.5 rounded-full bg-[#06b6d4]" />
                                <span className="text-slate-300">Subscriptions</span>
                                <span className="text-slate-400 font-medium ml-auto">22%</span>
                              </div>
                              <div className="flex items-center gap-1.5">
                                <span className="h-1.5 w-1.5 rounded-full bg-[#f43f5e]" />
                                <span className="text-slate-300">BNPL</span>
                                <span className="text-slate-400 font-medium ml-auto">15%</span>
                              </div>
                              <div className="flex items-center gap-1.5">
                                <span className="h-1.5 w-1.5 rounded-full bg-[#a855f7]" />
                                <span className="text-slate-300">Others</span>
                                <span className="text-slate-400 font-medium ml-auto">25%</span>
                              </div>
                            </div>
                          </div>

                          <div className="text-[8px] text-slate-400 text-center pt-1 border-t border-white/[0.04]">
                            Commitments account for 62% of capacity
                          </div>
                        </div>
                      </div>

                      {/* Disclaimer Footnote */}
                      <div className="text-[9px] text-slate-400 text-center tracking-tight">
                        * Illustrative demo metrics. Real insights reflect your synced statements.
                      </div>
                    </div>
                  </div>
                </div>

                {/* ── 3 FLOATING CALLOUT CARDS AROUND DASHBOARD ── */}

                {/* Callout 1 (Top Left): Hidden Subscriptions */}
                <motion.div
                  initial={reduceMotion ? false : { opacity: 0, scale: 0.88, y: -10 }}
                  animate={
                    reduceMotion
                      ? { opacity: 1, scale: 1, y: 0 }
                      : {
                          opacity: 1,
                          scale: 1,
                          y: [0, -4, 0],
                          transition: {
                            opacity: { duration: 0.5, delay: 0.55 },
                            scale: { duration: 0.5, delay: 0.55 },
                            y: { duration: 6, repeat: Infinity, ease: "easeInOut", delay: 0.55 },
                          },
                        }
                  }
                  whileHover={{ scale: 1.04 }}
                  onClick={() => openOverlay("subscriptions")}
                  className="hidden sm:flex absolute -top-4 -left-3 sm:-left-6 lg:-left-7 z-30 items-center gap-2.5 px-3 py-2 rounded-xl bg-[#0f172a]/95 border border-white/15 shadow-[0_12px_30px_rgba(0,0,0,0.65),0_0_20px_rgba(244,63,94,0.18)] backdrop-blur-xl transition-all cursor-pointer group"
                >
                  <div className="h-7 w-7 rounded-lg bg-rose-500/20 border border-rose-500/30 flex items-center justify-center text-rose-400">
                    <Bell size={13} />
                  </div>
                  <div className="text-left">
                    <p className="text-[11px] font-semibold text-white leading-tight">Hidden Subscriptions</p>
                    <p className="text-[9px] text-slate-400 leading-tight">2 unused subscriptions found</p>
                  </div>
                  <div className="h-6 w-6 rounded-full bg-blue-600/30 group-hover:bg-blue-600 flex items-center justify-center text-blue-300 group-hover:text-white transition-colors ml-1">
                    <ArrowRight size={10} />
                  </div>
                </motion.div>

                {/* Callout 2 (Top Right): What-If Simulator */}
                <motion.div
                  initial={reduceMotion ? false : { opacity: 0, scale: 0.88, y: -10 }}
                  animate={
                    reduceMotion
                      ? { opacity: 1, scale: 1, y: 0 }
                      : {
                          opacity: 1,
                          scale: 1,
                          y: [0, 4, 0],
                          transition: {
                            opacity: { duration: 0.5, delay: 0.65 },
                            scale: { duration: 0.5, delay: 0.65 },
                            y: { duration: 7, repeat: Infinity, ease: "easeInOut", delay: 0.65 },
                          },
                        }
                  }
                  whileHover={{ scale: 1.04 }}
                  onClick={() => openOverlay("what-if")}
                  className="hidden sm:flex absolute -top-5 -right-2 sm:-right-6 lg:-right-7 z-30 items-center gap-2.5 px-3 py-2 rounded-xl bg-[#0f172a]/95 border border-white/15 shadow-[0_12px_30px_rgba(0,0,0,0.65),0_0_20px_rgba(56,189,248,0.18)] backdrop-blur-xl transition-all cursor-pointer group"
                >
                  <div className="h-7 w-7 rounded-lg bg-blue-500/20 border border-blue-500/30 flex items-center justify-center text-blue-400">
                    <BarChart3 size={13} />
                  </div>
                  <div className="text-left">
                    <p className="text-[11px] font-semibold text-white leading-tight">What-If Simulator</p>
                    <p className="text-[9px] text-slate-400 leading-tight">See how new commitments affect exposure</p>
                  </div>
                  <div className="h-6 w-6 rounded-full bg-blue-600/30 group-hover:bg-blue-600 flex items-center justify-center text-blue-300 group-hover:text-white transition-colors ml-1">
                    <ArrowRight size={10} />
                  </div>
                </motion.div>

                {/* Callout 3 (Bottom Right): Financial Assistant */}
                <motion.div
                  initial={reduceMotion ? false : { opacity: 0, scale: 0.88, y: 10 }}
                  animate={
                    reduceMotion
                      ? { opacity: 1, scale: 1, y: 0 }
                      : {
                          opacity: 1,
                          scale: 1,
                          y: [0, -3.5, 0],
                          transition: {
                            opacity: { duration: 0.5, delay: 0.75 },
                            scale: { duration: 0.5, delay: 0.75 },
                            y: { duration: 6.5, repeat: Infinity, ease: "easeInOut", delay: 0.75 },
                          },
                        }
                  }
                  whileHover={{ scale: 1.04 }}
                  onClick={() => openOverlay("assistant")}
                  className="hidden sm:flex absolute -bottom-4 right-1 sm:-right-4 lg:-right-5 z-30 items-center gap-2.5 px-3.5 py-2.5 rounded-xl bg-[#0f172a]/95 border border-white/15 shadow-[0_12px_30px_rgba(0,0,0,0.65),0_0_20px_rgba(168,85,247,0.18)] backdrop-blur-xl transition-all cursor-pointer group"
                >
                  <div className="h-7 w-7 rounded-lg bg-purple-500/20 border border-purple-500/30 flex items-center justify-center text-purple-400">
                    <Bot size={13} />
                  </div>
                  <div className="text-left">
                    <p className="text-[11px] font-semibold text-white leading-tight">Financial Assistant</p>
                    <p className="text-[9px] text-slate-400 leading-tight">Ask questions about your spending</p>
                  </div>
                  <div className="h-6 w-6 rounded-full bg-blue-600/30 group-hover:bg-blue-600 flex items-center justify-center text-blue-300 group-hover:text-white transition-colors ml-1">
                    <ArrowRight size={10} />
                  </div>
                </motion.div>

              </motion.div>
            </div>

          </div>
        </div>

        {/* Hero Bottom Subtle Border/Fade */}
        <div className="h-px w-full bg-gradient-to-r from-transparent via-white/[0.08] to-transparent pointer-events-none" />
      </section>

            {/* ═════════════════════════════════════════════════════════════
          PREMIUM PROFESSIONAL FINTECH FOOTER
      ═════════════════════════════════════════════════════════════ */}
      <motion.footer
        initial={reduceMotion ? false : { opacity: 0, y: 16 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-40px" }}
        transition={{ duration: 0.6, ease: "easeOut" }}
        className="w-full border-t border-white/[0.06] bg-[#05070e] pt-14 pb-10 sm:pt-16 sm:pb-12 px-6 sm:px-10 lg:px-16 text-slate-400"
      >
        <div className="w-full max-w-[1440px] mx-auto space-y-12 sm:space-y-14">
          {/* Upper Footer: 3 Columns on Desktop */}
          <div className="grid grid-cols-1 md:grid-cols-12 gap-10 md:gap-8 lg:gap-12">
            
            {/* Column 1 — Brand */}
            <div className="md:col-span-6 lg:col-span-6 flex flex-col items-start space-y-4">
              <div
                className="flex items-center gap-1.5 cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-indigo-400 rounded-md"
                onClick={() => {
                  setActiveOverlay(null);
                  window.scrollTo({ top: 0, behavior: "smooth" });
                }}
                tabIndex={0}
                role="button"
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    setActiveOverlay(null);
                    window.scrollTo({ top: 0, behavior: "smooth" });
                  }
                }}
              >
                <FinSightLogo variant="full" size="md" showSparkle={false} />
                <span className="text-indigo-400 font-bold text-lg leading-none -ml-1">+</span>
              </div>

              <div className="space-y-2 max-w-sm">
                <p className="text-xs font-semibold uppercase tracking-wider text-indigo-400/90">
                  Financial Exposure Intelligence System
                </p>
                <p className="text-sm text-slate-400 leading-relaxed">
                  Turn transaction history into a clearer picture of recurring commitments and financial exposure.
                </p>
              </div>

              <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-white/[0.08] bg-white/[0.02] text-[11px] text-slate-400">
                <span className="h-1.5 w-1.5 rounded-full bg-indigo-400/80" />
                <span>Financial clarity, by design.</span>
              </div>
            </div>

            {/* Column 2 — Explore */}
            <div className="md:col-span-3 lg:col-span-3 flex flex-col space-y-3.5">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                Explore
              </h3>
              <ul className="space-y-2.5 text-sm">
                <li>
                  <button
                    type="button"
                    onClick={() => openOverlay("how-it-works")}
                    className="text-slate-400 hover:text-white transition-colors duration-150 cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-indigo-400 rounded-sm"
                  >
                    How It Works
                  </button>
                </li>
                <li>
                  <button
                    type="button"
                    onClick={() => {
                      setIntelligenceTab("subscriptions");
                      openOverlay("intelligence");
                    }}
                    className="text-slate-400 hover:text-white transition-colors duration-150 cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-indigo-400 rounded-sm"
                  >
                    Intelligence
                  </button>
                </li>
                <li>
                  <button
                    type="button"
                    onClick={() => openOverlay("what-if")}
                    className="text-slate-400 hover:text-white transition-colors duration-150 cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-indigo-400 rounded-sm"
                  >
                    What-If Simulator
                  </button>
                </li>
                <li>
                  <button
                    type="button"
                    onClick={() => openOverlay("assistant")}
                    className="text-slate-400 hover:text-white transition-colors duration-150 cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-indigo-400 rounded-sm"
                  >
                    Financial Assistant
                  </button>
                </li>
              </ul>
            </div>

            {/* Column 3 — Account */}
            <div className="md:col-span-3 lg:col-span-3 flex flex-col space-y-3.5">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                Account
              </h3>
              <ul className="space-y-2.5 text-sm">
                <li>
                  <button
                    type="button"
                    onClick={onLogin}
                    className="text-slate-400 hover:text-white transition-colors duration-150 cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-indigo-400 rounded-sm"
                  >
                    Sign In
                  </button>
                </li>
                <li>
                  <button
                    type="button"
                    onClick={onRegister}
                    className="text-slate-400 hover:text-white transition-colors duration-150 cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-indigo-400 rounded-sm"
                  >
                    Get Started
                  </button>
                </li>
                <li>
                  <button
                    type="button"
                    onClick={() => openOverlay("security")}
                    className="text-slate-400 hover:text-white transition-colors duration-150 cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-indigo-400 rounded-sm"
                  >
                    Security & Privacy
                  </button>
                </li>
              </ul>
            </div>

          </div>

          {/* Bottom Footer: Subtle Divider & Legal Disclaimer */}
          <div className="pt-6 sm:pt-8 border-t border-white/[0.06] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 sm:gap-6 text-xs text-slate-400">
            <p className="text-slate-400">
              &copy; 2026 FinSight. All rights reserved.
            </p>
            <p className="text-slate-400 sm:text-right text-[11px] sm:text-xs">
              Demonstrative numbers shown on public previews.
            </p>
          </div>
        </div>
      </motion.footer>

{/* ═════════════════════════════════════════════════════════════
          INTERACTIVE OVERLAYS (MODALS)
      ═════════════════════════════════════════════════════════════ */}
      <AnimatePresence>
        {activeOverlay && (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-black/80 backdrop-blur-md"
            onClick={(e) => {
              if (e.target === e.currentTarget) setActiveOverlay(null);
            }}
            role="dialog"
            aria-modal="true"
          >
            <motion.div
              initial={reduceMotion ? { opacity: 1 } : { opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={reduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0.95, y: 10 }}
              transition={{ duration: 0.2 }}
              className="relative w-full max-w-2xl max-h-[90vh] sm:max-h-[85vh] overflow-y-auto rounded-2xl bg-[#0b101e] border border-white/15 p-4 sm:p-6 md:p-8 text-left shadow-2xl text-slate-100 space-y-5 sm:space-y-6"
            >
              {/* Close Button */}
              <button
                type="button"
                onClick={() => setActiveOverlay(null)}
                className="absolute top-5 right-5 p-2 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
                aria-label="Close dialog"
              >
                <X size={18} />
              </button>

              {/* ── OVERLAY A: HOW IT WORKS ── */}
              {activeOverlay === "how-it-works" && (
                <div className="space-y-6">
                  <div>
                    <span className="text-[10px] font-mono uppercase tracking-[0.18em] text-indigo-400 font-semibold">
                      System Workflow
                    </span>
                    <h2 className="text-xl sm:text-2xl font-bold text-white tracking-tight mt-1">
                      How FinSight Uncovers Your Exposure
                    </h2>
                    <p className="text-sm text-slate-400 mt-2">
                      Four simple steps convert raw bank statement files into actionable recurring commitment intelligence.
                    </p>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="p-4 rounded-xl bg-white/[0.03] border border-white/10 space-y-2">
                      <div className="flex items-center gap-2">
                        <span className="h-6 w-6 rounded-full bg-indigo-500/20 text-indigo-400 font-bold text-xs flex items-center justify-center">1</span>
                        <h3 className="text-sm font-semibold text-white">Create Account</h3>
                      </div>
                      <p className="text-xs text-slate-400 leading-relaxed">
                        Sign up securely. All customer statements and analytics are partitioned into strict isolated tenant records.
                      </p>
                    </div>

                    <div className="p-4 rounded-xl bg-white/[0.03] border border-white/10 space-y-2">
                      <div className="flex items-center gap-2">
                        <span className="h-6 w-6 rounded-full bg-indigo-500/20 text-indigo-400 font-bold text-xs flex items-center justify-center">2</span>
                        <h3 className="text-sm font-semibold text-white">Import Statements</h3>
                      </div>
                      <p className="text-xs text-slate-400 leading-relaxed">
                        Upload standard PDF or CSV bank statements. Intelligent normalization automatically detects headers and dates.
                      </p>
                    </div>

                    <div className="p-4 rounded-xl bg-white/[0.03] border border-white/10 space-y-2">
                      <div className="flex items-center gap-2">
                        <span className="h-6 w-6 rounded-full bg-indigo-500/20 text-indigo-400 font-bold text-xs flex items-center justify-center">3</span>
                        <h3 className="text-sm font-semibold text-white">Automated Classification</h3>
                      </div>
                      <p className="text-xs text-slate-400 leading-relaxed">
                        Engines categorize repeating transactions into Subscriptions, ongoing EMIs, and staggered BNPL payments.
                      </p>
                    </div>

                    <div className="p-4 rounded-xl bg-white/[0.03] border border-white/10 space-y-2">
                      <div className="flex items-center gap-2">
                        <span className="h-6 w-6 rounded-full bg-indigo-500/20 text-indigo-400 font-bold text-xs flex items-center justify-center">4</span>
                        <h3 className="text-sm font-semibold text-white">Actionable Planning</h3>
                      </div>
                      <p className="text-xs text-slate-400 leading-relaxed">
                        View your Exposure Ratio (0-100%), explore hypothetical scenarios, or query your Copilot Assistant.
                      </p>
                    </div>
                  </div>

                  <div className="pt-2 flex justify-end gap-3">
                    <button
                      type="button"
                      onClick={() => setActiveOverlay(null)}
                      className="px-4 py-2 rounded-xl border border-white/15 text-xs font-medium text-slate-300 hover:text-white"
                    >
                      Close
                    </button>
                    <button
                      type="button"
                      onClick={onRegister}
                      className="px-5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold text-white shadow-md flex items-center gap-1.5"
                    >
                      Get Started Free <ArrowRight size={13} />
                    </button>
                  </div>
                </div>
              )}

              {/* ── OVERLAY B: INTELLIGENCE ── */}
              {activeOverlay === "intelligence" && (
                <div className="space-y-6">
                  <div>
                    <span className="text-[10px] font-mono uppercase tracking-[0.18em] text-cyan-400 font-semibold">
                      Analytics Engines
                    </span>
                    <h2 className="text-xl sm:text-2xl font-bold text-white tracking-tight mt-1">
                      Verified Financial Intelligence
                    </h2>
                    <p className="text-sm text-slate-400 mt-2">
                      FinSight uses deterministic rules and verified statistical models to surface hidden liabilities.
                    </p>
                  </div>

                  {/* Tabs */}
                  <div className="flex flex-wrap gap-2 border-b border-white/10 pb-3">
                    {(["subscriptions", "emis", "bnpl", "exposure"] as const).map((tab) => (
                      <button
                        key={tab}
                        type="button"
                        onClick={() => setIntelligenceTab(tab)}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition-colors ${
                          intelligenceTab === tab
                            ? "bg-indigo-600 text-white"
                            : "bg-white/5 text-slate-400 hover:text-white"
                        }`}
                      >
                        {tab === "emis" ? "EMIs & Loans" : tab === "bnpl" ? "BNPL Split" : tab}
                      </button>
                    ))}
                  </div>

                  {/* Tab Details */}
                  {intelligenceTab === "subscriptions" && (
                    <div className="space-y-3">
                      <h3 className="text-base font-semibold text-white flex items-center gap-2">
                        <Calendar size={16} className="text-purple-400" /> Subscription Intelligence
                      </h3>
                      <p className="text-xs text-slate-400 leading-relaxed">
                        Tracks recurring merchant billing cadence (weekly, monthly, quarterly, annual). Pinpoints price creep, unexpected renewals, and silent subscriptions eating your monthly capacity.
                      </p>
                      <ul className="space-y-1.5 text-xs text-slate-300">
                        <li className="flex items-center gap-2"><CheckCircle2 size={13} className="text-emerald-400 shrink-0" /> Automatic cadence detection & cadence variance monitoring</li>
                        <li className="flex items-center gap-2"><CheckCircle2 size={13} className="text-emerald-400 shrink-0" /> Free trial conversion warning flags</li>
                        <li className="flex items-center gap-2"><CheckCircle2 size={13} className="text-emerald-400 shrink-0" /> Unused or redundant service identification</li>
                      </ul>
                    </div>
                  )}

                  {intelligenceTab === "emis" && (
                    <div className="space-y-3">
                      <h3 className="text-base font-semibold text-white flex items-center gap-2">
                        <CreditCard size={16} className="text-blue-400" /> EMI & Debt Intelligence
                      </h3>
                      <p className="text-xs text-slate-400 leading-relaxed">
                        Analyzes loan installments (home, personal, vehicle, electronics) and quantifies the fixed amortized debt load locking your monthly liquidity.
                      </p>
                      <ul className="space-y-1.5 text-xs text-slate-300">
                        <li className="flex items-center gap-2"><CheckCircle2 size={13} className="text-emerald-400 shrink-0" /> Monthly installment aggregation and tenure tracking</li>
                        <li className="flex items-center gap-2"><CheckCircle2 size={13} className="text-emerald-400 shrink-0" /> Debt-to-income and debt-to-capacity ratios</li>
                        <li className="flex items-center gap-2"><CheckCircle2 size={13} className="text-emerald-400 shrink-0" /> End-of-tenure relief projection schedules</li>
                      </ul>
                    </div>
                  )}

                  {intelligenceTab === "bnpl" && (
                    <div className="space-y-3">
                      <h3 className="text-base font-semibold text-white flex items-center gap-2">
                        <Wallet size={16} className="text-amber-400" /> Buy-Now-Pay-Later (BNPL) Analysis
                      </h3>
                      <p className="text-xs text-slate-400 leading-relaxed">
                        Detects micro-installments, split-checkout obligations (Pay-in-3, Pay-in-4), and short-tenure commitments that bypass traditional credit monitoring.
                      </p>
                      <ul className="space-y-1.5 text-xs text-slate-300">
                        <li className="flex items-center gap-2"><CheckCircle2 size={13} className="text-emerald-400 shrink-0" /> Staggered payment schedule timeline alignment</li>
                        <li className="flex items-center gap-2"><CheckCircle2 size={13} className="text-emerald-400 shrink-0" /> Stacked micro-loan cashflow crunch alerts</li>
                        <li className="flex items-center gap-2"><CheckCircle2 size={13} className="text-emerald-400 shrink-0" /> Clear separation of optional vs mandatory checkout installments</li>
                      </ul>
                    </div>
                  )}

                  {intelligenceTab === "exposure" && (
                    <div className="space-y-3">
                      <h3 className="text-base font-semibold text-white flex items-center gap-2">
                        <PieChart size={16} className="text-rose-400" /> Financial Exposure Index
                      </h3>
                      <p className="text-xs text-slate-400 leading-relaxed">
                        Calculates your true commitment ratio: <span className="font-mono text-indigo-300">(Monthly Commitments / Monthly Capacity) × 100</span>. Classifies your vulnerability into Low, Moderate, Elevated, or Critical risk bands.
                      </p>
                      <ul className="space-y-1.5 text-xs text-slate-300">
                        <li className="flex items-center gap-2"><CheckCircle2 size={13} className="text-emerald-400 shrink-0" /> Realistic capacity based on historical net inflows</li>
                        <li className="flex items-center gap-2"><CheckCircle2 size={13} className="text-emerald-400 shrink-0" /> Transparent category breakdown across debt, utilities & subscriptions</li>
                        <li className="flex items-center gap-2"><CheckCircle2 size={13} className="text-emerald-400 shrink-0" /> Uncommitted safe-to-spend buffer calculation</li>
                      </ul>
                    </div>
                  )}

                  <div className="pt-2 flex justify-end gap-3">
                    <button
                      type="button"
                      onClick={() => setActiveOverlay(null)}
                      className="px-4 py-2 rounded-xl border border-white/15 text-xs font-medium text-slate-300 hover:text-white"
                    >
                      Close
                    </button>
                    <button
                      type="button"
                      onClick={onRegister}
                      className="px-5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold text-white shadow-md flex items-center gap-1.5"
                    >
                      Explore in FinSight <ArrowRight size={13} />
                    </button>
                  </div>
                </div>
              )}

              {/* ── OVERLAY C: WHAT-IF SIMULATOR ── */}
              {activeOverlay === "what-if" && (
                <div className="space-y-6">
                  <div>
                    <span className="text-[10px] font-mono uppercase tracking-[0.18em] text-teal-400 font-semibold">
                      Scenario Sandbox
                    </span>
                    <h2 className="text-xl sm:text-2xl font-bold text-white tracking-tight mt-1">
                      What-If Scenario Simulator
                    </h2>
                    <p className="text-sm text-slate-400 mt-2">
                      Test hypothetical financial commitments before you sign the contract or click subscribe.
                    </p>
                  </div>

                  <div className="p-4 rounded-xl bg-slate-900/80 border border-white/10 space-y-4">
                    <div className="flex items-center justify-between pb-3 border-b border-white/10">
                      <div>
                        <span className="text-xs text-slate-400">Current Exposure</span>
                        <p className="text-lg font-bold text-white">62% <span className="text-xs text-amber-400 font-normal">(Elevated)</span></p>
                      </div>
                      <div className="text-right">
                        <span className="text-xs text-slate-400">Available Capacity</span>
                        <p className="text-lg font-bold text-emerald-400">₹27,200</p>
                      </div>
                    </div>

                    <div className="space-y-2">
                      <span className="text-xs font-semibold text-slate-300">Simulate Adding a New Commitment:</span>
                      <div className="p-3 rounded-lg bg-white/5 border border-white/10 flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <CreditCard size={15} className="text-indigo-400" />
                          <span className="text-xs font-medium text-white">New Vehicle EMI</span>
                        </div>
                        <span className="text-xs font-bold text-rose-400">+₹8,500 /mo</span>
                      </div>
                    </div>

                    <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 flex items-center justify-between">
                      <span className="text-xs text-rose-300">Projected Exposure Impact:</span>
                      <span className="text-sm font-bold text-rose-400">74% → High Risk</span>
                    </div>
                  </div>

                  <div className="pt-2 flex justify-end gap-3">
                    <button
                      type="button"
                      onClick={() => setActiveOverlay(null)}
                      className="px-4 py-2 rounded-xl border border-white/15 text-xs font-medium text-slate-300 hover:text-white"
                    >
                      Close
                    </button>
                    <button
                      type="button"
                      onClick={onRegister}
                      className="px-5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold text-white shadow-md flex items-center gap-1.5"
                    >
                      Launch Simulator <ArrowRight size={13} />
                    </button>
                  </div>
                </div>
              )}

              {/* ── OVERLAY D: FINANCIAL ASSISTANT ── */}
              {activeOverlay === "assistant" && (
                <div className="space-y-6">
                  <div>
                    <span className="text-[10px] font-mono uppercase tracking-[0.18em] text-purple-400 font-semibold">
                      FinSight Copilot
                    </span>
                    <h2 className="text-xl sm:text-2xl font-bold text-white tracking-tight mt-1">
                      Context-Aware Financial Assistant
                    </h2>
                    <p className="text-sm text-slate-400 mt-2">
                      Ask natural language questions about your recurring obligations, upcoming debits, and spending capacity.
                    </p>
                  </div>

                  <div className="space-y-3">
                    <p className="text-xs font-semibold text-slate-300">Example Questions You Can Ask:</p>
                    <div className="space-y-2">
                      <div className="p-2.5 rounded-lg bg-white/5 border border-white/10 text-xs text-slate-200">
                        💬 "How much do I pay across all entertainment subscriptions every month?"
                      </div>
                      <div className="p-2.5 rounded-lg bg-white/5 border border-white/10 text-xs text-slate-200">
                        💬 "When is my next major loan EMI due, and how much will remain?"
                      </div>
                      <div className="p-2.5 rounded-lg bg-white/5 border border-white/10 text-xs text-slate-200">
                        💬 "Can I safely afford an additional ₹5,000 monthly commitment without exceeding 70% exposure?"
                      </div>
                    </div>
                  </div>

                  <div className="p-3.5 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-xs text-indigo-300">
                    <span className="font-semibold text-white">Deterministic & Grounded:</span> The assistant computes answers directly from your parsed transaction records and verified accounting rules — never from random guesses.
                  </div>

                  <div className="pt-2 flex justify-end gap-3">
                    <button
                      type="button"
                      onClick={() => setActiveOverlay(null)}
                      className="px-4 py-2 rounded-xl border border-white/15 text-xs font-medium text-slate-300 hover:text-white"
                    >
                      Close
                    </button>
                    <button
                      type="button"
                      onClick={onRegister}
                      className="px-5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold text-white shadow-md flex items-center gap-1.5"
                    >
                      Try Financial Assistant <ArrowRight size={13} />
                    </button>
                  </div>
                </div>
              )}

              {/* ── OVERLAY E: SECURITY & PRIVACY ── */}
              {activeOverlay === "security" && (
                <div className="space-y-6">
                  <div>
                    <span className="text-[10px] font-mono uppercase tracking-[0.18em] text-emerald-400 font-semibold">
                      Verified Architecture
                    </span>
                    <h2 className="text-xl sm:text-2xl font-bold text-white tracking-tight mt-1">
                      Enterprise Security & Privacy
                    </h2>
                    <p className="text-sm text-slate-400 mt-2">
                      Your financial records and statements remain strictly isolated, encrypted, and in your direct control.
                    </p>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="p-4 rounded-xl bg-white/[0.03] border border-white/10 space-y-1.5">
                      <div className="flex items-center gap-2 text-emerald-400">
                        <Lock size={15} />
                        <h3 className="text-xs font-semibold text-white">Isolated Tenant Model</h3>
                      </div>
                      <p className="text-[11px] text-slate-400 leading-relaxed">
                        Each registered user is assigned a distinct tenant ID. Database queries enforce strict user foreign-key boundaries.
                      </p>
                    </div>

                    <div className="p-4 rounded-xl bg-white/[0.03] border border-white/10 space-y-1.5">
                      <div className="flex items-center gap-2 text-indigo-400">
                        <ShieldCheck size={15} />
                        <h3 className="text-xs font-semibold text-white">Salted Password & OTP</h3>
                      </div>
                      <p className="text-[11px] text-slate-400 leading-relaxed">
                        Passwords use cryptographically salted scrypt hashes. Resets use single-use, 5-minute salted SHA-256 OTPs with attempt lockout.
                      </p>
                    </div>

                    <div className="p-4 rounded-xl bg-white/[0.03] border border-white/10 space-y-1.5">
                      <div className="flex items-center gap-2 text-blue-400">
                        <Activity size={15} />
                        <h3 className="text-xs font-semibold text-white">Instant Session Invalidation</h3>
                      </div>
                      <p className="text-[11px] text-slate-400 leading-relaxed">
                        Whenever your credentials update, session versions increment, terminating all active JWT access tokens globally.
                      </p>
                    </div>

                    <div className="p-4 rounded-xl bg-white/[0.03] border border-white/10 space-y-1.5">
                      <div className="flex items-center gap-2 text-teal-400">
                        <FileText size={15} />
                        <h3 className="text-xs font-semibold text-white">Stateless Statement Parsing</h3>
                      </div>
                      <p className="text-[11px] text-slate-400 leading-relaxed">
                        Uploaded bank statements are processed in memory during import. Bank login credentials are never requested or stored.
                      </p>
                    </div>
                  </div>

                  <div className="pt-2 flex justify-end gap-3">
                    <button
                      type="button"
                      onClick={() => setActiveOverlay(null)}
                      className="px-4 py-2 rounded-xl border border-white/15 text-xs font-medium text-slate-300 hover:text-white"
                    >
                      Close
                    </button>
                    <button
                      type="button"
                      onClick={onRegister}
                      className="px-5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold text-white shadow-md flex items-center gap-1.5"
                    >
                      Create Secure Account <ArrowRight size={13} />
                    </button>
                  </div>
                </div>
              )}

              {/* ── OVERLAY F: WATCH DEMO ── */}
              {activeOverlay === "demo" && (
                <div className="space-y-6">
                  <div>
                    <span className="text-[10px] font-mono uppercase tracking-[0.18em] text-indigo-400 font-semibold">
                      Interactive Product Tour
                    </span>
                    <h2 className="text-xl sm:text-2xl font-bold text-white tracking-tight mt-1">
                      FinSight In Action: 60-Second Walkthrough
                    </h2>
                    <p className="text-sm text-slate-400 mt-2">
                      Click through the steps below to experience how FinSight uncovers financial exposure.
                    </p>
                  </div>

                  {/* Step Selector */}
                  <div className="flex gap-2">
                    {[
                      "1. Upload Statement",
                      "2. Exposure Analysis",
                      "3. What-If Simulation",
                    ].map((label, idx) => (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => setDemoStep(idx)}
                        className={`flex-1 py-2 text-xs font-semibold rounded-lg transition-all ${
                          demoStep === idx
                            ? "bg-indigo-600 text-white shadow-md"
                            : "bg-white/5 text-slate-400 hover:text-white"
                        }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>

                  {/* Step 0: Upload */}
                  {demoStep === 0 && (
                    <div className="p-6 rounded-xl bg-slate-900/90 border border-white/10 text-center space-y-3">
                      <div className="mx-auto h-12 w-12 rounded-full bg-indigo-500/20 text-indigo-400 flex items-center justify-center">
                        <FileText size={24} />
                      </div>
                      <h4 className="text-sm font-semibold text-white">Drop your bank statement (PDF or CSV)</h4>
                      <p className="text-xs text-slate-400 max-w-md mx-auto">
                        FinSight normalizes merchant labels, parses debit rows, and isolates recurring patterns in seconds.
                      </p>
                      <div className="inline-block px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-400 text-[11px] font-medium border border-emerald-500/20">
                        ✓ 38 recurring commitments detected
                      </div>
                    </div>
                  )}

                  {/* Step 1: Exposure */}
                  {demoStep === 1 && (
                    <div className="p-6 rounded-xl bg-slate-900/90 border border-white/10 space-y-3">
                      <div className="flex items-center justify-between">
                        <h4 className="text-sm font-semibold text-white">Calculated Exposure: 62%</h4>
                        <span className="text-[10px] font-bold text-rose-400 bg-rose-500/20 px-2 py-0.5 rounded">High Exposure</span>
                      </div>
                      <p className="text-xs text-slate-400">
                        Monthly commitments total ₹42,800 against ₹70,000 capacity. Your uncommitted safe margin is ₹27,200.
                      </p>
                      <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
                        <div className="h-full bg-gradient-to-r from-cyan-400 to-rose-500 rounded-full" style={{ width: "62%" }} />
                      </div>
                    </div>
                  )}

                  {/* Step 2: What-If */}
                  {demoStep === 2 && (
                    <div className="p-6 rounded-xl bg-slate-900/90 border border-white/10 space-y-3">
                      <h4 className="text-sm font-semibold text-white">Interactive Scenario Sandbox</h4>
                      <p className="text-xs text-slate-400">
                        Simulate adding a ₹4,500/mo gym membership or canceling 3 redundant streaming services. Real-time graphs immediately update your risk band.
                      </p>
                      <div className="flex items-center justify-between text-xs p-2.5 rounded bg-white/5 border border-white/10">
                        <span>Canceling 2 Unused Subscriptions:</span>
                        <span className="font-bold text-emerald-400">+₹948/mo Recovered</span>
                      </div>
                    </div>
                  )}

                  <div className="pt-2 flex justify-between items-center">
                    <button
                      type="button"
                      onClick={() => setDemoStep((s) => (s > 0 ? s - 1 : 2))}
                      className="text-xs text-slate-400 hover:text-white"
                    >
                      Previous
                    </button>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => setActiveOverlay(null)}
                        className="px-4 py-2 rounded-xl border border-white/15 text-xs font-medium text-slate-300 hover:text-white"
                      >
                        Close
                      </button>
                      <button
                        type="button"
                        onClick={onRegister}
                        className="px-5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold text-white shadow-md flex items-center gap-1.5"
                      >
                        Get Started with FinSight <ArrowRight size={13} />
                      </button>
                    </div>
                  </div>
                </div>
              )}

            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
