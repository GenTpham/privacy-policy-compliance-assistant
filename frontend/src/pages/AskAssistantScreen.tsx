import { useState, useRef, useEffect } from "react";
import { useTheme } from "@/lib/theme";
import { ConfidenceBar } from "@/components/ui/ConfidenceBar";
import { StreamingCursor } from "@/components/chat/StreamingCursor";
import { SUGGESTED_PROMPTS } from "@/lib/mockData";
import { fetchWithAuth } from "@/lib/api";
import type { UseSSEChatReturn, Citation } from "@/hooks/useSSEChat";

interface Props {
  chat: UseSSEChatReturn;
  forceLogout: () => void;
}

export function AskAssistantScreen({ chat, forceLogout }: Props) {
  const { t, accent } = useTheme();
  const { messages, isStreaming, submit } = chat;

  const [input, setInput] = useState("");
  const [sources, setSources] = useState<string[]>([]);
  const [sourcesLoading, setSourcesLoading] = useState(true);
  const [sourcesError, setSourcesError] = useState<string | null>(null);
  const [activeFilter, setActiveFilter] = useState("All Sources");
  const [topicFilter, setTopicFilter] = useState("All Topics");
  const [activeEvidence, setActiveEvidence] = useState<Citation[]>([]);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const allTopics = ["All Topics", "Data Collection", "Third-Party Sharing", "Data Retention", "User Rights", "Cookies"];

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    const last = messages[messages.length - 1];
    if (last?.role === "assistant" && last.citations && last.citations.length > 0) {
      setActiveEvidence(last.citations);
    }
  }, [messages]);

  useEffect(() => {
    fetchWithAuth("/api/sources", { method: "GET" }, forceLogout)
      .then((r) => r.json())
      .then((data: { sources: string[] }) => {
        setSources(data.sources ?? []);
        setSourcesLoading(false);
      })
      .catch(() => {
        setSourcesError("Could not load sources. Try refreshing the page.");
        setSourcesLoading(false);
      });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  // mount only — forceLogout identity changes on each render; adding it would re-fetch continuously

  const handleSend = () => {
    if (!input.trim() || isStreaming) return;
    submit(input, forceLogout, activeFilter === "All Sources" ? null : activeFilter);
    setInput("");
  };

  return (
    <div style={{ display: "flex", height: "100%", overflow: "hidden" }}>
      {/* Left filter sidebar */}
      <div style={{ width: 220, borderRight: `1px solid ${t.border}`, background: t.surface2, display: "flex", flexDirection: "column", flexShrink: 0 }}>
        <div style={{ padding: "20px 16px 12px", borderBottom: `1px solid ${t.border2}` }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: t.faint, letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 10 }}>Policy Source</div>
          {indexedPolicies.map((p) => (
            <button
              key={p.id}
              onClick={() => setActiveFilter(p.name)}
              style={{
                display: "block", width: "100%", textAlign: "left",
                padding: "7px 10px", borderRadius: 5, fontSize: 12, border: "none", cursor: "pointer", marginBottom: 2,
                background: activeFilter === p.name ? accent : "transparent",
                color: activeFilter === p.name ? "#fff" : t.text3,
                fontWeight: activeFilter === p.name ? 600 : 400,
              }}
            >
              {p.name.replace(" Privacy Policy", "").replace(" Privacy Statement", "")}
            </button>
          ))}
        </div>
        <div style={{ padding: "16px 16px 12px" }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: t.faint, letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 10 }}>Topic Filter</div>
          {allTopics.map((tp) => (
            <button
              key={tp}
              onClick={() => setTopicFilter(tp)}
              style={{
                display: "block", width: "100%", textAlign: "left",
                padding: "7px 10px", borderRadius: 5, fontSize: 12, border: "none", cursor: "pointer", marginBottom: 2,
                background: topicFilter === tp ? accent : "transparent",
                color: topicFilter === tp ? "#fff" : t.text3,
                fontWeight: topicFilter === tp ? 600 : 400,
              }}
            >
              {tp}
            </button>
          ))}
        </div>
      </div>

      {/* Center chat */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", minWidth: 0, background: t.bg }}>
        <div style={{ padding: "14px 20px", borderBottom: `1px solid ${t.border}`, background: t.surface, display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: t.text }}>Ask Assistant</span>
          <span style={{ fontSize: 11, color: t.faint }}>·</span>
          <span style={{ fontSize: 12, color: accent, fontWeight: 500 }}>
            {activeFilter.replace(" Privacy Policy", "").replace(" Privacy Statement", "")}
          </span>
          {topicFilter !== "All Topics" && (
            <>
              <span style={{ fontSize: 11, color: t.faint }}>·</span>
              <span style={{ fontSize: 12, color: accent }}>{topicFilter}</span>
            </>
          )}
        </div>

        {/* Messages */}
        <div style={{ flex: 1, overflowY: "auto", padding: "20px 24px", display: "flex", flexDirection: "column", gap: 20 }}>
          {messages.length === 0 && (
            <div style={{ textAlign: "center", padding: "60px 20px", fontSize: 13 }}>
              <div style={{ fontSize: 32, marginBottom: 12 }}>💬</div>
              <div style={{ fontWeight: 700, color: t.text, marginBottom: 6, fontSize: 15 }}>Ask a policy question</div>
              <div style={{ color: t.text2, fontSize: 13 }}>Select a policy source and type your question below.</div>
            </div>
          )}
          {messages.map((msg, idx) => (
            <div
              key={idx}
              style={{
                display: "flex", flexDirection: "column",
                alignItems: msg.role === "user" ? "flex-end" : "flex-start",
                maxWidth: "85%",
                alignSelf: msg.role === "user" ? "flex-end" : "flex-start",
              }}
            >
              {msg.role === "user" ? (
                <div style={{ background: t.userBubble, color: t.userBubbleText, borderRadius: "8px 8px 2px 8px", padding: "10px 14px", fontSize: 13, lineHeight: 1.5 }}>
                  {msg.content}
                </div>
              ) : (
                <div style={{ background: t.surface, border: `1px solid ${t.border}`, borderRadius: "2px 8px 8px 8px", padding: "14px 16px", fontSize: 13, lineHeight: 1.6, color: t.text2 }}>
                  <p style={{ margin: "0 0 12px" }}>
                    {msg.content}
                    {isStreaming && idx === messages.length - 1 && <StreamingCursor />}
                  </p>
                  {msg.citations && msg.citations.length > 0 && !isStreaming && (
                    <div style={{ borderTop: `1px solid ${t.border2}`, paddingTop: 10, display: "flex", alignItems: "center", gap: 12 }}>
                      <span style={{ fontSize: 11, color: t.faint }}>Confidence</span>
                      <div style={{ width: 120 }}>
                        <ConfidenceBar score={0.88} />
                      </div>
                      <button
                        onClick={() => setActiveEvidence(msg.citations!)}
                        style={{ marginLeft: "auto", fontSize: 11, color: accent, background: "none", border: `1px solid ${accent}`, borderRadius: 4, padding: "3px 8px", cursor: "pointer", fontWeight: 600 }}
                      >
                        {msg.citations.length} citation{msg.citations.length > 1 ? "s" : ""}
                      </button>
                    </div>
                  )}
                  {msg.isNoMatch && !isStreaming && (
                    <div style={{ fontSize: 12, color: t.muted, fontStyle: "italic", marginTop: 8 }}>
                      No matching policy sections found for this query.
                    </div>
                  )}
                </div>
              )}
              <span style={{ fontSize: 10, color: t.faintest, marginTop: 4 }}>
                {new Date().toTimeString().slice(0, 5)}
              </span>
            </div>
          ))}
          {isStreaming && messages[messages.length - 1]?.role !== "assistant" && (
            <div style={{ display: "flex", gap: 4, padding: "12px 16px", background: t.surface, border: `1px solid ${t.border}`, borderRadius: 8, width: "fit-content" }}>
              {[0, 1, 2].map((i) => (
                <div key={i} style={{ width: 6, height: 6, borderRadius: "50%", background: accent, animation: `dot-bounce 1.2s ${i * 0.2}s infinite ease-in-out` }} />
              ))}
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Suggested prompts */}
        <div style={{ padding: "8px 24px", borderTop: `1px solid ${t.border2}`, background: t.surface, display: "flex", gap: 8, overflowX: "auto", flexShrink: 0 }}>
          {SUGGESTED_PROMPTS.map((p, i) => (
            <button
              key={i}
              onClick={() => setInput(p)}
              style={{ whiteSpace: "nowrap", fontSize: 11, padding: "4px 10px", border: `1px solid ${t.border}`, borderRadius: 4, background: t.surface2, color: t.text3, cursor: "pointer", flexShrink: 0 }}
            >
              {p}
            </button>
          ))}
        </div>

        {/* Input */}
        <div style={{ padding: "12px 24px 20px", flexShrink: 0, background: t.surface }}>
          <div style={{ display: "flex", gap: 8, border: `1px solid ${t.border}`, borderRadius: 8, padding: "10px 14px", background: t.surface2 }}>
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
              placeholder={`Ask about ${activeFilter.replace(" Privacy Policy", "").replace(" Privacy Statement", "")}…`}
              rows={2}
              style={{ flex: 1, border: "none", outline: "none", resize: "none", fontSize: 13, color: t.text, background: "transparent", fontFamily: "inherit", lineHeight: 1.5 }}
            />
            <button
              onClick={handleSend}
              disabled={isStreaming}
              style={{ alignSelf: "flex-end", background: accent, color: "#fff", border: "none", borderRadius: 6, padding: "7px 16px", fontSize: 13, fontWeight: 600, cursor: isStreaming ? "not-allowed" : "pointer", opacity: isStreaming ? 0.6 : 1 }}
            >
              Send
            </button>
          </div>
        </div>
      </div>

      {/* Right evidence panel */}
      <div style={{ width: 300, borderLeft: `1px solid ${t.border}`, background: t.surface2, display: "flex", flexDirection: "column", flexShrink: 0 }}>
        <div style={{ padding: "14px 16px", borderBottom: `1px solid ${t.border2}` }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: t.text, letterSpacing: "0.04em", textTransform: "uppercase" }}>Evidence</span>
          <span style={{ fontSize: 11, color: t.faint, marginLeft: 6 }}>{activeEvidence.length} sources</span>
        </div>
        <div style={{ flex: 1, overflowY: "auto", padding: 12 }}>
          {activeEvidence.length > 0 ? activeEvidence.map((c) => (
            <div key={c.id} style={{ background: t.surface, border: `1px solid ${t.border}`, borderRadius: 6, padding: 12, marginBottom: 10 }}>
              <div style={{ fontSize: 10, fontWeight: 700, color: accent, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4 }}>
                {activeFilter.replace(" Privacy Policy", "").replace(" Privacy Statement", "")}
              </div>
              <div style={{ fontSize: 11, fontWeight: 600, color: t.text2, marginBottom: 6 }}>{c.title}</div>
              <p style={{ fontSize: 12, color: t.text3, lineHeight: 1.55, margin: "0 0 10px", background: t.surface2, borderLeft: `3px solid ${accent}`, padding: "6px 8px", borderRadius: "0 4px 4px 0" }}>
                "{c.text.slice(0, 160)}{c.text.length > 160 ? "…" : ""}"
              </p>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: 10, color: t.faint }}>Source #{c.id}</span>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span style={{ fontSize: 10, color: t.faint }}>Relevance</span>
                  <div style={{ width: 80 }}><ConfidenceBar score={0.85} /></div>
                </div>
              </div>
            </div>
          )) : (
            <div style={{ textAlign: "center", padding: "40px 20px", color: t.faint, fontSize: 12 }}>
              <div style={{ fontSize: 24, marginBottom: 8 }}>📋</div>
              Send a query to see evidence
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
