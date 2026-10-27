import React, { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  Settings,
  User,
  Shield,
  Lock,
  LogOut,
  ChevronRight,
  Download,
  Info,
  Camera,
  Trash2,
  X,
  FileText,
  Calendar,
  KeyRound,
  Check,
  AlertCircle,
  TrendingUp,
  Loader2,
} from "lucide-react";
import {
  AuthenticatedUser,
  ApiError,
  authApi,
  getAvatarUrl,
  getStoredAccessToken,
  transactionApi,
  FinancialSummary,
} from "../api/client";

interface SettingsPageProps {
  user: AuthenticatedUser;
  onLogout: () => void;
  onUploadNew: () => void;
  onUserUpdate?: (updatedUser: AuthenticatedUser) => void;
}

export function SettingsPage({
  user,
  onLogout,
  onUploadNew,
  onUserUpdate,
}: SettingsPageProps) {
  // ── Profile State ───────────────────────────────────────────
  const fallbackName =
    user.email.split("@")[0].charAt(0).toUpperCase() +
    user.email.split("@")[0].slice(1);
  const displayName = user.display_name?.trim() || fallbackName;

  const [profileSuccessMessage, setProfileSuccessMessage] = useState<string | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);

  // Edit Profile Modal
  const [showEditModal, setShowEditModal] = useState(false);
  const [editNameInput, setEditNameInput] = useState(displayName);
  const [isSavingProfile, setIsSavingProfile] = useState(false);
  const [isUploadingAvatar, setIsUploadingAvatar] = useState(false);
  const avatarInputRef = useRef<HTMLInputElement>(null);
  const modalAvatarInputRef = useRef<HTMLInputElement>(null);

  // Synchronize editNameInput when user changes
  useEffect(() => {
    setEditNameInput(displayName);
  }, [displayName]);

  // ── Financial Data State ────────────────────────────────────
  const [summaryData, setSummaryData] = useState<FinancialSummary | null>(null);
  const [loadingData, setLoadingData] = useState(true);
  const [dataError, setDataError] = useState<string | null>(null);
  const [dataRetryKey, setDataRetryKey] = useState(0);

  useEffect(() => {
    const token = getStoredAccessToken();
    if (!token) {
      setDataError("Financial data is unavailable.");
      setLoadingData(false);
      return;
    }

    let cancelled = false;
    setLoadingData(true);
    setDataError(null);

    transactionApi
      .summary(token)
      .then((data) => {
        if (cancelled) return;
        setSummaryData(data);
        setLoadingData(false);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          onLogout();
          return;
        }
        setSummaryData(null);
        setDataError(
          err instanceof ApiError
            ? err.message
            : "Financial data is unavailable."
        );
        setLoadingData(false);
      });

    return () => {
      cancelled = true;
    };
  }, [dataRetryKey, onLogout]);

  // ── Password Modal State ─────────────────────────────────────
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [passwordModalError, setPasswordModalError] = useState<string | null>(null);

  const handleChangePassword = async () => {
    setPasswordModalError(null);
    if (!currentPassword) {
      setPasswordModalError("Current password is required.");
      return;
    }
    if (!newPassword) {
      setPasswordModalError("New password is required.");
      return;
    }
    if (newPassword.length < 8) {
      setPasswordModalError("Password must be at least 8 characters long.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordModalError("New password and confirmation do not match.");
      return;
    }
    const token = getStoredAccessToken();
    if (!token) {
      onLogout();
      return;
    }
    setPasswordSaving(true);
    try {
      await authApi.changePassword(
        { current_password: currentPassword, new_password: newPassword },
        token
      );
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setShowPasswordModal(false);
      setProfileSuccessMessage("Password changed successfully.");
      setTimeout(() => setProfileSuccessMessage(null), 4000);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) onLogout();
      else {
        setPasswordModalError(
          err instanceof ApiError
            ? err.message
            : "Unable to change your password."
        );
      }
    } finally {
      setPasswordSaving(false);
    }
  };

  // ── Avatar Upload & Remove ───────────────────────────────────
  const handleAvatarSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.type.match(/^image\/(jpeg|jpg|png|webp)$/i)) {
      setProfileError("Please select a valid image file (JPEG, PNG, or WebP).");
      return;
    }

    if (file.size > 5 * 1024 * 1024) {
      setProfileError("Image size must be less than 5 MB.");
      return;
    }

    const token = getStoredAccessToken();
    if (!token) {
      onLogout();
      return;
    }

    setIsUploadingAvatar(true);
    setProfileError(null);
    try {
      const updatedUser = await authApi.uploadAvatar(file, token);
      onUserUpdate?.(updatedUser);
      setProfileSuccessMessage("Profile photo updated.");
      setTimeout(() => setProfileSuccessMessage(null), 3500);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) onLogout();
      else {
        setProfileError(
          err instanceof ApiError ? err.message : "Failed to upload avatar."
        );
      }
    } finally {
      setIsUploadingAvatar(false);
      if (avatarInputRef.current) avatarInputRef.current.value = "";
      if (modalAvatarInputRef.current) modalAvatarInputRef.current.value = "";
    }
  };

  const handleRemoveAvatar = async () => {
    const token = getStoredAccessToken();
    if (!token) {
      onLogout();
      return;
    }

    setIsUploadingAvatar(true);
    setProfileError(null);
    try {
      const updatedUser = await authApi.deleteAvatar(token);
      onUserUpdate?.(updatedUser);
      setProfileSuccessMessage("Profile photo removed.");
      setTimeout(() => setProfileSuccessMessage(null), 3500);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) onLogout();
      else {
        setProfileError(
          err instanceof ApiError ? err.message : "Failed to remove avatar."
        );
      }
    } finally {
      setIsUploadingAvatar(false);
    }
  };

  const handleSaveProfile = async () => {
    const trimmed = editNameInput.trim();
    if (!trimmed) {
      setProfileError("Name cannot be empty.");
      return;
    }

    const token = getStoredAccessToken();
    if (!token) {
      onLogout();
      return;
    }

    setIsSavingProfile(true);
    setProfileError(null);
    try {
      const updatedUser = await authApi.updateProfile(
        { display_name: trimmed },
        token
      );
      onUserUpdate?.(updatedUser);
      setShowEditModal(false);
      setProfileSuccessMessage("Profile updated successfully.");
      setTimeout(() => setProfileSuccessMessage(null), 3500);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) onLogout();
      else {
        setProfileError(
          err instanceof ApiError ? err.message : "Failed to update profile."
        );
      }
    } finally {
      setIsSavingProfile(false);
    }
  };

  // ── Data Export ──────────────────────────────────────────────
  const [exportingFormat, setExportingFormat] = useState<"json" | "csv" | "pdf" | null>(null);
  const [exportSuccessMessage, setExportSuccessMessage] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  const handleExportData = async (format: "json" | "csv" | "pdf" = "json") => {
    if (exportingFormat !== null) return;
    const token = getStoredAccessToken();
    if (!token) {
      onLogout();
      return;
    }

    setExportingFormat(format);
    setProfileError(null);
    setExportError(null);
    try {
      const { blob, filename: serverFilename } = await authApi.exportData(token, format);
      const todayStr = new Date().toISOString().split("T")[0];
      const fallbackFilename =
        format === "pdf"
          ? `FinSight_Financial_Report_${todayStr}.pdf`
          : format === "json"
          ? "finsight_financial_export.json"
          : "finsight_transactions.csv";
      const resolvedFilename = serverFilename || fallbackFilename;

      const downloadUrl = URL.createObjectURL(blob);
      const downloadAnchor = document.createElement("a");
      downloadAnchor.href = downloadUrl;
      downloadAnchor.download = resolvedFilename;
      document.body.appendChild(downloadAnchor);
      downloadAnchor.click();
      document.body.removeChild(downloadAnchor);

      setTimeout(() => {
        URL.revokeObjectURL(downloadUrl);
      }, 1000);

      const successMsg =
        format === "pdf"
          ? "Financial Analysis Report downloaded as PDF."
          : `Financial data exported as ${format.toUpperCase()}.`;
      setProfileSuccessMessage(successMsg);
      setExportSuccessMessage(successMsg);
      setTimeout(() => {
        setProfileSuccessMessage(null);
        setExportSuccessMessage(null);
      }, 3500);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        onLogout();
      } else {
        const errorMsg =
          err instanceof ApiError
            ? err.message
            : err instanceof Error
            ? err.message
            : "Unable to export data.";
        if (import.meta.env.DEV) {
          console.error(
            `[FinSight Export] Failed to export ${format.toUpperCase()}:`,
            err instanceof ApiError ? `Status ${err.status} - ${err.message}` : err
          );
        }
        setProfileError(errorMsg);
        setExportError(errorMsg);
      }
    } finally {
      setExportingFormat(null);
    }
  };

  const resolvedAvatarUrl = getAvatarUrl(user.avatar_url);
  const initials = displayName.slice(0, 2).toUpperCase();

  return (
    <div className="w-full max-w-[1400px] mx-auto p-5 sm:p-8 lg:p-10 space-y-7 select-none text-slate-100">
      {/* ─────────────────────────────────────────────────────────────
          PAGE HEADER
      ───────────────────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="w-12 h-12 rounded-2xl bg-indigo-500/15 border border-indigo-500/25 flex items-center justify-center text-indigo-400 shadow-[0_0_15px_rgba(99,102,241,0.15)] shrink-0">
            <Settings size={22} />
          </div>
          <div>
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-white">
              Settings
            </h1>
            <p className="text-xs sm:text-sm text-slate-400 mt-0.5">
              Manage your account, security, and financial data.
            </p>
          </div>
        </div>

        {/* Global Notifications / Alerts */}
        <div className="flex items-center gap-2">
          {profileSuccessMessage && (
            <motion.div
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              role="status"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-emerald-500/30 bg-emerald-500/10 text-emerald-400 text-xs font-medium shadow-sm"
            >
              <Check size={13} />
              <span>{profileSuccessMessage}</span>
            </motion.div>
          )}

          {profileError && (
            <motion.div
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              role="alert"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-rose-500/30 bg-rose-500/10 text-rose-400 text-xs font-medium shadow-sm"
            >
              <AlertCircle size={13} />
              <span>{profileError}</span>
              <button
                onClick={() => setProfileError(null)}
                className="ml-1 text-rose-400 hover:text-white"
                aria-label="Dismiss alert"
              >
                <X size={12} />
              </button>
            </motion.div>
          )}
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          2-COLUMN TOP ROW: Account Profile & Financial Data
      ───────────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-stretch">
        {/* ── CARD 1: ACCOUNT PROFILE ─────────────────────────────── */}
        <div className="rounded-2xl bg-[#090e1c] border border-white/[0.08] p-5 sm:p-6 shadow-sm flex flex-col justify-between space-y-6">
          <div className="space-y-5">
            {/* Header */}
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-indigo-500/15 border border-indigo-500/25 flex items-center justify-center text-indigo-400 shrink-0">
                <User size={18} />
              </div>
              <div>
                <h2 className="text-sm font-bold text-white">Account Profile</h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  Your personal and account details.
                </p>
              </div>
            </div>

            {/* Profile Bar */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-xl bg-[#0f172a] border border-white/[0.06]">
              <div className="flex items-center gap-3.5 min-w-0">
                <div className="relative group shrink-0">
                  {resolvedAvatarUrl ? (
                    <img
                      src={resolvedAvatarUrl}
                      alt={displayName}
                      className="w-14 h-14 rounded-full object-cover border-2 border-indigo-500/40 shadow-sm"
                    />
                  ) : (
                    <div className="w-14 h-14 rounded-full bg-gradient-to-tr from-indigo-600 via-indigo-500 to-cyan-400 text-white font-bold text-lg flex items-center justify-center border-2 border-white/20 shadow-md">
                      {initials}
                    </div>
                  )}

                  <button
                    onClick={() => avatarInputRef.current?.click()}
                    disabled={isUploadingAvatar}
                    className="absolute inset-0 rounded-full bg-black/60 opacity-0 group-hover:opacity-100 flex items-center justify-center text-white transition-opacity cursor-pointer disabled:cursor-not-allowed"
                    title="Change profile photo"
                    aria-label="Change profile photo"
                  >
                    <Camera size={18} />
                  </button>
                  <input
                    ref={avatarInputRef}
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    onChange={handleAvatarSelect}
                    className="hidden"
                  />
                </div>

                <div className="min-w-0 space-y-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-bold text-white text-sm truncate">
                      {displayName}
                    </span>
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-emerald-500/10 border border-emerald-500/25 text-emerald-400">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                      Authenticated
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 truncate font-mono">
                    {user.email}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2 self-start sm:self-center shrink-0">
                <button
                  onClick={() => {
                    setEditNameInput(displayName);
                    setShowEditModal(true);
                  }}
                  className="px-3.5 py-2 rounded-xl border border-indigo-500/40 bg-indigo-500/10 hover:bg-indigo-500/20 text-xs font-semibold text-indigo-300 hover:text-white transition-all flex items-center gap-1.5 shadow-sm"
                >
                  <User size={13} className="text-indigo-400" />
                  <span>Edit Profile</span>
                </button>

                {resolvedAvatarUrl && (
                  <button
                    onClick={handleRemoveAvatar}
                    disabled={isUploadingAvatar}
                    className="p-2 rounded-xl border border-white/10 bg-white/[0.04] hover:bg-rose-500/10 hover:border-rose-500/30 text-slate-400 hover:text-rose-400 transition-all text-xs"
                    title="Remove profile photo"
                    aria-label="Remove profile photo"
                  >
                    <Trash2 size={14} />
                  </button>
                )}
              </div>
            </div>

            {/* Profile Key-Value Rows */}
            <div className="divide-y divide-white/[0.06] pt-1">
              <div className="py-3 flex items-center justify-between text-xs">
                <span className="text-slate-400">Full Name</span>
                <span className="font-semibold text-white">{displayName}</span>
              </div>
              <div className="py-3 flex items-center justify-between text-xs">
                <span className="text-slate-400">Email Address</span>
                <span className="font-mono text-slate-300">{user.email}</span>
              </div>
            </div>
          </div>
        </div>

        {/* ── CARD 2: FINANCIAL DATA ──────────────────────────────── */}
        <div className="rounded-2xl bg-[#090e1c] border border-white/[0.08] p-5 sm:p-6 shadow-sm flex flex-col justify-between space-y-6">
          <div className="space-y-5">
            {/* Header */}
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-indigo-500/15 border border-indigo-500/25 flex items-center justify-center text-indigo-400 shrink-0">
                <FileText size={18} />
              </div>
              <div>
                <h2 className="text-sm font-bold text-white">Financial Data</h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  Summary of your uploaded transactions.
                </p>
              </div>
            </div>

            {/* Loading / Error States */}
            {loadingData ? (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {[1, 2, 3].map((i) => (
                  <div
                    key={i}
                    className="p-4 rounded-xl bg-[#0f172a] border border-white/[0.06] flex flex-col justify-between space-y-3 animate-pulse"
                  >
                    <div className="w-8 h-8 rounded-lg bg-white/[0.05]" />
                    <div className="space-y-1.5">
                      <div className="w-16 h-2.5 bg-white/[0.05] rounded" />
                      <div className="w-24 h-4 bg-white/[0.08] rounded" />
                      <div className="w-20 h-2 bg-white/[0.04] rounded" />
                    </div>
                  </div>
                ))}
              </div>
            ) : dataError ? (
              <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/25 flex items-center justify-between gap-4">
                <p className="text-xs text-rose-300">{dataError}</p>
                <button
                  onClick={() => setDataRetryKey((v) => v + 1)}
                  className="rounded-lg border border-rose-500/30 px-2.5 py-1 text-xs font-semibold text-rose-300 hover:bg-rose-500/20"
                >
                  Retry
                </button>
              </div>
            ) : (
              /* 3 Highlight Metric Cards matching reference screenshot */
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {/* 1. Total Transactions */}
                <div className="p-4 rounded-xl bg-[#0f172a] border border-white/[0.06] flex flex-col justify-between space-y-3">
                  <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
                    <FileText size={16} />
                  </div>
                  <div>
                    <p className="text-[11px] font-medium text-slate-400">
                      Total Transactions
                    </p>
                    <p className="text-xl font-bold text-white mt-0.5 tracking-tight">
                      {summaryData?.total_transactions !== undefined
                        ? summaryData.total_transactions.toLocaleString("en-IN")
                        : "—"}
                    </p>
                    <p className="text-[10px] text-slate-500 mt-0.5">
                      Valid rows processed
                    </p>
                  </div>
                </div>

                {/* 2. Date Range */}
                <div className="p-4 rounded-xl bg-[#0f172a] border border-white/[0.06] flex flex-col justify-between space-y-3">
                  <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
                    <Calendar size={16} />
                  </div>
                  <div>
                    <p className="text-[11px] font-medium text-slate-400">
                      Date Range
                    </p>
                    <p className="text-xs font-bold text-white mt-1 leading-snug">
                      {summaryData?.start_date && summaryData?.end_date
                        ? `${new Date(summaryData.start_date).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })} – ${new Date(summaryData.end_date).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}`
                        : "No data available"}
                    </p>
                    <p className="text-[10px] text-slate-500 mt-1">
                      Historical period
                    </p>
                  </div>
                </div>

                {/* 3. Last Analyzed */}
                <div className="p-4 rounded-xl bg-[#0f172a] border border-white/[0.06] flex flex-col justify-between space-y-3">
                  <div className="w-8 h-8 rounded-lg bg-teal-500/10 border border-teal-500/20 flex items-center justify-center text-teal-400">
                    <TrendingUp size={16} />
                  </div>
                  <div>
                    <p className="text-[11px] font-medium text-slate-400">
                      Last Analyzed
                    </p>
                    <p className="text-xs font-bold text-white mt-1 leading-snug">
                      {summaryData?.last_analyzed
                        ? new Date(summaryData.last_analyzed).toLocaleDateString("en-US", {
                            month: "short",
                            day: "numeric",
                            year: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          })
                        : "Unavailable"}
                    </p>
                    <p className="text-[10px] text-slate-500 mt-1">
                      FinSight intelligence
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          2-COLUMN BOTTOM ROW: Security & Privacy & Data
      ───────────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-stretch">
        {/* ── CARD 3: SECURITY ────────────────────────────────────── */}
        <div className="rounded-2xl bg-[#090e1c] border border-white/[0.08] p-5 sm:p-6 shadow-sm flex flex-col justify-between space-y-6">
          <div className="space-y-5">
            {/* Header */}
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-indigo-500/15 border border-indigo-500/25 flex items-center justify-center text-indigo-400 shrink-0">
                <Lock size={18} />
              </div>
              <div>
                <h2 className="text-sm font-bold text-white">Security</h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  Manage your password and account security.
                </p>
              </div>
            </div>

            <div className="space-y-3">
              {/* Row 1: Change Password */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-xl bg-[#0f172a] border border-white/[0.06]">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 shrink-0">
                    <KeyRound size={15} />
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-white">
                      Change Password
                    </p>
                    <p className="text-[11px] text-slate-400">
                      Update your password to keep your account secure.
                    </p>
                  </div>
                </div>

                <button
                  onClick={() => {
                    setPasswordModalError(null);
                    setShowPasswordModal(true);
                  }}
                  className="px-3.5 py-1.5 rounded-xl border border-indigo-500/30 bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-300 hover:text-white text-xs font-semibold transition-all flex items-center gap-1.5 shrink-0 self-start sm:self-center"
                >
                  <span>Change Password</span>
                  <ChevronRight size={13} />
                </button>
              </div>

              {/* Row 2: Sign Out */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-xl bg-[#0f172a] border border-white/[0.06]">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-rose-500/10 border border-rose-500/20 flex items-center justify-center text-rose-400 shrink-0">
                    <LogOut size={15} />
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-white">Sign Out</p>
                    <p className="text-[11px] text-slate-400">
                      Sign out from your account on this device.
                    </p>
                  </div>
                </div>

                <button
                  onClick={onLogout}
                  className="px-3.5 py-1.5 rounded-xl border border-rose-500/30 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 hover:text-rose-300 text-xs font-semibold transition-all flex items-center gap-1.5 shrink-0 self-start sm:self-center"
                >
                  <span>Sign Out</span>
                  <ChevronRight size={13} />
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* ── CARD 4: PRIVACY & DATA ──────────────────────────────── */}
        <div className="rounded-2xl bg-[#090e1c] border border-white/[0.08] p-5 sm:p-6 shadow-sm flex flex-col justify-between space-y-6">
          <div className="space-y-5">
            {/* Header */}
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-indigo-500/15 border border-indigo-500/25 flex items-center justify-center text-indigo-400 shrink-0">
                <Shield size={18} />
              </div>
              <div>
                <h2 className="text-sm font-bold text-white">Privacy & Data</h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  Control your data and export options.
                </p>
              </div>
            </div>

            <div className="space-y-3">
              {/* Inline export feedback */}
              {exportSuccessMessage && (
                <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs flex items-center gap-2">
                  <Check size={14} className="shrink-0 text-emerald-400" />
                  <span>{exportSuccessMessage}</span>
                </div>
              )}
              {exportError && (
                <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <AlertCircle size={14} className="shrink-0 text-rose-400" />
                    <span className="truncate">{exportError}</span>
                  </div>
                  <button
                    onClick={() => setExportError(null)}
                    className="text-rose-400 hover:text-white shrink-0 p-0.5"
                    aria-label="Dismiss export error"
                  >
                    <X size={12} />
                  </button>
                </div>
              )}

              {/* Row 1: Financial Analysis Report (PDF) - Primary Action */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3.5 p-4 rounded-xl bg-[#0f172a] border border-white/[0.06] hover:border-white/[0.1] transition-colors">
                <div className="flex items-start sm:items-center gap-3 min-w-0 flex-1">
                  <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 shrink-0 mt-0.5 sm:mt-0">
                    <FileText size={15} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-semibold text-white">Financial Analysis Report</p>
                    <p className="text-[11px] text-slate-400 leading-relaxed mt-0.5">
                      Download a professional report of your financial analysis, recurring commitments, exposure, and available predictive insights.
                    </p>
                  </div>
                </div>

                <div className="flex items-center shrink-0 self-start sm:self-center w-full sm:w-auto">
                  <button
                    type="button"
                    onClick={() => handleExportData("pdf")}
                    disabled={exportingFormat !== null}
                    className="w-full sm:w-auto px-3.5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white text-xs font-semibold shadow-sm shadow-indigo-600/20 transition-all flex items-center justify-center gap-1.5 shrink-0 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
                    title="Download complete Financial Analysis Report as PDF"
                  >
                    {exportingFormat === "pdf" ? (
                      <>
                        <Loader2 size={13} className="animate-spin text-indigo-200 shrink-0" />
                        <span>Generating PDF Report...</span>
                      </>
                    ) : (
                      <>
                        <FileText size={13} className="shrink-0" />
                        <span>Download PDF Report</span>
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* Row 2: Raw Data Export (JSON) - Secondary Action */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3.5 p-4 rounded-xl bg-[#0f172a] border border-white/[0.06] hover:border-white/[0.1] transition-colors">
                <div className="flex items-start sm:items-center gap-3 min-w-0 flex-1">
                  <div className="w-8 h-8 rounded-lg bg-white/[0.04] border border-white/[0.08] flex items-center justify-center text-slate-400 shrink-0 mt-0.5 sm:mt-0">
                    <Download size={15} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-semibold text-white">Raw Data Export</p>
                    <p className="text-[11px] text-slate-400 leading-relaxed mt-0.5">
                      Download your available financial data and transactions in JSON format.
                    </p>
                  </div>
                </div>

                <div className="flex items-center shrink-0 self-start sm:self-center w-full sm:w-auto">
                  <button
                    type="button"
                    onClick={() => handleExportData("json")}
                    disabled={exportingFormat !== null}
                    className="w-full sm:w-auto px-3.5 py-2 rounded-xl border border-white/[0.1] bg-white/[0.05] hover:bg-white/[0.1] active:bg-white/[0.15] text-slate-300 hover:text-white text-xs font-medium transition-all flex items-center justify-center gap-1.5 shrink-0 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer focus:outline-none focus:ring-2 focus:ring-slate-500/50"
                    title="Download raw financial data as verified JSON"
                  >
                    {exportingFormat === "json" ? (
                      <>
                        <Loader2 size={13} className="animate-spin text-slate-400 shrink-0" />
                        <span>Exporting JSON...</span>
                      </>
                    ) : (
                      <>
                        <Download size={13} className="text-slate-400 shrink-0" />
                        <span>Export JSON</span>
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* Row 2: Data Privacy Box */}
              <div className="p-4 rounded-xl bg-[#0f172a] border border-white/[0.06] space-y-1.5">
                <div className="flex items-center gap-2">
                  <Info size={14} className="text-indigo-400 shrink-0" />
                  <p className="text-xs font-semibold text-white">Data Privacy</p>
                </div>
                <p className="text-[11px] text-slate-400 leading-relaxed pl-5">
                  Your transactions are processed securely for financial intelligence calculation. No third-party data broker sharing or marketing models.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          EDIT PROFILE MODAL
      ───────────────────────────────────────────────────────────── */}
      <AnimatePresence>
        {showEditModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setShowEditModal(false)}
              className="fixed inset-0 bg-black/75 backdrop-blur-sm"
            />

            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="relative w-full max-w-md rounded-2xl bg-[#090e1c] border border-white/10 p-4 sm:p-6 shadow-2xl z-10 space-y-4 sm:space-y-5 text-white max-h-[90vh] overflow-y-auto"
            >
              <div className="flex items-center justify-between border-b border-white/[0.08] pb-3">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-xl bg-indigo-500/15 border border-indigo-500/25 flex items-center justify-center text-indigo-400">
                    <User size={16} />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white">Edit Profile</h3>
                    <p className="text-[11px] text-slate-400">
                      Update your account details and profile picture.
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setShowEditModal(false)}
                  className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-white/[0.06] transition-colors"
                >
                  <X size={16} />
                </button>
              </div>

              {/* Photo Upload Area */}
              <div className="flex items-center gap-4 p-3.5 rounded-xl bg-[#0f172a] border border-white/[0.06]">
                <div className="relative group shrink-0">
                  {resolvedAvatarUrl ? (
                    <img
                      src={resolvedAvatarUrl}
                      alt={displayName}
                      className="w-14 h-14 rounded-full object-cover border-2 border-indigo-500/40"
                    />
                  ) : (
                    <div className="w-14 h-14 rounded-full bg-gradient-to-tr from-indigo-600 to-indigo-400 text-white font-bold text-base flex items-center justify-center border border-white/20">
                      {initials}
                    </div>
                  )}
                </div>

                <div className="flex-1 space-y-1.5">
                  <p className="text-xs font-semibold text-white">Profile Photo</p>
                  <p className="text-[10px] text-slate-400">
                    Supports JPEG, PNG, or WebP under 5 MB.
                  </p>
                  <div className="flex items-center gap-2 pt-1">
                    <button
                      type="button"
                      onClick={() => modalAvatarInputRef.current?.click()}
                      disabled={isUploadingAvatar}
                      className="px-2.5 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-[11px] font-semibold transition-all flex items-center gap-1 disabled:opacity-50"
                    >
                      <Camera size={12} />
                      <span>{isUploadingAvatar ? "Uploading…" : "Upload Photo"}</span>
                    </button>
                    <input
                      ref={modalAvatarInputRef}
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      onChange={handleAvatarSelect}
                      className="hidden"
                    />
                    {resolvedAvatarUrl && (
                      <button
                        type="button"
                        onClick={handleRemoveAvatar}
                        disabled={isUploadingAvatar}
                        className="px-2.5 py-1 rounded-lg border border-rose-500/30 text-rose-400 hover:bg-rose-500/10 text-[11px] font-semibold transition-all"
                      >
                        Remove
                      </button>
                    )}
                  </div>
                </div>
              </div>

              {/* Display Name Input */}
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-slate-300">
                  Display Name
                </label>
                <input
                  type="text"
                  value={editNameInput}
                  onChange={(e) => setEditNameInput(e.target.value)}
                  placeholder="Enter your name"
                  className="w-full rounded-xl border border-white/10 bg-[#0f172a] px-3.5 py-2 text-sm text-white focus:outline-none focus:border-indigo-500 transition-colors"
                />
              </div>

              {/* Email (Read-Only) */}
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-slate-400">
                  Email Address (Verified)
                </label>
                <input
                  type="email"
                  value={user.email}
                  disabled
                  className="w-full rounded-xl border border-white/[0.06] bg-[#0f172a]/50 px-3.5 py-2 text-xs font-mono text-slate-400 cursor-not-allowed"
                />
              </div>

              {/* Actions */}
              <div className="pt-2 flex justify-end gap-2 border-t border-white/[0.08]">
                <button
                  type="button"
                  onClick={() => setShowEditModal(false)}
                  className="px-4 py-2 rounded-xl border border-white/10 hover:bg-white/[0.06] text-xs font-medium text-slate-300 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleSaveProfile}
                  disabled={isSavingProfile || !editNameInput.trim()}
                  className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition-all disabled:opacity-50 shadow-md shadow-indigo-600/30"
                >
                  {isSavingProfile ? "Saving…" : "Save Changes"}
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* ─────────────────────────────────────────────────────────────
          CHANGE PASSWORD MODAL
      ───────────────────────────────────────────────────────────── */}
      <AnimatePresence>
        {showPasswordModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setShowPasswordModal(false)}
              className="fixed inset-0 bg-black/75 backdrop-blur-sm"
            />

            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="relative w-full max-w-md rounded-2xl bg-[#090e1c] border border-white/10 p-4 sm:p-6 shadow-2xl z-10 space-y-4 text-white max-h-[90vh] overflow-y-auto"
            >
              <div className="flex items-center justify-between border-b border-white/[0.08] pb-3">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-xl bg-indigo-500/15 border border-indigo-500/25 flex items-center justify-center text-indigo-400">
                    <KeyRound size={16} />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white">Change Password</h3>
                    <p className="text-[11px] text-slate-400">
                      Update your account security credentials.
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setShowPasswordModal(false)}
                  className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-white/[0.06] transition-colors"
                >
                  <X size={16} />
                </button>
              </div>

              {passwordModalError && (
                <div
                  role="alert"
                  className="p-3 rounded-xl border border-rose-500/30 bg-rose-500/10 text-rose-300 text-xs flex items-center gap-2"
                >
                  <AlertCircle size={14} className="shrink-0" />
                  <span>{passwordModalError}</span>
                </div>
              )}

              <div className="space-y-3">
                <label className="block space-y-1">
                  <span className="text-xs font-medium text-slate-300">
                    Current Password
                  </span>
                  <input
                    type="password"
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    className="w-full rounded-xl border border-white/10 bg-[#0f172a] px-3.5 py-2 text-sm text-white focus:outline-none focus:border-indigo-500 transition-colors"
                    autoComplete="current-password"
                  />
                </label>

                <label className="block space-y-1">
                  <span className="text-xs font-medium text-slate-300">
                    New Password
                  </span>
                  <input
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    className="w-full rounded-xl border border-white/10 bg-[#0f172a] px-3.5 py-2 text-sm text-white focus:outline-none focus:border-indigo-500 transition-colors"
                    autoComplete="new-password"
                  />
                  <span className="text-[10px] text-slate-500">
                    Minimum 8 characters.
                  </span>
                </label>

                <label className="block space-y-1">
                  <span className="text-xs font-medium text-slate-300">
                    Confirm New Password
                  </span>
                  <input
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="w-full rounded-xl border border-white/10 bg-[#0f172a] px-3.5 py-2 text-sm text-white focus:outline-none focus:border-indigo-500 transition-colors"
                    autoComplete="new-password"
                  />
                </label>
              </div>

              <div className="pt-2 flex justify-end gap-2 border-t border-white/[0.08]">
                <button
                  type="button"
                  onClick={() => setShowPasswordModal(false)}
                  className="px-4 py-2 rounded-xl border border-white/10 hover:bg-white/[0.06] text-xs font-medium text-slate-300 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleChangePassword}
                  disabled={
                    passwordSaving ||
                    !currentPassword ||
                    !newPassword ||
                    !confirmPassword
                  }
                  className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-md shadow-indigo-600/30 transition-all disabled:opacity-50"
                >
                  {passwordSaving ? "Updating…" : "Update Password"}
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
