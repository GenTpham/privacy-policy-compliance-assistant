import { useState, useRef, useEffect, useCallback } from "react";
import { StreamingCursor } from "@/components/chat/StreamingCursor";
import { AnswerCard } from "@/components/chat/AnswerCard";
import { UploadProgressCard } from "@/components/chat/UploadProgressCard";
import { fetchWithAuth } from "@/lib/api";
import type { UseSSEChatReturn, Citation } from "@/hooks/useSSEChat";

import { ChatSidebar } from "@/components/chat/ChatSidebar";
import { ChatInput } from "@/components/chat/ChatInput";
import { EvidencePanel } from "@/components/chat/EvidencePanel";
import { EmptyChatState } from "@/components/chat/EmptyChatState";
import { User, Share, ArrowRight, ChevronRight, Plus } from "lucide-react";

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

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [isAutoScroll, setIsAutoScroll] = useState(true);
  const prevLengthRef = useRef(messages.length);

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
      <ChatSidebar
        sources={sources}
        sourcesLoading={sourcesLoading}
        sourcesError={sourcesError}
        activeFilter={activeFilter}
        onFilterChange={setActiveFilter}
        topicFilter={topicFilter}
        onTopicChange={setTopicFilter}
      />

      {/* Center chat */}
      <div className="flex-1 flex flex-col overflow-hidden min-w-0 bg-background">
        <header className="px-6 py-4 border-b border-border bg-surface flex items-center gap-2 shadow-sm z-10">
          <button className="w-8 h-8 flex items-center justify-center rounded-md border border-border bg-surface shadow-sm hover:bg-surface-2 transition-colors">
            <Plus className="w-4 h-4 text-text-2" />
          </button>
          
          <div className="flex items-center text-[14px] font-bold">
            <div className="flex items-center gap-2 px-2 text-text-2">
              <div className="w-2 h-2 rounded-full border border-text-2" />
              Private
            </div>
            <ChevronRight className="w-4 h-4 text-border-2 mx-1" />
            <div className="flex items-center gap-2 px-2 text-text-2">
              <div className="w-2 h-2 rounded-full border border-text-2" />
              Notes
            </div>
            <ChevronRight className="w-4 h-4 text-border-2 mx-1" />
            <div className="flex items-center gap-2 px-2 text-accent">
              <div className="w-2 h-2 rounded-full border border-accent bg-accent/10" />
              {activeFilter.replace(" Privacy Policy", "").replace(" Privacy Statement", "")}
            </div>
          </div>
        </header>

        {/* Messages */}
        <main 
          ref={scrollContainerRef}
          onScroll={handleScroll}
          className="flex-1 overflow-y-auto px-8 lg:px-24 py-12 flex flex-col gap-0"
          aria-label="Chat history"
          role="log"
        >
          {messages.length === 0 && !uploadState && <EmptyChatState />}
          
          {messages.map((msg, idx) => (
            <div
              key={idx}
              className={`flex flex-col w-full max-w-4xl mx-auto animate-stagger ${msg.role === "user" ? "mb-10" : "mb-12"}`}
            >
              {msg.role === "user" ? (
                <div className="w-full">
                  <h1 className="text-[24px] md:text-[32px] font-extrabold text-text-1 mb-6 tracking-tight leading-snug">
                    {msg.content}
                  </h1>
                  <div className="flex items-center justify-between pb-6 border-b border-border">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 bg-surface border border-border rounded-full flex items-center justify-center shadow-sm">
                        <User className="w-5 h-5 text-text-2" />
                      </div>
                      <div className="flex flex-col">
                        <span className="font-bold text-text-1 text-[14px]">x-ae-a-221b</span>
                        <span className="text-[12px] font-medium text-text-3 flex items-center">
                          Just now
                        </span>
                      </div>
                    </div>
                    <button className="flex items-center gap-2 bg-accent text-white px-4 py-2 rounded-lg font-bold text-[14px] shadow-sm hover:bg-accent/90 transition-colors">
                      <Share className="w-4 h-4" /> Share <ArrowRight className="w-4 h-4 ml-1" />
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex flex-col items-start w-full">
                  {isStreaming && idx === messages.length - 1 ? (
                    <div className="w-full">
                      {!msg.content ? (
                        <div className="flex items-center gap-1.5 py-1" role="status" aria-label="Assistant is thinking">
                          <div className="w-2 h-2 rounded-full bg-accent animate-[dot-bounce_1.4s_infinite_ease-in-out_both] [animation-delay:-0.32s]"></div>
                          <div className="w-2 h-2 rounded-full bg-accent animate-[dot-bounce_1.4s_infinite_ease-in-out_both] [animation-delay:-0.16s]"></div>
                          <div className="w-2 h-2 rounded-full bg-accent animate-[dot-bounce_1.4s_infinite_ease-in-out_both]"></div>
                          <span className="ml-2 text-[12px] font-bold text-accent tracking-widest uppercase animate-pulse">Reasoning</span>
                        </div>
                      ) : (
                        <div className="text-[15px] leading-[1.8] text-text-2">
                          {msg.content}
                          <StreamingCursor />
                        </div>
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
        </main>

        <ChatInput
          input={input}
          isStreaming={isStreaming}
          activeFilter={activeFilter}
          onInputChange={setInput}
          onSubmit={handleSend}
          onUploadFile={handleUploadFile}
        />
      </div>

      {/* Right evidence panel */}
      {isEvidenceOpen && (
        <EvidencePanel
          evidence={activeEvidence}
          activeFilter={activeFilter}
          onClose={() => setIsEvidenceOpen(false)}
        />
      )}
    </div>
  );
}
