import { CheckCircle2, FileText, Loader2, Sparkles, TerminalSquare, XCircle } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useEffect, useState } from "react";

interface UploadProgressCardProps {
  fileName: string;
  docStatus: string;      // "processing", "ready", "failed"
  currentTask: string;    // "download", "extract", "chunk", "embed", etc.
  jobStatus: string;      // "queued", "running", "completed", "failed"
}

// ----------------------------------------------------------------------
// Sub-task simulator to give the "AI Agent thinking" vibe
// ----------------------------------------------------------------------
const SUB_TASKS: Record<string, string[]> = {
  download: ["> Connecting to blob storage...", "> Fetching PDF bytes...", "> Verifying checksum..."],
  extract: ["> Initializing parsing engine...", "> Analyzing document layout...", "> Extracting textual nodes..."],
  validate: ["> Checking text integrity...", "> Scanning for anomalies...", "> Normalizing whitespace..."],
  chunk: ["> Initializing semantic splitter...", "> Analyzing token density...", "> Formatting chunk metadata..."],
  embed_and_graph: [
    "> Loading embedding model (Nemotron)...", 
    "> Generating dense vectors...", 
    "> Connecting to OpenRouter LLM...", 
    "> Extracting entities & relationships...", 
    "> Upserting vectors to Qdrant...", 
    "> Syncing knowledge graph to Neo4j..."
  ],
};

function SimulatedTerminal({ taskKey }: { taskKey: string }) {
  const tasks = SUB_TASKS[taskKey] || ["> Processing data stream..."];
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setIndex((prev) => (prev + 1) % tasks.length);
    }, 2500); // cycle every 2.5s
    return () => clearInterval(interval);
  }, [tasks.length]);

  return (
    <motion.div 
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: "auto" }}
      exit={{ opacity: 0, height: 0 }}
      className="mt-2 mb-1 overflow-hidden rounded-lg bg-surface-2 border border-border-2/50"
    >
      <div className="px-3 py-2 flex items-center gap-2">
        <TerminalSquare className="w-3.5 h-3.5 text-muted shrink-0" />
        <AnimatePresence mode="wait">
          <motion.div
            key={index}
            initial={{ opacity: 0, x: 5 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -5 }}
            transition={{ duration: 0.2 }}
            className="text-[12px] font-mono text-text-2 truncate"
          >
            {tasks[index]}
          </motion.div>
        </AnimatePresence>
      </div>
    </motion.div>
  );
}

// ----------------------------------------------------------------------
// Main Component
// ----------------------------------------------------------------------
export function UploadProgressCard({ fileName, docStatus, currentTask, jobStatus }: UploadProgressCardProps) {
  const steps = [
    { id: "init", taskKey: "init", label: "Initializing task" },
    { id: "download", taskKey: "download", label: "Downloading artifact" },
    { id: "extract", taskKey: "extract", label: "Parsing document structure" },
    { id: "validate", taskKey: "validate", label: "Validating integrity" },
    { id: "chunk", taskKey: "chunk", label: "Semantic chunking" },
    { id: "embed_and_graph", taskKey: "embed_and_graph", label: "AI Knowledge Synthesis" },
    { id: "ready", taskKey: "ready", label: "Agent Ready" },
  ];

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
    else activeIndex = 1; 
  } else if (jobStatus === "queued") {
    activeIndex = 0;
  }

  const isFailed = docStatus === "failed" || jobStatus === "failed";
  const visibleSteps = steps.filter((_, idx) => idx <= activeIndex);

  return (
    <div className="w-full max-w-md my-6 relative group">
      {/* Animated Rotating Glow Border (Only when running) */}
      {jobStatus === "running" && !isFailed && docStatus !== "ready" && (
        <div className="absolute -inset-[1px] rounded-[24px] overflow-hidden opacity-50 z-0">
          <motion.div 
            animate={{ rotate: 360 }}
            transition={{ repeat: Infinity, duration: 4, ease: "linear" }}
            className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[150%] h-[150%] bg-[conic-gradient(from_0deg,transparent_0_340deg,var(--accent)_360deg)]"
          />
        </div>
      )}

      {/* Main Glassmorphism Card */}
      <motion.div 
        layout
        className="relative z-10 bg-surface border border-border rounded-[23px] p-5 shadow-[var(--shadow-diffusion)] overflow-hidden"
      >
        {/* Header Section */}
        <motion.div layout className="flex items-start gap-4 mb-5">
          <div className="relative w-12 h-12 rounded-xl bg-surface-2 flex items-center justify-center border border-border-2 shrink-0 overflow-hidden">
            {/* Shimmer effect inside icon box */}
            {(jobStatus === "running" && docStatus !== "ready") && (
              <motion.div 
                animate={{ x: ["-100%", "200%"] }}
                transition={{ repeat: Infinity, duration: 2, ease: "easeInOut" }}
                className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent w-full"
              />
            )}
            {docStatus === "ready" ? (
              <Sparkles className="w-6 h-6 text-green-500" />
            ) : (
              <FileText className="w-6 h-6 text-text-2" />
            )}
          </div>
          <div className="flex-1 min-w-0 pt-1">
            <div className="text-[15px] font-bold text-text-1 truncate tracking-tight">{fileName}</div>
            <div className="text-[13px] font-medium mt-0.5">
              {isFailed ? (
                <span className="text-red-500">Task Failed</span>
              ) : docStatus === "ready" ? (
                <span className="text-green-500">Task Completed Successfully</span>
              ) : (
                <span className="text-accent flex items-center gap-2">
                  Agent is working
                  <motion.span 
                    animate={{ opacity: [0, 1, 0] }} 
                    transition={{ repeat: Infinity, duration: 1.5 }}
                  >
                    ...
                  </motion.span>
                </span>
              )}
            </div>
          </div>
        </motion.div>

        {/* Steps Timeline */}
        <motion.div layout className="relative pl-3 mt-4 space-y-0">
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
                  initial={{ opacity: 0, y: -10, scale: 0.95 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  transition={{ type: "spring", stiffness: 100, damping: 20 }}
                  className="relative"
                >
                  {/* Connecting Line */}
                  {!isLastVisible && (
                    <motion.div 
                      layout
                      className="absolute left-[7px] top-[26px] bottom-[-10px] w-[2px] bg-border overflow-hidden" 
                    >
                      {/* Flowing energy through the line if the next step is active */}
                      {idx === activeIndex - 1 && !isFailed && docStatus !== "ready" && (
                        <motion.div 
                          animate={{ y: ["-100%", "200%"] }}
                          transition={{ repeat: Infinity, duration: 1.5, ease: "linear" }}
                          className="w-full h-[50%] bg-accent opacity-50 blur-[1px]"
                        />
                      )}
                    </motion.div>
                  )}
                  
                  <div className="flex items-start gap-4 py-2 relative z-10">
                    <div className="relative py-1 bg-surface">
                      {isCurrentFail ? (
                        <XCircle className="w-[16px] h-[16px] text-red-500 relative z-10" />
                      ) : isPast ? (
                        <CheckCircle2 className="w-[16px] h-[16px] text-text-3 relative z-10" />
                      ) : isActive ? (
                        <div className="relative w-[16px] h-[16px] flex items-center justify-center">
                          {/* Outer spinning dash */}
                          <Loader2 className="absolute inset-0 w-full h-full text-accent animate-spin opacity-40" />
                          {/* Inner pulsing dot */}
                          <div className="w-[6px] h-[6px] bg-accent rounded-full animate-pulse" />
                        </div>
                      ) : (
                        <div className="w-[16px] h-[16px] rounded-full border-2 border-border-2" />
                      )}
                    </div>
                    
                    <div className="flex-1 min-w-0 pb-1">
                      <div className={`text-[13.5px] transition-colors duration-300 ${isActive ? "text-text-1 font-semibold" : "text-text-2 font-medium"}`}>
                        {step.label}
                      </div>
                      
                      {/* Active Step Terminal Simulator */}
                      <AnimatePresence>
                        {isActive && !isFailed && step.taskKey !== "init" && step.taskKey !== "ready" && (
                          <SimulatedTerminal taskKey={step.taskKey} />
                        )}
                      </AnimatePresence>
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </motion.div>
      </motion.div>
    </div>
  );
}
