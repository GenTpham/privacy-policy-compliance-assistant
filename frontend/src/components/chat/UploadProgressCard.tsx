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
  
  // Claude Code Agent Style: Reveal steps sequentially
  const visibleSteps = steps.filter((_, idx) => idx <= activeIndex);

  return (
    <motion.div 
      layout
      className="bg-surface border border-border rounded-2xl p-5 shadow-[var(--shadow-diffusion)] w-full max-w-md my-4"
    >
      <motion.div layout className="flex items-center gap-4 mb-4">
        <div className="w-10 h-10 rounded-xl bg-surface-2 flex items-center justify-center border border-border-2 shrink-0">
          <FileText className="w-5 h-5 text-text-2" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[14px] font-bold text-text-1 truncate tracking-tight">{fileName}</div>
          <div className="text-[12px] font-medium mt-0.5">
            {isFailed ? (
              <span className="text-red-500">Failed to process</span>
            ) : docStatus === "ready" ? (
              <span className="text-green-500">Processing complete</span>
            ) : (
              <span className="text-accent flex items-center gap-1.5">
                <span className="relative flex h-1.5 w-1.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-accent"></span>
                </span>
                Processing...
              </span>
            )}
          </div>
        </div>
      </motion.div>

      <motion.div layout className="space-y-0 relative pl-2 mt-2">
        <AnimatePresence initial={false}>
          {visibleSteps.map((step, idx) => {
            const isPast = idx < activeIndex || docStatus === "ready";
            const isActive = idx === activeIndex && !isFailed && docStatus !== "ready";
            const isCurrentFail = isFailed && idx === activeIndex;
            const isLastVisible = idx === visibleSteps.length - 1;

            return (
              <motion.div
                key={step.id}
                layout
                initial={{ opacity: 0, y: -10, filter: "blur(4px)" }}
                animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
                transition={{ type: "spring", stiffness: 100, damping: 20 }}
                className="relative"
              >
                {!isLastVisible && (
                  <motion.div 
                    layout
                    className="absolute left-[9px] top-6 bottom-[-6px] w-[2px] bg-border-2 opacity-50" 
                  />
                )}
                
                <div className="flex items-start gap-4 py-1.5 relative z-10">
                  <div className="relative bg-surface py-0.5">
                    {isCurrentFail ? (
                      <XCircle className="w-5 h-5 text-red-500" />
                    ) : isPast ? (
                      <CheckCircle2 className="w-5 h-5 text-green-500" />
                    ) : isActive ? (
                      <Loader2 className="w-5 h-5 text-accent animate-spin" />
                    ) : (
                      <div className="w-5 h-5 rounded-full border-2 border-border-2" />
                    )}
                  </div>
                  <div className={`text-[13px] py-0.5 transition-colors duration-300 ${isActive ? "text-text-1 font-semibold" : "text-text-2 font-medium"}`}>
                    {step.label}
                  </div>
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </motion.div>
    </motion.div>
  );
}
