import { memo } from "react";
import { FileText, X } from "lucide-react";
import { Badge } from "@/components/ui/Badge";

interface Document {
  id: number;
  title: string;
  status: string;
  created_at: string;
  updated_at: string;
}

interface PolicyDetailDrawerProps {
  selected: Document | null;
  onClose: () => void;
  onAsk?: (policyName: string) => void;
}

export const PolicyDetailDrawer = memo(function PolicyDetailDrawer({
  selected,
  onClose,
  onAsk
}: PolicyDetailDrawerProps) {
  if (!selected) return null;

  return (
    <aside 
      className="w-[400px] border-l border-border bg-surface flex flex-col overflow-hidden shrink-0 shadow-[-20px_0_40px_-15px_rgba(0,0,0,0.05)] z-20 animate-stagger"
      aria-label="Document Details"
    >
      <header className="px-8 py-6 border-b border-border-2 flex justify-between items-center bg-surface-2/30">
        <h2 className="text-[15px] font-bold text-text-1 tracking-tight m-0">Document Details</h2>
        <button 
          onClick={onClose} 
          className="bg-transparent border-none cursor-pointer text-faint hover:text-text-1 transition-all w-8 h-8 flex items-center justify-center rounded-full hover:bg-border active:scale-95"
          aria-label="Close details"
        >
          <X className="w-5 h-5" />
        </button>
      </header>
      
      <div className="flex-1 overflow-y-auto p-8 flex flex-col">
        <div className="w-12 h-12 rounded-2xl bg-accent/10 flex items-center justify-center mb-5 border border-accent/20" aria-hidden="true">
          <FileText className="w-6 h-6 text-accent" />
        </div>
        
        <h3 className="text-xl font-bold text-text-1 leading-tight mb-8">
          {selected.title}
        </h3>
        
        <dl className="grid grid-cols-2 gap-4 mb-10">
          <div className="bg-surface-2 border border-border-2/50 rounded-2xl px-5 py-4 shadow-sm hover:border-accent/30 transition-colors">
            <dt className="text-[11px] text-faint font-bold uppercase tracking-widest mb-2">Date Added</dt>
            <dd className="text-[14px] font-semibold text-text-2 m-0">{new Date(selected.created_at).toLocaleDateString()}</dd>
          </div>
          
          <div className="bg-surface-2 border border-border-2/50 rounded-2xl px-5 py-4 shadow-sm hover:border-accent/30 transition-colors">
            <dt className="text-[11px] text-faint font-bold uppercase tracking-widest mb-2">Status</dt>
            <dd className="text-[14px] font-semibold text-text-2 m-0"><Badge status={selected.status} /></dd>
          </div>
          
          <div className="bg-surface-2 border border-border-2/50 rounded-2xl px-5 py-4 shadow-sm hover:border-accent/30 transition-colors">
            <dt className="text-[11px] text-faint font-bold uppercase tracking-widest mb-2">Doc ID</dt>
            <dd className="text-[14px] font-semibold text-text-2 m-0">#{selected.id}</dd>
          </div>
        </dl>
        
        <div className="space-y-3 mt-auto">
          <button
            onClick={() => onAsk?.(selected.title)}
            disabled={selected.status !== "success"}
            className="w-full py-3.5 bg-accent text-white border-none rounded-xl text-[14px] font-bold cursor-pointer hover:bg-accent/90 active:scale-95 transition-all shadow-sm flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Ask questions about this
          </button>
        </div>
      </div>
    </aside>
  );
});
