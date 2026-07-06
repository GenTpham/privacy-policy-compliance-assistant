import { memo, useRef, FormEvent } from "react";
import { Paperclip, Send, Mic, PlusCircle } from "lucide-react";
import { SUGGESTED_PROMPTS } from "@/lib/mockData";

interface ChatInputProps {
  input: string;
  isStreaming: boolean;
  activeFilter: string;
  onInputChange: (val: string) => void;
  onSubmit: () => void;
  onUploadFile: (e: React.ChangeEvent<HTMLInputElement>) => void;
}

export const ChatInput = memo(function ChatInput({
  input,
  isStreaming,
  activeFilter,
  onInputChange,
  onSubmit,
  onUploadFile
}: ChatInputProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSubmit = (e?: FormEvent) => {
    e?.preventDefault();
    if (!input.trim() || isStreaming) return;
    onSubmit();
  };

  const policyName = activeFilter.replace(" Privacy Policy", "").replace(" Privacy Statement", "");

  return (
    <div className="flex flex-col shrink-0">
      {/* Suggested prompts */}
      <div 
        className="px-6 py-3 border-t border-border-2 bg-surface flex gap-2.5 overflow-x-auto hide-scrollbar" 
        style={{ scrollbarWidth: 'none' }}
        aria-label="Suggested prompts"
      >
        {SUGGESTED_PROMPTS.map((p, i) => (
          <button
            key={i}
            onClick={() => onInputChange(p)}
            className="whitespace-nowrap text-[13px] px-3.5 py-1.5 border border-border rounded-full bg-surface-2 text-text-3 font-medium cursor-pointer shrink-0 hover:bg-border transition-colors hover:text-text-2"
          >
            {p}
          </button>
        ))}
      </div>

      {/* Input area */}
      <div className="px-6 pb-6 pt-3 bg-surface">
        <form 
          onSubmit={handleSubmit}
          className="flex items-center gap-2 border border-border rounded-full p-2 bg-surface shadow-sm transition-colors focus-within:border-accent/50 focus-within:ring-2 focus-within:ring-accent/20"
        >
          <div className="flex items-center gap-2 flex-1 pl-2">
            <PlusCircle className="w-5 h-5 text-text-1" />
            <input
              type="file"
              className="hidden"
              ref={fileInputRef}
              onChange={onUploadFile}
              accept=".pdf,.txt,.md,.docx"
              aria-label="Hidden file input for policy upload"
            />
            
            <input
              type="text"
              value={input}
              onChange={(e) => onInputChange(e.target.value)}
              placeholder="Ask a follow up..."
              aria-label="Ask a follow up"
              className="flex-1 border-none outline-none text-[16px] text-text-2 bg-transparent font-sans leading-relaxed placeholder:text-text-3"
            />
          </div>
          
          <div className="flex items-center gap-2 pr-1">
            <button
              type="button"
              className="p-2 text-text-1 hover:bg-surface-2 rounded-full cursor-pointer transition-colors active:scale-95 flex items-center justify-center shrink-0"
              aria-label="Voice input"
              title="Voice input"
            >
              <Mic className="w-5 h-5" />
            </button>
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="p-2 text-text-1 hover:bg-surface-2 rounded-full cursor-pointer transition-colors active:scale-95 flex items-center justify-center shrink-0"
              aria-label="Upload Policy"
              title="Upload Policy"
            >
              <Paperclip className="w-5 h-5" />
            </button>
            <button
              type="submit"
              disabled={isStreaming || !input.trim()}
              className="bg-accent text-white border-none rounded-full w-10 h-10 flex items-center justify-center cursor-pointer transition-all hover:bg-accent/90 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed shadow-sm shrink-0"
              aria-label="Send message"
            >
              <Send className="w-4 h-4 ml-0.5" />
            </button>
          </div>
        </form>
      </div>
    </div>
  );
});
