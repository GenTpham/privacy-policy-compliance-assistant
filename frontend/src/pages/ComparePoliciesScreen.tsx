import { useState } from "react";
import { POLICIES, COMPARE_TOPICS, COMPARE_RESULTS } from "@/lib/mockData";

export function ComparePoliciesScreen() {
  const [policyA, setPolicyA] = useState("Google Privacy Policy");
  const [policyB, setPolicyB] = useState("OpenAI Privacy Policy");
  const [topic, setTopic] = useState("Data Retention");
  const [compared, setCompared] = useState(true);
  const [loading, setLoading] = useState(false);

  const indexedPolicies = POLICIES.filter((p) => p.status === "indexed").map((p) => p.name);
  const result = COMPARE_RESULTS[topic] ?? COMPARE_RESULTS["Data Retention"];

  const runCompare = () => {
    setLoading(true);
    setCompared(false);
    setTimeout(() => { setCompared(true); setLoading(false); }, 900);
  };

  const shortName = (n: string) => n.replace(" Privacy Policy", "").replace(" Privacy Statement", "");

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Controls */}
      <div className="px-8 py-6 border-b border-border bg-surface shrink-0 shadow-sm z-10">
        <h1 className="text-2xl font-bold text-text-1 tracking-tight mb-5">Compare Policies</h1>
        <div className="flex gap-4 items-end">
          <div className="flex-1 max-w-[280px]">
            <label className="block text-[11px] font-bold text-muted uppercase tracking-wider mb-2">Policy A</label>
            <select 
              value={policyA} 
              onChange={(e) => setPolicyA(e.target.value)} 
              className="w-full px-3.5 py-2.5 text-[13px] border border-border rounded-lg bg-surface-2 text-text-1 outline-none font-sans focus:border-accent focus:ring-2 focus:ring-accent/20 transition-all shadow-sm cursor-pointer appearance-none"
            >
              {indexedPolicies.map((p) => <option key={p}>{p}</option>)}
            </select>
          </div>
          <div className="text-xl text-faint pb-2.5 px-2">⇔</div>
          <div className="flex-1 max-w-[280px]">
            <label className="block text-[11px] font-bold text-muted uppercase tracking-wider mb-2">Policy B</label>
            <select 
              value={policyB} 
              onChange={(e) => setPolicyB(e.target.value)} 
              className="w-full px-3.5 py-2.5 text-[13px] border border-border rounded-lg bg-surface-2 text-text-1 outline-none font-sans focus:border-accent focus:ring-2 focus:ring-accent/20 transition-all shadow-sm cursor-pointer appearance-none"
            >
              {indexedPolicies.map((p) => <option key={p}>{p}</option>)}
            </select>
          </div>
          <div className="flex-1 max-w-[220px]">
            <label className="block text-[11px] font-bold text-muted uppercase tracking-wider mb-2">Topic</label>
            <select 
              value={topic} 
              onChange={(e) => setTopic(e.target.value)} 
              className="w-full px-3.5 py-2.5 text-[13px] border border-border rounded-lg bg-surface-2 text-text-1 outline-none font-sans focus:border-accent focus:ring-2 focus:ring-accent/20 transition-all shadow-sm cursor-pointer appearance-none"
            >
              {COMPARE_TOPICS.map((tp) => <option key={tp}>{tp}</option>)}
            </select>
          </div>
          <button
            onClick={runCompare}
            className="px-6 py-2.5 bg-accent text-white border-none rounded-lg text-[13px] font-semibold cursor-pointer hover:bg-accent/90 active:scale-95 transition-all shadow-sm h-[42px]"
          >
            Compare
          </button>
        </div>
      </div>

      {/* Results */}
      <div className="flex-1 overflow-y-auto px-8 py-8 bg-background">
        {loading && (
          <div className="text-center py-20 text-[13px] text-faint font-medium animate-pulse">
            Comparing policies…
          </div>
        )}
        {compared && !loading && (
          <div className="max-w-[1200px] mx-auto">
            {/* Side-by-side summaries */}
            <div className="grid grid-cols-2 gap-6 mb-8">
              {[
                { label: shortName(policyA), data: result.policyA, isA: true },
                { label: shortName(policyB), data: result.policyB, isA: false },
              ].map((col, i) => (
                <div key={i} className="bg-surface border border-border rounded-[2rem] overflow-hidden shadow-[var(--shadow-diffusion)] transition-shadow">
                  <div className={`px-5 py-3.5 ${i === 0 ? "bg-user-bubble text-user-bubble-text" : "bg-accent text-white"}`}>
                    <span className="text-[14px] font-bold tracking-tight">{col.label}</span>
                    <span className="text-[12px] opacity-80 ml-2 font-medium">· {topic}</span>
                  </div>
                  <div className="p-6">
                    <p className="text-[13.5px] text-text-2 leading-relaxed m-0 mb-5">{col.data.summary}</p>
                    <div className="text-[11px] font-bold text-faint uppercase tracking-wider mb-3">Sources</div>
                    <div className="flex flex-col gap-2">
                      {col.data.citations.map((c, j) => (
                        <div key={j} className="text-[12px] text-accent font-medium px-3 py-2 bg-accent/10 rounded-md inline-flex items-start gap-2 hover:bg-accent/15 transition-colors cursor-pointer w-fit">
                          <span className="mt-0.5">↗</span> 
                          <span>{c}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Key Differences */}
            <div className="bg-surface border border-border rounded-[2rem] overflow-hidden shadow-[var(--shadow-diffusion)]">
              <div className="px-6 py-5 border-b border-border-2 flex items-center gap-3 bg-surface-2/50">
                <span className="text-[14px] font-bold text-text-1 tracking-tight">Key Differences</span>
                <span className="text-[11px] px-2.5 py-1 bg-amber-100 dark:bg-amber-900/30 text-amber-800 dark:text-amber-500 rounded-md font-bold tracking-wide">
                  {result.differences.length} identified
                </span>
              </div>
              <div className="divide-y divide-border-2">
                {result.differences.map((d, i) => (
                  <div key={i} className="p-5 flex gap-4 hover:bg-surface-2/30 transition-colors">
                    <span className="text-[14px] text-amber-500 font-bold mt-0.5 shrink-0">△</span>
                    <p className="text-[13.5px] text-text-3 leading-relaxed m-0">{d}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
