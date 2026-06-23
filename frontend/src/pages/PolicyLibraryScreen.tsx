import { useState, useEffect, useRef } from "react";
import { Badge } from "@/components/ui/Badge";
import { fetchWithAuth } from "@/lib/api";
import { UploadCloud, X, FileText, CheckCircle2 } from "lucide-react";

interface Document {
  id: number;
  title: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export function PolicyLibraryScreen({ onAsk, forceLogout }: { onAsk?: (policyName: string) => void, forceLogout: () => void }) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [selected, setSelected] = useState<Document | null>(null);
  const [search, setSearch] = useState("");
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadTitle, setUploadTitle] = useState("");
  const [isUploading, setIsUploading] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadDocs = () => {
    fetchWithAuth("/api/documents/", { method: "GET" }, forceLogout)
      .then(res => res.json())
      .then(data => setDocuments(data || []))
      .catch(console.error);
  };

  useEffect(() => {
    loadDocs();
    const interval = setInterval(() => {
      setDocuments(prev => {
        if (prev.some(d => !["success", "failed"].includes(d.status))) {
          loadDocs();
        }
        return prev;
      });
    }, 1500);
    return () => clearInterval(interval);
  }, []);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile) return;
    setIsUploading(true);
    const formData = new FormData();
    formData.append("file", uploadFile);
    if (uploadTitle) formData.append("title", uploadTitle);

    try {
      const res = await fetchWithAuth("/api/documents/", {
        method: "POST",
        body: formData,
      }, forceLogout);
      
      if (res.ok) {
        setIsModalOpen(false);
        setUploadFile(null);
        setUploadTitle("");
        loadDocs();
      }
    } catch (err) {
      console.error("Upload failed", err);
    } finally {
      setIsUploading(false);
    }
  };

  const filtered = documents.filter((p) => p.title.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="flex h-full overflow-hidden">
      {/* Table area */}
      <div className="flex-1 flex flex-col overflow-hidden bg-background">
        {/* Header */}
        <div className="px-10 py-8 border-b border-border bg-surface flex justify-between items-center z-10 shadow-sm animate-stagger" style={{ "--idx": 0 } as React.CSSProperties}>
          <div>
            <h1 className="text-3xl font-bold text-text-1 tracking-tighter m-0">Policy Library</h1>
            <p className="text-[14px] text-muted font-medium mt-1">
              {documents.length} documents · {documents.filter((p) => p.status === "success").length} indexed
            </p>
          </div>
          <div className="flex gap-4">
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search documents…"
              className="px-4 py-2.5 text-[14px] border border-border rounded-xl outline-none w-[260px] bg-surface-2 text-text-1 focus:border-accent focus:ring-2 focus:ring-accent/20 transition-all placeholder:text-faint"
            />
            <button 
              onClick={() => setIsModalOpen(true)}
              className="bg-text-1 text-surface border-none rounded-xl px-5 py-2.5 text-[14px] font-bold cursor-pointer hover:bg-text-2 transition-all shadow-sm active:scale-95 flex items-center gap-2"
            >
              <UploadCloud className="w-4 h-4" />
              Upload Policy
            </button>
          </div>
        </div>

        {/* Table */}
        <div className="flex-1 overflow-y-auto px-10 py-6">
          <div className="bg-surface border border-border rounded-[2rem] overflow-hidden shadow-[var(--shadow-diffusion)] animate-stagger" style={{ "--idx": 1 } as React.CSSProperties}>
            <table className="w-full border-collapse">
              <thead className="bg-surface-2/50 border-b border-border">
                <tr>
                  {["Document Title", "Status", "Uploaded On", "File ID"].map((h) => (
                    <th key={h} className="px-8 py-5 text-left text-[11px] font-bold text-faint tracking-widest uppercase whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((p, idx) => {
                  const isSelected = selected?.id === p.id;
                  return (
                    <tr
                      key={p.id}
                      onClick={() => setSelected(p)}
                      className={`border-b border-border-2 cursor-pointer transition-colors animate-stagger ${
                        isSelected 
                          ? "bg-accent/5 hover:bg-accent/10" 
                          : "hover:bg-surface-2/50 bg-surface"
                      }`}
                      style={{ "--idx": idx + 2 } as React.CSSProperties}
                    >
                      <td className="px-8 py-5">
                        <div className="text-[15px] font-semibold text-text-1 mb-1 flex items-center gap-2">
                          <FileText className="w-4 h-4 text-muted" />
                          {p.title}
                        </div>
                      </td>
                      <td className="px-8 py-5">
                        <Badge status={p.status} />
                      </td>
                      <td className="px-8 py-5 text-[14px] text-muted font-mono">{new Date(p.created_at).toLocaleDateString()}</td>
                      <td className="px-8 py-5 text-[13px] text-faint font-mono">#{p.id}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {filtered.length === 0 && (
              <div className="text-center py-24">
                <div className="text-faint flex justify-center mb-4"><FileText className="w-12 h-12" strokeWidth={1} /></div>
                <div className="text-[16px] text-text-1 font-bold mb-1">No documents found</div>
                <div className="text-[14px] text-muted font-medium">Upload a document to get started.</div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Detail drawer */}
      {selected && (
        <div className="w-[400px] border-l border-border bg-surface flex flex-col overflow-hidden shrink-0 shadow-[-20px_0_40px_-15px_rgba(0,0,0,0.05)] z-20 animate-stagger">
          <div className="px-8 py-6 border-b border-border-2 flex justify-between items-center bg-surface-2/30">
            <span className="text-[15px] font-bold text-text-1 tracking-tight">Document Details</span>
            <button 
              onClick={() => setSelected(null)} 
              className="bg-transparent border-none cursor-pointer text-faint hover:text-text-1 transition-all w-8 h-8 flex items-center justify-center rounded-full hover:bg-border active:scale-95"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-8">
            <div className="w-12 h-12 rounded-2xl bg-accent/10 flex items-center justify-center mb-5 border border-accent/20">
              <FileText className="w-6 h-6 text-accent" />
            </div>
            <h2 className="text-xl font-bold text-text-1 leading-tight mb-8">{selected.title}</h2>
            
            <div className="grid grid-cols-2 gap-4 mb-10">
              {[
                { label: "Date Added", val: new Date(selected.created_at).toLocaleDateString() },
                { label: "Status",   val: <Badge status={selected.status} /> },
                { label: "Doc ID", val: `#${selected.id}` },
              ].map((r) => (
                <div key={r.label} className="bg-surface-2 border border-border-2/50 rounded-2xl px-5 py-4 shadow-sm hover:border-accent/30 transition-colors">
                  <div className="text-[11px] text-faint font-bold uppercase tracking-widest mb-2">{r.label}</div>
                  <div className="text-[14px] font-semibold text-text-2">{r.val}</div>
                </div>
              ))}
            </div>
            
            <div className="space-y-3 mt-auto">
              <button
                onClick={() => onAsk?.(selected.title)}
                disabled={selected.status !== "success"}
                className="w-full py-3.5 bg-accent text-white border-none rounded-xl text-[14px] font-bold cursor-pointer hover:bg-accent/90 active:scale-95 transition-all shadow-sm flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <span>Ask questions about this</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Upload Modal (Liquid Glass Morphism Style) */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-background/60 backdrop-blur-md" onClick={() => !isUploading && setIsModalOpen(false)}></div>
          <div className="relative w-full max-w-lg bg-surface border border-border rounded-[2.5rem] shadow-[var(--shadow-diffusion)] overflow-hidden animate-stagger">
            <div className="px-8 py-6 border-b border-border bg-surface-2/30 flex justify-between items-center">
              <h2 className="text-xl font-bold text-text-1 m-0 tracking-tight">Upload Policy</h2>
              <button onClick={() => !isUploading && setIsModalOpen(false)} className="text-faint hover:text-text-1 transition-colors">
                <X className="w-6 h-6" />
              </button>
            </div>
            
            <form onSubmit={handleUpload} className="p-8">
              <div className="mb-6">
                <label className="block text-[12px] font-bold text-text-2 uppercase tracking-widest mb-2">Policy Title (Optional)</label>
                <input 
                  type="text" 
                  value={uploadTitle}
                  onChange={e => setUploadTitle(e.target.value)}
                  placeholder="e.g. Acme Corp Privacy Policy"
                  className="w-full px-4 py-3 bg-surface-2 border border-border rounded-xl text-[14px] text-text-1 focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/20 transition-all"
                  disabled={isUploading}
                />
              </div>

              <div className="mb-8">
                <label className="block text-[12px] font-bold text-text-2 uppercase tracking-widest mb-2">Document File</label>
                <div 
                  className={`border-2 border-dashed rounded-2xl p-8 text-center transition-all cursor-pointer ${uploadFile ? 'border-accent bg-accent/5' : 'border-border hover:border-accent/50 hover:bg-surface-2'}`}
                  onClick={() => !isUploading && fileInputRef.current?.click()}
                >
                  <input 
                    type="file" 
                    className="hidden" 
                    ref={fileInputRef} 
                    onChange={e => setUploadFile(e.target.files?.[0] || null)}
                    accept=".pdf,.txt,.md,.docx"
                    disabled={isUploading}
                  />
                  {uploadFile ? (
                    <div className="flex flex-col items-center">
                      <div className="w-12 h-12 bg-accent/10 rounded-full flex items-center justify-center mb-3">
                        <CheckCircle2 className="w-6 h-6 text-accent" />
                      </div>
                      <span className="text-[14px] font-bold text-text-1">{uploadFile.name}</span>
                      <span className="text-[12px] text-muted mt-1">{(uploadFile.size / 1024 / 1024).toFixed(2)} MB</span>
                    </div>
                  ) : (
                    <div className="flex flex-col items-center">
                      <div className="w-12 h-12 bg-surface border border-border rounded-full flex items-center justify-center mb-3 shadow-sm">
                        <UploadCloud className="w-6 h-6 text-muted" />
                      </div>
                      <span className="text-[14px] font-bold text-text-1">Click to browse file</span>
                      <span className="text-[12px] text-muted mt-1">PDF, TXT, MD, DOCX up to 10MB</span>
                    </div>
                  )}
                </div>
              </div>

              <div className="flex justify-end gap-3">
                <button 
                  type="button" 
                  onClick={() => setIsModalOpen(false)}
                  className="px-6 py-3 rounded-xl text-[14px] font-bold text-text-2 hover:bg-surface-2 transition-all"
                  disabled={isUploading}
                >
                  Cancel
                </button>
                <button 
                  type="submit" 
                  disabled={!uploadFile || isUploading}
                  className="px-6 py-3 rounded-xl text-[14px] font-bold bg-text-1 text-surface hover:bg-text-2 transition-all shadow-sm active:scale-95 disabled:opacity-50 flex items-center gap-2"
                >
                  {isUploading ? (
                    <>
                      <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" className="opacity-25"/><path fill="currentColor" className="opacity-75" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"/></svg>
                      Uploading...
                    </>
                  ) : "Upload & Index"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
