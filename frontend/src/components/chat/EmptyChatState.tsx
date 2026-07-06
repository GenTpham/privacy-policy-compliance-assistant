import { memo } from "react";
import { MessageSquare } from "lucide-react";

export const EmptyChatState = memo(function EmptyChatState() {
  return (
    <div className="flex flex-col items-center justify-center px-5 py-24 animate-stagger" style={{ "--idx": 1 } as React.CSSProperties}>
      <div className="relative mb-6" aria-hidden="true">
        <div className="absolute inset-0 bg-accent/20 blur-2xl rounded-full" />
        <div className="relative bg-surface border border-border shadow-[var(--shadow-diffusion)] w-16 h-16 rounded-3xl flex items-center justify-center">
          <MessageSquare className="w-8 h-8 text-accent" strokeWidth={1.5} />
        </div>
      </div>
      <h2 className="font-bold text-text-1 mb-2 text-2xl tracking-tight text-center">
        Ask a policy question
      </h2>
      <p className="text-text-2 text-[15px] max-w-md text-center leading-relaxed">
        Select a policy source and type your question below. We will analyze the documents to find the exact compliance answers.
      </p>
    </div>
  );
});
