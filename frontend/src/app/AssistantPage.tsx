import React, { Component, ErrorInfo, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  Check,
  ChevronRight,
  Copy,
  Edit2,
  FileText,
  Menu,
  MessageSquare,
  PanelLeftClose,
  PanelLeftOpen,
  Paperclip,
  Plus,
  RefreshCw,
  Search,
  Send,
  Sparkles,
  Terminal,
  Trash2,
  X,
} from "lucide-react";
import {
  ApiError,
  AuthenticatedUser,
  DocumentAnalyzeResponse,
  copilotApi,
  getStoredAccessToken,
} from "../api/client";

interface AssistantPageProps {
  initialQuestion?: string;
  user?: AuthenticatedUser;
  onUnauthorized?: () => void;
}

interface ChatMessage {
  id: string;
  sender: "user" | "assistant";
  text: string;
  timestamp: string;
  intent?: string;
  tools_invoked?: string[];
  latency_ms?: number;
  model?: string;
}

interface ConversationSession {
  id: string;
  title: string;
  preview: string;
  timestamp: string;
  dateGroup: "Today" | "Previous 7 days" | "Older";
}

const DEFAULT_SUGGESTIONS = [
  "What is my cash flow forecast?",
  "Explain my recurring commitments.",
  "How is my financial exposure calculated?",
  "Explain Big-O notation.",
  "Help me debug Python code.",
];

function formatTime(d = new Date()): string {
  try {
    return d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", hour12: true });
  } catch {
    return "";
  }
}

function formatTimestamp(isoStr?: string | null): string {
  if (!isoStr) return formatTime();
  try {
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) return formatTime();
    return d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", hour12: true });
  } catch {
    return formatTime();
  }
}

function getDateGroup(isoStr?: string | null): "Today" | "Previous 7 days" | "Older" {
  if (!isoStr) return "Today";
  try {
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) return "Today";
    const now = new Date();
    const diffHours = (now.getTime() - d.getTime()) / (1000 * 60 * 60);
    if (diffHours <= 24) return "Today";
    if (diffHours <= 24 * 7) return "Previous 7 days";
    return "Older";
  } catch {
    return "Today";
  }
}

// Glowing FinSight Orb
function FinSightOrb({ size = "md" }: { size?: "sm" | "md" | "lg" }) {
  const dim = size === "sm" ? "w-6 h-6" : size === "lg" ? "w-9 h-9" : "w-7 h-7";
  return (
    <div
      className={`${dim} rounded-full flex items-center justify-center shrink-0 relative overflow-hidden bg-gradient-to-tr from-[#312e81] via-[#4338ca] to-[#38bdf8] shadow-[0_0_12px_rgba(99,102,241,0.35)] border border-white/20`}
    >
      <div className="w-2 h-2 rounded-full bg-cyan-300 blur-[0.5px] animate-pulse" />
    </div>
  );
}

// React Error Boundary to prevent any blank-screen regressions
class AssistantErrorBoundary extends Component<
  { children: React.ReactNode; onReset?: () => void },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: React.ReactNode; onReset?: () => void }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Assistant Error Boundary caught an exception:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex h-full w-full items-center justify-center p-6 bg-[#090e1c] text-slate-200">
          <div className="max-w-md w-full p-6 rounded-2xl bg-[#0f172a] border border-rose-500/30 shadow-xl space-y-4 text-center">
            <div className="w-12 h-12 rounded-xl bg-rose-500/10 text-rose-400 mx-auto flex items-center justify-center">
              <AlertCircle size={24} />
            </div>
            <div className="space-y-1">
              <h3 className="text-sm font-bold text-white">Assistant Error</h3>
              <p className="text-xs text-slate-400">
                A rendering issue occurred. Click below to reload your workspace.
              </p>
            </div>
            <button
              onClick={() => {
                this.setState({ hasError: false, error: null });
                this.props.onReset?.();
              }}
              className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-md transition-all"
            >
              Reload Assistant
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

// Resilient Markdown and Code Renderer
function MarkdownRenderer({ content }: { content?: string | null }) {
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  const safeContent = useMemo(() => {
    if (typeof content === "string") return content;
    if (content === null || content === undefined) return "";
    return String(content);
  }, [content]);

  const handleCopyCode = (code: string, index: number) => {
    navigator.clipboard.writeText(code);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  const parts = useMemo(() => {
    if (!safeContent) return [];
    const regex = /```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g;
    const elements: { type: "code" | "text"; content: string; lang?: string }[] = [];
    let lastIndex = 0;
    let match: RegExpExecArray | null;

    try {
      while ((match = regex.exec(safeContent)) !== null) {
        if (match.index > lastIndex) {
          elements.push({
            type: "text",
            content: safeContent.substring(lastIndex, match.index),
          });
        }
        elements.push({
          type: "code",
          lang: match[1] || "text",
          content: match[2].trim(),
        });
        lastIndex = regex.lastIndex;
      }

      if (lastIndex < safeContent.length) {
        elements.push({
          type: "text",
          content: safeContent.substring(lastIndex),
        });
      }
    } catch {
      return [{ type: "text" as const, content: safeContent }];
    }

    return elements;
  }, [safeContent]);

  const renderFormattedText = (textBlock: string, blockKey: number) => {
    if (!textBlock) return null;
    const lines = textBlock.split("\n");
    return (
      <div key={blockKey} className="space-y-1.5">
        {lines.map((line, lineIdx) => {
          const trimmed = line.trim();
          if (!trimmed) {
            return <div key={lineIdx} className="h-1" />;
          }

          if (trimmed.startsWith("### ")) {
            return (
              <h4 key={lineIdx} className="text-xs sm:text-sm font-bold text-indigo-300 mt-2 mb-1">
                {renderInlineStyles(trimmed.slice(4))}
              </h4>
            );
          }
          if (trimmed.startsWith("## ")) {
            return (
              <h3 key={lineIdx} className="text-sm font-bold text-white mt-2.5 mb-1">
                {renderInlineStyles(trimmed.slice(3))}
              </h3>
            );
          }
          if (trimmed.startsWith("# ")) {
            return (
              <h2 key={lineIdx} className="text-base font-extrabold text-white mt-2.5 mb-1">
                {renderInlineStyles(trimmed.slice(2))}
              </h2>
            );
          }

          if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
            return (
              <div key={lineIdx} className="flex items-start gap-2 ml-1 text-slate-200">
                <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 mt-1.5 shrink-0" />
                <span className="flex-1 break-words leading-relaxed text-xs sm:text-sm">
                  {renderInlineStyles(trimmed.slice(2))}
                </span>
              </div>
            );
          }

          const numMatch = trimmed.match(/^(\d+)\.\s+(.*)/);
          if (numMatch) {
            return (
              <div key={lineIdx} className="flex items-start gap-2 ml-1 text-slate-200">
                <span className="text-indigo-400 font-mono text-xs font-semibold shrink-0">
                  {numMatch[1]}.
                </span>
                <span className="flex-1 break-words leading-relaxed text-xs sm:text-sm">
                  {renderInlineStyles(numMatch[2])}
                </span>
              </div>
            );
          }

          if (trimmed.startsWith("> ")) {
            return (
              <blockquote
                key={lineIdx}
                className="pl-3 border-l-2 border-indigo-500/60 text-slate-300 italic text-xs my-1"
              >
                {renderInlineStyles(trimmed.slice(2))}
              </blockquote>
            );
          }

          return (
            <p key={lineIdx} className="break-words leading-relaxed text-xs sm:text-sm">
              {renderInlineStyles(line)}
            </p>
          );
        })}
      </div>
    );
  };

  const renderInlineStyles = (str: string) => {
    if (!str) return null;
    const codeParts = str.split(/(`[^`]+`)/g);
    return codeParts.map((part, pIdx) => {
      if (part.startsWith("`") && part.endsWith("`") && part.length >= 2) {
        return (
          <code
            key={pIdx}
            className="px-1.5 py-0.5 mx-0.5 rounded bg-indigo-950/70 border border-indigo-500/30 text-indigo-200 font-mono text-[11px]"
          >
            {part.slice(1, -1)}
          </code>
        );
      }

      const boldParts = part.split(/(\*\*[^*]+\*\*)/g);
      return boldParts.map((bPart, bIdx) => {
        if (bPart.startsWith("**") && bPart.endsWith("**") && bPart.length >= 4) {
          return (
            <strong key={`${pIdx}-${bIdx}`} className="font-semibold text-white">
              {bPart.slice(2, -2)}
            </strong>
          );
        }
        return bPart;
      });
    });
  };

  if (!safeContent) return null;

  return (
    <div className="space-y-2">
      {parts.map((p, idx) => {
        if (p.type === "code") {
          return (
            <div
              key={idx}
              className="my-2.5 rounded-xl border border-white/10 bg-[#080d1a] overflow-hidden shadow-md"
            >
              <div className="flex items-center justify-between px-3 py-1.5 bg-white/[0.04] border-b border-white/[0.06] text-[11px] text-slate-400 font-mono">
                <span className="flex items-center gap-1.5 text-indigo-300">
                  <Terminal size={12} />
                  <span>{p.lang || "code"}</span>
                </span>
                <button
                  onClick={() => handleCopyCode(p.content, idx)}
                  className="flex items-center gap-1 hover:text-white px-2 py-0.5 rounded hover:bg-white/[0.08] transition-colors"
                >
                  {copiedIndex === idx ? (
                    <>
                      <Check size={11} className="text-emerald-400" />
                      <span className="text-emerald-400">Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy size={11} />
                      <span>Copy</span>
                    </>
                  )}
                </button>
              </div>
              <pre className="p-3 text-xs text-indigo-100 font-mono overflow-x-auto leading-relaxed">
                <code>{p.content}</code>
              </pre>
            </div>
          );
        }
        return renderFormattedText(p.content, idx);
      })}
    </div>
  );
}

export function AssistantPage({ initialQuestion, user, onUnauthorized }: AssistantPageProps) {
  return (
    <AssistantErrorBoundary onReset={() => window.location.reload()}>
      <AssistantWorkspace
        initialQuestion={initialQuestion}
        user={user}
        onUnauthorized={onUnauthorized}
      />
    </AssistantErrorBoundary>
  );
}

function AssistantWorkspace({ initialQuestion, user, onUnauthorized }: AssistantPageProps) {
  // Sidebar state
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [conversations, setConversations] = useState<ConversationSession[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [loadingConversations, setLoadingConversations] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [searchFilter, setSearchFilter] = useState("");
  const [showSearch, setShowSearch] = useState(false);
  const [globalError, setGlobalError] = useState<string | null>(null);

  // Rename & Delete state
  const [editingConvId, setEditingConvId] = useState<string | null>(null);
  const [editTitleInput, setEditTitleInput] = useState("");
  const [deletingConv, setDeletingConv] = useState<ConversationSession | null>(null);

  // Chat message state
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState(initialQuestion ?? "");
  const [isTyping, setIsTyping] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Document attachment state
  const [attachedDoc, setAttachedDoc] = useState<DocumentAnalyzeResponse | null>(null);
  const [isUploadingDoc, setIsUploadingDoc] = useState(false);
  const [docError, setDocError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Active mode indicator state
  const [activeMode, setActiveMode] = useState<"financial" | "rag" | "general">("general");

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const hasAutoAsked = useRef(false);
  const activeConvIdRef = useRef<string | null>(null);
  const requestIdRef = useRef(0);

  activeConvIdRef.current = activeConvId;

  const userInitials = user?.email ? user.email.slice(0, 2).toUpperCase() : "ME";

  // Load conversation list from backend (does NOT auto-create any conversations)
  const fetchConversationsList = async (autoSelect = false) => {
    const token = getStoredAccessToken();
    if (!token) {
      setLoadingConversations(false);
      return;
    }

    try {
      const list = await copilotApi.listConversations(token);
      if (Array.isArray(list)) {
        const mapped: ConversationSession[] = list.map((item) => ({
          id: item.id,
          title: item.title || "New Conversation",
          preview: item.preview || "No messages yet",
          timestamp: formatTimestamp(item.updated_at),
          dateGroup: getDateGroup(item.updated_at),
        }));
        setConversations(mapped);

        // Auto-select most recent if available and none selected
        if (autoSelect && mapped.length > 0 && !activeConvIdRef.current) {
          selectConversation(mapped[0].id);
        }
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        onUnauthorized?.();
      }
    } finally {
      setLoadingConversations(false);
    }
  };

  useEffect(() => {
    fetchConversationsList(true);
  }, []);

  // Select conversation & load messages with race-condition prevention
  const selectConversation = async (convId: string) => {
    setActiveConvId(convId);
    activeConvIdRef.current = convId;
    const currentReqId = ++requestIdRef.current;
    setLoadingMessages(true);
    setGlobalError(null);

    const token = getStoredAccessToken();
    if (!token) {
      setLoadingMessages(false);
      return;
    }

    try {
      const detail = await copilotApi.getConversation(convId, token);
      if (requestIdRef.current !== currentReqId || activeConvIdRef.current !== convId) {
        return;
      }

      if (detail && Array.isArray(detail.messages)) {
        const loadedMessages: ChatMessage[] = detail.messages.map((m) => {
          const msgSender = (m.sender || m.role || "user") as "user" | "assistant";
          const msgText = m.text || m.content || "";
          return {
            id: m.id,
            sender: msgSender,
            text: msgText,
            timestamp: formatTimestamp(m.created_at),
            intent: m.intent ?? undefined,
          };
        });
        setMessages(loadedMessages);

        // Determine active mode from latest assistant message
        const lastAsst = [...loadedMessages].reverse().find((m) => m.sender === "assistant");
        if (
          lastAsst?.intent?.toLowerCase().includes("cash_flow") ||
          lastAsst?.intent?.toLowerCase().includes("commitment") ||
          lastAsst?.intent?.toLowerCase().includes("shortfall") ||
          lastAsst?.intent?.toLowerCase().includes("exposure")
        ) {
          setActiveMode("financial");
        } else if (lastAsst?.intent?.toLowerCase().includes("rag")) {
          setActiveMode("rag");
        } else {
          setActiveMode("general");
        }
      } else {
        setMessages([]);
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        onUnauthorized?.();
        return;
      }
      setGlobalError("Unable to load conversation messages. You can still send a message.");
    } finally {
      if (requestIdRef.current === currentReqId) {
        setLoadingMessages(false);
      }
    }
  };

  // Scroll to bottom on message updates
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  // Handle auto-ask from initialQuestion
  useEffect(() => {
    if (initialQuestion && !hasAutoAsked.current) {
      hasAutoAsked.current = true;
      handleSendMessage(initialQuestion);
    }
  }, [initialQuestion]);

  // Send message
  async function handleSendMessage(textToSend?: string) {
    const queryText = (textToSend ?? inputValue).trim();
    if (!queryText || isTyping) return;

    const token = getStoredAccessToken();
    if (!token) {
      onUnauthorized?.();
      return;
    }

    setGlobalError(null);
    const displayText = attachedDoc
      ? `${queryText}\n\n[Attached: ${attachedDoc.filename}]`
      : queryText;

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: "user",
      text: displayText,
      timestamp: formatTime(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputValue("");
    const docContext = attachedDoc?.document_text;
    setAttachedDoc(null);
    setIsTyping(true);

    try {
      const res = await copilotApi.chat(
        {
          message: queryText,
          conversation_id: activeConvId,
          document_context: docContext,
        },
        token
      );

      const aiText = res.text || res.response || "No response received.";
      const aiMsg: ChatMessage = {
        id: res.message_id || `ai-${Date.now()}`,
        sender: "assistant",
        text: aiText,
        timestamp: formatTime(),
        intent: res.intent,
        tools_invoked: res.tools_invoked,
        latency_ms: res.latency_ms,
        model: res.model,
      };

      setMessages((prev) => [...prev, aiMsg]);
      setActiveConvId(res.conversation_id);
      activeConvIdRef.current = res.conversation_id;

      if (res.tools_invoked && res.tools_invoked.length > 0) {
        setActiveMode("financial");
      } else if (res.intent?.toLowerCase().includes("rag")) {
        setActiveMode("rag");
      } else {
        setActiveMode("general");
      }

      fetchConversationsList(false);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        onUnauthorized?.();
        return;
      }
      const errMsg =
        err instanceof ApiError
          ? err.message
          : "Unable to process your request at this moment. Please try again.";

      const aiErrorMsg: ChatMessage = {
        id: `ai-err-${Date.now()}`,
        sender: "assistant",
        text: `**Notice**: ${errMsg}`,
        timestamp: formatTime(),
      };
      setMessages((prev) => [...prev, aiErrorMsg]);
    } finally {
      setIsTyping(false);
    }
  }

  // Handle New Chat (does NOT create a database conversation until user sends a message)
  const handleNewChat = () => {
    setActiveConvId(null);
    activeConvIdRef.current = null;
    setMessages([]);
    setInputValue("");
    setAttachedDoc(null);
    setGlobalError(null);
    setActiveMode("general");
    textareaRef.current?.focus();
  };

  // Safe delete with confirmation
  const handleConfirmDelete = async () => {
    if (!deletingConv) return;
    const token = getStoredAccessToken();
    if (!token) return;

    try {
      await copilotApi.deleteConversation(deletingConv.id, token);
      setConversations((prev) => prev.filter((c) => c.id !== deletingConv.id));
      if (activeConvId === deletingConv.id) {
        handleNewChat();
      }
    } catch (err) {
      console.error("Failed to delete conversation:", err);
    } finally {
      setDeletingConv(null);
    }
  };

  // Safe rename
  const handleStartRename = (e: React.MouseEvent, c: ConversationSession) => {
    e.stopPropagation();
    setEditingConvId(c.id);
    setEditTitleInput(c.title);
  };

  const handleSaveRename = async (e: React.MouseEvent | React.KeyboardEvent, id: string) => {
    e.stopPropagation();
    const newTitle = editTitleInput.trim();
    if (!newTitle) {
      setEditingConvId(null);
      return;
    }
    const token = getStoredAccessToken();
    if (!token) return;

    try {
      await copilotApi.renameConversation(id, newTitle, token);
      setConversations((prev) =>
        prev.map((c) => (c.id === id ? { ...c, title: newTitle } : c))
      );
    } catch (err) {
      console.error("Failed to rename conversation:", err);
    } finally {
      setEditingConvId(null);
    }
  };

  // Copy answer to clipboard
  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  // Textarea key handling
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  // Document attachment handler
  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const token = getStoredAccessToken();
    if (!token) {
      onUnauthorized?.();
      return;
    }

    setDocError(null);
    setIsUploadingDoc(true);
    try {
      const res = await copilotApi.analyzeDocument(file, token);
      setAttachedDoc(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to extract text from document";
      setDocError(msg);
    } finally {
      setIsUploadingDoc(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  // Filtered conversations
  const filteredConversations = useMemo(() => {
    if (!searchFilter.trim()) return conversations;
    const q = searchFilter.toLowerCase();
    return conversations.filter(
      (c) => c.title.toLowerCase().includes(q) || c.preview.toLowerCase().includes(q)
    );
  }, [conversations, searchFilter]);

  return (
    <div className="flex h-[calc(100vh-56px)] bg-[#090e1c] text-slate-100 overflow-hidden w-full max-w-full">
      {/* Hidden file input */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileSelect}
        accept=".txt,.md,.csv,.json,.pdf,.doc,.docx"
        className="hidden"
      />

      {/* Confirmation Dialog for Deletion */}
      {deletingConv && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-[#0f172a] border border-white/10 rounded-2xl p-5 max-w-sm w-full space-y-4 shadow-2xl">
            <h3 className="text-sm font-bold text-white">Delete Conversation?</h3>
            <p className="text-xs text-slate-300 leading-relaxed">
              Are you sure you want to delete <span className="text-white font-medium">"{deletingConv.title}"</span>? This will permanently remove its message history.
            </p>
            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                onClick={() => setDeletingConv(null)}
                className="px-3 py-1.5 rounded-lg text-xs font-medium text-slate-300 hover:text-white hover:bg-white/[0.06] transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmDelete}
                className="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-rose-600 hover:bg-rose-500 text-white transition-colors shadow-sm"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────
          SECTION 1: COMPACT LEFT CONVERSATION SIDEBAR
      ───────────────────────────────────────────────────────────── */}
      <aside
        className={`${
          sidebarOpen ? "w-64 sm:w-72" : "w-0 hidden"
        } border-r border-white/[0.08] bg-[#090e1c] flex flex-col shrink-0 transition-all duration-200 z-20`}
      >
        <div className="p-3.5 border-b border-white/[0.06] space-y-2.5">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-bold text-white flex items-center gap-1.5 uppercase tracking-wider">
              <MessageSquare size={13} className="text-indigo-400" />
              <span>Chats</span>
            </h2>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setShowSearch((s) => !s)}
                className={`p-1 rounded-md transition-colors ${
                  showSearch ? "bg-indigo-600/30 text-indigo-300" : "text-slate-400 hover:text-white"
                }`}
                title="Search chats"
              >
                <Search size={13} />
              </button>
              <button
                onClick={() => setSidebarOpen(false)}
                className="p-1 rounded-md text-slate-400 hover:text-white sm:hidden"
                title="Close sidebar"
              >
                <PanelLeftClose size={14} />
              </button>
            </div>
          </div>

          {showSearch && (
            <div className="relative">
              <input
                type="text"
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
                placeholder="Search..."
                className="w-full bg-[#0f172a] border border-white/10 rounded-lg px-2.5 py-1 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500/50"
              />
              {searchFilter && (
                <button
                  onClick={() => setSearchFilter("")}
                  className="absolute right-2 top-1.5 text-slate-400 hover:text-white"
                >
                  <X size={11} />
                </button>
              )}
            </div>
          )}

          <button
            onClick={handleNewChat}
            className="w-full py-2 px-3 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs flex items-center justify-center gap-1.5 transition-colors shadow-sm"
          >
            <Plus size={13} />
            <span>New Chat</span>
          </button>
        </div>

        {/* Scrollable Conversation List */}
        <div className="flex-1 overflow-y-auto p-2.5 space-y-3 scrollbar-none">
          {conversations.length === 0 && !loadingConversations ? (
            <div className="p-3 text-center text-xs text-slate-500">
              No conversations yet.
            </div>
          ) : (
            (["Today", "Previous 7 days", "Older"] as const).map((groupName) => {
              const groupItems = filteredConversations.filter((c) => c.dateGroup === groupName);
              if (groupItems.length === 0) return null;
              return (
                <div key={groupName} className="space-y-1">
                  <span className="text-[10px] font-semibold text-slate-500 px-2 uppercase tracking-wider block">
                    {groupName}
                  </span>
                  {groupItems.map((c) => {
                    const active = activeConvId === c.id;
                    const isEditing = editingConvId === c.id;
                    return (
                      <div
                        key={c.id}
                        onClick={() => !isEditing && selectConversation(c.id)}
                        role="button"
                        tabIndex={0}
                        className={`w-full text-left px-2.5 py-2 rounded-lg transition-colors flex items-center justify-between group cursor-pointer ${
                          active
                            ? "bg-indigo-950/80 text-white border border-indigo-500/30"
                            : "hover:bg-white/[0.04] text-slate-300"
                        }`}
                      >
                        {isEditing ? (
                          <div className="flex items-center gap-1 w-full" onClick={(e) => e.stopPropagation()}>
                            <input
                              type="text"
                              value={editTitleInput}
                              onChange={(e) => setEditTitleInput(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === "Enter") handleSaveRename(e, c.id);
                                if (e.key === "Escape") setEditingConvId(null);
                              }}
                              autoFocus
                              className="w-full bg-[#0f172a] border border-indigo-500/50 rounded px-1.5 py-0.5 text-xs text-white focus:outline-none"
                            />
                            <button
                              onClick={(e) => handleSaveRename(e, c.id)}
                              className="p-1 rounded text-emerald-400 hover:bg-white/10"
                            >
                              <Check size={11} />
                            </button>
                            <button
                              onClick={() => setEditingConvId(null)}
                              className="p-1 rounded text-slate-400 hover:bg-white/10"
                            >
                              <X size={11} />
                            </button>
                          </div>
                        ) : (
                          <>
                            <div className="min-w-0 flex-1 pr-2">
                              <p className="text-xs font-medium truncate">{c.title}</p>
                              <p className="text-[10px] text-slate-500 truncate mt-0.5">{c.preview}</p>
                            </div>
                            <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                              <button
                                onClick={(e) => handleStartRename(e, c)}
                                className="p-1 rounded hover:bg-white/[0.08] text-slate-400 hover:text-white"
                                title="Rename"
                              >
                                <Edit2 size={11} />
                              </button>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setDeletingConv(c);
                                }}
                                className="p-1 rounded hover:bg-rose-500/20 text-slate-400 hover:text-rose-300"
                                title="Delete"
                              >
                                <Trash2 size={11} />
                              </button>
                            </div>
                          </>
                        )}
                      </div>
                    );
                  })}
                </div>
              );
            })
          )}
        </div>
      </aside>

      {/* ─────────────────────────────────────────────────────────────
          SECTION 2: PRIMARY CENTER CHAT AREA (EXPANDED TO FULL WIDTH)
      ───────────────────────────────────────────────────────────── */}
      <main className="flex-1 flex flex-col min-w-0 h-full bg-[#0b1120] relative overflow-hidden">
        {/* Compact Header */}
        <header className="h-14 px-4 sm:px-6 border-b border-white/[0.08] flex items-center justify-between bg-[#090e1c] shrink-0 z-10">
          <div className="flex items-center gap-3 min-w-0">
            <button
              onClick={() => setSidebarOpen((s) => !s)}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/[0.06] transition-colors"
              title={sidebarOpen ? "Hide sidebar" : "Show sidebar"}
            >
              {sidebarOpen ? <PanelLeftClose size={16} /> : <PanelLeftOpen size={16} />}
            </button>
            <FinSightOrb size="sm" />
            <div className="min-w-0">
              <h1 className="text-xs sm:text-sm font-bold text-white truncate">
                FinSight AI Assistant
              </h1>
              <p className="text-[11px] text-slate-400 hidden sm:block truncate">
                Your AI assistant for finance, coding and problem-solving.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5 shrink-0">
            {/* Compact Mode Badge */}
            <span
              className={`px-2 py-0.5 rounded text-[10px] font-medium border ${
                activeMode === "financial"
                  ? "bg-emerald-950/50 text-emerald-300 border-emerald-500/30"
                  : activeMode === "rag"
                  ? "bg-cyan-950/50 text-cyan-300 border-cyan-500/30"
                  : "bg-indigo-950/50 text-indigo-300 border-indigo-500/30"
              }`}
            >
              {activeMode === "financial"
                ? "Financial Intelligence"
                : activeMode === "rag"
                ? "FinSight Knowledge"
                : "General AI"}
            </span>

            {/* Live Connection Pill */}
            <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-[#0f172a] border border-white/10 text-[10px] text-slate-300">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span>Connected</span>
            </div>
          </div>
        </header>

        {/* Global error banner if present */}
        {globalError && (
          <div className="px-4 py-2 bg-rose-950/50 border-b border-rose-500/20 text-xs text-rose-300 flex items-center justify-between">
            <span>{globalError}</span>
            <button onClick={() => setGlobalError(null)} className="p-0.5 hover:text-white">
              <X size={12} />
            </button>
          </div>
        )}

        {/* Chat Message Stream — comfortable centered max width */}
        <div className="flex-1 overflow-y-auto overflow-x-hidden p-4 sm:p-6 space-y-5 scrollbar-none w-full">
          <div className="max-w-3xl sm:max-w-4xl mx-auto w-full space-y-5">
            {loadingMessages ? (
              <div className="flex h-40 items-center justify-center">
                <RefreshCw size={18} className="animate-spin text-indigo-400" />
              </div>
            ) : messages.length === 0 ? (
              /* Compact Clean Welcome State */
              <div className="py-12 text-center space-y-5 max-w-lg mx-auto">
                <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 mx-auto flex items-center justify-center shadow-[0_0_15px_rgba(99,102,241,0.2)]">
                  <Sparkles size={22} />
                </div>
                <div className="space-y-1">
                  <h2 className="text-base sm:text-lg font-bold text-white">
                    Hi! I'm FinSight AI.
                  </h2>
                  <p className="text-xs text-slate-400 leading-relaxed">
                    Ask me about your finances, coding, computer science, or FinSight.
                  </p>
                </div>

                {/* 5 Clean Suggested Prompts */}
                <div className="pt-2 space-y-2 text-left">
                  {DEFAULT_SUGGESTIONS.map((q) => (
                    <button
                      key={q}
                      onClick={() => handleSendMessage(q)}
                      className="w-full p-2.5 rounded-xl bg-[#0f172a] hover:bg-[#1e293b] border border-white/[0.08] hover:border-indigo-500/40 text-xs text-slate-300 hover:text-white transition-all flex items-center justify-between group shadow-xs"
                    >
                      <span>{q}</span>
                      <ChevronRight size={13} className="text-slate-500 group-hover:text-indigo-400 shrink-0" />
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex flex-col w-full ${
                    msg.sender === "user" ? "items-end" : "items-start"
                  }`}
                >
                  <span className="text-[10px] text-slate-500 font-mono mb-1 px-1">
                    {msg.timestamp}
                  </span>

                  {msg.sender === "user" ? (
                    <div className="flex items-end gap-2.5 max-w-full sm:max-w-xl">
                      <div className="p-3.5 sm:p-4 rounded-2xl rounded-br-sm bg-indigo-600 text-white text-xs sm:text-sm font-medium shadow-md leading-relaxed break-words [overflow-wrap:anywhere]">
                        {msg.text}
                      </div>
                      <div className="w-7 h-7 rounded-full bg-indigo-700 text-white font-mono text-[10px] font-bold flex items-center justify-center shrink-0">
                        {userInitials}
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-start gap-3 max-w-full w-full min-w-0">
                      <FinSightOrb size="sm" />
                      <div className="flex-1 min-w-0 rounded-2xl rounded-tl-sm bg-[#0f172a] border border-white/[0.08] shadow-md overflow-hidden">
                        <div className="p-4 sm:p-5 text-xs sm:text-sm text-slate-200 leading-relaxed break-words [overflow-wrap:anywhere]">
                          <MarkdownRenderer content={msg.text} />
                        </div>
                        <div className="px-4 py-2 bg-[#090e1c] border-t border-white/[0.06] flex items-center justify-between text-[11px] text-slate-400">
                          <span className="truncate">
                            {msg.tools_invoked && msg.tools_invoked.length > 0
                              ? `Grounded: ${msg.tools_invoked.join(", ")}`
                              : "FinSight AI"}
                          </span>
                          <button
                            onClick={() => handleCopy(msg.id, msg.text)}
                            className="p-1 rounded hover:bg-white/[0.08] hover:text-white transition-colors"
                            title="Copy response"
                          >
                            {copiedId === msg.id ? (
                              <Check size={12} className="text-emerald-400" />
                            ) : (
                              <Copy size={12} />
                            )}
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ))
            )}

            {/* Typing Indicator */}
            {isTyping && (
              <div className="flex items-start gap-3">
                <FinSightOrb size="sm" />
                <div className="px-4 py-2.5 rounded-2xl rounded-tl-sm bg-[#0f172a] border border-white/[0.08] flex items-center gap-2.5 text-xs text-slate-400">
                  <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce" />
                  <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-bounce [animation-delay:0.2s]" />
                  <span className="w-1.5 h-1.5 rounded-full bg-purple-400 animate-bounce [animation-delay:0.4s]" />
                  <span className="text-[11px] ml-1">FinSight is thinking...</span>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* ─────────────────────────────────────────────────────────────
            FIXED BOTTOM INPUT AREA
        ───────────────────────────────────────────────────────────── */}
        <div className="p-2.5 sm:p-4 border-t border-white/[0.08] bg-[#090e1c] shrink-0 w-full">
          <div className="max-w-3xl sm:max-w-4xl mx-auto w-full space-y-2">
            {/* Document error alert if any */}
            {docError && (
              <div className="text-[11px] text-rose-400 flex items-center justify-between px-1">
                <span>{docError}</span>
                <button onClick={() => setDocError(null)}>
                  <X size={11} />
                </button>
              </div>
            )}

            {/* Attached Document Pill */}
            {attachedDoc && (
              <div className="flex items-center justify-between px-3 py-1.5 rounded-xl bg-indigo-950/60 border border-indigo-500/30 text-xs text-indigo-200">
                <div className="flex items-center gap-2 truncate">
                  <FileText size={13} className="text-indigo-400 shrink-0" />
                  <span className="truncate">{attachedDoc.filename}</span>
                </div>
                <button
                  onClick={() => setAttachedDoc(null)}
                  className="p-0.5 hover:text-white"
                  title="Remove"
                >
                  <X size={12} />
                </button>
              </div>
            )}

            {/* Input Composer Box */}
            <div className="relative rounded-2xl bg-[#0f172a] border border-white/10 focus-within:border-indigo-500/50 p-2 flex items-center gap-2 shadow-inner w-full min-w-0">
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={isUploadingDoc}
                className="w-8 h-8 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] text-slate-400 hover:text-white flex items-center justify-center transition-colors shrink-0"
                title="Attach document (.txt, .md, .csv, .json, .pdf)"
              >
                <Paperclip size={15} />
              </button>

              <textarea
                ref={textareaRef}
                rows={1}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask anything (finances, coding, algorithms)..."
                className="flex-1 min-w-0 bg-transparent text-xs sm:text-sm text-white placeholder-slate-500 focus:outline-none resize-none py-1.5 px-1 max-h-28"
              />

              <button
                onClick={() => handleSendMessage()}
                disabled={isTyping || (!inputValue.trim() && !attachedDoc)}
                className="w-8 h-8 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-30 text-white flex items-center justify-center transition-all shrink-0 active:scale-95"
              >
                <Send size={13} className="ml-0.5" />
              </button>
            </div>

            <div className="flex items-center justify-between text-[10px] text-slate-500 px-1">
              <span>Enter to send • Shift + Enter for new line</span>
              {isUploadingDoc && <span className="text-cyan-400">Parsing document...</span>}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
