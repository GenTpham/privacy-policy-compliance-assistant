import { useState, useEffect } from "react";
import { Badge } from "@/components/ui/Badge";
import { fetchWithAuth } from "@/lib/api";
import { UploadCloud, FileText } from "lucide-react";
import { PolicyUploadModal } from "@/components/ui/PolicyUploadModal";
import { PolicyDetailDrawer } from "@/components/ui/PolicyDetailDrawer";

export interface Document {
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
      <main className="flex-1 flex flex-col overflow-hidden bg-background">
        {/* Header */}
        <header className="px-10 py-8 border-b border-border bg-surface flex justify-between items-center z-10 shadow-sm animate-stagger" style={{ "--idx": 0 } as React.CSSProperties}>
          <div>
            <h1 className="text-3xl font-bold text-text-1 tracking-tighter m-0">Policy Library</h1>
            <p className="text-[14px] text-muted font-medium mt-1">
              {documents.length} documents · {documents.filter((p) => p.status === "success").length} indexed
            </p>
          </div>
          <div className="flex gap-4">
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search documents…"
              aria-label="Search documents"
              className="px-4 py-2.5 text-[14px] border border-border rounded-xl outline-none w-[260px] bg-surface-2 text-text-1 focus:border-accent focus:ring-2 focus:ring-accent/20 transition-all placeholder:text-faint"
            />
            <button 
              onClick={() => setIsModalOpen(true)}
              className="bg-text-1 text-surface border-none rounded-xl px-5 py-2.5 text-[14px] font-bold cursor-pointer hover:bg-text-2 transition-all shadow-sm active:scale-95 flex items-center gap-2"
              aria-label="Upload Policy"
            >
              <UploadCloud className="w-4 h-4" />
              Upload Policy
            </button>
          </div>
        </header>

        {/* Table */}
        <div className="flex-1 overflow-y-auto px-10 py-6" role="region" aria-label="Document list">
          <div className="bg-surface border border-border rounded-[2rem] overflow-hidden shadow-[var(--shadow-diffusion)] animate-stagger" style={{ "--idx": 1 } as React.CSSProperties}>
            <table className="w-full border-collapse">
              <thead className="bg-surface-2/50 border-b border-border">
                <tr>
                  {["Document Title", "Status", "Uploaded On", "File ID"].map((h) => (
                    <th key={h} className="px-8 py-5 text-left text-[12px] font-bold text-text-2 tracking-widest uppercase whitespace-nowrap" scope="col">
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
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          setSelected(p);
                        }
                      }}
                      tabIndex={0}
                      aria-selected={isSelected}
                      role="button"
                      className={`border-b border-border-2 cursor-pointer transition-colors animate-stagger outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent/50 ${
                        isSelected 
                          ? "bg-accent/5 hover:bg-accent/10" 
                          : "hover:bg-surface-2/50 bg-surface"
                      }`}
                      style={{ "--idx": idx + 2 } as React.CSSProperties}
                    >
                      <td className="px-8 py-5">
                        <div className="text-[15px] font-semibold text-text-1 mb-1 flex items-center gap-2">
                          <FileText className="w-4 h-4 text-text-3" aria-hidden="true" />
                          {p.title}
                        </div>
                      </td>
                      <td className="px-8 py-5">
                        <Badge status={p.status} />
                      </td>
                      <td className="px-8 py-5 text-[14px] text-text-2 font-mono">{new Date(p.created_at).toLocaleDateString()}</td>
                      <td className="px-8 py-5 text-[13px] text-text-3 font-mono">#{p.id}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {filtered.length === 0 && (
              <div className="text-center py-24" role="status">
                <div className="text-faint flex justify-center mb-4" aria-hidden="true">
                  <FileText className="w-12 h-12" strokeWidth={1} />
                </div>
                <div className="text-[16px] text-text-1 font-bold mb-1">No documents found</div>
                <div className="text-[14px] text-muted font-medium">Upload a document to get started.</div>
              </div>
            )}
          </div>
        </div>
      </main>

      <PolicyDetailDrawer 
        selected={selected} 
        onClose={() => setSelected(null)} 
        onAsk={onAsk} 
      />

      <PolicyUploadModal
        isOpen={isModalOpen}
        isUploading={isUploading}
        uploadFile={uploadFile}
        uploadTitle={uploadTitle}
        onClose={() => setIsModalOpen(false)}
        onFileSelect={setUploadFile}
        onTitleChange={setUploadTitle}
        onSubmit={handleUpload}
      />
    </div>
  );
}
