import { useEffect, useRef, useState } from "react";
import { MessageBubble } from "./MessageBubble";
import type { Message } from "@/hooks/useSSEChat";

interface MessageListProps {
  messages: Message[];
  isStreaming: boolean;
}

/**
 * Scrollable message history.
 * Auto-scrolls to bottom on new messages via useRef + scrollIntoView.
 * Empty state shown when messages.length === 0.
 * Copywriting from UI-SPEC.md Copywriting Contract.
 */
export function MessageList({ messages, isStreaming }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
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

    if (isNewMessage) {
      setIsAutoScroll(true);
      scrollToBottom(true);
    } else if (isAutoScroll) {
      scrollToBottom(false);
    }
  }, [messages, isAutoScroll]);

  const handleScroll = () => {
    if (scrollContainerRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = scrollContainerRef.current;
      const isBottom = scrollHeight - scrollTop - clientHeight < 50;
      setIsAutoScroll(isBottom);
    }
  };

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-center px-8 py-12">
        <h2 className="text-xl font-semibold text-zinc-950 mb-2">
          Ask a policy question
        </h2>
        <p className="text-base text-zinc-500 max-w-[480px]">
          Type a question about any privacy policy in the corpus. For example:{" "}
          <span className="text-zinc-700">
            &ldquo;Which policy applies to customer data retention?&rdquo;
          </span>
        </p>
      </div>
    );
  }

  return (
    <div 
      className="flex-1 overflow-y-auto px-4 py-8"
      ref={scrollContainerRef}
      onScroll={handleScroll}
    >
      <div className="flex flex-col gap-4 max-w-3xl mx-auto">
        {messages.map((msg, index) => (
          <MessageBubble
            key={index}
            role={msg.role}
            content={msg.content}
            citations={msg.citations}
            isStreaming={
              isStreaming &&
              index === messages.length - 1 &&
              msg.role === "assistant"
            }
            isNoMatch={msg.isNoMatch}
            isError={msg.isError}
          />
        ))}
        {/* Scroll anchor */}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
