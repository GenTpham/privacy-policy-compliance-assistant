import { CheckCircle2, FileText, Loader2, XCircle } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

interface UploadProgressCardProps {
  fileName: string;
  docStatus: string;      // "processing", "ready", "failed"
  currentTask: string;    // "download", "extract", "chunk", "embed", etc.
  jobStatus: string;      // "queued", "running", "completed", "failed"
}

export function UploadProgressCard({ fileName, docStatus, currentTask, jobStatus }: UploadProgressCardProps) {
  // Map internal tasks to user-friendly steps
  const steps = [
    { id: "init", label: "Uploading file" },
    { id: "download", label: "Downloading file" },
    { id: "extract", label: "Extracting text" },
    { id: "validate", label: "Validating text" },
    { id: "chunk", label: "Chunking & formatting" },
    { id: "embed_and_graph", label: "Embedding & Knowledge Graph generation" },
    { id: "ready", label: "Ready for questions" },
  ];

  // Determine current step index
  let activeIndex = 0;
  if (docStatus === "ready") {
    activeIndex = 6;
  } else if (jobStatus === "running") {
    if (currentTask === "download_pdf") activeIndex = 1;
    else if (currentTask === "extract_text") activeIndex = 2;
    else if (currentTask === "validate_text") activeIndex = 3;
    else if (currentTask === "chunk_text") activeIndex = 4;
    else if (
      currentTask === "embed_and_upsert_qdrant" || 
      currentTask === "generate_embeddings" || 
      currentTask === "upsert_qdrant" || 
      currentTask === "build_graph" || 
      currentTask === "upsert_neo4j"
    ) activeIndex = 5;
    else if (currentTask === "finalize") activeIndex = 6;
    else activeIndex = 1; // default if unknown running task
  } else if (jobStatus === "queued") {
    activeIndex = 0;
  }

  const isFailed = docStatus === "failed" || jobStatus === "failed";

  return (
    <div className="bg-surface border border-border rounded-2xl p-5 shadow-[var(--shadow-diffusion)] w-full max-w-md my-4">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-10 h-10 rounded-xl bg-accent/10 flex items-center justify-center border border-accent/20">
          <FileText className="w-5 h-5 text-accent" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[14px] font-bold text-text-1 truncate">{fileName}</div>
          <div className="text-[12px] font-medium text-muted">
            {isFailed ? (
              <span className="text-red-500">Failed to process</span>
            ) : docStatus === "ready" ? (
              <span className="text-green-600">Processing complete</span>
            ) : (
              <span className="text-accent animate-pulse">Processing...</span>
            )}
          </div>
        </div>
      </div>

      <div className="space-y-3 relative">
        {/* Subtle vertical line connecting steps */}
        <div className="absolute left-[11px] top-2 bottom-4 w-[2px] bg-border-2" />

        <AnimatePresence>
          {steps.map((step, idx) => {
            // Don't show future steps if failed
            if (isFailed && idx > activeIndex) return null;

            const isPast = idx < activeIndex || docStatus === "ready";
            const isActive = idx === activeIndex && !isFailed && docStatus !== "ready";
            const isCurrentFail = isFailed && idx === activeIndex;

            // Opacity logic: past steps are dimmed slightly, active is bright
            const opacityClass = isPast ? "opacity-60" : isActive ? "opacity-100" : "opacity-30";

            return (
              <motion.div
                key={step.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: idx * 0.1 }}
                className={`flex items-start gap-3 relative ${opacityClass}`}
              >
                <div className="relative z-10 bg-surface py-1">
                  {isCurrentFail ? (
                    <XCircle className="w-5 h-5 text-red-500 bg-surface rounded-full" />
                  ) : isPast ? (
                    <CheckCircle2 className="w-5 h-5 text-green-500 bg-surface rounded-full" />
                  ) : isActive ? (
                    <Loader2 className="w-5 h-5 text-accent animate-spin bg-surface rounded-full" />
                  ) : (
                    <div className="w-5 h-5 rounded-full border-2 border-border-2 bg-surface" />
                  )}
                </div>
                <div className={`text-[13px] font-medium py-1 ${isActive ? "text-text-1" : "text-text-2"}`}>
                  {step.label}
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </div>
  );
}
