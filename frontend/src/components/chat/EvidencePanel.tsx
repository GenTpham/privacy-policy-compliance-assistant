import { memo } from "react";
import { ConfidenceBar } from "@/components/ui/ConfidenceBar";
import type { Citation } from "@/hooks/useSSEChat";
import { XIcon } from "lucide-react";

interface EvidencePanelProps {
  evidence: Citation[];
  activeFilter: string;
  onClose: () => void;
}

export const EvidencePanel = memo(function EvidencePanel({
  evidence,
  activeFilter,
  onClose
}: EvidencePanelProps) {
  return (
    <aside 
      className="w-[320px] border-l border-border bg-surface-2 flex flex-col shrink-0 shadow-[-4px_0_15px_-3px_rgba(0,0,0,0.05)] z-20"
      aria-label="Evidence panel"
    >
      <header className="px-5 py-4 border-b border-border-2 flex justify-between items-center bg-surface">
        <div>
          <h2 className="text-[12px] font-bold text-text-1 tracking-wider uppercase inline">Evidence</h2>
          <span className="text-[12px] text-faint ml-2 font-medium" aria-label={`${evidence.length} sources found`}>
            {evidence.length} sources
          </span>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="bg-transparent border-none cursor-pointer text-faint hover:text-text-1 transition-colors flex items-center justify-center w-6 h-6 rounded-md hover:bg-border"
          aria-label="Close evidence panel"
        >
          <XIcon className="w-4 h-4" />
        </button>
      </header>
      
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {evidence.length > 0 ? evidence.map((c) => (
          <article key={c.id} className="bg-surface border border-border rounded-xl p-4 shadow-sm hover:border-accent/30 transition-colors">
            <div className="text-[10px] font-bold text-accent uppercase tracking-wider mb-1.5">
              {activeFilter.replace(" Privacy Policy", "").replace(" Privacy Statement", "")}
            </div>
            <h3 className="text-[13px] font-semibold text-text-2 mb-2 leading-tight">{c.title}</h3>
            <blockquote className="text-[12px] text-text-3 leading-relaxed mb-3 bg-surface-2 border-l-2 border-accent pl-3 py-1.5 rounded-r-md italic">
              "{c.text.slice(0, 160)}{c.text.length > 160 ? "…" : ""}"
            </blockquote>
            <div className="flex justify-between items-center pt-2 border-t border-border-2/50">
              <span className="text-[11px] text-faint font-medium">Source #{c.id}</span>
              <div className="flex items-center gap-2">
                <span className="text-[11px] text-faint font-medium">Relevance</span>
                <div className="w-16" aria-label={`Relevance score: ${c.score ?? 0}`}>
                  <ConfidenceBar score={c.score ?? 0} />
                </div>
              </div>
            </div>
          </article>
        )) : (
          <div className="text-center px-4 py-12 text-faint text-[13px]" role="status">
            <div className="text-3xl mb-3 opacity-50" aria-hidden="true">📋</div>
            Send a query to see evidence
          </div>
        )}
      </div>
    </aside>
  );
});
