import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  LayoutDashboard,
  ArrowLeftRight,
  CreditCard,
  RefreshCw,
  BarChart3,
  Wand2,
  MessageCircle,
  Settings,
  ChevronLeft,
  ChevronRight,
  Search,
  LogOut,
  X,
  Sparkles,
  Command,
} from "lucide-react";
import { FinSightLogo } from "./FinSightLogo";
import { AuthenticatedUser, getAvatarUrl } from "../../api/client";

export type AppPage =
  | "dashboard"
  | "transactions"
  | "commitments"
  | "intelligence"
  | "what-if"
  | "assistant"
  | "settings";

interface NavItem {
  id: AppPage;
  label: string;
  subtitle: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
}

const NAV_ITEMS: NavItem[] = [
  {
    id: "dashboard",
    label: "Dashboard",
    subtitle: "Overview & Insights",
    icon: LayoutDashboard,
  },
  {
    id: "transactions",
    label: "Transactions",
    subtitle: "All your transactions",
    icon: ArrowLeftRight,
  },
  {
    id: "commitments",
    label: "Recurring Payments",
    subtitle: "Subscriptions, EMIs, Bills",
    icon: RefreshCw,
  },
  {
    id: "intelligence",
    label: "Intelligence",
    subtitle: "AI Financial Analysis",
    icon: BarChart3,
  },
  {
    id: "what-if",
    label: "What-If Simulator",
    subtitle: "Plan your next move",
    icon: Wand2,
  },
  {
    id: "assistant",
    label: "Assistant",
    subtitle: "Ask FinSight",
    icon: MessageCircle,
  },
  {
    id: "settings",
    label: "Settings",
    subtitle: "Account & Preferences",
    icon: Settings,
  },
];

interface AppSidebarProps {
  page: AppPage;
  onNavigate: (p: AppPage) => void;
  onLogout: () => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
  user: AuthenticatedUser;
  mobileOpen?: boolean;
  onCloseMobile?: () => void;
}

export function AppSidebar({
  page,
  onNavigate,
  onLogout,
  collapsed,
  onToggleCollapse,
  user,
  mobileOpen = false,
  onCloseMobile,
}: AppSidebarProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const fallbackName = user.email.split("@")[0].charAt(0).toUpperCase() + user.email.split("@")[0].slice(1);
  const userName = user.display_name?.trim() || fallbackName;
  const userAvatar = getAvatarUrl(user.avatar_url);

  const initials = userName
    ? userName.slice(0, 2).toUpperCase()
    : user.email.slice(0, 2).toUpperCase();

  const filteredNavItems = searchQuery.trim()
    ? NAV_ITEMS.filter(
        (item) =>
          item.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
          item.subtitle.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : NAV_ITEMS;

  // Handle Ctrl+K shortcut to focus search
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        const searchInput = document.getElementById("sidebar-search-input");
        searchInput?.focus();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const sidebarContent = (isDrawer = false) => (
    <div className="flex flex-col h-full bg-[#090e1c] text-slate-100 overflow-hidden select-none border-r border-white/[0.08] relative">
      {/* ─────────────────────────────────────────────────────────────
          HEADER / BRANDING
      ───────────────────────────────────────────────────────────── */}
      <div
        className={`flex items-center justify-between px-4 py-4 h-16 shrink-0 border-b border-white/[0.06] ${
          collapsed && !isDrawer ? "justify-center px-2" : ""
        }`}
      >
        {(!collapsed || isDrawer) ? (
          <button
            type="button"
            onClick={() => onNavigate("dashboard")}
            className="flex items-center gap-2 cursor-pointer group bg-transparent border-0 p-0 text-left"
            aria-label="Go to dashboard"
          >
            <FinSightLogo variant="full" size="md" showSparkle={true} />
          </button>
        ) : (
          <button
            type="button"
            onClick={() => onNavigate("dashboard")}
            className="cursor-pointer hover:scale-105 transition-transform bg-transparent border-0 p-0"
            title="FinSight Dashboard"
            aria-label="Go to dashboard"
          >
            <FinSightLogo variant="mark" size="md" />
          </button>
        )}

        {isDrawer ? (
          <button
            type="button"
            onClick={onCloseMobile}
            className="p-1.5 rounded-xl text-slate-400 hover:text-white hover:bg-white/[0.08] transition-colors"
            title="Close menu"
            aria-label="Close navigation menu"
          >
            <X size={18} />
          </button>
        ) : (
          <button
            onClick={onToggleCollapse}
            className={`w-7 h-7 flex items-center justify-center rounded-lg text-slate-400 hover:text-white hover:bg-white/[0.08] transition-colors shrink-0 ${
              collapsed ? "mt-2 mx-auto" : "ml-auto"
            }`}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
          </button>
        )}
      </div>

      {/* ─────────────────────────────────────────────────────────────
          SEARCH BAR (when expanded or in drawer)
      ───────────────────────────────────────────────────────────── */}
      {(!collapsed || isDrawer) && (
        <div className="px-3 pt-3 pb-2 shrink-0">
          <div className="relative flex items-center rounded-xl bg-[#0f172a] border border-white/10 focus-within:border-indigo-500/50 px-3 py-2 transition-all shadow-inner">
            <Search size={14} className="text-slate-400 shrink-0 mr-2" />
            <input
              id="sidebar-search-input"
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search anything..."
              className="w-full bg-transparent text-xs text-white placeholder-slate-500 focus:outline-none"
            />
            {searchQuery ? (
              <button
                type="button"
                onClick={() => setSearchQuery("")}
                aria-label="Clear navigation search"
                className="text-slate-500 hover:text-white shrink-0 ml-1"
              >
                <X size={12} />
              </button>
            ) : (
              <span className="flex items-center gap-0.5 text-[10px] font-mono text-slate-400 bg-white/[0.06] border border-white/10 px-1.5 py-0.5 rounded ml-1 shrink-0">
                <Command size={9} />
                <span>K</span>
              </span>
            )}
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────
          NAVIGATION ITEMS
      ───────────────────────────────────────────────────────────── */}
      <nav className="flex-1 px-3 py-2 space-y-1 overflow-y-auto scrollbar-none">
        {filteredNavItems.map((item) => {
          const active = page === item.id;
          const Icon = item.icon;

          if (collapsed && !isDrawer) {
            return (
              <button
                key={item.id}
                onClick={() => {
                  onNavigate(item.id);
                  onCloseMobile?.();
                }}
                title={`${item.label} — ${item.subtitle}`}
                className={`relative w-full flex items-center justify-center p-3 rounded-xl transition-all group ${
                  active
                    ? "bg-gradient-to-r from-indigo-950/80 to-indigo-900/40 border border-indigo-500/40 text-white shadow-[0_0_15px_rgba(99,102,241,0.25)]"
                    : "text-slate-400 hover:text-white hover:bg-white/[0.04]"
                }`}
              >
                {active && (
                  <span className="absolute left-0 top-2 bottom-2 w-1 rounded-r-full bg-gradient-to-b from-cyan-400 to-indigo-500" />
                )}
                <Icon
                  size={18}
                  className={`transition-colors ${
                    active ? "text-cyan-300" : "group-hover:text-slate-200"
                  }`}
                />
              </button>
            );
          }

          return (
            <button
              key={item.id}
              onClick={() => {
                onNavigate(item.id);
                onCloseMobile?.();
              }}
              className={`w-full text-left flex items-center gap-3 px-3 py-2.5 rounded-2xl transition-all relative group ${
                active
                  ? "bg-gradient-to-r from-indigo-950/70 to-indigo-900/30 border border-indigo-500/35 text-white shadow-[0_0_18px_rgba(99,102,241,0.18)]"
                  : "text-slate-400 hover:text-white hover:bg-white/[0.04] border border-transparent"
              }`}
            >
              {active && (
                <span className="absolute left-1.5 top-2.5 bottom-2.5 w-1 rounded-full bg-gradient-to-b from-cyan-400 to-indigo-500 shadow-[0_0_8px_rgba(56,189,248,0.6)]" />
              )}

              <div
                className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 transition-colors ${
                  active
                    ? "bg-indigo-600/25 border border-indigo-400/30 text-cyan-300"
                    : "bg-white/[0.03] group-hover:bg-white/[0.08] text-slate-400 group-hover:text-slate-200"
                }`}
              >
                <Icon size={16} />
              </div>

              <div className="flex-1 min-w-0">
                <p
                  className={`text-xs font-semibold leading-tight truncate ${
                    active ? "text-white" : "text-slate-300 group-hover:text-white"
                  }`}
                >
                  {item.label}
                </p>
                <p
                  className={`text-[11px] leading-tight truncate mt-0.5 ${
                    active ? "text-indigo-300/80" : "text-slate-400"
                  }`}
                >
                  {item.subtitle}
                </p>
              </div>

              {isDrawer && (
                <ChevronRight
                  size={14}
                  className={`shrink-0 ${
                    active ? "text-indigo-400" : "text-slate-600 group-hover:text-slate-400"
                  }`}
                />
              )}
            </button>
          );
        })}
      </nav>

      {/* ─────────────────────────────────────────────────────────────
          BOTTOM PROFILE & ACTIONS
      ───────────────────────────────────────────────────────────── */}
      <div className="p-3 border-t border-white/[0.06] bg-[#090e1c] shrink-0 space-y-2">
        {(!collapsed || isDrawer) ? (
          <>
            {/* User Profile Card */}
            <button
              type="button"
              onClick={() => {
                onNavigate("settings");
                onCloseMobile?.();
              }}
              className="w-full flex items-center gap-3 p-2.5 rounded-2xl bg-[#0f172a] hover:bg-[#1e293b]/80 border border-white/10 hover:border-indigo-500/30 transition-all cursor-pointer group shadow-sm text-left"
              title="View settings and profile"
              aria-label="Open settings and profile"
            >
              {userAvatar ? (
                <img
                  src={userAvatar}
                  alt={userName}
                  className="w-8 h-8 rounded-full object-cover border border-indigo-400/40 shrink-0"
                />
              ) : (
                <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-indigo-700 to-indigo-500 text-white font-bold text-xs flex items-center justify-center shrink-0 border border-white/20 shadow-inner">
                  {initials}
                </div>
              )}

              <div className="flex-1 min-w-0">
                <p className="text-xs font-semibold text-white truncate leading-tight group-hover:text-indigo-300 transition-colors">
                  {userName}
                </p>
                <p className="text-[11px] text-slate-400 truncate leading-tight mt-0.5 font-mono">
                  {user.email}
                </p>
              </div>

              <ChevronRight
                size={14}
                className="text-slate-400 group-hover:text-slate-200 transition-colors shrink-0"
              />
            </button>

            {/* Mobile Dedicated Sign Out Button */}
            {isDrawer && (
              <button
                type="button"
                onClick={onLogout}
                className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl border border-rose-500/30 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 hover:text-rose-300 text-xs font-medium transition-all"
                aria-label="Sign out"
              >
                <LogOut size={13} />
                <span>Sign Out</span>
              </button>
            )}
          </>
        ) : (
          /* Collapsed User Avatar */
          <div className="flex flex-col items-center gap-2 py-1">
            <button
              type="button"
              onClick={() => onNavigate("settings")}
              className="relative rounded-full focus:outline-none group"
              title={`${userName} (${user.email})`}
              aria-label="Open settings and profile"
            >
              {userAvatar ? (
                <img
                  src={userAvatar}
                  alt={userName}
                  className="w-8 h-8 rounded-full object-cover border border-indigo-400/40"
                />
              ) : (
                <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-indigo-700 to-indigo-500 text-white font-bold text-[11px] flex items-center justify-center border border-white/20">
                  {initials}
                </div>
              )}
              <span className="absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full bg-emerald-400 border-2 border-[#090e1c]" />
            </button>
          </div>
        )}
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop / Tablet Sidebar */}
      <aside
        className={`hidden md:flex flex-col h-screen shrink-0 transition-all duration-300 z-30 ${
          collapsed ? "w-[68px]" : "w-[260px] xl:w-[275px]"
        }`}
      >
        {sidebarContent(false)}
      </aside>

      {/* Mobile Slide-Over Drawer */}
      <AnimatePresence>
        {mobileOpen && (
          <div className="fixed inset-0 z-50 md:hidden flex">
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={onCloseMobile}
              className="fixed inset-0 bg-black/70 backdrop-blur-sm"
            />

            {/* Slide drawer */}
            <motion.div
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ type: "spring", damping: 25, stiffness: 280 }}
              className="relative w-[285px] max-w-[85vw] h-full shadow-2xl z-10"
            >
              {sidebarContent(true)}
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </>
  );
}
