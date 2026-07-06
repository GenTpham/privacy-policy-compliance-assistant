import { memo, useRef } from "react";
import { UploadCloud, X, CheckCircle2 } from "lucide-react";

interface PolicyUploadModalProps {
  isOpen: boolean;
  isUploading: boolean;
  uploadFile: File | null;
  uploadTitle: string;
  onClose: () => void;
  onFileSelect: (file: File | null) => void;
  onTitleChange: (title: string) => void;
  onSubmit: (e: React.FormEvent) => void;
}

export const PolicyUploadModal = memo(function PolicyUploadModal({
  isOpen,
  isUploading,
  uploadFile,
  uploadTitle,
  onClose,
  onFileSelect,
  onTitleChange,
  onSubmit,
}: PolicyUploadModalProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Close on escape key
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape" && !isUploading) {
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="upload-modal-title"
      onKeyDown={handleKeyDown}
    >
      <div 
        className="absolute inset-0 bg-background/60 backdrop-blur-md" 
        onClick={() => !isUploading && onClose()}
        aria-hidden="true"
      />
      <div className="relative w-full max-w-lg bg-surface border border-border rounded-[2.5rem] shadow-[var(--shadow-diffusion)] overflow-hidden animate-stagger">
        <header className="px-8 py-6 border-b border-border bg-surface-2/30 flex justify-between items-center">
          <h2 id="upload-modal-title" className="text-xl font-bold text-text-1 m-0 tracking-tight">Upload Policy</h2>
          <button 
            onClick={() => !isUploading && onClose()} 
            className="text-faint hover:text-text-1 transition-colors bg-transparent border-none cursor-pointer"
            aria-label="Close modal"
          >
            <X className="w-6 h-6" />
          </button>
        </header>
        
        <form onSubmit={onSubmit} className="p-8">
          <div className="mb-6">
            <label htmlFor="policy-title" className="block text-[12px] font-bold text-text-2 uppercase tracking-widest mb-2">
              Policy Title (Optional)
            </label>
            <input 
              id="policy-title"
              type="text" 
              value={uploadTitle}
              onChange={e => onTitleChange(e.target.value)}
              placeholder="e.g. Acme Corp Privacy Policy"
              className="w-full px-4 py-3 bg-surface-2 border border-border rounded-xl text-[14px] text-text-1 focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/20 transition-all"
              disabled={isUploading}
            />
          </div>

          <div className="mb-8">
            <label className="block text-[12px] font-bold text-text-2 uppercase tracking-widest mb-2" id="file-upload-label">
              Document File
            </label>
            <div 
              className={`border-2 border-dashed rounded-2xl p-8 text-center transition-all cursor-pointer ${uploadFile ? 'border-accent bg-accent/5' : 'border-border hover:border-accent/50 hover:bg-surface-2'}`}
              onClick={() => !isUploading && fileInputRef.current?.click()}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  if (!isUploading) fileInputRef.current?.click();
                }
              }}
              role="button"
              tabIndex={0}
              aria-labelledby="file-upload-label"
              aria-describedby="file-upload-desc"
            >
              <input 
                type="file" 
                className="hidden" 
                ref={fileInputRef} 
                onChange={e => onFileSelect(e.target.files?.[0] || null)}
                accept=".pdf,.txt,.md,.docx"
                disabled={isUploading}
                tabIndex={-1}
              />
              {uploadFile ? (
                <div className="flex flex-col items-center">
                  <div className="w-12 h-12 bg-accent/10 rounded-full flex items-center justify-center mb-3">
                    <CheckCircle2 className="w-6 h-6 text-accent" />
                  </div>
                  <span className="text-[14px] font-bold text-text-1">{uploadFile.name}</span>
                  <span className="text-[12px] text-muted mt-1" id="file-upload-desc">
                    {(uploadFile.size / 1024 / 1024).toFixed(2)} MB
                  </span>
                </div>
              ) : (
                <div className="flex flex-col items-center">
                  <div className="w-12 h-12 bg-surface border border-border rounded-full flex items-center justify-center mb-3 shadow-sm">
                    <UploadCloud className="w-6 h-6 text-muted" />
                  </div>
                  <span className="text-[14px] font-bold text-text-1">Click to browse file</span>
                  <span className="text-[12px] text-muted mt-1" id="file-upload-desc">
                    PDF, TXT, MD, DOCX up to 10MB
                  </span>
                </div>
              )}
            </div>
          </div>

          <div className="flex justify-end gap-3">
            <button 
              type="button" 
              onClick={() => onClose()}
              className="px-6 py-3 rounded-xl text-[14px] font-bold text-text-2 hover:bg-surface-2 bg-transparent border-none cursor-pointer transition-all"
              disabled={isUploading}
            >
              Cancel
            </button>
            <button 
              type="submit" 
              disabled={!uploadFile || isUploading}
              className="px-6 py-3 rounded-xl text-[14px] font-bold bg-text-1 text-surface border-none cursor-pointer hover:bg-text-2 transition-all shadow-sm active:scale-95 disabled:opacity-50 flex items-center gap-2"
            >
              {isUploading ? (
                <>
                  <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                    <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" className="opacity-25" />
                    <path fill="currentColor" className="opacity-75" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Uploading...
                </>
              ) : "Upload & Index"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
});
