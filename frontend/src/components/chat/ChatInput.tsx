import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SendHorizonal } from "lucide-react";

interface ChatInputProps {
  isStreaming: boolean;
  onSubmit: (message: string) => void;
}

/**
 * Chat input row.
 * Submit on Enter (not Shift+Enter) per ACCESSIBILITY CONTRACT in UI-SPEC.
 * Disabled while isStreaming === true.
 * Input row height: 52px (UI-SPEC spacing exception).
 */
export function ChatInput({ isStreaming, onSubmit }: ChatInputProps) {
  const [value, setValue] = useState("");

  const handleSubmit = () => {
    const trimmed = value.trim();
    if (!trimmed || isStreaming) return;
    onSubmit(trimmed);
    setValue("");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="flex items-center gap-2 px-4 py-2 bg-zinc-50 border-t border-zinc-200 h-[52px] shrink-0">
      <Input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask a policy question..."
        disabled={isStreaming}
        className="flex-1 bg-white"
        aria-label="Chat message input"
      />
      <Button
        onClick={handleSubmit}
        disabled={isStreaming || !value.trim()}
        className="bg-zinc-950 text-white hover:bg-zinc-800 shrink-0"
        aria-label="Send Message"
      >
        <SendHorizonal className="h-4 w-4 mr-1" aria-hidden="true" />
        Send Message
      </Button>
    </div>
  );
}
