import { memo } from "react";

interface ChatSidebarProps {
  sources: string[];
  sourcesLoading: boolean;
  sourcesError: string | null;
  activeFilter: string;
  onFilterChange: (filter: string) => void;
  topicFilter: string;
  onTopicChange: (topic: string) => void;
}

const ALL_TOPICS = [
  "All Topics",
  "Data Collection",
  "Third-Party Sharing",
  "Data Retention",
  "User Rights",
  "Cookies"
];

export const ChatSidebar = memo(function ChatSidebar({
  sources,
  sourcesLoading,
  sourcesError,
  activeFilter,
  onFilterChange,
  topicFilter,
  onTopicChange
}: ChatSidebarProps) {
  return (
    <aside className="w-[220px] border-r border-border bg-surface-2 flex flex-col shrink-0" aria-label="Chat filters">
      <div className="px-4 pt-5 pb-3 border-b border-border-2">
        <h2 className="text-[11px] font-semibold text-faint tracking-wider uppercase mb-3" id="policy-source-heading">
          Policy Source
        </h2>
        
        {sourcesLoading ? (
          <div aria-busy="true" aria-labelledby="policy-source-heading">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-8 rounded-md bg-border mb-1 animate-pulse" />
            ))}
          </div>
        ) : sourcesError ? (
          <div role="alert" className="text-xs text-faint">
            {sourcesError}
          </div>
        ) : (
          <nav aria-labelledby="policy-source-heading" className="space-y-0.5">
            {sources.length === 0 ? (
              <div className="text-xs text-faint px-2">No policies indexed.</div>
            ) : (
              ["All Sources", ...sources].map((name) => {
                const isActive = activeFilter === name;
                return (
                  <button
                    key={name}
                    onClick={() => onFilterChange(name)}
                    title={name}
                    aria-current={isActive ? "page" : undefined}
                    className={`block w-full text-left px-3 py-2 rounded-md text-[13px] border-none cursor-pointer transition-colors ${
                      isActive 
                        ? "bg-accent/15 text-accent font-semibold" 
                        : "bg-transparent text-text-3 font-medium hover:bg-surface hover:text-text-2"
                    }`}
                  >
                    {name === "All Sources"
                      ? name
                      : name.replace(" Privacy Policy", "").replace(" Privacy Statement", "")}
                  </button>
                );
              })
            )}
          </nav>
        )}
      </div>
      
      <div className="px-4 pt-4 pb-3">
        <h2 className="text-[11px] font-semibold text-faint tracking-wider uppercase mb-3" id="topic-filter-heading">
          Topic Filter
        </h2>
        <nav aria-labelledby="topic-filter-heading" className="space-y-0.5">
          {ALL_TOPICS.map((tp) => (
            <button
              key={tp}
              onClick={() => onTopicChange(tp)}
              disabled
              aria-disabled="true"
              className="block w-full text-left px-3 py-2 rounded-md text-[13px] border-none bg-transparent text-faint font-medium opacity-50 cursor-not-allowed"
            >
              {tp}
            </button>
          ))}
        </nav>
      </div>
    </aside>
  );
});
