import { useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import {
  AlertTriangle,
  ArrowRight,
  BrainCircuit,
  Check,
  FileText,
  FileUp,
  LoaderCircle,
  X,
  ChevronLeft,
  Columns,
  Table,
  CheckCircle2,
  Calendar,
  DollarSign,
  Info,
} from "lucide-react";
import {
  ApiError,
  getStoredAccessToken,
  transactionApi,
  TransactionUploadResponse,
  ImportPreviewResponse,
} from "../api/client";
import { FinSightLogo } from "./components/FinSightLogo";

type UploadState = "empty" | "selected" | "extracting" | "preview" | "importing" | "success";

interface UploadPageProps {
  onComplete: () => void;
  onUnauthorized: () => void;
  hasExistingData?: boolean;
  onCancel?: () => void;
}

const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50 MB to accommodate larger statements

function formatFileSize(bytes: number) {
  return bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(1)} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function UploadPage({ onComplete, onUnauthorized, hasExistingData = false, onCancel }: UploadPageProps) {
  const [state, setState] = useState<UploadState>("empty");
  const [file, setFile] = useState<File | null>(null);
  const [previewData, setPreviewData] = useState<ImportPreviewResponse | null>(null);
  const [uploadResult, setUploadResult] = useState<TransactionUploadResponse | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const reduceMotion = useReducedMotion();

  function resetFileInput() {
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function chooseAnotherFile() {
    setError(null);
    setFile(null);
    setState("empty");
    setPreviewData(null);
    setUploadResult(null);
    resetFileInput();
    fileInputRef.current?.click();
  }

  function selectFile(selectedFile: File) {
    setError(null);
    const lowerName = selectedFile.name.toLowerCase();
    const isCsv = lowerName.endsWith(".csv");
    const isPdf = lowerName.endsWith(".pdf");

    if (!isCsv && !isPdf) {
      setFile(null);
      setState("empty");
      setError("Supported file types are CSV (.csv) and PDF bank statements (.pdf).");
      resetFileInput();
      return;
    }
    if (selectedFile.size > MAX_FILE_SIZE) {
      setFile(null);
      setState("empty");
      setError("This statement exceeds the 50 MB limit. Please select a smaller file.");
      resetFileInput();
      return;
    }
    setFile(selectedFile);
    setState("selected");
  }

  function handleFileSelect(event: React.ChangeEvent<HTMLInputElement>) {
    const selectedFile = event.target.files?.[0];
    if (selectedFile) selectFile(selectedFile);
  }

  function handleDrop(event: React.DragEvent) {
    event.preventDefault();
    setIsDragOver(false);
    const selectedFile = event.dataTransfer.files?.[0];
    if (selectedFile) selectFile(selectedFile);
  }

  async function generatePreview() {
    if (!file || state === "extracting") return;
    const token = getStoredAccessToken();
    if (!token) {
      onUnauthorized();
      return;
    }

    setError(null);
    setState("extracting");
    try {
      const res = await transactionApi.preview(file, token);
      setPreviewData(res);
      setState("preview");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        onUnauthorized();
        return;
      }
      setError(err instanceof ApiError ? err.message : "Unable to parse this statement. Please verify file format.");
      setState("selected");
    }
  }

  async function confirmImport() {
    if (!previewData?.preview_token || state === "importing") return;
    const token = getStoredAccessToken();
    if (!token) {
      onUnauthorized();
      return;
    }

    setError(null);
    setState("importing");
    try {
      const res = await transactionApi.confirm(previewData.preview_token, token);
      setUploadResult(res);
      setState("success");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        onUnauthorized();
        return;
      }
      setError(err instanceof ApiError ? err.message : "Confirmation failed. Please try re-uploading.");
      setState("preview");
    }
  }

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background px-4 py-8 sm:py-12 select-none">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-40 [background-image:linear-gradient(var(--border)_1px,transparent_1px),linear-gradient(90deg,var(--border)_1px,transparent_1px)] [background-size:48px_48px]"
      />
      <motion.div
        aria-hidden="true"
        animate={reduceMotion ? undefined : { x: [0, 18, 0], y: [0, -14, 0] }}
        transition={{ duration: 12, repeat: Infinity, ease: "easeInOut" }}
        className="pointer-events-none absolute -left-24 top-16 h-72 w-72 rounded-full bg-primary/8 blur-3xl"
      />

      <motion.section
        initial={reduceMotion ? false : { opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45, ease: "easeOut" }}
        className={`relative z-10 w-full ${state === "preview" ? "max-w-4xl" : "max-w-2xl"}`}
        aria-labelledby="upload-title"
      >
        {/* Cancel button if navigating back to dashboard */}
        {onCancel && hasExistingData && (
          <button
            onClick={onCancel}
            className="mb-4 inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <ChevronLeft size={14} />
            <span>Back to Dashboard</span>
          </button>
        )}

        <header className="mb-7 text-center">
          <div className="mb-4 flex items-center justify-center">
            <FinSightLogo variant="full" size="md" showSparkle={true} />
          </div>
          <h1 id="upload-title" className="text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
            {hasExistingData ? "Add to your financial dataset" : "Intelligent Bank Statement Import"}
          </h1>
          <p className="mx-auto mt-2.5 max-w-lg text-sm leading-relaxed text-muted-foreground">
            {hasExistingData
              ? "Upload additional CSV or PDF bank statements. FinSight merges new transactions with automatic deduplication."
              : "Upload a bank statement in CSV or PDF format. FinSight extracts, normalizes, and connects your transactions to intelligent insights."}
          </p>
        </header>

        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,text/csv,application/pdf,.pdf"
          onChange={handleFileSelect}
          className="sr-only"
          aria-label="Choose a transaction CSV or PDF file"
        />

        <AnimatePresence mode="wait">
          {state === "empty" && (
            <motion.div
              key="empty"
              initial={reduceMotion ? false : { opacity: 0, scale: 0.985 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.985 }}
              className="rounded-2xl border border-border bg-card/95 p-4 shadow-xl shadow-black/5 backdrop-blur-sm sm:p-6"
            >
              <div
                role="button"
                tabIndex={0}
                onClick={() => fileInputRef.current?.click()}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    fileInputRef.current?.click();
                  }
                }}
                onDragOver={(event) => {
                  event.preventDefault();
                  setIsDragOver(true);
                }}
                onDragLeave={() => setIsDragOver(false)}
                onDrop={handleDrop}
                className={`group cursor-pointer rounded-xl border border-dashed px-5 py-12 text-center outline-none transition-all sm:px-10 ${
                  isDragOver
                    ? "border-primary bg-primary/8 shadow-inner"
                    : "border-border bg-muted/20 hover:border-primary/50 hover:bg-primary/[0.03] focus-visible:border-primary focus-visible:ring-4 focus-visible:ring-primary/10"
                }`}
              >
                <motion.div
                  animate={reduceMotion ? undefined : isDragOver ? { y: -4, scale: 1.04 } : { y: [0, -3, 0] }}
                  transition={isDragOver ? { duration: 0.2 } : { duration: 3.6, repeat: Infinity, ease: "easeInOut" }}
                  className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-2xl border border-primary/15 bg-primary/8 text-primary"
                >
                  <FileUp size={24} />
                </motion.div>
                <p className="text-base font-semibold text-foreground">Drop your Bank CSV or PDF here</p>
                <p className="mt-1.5 text-sm text-muted-foreground">or click to browse your computer</p>
                <span className="mt-5 inline-flex items-center rounded-lg border border-border bg-card px-3 py-2 text-xs font-medium text-primary transition-colors group-hover:border-primary/30">
                  Browse files
                </span>
                <p className="mt-5 text-xs text-muted-foreground">Supports CSV & Text-based PDF · Up to 50 MB</p>
              </div>

              {error && (
                <div
                  role="alert"
                  className="mt-4 flex items-start justify-between gap-3 rounded-xl border border-destructive/20 bg-destructive/5 px-3.5 py-3 text-sm text-destructive"
                >
                  <span className="flex gap-2">
                    <AlertTriangle size={16} className="mt-0.5 shrink-0" />
                    {error}
                  </span>
                  <button onClick={chooseAnotherFile} className="shrink-0 text-xs font-semibold underline">
                    Choose another
                  </button>
                </div>
              )}
            </motion.div>
          )}

          {state === "selected" && file && (
            <motion.div
              key="selected"
              initial={reduceMotion ? false : { opacity: 0, scale: 0.985 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.985 }}
              className="rounded-2xl border border-border bg-card/95 p-5 sm:p-6 shadow-xl shadow-black/5 backdrop-blur-sm space-y-6"
            >
              {/* File Pill */}
              <div className="flex items-center gap-4 rounded-xl border border-primary/15 bg-primary/[0.035] p-4">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                  <FileText size={20} />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-foreground" title={file.name}>
                    {file.name}
                  </p>
                  <p className="mt-0.5 text-xs text-muted-foreground font-mono">
                    {file.name.toLowerCase().endsWith(".pdf") ? "PDF Statement" : "CSV Statement"} · {formatFileSize(file.size)}
                  </p>
                </div>
                <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1 text-xs font-medium text-emerald-400">
                  <Check size={12} strokeWidth={3} /> Ready to parse
                </span>
              </div>

              {error && (
                <div
                  role="alert"
                  className="flex items-start justify-between gap-3 rounded-xl border border-destructive/20 bg-destructive/5 px-3.5 py-3 text-sm text-destructive"
                >
                  <span className="flex gap-2">
                    <AlertTriangle size={16} className="mt-0.5 shrink-0" />
                    {error}
                  </span>
                  <button onClick={chooseAnotherFile} className="shrink-0 text-xs font-semibold underline">
                    Choose another
                  </button>
                </div>
              )}

              <div className="flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between pt-2 border-t border-border">
                <button
                  onClick={chooseAnotherFile}
                  className="inline-flex items-center justify-center gap-1.5 rounded-lg px-2 py-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
                >
                  <X size={14} /> Choose another file
                </button>
                <button
                  onClick={generatePreview}
                  className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-primary hover:bg-primary/90 text-primary-foreground font-semibold text-sm shadow-md transition-all active:scale-[0.98]"
                >
                  <span>Preview & Normalize</span>
                  <ArrowRight size={16} />
                </button>
              </div>
            </motion.div>
          )}

          {state === "extracting" && (
            <motion.div
              key="extracting"
              initial={reduceMotion ? false : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="rounded-2xl border border-border bg-card/95 p-8 text-center shadow-xl shadow-black/5 backdrop-blur-sm sm:p-10"
              aria-live="polite"
            >
              <div className="relative mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl border border-primary/15 bg-primary/8 text-primary">
                <motion.div
                  animate={reduceMotion ? undefined : { rotate: 360 }}
                  transition={{ duration: 2.5, repeat: Infinity, ease: "linear" }}
                  className="absolute inset-[-5px] rounded-[1.15rem] border border-dashed border-primary/35"
                />
                <BrainCircuit size={26} />
              </div>
              <h2 className="text-xl font-semibold text-foreground">Analyzing Statement Structure</h2>
              <p className="mx-auto mt-2 max-w-sm text-sm leading-relaxed text-muted-foreground">
                Detecting columns, mapping debit/credit directions, and validating transaction dates.
              </p>
              <div className="mx-auto mt-7 flex max-w-xs items-center justify-between text-xs text-muted-foreground">
                <span className="flex items-center gap-2">
                  <FileText size={14} className="text-primary" /> Extracting Text
                </span>
                <motion.span
                  animate={reduceMotion ? undefined : { opacity: [0.45, 1, 0.45] }}
                  transition={{ duration: 1.4, repeat: Infinity }}
                  className="flex items-center gap-2"
                >
                  <LoaderCircle size={14} className="animate-spin text-primary" /> Normalizing
                </motion.span>
                <span className="flex items-center gap-2">
                  <Table size={14} className="text-muted-foreground" /> Preview
                </span>
              </div>
            </motion.div>
          )}

          {state === "preview" && previewData && (
            <motion.div
              key="preview"
              initial={{ opacity: 0, scale: 0.985 }}
              animate={{ opacity: 1, scale: 1 }}
              className="rounded-2xl border border-border bg-card/95 p-4 sm:p-6 shadow-xl backdrop-blur-sm space-y-5 sm:space-y-6"
            >
              {/* Header metrics */}
              <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border pb-4">
                <div>
                  <h2 className="text-xl font-bold text-foreground">Statement Import Preview</h2>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {previewData.file_name} · Format: {previewData.file_type.toUpperCase()}
                  </p>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium">
                    <CheckCircle2 size={13} /> {previewData.valid_rows_count} Valid Rows
                  </span>
                  {previewData.estimated_duplicate_count > 0 && (
                    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 font-medium">
                      <Info size={13} /> {previewData.estimated_duplicate_count} Duplicates Ignored
                    </span>
                  )}
                </div>
              </div>

              {/* Summary Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-3 rounded-xl bg-muted/40 border border-border">
                  <p className="text-[11px] text-muted-foreground flex items-center gap-1.5">
                    <Calendar size={13} /> Date Range
                  </p>
                  <p className="text-xs font-semibold text-foreground mt-1 truncate">
                    {previewData.date_range_start || "N/A"} to {previewData.date_range_end || "N/A"}
                  </p>
                </div>
                <div className="p-3 rounded-xl bg-muted/40 border border-border">
                  <p className="text-[11px] text-muted-foreground flex items-center gap-1.5">
                    <DollarSign size={13} className="text-emerald-400" /> Total Credits
                  </p>
                  <p className="text-sm font-bold text-emerald-400 font-mono mt-1">
                    ₹{previewData.total_credits.toLocaleString()}
                  </p>
                </div>
                <div className="p-3 rounded-xl bg-muted/40 border border-border">
                  <p className="text-[11px] text-muted-foreground flex items-center gap-1.5">
                    <DollarSign size={13} className="text-rose-400" /> Total Debits
                  </p>
                  <p className="text-sm font-bold text-rose-400 font-mono mt-1">
                    ₹{previewData.total_debits.toLocaleString()}
                  </p>
                </div>
                <div className="p-3 rounded-xl bg-muted/40 border border-border">
                  <p className="text-[11px] text-muted-foreground flex items-center gap-1.5">
                    <Columns size={13} /> Columns Mapped
                  </p>
                  <p className="text-sm font-semibold text-foreground mt-1">
                    {Object.keys(previewData.detected_mappings).length} Recognized
                  </p>
                </div>
              </div>

              {/* Sample Table Preview */}
              <div>
                <p className="text-xs font-semibold text-foreground mb-2 flex items-center gap-1.5">
                  <Table size={14} className="text-primary" /> Normalized Transaction Sample (First {previewData.sample_transactions.length} rows)
                </p>
                <div className="overflow-x-auto rounded-xl border border-border bg-background">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-muted/60 text-muted-foreground border-b border-border">
                      <tr>
                        <th className="p-2.5 font-medium">Date</th>
                        <th className="p-2.5 font-medium">Description</th>
                        <th className="p-2.5 font-medium">Direction</th>
                        <th className="p-2.5 font-medium text-right">Amount</th>
                        <th className="p-2.5 font-medium">Detected Class</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {previewData.sample_transactions.map((tx, idx) => (
                        <tr key={idx} className="hover:bg-muted/20 transition-colors">
                          <td className="p-2.5 font-mono text-muted-foreground">{tx.transaction_date}</td>
                          <td className="p-2.5 font-medium text-foreground truncate max-w-xs">{tx.description || tx.merchant_name || "Transaction"}</td>
                          <td className="p-2.5">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                                tx.direction === "Income"
                                  ? "bg-emerald-500/10 text-emerald-400"
                                  : "bg-rose-500/10 text-rose-400"
                              }`}
                            >
                              {tx.direction}
                            </span>
                          </td>
                          <td className="p-2.5 font-mono text-right font-semibold text-foreground">
                            ₹{tx.amount.toFixed(2)}
                          </td>
                          <td className="p-2.5 text-muted-foreground capitalize">{tx.transaction_class || "General"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {error && (
                <div
                  role="alert"
                  className="flex items-start justify-between gap-3 rounded-xl border border-destructive/20 bg-destructive/5 px-3.5 py-3 text-sm text-destructive"
                >
                  <span className="flex gap-2">
                    <AlertTriangle size={16} className="mt-0.5 shrink-0" />
                    {error}
                  </span>
                </div>
              )}

              {/* Action Buttons */}
              <div className="flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between pt-2 border-t border-border">
                <button
                  onClick={chooseAnotherFile}
                  className="inline-flex items-center justify-center gap-1.5 rounded-lg px-2 py-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
                >
                  <X size={14} /> Cancel & re-upload
                </button>
                <button
                  onClick={confirmImport}
                  className="inline-flex items-center justify-center gap-2 px-6 py-2.5 rounded-xl bg-primary hover:bg-primary/90 text-primary-foreground font-semibold text-sm shadow-md transition-all active:scale-[0.98]"
                >
                  <span>Confirm & Import Ledger</span>
                  <ArrowRight size={16} />
                </button>
              </div>
            </motion.div>
          )}

          {state === "importing" && (
            <motion.div
              key="importing"
              initial={reduceMotion ? false : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="rounded-2xl border border-border bg-card/95 p-8 text-center shadow-xl shadow-black/5 backdrop-blur-sm sm:p-10"
              aria-live="polite"
            >
              <div className="relative mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl border border-primary/15 bg-primary/8 text-primary">
                <motion.div
                  animate={reduceMotion ? undefined : { rotate: 360 }}
                  transition={{ duration: 2.5, repeat: Infinity, ease: "linear" }}
                  className="absolute inset-[-5px] rounded-[1.15rem] border border-dashed border-primary/35"
                />
                <BrainCircuit size={26} />
              </div>
              <h2 className="text-xl font-semibold text-foreground">Synchronizing Financial Intelligence</h2>
              <p className="mx-auto mt-2 max-w-sm text-sm leading-relaxed text-muted-foreground">
                Persisting validated records, reconciling recurring commitments, and calculating exposure.
              </p>
              <div className="mx-auto mt-7 flex max-w-xs items-center justify-between text-xs text-muted-foreground">
                <span className="flex items-center gap-2">
                  <Check size={14} className="text-emerald-400" /> Database Saved
                </span>
                <motion.span
                  animate={reduceMotion ? undefined : { opacity: [0.45, 1, 0.45] }}
                  transition={{ duration: 1.4, repeat: Infinity }}
                  className="flex items-center gap-2"
                >
                  <LoaderCircle size={14} className="animate-spin text-primary" /> Reconciling
                </motion.span>
                <span className="flex items-center gap-2">
                  <BrainCircuit size={14} className="text-ai" /> Dashboard
                </span>
              </div>
            </motion.div>
          )}

          {state === "success" && uploadResult && (
            <motion.div
              key="success"
              initial={{ opacity: 0, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
              className="rounded-2xl border border-emerald-500/25 bg-card/95 p-6 sm:p-8 text-center shadow-xl backdrop-blur-sm space-y-5"
            >
              <div className="w-14 h-14 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 mx-auto flex items-center justify-center">
                <Check size={28} strokeWidth={2.5} />
              </div>

              <div>
                <h2 className="text-xl font-bold text-foreground">Statement Ingested & Analyzed</h2>
                <p className="text-xs text-muted-foreground mt-1 max-w-md mx-auto">
                  FinSight merged your verified transactions and updated your financial exposure models.
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3 max-w-sm mx-auto text-left">
                <div className="p-3 rounded-xl bg-muted/50 border border-border">
                  <p className="text-[11px] text-muted-foreground">New Transactions</p>
                  <p className="text-lg font-bold text-emerald-400 font-mono mt-0.5">
                    +{uploadResult.accepted_count}
                  </p>
                </div>
                <div className="p-3 rounded-xl bg-muted/50 border border-border">
                  <p className="text-[11px] text-muted-foreground">Duplicates Skipped</p>
                  <p className="text-lg font-bold text-muted-foreground font-mono mt-0.5">
                    {uploadResult.duplicate_count}
                  </p>
                </div>
              </div>

              <div className="pt-2">
                <button
                  onClick={onComplete}
                  className="w-full sm:w-auto px-6 py-2.5 rounded-xl bg-primary hover:bg-primary/90 text-primary-foreground font-semibold text-sm shadow-md transition-all inline-flex items-center justify-center gap-2"
                >
                  <span>Go to Dashboard</span>
                  <ArrowRight size={15} />
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.section>
    </main>
  );
}
