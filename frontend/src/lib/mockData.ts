export interface Policy {
  id: number;
  name: string;
  vendor: string;
  effectiveDate: string;
  chunks: number;
  status: "indexed" | "processing" | "failed";
  tags: string[];
  version: string;
}

export const POLICIES: Policy[] = [
  { id: 1, name: "Google Privacy Policy",        vendor: "Google LLC",             effectiveDate: "2024-01-05", chunks: 312, status: "indexed",    tags: ["data-collection","third-party","cookies"],        version: "v14.2" },
  { id: 2, name: "OpenAI Privacy Policy",         vendor: "OpenAI Inc.",            effectiveDate: "2024-03-15", chunks: 198, status: "indexed",    tags: ["AI-training","user-rights","retention"],          version: "v3.1" },
  { id: 3, name: "Meta Platforms Privacy Policy", vendor: "Meta Platforms Inc.",    effectiveDate: "2023-12-04", chunks: 445, status: "indexed",    tags: ["third-party","cookies","advertising"],            version: "v9.0" },
  { id: 4, name: "Microsoft Privacy Statement",   vendor: "Microsoft Corp.",        effectiveDate: "2024-02-20", chunks: 520, status: "indexed",    tags: ["data-collection","user-rights","retention"],      version: "v12.0" },
  { id: 5, name: "Shopify Privacy Policy",        vendor: "Shopify Inc.",           effectiveDate: "2023-11-01", chunks: 176, status: "indexed",    tags: ["e-commerce","cookies","third-party"],             version: "v6.4" },
  { id: 6, name: "Stripe Privacy Policy",         vendor: "Stripe Inc.",            effectiveDate: "2024-01-22", chunks: 203, status: "processing", tags: ["payments","data-collection","retention"],         version: "v5.1" },
  { id: 7, name: "Notion Privacy Policy",         vendor: "Notion Labs Inc.",       effectiveDate: "2023-09-10", chunks: 141, status: "indexed",    tags: ["SaaS","user-rights","cookies"],                   version: "v2.3" },
  { id: 8, name: "Zoom Privacy Statement",        vendor: "Zoom Video Comm.",       effectiveDate: "2024-04-01", chunks:  88, status: "failed",     tags: ["video","data-collection"],                        version: "v7.0" },
];

export interface AuditEntry {
  id: string;
  timestamp: string;
  query: string;
  policies: string[];
  chunksRetrieved: number;
  status: "answered" | "insufficient";
  confidence: number;
  user: string;
  feedback: "helpful" | "not-helpful" | null;
}

export const AUDIT_ENTRIES: AuditEntry[] = [
  { id: "a001", timestamp: "2026-04-22 09:16:38", query: "What are the user data deletion rights under this policy?",               policies: ["Google Privacy Policy"],                              chunksRetrieved: 4, status: "answered",     confidence: 0.88, user: "analyst@firm.io",    feedback: "helpful" },
  { id: "a002", timestamp: "2026-04-22 09:14:02", query: "Does Google's policy allow sharing user data with third parties?",         policies: ["Google Privacy Policy"],                              chunksRetrieved: 6, status: "answered",     confidence: 0.91, user: "analyst@firm.io",    feedback: "helpful" },
  { id: "a003", timestamp: "2026-04-22 08:55:10", query: "How long does Meta retain user data after account deletion?",              policies: ["Meta Platforms Privacy Policy"],                      chunksRetrieved: 3, status: "answered",     confidence: 0.74, user: "compliance@firm.io", feedback: null },
  { id: "a004", timestamp: "2026-04-22 08:44:20", query: "Does Zoom comply with GDPR data residency requirements?",                  policies: ["Zoom Privacy Statement"],                             chunksRetrieved: 0, status: "insufficient", confidence: 0.12, user: "compliance@firm.io", feedback: "not-helpful" },
  { id: "a005", timestamp: "2026-04-22 08:30:01", query: "What cookies does Shopify use for tracking?",                              policies: ["Shopify Privacy Policy"],                             chunksRetrieved: 5, status: "answered",     confidence: 0.82, user: "analyst@firm.io",    feedback: null },
  { id: "a006", timestamp: "2026-04-21 17:02:44", query: "Compare data retention policies between Microsoft and OpenAI",             policies: ["Microsoft Privacy Statement","OpenAI Privacy Policy"], chunksRetrieved: 8, status: "answered",     confidence: 0.79, user: "analyst@firm.io",    feedback: "helpful" },
  { id: "a007", timestamp: "2026-04-21 16:48:11", query: "Does OpenAI use conversation data for model training?",                    policies: ["OpenAI Privacy Policy"],                              chunksRetrieved: 5, status: "answered",     confidence: 0.95, user: "legal@firm.io",      feedback: "helpful" },
  { id: "a008", timestamp: "2026-04-21 15:30:00", query: "What user rights exist under Notion's privacy policy?",                   policies: ["Notion Privacy Policy"],                              chunksRetrieved: 4, status: "answered",     confidence: 0.83, user: "legal@firm.io",      feedback: null },
];

export const COMPARE_TOPICS = ["Data Collection","Third-Party Sharing","Data Retention","User Rights","Cookies & Tracking","Security Measures"];

export interface CompareResult {
  policyA: { summary: string; citations: string[] };
  policyB: { summary: string; citations: string[] };
  differences: string[];
}

export const COMPARE_RESULTS: Record<string, CompareResult> = {
  "Data Retention": {
    policyA: {
      summary: "Google retains data for varying periods depending on the type. Account data is retained as long as the account is active. Activity data can be set to auto-delete after 3, 18, or 36 months. Some logs are retained for a minimum of 9 months.",
      citations: ["Section 7 – Retaining your information","My Activity auto-delete settings"],
    },
    policyB: {
      summary: "OpenAI retains personal data for as long as necessary to provide services or as required by law. Conversation data may be retained for up to 30 days for abuse monitoring, unless the user opts out. Training data retention policies vary by product.",
      citations: ["Section 4 – Data Retention","API Data Usage Policy"],
    },
    differences: [
      "Google provides granular user-controlled auto-delete settings (3/18/36 months); OpenAI does not offer equivalent user controls.",
      "OpenAI explicitly mentions a 30-day abuse monitoring window; Google does not specify such a period.",
      "Google retains some logs a minimum of 9 months regardless of user settings.",
    ],
  },
  "Third-Party Sharing": {
    policyA: {
      summary: "Google shares data with affiliates, service providers, advertisers, and business partners. Data shared with advertisers is typically aggregated or anonymized. Direct sharing with third parties requires user consent or legal basis.",
      citations: ["Section 3 – Sharing your information"],
    },
    policyB: {
      summary: "OpenAI may share data with vendors and service providers necessary to operate the service. OpenAI does not sell personal data. Data may be shared with business partners and for legal compliance.",
      citations: ["Section 5 – Disclosure of Personal Information"],
    },
    differences: [
      "Google maintains active advertising partnerships involving user data; OpenAI explicitly states it does not sell personal data.",
      "Google has a broader network of third-party sharing for advertising; OpenAI limits sharing to operational service providers.",
    ],
  },
};

export const SUGGESTED_PROMPTS = [
  "Does this policy allow third-party data sharing?",
  "What are the user deletion rights?",
  "How long is personal data retained?",
  "What cookies and trackers are used?",
  "Is this policy GDPR compliant?",
];

export const KPI = {
  totalPolicies: 8,
  indexedChunks: 2083,
  queriesToday: 24,
  citationCoverage: "87%",
  insufficientRate: "9%",
};

export const RECENT_ACTIVITY = [
  { time: "09:16", query: "User deletion rights — Google",       status: "answered"     },
  { time: "09:14", query: "Third-party sharing — Google",         status: "answered"     },
  { time: "08:55", query: "Data retention after deletion — Meta", status: "answered"     },
  { time: "08:44", query: "GDPR compliance — Zoom",              status: "insufficient" },
  { time: "08:30", query: "Cookie tracking — Shopify",           status: "answered"     },
];

export const TOP_TOPICS = [
  { topic: "Data Retention",     count: 38 },
  { topic: "Third-Party Sharing",count: 31 },
  { topic: "User Rights",        count: 27 },
  { topic: "Cookies & Tracking", count: 22 },
  { topic: "Security",           count: 15 },
];

export const POLICY_SECTIONS = [
  "1. Introduction",
  "2. Information We Collect",
  "3. How We Use Information",
  "4. Information Sharing",
  "5. Data Retention",
  "6. Your Privacy Controls",
  "7. About This Policy",
];
