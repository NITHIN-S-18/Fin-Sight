import React from "react";

interface FinSightLogoProps {
  variant?: "full" | "mark" | "compact";
  size?: "sm" | "md" | "lg" | "xl";
  className?: string;
  showSparkle?: boolean;
}

export function FinSightLogo({
  variant = "full",
  size = "md",
  className = "",
  showSparkle = false,
}: FinSightLogoProps) {
  // Dimension definitions
  const markDimensions = {
    sm: "w-6 h-6",
    md: "w-8 h-8",
    lg: "w-10 h-10",
    xl: "w-12 h-12",
  };

  const textSizes = {
    sm: "text-base",
    md: "text-lg",
    lg: "text-xl",
    xl: "text-2xl",
  };

  // Modern SVG Ribbon F Mark with Glowing Financial Bars
  const LogoMark = (
    <div
      className={`relative flex items-center justify-center shrink-0 ${markDimensions[size]} ${className}`}
    >
      <svg
        viewBox="0 0 100 100"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="w-full h-full drop-shadow-[0_2px_10px_rgba(99,102,241,0.35)]"
      >
        <defs>
          {/* Main Top Ribbon Gradient */}
          <linearGradient id="fTopGradient" x1="15%" y1="10%" x2="95%" y2="50%">
            <stop offset="0%" stopColor="#38BDF8" />
            <stop offset="45%" stopColor="#6366F1" />
            <stop offset="100%" stopColor="#C084FC" />
          </linearGradient>

          {/* Inner Loop Gradient */}
          <linearGradient id="fInnerGradient" x1="25%" y1="40%" x2="85%" y2="80%">
            <stop offset="0%" stopColor="#818CF8" />
            <stop offset="60%" stopColor="#A855F7" />
            <stop offset="100%" stopColor="#60A5FA" />
          </linearGradient>

          {/* Spine Glow Gradient */}
          <linearGradient id="fSpineGradient" x1="10%" y1="15%" x2="40%" y2="90%">
            <stop offset="0%" stopColor="#38BDF8" stopOpacity="0.95" />
            <stop offset="50%" stopColor="#4F46E5" stopOpacity="0.9" />
            <stop offset="100%" stopColor="#3B82F6" stopOpacity="0.85" />
          </linearGradient>

          {/* Financial Bars Gradients */}
          <linearGradient id="bar1Grad" x1="0%" y1="100%" x2="0%" y2="0%">
            <stop offset="0%" stopColor="#0284C7" />
            <stop offset="100%" stopColor="#38BDF8" />
          </linearGradient>
          <linearGradient id="bar2Grad" x1="0%" y1="100%" x2="0%" y2="0%">
            <stop offset="0%" stopColor="#4F46E5" />
            <stop offset="100%" stopColor="#60A5FA" />
          </linearGradient>
          <linearGradient id="bar3Grad" x1="0%" y1="100%" x2="0%" y2="0%">
            <stop offset="0%" stopColor="#7C3AED" />
            <stop offset="100%" stopColor="#C084FC" />
          </linearGradient>

          {/* Soft Glow Filter */}
          <filter id="glowFilter" x="-10%" y="-10%" width="120%" height="120%">
            <feGaussianBlur stdDeviation="2" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>

        {/* Back glow layer */}
        <path
          d="M24 82 C 16 65, 18 36, 32 22 C 45 9, 74 12, 86 16 C 89 17, 85 24, 76 25 C 56 28, 38 31, 32 45 C 37 41, 56 40, 72 43 C 78 44, 76 52, 68 53 C 54 55, 38 60, 32 76 C 29 82, 26 84, 24 82 Z"
          fill="url(#fTopGradient)"
          opacity="0.25"
          filter="url(#glowFilter)"
        />

        {/* Financial Growth Bars inside the F curve */}
        {/* Bar 1 (Shortest - Cyan) */}
        <rect x="42" y="65" width="6" height="15" rx="3" fill="url(#bar1Grad)" />
        {/* Bar 2 (Medium - Blue) */}
        <rect x="52" y="55" width="6" height="25" rx="3" fill="url(#bar2Grad)" />
        {/* Bar 3 (Tallest - Violet) */}
        <rect x="62" y="44" width="6" height="36" rx="3" fill="url(#bar3Grad)" />

        {/* F Swoop Stem / Spine */}
        <path
          d="M 23 83 C 16 66, 17 38, 32 23 C 44 11, 74 13, 86 17 C 88 18, 86 24, 78 25 C 57 28, 38 31, 32 46 C 30 52, 28 66, 33 76 C 30 81, 26 84, 23 83 Z"
          fill="url(#fSpineGradient)"
        />

        {/* Upper Wing / Horizontal Top Bar */}
        <path
          d="M 31 24 C 44 12, 73 13, 85 17 C 88 18, 87 23, 80 25 C 60 28, 41 30, 33 44 C 31 36, 30 29, 31 24 Z"
          fill="url(#fTopGradient)"
        />

        {/* Middle Crossbar Fold */}
        <path
          d="M 31 46 C 41 42, 60 41, 73 44 C 77 45, 75 51, 68 53 C 56 55, 41 58, 33 72 C 31 64, 30 54, 31 46 Z"
          fill="url(#fInnerGradient)"
        />

        {/* Specular Edge Highlights for Glass 3D Effect */}
        <path
          d="M 33 24 C 45 13, 73 14, 85 18"
          stroke="#FFFFFF"
          strokeWidth="1.2"
          strokeLinecap="round"
          opacity="0.6"
        />
        <path
          d="M 34 46 C 44 43, 62 42, 73 45"
          stroke="#FFFFFF"
          strokeWidth="1"
          strokeLinecap="round"
          opacity="0.5"
        />
      </svg>
    </div>
  );

  if (variant === "mark") {
    return LogoMark;
  }

  return (
    <div className={`flex items-center gap-2.5 select-none ${className}`}>
      {LogoMark}
      <div className="flex items-center gap-1.5 leading-none">
        <span
          className={`font-semibold tracking-tight ${textSizes[size]} text-slate-900 dark:text-white transition-colors`}
          style={{ letterSpacing: "-0.02em" }}
        >
          Fin
          <span className="bg-gradient-to-r from-blue-500 via-indigo-400 to-purple-400 bg-clip-text text-transparent font-bold">
            Sight
          </span>
        </span>

        {showSparkle && (
          <span className="inline-flex items-center justify-center text-indigo-400 dark:text-indigo-300 opacity-90 animate-pulse">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 0L14.59 9.41L24 12L14.59 14.59L12 24L9.41 14.59L0 12L9.41 9.41L12 0Z" />
            </svg>
          </span>
        )}
      </div>
    </div>
  );
}
