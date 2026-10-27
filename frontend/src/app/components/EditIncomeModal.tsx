import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "motion/react";
import { X, Check, AlertCircle, Loader2, Sparkles, Wallet } from "lucide-react";
import {
  incomeApi,
  IncomeMode,
  IncomeConfigurationUpdateRequest,
} from "../../api/client";

interface EditIncomeModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  currentIncome: number;
  currentMode?: string;
  currentSource?: string;
  manualIncomeValue?: number | null;
  expectedIncomeValue?: number | null;
  token: string;
}

export function EditIncomeModal({
  isOpen,
  onClose,
  onSuccess,
  currentIncome,
  currentMode = "auto",
  currentSource = "Observed",
  manualIncomeValue,
  expectedIncomeValue,
  token,
}: EditIncomeModalProps) {
  const [mode, setMode] = useState<"auto" | "manual">("auto");
  const [manualAmount, setManualAmount] = useState<string>("");
  const [effectiveDate, setEffectiveDate] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      const validMode = currentMode === "manual" ? "manual" : "auto";
      setMode(validMode);
      setManualAmount(
        manualIncomeValue && manualIncomeValue > 0
          ? String(Math.round(manualIncomeValue))
          : currentIncome > 0
          ? String(Math.round(currentIncome))
          : ""
      );
      setEffectiveDate("");
      setError(null);
    }
  }, [isOpen, currentMode, currentIncome, manualIncomeValue]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const payload: IncomeConfigurationUpdateRequest = {
      income_mode: mode,
    };

    if (mode === "manual") {
      const parsedManual = parseFloat(manualAmount.replace(/,/g, "").trim());
      if (isNaN(parsedManual) || parsedManual <= 0) {
        setError("Please enter a valid monthly income greater than ₹0.");
        return;
      }
      if (parsedManual > 1_000_000_000) {
        setError("Monthly income cannot exceed ₹100,00,00,000.");
        return;
      }
      payload.manual_monthly_income = parsedManual;
    }

    if (effectiveDate) {
      payload.effective_date = effectiveDate;
    }

    setLoading(true);
    try {
      await incomeApi.updateConfig(payload, token);
      onSuccess();
      onClose();
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to update income configuration.";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 10 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 10 }}
          transition={{ duration: 0.2 }}
          className="relative w-full max-w-lg rounded-2xl border border-white/10 bg-[#0d1322] p-4 sm:p-6 shadow-2xl text-slate-100 max-h-[90vh] overflow-y-auto"
          role="dialog"
          aria-labelledby="income-modal-title"
        >
          {/* Close button */}
          <button
            type="button"
            onClick={onClose}
            className="absolute top-4 right-4 p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
            aria-label="Close modal"
          >
            <X size={18} />
          </button>

          {/* Header */}
          <div className="flex items-center gap-3 mb-5">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20">
              <Wallet size={20} />
            </div>
            <div>
              <h2 id="income-modal-title" className="text-lg font-bold text-white tracking-tight">
                Configure Monthly Income
              </h2>
              <p className="text-xs text-slate-400">
                Adjust how your income capacity is evaluated across FinSight.
              </p>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Mode Selector */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                Income Calculation Mode
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {/* Auto Mode */}
                <button
                  type="button"
                  onClick={() => setMode("auto")}
                  className={`flex flex-col items-start p-3 rounded-xl border text-left transition-all ${
                    mode === "auto"
                      ? "border-blue-500 bg-blue-500/15 text-white"
                      : "border-white/10 bg-white/[0.02] text-slate-400 hover:border-white/20 hover:text-slate-200"
                  }`}
                >
                  <div className="flex items-center justify-between w-full">
                    <span className="text-xs font-bold text-white">Automatic</span>
                    {mode === "auto" && <Check size={14} className="text-blue-400" />}
                  </div>
                  <span className="text-[11px] text-slate-400 mt-1">Auto-detected from deposits</span>
                </button>

                {/* Manual Mode */}
                <button
                  type="button"
                  onClick={() => setMode("manual")}
                  className={`flex flex-col items-start p-3 rounded-xl border text-left transition-all ${
                    mode === "manual"
                      ? "border-emerald-500 bg-emerald-500/15 text-white"
                      : "border-white/10 bg-white/[0.02] text-slate-400 hover:border-white/20 hover:text-slate-200"
                  }`}
                >
                  <div className="flex items-center justify-between w-full">
                    <span className="text-xs font-bold text-white">Manual</span>
                    {mode === "manual" && <Check size={14} className="text-emerald-400" />}
                  </div>
                  <span className="text-[11px] text-slate-400 mt-1">Custom verified salary</span>
                </button>
              </div>
            </div>

            {/* Explanatory Guidance Card */}
            <div className="rounded-xl border border-white/[0.08] bg-slate-900/60 p-3 text-xs leading-relaxed text-slate-300">
              {mode === "auto" ? (
                <div className="flex items-start gap-2">
                  <Sparkles size={16} className="text-blue-400 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-semibold text-white">Automatic Detection:</span> FinSight continuously evaluates your transaction history to determine monthly salary deposits. (Currently: <span className="font-mono font-medium text-emerald-400">₹{Math.round(currentIncome).toLocaleString("en-IN")}</span>).
                  </div>
                </div>
              ) : (
                <div className="flex items-start gap-2">
                  <Wallet size={16} className="text-emerald-400 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-semibold text-white">Manual Current Salary:</span> Overrides transaction detection. This amount directly updates your Exposure Score, Available Capacity, and Financial Health.
                  </div>
                </div>
              )}
            </div>

            {/* Inputs based on Mode */}
            {mode === "manual" && (
              <div>
                <label
                  htmlFor="manual-income-input"
                  className="block text-xs font-semibold text-slate-300 mb-1"
                >
                  Monthly Take-Home Salary (₹)
                </label>
                <div className="relative">
                  <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 font-mono font-medium text-sm">
                    ₹
                  </span>
                  <input
                    id="manual-income-input"
                    type="number"
                    step="any"
                    min="1"
                    max="1000000000"
                    value={manualAmount}
                    onChange={(e) => setManualAmount(e.target.value)}
                    placeholder="e.g. 85000"
                    required
                    className="w-full rounded-xl border border-white/10 bg-black/40 pl-8 pr-4 py-2.5 text-sm font-mono text-white placeholder-slate-500 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 focus:outline-none transition-all"
                  />
                </div>
              </div>
            )}

            {/* Optional Effective Date */}
            {mode !== "auto" && (
              <div>
                <label
                  htmlFor="effective-date-input"
                  className="block text-xs font-semibold text-slate-300 mb-1"
                >
                  Effective Date <span className="text-slate-500 font-normal">(Optional)</span>
                </label>
                <input
                  id="effective-date-input"
                  type="date"
                  value={effectiveDate}
                  onChange={(e) => setEffectiveDate(e.target.value)}
                  className="w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2 text-sm text-slate-200 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none transition-all"
                />
              </div>
            )}

            {/* Error Message */}
            {error && (
              <div className="flex items-center gap-2 p-3 rounded-xl border border-red-500/20 bg-red-500/10 text-red-400 text-xs">
                <AlertCircle size={15} className="shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {/* Buttons */}
            <div className="flex items-center justify-end gap-3 pt-3 border-t border-white/[0.08]">
              <button
                type="button"
                onClick={onClose}
                disabled={loading}
                className="px-4 py-2 rounded-xl text-xs font-medium text-slate-400 hover:text-white hover:bg-white/[0.06] transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading}
                className="flex items-center gap-2 px-5 py-2 rounded-xl text-xs font-semibold text-white bg-blue-600 hover:bg-blue-500 disabled:opacity-50 transition-all shadow-md shadow-blue-600/20"
              >
                {loading && <Loader2 size={14} className="animate-spin" />}
                <span>{loading ? "Saving..." : "Save Configuration"}</span>
              </button>
            </div>
          </form>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
