import { useState, useRef, useEffect, useCallback } from "react";
import { MessageSquare, Paperclip } from "lucide-react";
import { ConfidenceBar } from "@/components/ui/ConfidenceBar";
import { StreamingCursor } from "@/components/chat/StreamingCursor";
import { AnswerCard } from "@/components/chat/AnswerCard";
import { UploadProgressCard } from "@/components/chat/UploadProgressCard";
import { SUGGESTED_PROMPTS } from "@/lib/mockData";
import { fetchWithAuth } from "@/lib/api";
import type { UseSSEChatReturn, Citation } from "@/hooks/useSSEChat";

interface Props {
  chat: UseSSEChatReturn;
  forceLogout: () => void;
}

export function AskAssistantScreen({ chat, forceLogout }: Props) {
  const { messages, isStreaming, submit, retry } = chat;

  const [input, setInput] = useState("");
  const [sources, setSources] = useState<string[]>([]);
  const [sourcesLoading, setSourcesLoading] = useState(true);
  const [sourcesError, setSourcesError] = useState<string | null>(null);
  const [activeFilter, setActiveFilter] = useState("All Sources");
  const [topicFilter, setTopicFilter] = useState("All Topics");
  const [activeEvidence, setActiveEvidence] = useState<Citation[]>([]);
  const [isEvidenceOpen, setIsEvidenceOpen] = useState(false);

  // Upload state
  const [uploadState, setUploadState] = useState<{
    docId: string;
    fileName: string;
    docStatus: string;
    currentTask: string;
    jobStatus: string;
  } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [isAutoScroll, setIsAutoScroll] = useState(true);
  const prevLengthRef = useRef(messages.length);

  const allTopics = ["All Topics", "Data Collection", "Third-Party Sharing", "Data Retention", "User Rights", "Cookies"];

  const scrollToBottom = (smooth: boolean) => {
    if (scrollContainerRef.current) {
      const { scrollHeight, clientHeight } = scrollContainerRef.current;
      scrollContainerRef.current.scrollTo({
        top: scrollHeight - clientHeight,
        behavior: smooth ? "smooth" : "auto",
      });
    }
  };

  useEffect(() => {
    const isNewMessage = messages.length > prevLengthRef.current;
    prevLengthRef.current = messages.length;

    if (isNewMessage || uploadState) {
      setIsAutoScroll(true);
      scrollToBottom(true);
    } else if (isAutoScroll) {
      scrollToBottom(false);
    }

    const last = messages[messages.length - 1];
    if (last?.role === "assistant" && last.citations && last.citations.length > 0) {
      setActiveEvidence(last.citations);
    }
  }, [messages, uploadState, isAutoScroll]);

  const handleScroll = () => {
    if (scrollContainerRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = scrollContainerRef.current;
      const isBottom = scrollHeight - scrollTop - clientHeight < 50;
      setIsAutoScroll(isBottom);
    }
  };

  const fetchSources = useCallback(() => {
    fetchWithAuth("/api/sources", { method: "GET" }, forceLogout)
      .then((r) => {
        if (!r.ok) throw new Error(`Sources fetch failed: ${r.status}`);
        return r.json();
      })
      .then((data: { sources: string[] }) => {
        setSources(data.sources ?? []);
        setSourcesLoading(false);
      })
      .catch(() => {
        setSourcesError("Could not load sources. Try refreshing the page.");
        setSourcesLoading(false);
      });
  }, [forceLogout]);

  useEffect(() => {
    fetchSources();
  }, [fetchSources]);

  // Polling effect for upload
  useEffect(() => {
    if (!uploadState?.docId) return;
    if (uploadState.docStatus === "ready" || uploadState.docStatus === "failed") return;

    const interval = setInterval(async () => {
      try {
        const res = await fetchWithAuth(`/api/documents/${uploadState.docId}/job_status`, { method: "GET" }, forceLogout);
        if (res.ok) {
          const data = await res.json();
          setUploadState(prev => prev ? {
            ...prev,
            docStatus: data.doc_status,
            currentTask: data.current_task || prev.currentTask,
            jobStatus: data.job_status || prev.jobStatus
          } : null);

          if (data.doc_status === "ready") {
            fetchSources();
          }
        }
      } catch (e) {
        // ignore errors during polling
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [uploadState?.docId, uploadState?.docStatus, forceLogout, fetchSources]);

  const handleUploadFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    setUploadState({
      docId: "",
      fileName: file.name,
      docStatus: "processing",
      currentTask: "upload",
      jobStatus: "running"
    });
    
    const formData = new FormData();
    formData.append("file", file);
    
    try {
      const res = await fetchWithAuth("/api/documents/", {
        method: "POST",
        body: formData,
      }, forceLogout);
      
      if (res.ok) {
        const data = await res.json();
        setUploadState(prev => prev ? { ...prev, docId: data.document_id, jobStatus: "queued" } : null);
        fetchSources();
      } else {
        setUploadState(prev => prev ? { ...prev, docStatus: "failed", jobStatus: "failed" } : null);
      }
    } catch (err) {
      setUploadState(prev => prev ? { ...prev, docStatus: "failed", jobStatus: "failed" } : null);
    }
    
    // reset input
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleOpenEvidence = (c: Citation) => {
    setActiveEvidence([c]);
    setIsEvidenceOpen(true);
  };

  const handleRetry = () => {
    retry(forceLogout, activeFilter === "All Sources" ? null : activeFilter);
  };

  const handleSend = () => {
    if (!input.trim() || isStreaming) return;
    submit(input, forceLogout, activeFilter === "All Sources" ? null : activeFilter);
    setInput("");
    setIsEvidenceOpen(false);
  };

  return (
    <div className="flex h-full overflow-hidden">
      {/* Left filter sidebar */}
      <div className="w-[220px] border-r border-border bg-surface-2 flex flex-col shrink-0">
        <div className="px-4 pt-5 pb-3 border-b border-border-2">
          {/* Section label */}
          <div className="text-[11px] font-semibold text-faint tracking-wider uppercase mb-3">Policy Source</div>
          {sourcesLoading ? (
            <div aria-busy="true">
              {[0, 1, 2].map((i) => (
                <div key={i} className="h-8 rounded-md bg-border mb-1 animate-pulse" />
              ))}
            </div>
          ) : sourcesError ? (
            <div role="alert" className="text-xs text-faint">
              {sourcesError}
            </div>
          ) : (
            <nav aria-label="Policy source filter" className="space-y-0.5">
              {sources.length === 0 ? (
                <div className="text-xs text-faint px-2">No policies indexed.</div>
              ) : (
                ["All Sources", ...sources].map((name) => {
                  const isActive = activeFilter === name;
                  return (
                    <button
                      key={name}
                      onClick={() => setActiveFilter(name)}
                      title={name}
                      className={`block w-full text-left px-3 py-2 rounded-md text-[13px] border-none cursor-pointer transition-colors ${
                        isActive 
                          ? "bg-accent/15 text-accent font-semibold" 
                          : "bg-transparent text-text-3 font-medium hover:bg-surface hover:text-text-2"
                      }`}
                    >
                      {name === "All Sources"
                        ? name
                        : name.replace(" Privacy Policy", "").replace(" Privacy Statement", "")}
                    </button>
                  );
                })
              )}
            </nav>
          )}
        </div>
        <div className="px-4 pt-4 pb-3">
          <div className="text-[11px] font-semibold text-faint tracking-wider uppercase mb-3">Topic Filter</div>
          <div className="space-y-0.5">
            {allTopics.map((tp) => (
              <button
                key={tp}
                onClick={() => setTopicFilter(tp)}
                disabled
                className="block w-full text-left px-3 py-2 rounded-md text-[13px] border-none bg-transparent text-faint font-medium opacity-50 cursor-not-allowed"
              >
                {tp}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Center chat */}
      <div className="flex-1 flex flex-col overflow-hidden min-w-0 bg-background">
        <div className="px-6 py-3.5 border-b border-border bg-surface flex items-center gap-2.5 shadow-sm z-10">
          <span className="text-[14px] font-semibold text-text-1">Ask Assistant</span>
          <span className="text-xs text-faint">·</span>
          <span className="text-[13px] text-accent font-semibold tracking-tight">
            {activeFilter.replace(" Privacy Policy", "").replace(" Privacy Statement", "")}
          </span>
          {topicFilter !== "All Topics" && (
            <>
              <span className="text-xs text-faint">·</span>
              <span className="text-[13px] text-accent font-medium">{topicFilter}</span>
            </>
          )}
        </div>

        {/* Messages */}
        <div 
          ref={scrollContainerRef}
          onScroll={handleScroll}
          className="flex-1 overflow-y-auto px-6 py-8 flex flex-col gap-6"
        >
          {messages.length === 0 && !uploadState && (
            <div className="flex flex-col items-center justify-center px-5 py-24 animate-stagger" style={{ "--idx": 1 } as React.CSSProperties}>
              <div className="relative mb-6">
                <div className="absolute inset-0 bg-accent/20 blur-2xl rounded-full" />
                <div className="relative bg-surface border border-border shadow-[var(--shadow-diffusion)] w-16 h-16 rounded-3xl flex items-center justify-center">
                  <MessageSquare className="w-8 h-8 text-accent" strokeWidth={1.5} />
                </div>
              </div>
              <div className="font-bold text-text-1 mb-2 text-2xl tracking-tight">Ask a policy question</div>
              <div className="text-text-2 text-[15px] max-w-md text-center">Select a policy source and type your question below. We will analyze the documents to find the exact compliance answers.</div>
            </div>
          )}
          {messages.map((msg, idx) => (
            <div
              key={idx}
              className={`flex flex-col max-w-[85%] animate-stagger ${msg.role === "user" ? "items-end self-end" : "items-start self-start"}`}
            >
              {msg.role === "user" ? (
                <div className="bg-user-bubble text-user-bubble-text rounded-2xl rounded-tr-sm px-4 py-3 text-[14px] leading-relaxed shadow-sm">
                  {msg.content}
                </div>
              ) : (
                <div className="flex flex-col items-start w-full">
                  {isStreaming && idx === messages.length - 1 ? (
                    <div className="bg-surface border border-border rounded-[2rem] rounded-tl-sm px-6 py-5 text-[14px] leading-relaxed text-text-2 shadow-[var(--shadow-diffusion)] min-w-[140px]">
                      {!msg.content ? (
                        <div className="flex items-center gap-1.5 py-1">
                          <div className="w-1.5 h-1.5 rounded-full bg-accent animate-[dot-bounce_1.4s_infinite_ease-in-out_both] [animation-delay:-0.32s]"></div>
                          <div className="w-1.5 h-1.5 rounded-full bg-accent animate-[dot-bounce_1.4s_infinite_ease-in-out_both] [animation-delay:-0.16s]"></div>
                          <div className="w-1.5 h-1.5 rounded-full bg-accent animate-[dot-bounce_1.4s_infinite_ease-in-out_both]"></div>
                          <span className="ml-2 text-[11px] font-bold text-accent tracking-widest uppercase animate-pulse">Reasoning</span>
                        </div>
                      ) : (
                        <p className="m-0">
                          {msg.content}
                          <StreamingCursor />
                        </p>
                      )}
                    </div>
                  ) : (
                    <AnswerCard
                      content={msg.content}
                      citations={msg.citations}
                      isNoMatch={msg.isNoMatch}
                      isError={msg.isError}
                      onRetry={handleRetry}
                      onOpenEvidence={handleOpenEvidence}
                      activeFilter={activeFilter}
                    />
                  )}
                </div>
              )}
              <span className="text-[11px] text-faint mt-1.5 font-medium px-1">
                {new Date().toTimeString().slice(0, 5)}
              </span>
            </div>
          ))}

          {/* Upload Progress Message */}
          {uploadState && (
            <div className="flex flex-col max-w-[85%] items-start self-start">
              <UploadProgressCard
                fileName={uploadState.fileName}
                docStatus={uploadState.docStatus}
                currentTask={uploadState.currentTask}
                jobStatus={uploadState.jobStatus}
              />
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Suggested prompts */}
        <div className="px-6 py-3 border-t border-border-2 bg-surface flex gap-2.5 overflow-x-auto shrink-0 hide-scrollbar" style={{ scrollbarWidth: 'none' }}>
          {SUGGESTED_PROMPTS.map((p, i) => (
            <button
              key={i}
              onClick={() => setInput(p)}
              className="whitespace-nowrap text-[13px] px-3.5 py-1.5 border border-border rounded-full bg-surface-2 text-text-3 font-medium cursor-pointer shrink-0 hover:bg-border transition-colors hover:text-text-2"
            >
              {p}
            </button>
          ))}
        </div>

        {/* Input */}
        <div className="px-6 pb-6 pt-3 shrink-0 bg-surface">
          <div className="flex items-center gap-3 border border-border rounded-xl p-2.5 bg-surface-2 transition-colors focus-within:border-accent focus-within:ring-2 focus-within:ring-accent/20 focus-within:bg-background shadow-sm">
            <button
              onClick={() => fileInputRef.current?.click()}
              className="p-2 text-faint hover:text-accent bg-transparent border-none rounded-lg cursor-pointer transition-colors active:scale-95 flex items-center justify-center"
              title="Upload Policy"
            >
              <Paperclip className="w-5 h-5" />
            </button>
            <input 
              type="file" 
              className="hidden" 
              ref={fileInputRef} 
              onChange={handleUploadFile}
              accept=".pdf,.txt,.md,.docx"
            />
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
              placeholder={`Ask about ${activeFilter.replace(" Privacy Policy", "").replace(" Privacy Statement", "")}…`}
              rows={2}
              className="flex-1 border-none outline-none resize-none text-[14px] text-text-1 bg-transparent font-sans leading-relaxed px-1 py-1 placeholder:text-faint"
            />
            <button
              onClick={handleSend}
              disabled={isStreaming}
              className="self-end bg-accent text-white border-none rounded-lg px-5 py-2 text-[14px] font-semibold cursor-pointer transition-all hover:bg-accent/90 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
            >
              Send
            </button>
          </div>
        </div>
      </div>

      {/* Right evidence panel */}
      {isEvidenceOpen && (
        <div className="w-[320px] border-l border-border bg-surface-2 flex flex-col shrink-0 shadow-[-4px_0_15px_-3px_rgba(0,0,0,0.05)] z-20">
          <div className="px-5 py-4 border-b border-border-2 flex justify-between items-center bg-surface">
            <div>
              <span className="text-[12px] font-bold text-text-1 tracking-wider uppercase">Evidence</span>
              <span className="text-[12px] text-faint ml-2 font-medium">{activeEvidence.length} sources</span>
            </div>
            <button
              type="button"
              onClick={() => setIsEvidenceOpen(false)}
              className="bg-transparent border-none cursor-pointer text-lg text-faint hover:text-text-1 transition-colors flex items-center justify-center w-6 h-6 rounded-md hover:bg-border"
              aria-label="Close evidence panel"
            >
              ✕
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {activeEvidence.length > 0 ? activeEvidence.map((c) => (
              <div key={c.id} className="bg-surface border border-border rounded-xl p-4 shadow-sm hover:border-accent/30 transition-colors">
                <div className="text-[10px] font-bold text-accent uppercase tracking-wider mb-1.5">
                  {activeFilter.replace(" Privacy Policy", "").replace(" Privacy Statement", "")}
                </div>
                <div className="text-[13px] font-semibold text-text-2 mb-2 leading-tight">{c.title}</div>
                <p className="text-[12px] text-text-3 leading-relaxed mb-3 bg-surface-2 border-l-2 border-accent pl-3 py-1.5 rounded-r-md italic">
                  "{c.text.slice(0, 160)}{c.text.length > 160 ? "…" : ""}"
                </p>
                <div className="flex justify-between items-center pt-2 border-t border-border-2/50">
                  <span className="text-[11px] text-faint font-medium">Source #{c.id}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] text-faint font-medium">Relevance</span>
                    <div className="w-16"><ConfidenceBar score={c.score ?? 0} /></div>
                  </div>
                </div>
              </div>
            )) : (
              <div className="text-center px-4 py-12 text-faint text-[13px]">
                <div className="text-3xl mb-3 opacity-50">📋</div>
                Send a query to see evidence
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
