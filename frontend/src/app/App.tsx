import React, { lazy, Suspense, useState, useEffect } from "react";
import { ThemeProvider, useTheme } from "@figma/astraui";
import {
  Sun,
  Moon,
  Monitor,
  Menu,
  MessageCircle,
} from "lucide-react";
import { motion, AnimatePresence, useReducedMotion } from "motion/react";

import { LandingPage } from "./LandingPage";
import { LoginPage, RegisterPage, ForgotPasswordPage, ResetPasswordPage } from "./AuthPages";
import { UploadPage } from "./UploadPage";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { AppSidebar, AppPage } from "./components/AppSidebar";
import {
  AuthenticatedUser,
  authApi,
  clearStoredAccessToken,
  getStoredAccessToken,
  transactionApi,
} from "../api/client";

type AuthView = "landing" | "login" | "register" | "forgot" | "reset";
type Theme = "light" | "dark" | "system";
type AnyIcon = React.ComponentType<{ size?: number; className?: string }>;

const DashboardPage = lazy(() => import("./DashboardPage").then(({ DashboardPage }) => ({ default: DashboardPage })));
const TransactionsPage = lazy(() => import("./TransactionsPage").then(({ TransactionsPage }) => ({ default: TransactionsPage })));
const CommitmentsPage = lazy(() => import("./CommitmentsPage").then(({ CommitmentsPage }) => ({ default: CommitmentsPage })));
const IntelligencePage = lazy(() => import("./IntelligencePage").then(({ IntelligencePage }) => ({ default: IntelligencePage })));
const WhatIfPage = lazy(() => import("./WhatIfPage").then(({ WhatIfPage }) => ({ default: WhatIfPage })));
const AssistantPage = lazy(() => import("./AssistantPage").then(({ AssistantPage }) => ({ default: AssistantPage })));
const SettingsPage = lazy(() => import("./SettingsPage").then(({ SettingsPage }) => ({ default: SettingsPage })));

// ─────────────────────────────────────────────────────────────
// Page Titles
// ─────────────────────────────────────────────────────────────
const PAGE_TITLES: Record<AppPage, string> = {
  dashboard: "Dashboard",
  transactions: "Transactions",
  commitments: "Recurring Payments",
  intelligence: "Financial Intelligence",
  "what-if": "What-If Simulator",
  assistant: "AI Assistant",
  settings: "Settings",
};

// ─────────────────────────────────────────────────────────────
// Top header bar with responsive hamburger & theme switcher
// ─────────────────────────────────────────────────────────────
function AppHeader({
  page,
  theme,
  onThemeChange,
  onAskAssistant,
  onOpenMobile,
}: {
  page: AppPage;
  theme: Theme;
  onThemeChange: (t: Theme) => void;
  onAskAssistant?: (q?: string) => void;
  onOpenMobile?: () => void;
}) {
  const reduceMotion = useReducedMotion();
  const themeOptions: { value: Theme; label: string; icon: AnyIcon }[] = [
    { value: "light", label: "Light", icon: Sun as AnyIcon },
    { value: "system", label: "System", icon: Monitor as AnyIcon },
    { value: "dark", label: "Dark", icon: Moon as AnyIcon },
  ];

  return (
    <header className="h-14 shrink-0 flex items-center justify-between px-3 sm:px-6 bg-card/90 dark:bg-[#090e1c]/90 backdrop-blur-md border-b border-border dark:border-white/[0.08] z-20 transition-colors">
      <div className="flex items-center gap-2 sm:gap-3 min-w-0">
        {/* Mobile menu hamburger button */}
        {onOpenMobile && (
          <button
            onClick={onOpenMobile}
            className="md:hidden p-1.5 rounded-xl text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            title="Open menu"
            aria-label="Open navigation menu"
          >
            <Menu size={19} />
          </button>
        )}
        <h1 className="text-sm font-semibold text-foreground tracking-tight truncate max-w-[130px] min-[400px]:max-w-[180px] sm:max-w-none">
          {PAGE_TITLES[page]}
        </h1>
      </div>

      <div className="flex items-center gap-1.5 sm:gap-3 shrink-0">
        {/* Polished glossy theme toggle */}
        <div
          className="flex items-center rounded-full border border-border dark:border-white/10 bg-muted/60 dark:bg-[#0f172a]/80 backdrop-blur-md p-1 gap-1 shadow-inner shadow-black/10 dark:shadow-black/30"
          aria-label="Theme mode"
        >
          {themeOptions.map(({ value, label, icon: Icon }) => {
            const isActive = theme === value;
            return (
              <motion.button
                key={value}
                onClick={() => onThemeChange(value)}
                title={`${label} mode`}
                aria-label={`${label} mode`}
                aria-pressed={isActive}
                whileHover={reduceMotion ? undefined : { scale: 1.05 }}
                whileTap={reduceMotion ? undefined : { scale: 0.95 }}
                className={`relative flex h-7 w-7 items-center justify-center rounded-full transition-colors z-10 ${
                  isActive
                    ? "text-foreground dark:text-white"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {isActive && (
                  <motion.span
                    layoutId="app-theme-active-indicator"
                    className="absolute inset-0 rounded-full bg-card dark:bg-slate-800/95 border border-border dark:border-white/15 shadow-[0_0_12px_rgba(99,102,241,0.25)]"
                    transition={{ type: "spring", stiffness: 450, damping: 32 }}
                  />
                )}
                <motion.span
                  animate={
                    isActive && !reduceMotion
                      ? { rotate: [0, 10, 0], scale: [1, 1.08, 1] }
                      : { rotate: 0, scale: 1 }
                  }
                  transition={{ duration: 0.25 }}
                  className="relative z-10"
                >
                  <Icon size={13} />
                </motion.span>
              </motion.button>
            );
          })}
        </div>

        {onAskAssistant && page !== "assistant" && (
          <button
            onClick={() => onAskAssistant()}
            className="inline-flex items-center gap-1.5 rounded-full border border-border dark:border-white/10 hover:border-indigo-500/40 bg-card dark:bg-[#0f172a]/80 hover:bg-muted dark:hover:bg-[#1e293b]/90 px-2.5 sm:px-3.5 py-1.5 text-xs font-medium text-foreground dark:text-slate-200 transition-all hover:shadow-[0_0_14px_rgba(99,102,241,0.2)] shadow-sm"
            title="Ask FinSight Assistant"
          >
            <MessageCircle size={13} className="text-indigo-500 dark:text-indigo-400" />
            <span className="hidden sm:inline">Ask FinSight</span>
            <span className="hidden min-[380px]:inline sm:hidden">Assistant</span>
          </button>
        )}
      </div>
    </header>
  );
}

// ─────────────────────────────────────────────────────────────
// App shell — sidebar + header + main content
// ─────────────────────────────────────────────────────────────
function AppShell({
  page,
  onNavigate,
  onLogout,
  onAskAssistant,
  theme,
  onThemeChange,
  onUploadNew,
  assistantQuestion,
  user,
  onUnauthorized,
  onUserUpdate,
}: {
  page: AppPage;
  onNavigate: (p: AppPage) => void;
  onLogout: () => void;
  onAskAssistant: (q?: string) => void;
  theme: Theme;
  onThemeChange: (t: Theme) => void;
  onUploadNew: () => void;
  assistantQuestion?: string;
  user: AuthenticatedUser;
  onUnauthorized: () => void;
  onUserUpdate?: (updatedUser: AuthenticatedUser) => void;
}) {
  const [collapsed, setCollapsed] = useState(
    () => typeof window !== "undefined" && window.innerWidth >= 768 && window.innerWidth < 1024
  );
  const [mobileOpen, setMobileOpen] = useState(false);

  const pageEl = (() => {
    switch (page) {
      case "dashboard":
        return (
          <DashboardPage
            onNavigate={onNavigate}
            onAskAssistant={onAskAssistant}
            user={user}
            onUnauthorized={onUnauthorized}
            onUpload={onUploadNew}
          />
        );
      case "transactions":
        return (
          <TransactionsPage
            user={user}
            onUnauthorized={onUnauthorized}
            onUpload={onUploadNew}
            onAskAssistant={onAskAssistant}
          />
        );
      case "commitments":
        return (
          <CommitmentsPage
            onAskAssistant={onAskAssistant}
            user={user}
            onUnauthorized={onUnauthorized}
            onUpload={onUploadNew}
          />
        );
      case "intelligence":
        return (
          <IntelligencePage
            onAskAssistant={onAskAssistant}
            user={user}
            onUnauthorized={onUnauthorized}
          />
        );
      case "what-if":
        return (
          <WhatIfPage
            onAskAssistant={onAskAssistant}
            user={user}
            onUnauthorized={onUnauthorized}
          />
        );
      case "assistant":
        return (
          <AssistantPage
            initialQuestion={assistantQuestion}
            user={user}
            onUnauthorized={onUnauthorized}
          />
        );
      case "settings":
        return (
          <SettingsPage
            user={user}
            onLogout={onLogout}
            onUploadNew={onUploadNew}
            onUserUpdate={onUserUpdate}
          />
        );
      default:
        return null;
    }
  })();

  return (
    <div className="flex h-screen overflow-hidden bg-background text-foreground select-none">
      <AppSidebar
        page={page}
        onNavigate={onNavigate}
        onLogout={onLogout}
        collapsed={collapsed}
        onToggleCollapse={() => setCollapsed((v) => !v)}
        user={user}
        mobileOpen={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
      />
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        <AppHeader
          page={page}
          theme={theme}
          onThemeChange={onThemeChange}
          onAskAssistant={onAskAssistant}
          onOpenMobile={() => setMobileOpen(true)}
        />
        <main className="flex-1 overflow-y-auto bg-background">
          <AnimatePresence mode="wait">
            <motion.div
              key={page}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.18 }}
            >
              <Suspense
                fallback={
                  <div className="flex min-h-[40vh] items-center justify-center px-6">
                    <p className="text-sm text-muted-foreground animate-pulse">Loading your workspace…</p>
                  </div>
                }
              >
                {pageEl}
              </Suspense>
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Root App with ThemeProvider + routing state machine
// ─────────────────────────────────────────────────────────────
function FinSightApp() {
  const { setTheme } = useTheme();
  const [resetToken, setResetToken] = useState<string | null>(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      return params.get("token");
    }
    return null;
  });
  const [authView, setAuthView] = useState<AuthView>(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      if (params.get("token") || window.location.pathname.includes("/reset-password")) {
        return "reset";
      }
    }
    return "landing";
  });
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isRestoringSession, setIsRestoringSession] = useState(true);
  const [authenticatedUser, setAuthenticatedUser] = useState<AuthenticatedUser | null>(null);
  const [hasData, setHasData] = useState(false);
  const [sessionRestoreError, setSessionRestoreError] = useState<string | null>(null);
  const [isUploadingMore, setIsUploadingMore] = useState(false);
  const [appPage, setAppPage] = useState<AppPage>("dashboard");
  const [theme, setLocalTheme] = useState<Theme>(() => {
    return (localStorage.getItem("finsight-theme") as Theme | null) ?? "system";
  });
  const [assistantQuestion, setAssistantQuestion] = useState<string | undefined>();
  const [forgotPasswordEmail, setForgotPasswordEmail] = useState("");

  // Synchronize URL and handle reset-password link routing
  useEffect(() => {
    const handleUrlChange = () => {
      const params = new URLSearchParams(window.location.search);
      const token = params.get("token");
      if (token || window.location.pathname.includes("/reset-password")) {
        setResetToken(token);
        setAuthView("reset");
      }
    };
    window.addEventListener("popstate", handleUrlChange);
    return () => window.removeEventListener("popstate", handleUrlChange);
  }, []);

  // Synchronize theme on initial mount and when system preference changes
  useEffect(() => {
    const saved = (localStorage.getItem("finsight-theme") as Theme | null) ?? "system";
    applyTheme(saved);

    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => {
      const current = (localStorage.getItem("finsight-theme") ?? "system") as Theme;
      if (current === "system") {
        applyTheme("system");
      }
    };
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  // Restore authenticated session
  useEffect(() => {
    const token = getStoredAccessToken();
    if (!token) {
      setIsRestoringSession(false);
      return;
    }

    let cancelled = false;
    async function restoreSession() {
      try {
        const [user, imports] = await Promise.all([
          authApi.me(token),
          transactionApi.imports(token),
        ]);
        if (cancelled) return;
        setAuthenticatedUser(user);
        setIsAuthenticated(true);
        setHasData(imports.some((record) => record.transaction_count > 0));
        setAppPage("dashboard");
      } catch {
        if (!cancelled) {
          clearStoredAccessToken();
          setAuthenticatedUser(null);
          setIsAuthenticated(false);
          setHasData(false);
          setSessionRestoreError("Unable to restore your session. Please sign in again.");
        }
      } finally {
        if (!cancelled) setIsRestoringSession(false);
      }
    }

    void restoreSession();
    return () => {
      cancelled = true;
    };
  }, []);

  function applyTheme(t: Theme) {
    setLocalTheme(t);
    localStorage.setItem("finsight-theme", t);
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const isDark = t === "dark" || (t === "system" && prefersDark);

    if (isDark) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
    setTheme(isDark ? "dark" : "light");
  }

  function handleLogin(user: AuthenticatedUser) {
    setAuthenticatedUser(user);
    setIsAuthenticated(true);
    setHasData(false);
    setAppPage("dashboard");
    const token = getStoredAccessToken();
    if (token) {
      transactionApi
        .imports(token)
        .then((imports) => {
          setHasData(imports.some((record) => record.transaction_count > 0));
        })
        .catch(() => setHasData(false));
    }
  }

  function handleLogout() {
    clearStoredAccessToken();
    localStorage.removeItem("finsight-user-name");
    localStorage.removeItem("finsight-user-avatar");
    localStorage.removeItem("finsight-notifications");
    setAuthenticatedUser(null);
    setIsAuthenticated(false);
    setHasData(false);
    setIsUploadingMore(false);
    setAuthView("landing");
  }

  function handleRegisterSuccess(user: AuthenticatedUser) {
    setAuthenticatedUser(user);
    setIsAuthenticated(true);
    setHasData(false);
    setAppPage("dashboard");
  }

  function handleUploadComplete() {
    setHasData(true);
    setIsUploadingMore(false);
    setAppPage("dashboard");
  }

  function handleAskAssistant(q?: string) {
    setAssistantQuestion(q);
    setAppPage("assistant");
  }

  function handleNavigate(p: AppPage) {
    if (p !== "assistant") setAssistantQuestion(undefined);
    setAppPage(p);
  }

  function handleUploadNew() {
    setIsUploadingMore(true);
  }

  if (isRestoringSession) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center px-4">
        <p className="text-sm text-muted-foreground animate-pulse">Restoring your session…</p>
      </div>
    );
  }

  if (sessionRestoreError) {
    return (
      <div className="min-h-screen bg-background flex flex-col items-center justify-center gap-4 px-4 text-center">
        <p className="text-sm text-destructive">{sessionRestoreError}</p>
        <button
          onClick={() => {
            setSessionRestoreError(null);
            setIsAuthenticated(false);
            setAuthenticatedUser(null);
            setHasData(false);
            setAuthView("login");
          }}
          className="text-sm text-primary hover:text-primary/80 transition-colors"
        >
          Back to Sign In
        </button>
      </div>
    );
  }

  // Uploading an additional dataset while authenticated
  if (isAuthenticated && authenticatedUser && isUploadingMore) {
    return (
      <UploadPage
        hasExistingData={true}
        onComplete={handleUploadComplete}
        onCancel={() => setIsUploadingMore(false)}
        onUnauthorized={handleLogout}
      />
    );
  }

  // Authenticated + has data → main app shell
  if (isAuthenticated && authenticatedUser && hasData) {
    return (
      <AppShell
        page={appPage}
        onNavigate={handleNavigate}
        onLogout={handleLogout}
        onAskAssistant={handleAskAssistant}
        theme={theme}
        onThemeChange={applyTheme}
        onUploadNew={handleUploadNew}
        assistantQuestion={assistantQuestion}
        user={authenticatedUser}
        onUnauthorized={handleLogout}
        onUserUpdate={(updatedUser) => setAuthenticatedUser(updatedUser)}
      />
    );
  }

  // Authenticated but no data → onboarding upload flow
  if (isAuthenticated && authenticatedUser && !hasData) {
    return (
      <UploadPage
        hasExistingData={false}
        onComplete={handleUploadComplete}
        onUnauthorized={handleLogout}
      />
    );
  }

  // Not authenticated → auth flow
  return (
    <ErrorBoundary onReset={() => setAuthView("login")}>
      <AnimatePresence mode="wait">
      {authView === "landing" && (
        <motion.div key="landing" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <LandingPage
            onLogin={() => setAuthView("login")}
            onRegister={() => setAuthView("register")}
            theme={theme}
            onThemeChange={applyTheme}
          />
        </motion.div>
      )}
      {authView === "login" && (
        <motion.div key="login" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <LoginPage
            onSuccess={handleLogin}
            onRegister={() => setAuthView("register")}
            onForgot={(em) => {
              setForgotPasswordEmail(em || "");
              setAuthView("forgot");
            }}
            onBack={() => setAuthView("landing")}
          />
        </motion.div>
      )}
      {authView === "register" && (
        <motion.div key="register" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <RegisterPage
            onSuccess={handleRegisterSuccess}
            onLogin={() => setAuthView("login")}
            onBack={() => setAuthView("landing")}
          />
        </motion.div>
      )}
      {authView === "forgot" && (
        <motion.div key="forgot" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <ForgotPasswordPage
            initialEmail={forgotPasswordEmail}
            onBack={() => setAuthView("login")}
          />
        </motion.div>
      )}
      {authView === "reset" && (
        <motion.div key="reset" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <ResetPasswordPage
            token={resetToken}
            onSuccess={() => {
              window.history.replaceState({}, "", "/");
              setResetToken(null);
              setAuthView("login");
            }}
            onBack={() => {
              window.history.replaceState({}, "", "/");
              setResetToken(null);
              setAuthView("login");
            }}
            onForgotPassword={() => {
              window.history.replaceState({}, "", "/");
              setResetToken(null);
              setForgotPasswordEmail("");
              setAuthView("forgot");
            }}
          />
        </motion.div>
      )}
      </AnimatePresence>
    </ErrorBoundary>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <FinSightApp />
    </ThemeProvider>
  );
}
