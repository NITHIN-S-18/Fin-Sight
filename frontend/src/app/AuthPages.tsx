import React, { useEffect, useId, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { ArrowLeft, AlertCircle, CheckCircle2, Eye, EyeOff, Check, Info, ShieldCheck, KeyRound, RotateCcw } from "lucide-react";
import { InputOTP, InputOTPGroup, InputOTPSlot } from "./components/ui/input-otp";
import { Button } from "@figma/astraui";
import { ApiError, authApi, AuthenticatedUser, storeAccessToken, clearStoredAccessToken } from "../api/client";
import { FinSightLogo } from "./components/FinSightLogo";

const REMEMBERED_EMAIL_KEY = "finsight-remembered-email";

interface AuthPageWrapperProps {
  children: React.ReactNode;
  onBack?: () => void;
}

interface AuthInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label: string;
  suffix?: React.ReactNode;
}

function AuthInput({ label, suffix, className = "", ...inputProps }: AuthInputProps) {
  const id = useId();
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-xs font-semibold text-foreground">
        {label}
      </label>
      <div className="group relative">
        <input
          id={id}
          className={`h-11 w-full rounded-xl border border-border bg-card px-3.5 pr-11 text-sm text-foreground outline-none transition-all placeholder:text-muted-foreground focus:border-primary focus:ring-4 focus:ring-primary/10 ${className}`}
          {...inputProps}
        />
        {suffix && <div className="absolute inset-y-0 right-3 flex items-center">{suffix}</div>}
      </div>
    </div>
  );
}

function AuthWrapper({ children, onBack }: AuthPageWrapperProps) {
  const reduceMotion = useReducedMotion();
  return (
    <div className="relative min-h-screen overflow-hidden bg-background flex items-center justify-center px-3 sm:px-4 py-6 sm:py-12">
      <motion.div
        aria-hidden="true"
        animate={reduceMotion ? undefined : { x: [0, 18, 0], y: [0, -12, 0] }}
        transition={{ duration: 12, repeat: Infinity, ease: "easeInOut" }}
        className="pointer-events-none absolute -left-24 top-16 h-64 w-64 rounded-full bg-primary/8 blur-3xl"
      />
      <div aria-hidden="true" className="pointer-events-none absolute right-0 bottom-0 h-72 w-72 rounded-full bg-ai/8 blur-3xl" />
      <motion.div
        initial={reduceMotion ? false : { opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45, ease: "easeOut" }}
        className="relative z-10 w-full max-w-md"
      >
        {onBack && (
          <button
            onClick={onBack}
            className="group flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors mb-7"
          >
            <ArrowLeft size={14} className="transition-transform group-hover:-translate-x-0.5" />
            Back
          </button>
        )}
        <div className="mb-6">
          <FinSightLogo variant="full" size="lg" showSparkle={true} />
        </div>
        <div className="rounded-2xl border border-border bg-card/90 p-4 sm:p-7 shadow-xl shadow-black/5 backdrop-blur-sm">
          {children}
        </div>
      </motion.div>
    </div>
  );
}

// ──────────────────────────────────────────────
// LOGIN
// ──────────────────────────────────────────────
interface LoginPageProps {
  onSuccess: (user: AuthenticatedUser) => void;
  onRegister: () => void;
  onForgot: (email?: string) => void;
  onBack: () => void;
}

export function LoginPage({ onSuccess, onRegister, onForgot, onBack }: LoginPageProps) {
  const [email, setEmail] = useState(() => localStorage.getItem(REMEMBERED_EMAIL_KEY) ?? "");
  const [password, setPassword] = useState("");
  const [rememberEmail, setRememberEmail] = useState(() => Boolean(localStorage.getItem(REMEMBERED_EMAIL_KEY)));
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleLogin() {
    if (!email) { setError("Email is required."); return; }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { setError("Please enter a valid email."); return; }
    if (!password) { setError("Password is required."); return; }
    setError("");
    setLoading(true);
    try {
      const tokenResponse = await authApi.login({ email: email.trim(), password });
      storeAccessToken(tokenResponse.access_token);
      const user = await authApi.me(tokenResponse.access_token);
      if (rememberEmail) localStorage.setItem(REMEMBERED_EMAIL_KEY, email.trim());
      else localStorage.removeItem(REMEMBERED_EMAIL_KEY);
      onSuccess(user);
    } catch (err) {
      clearStoredAccessToken();
      setError(err instanceof ApiError ? err.message : "Unable to sign in. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  function handleRememberEmail(checked: boolean) {
    setRememberEmail(checked);
    if (!checked) localStorage.removeItem(REMEMBERED_EMAIL_KEY);
  }

  return (
    <AuthWrapper onBack={onBack}>
      <p className="text-[10px] font-mono uppercase tracking-[0.16em] text-primary mb-2">Account access</p>
      <h1 className="text-foreground text-2xl font-semibold tracking-tight mb-2">Welcome back</h1>
      <p className="text-muted-foreground text-sm leading-relaxed mb-7">Sign in to continue understanding your financial exposure.</p>

      {error && (
        <div className="flex items-center gap-2 bg-destructive/10 border border-destructive/20 rounded-md px-3 py-2.5 mb-4">
          <AlertCircle size={14} className="text-destructive shrink-0" />
          <span className="text-destructive text-sm">{error}</span>
        </div>
      )}

      <div className="space-y-4">
        <AuthInput
          label="Email"
          type="email"
          placeholder="you@example.com"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          autoComplete="username"
        />
        <AuthInput
          label="Password"
          type={showPassword ? "text" : "password"}
          placeholder="Enter your password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete="current-password"
          suffix={
            <button
              type="button"
              onClick={() => setShowPassword((v) => !v)}
              aria-label={showPassword ? "Hide password" : "Show password"}
              className="rounded-md text-muted-foreground hover:text-foreground focus:outline-none focus:ring-2 focus:ring-primary/30 transition-colors"
            >
              {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          }
        />

        <div className="flex items-center justify-between gap-4">
          <label className="group flex min-w-0 cursor-pointer items-center gap-2.5 rounded-lg py-1 text-xs text-muted-foreground">
            <input
              type="checkbox"
              checked={rememberEmail}
              onChange={(event) => handleRememberEmail(event.target.checked)}
              className="peer sr-only"
              aria-describedby={rememberEmail ? "remember-email-note" : undefined}
            />
            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md border border-muted-foreground/50 bg-background text-primary-foreground shadow-sm transition-all duration-200 peer-checked:border-primary peer-checked:bg-primary peer-focus-visible:ring-2 peer-focus-visible:ring-primary/50 peer-focus-visible:ring-offset-2 peer-focus-visible:ring-offset-card">
              <Check size={13} strokeWidth={3} className="scale-0 opacity-0 transition-all duration-200 peer-checked:scale-100 peer-checked:opacity-100" />
            </span>
            <span className="select-none font-medium group-hover:text-foreground transition-colors">Remember me</span>
          </label>
          <button
            type="button"
            onClick={() => onForgot(email.trim())}
            className="text-xs text-primary hover:text-primary/80 transition-colors"
          >
            Forgot password?
          </button>
        </div>
        {rememberEmail && (
          <motion.p
            id="remember-email-note"
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
            className="-mt-1 pl-7 text-[11px] text-muted-foreground"
          >
            This email will be remembered on this device.
          </motion.p>
        )}

        <Button variant="primary" className="w-full transition-transform hover:-translate-y-px" onClick={handleLogin} disabled={loading}>
          {loading ? "Signing in…" : "Sign In"}
        </Button>
      </div>

      <p className="text-center text-sm text-muted-foreground mt-6">
        Don&apos;t have an account?{" "}
        <button onClick={onRegister} className="font-medium text-primary hover:text-primary/80 transition-colors">
          Create account
        </button>
      </p>
    </AuthWrapper>
  );
}

// ──────────────────────────────────────────────
// REGISTER
// ──────────────────────────────────────────────
interface RegisterPageProps {
  onSuccess: (user: AuthenticatedUser) => void;
  onLogin: () => void;
  onBack: () => void;
}

function getPasswordStrength(pw: string): { label: string; color: string; pct: number } {
  if (!pw) return { label: "", color: "bg-muted", pct: 0 };
  if (pw.length < 6) return { label: "Too short", color: "bg-red-500", pct: 20 };
  const has = (re: RegExp) => re.test(pw);
  const score =
    (has(/[A-Z]/) ? 1 : 0) +
    (has(/[0-9]/) ? 1 : 0) +
    (has(/[^A-Za-z0-9]/) ? 1 : 0) +
    (pw.length >= 10 ? 1 : 0);
  if (score <= 1) return { label: "Weak", color: "bg-red-400", pct: 35 };
  if (score === 2) return { label: "Fair", color: "bg-amber-400", pct: 55 };
  if (score === 3) return { label: "Good", color: "bg-emerald-400", pct: 80 };
  return { label: "Strong", color: "bg-emerald-500", pct: 100 };
}

export function RegisterPage({ onSuccess, onLogin, onBack }: RegisterPageProps) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [showPw, setShowPw] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const strength = getPasswordStrength(password);
  const mismatch = confirm && password !== confirm;

  async function handleRegister() {
    if (!name.trim()) { setError("Full name is required."); return; }
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { setError("Enter a valid email."); return; }
    if (strength.pct < 55) { setError("Please choose a stronger password."); return; }
    if (password !== confirm) { setError("Passwords do not match."); return; }
    if (!agreed) { setError("Please accept the terms to continue."); return; }
    setError("");
    setLoading(true);
    let registrationCompleted = false;
    try {
      await authApi.register({ email: email.trim(), password, display_name: name.trim() });
      registrationCompleted = true;
      const tokenResponse = await authApi.login({ email: email.trim(), password });
      storeAccessToken(tokenResponse.access_token);
      const user = await authApi.me(tokenResponse.access_token);
      setPassword("");
      setConfirm("");
      onSuccess(user);
    } catch (err) {
      if (registrationCompleted) {
        clearStoredAccessToken();
        setPassword("");
        setConfirm("");
        setError("Your account was created, but we couldn't sign you in automatically. Please sign in to continue.");
      } else {
        setError(err instanceof ApiError ? err.message : "Unable to create your account. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthWrapper onBack={onBack}>
      <p className="text-[10px] font-mono uppercase tracking-[0.16em] text-primary mb-2">Start with clarity</p>
      <h1 className="text-foreground text-2xl font-semibold tracking-tight mb-2">Create your account</h1>
      <p className="text-muted-foreground text-sm leading-relaxed mb-7">Start understanding your financial exposure.</p>

      {error && (
        <div className="flex items-center gap-2 bg-destructive/10 border border-destructive/20 rounded-md px-3 py-2.5 mb-4">
          <AlertCircle size={14} className="text-destructive shrink-0" />
          <span className="text-destructive text-sm">{error}</span>
        </div>
      )}

      <div className="space-y-4">
        <AuthInput label="Full Name" placeholder="Enter your full name" value={name} onChange={(event) => setName(event.target.value)} autoComplete="name" />
        <AuthInput label="Email" type="email" placeholder="you@example.com" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" />

        <div>
          <AuthInput
            label="Password"
            type={showPw ? "text" : "password"}
            placeholder="Create a strong password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="new-password"
            suffix={
              <button type="button" onClick={() => setShowPw((v) => !v)} aria-label={showPw ? "Hide password" : "Show password"} className="rounded-md text-muted-foreground hover:text-foreground focus:outline-none focus:ring-2 focus:ring-primary/30 transition-colors">
                {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            }
          />
          {password && (
            <div className="mt-1.5">
              <div className="h-1 bg-muted rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-300 ${strength.color}`}
                  style={{ width: `${strength.pct}%` }}
                />
              </div>
              <p className="text-xs text-muted-foreground mt-1">{strength.label}</p>
            </div>
          )}
        </div>

        <div>
          <AuthInput
            label="Confirm Password"
            type={showConfirm ? "text" : "password"}
            placeholder="Re-enter your password"
            value={confirm}
            onChange={(event) => setConfirm(event.target.value)}
            autoComplete="new-password"
            suffix={
              <button type="button" onClick={() => setShowConfirm((v) => !v)} aria-label={showConfirm ? "Hide password" : "Show password"} className="rounded-md text-muted-foreground hover:text-foreground focus:outline-none focus:ring-2 focus:ring-primary/30 transition-colors">
                {showConfirm ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            }
          />
          {mismatch && <p className="text-xs text-red-400 mt-1">Passwords do not match</p>}
        </div>

        <div className="flex items-start gap-2">
          {/* using <input> instead of <Checkbox>: terms label requires JSX hyperlinks; Checkbox only accepts a string label */}
          <input
            type="checkbox"
            id="terms"
            checked={agreed}
            onChange={(e) => setAgreed(e.target.checked)}
            className="mt-0.5 h-4 w-4 rounded accent-primary"
          />
          <label htmlFor="terms" className="text-xs text-muted-foreground leading-relaxed">
            I agree to the{" "}
            <span className="text-primary cursor-pointer">Terms of Service</span> and{" "}
            <span className="text-primary cursor-pointer">Privacy Policy</span>
          </label>
        </div>

        <Button variant="primary" className="w-full transition-transform hover:-translate-y-px" onClick={handleRegister} disabled={loading}>
          {loading ? "Creating account…" : "Create Account"}
        </Button>
      </div>

      <p className="text-center text-sm text-muted-foreground mt-6">
        Already have an account?{" "}
        <button onClick={onLogin} className="font-medium text-primary hover:text-primary/80 transition-colors">
          Sign in
        </button>
      </p>
    </AuthWrapper>
  );
}

// ──────────────────────────────────────────────
// FORGOT PASSWORD
// ──────────────────────────────────────────────
export interface ForgotPasswordPageProps {
  initialEmail?: string;
  onBack: () => void;
}

export type ForgotPasswordStep = "email" | "otp" | "password" | "success";

export function ForgotPasswordPage({ initialEmail, onBack }: ForgotPasswordPageProps) {
  const [step, setStep] = useState<ForgotPasswordStep>("email");
  const [email, setEmail] = useState(() => initialEmail?.trim() ?? "");
  const [otp, setOtp] = useState("");
  const [resetToken, setResetToken] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [resendCountdown, setResendCountdown] = useState(0);
  const [resendNotice, setResendNotice] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (initialEmail && step === "email") {
      setEmail(initialEmail.trim());
    }
  }, [initialEmail, step]);

  useEffect(() => {
    if (resendCountdown <= 0) return;
    const interval = setInterval(() => {
      setResendCountdown((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(interval);
  }, [resendCountdown]);

  // STEP 1: Request 6-digit OTP
  async function handleRequestOtp(e?: React.FormEvent) {
    if (e) e.preventDefault();
    const targetEmail = email.trim();
    if (!targetEmail) {
      setError("Email is required.");
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(targetEmail)) {
      setError("Please enter a valid email address.");
      return;
    }
    setError("");
    setLoading(true);
    setResendNotice(false);
    try {
      await authApi.forgotPassword({ email: targetEmail });
      setStep("otp");
      setOtp("");
      setResendCountdown(60);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to process your request. Please try again later.");
    } finally {
      setLoading(false);
    }
  }

  // STEP 2: Resend OTP
  async function handleResendOtp() {
    if (resendCountdown > 0 || resending || loading) return;
    const targetEmail = email.trim();
    if (!targetEmail) return;
    setError("");
    setResending(true);
    setResendNotice(false);
    try {
      await authApi.resendOtp({ email: targetEmail });
      setResendCountdown(60);
      setResendNotice(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to resend code. Please try again.");
    } finally {
      setResending(false);
    }
  }

  // STEP 2: Verify 6-digit OTP
  async function handleVerifyOtp(e?: React.FormEvent) {
    if (e) e.preventDefault();
    const cleanOtp = otp.trim();
    if (cleanOtp.length !== 6 || !/^\d{6}$/.test(cleanOtp)) {
      setError("Please enter the complete 6-digit verification code.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const res = await authApi.verifyOtp({ email: email.trim(), otp: cleanOtp });
      setResetToken(res.reset_token);
      setStep("password");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Invalid or expired verification code.");
    } finally {
      setLoading(false);
    }
  }

  // STEP 3: Submit New Password
  async function handleResetPassword(e?: React.FormEvent) {
    if (e) e.preventDefault();
    if (!resetToken) {
      setError("Reset session expired. Please request a new verification code.");
      setStep("email");
      return;
    }
    if (!password) {
      setError("New password is required.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters long.");
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      await authApi.resetPassword({ token: resetToken, new_password: password });
      setStep("success");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Invalid or expired reset session. Please request a new code.");
    } finally {
      setLoading(false);
    }
  }

  const strength = getPasswordStrength(password);
  const mismatch = Boolean(confirm && password !== confirm);

  // STEP 4: Success View
  if (step === "success") {
    return (
      <AuthWrapper onBack={onBack}>
        <div className="space-y-6">
          <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-6 text-center">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-400 ring-8 ring-emerald-500/10">
              <CheckCircle2 size={32} />
            </div>
            <h1 className="text-xl font-bold tracking-tight text-foreground">Password reset complete</h1>
            <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
              Your password has been successfully updated. All previous active sessions have been invalidated for security. You can now sign in with your new credentials.
            </p>
          </div>

          <Button
            variant="primary"
            className="w-full h-11 text-sm font-medium transition-transform hover:-translate-y-px"
            onClick={onBack}
          >
            Sign In with New Password
          </Button>
        </div>
      </AuthWrapper>
    );
  }

  // STEP 3: Password Form View
  if (step === "password") {
    return (
      <AuthWrapper onBack={() => setStep("otp")}>
        <p className="text-[10px] font-mono uppercase tracking-[0.16em] text-primary mb-2">Account Security</p>
        <h1 className="text-foreground text-2xl font-semibold tracking-tight mb-2">Set a new password</h1>
        <p className="text-muted-foreground text-sm leading-relaxed mb-6">
          Verification confirmed. Create a strong, new password for your FinSight account.
        </p>

        {error && (
          <div className="flex items-start gap-2 bg-destructive/10 border border-destructive/20 rounded-md p-3 mb-4">
            <AlertCircle size={15} className="text-destructive shrink-0 mt-0.5" />
            <div className="space-y-1">
              <span className="text-destructive text-sm block leading-snug">{error}</span>
              {(error.toLowerCase().includes("invalid") || error.toLowerCase().includes("expired")) && (
                <button
                  type="button"
                  onClick={() => {
                    setStep("email");
                    setError("");
                  }}
                  className="text-xs text-primary underline hover:text-primary/80 cursor-pointer"
                >
                  Request a fresh verification code
                </button>
              )}
            </div>
          </div>
        )}

        <form onSubmit={handleResetPassword} className="space-y-4">
          <div>
            <AuthInput
              label="New Password"
              type={showPw ? "text" : "password"}
              placeholder="Enter new password (min. 8 characters)"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
              disabled={loading}
              suffix={
                <button
                  type="button"
                  onClick={() => setShowPw((v) => !v)}
                  aria-label={showPw ? "Hide password" : "Show password"}
                  className="rounded-md text-muted-foreground hover:text-foreground focus:outline-none focus:ring-2 focus:ring-primary/30 transition-colors"
                >
                  {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              }
            />
            {password && (
              <div className="mt-1.5">
                <div className="h-1 bg-muted rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-300 ${strength.color}`}
                    style={{ width: `${strength.pct}%` }}
                  />
                </div>
                <div className="flex items-center justify-between mt-1 text-xs text-muted-foreground">
                  <span>{strength.label}</span>
                  <span>Min. 8 characters</span>
                </div>
              </div>
            )}
          </div>

          <div>
            <AuthInput
              label="Confirm New Password"
              type={showConfirm ? "text" : "password"}
              placeholder="Re-enter your new password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              autoComplete="new-password"
              disabled={loading}
              suffix={
                <button
                  type="button"
                  onClick={() => setShowConfirm((v) => !v)}
                  aria-label={showConfirm ? "Hide confirm password" : "Show confirm password"}
                  className="rounded-md text-muted-foreground hover:text-foreground focus:outline-none focus:ring-2 focus:ring-primary/30 transition-colors"
                >
                  {showConfirm ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              }
            />
            {mismatch && (
              <p className="text-xs text-destructive mt-1 flex items-center gap-1">
                <AlertCircle size={12} /> Passwords do not match
              </p>
            )}
          </div>

          <Button
            variant="primary"
            type="submit"
            className="w-full transition-transform hover:-translate-y-px"
            disabled={loading || mismatch || !password || password.length < 8}
          >
            {loading ? "Updating password…" : "Reset Password"}
          </Button>

          <p className="text-center text-sm text-muted-foreground pt-2">
            <button
              type="button"
              onClick={onBack}
              className="font-medium text-primary hover:text-primary/80 transition-colors"
            >
              Cancel and return to Sign In
            </button>
          </p>
        </form>
      </AuthWrapper>
    );
  }

  // STEP 2: OTP Verification View
  if (step === "otp") {
    return (
      <AuthWrapper onBack={() => setStep("email")}>
        <p className="text-[10px] font-mono uppercase tracking-[0.16em] text-primary mb-2">Security Verification</p>
        <h1 className="text-foreground text-2xl font-semibold tracking-tight mb-2">Enter 6-digit code</h1>
        <p className="text-muted-foreground text-sm leading-relaxed mb-6">
          We sent a verification code to <span className="font-semibold text-foreground">{email}</span>.{" "}
          <button
            type="button"
            onClick={() => {
              setStep("email");
              setError("");
            }}
            className="text-primary hover:underline font-medium text-xs ml-1"
          >
            Change email
          </button>
        </p>

        {error && (
          <div className="flex items-center gap-2 bg-destructive/10 border border-destructive/20 rounded-md px-3 py-2.5 mb-4">
            <AlertCircle size={14} className="text-destructive shrink-0" />
            <span className="text-destructive text-sm leading-snug">{error}</span>
          </div>
        )}

        {resendNotice && !error && (
          <div className="flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/20 rounded-md px-3 py-2.5 mb-4">
            <CheckCircle2 size={14} className="text-emerald-400 shrink-0" />
            <span className="text-emerald-400 text-xs">A new 6-digit verification code has been sent.</span>
          </div>
        )}

        <form onSubmit={handleVerifyOtp} className="space-y-6">
          <div className="flex flex-col items-center justify-center space-y-2">
            <label className="text-xs font-semibold text-foreground self-start">
              Verification Code (OTP)
            </label>
            <InputOTP
              maxLength={6}
              value={otp}
              onChange={(val) => {
                setOtp(val.replace(/\D/g, "").slice(0, 6));
                if (error) setError("");
              }}
              disabled={loading}
              autoFocus
              containerClassName="justify-center w-full"
            >
              <InputOTPGroup className="gap-1 sm:gap-2 sm:gap-2.5 justify-center">
                <InputOTPSlot index={0} className="h-11 sm:h-12 w-8 min-[360px]:w-9 min-[400px]:w-10 sm:w-12 text-base sm:text-lg font-mono font-bold rounded-lg border-border bg-card" />
                <InputOTPSlot index={1} className="h-11 sm:h-12 w-8 min-[360px]:w-9 min-[400px]:w-10 sm:w-12 text-base sm:text-lg font-mono font-bold rounded-lg border-border bg-card" />
                <InputOTPSlot index={2} className="h-11 sm:h-12 w-8 min-[360px]:w-9 min-[400px]:w-10 sm:w-12 text-base sm:text-lg font-mono font-bold rounded-lg border-border bg-card" />
                <InputOTPSlot index={3} className="h-11 sm:h-12 w-8 min-[360px]:w-9 min-[400px]:w-10 sm:w-12 text-base sm:text-lg font-mono font-bold rounded-lg border-border bg-card" />
                <InputOTPSlot index={4} className="h-11 sm:h-12 w-8 min-[360px]:w-9 min-[400px]:w-10 sm:w-12 text-base sm:text-lg font-mono font-bold rounded-lg border-border bg-card" />
                <InputOTPSlot index={5} className="h-11 sm:h-12 w-8 min-[360px]:w-9 min-[400px]:w-10 sm:w-12 text-base sm:text-lg font-mono font-bold rounded-lg border-border bg-card" />
              </InputOTPGroup>
            </InputOTP>
            <p className="text-[11px] text-muted-foreground pt-1">
              Code expires in 5 minutes. Maximum 5 verification attempts.
            </p>
          </div>

          <Button
            variant="primary"
            type="submit"
            className="w-full transition-transform hover:-translate-y-px"
            disabled={loading || otp.trim().length !== 6}
          >
            {loading ? "Verifying code…" : "Verify Code"}
          </Button>

          <div className="flex flex-col items-center gap-2 pt-1 text-xs text-muted-foreground">
            {resendCountdown > 0 ? (
              <span className="text-muted-foreground/80">
                Resend code in <span className="font-semibold text-foreground">{resendCountdown}s</span>
              </span>
            ) : (
              <button
                type="button"
                onClick={handleResendOtp}
                disabled={resending}
                className="font-medium text-primary hover:text-primary/80 transition-colors cursor-pointer flex items-center gap-1.5"
              >
                <RotateCcw size={12} className={resending ? "animate-spin" : ""} />
                {resending ? "Resending code…" : "Resend verification code"}
              </button>
            )}

            <button
              type="button"
              onClick={onBack}
              className="text-muted-foreground hover:text-foreground transition-colors pt-2"
            >
              Back to Sign In
            </button>
          </div>
        </form>
      </AuthWrapper>
    );
  }

  // STEP 1: Email Input View
  return (
    <AuthWrapper onBack={onBack}>
      <p className="text-[10px] font-mono uppercase tracking-[0.16em] text-primary mb-2">Account Recovery</p>
      <h1 className="text-foreground text-2xl font-semibold tracking-tight mb-2">Reset your password</h1>
      <p className="text-muted-foreground text-sm leading-relaxed mb-6">
        Enter your registered email address and we will send you a 6-digit verification code to reset your password.
      </p>

      {error && (
        <div className="flex items-center gap-2 bg-destructive/10 border border-destructive/20 rounded-md px-3 py-2.5 mb-4">
          <AlertCircle size={14} className="text-destructive shrink-0" />
          <span className="text-destructive text-sm">{error}</span>
        </div>
      )}

      <form onSubmit={handleRequestOtp} className="space-y-4">
        <AuthInput
          label="Registered Email"
          type="email"
          placeholder="you@example.com"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          autoComplete="email"
          disabled={loading}
        />

        <Button
          variant="primary"
          type="submit"
          className="w-full transition-transform hover:-translate-y-px"
          disabled={loading}
        >
          {loading ? "Sending verification code…" : "Send Verification Code"}
        </Button>

        <p className="text-center text-sm text-muted-foreground pt-2">
          Remember your password?{" "}
          <button
            type="button"
            onClick={onBack}
            className="font-medium text-primary hover:text-primary/80 transition-colors"
          >
            Sign in
          </button>
        </p>
      </form>
    </AuthWrapper>
  );
}

// ──────────────────────────────────────────────
export interface ResetPasswordPageProps {
  token: string | null;
  onSuccess: () => void;
  onBack: () => void;
  onForgotPassword: () => void;
}

export function ResetPasswordPage({ token, onSuccess, onBack, onForgotPassword }: ResetPasswordPageProps) {
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [completed, setCompleted] = useState(false);

  const strength = getPasswordStrength(password);
  const mismatch = confirm && password !== confirm;

  async function handleReset(e?: React.FormEvent) {
    if (e) e.preventDefault();
    if (!token) {
      setError("Reset token is missing. Please request a new password reset link.");
      return;
    }
    if (!password) {
      setError("New password is required.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters long.");
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setError("");
    setLoading(true);

    try {
      await authApi.resetPassword({ token, new_password: password });
      setCompleted(true);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Invalid or expired password reset link. Please request a new reset link."
      );
    } finally {
      setLoading(false);
    }
  }

  // If token is missing from the URL or state
  if (!token) {
    return (
      <AuthWrapper onBack={onBack}>
        <div className="flex items-start gap-3 rounded-xl border border-border bg-muted/40 p-4 mb-6">
          <AlertCircle size={18} className="mt-0.5 shrink-0 text-amber-500" />
          <div>
            <h1 className="text-foreground text-lg font-semibold mb-1">Missing or invalid reset link</h1>
            <p className="text-muted-foreground text-sm leading-relaxed">
              No reset token was found in this link. The link may have been truncated or modified.
            </p>
          </div>
        </div>
        <div className="space-y-3">
          <Button variant="primary" className="w-full" onClick={onForgotPassword}>
            Request New Reset Link
          </Button>
          <button
            onClick={onBack}
            className="w-full text-center text-sm text-primary hover:text-primary/80 transition-colors py-2"
          >
            Back to Sign In
          </button>
        </div>
      </AuthWrapper>
    );
  }

  return (
    <AuthWrapper onBack={onBack}>
      <p className="text-[10px] font-mono uppercase tracking-[0.16em] text-primary mb-2">Account Security</p>
      <h1 className="text-foreground text-2xl font-semibold tracking-tight mb-2">Set a new password</h1>
      <p className="text-muted-foreground text-sm leading-relaxed mb-6">
        Create a new secure password for your FinSight account.
      </p>

      {error && (
        <div className="flex items-start gap-2 bg-destructive/10 border border-destructive/20 rounded-md p-3 mb-4">
          <AlertCircle size={15} className="text-destructive shrink-0 mt-0.5" />
          <div className="space-y-1">
            <span className="text-destructive text-sm block leading-snug">{error}</span>
            {(error.toLowerCase().includes("invalid") || error.toLowerCase().includes("expired")) && (
              <button
                type="button"
                onClick={onForgotPassword}
                className="text-xs text-primary underline hover:text-primary/80 cursor-pointer"
              >
                Request a fresh reset link
              </button>
            )}
          </div>
        </div>
      )}

      {completed ? (
        <div className="space-y-5">
          <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/10 p-4">
            <div className="flex items-start gap-3">
              <CheckCircle2 size={18} className="mt-0.5 shrink-0 text-emerald-500" />
              <div className="space-y-1">
                <p className="text-sm font-semibold text-foreground">Password reset complete</p>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  Your password has been successfully updated. You can now sign in with your new credentials.
                </p>
              </div>
            </div>
          </div>
          <Button variant="primary" className="w-full" onClick={onSuccess}>
            Sign In with New Password
          </Button>
        </div>
      ) : (
        <form onSubmit={handleReset} className="space-y-4">
          <div>
            <AuthInput
              label="New Password"
              type={showPw ? "text" : "password"}
              placeholder="Enter new password (min. 8 characters)"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
              disabled={loading}
              suffix={
                <button
                  type="button"
                  onClick={() => setShowPw((v) => !v)}
                  aria-label={showPw ? "Hide password" : "Show password"}
                  className="rounded-md text-muted-foreground hover:text-foreground focus:outline-none focus:ring-2 focus:ring-primary/30 transition-colors"
                >
                  {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              }
            />
            {password && (
              <div className="mt-1.5">
                <div className="h-1 bg-muted rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-300 ${strength.color}`}
                    style={{ width: `${strength.pct}%` }}
                  />
                </div>
                <div className="flex items-center justify-between mt-1 text-xs text-muted-foreground">
                  <span>{strength.label}</span>
                  <span>Min. 8 characters</span>
                </div>
              </div>
            )}
          </div>

          <div>
            <AuthInput
              label="Confirm New Password"
              type={showConfirm ? "text" : "password"}
              placeholder="Re-enter your new password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              autoComplete="new-password"
              disabled={loading}
              suffix={
                <button
                  type="button"
                  onClick={() => setShowConfirm((v) => !v)}
                  aria-label={showConfirm ? "Hide password" : "Show password"}
                  className="rounded-md text-muted-foreground hover:text-foreground focus:outline-none focus:ring-2 focus:ring-primary/30 transition-colors"
                >
                  {showConfirm ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              }
            />
            {mismatch && <p className="text-xs text-red-400 mt-1">Passwords do not match</p>}
          </div>

          <Button
            variant="primary"
            type="submit"
            className="w-full transition-transform hover:-translate-y-px"
            disabled={loading}
          >
            {loading ? "Resetting password…" : "Reset Password"}
          </Button>

          <p className="text-center text-sm text-muted-foreground pt-2">
            <button
              type="button"
              onClick={onBack}
              className="font-medium text-primary hover:text-primary/80 transition-colors"
            >
              Back to Sign In
            </button>
          </p>
        </form>
      )}
    </AuthWrapper>
  );
}

