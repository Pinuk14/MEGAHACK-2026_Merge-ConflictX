import { useState, useEffect, useRef, useCallback } from "react";

// ─── API CONFIGURATION ────────────────────────────────────────────────────────
const API_BASE = "http://localhost:8000";

// ─── DESIGN TOKENS (from reference HTML) ─────────────────────────────────────
const C = {
  primary: "#ec5b13",
  yellow: "#facc15",
  cyan: "#22d3ee",
  bg: "#0a0a0a",
  card: "#18181b", // zinc-900
  cardDark: "#000000",
  grid: "#262626",
  text: "#f1f5f9",
  muted: "#dbeafe",
  green: "#22c55e",
  red: "#ef4444",
};

// ─── PIPELINE DATA ────────────────────────────────────────────────────────────
const STEPS = [
  {
    id: "ingest",
    label: "Document Ingestion",
    short: "INGEST",
    sector: "S1",
    color: C.primary,
    desc: "Parsing raw input, detecting encoding, stripping layout noise and rendering artifacts.",
    duration: 4000,
    subTasks: [
      { label: "Reading file buffer", pct: 0.08 },
      { label: "Detecting MIME type", pct: 0.06 },
      { label: "UTF-8 normalization", pct: 0.12 },
      { label: "Stripping PDF metadata", pct: 0.14 },
      { label: "Extracting text layers", pct: 0.28 },
      { label: "Removing headers/footers", pct: 0.16 },
      { label: "Noise artifact sweep", pct: 0.16 },
    ],
    metrics: [
      { key: "File Type", val: "PDF/A-1b" },
      { key: "Encoding", val: "UTF-8" },
      { key: "Pages", val: "48" },
      { key: "Raw Tokens", val: "42,817" },
      { key: "Noise Ratio", val: "3.2%" },
      { key: "Artifacts", val: "1,204" },
    ],
    verdict: {
      flash: "SECTOR COMPLETE",
      badge: "PRIORITY ALPHA",
      title: "CLEAN TOKEN STREAM READY",
      sub: "Raw document fully normalised — 42,817 tokens extracted across 48 pages. 3.2% noise eliminated.",
      alertLabel: "PRIMARY OUTPUT",
      alertText:
        "UTF-8 clean token stream. All layout artifacts, headers and footers removed. Ready for NLP pipeline.",
      actionLabel: "NEXT SECTOR",
      actionText:
        "Semantic tokenization will segment into 1,204 sentence units and resolve named entity co-references.",
      riskIndex: "3.2",
      riskLabel: "NOISE INDEX",
      economicVal: "42.8K",
      economicLabel: "TOKENS EXTRACTED",
      stats: [
        { k: "TOKENS", v: "42,817" },
        { k: "PAGES", v: "48" },
        { k: "NOISE", v: "3.2%" },
        { k: "ARTIFACTS", v: "1,204" },
      ],
      tags: ["UTF-8 Clean", "PDF/A-1b", "48 pages"],
    },
  },
  {
    id: "tokenize",
    label: "Semantic Tokenization",
    short: "TOKENIZE",
    sector: "S1",
    color: C.primary,
    desc: "Segmenting text into semantic units using transformer NLP. Resolving entity co-references.",
    duration: 4500,
    subTasks: [
      { label: "Loading spaCy en_core_web_trf", pct: 0.14 },
      { label: "Sentence boundary detection", pct: 0.18 },
      { label: "Named entity recognition", pct: 0.22 },
      { label: "Co-reference resolution", pct: 0.24 },
      { label: "Dependency parsing", pct: 0.14 },
      { label: "POS tagging", pct: 0.08 },
    ],
    metrics: [
      { key: "Model", val: "en_core_web_trf" },
      { key: "Sentences", val: "1,204" },
      { key: "Entities", val: "347" },
      { key: "Co-ref Chains", val: "89" },
      { key: "Lexical Density", val: "72%" },
      { key: "Avg Sent", val: "18.4 tok" },
    ],
    verdict: {
      flash: "NLP COMPLETE",
      badge: "ENTITIES MAPPED",
      title: "347 NAMED ENTITIES EXTRACTED",
      sub: "1,204 sentences segmented. 89 co-reference chains fully resolved. Dependency trees built.",
      alertLabel: "KEY ENTITIES",
      alertText:
        "EU Health Authority ×12 · Directive 2024/EU-H ×8 · €2.4B ×3 · 90 days ×4 · Commissioner Valdis ×5",
      actionLabel: "CO-REF RESOLVED",
      actionText:
        '89 pronoun chains disambiguated. "they" → healthcare providers, "it" → Directive 2024/EU-H.',
      riskIndex: "72%",
      riskLabel: "LEXICAL DENSITY",
      economicVal: "1,204",
      economicLabel: "SENTENCES MAPPED",
      stats: [
        { k: "SENTENCES", v: "1,204" },
        { k: "ENTITIES", v: "347" },
        { k: "CO-REF", v: "89" },
        { k: "DENSITY", v: "72%" },
      ],
      tags: ["en_core_web_trf", "347 entities", "89 chains"],
    },
  },
  {
    id: "classify",
    label: "Topic Classification",
    short: "CLASSIFY",
    sector: "S2",
    color: C.yellow,
    desc: "Multi-label BERTopic classification across policy, regulatory and domain taxonomies.",
    duration: 4200,
    subTasks: [
      { label: "Building TF-IDF matrix", pct: 0.14 },
      { label: "Running BERTopic model", pct: 0.26 },
      { label: "UMAP dimensionality reduction", pct: 0.2 },
      { label: "HDBSCAN clustering", pct: 0.18 },
      { label: "Coherence scoring", pct: 0.12 },
      { label: "Label assignment", pct: 0.1 },
    ],
    metrics: [
      { key: "Domain", val: "Healthcare" },
      { key: "Topics", val: "7 clusters" },
      { key: "Top Topic", val: "Regulatory" },
      { key: "Confidence", val: "94%" },
      { key: "Coherence", val: "c_v=0.87" },
      { key: "Model", val: "BERTopic" },
    ],
    verdict: {
      flash: "CLASSIFICATION DONE",
      badge: "ECONOMIC ADVANTAGE",
      title: "7 TOPIC CLUSTERS IDENTIFIED",
      sub: "Regulatory compliance dominates at 34%. High coherence score 0.87. Depth-4 taxonomy confirmed.",
      alertLabel: "TOPIC DISTRIBUTION",
      alertText:
        "Regulatory Compliance 34% · Public Health Infra 28% · Funding Allocation 18% · Obligations 12%",
      actionLabel: "DOMAIN CONFIRMED",
      actionText:
        "Primary domain: Healthcare Policy. Confidence 94% — above the 85% quality threshold for deployment.",
      riskIndex: "94%",
      riskLabel: "CONFIDENCE",
      economicVal: "0.87",
      economicLabel: "COHERENCE SCORE",
      stats: [
        { k: "TOPICS", v: "7" },
        { k: "CONFIDENCE", v: "94%" },
        { k: "COHERENCE", v: "0.87" },
        { k: "DEPTH", v: "Lvl 4" },
      ],
      tags: ["BERTopic 0.16", "Healthcare Policy", "7 clusters"],
    },
  },
  {
    id: "segment",
    label: "Semantic Segmentation",
    short: "SEGMENT",
    sector: "S2",
    color: C.yellow,
    desc: "Identifying clause boundaries, logical sections, argumentative structure and critical clauses.",
    duration: 3800,
    subTasks: [
      { label: "Clause boundary detection", pct: 0.18 },
      { label: "Section hierarchy mapping", pct: 0.22 },
      { label: "Argument chain extraction", pct: 0.22 },
      { label: "Rhetoric role labelling", pct: 0.18 },
      { label: "Coherence scoring", pct: 0.2 },
    ],
    metrics: [
      { key: "Sections", val: "23" },
      { key: "Critical Clauses", val: "47" },
      { key: "Arg Chains", val: "12" },
      { key: "Coherence", val: "88%" },
      { key: "Ambiguous", val: "6 ⚠" },
      { key: "Nested Refs", val: "34" },
    ],
    verdict: {
      flash: "SEGMENTATION DONE",
      badge: "PRIORITY ALPHA",
      title: "47 CRITICAL CLAUSES FLAGGED",
      sub: "23 logical sections mapped. 47 clauses above criticality threshold 0.72. 6 require human review.",
      alertLabel: "CRITICAL CLAUSE",
      alertText:
        '§4.2 — "comply within 90 days" → Binding obligation, HIGH priority. Zero SME exemptions stated.',
      actionLabel: "RISK FLAG ⚠",
      actionText:
        "§9 uses ambiguous 'operational readiness' — dual interpretation risk across member states detected.",
      riskIndex: "7.8",
      riskLabel: "RISK INDEX",
      economicVal: "47",
      economicLabel: "CRITICAL CLAUSES",
      stats: [
        { k: "SECTIONS", v: "23" },
        { k: "CLAUSES", v: "47" },
        { k: "AMBIGUOUS", v: "6" },
        { k: "ARG CHAINS", v: "12" },
      ],
      tags: ["47 clauses", "23 sections", "6 flagged"],
    },
  },
  {
    id: "summarize",
    label: "Contextual Summarization",
    short: "SUMM",
    sector: "S3",
    color: C.primary,
    desc: "Extractive + abstractive fusion. Meaningful context beyond surface-level summarization.",
    duration: 4800,
    subTasks: [
      { label: "LexRank extractive pass", pct: 0.18 },
      { label: "Loading T5-base (220M params)", pct: 0.14 },
      { label: "Abstractive generation beam=4", pct: 0.3 },
      { label: "Executive summary fusion", pct: 0.2 },
      { label: "Claim verification pass", pct: 0.18 },
    ],
    metrics: [
      { key: "Extractive", val: "LexRank" },
      { key: "Abstractive", val: "T5-base" },
      { key: "Compression", val: "14:1" },
      { key: "Key Claims", val: "31" },
      { key: "ROUGE-L", val: "0.423" },
      { key: "Evidence", val: "67%" },
    ],
    verdict: {
      flash: "SUMMARY GENERATED",
      badge: "ECONOMIC ADVANTAGE",
      title: "EXECUTIVE BRIEF COMPILED",
      sub: "14:1 compression achieved. 31 key claims verified. Fusion captures latent context missed by extractive-only.",
      alertLabel: "KEY FINDING",
      alertText:
        "90-day compliance mandate (§4.2) with zero SME exemptions. €2.4B funding: 88% urban vs 12% rural — structural inequity.",
      actionLabel: "IMMEDIATE ACTION",
      actionText:
        "§9 ambiguity on 'operational readiness' poses cross-border arbitrage risk. Requires urgent legal clarification.",
      riskIndex: "8.4",
      riskLabel: "URGENCY INDEX",
      economicVal: "$1.2M",
      economicLabel: "EST. COMPLIANCE COST",
      stats: [
        { k: "COMPRESSION", v: "14:1" },
        { k: "CLAIMS", v: "31" },
        { k: "ROUGE-L", v: "0.423" },
        { k: "EVIDENCE", v: "67%" },
      ],
      tags: ["T5-base", "LexRank", "ROUGE-L 0.423"],
    },
  },
  {
    id: "stakeholder",
    label: "Stakeholder Impact",
    short: "IMPACT",
    sector: "S3",
    color: C.primary,
    desc: "Mapping policy implications across stakeholder groups via obligation parsing.",
    duration: 3600,
    subTasks: [
      { label: "Stakeholder entity extraction", pct: 0.18 },
      { label: "Obligation parsing (MUST/SHALL)", pct: 0.22 },
      { label: "Impact vector scoring", pct: 0.24 },
      { label: "Risk flag identification", pct: 0.2 },
      { label: "Priority action generation", pct: 0.16 },
    ],
    metrics: [
      { key: "Groups", val: "6" },
      { key: "Impact Vectors", val: "18" },
      { key: "Risk Flags", val: "4 HIGH" },
      { key: "Actions", val: "9" },
      { key: "Obligations", val: "23" },
      { key: "Max Score", val: "9.1/10" },
    ],
    verdict: {
      flash: "IMPACT MAPPED",
      badge: "PRIORITY ALPHA",
      title: "6 STAKEHOLDER GROUPS SCORED",
      sub: "Providers (9.1/10) and SMEs (8.7/10) face highest burden. 4 high-risk flags escalated.",
      alertLabel: "HIGHEST IMPACT",
      alertText:
        "Primary care providers: 9.1/10 impact score. Licensing costs +34% within 18 months. SMEs: no grace period.",
      actionLabel: "4 RISK FLAGS",
      actionText:
        "90-day cliff · §9 arbitrage gap · Rural funding inequity (12%) · Unlicensed cross-border data flows.",
      riskIndex: "9.1",
      riskLabel: "MAX IMPACT SCORE",
      economicVal: "€2.4B",
      economicLabel: "FUNDING AT STAKE",
      stats: [
        { k: "STAKEHOLDERS", v: "6" },
        { k: "RISK FLAGS", v: "4" },
        { k: "VECTORS", v: "18" },
        { k: "ACTIONS", v: "9" },
      ],
      tags: ["6 groups", "4 risk flags", "9 actions"],
    },
  },
  {
    id: "structure",
    label: "Structured Output",
    short: "EXPORT",
    sector: "FINISH",
    color: C.green,
    desc: "Compiling decision-ready JSON schema, executive brief and prioritised action board.",
    duration: 2800,
    subTasks: [
      { label: "JSON schema compilation", pct: 0.18 },
      { label: "Executive brief generation", pct: 0.26 },
      { label: "Action item prioritisation", pct: 0.22 },
      { label: "Confidence index calculation", pct: 0.16 },
      { label: "PDF report rendering", pct: 0.18 },
    ],
    metrics: [
      { key: "Format", val: "JSON+PDF" },
      { key: "Actions", val: "12" },
      { key: "Confidence", val: "91%" },
      { key: "Schema", val: "v2.4.1" },
      { key: "Pages", val: "4" },
      { key: "Runtime", val: "27.7s" },
    ],
    verdict: {
      flash: "RACE COMPLETE 🏁",
      badge: "DOWNLOAD READY",
      title: "DECISION REPORT DELIVERED",
      sub: "12 action items prioritised P1–P3. Confidence 91%. JSON + PDF cryptographically signed SHA-256.",
      alertLabel: "P1 ACTIONS",
      alertText:
        "Appoint DPO immediately · Legal review §9 · Launch compliance RFP · Schedule stakeholder consultation Q2.",
      actionLabel: "CONFIDENCE: 91%",
      actionText:
        "All 7 pipeline sectors complete. Full structured output: formula_ai_report_2024.json + executive PDF brief.",
      riskIndex: "91%",
      riskLabel: "CONFIDENCE INDEX",
      economicVal: "12",
      economicLabel: "ACTION ITEMS",
      stats: [
        { k: "ACTIONS", v: "12" },
        { k: "CONFIDENCE", v: "91%" },
        { k: "SECTORS", v: "7/7" },
        { k: "RUNTIME", v: "27.7s" },
      ],
      tags: ["JSON+PDF", "SHA-256", "91% confidence"],
    },
  },
];

// ─── TRACK SVG ────────────────────────────────────────────────────────────────
const TCX = 110,
  TCY = 110,
  TR = 82;
function TrackMap({ progress, currentStep, completedSteps, stepProgress }) {
  const C2 = 2 * Math.PI * TR;
  const p = Math.max(0, Math.min(progress, 1));
  const ringDash = p >= 0.999 ? `${C2} 0` : `${p * C2} ${C2}`;
  const ca = progress * Math.PI * 2 - Math.PI / 2;
  const cx = TCX + TR * Math.cos(ca),
    cy = TCY + TR * Math.sin(ca);
  const cc = STEPS[Math.min(currentStep, STEPS.length - 1)]?.color || C.primary;
  return (
    <svg viewBox="0 0 220 220" width="100%" height="100%">
      <defs>
        <filter id="gf2">
          <feGaussianBlur stdDeviation="4" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      {[...Array(12)].map((_, i) => (
        <circle
          key={i}
          cx={TCX}
          cy={TCY}
          r={TR + 14}
          fill="none"
          stroke={i % 2 ? "#fff" : C.primary}
          strokeWidth="3"
          opacity=".3"
          strokeDasharray={`${(C2 + 28 * Math.PI) / 12} ${(C2 + 28 * Math.PI) / 12}`}
          strokeDashoffset={`${(-i * (C2 + 28 * Math.PI)) / 12}`}
        />
      ))}
      <circle
        cx={TCX}
        cy={TCY}
        r={TR}
        fill="none"
        stroke="#111"
        strokeWidth="28"
      />
      <circle
        cx={TCX}
        cy={TCY}
        r={TR}
        fill="none"
        stroke="#1a1a1a"
        strokeWidth="26"
      />
      {progress > 0 && (
        <>
          <circle
            cx={TCX}
            cy={TCY}
            r={TR}
            fill="none"
            stroke={cc}
            strokeWidth="4"
            strokeOpacity=".15"
            strokeDasharray={ringDash}
            strokeDashoffset={C2 * 0.25}
            style={{ filter: "url(#gf2)" }}
          />
          <circle
            cx={TCX}
            cy={TCY}
            r={TR}
            fill="none"
            stroke={cc}
            strokeWidth="2"
            strokeOpacity=".9"
            strokeDasharray={ringDash}
            strokeDashoffset={C2 * 0.25}
            strokeLinecap="round"
          />
        </>
      )}
      {STEPS.map((s, i) => {
        const a = (i / STEPS.length) * Math.PI * 2 - Math.PI / 2;
        const mx = TCX + TR * Math.cos(a),
          my = TCY + TR * Math.sin(a);
        const done = completedSteps.includes(s.id),
          active = currentStep === i;
        return (
          <g key={s.id}>
            <circle
              cx={mx}
              cy={my}
              r={active ? 7 : done ? 5 : 3}
              fill={done || active ? s.color : "#222"}
              stroke={done || active ? s.color : "#333"}
              strokeWidth="1.5"
              style={active || done ? { filter: "url(#gf2)" } : {}}
            />
            {active && (
              <circle
                cx={mx}
                cy={my}
                r={12}
                fill="none"
                stroke={s.color}
                strokeWidth="1"
                opacity=".4"
              >
                <animate
                  attributeName="r"
                  values="7;16;7"
                  dur="1.4s"
                  repeatCount="indefinite"
                />
                <animate
                  attributeName="opacity"
                  values=".6;0;.6"
                  dur="1.4s"
                  repeatCount="indefinite"
                />
              </circle>
            )}
          </g>
        );
      })}
      {progress > 0 && (
        <g transform={`translate(${cx},${cy})`}>
          <circle cx="0" cy="0" r="14" fill="none" stroke={cc} opacity=".1">
            <animate
              attributeName="r"
              values="7;16;7"
              dur="2s"
              repeatCount="indefinite"
            />
            <animate
              attributeName="opacity"
              values=".3;0;.3"
              dur="2s"
              repeatCount="indefinite"
            />
          </circle>
          <circle
            cx="0"
            cy="0"
            r="6"
            fill={cc}
            style={{ filter: "url(#gf2)" }}
          />
          <circle cx="0" cy="0" r="2.5" fill="#fff" />
        </g>
      )}
      <text
        x={TCX}
        y={TCY - 12}
        textAnchor="middle"
        fill="#dbeafe"
        fontSize="7"
        fontFamily="monospace"
        letterSpacing="2"
        fontWeight="bold"
      >
        FORMULA/AI
      </text>
      <text
        x={TCX}
        y={TCY + 6}
        textAnchor="middle"
        fill="#fff"
        fontSize="22"
        fontWeight="900"
        fontFamily="monospace"
        fontStyle="italic"
      >
        {Math.round(progress * 100)}%
      </text>
      <text
        x={TCX}
        y={TCY + 18}
        textAnchor="middle"
        fill="#93c5fd"
        fontSize="6"
        fontFamily="monospace"
      >
        {completedSteps.length}/{STEPS.length} SECTORS
      </text>
    </svg>
  );
}

// ─── MAIN ─────────────────────────────────────────────────────────────────────
export default function FormulaAI({ onOpenChatbot }) {
  const [phase, setPhase] = useState("idle");
  const [curStep, setCurStep] = useState(0);
  const [progress, setProgress] = useState(0);
  const [doneIds, setDoneIds] = useState([]);
  const [trackProg, setTrackProg] = useState(0);
  const [showVerdict, setShowVerdict] = useState(false);
  const [verdictStep, setVerdictStep] = useState(null);
  const [newId, setNewId] = useState(null);
  const [raceTime, setRaceTime] = useState(0);
  const [inputText, setInputText] = useState("");
  const [inputError, setInputError] = useState("");
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [sessionTime, setSessionTime] = useState("00:00:00.000");
  const [verdictCountdown, setVerdictCountdown] = useState(5);

  // ─── API STATE ────────────────────────────────────────────────────────────
  const [jobId, setJobId] = useState(null);
  const [fileIds, setFileIds] = useState([]);
  const [apiSteps, setApiSteps] = useState(STEPS);
  const [panelData, setPanelData] = useState({
    stats: null,
    structure: null,
    radio: null,
    topics: null,
    clauses: null,
    recommendations: null,
    insights: null,
    stakeholders: null,
    risk: null,
  });
  const [panelDataLoaded, setPanelDataLoaded] = useState(false);
  const [panelDataError, setPanelDataError] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [expandedDetail, setExpandedDetail] = useState(null);

  const animRef = useRef(null);
  const runRef = useRef(null);
  const timerRef = useRef(null);
  const sessionRef = useRef(null);
  const startRef = useRef(null);
  const fileRef = useRef(null);
  const cdRef = useRef(null);
  const eventSourceRef = useRef(null);

  const cleanReadableText = (value, fallback = "") => {
    const text = String(value || "")
      .replace(/[\u0000-\u001F\u007F]/g, " ")
      .replace(/([a-z])([A-Z])/g, "$1 $2")
      .replace(/\s+/g, " ")
      .trim();
    return text || fallback;
  };

  const titleCaseLabel = (value) =>
    cleanReadableText(value)
      .replace(/[_-]+/g, " ")
      .toLowerCase()
      .replace(/\b\w/g, (m) => m.toUpperCase());

  const inferRecommendationPriority = (text, idx = 0) => {
    const low = String(text || "").toLowerCase();
    if (/\b(immediate|urgent|critical|now|asap|deadline|must)\b/.test(low)) {
      return "IMMEDIATE";
    }
    if (/\b(strategy|roadmap|plan|phase|milestone|owner)\b/.test(low)) {
      return "STRATEGIC";
    }
    return idx === 0 ? "IMMEDIATE" : idx === 1 ? "STRATEGIC" : "LONG-TERM";
  };

  const uniqueBy = (items, keyFn) => {
    const seen = new Set();
    return (items || []).filter((item) => {
      const key = keyFn(item);
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  };

  const normalizePanelPayload = (raw) => {
    const rawTopics = Array.isArray(raw?.topics)
      ? raw.topics
      : Array.isArray(raw?.topics?.topics)
        ? raw.topics.topics
        : [];
    const topics = uniqueBy(
      rawTopics
        .map((t) => ({
          label: titleCaseLabel(t?.label || t?.topic || "General Policy"),
          pct: Math.max(1, Math.min(100, Number(t?.pct ?? t?.confidence ?? 0) || 0)),
        }))
        .filter((t) => t.label),
      (t) => t.label.toLowerCase(),
    ).slice(0, 6);

    const rawClauses = Array.isArray(raw?.clauses)
      ? raw.clauses
      : Array.isArray(raw?.clauses?.clauses)
        ? raw.clauses.clauses
        : [];
    const clauses = rawClauses
      .map((c, idx) => ({
        label: cleanReadableText(c?.label || c?.clause_type || "Other", "Other").toUpperCase(),
        val: cleanReadableText(c?.val || c?.text || c?.rationale || ""),
        color: c?.color || C.primary,
        id: String(c?.id || `cl-${idx + 1}`),
      }))
      .filter((c) => c.val)
      .slice(0, 12);

    const rawInsights = Array.isArray(raw?.insights)
      ? raw.insights
      : Array.isArray(raw?.insights?.insights)
        ? raw.insights.insights
        : [];
    const insights = rawInsights
      .map((item, idx) => ({
        id: item?.id || `i${idx + 1}`,
        conf: cleanReadableText(item?.conf || "80%"),
        text: cleanReadableText(item?.text || item?.summary || ""),
        color: item?.color || C.primary,
      }))
      .filter((i) => i.text)
      .slice(0, 8);

    const rawRecs = Array.isArray(raw?.recommendations)
      ? raw.recommendations
      : Array.isArray(raw?.recommendations?.recommendations)
        ? raw.recommendations.recommendations
        : [];
    const recommendations = rawRecs
      .map((r, idx) => {
        const text = cleanReadableText(r?.text || r?.detail || r?.recommendation || "");
        return {
          priority: cleanReadableText(r?.priority || inferRecommendationPriority(text, idx), "INFO").toUpperCase(),
          text,
        };
      })
      .filter((r) => r.text)
      .slice(0, 6);

    const rawStakeholders = Array.isArray(raw?.stakeholders)
      ? raw.stakeholders
      : Array.isArray(raw?.stakeholders?.groups)
        ? raw.stakeholders.groups
        : [];
    const stakeholders = rawStakeholders.slice(0, 8);

    const radio = Array.isArray(raw?.radio)
      ? raw.radio
      : Array.isArray(raw?.radio?.comms)
        ? raw.radio.comms
        : [];

    return {
      stats: raw?.stats || null,
      structure: raw?.structure || null,
      radio,
      topics,
      clauses,
      recommendations,
      insights,
      stakeholders,
      risk: raw?.risk || null,
    };
  };

  const withGeneratedFallbacks = (normalized) => {
    const next = {
      ...normalized,
      topics: [...(normalized.topics || [])],
      clauses: [...(normalized.clauses || [])],
      recommendations: [...(normalized.recommendations || [])],
      insights: [...(normalized.insights || [])],
    };

    if (!next.insights.length && next.clauses.length) {
      next.insights = next.clauses.slice(0, 4).map((cl, idx) => ({
        id: `i${idx + 1}`,
        conf: `${88 - idx * 5}%`,
        text: `${titleCaseLabel(cl.label)} clause detected: ${cleanReadableText(cl.val)}`,
        color: cl.color || C.primary,
      }));
    }

    if (!next.topics.length && next.clauses.length) {
      const counts = next.clauses.reduce((acc, cl) => {
        const key = titleCaseLabel(cl.label || "General Policy");
        acc[key] = (acc[key] || 0) + 1;
        return acc;
      }, {});
      const total = Object.values(counts).reduce((sum, n) => sum + n, 0) || 1;
      next.topics = Object.entries(counts)
        .map(([label, count]) => ({
          label,
          pct: Math.max(1, Math.round((count / total) * 100)),
        }))
        .slice(0, 5);
    }

    if (!next.recommendations.length) {
      const seeded = [];
      if (next.clauses.some((c) => /OBLIGATION|COMPLIANCE|DEADLINE/.test(c.label))) {
        seeded.push("Create a compliance checklist with owners and target timelines.");
      }
      if (next.stakeholders.length) {
        seeded.push("Prioritize communication with high-impact stakeholder groups.");
      }
      if (!seeded.length && next.insights.length) {
        seeded.push("Translate top insights into an execution roadmap with milestones.");
      }
      seeded.push("Track implementation progress and refresh analysis after key updates.");

      next.recommendations = uniqueBy(
        seeded.map((text, idx) => ({
          priority: inferRecommendationPriority(text, idx),
          text,
        })),
        (item) => item.text.toLowerCase(),
      ).slice(0, 4);
    }

    if (!next.clauses.length && next.insights.length) {
      next.clauses = next.insights.slice(0, 4).map((ins, idx) => ({
        label: "INSIGHT",
        val: cleanReadableText(ins.text),
        color: C.primary,
        id: `gen-cl-${idx + 1}`,
      }));
    }

    return next;
  };

  // session clock
  useEffect(() => {
    sessionRef.current = setInterval(() => {
      const n = new Date();
      setSessionTime(
        `${String(n.getHours()).padStart(2, "0")}:${String(n.getMinutes()).padStart(2, "0")}:${String(n.getSeconds()).padStart(2, "0")}.${String(n.getMilliseconds()).padStart(3, "0")}`,
      );
    }, 50);
    return () => clearInterval(sessionRef.current);
  }, []);

  // ─── API FUNCTIONS ───────────────────────────────────────────────────────────

  const uploadFiles = async (files) => {
    if (!files?.length) return [];
    setIsUploading(true);
    try {
      const formData = new FormData();
      const endpoint = files.length > 1 ? "/upload-multiple" : "/upload";
      if (files.length > 1) {
        files.forEach((file) => formData.append("files", file));
      } else {
        formData.append("file", files[0]);
      }
      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) {
        let detail = "Upload failed";
        try {
          const err = await res.json();
          detail = err?.detail || detail;
        } catch {
          // ignore parse failures
        }
        throw new Error(detail);
      }
      const data = await res.json();
      const uploaded = Array.isArray(data.files) ? data.files : [data];
      setUploadedFiles(
        uploaded.map((f) => ({ name: f.filename, size: f.size_bytes })),
      );
      setFileIds(uploaded.map((f) => f.file_id));
      setInputError("");
      return uploaded.map((f) => f.file_id);
    } catch (err) {
      setInputError("File upload failed: " + err.message);
      return [];
    } finally {
      setIsUploading(false);
    }
  };

  const runJobOnAPI = async ({ text, fileIds: fileIdsForRun }) => {
    try {
      let body = { text };
      if (fileIdsForRun?.length === 1) {
        body = { file_id: fileIdsForRun[0] };
      } else if (fileIdsForRun?.length > 1) {
        body = { file_ids: fileIdsForRun };
      }

      const res = await fetch(`${API_BASE}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        let detail = "Job start failed";
        try {
          const errData = await res.json();
          detail = errData?.detail || detail;
        } catch {
          // ignore JSON parse failure
        }
        throw new Error(detail);
      }
      const data = await res.json();
      setJobId(data.job_id);
      return data.job_id;
    } catch (err) {
      setInputError("Failed to start job: " + err.message);
      return null;
    }
  };

  const setupSSE = (jid) => {
    try {
      const es = new EventSource(`${API_BASE}/jobs/${jid}/stream`);
      eventSourceRef.current = es;
      let stepIndex = 0;
      const normalizeStepId = (stepId) =>
        stepId === "impact" ? "structure" : stepId;

      es.addEventListener("step_progress", (e) => {
        const data = JSON.parse(e.data);
        const idx = Number(data.step_index || 0);
        const pct = Number(data.progress_pct || 0);

        setCurStep(idx);
        setProgress(pct);
        setTrackProg((idx + pct / 100) / STEPS.length);

        // Update current step's progress
        setApiSteps((prev) =>
          prev.map((s, i) =>
            i === idx
              ? {
                  ...s,
                  label: data.label || s.label,
                  desc: data.desc || s.desc,
                  sector: data.sector || s.sector,
                  short: data.short || s.short,
                  color: data.color || s.color,
                  progress: pct,
                  currentMetrics: data.metrics || s.metrics,
                }
              : s,
          ),
        );
      });

      es.addEventListener("step_complete", (e) => {
        const data = JSON.parse(e.data);
        const resolvedStepId = normalizeStepId(data.step_id);
        // Mark step as done, show verdict
        const stepData = STEPS.find((s) => s.id === resolvedStepId);
        if (stepData) {
          setVerdictStep({ ...stepData, verdict: data.verdict });
          setShowVerdict(true);
          stepIndex = STEPS.findIndex((s) => s.id === resolvedStepId);
          setCurStep(stepIndex);
          setProgress(100);
          setTrackProg((stepIndex + 1) / STEPS.length);
          setDoneIds((prev) =>
            prev.includes(resolvedStepId) ? prev : [...prev, resolvedStepId],
          );
        }
      });

      es.addEventListener("pipeline_done", async (e) => {
        const data = JSON.parse(e.data);
        es.close();
        eventSourceRef.current = null;

        // Fetch all panel data
        await fetchPanelData(jid);

        setPhase("done");
        setTrackProg(1);
        setCurStep(STEPS.length);
        setDoneIds(STEPS.map((s) => s.id));
        clearInterval(timerRef.current);
      });

      es.addEventListener("error", (e) => {
        const data = JSON.parse(e.data);
        setInputError("Pipeline error: " + data.message);
        es.close();
        eventSourceRef.current = null;
      });
    } catch (err) {
      setInputError("SSE connection failed: " + err.message);
    }
  };

  const fetchPanelData = async (jid) => {
    try {
      setPanelDataError("");
      const [
        stats,
        structure,
        radio,
        topics,
        clauses,
        recs,
        insights,
        stakeholders,
        risk,
      ] = await Promise.all([
        fetch(`${API_BASE}/jobs/${jid}/stats`).then((r) => r.json()),
        fetch(`${API_BASE}/jobs/${jid}/structure`).then((r) => r.json()),
        fetch(`${API_BASE}/jobs/${jid}/radio`).then((r) => r.json()),
        fetch(`${API_BASE}/jobs/${jid}/topics`).then((r) => r.json()),
        fetch(`${API_BASE}/jobs/${jid}/clauses`).then((r) => r.json()),
        fetch(`${API_BASE}/jobs/${jid}/recommendations`).then((r) => r.json()),
        fetch(`${API_BASE}/jobs/${jid}/insights`).then((r) => r.json()),
        fetch(`${API_BASE}/jobs/${jid}/stakeholders`).then((r) => r.json()),
        fetch(`${API_BASE}/jobs/${jid}/risk`).then((r) => r.json()),
      ]);

      const normalized = normalizePanelPayload({
        stats,
        structure,
        radio,
        topics,
        clauses,
        recommendations: recs,
        insights,
        stakeholders,
        risk,
      });

      setPanelData(withGeneratedFallbacks(normalized));
      setPanelDataLoaded(true);
    } catch (err) {
      console.error("Failed to fetch panel data:", err);
      setPanelData({
        stats: null,
        structure: null,
        radio: [],
        topics: [],
        clauses: [],
        recommendations: [],
        insights: [],
        stakeholders: [],
        risk: null,
      });
      setPanelDataLoaded(true);
      setPanelDataError(
        "Analysis completed, but panel data could not be loaded.",
      );
    }
  };

  const abortJob = async () => {
    if (!jobId) return;
    try {
      await fetch(`${API_BASE}/jobs/${jobId}`, { method: "DELETE" });
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      reset();
    } catch (err) {
      console.error("Abort failed:", err);
    }
  };

  const downloadReport = async (format = "json") => {
    if (!jobId) return;
    try {
      const res = await fetch(
        `${API_BASE}/jobs/${jobId}/report?format=${format}`,
      );
      if (!res.ok) throw new Error("Download failed");

      if (format === "json") {
        const data = await res.json();
        const blob = new Blob([JSON.stringify(data, null, 2)], {
          type: "application/json",
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `report_${jobId}.json`;
        a.click();
        URL.revokeObjectURL(url);
      }
    } catch (err) {
      console.error("Download failed:", err);
    }
  };

  const runStep = useCallback((idx, done) => {
    if (idx >= STEPS.length) {
      setPhase("done");
      setTrackProg(1);
      setCurStep(STEPS.length);
      clearInterval(timerRef.current);
      return;
    }
    const step = STEPS[idx];
    setCurStep(idx);
    setProgress(0);
    setShowVerdict(false);
    const t0 = Date.now();
    const base = idx / STEPS.length;
    const tick = () => {
      const e = Date.now() - t0;
      const p = Math.min(e / step.duration, 1);
      setProgress(p * 100);
      setTrackProg(base + p / STEPS.length);
      if (p < 1) {
        animRef.current = requestAnimationFrame(tick);
      } else {
        const nd = [...done, step.id];
        setDoneIds(nd);
        setNewId(step.id);
        setVerdictStep(step);
        setShowVerdict(true);
        setVerdictCountdown(5);
        // countdown
        let cd = 5;
        cdRef.current = setInterval(() => {
          cd -= 0.1;
          setVerdictCountdown(Math.max(0, cd));
          if (cd <= 0) {
            clearInterval(cdRef.current);
          }
        }, 100);
        setTimeout(() => {
          clearInterval(cdRef.current);
          setShowVerdict(false);
          setNewId(null);
          setTimeout(() => runRef.current?.(idx + 1, nd), 300);
        }, 5000);
      }
    };
    animRef.current = requestAnimationFrame(tick);
  }, []);

  useEffect(() => {
    runRef.current = runStep;
  }, [runStep]);

  const start = () => {
    setPhase("running");
    setCurStep(0);
    setProgress(0);
    setDoneIds([]);
    setTrackProg(0);
    setShowVerdict(false);
    setVerdictStep(null);
    setNewId(null);
    setRaceTime(0);
    startRef.current = Date.now();
    timerRef.current = setInterval(
      () => setRaceTime(((Date.now() - startRef.current) / 1000).toFixed(1)),
      100,
    );
    runStep(0, []);
  };

  const reset = () => {
    cancelAnimationFrame(animRef.current);
    clearInterval(timerRef.current);
    clearInterval(cdRef.current);
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setPhase("idle");
    setCurStep(0);
    setProgress(0);
    setDoneIds([]);
    setTrackProg(0);
    setShowVerdict(false);
    setVerdictStep(null);
    setNewId(null);
    setRaceTime(0);
    setInputText("");
    setUploadedFiles([]);
    setInputError("");
    setJobId(null);
    setFileIds([]);
    setApiSteps(STEPS);
    setPanelData({
      stats: null,
      structure: null,
      radio: null,
      topics: null,
      clauses: null,
      recommendations: null,
      insights: null,
      stakeholders: null,
      risk: null,
    });
    setPanelDataLoaded(false);
    setPanelDataError("");
  };

  useEffect(
    () => () => {
      cancelAnimationFrame(animRef.current);
      clearInterval(timerRef.current);
      clearInterval(cdRef.current);
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    },
    [],
  );

  const handleRun = async () => {
    const trimmedInput = inputText.trim();
    const isFilePlaceholder =
      /^\[Files?:\s*\d+\]$/i.test(trimmedInput) ||
      /^\[Files?:\s*\d+\]\s+/i.test(trimmedInput);
    const hasTypedText = !!trimmedInput && !isFilePlaceholder;
    const useFileSource = fileIds.length > 0 && !hasTypedText;

    if (!trimmedInput && fileIds.length === 0) {
      setInputError("Paste document text or upload a file first.");
      return;
    }
    if (!useFileSource && trimmedInput.length < 20) {
      setInputError("Input too short — provide a real document.");
      return;
    }

    setInputError("");
    setPhase("running");
    setCurStep(0);
    setProgress(0);
    setDoneIds([]);
    setTrackProg(0);
    setShowVerdict(false);
    setVerdictStep(null);
    setNewId(null);
    setRaceTime(0);
    setApiSteps(STEPS);
    startRef.current = Date.now();
    timerRef.current = setInterval(
      () => setRaceTime(((Date.now() - startRef.current) / 1000).toFixed(1)),
      100,
    );

    // Use API instead of local simulation
    const jid = await runJobOnAPI({
      text: useFileSource ? null : trimmedInput,
      fileIds: useFileSource ? fileIds : [],
    });
    if (jid) {
      setupSSE(jid);
    } else {
      setPhase("idle");
      clearInterval(timerRef.current);
    }
  };

  const step = apiSteps[Math.min(curStep, apiSteps.length - 1)];
  const stepColor = step?.color || C.primary;
  const liveMetrics = step?.currentMetrics || step?.metrics || [];

  // derived state for panels
  const doneClassify = doneIds.includes("classify");
  const doneSegment = doneIds.includes("segment");
  const doneSummarize = doneIds.includes("summarize");
  const doneStakeholder = doneIds.includes("stakeholder");
  const doneIngest = doneIds.includes("ingest");
  const doneTokenize = doneIds.includes("tokenize");

  // sub-task ranges
  let cursor = 0;
  const subRanges =
    step?.subTasks.map((st) => {
      const s = cursor;
      cursor += st.pct;
      return { start: s, end: cursor };
    }) || [];

  // topics from API only
  const topics = (panelData.topics || []).map((t) => ({
    label: t.label,
    pct: t.pct,
    color: C.primary,
  }));

  // clauses from API only
  const clauses = (panelData.clauses || []).map((c) => ({ ...c }));

  // standings from API only
  const standings = (panelData.stakeholders || []).map((s, i) => ({
    rank: String(i + 1).padStart(2, "0"),
    label: s.label,
    score: s.score,
    max: s.max_score,
    color: C.primary,
  }));

  // risk - use API or fallback
  const riskData =
    panelDataLoaded && panelData.risk
      ? {
          value: panelData.risk.risk_value * 10,
          sentiment: panelData.risk.sentiment,
          volatility: panelData.risk.volatility,
        }
      : {
          value: 0,
          sentiment: panelDataLoaded ? "unknown" : "pending",
          volatility: panelDataLoaded ? "unknown" : "pending",
        };

  const riskColor =
    riskData.value > 7 ? C.red : riskData.value > 4 ? C.yellow : C.green;
  const riskVal = riskData.value;
  const riskCircumference = 2 * Math.PI * 45;
  const riskDash = (riskData.value / 10) * riskCircumference;

  // insights from API only
  const insights = (panelData.insights || []).map((i) => ({
    id: i.id,
    conf: i.conf,
    text: i.text,
    color: i.color,
    shown: true,
  }));

  // radio comms from API only
  const comms = (panelData.radio || []).map((r) => ({
    type: r.type,
    text: r.text,
    color: r.color,
    shown: true,
  }));

  const recommendations = panelData.recommendations || [];
  const analysisComplete =
    phase === "done" &&
    panelDataLoaded &&
    doneIds.length === STEPS.length &&
    fileIds.length > 0;

  const trimText = (value, maxLen = 220) => {
    const text = String(value || "")
      .replace(/\s+/g, " ")
      .trim();
    if (text.length <= maxLen) return text;
    return `${text.slice(0, maxLen - 3)}...`;
  };

  const toggleExpandedDetail = (detail) => {
    setExpandedDetail((prev) => (prev?.key === detail.key ? null : detail));
  };

  const pipelineStatusNote = panelDataError
    ? panelDataError
    : panelDataLoaded
      ? "Analysis data loaded."
      : "Waiting for backend analysis data...";

  const statsData = panelDataLoaded
    ? {
        processed: panelData.stats?.tokens_processed ?? 0,
        accuracy: panelData.stats?.accuracy_pct ?? 0,
        delta: panelData.stats?.delta_pct ?? 0,
        velocity: panelData.stats?.velocity_series?.length
          ? panelData.stats.velocity_series[
              panelData.stats.velocity_series.length - 1
            ].val
          : 0,
      }
    : null;

  const velocitySeriesRaw =
    panelDataLoaded && Array.isArray(panelData.stats?.velocity_series)
      ? panelData.stats.velocity_series
      : [];

  const velocitySeries =
    velocitySeriesRaw.length >= 2
      ? velocitySeriesRaw
      : velocitySeriesRaw.length === 1
        ? [{ t: velocitySeriesRaw[0].t, val: 0 }, velocitySeriesRaw[0]]
        : [];

  const sparkW = 100;
  const sparkH = 40;
  const hasVelocitySeries = velocitySeries.length >= 2;

  let velocityLinePath = "";
  let velocityAreaPath = "";
  if (hasVelocitySeries) {
    const minT = Math.min(...velocitySeries.map((p) => Number(p.t) || 0));
    const maxT = Math.max(...velocitySeries.map((p) => Number(p.t) || 0));
    const maxV = Math.max(1, ...velocitySeries.map((p) => Number(p.val) || 0));
    const spanT = Math.max(1, maxT - minT);

    const points = velocitySeries.map((p) => {
      const x = ((Number(p.t) - minT) / spanT) * sparkW;
      const y =
        sparkH - (Math.max(0, Number(p.val) || 0) / maxV) * (sparkH - 3);
      return {
        x: Number.isFinite(x) ? x : 0,
        y: Number.isFinite(y) ? y : sparkH,
      };
    });

    velocityLinePath = points
      .map(
        (pt, idx) =>
          `${idx === 0 ? "M" : "L"}${pt.x.toFixed(2)} ${pt.y.toFixed(2)}`,
      )
      .join(" ");

    const first = points[0];
    const last = points[points.length - 1];
    velocityAreaPath = `${velocityLinePath} L${last.x.toFixed(2)} ${sparkH} L${first.x.toFixed(2)} ${sparkH} Z`;
  }

  const structureData = panelDataLoaded
    ? {
        sections: panelData.structure?.sections ?? 0,
        citationDensity: panelData.structure?.citation_density ?? 0,
        figures: panelData.structure?.figures ?? 0,
        tables: panelData.structure?.tables ?? 0,
      }
    : null;

  const modelConfidenceValue = panelDataLoaded
    ? Number(panelData.stats?.accuracy_pct ?? 0)
    : phase === "running"
      ? Math.round(trackProg * 1000) / 10
      : null;

  return (
    <div
      style={{
        minHeight: "100vh",
        background: C.bg,
        color: C.text,
        fontFamily: "'Public Sans','Courier New',monospace",
        backgroundImage:
          "radial-gradient(circle, #2a2a2a 1px, transparent 1px)",
        backgroundSize: "20px 20px",
        display: "flex",
        flexDirection: "column",
        padding: "16px",
        boxSizing: "border-box",
      }}
    >
      <style>{`
        @keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
        @keyframes spin360{to{transform:rotate(360deg)}}
        @keyframes slideInUp{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}
        @keyframes verdictIn{from{opacity:0;transform:scale(.97)}to{opacity:1;transform:scale(1)}}
        @keyframes slideRow{from{opacity:0;transform:translateX(10px)}to{opacity:1;transform:translateX(0)}}
        @keyframes blink{0%,100%{opacity:1}50%{opacity:0}}
        ::-webkit-scrollbar{width:3px}
        ::-webkit-scrollbar-track{background:#000}
        ::-webkit-scrollbar-thumb{background:#333}
        .skeuo-card{
          background:${C.card};
          border:2px solid #000;
          box-shadow:4px 4px 0px #000;
        }
        .dashboard-shell{
          width:100%;
          max-width:1320px;
          margin:0 auto;
          background:linear-gradient(180deg,#121218 0%,#0b0b10 100%);
          border:3px solid #000;
          box-shadow:8px 8px 0px #000;
          min-height:calc(100vh - 32px);
          display:flex;
          flex-direction:column;
          overflow:hidden;
        }
        .skeuo-inset{
          box-shadow:inset 4px 4px 8px rgba(0,0,0,.5),inset -1px -1px 2px rgba(255,255,255,.04);
        }
        .btn-primary{
          background:${C.primary};border:none;color:#fff;
          font-family:inherit;font-weight:900;font-size:12px;
          letter-spacing:.1em;padding:12px 20px;cursor:pointer;
          text-transform:uppercase;font-style:italic;
          transition:transform .1s,box-shadow .1s;
          display:block;width:100%;
        }
        .btn-primary:hover{transform:translateY(-2px);box-shadow:0 4px 0 #000}
        .btn-primary:active{transform:translateY(0);box-shadow:none}
        .btn-ghost{
          background:transparent;border:2px solid ${C.grid};color:#f8fafc;
          font-family:inherit;font-size:10px;padding:6px 12px;
          cursor:pointer;transition:all .12s;text-transform:uppercase;
          letter-spacing:1px;font-weight:700;
        }
        .btn-ghost:hover{border-color:${C.cyan};color:${C.cyan}}
        textarea{
          background:#000;border:2px solid ${C.grid};color:#f8fafc;
          font-family:monospace;font-size:11px;padding:12px;
          resize:none;outline:none;width:100%;box-sizing:border-box;line-height:1.7;
          border-radius:0;
        }
        textarea:focus{border-color:${C.primary}}
        textarea::placeholder{color:#93c5fd}
        .section-title{
          font-size:13px;font-weight:900;text-transform:uppercase;
          letter-spacing:-.02em;font-style:italic;margin-bottom:16px;
        }
        .section-sub{color:${C.cyan};font-weight:600;font-style:normal;font-size:12px}
        .gauge-bar{background:linear-gradient(90deg,${C.primary} 0%,${C.yellow} 100%)}
      `}</style>

      <div className="dashboard-shell">
        {/* ══ HEADER ══════════════════════════════════════════════════════════ */}
        <header
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            borderBottom: `4px solid #000`,
            background: C.bg,
            padding: "0 24px",
            height: "56px",
            flexShrink: 0,
            position: "sticky",
            top: 0,
            zIndex: 50,
          }}
        >
          {/* Logo */}
          <div style={{ display: "flex", alignItems: "center", gap: "20px" }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "10px",
                color: C.primary,
              }}
            >
              {phase === "running" ? (
                <div
                  style={{
                    width: "28px",
                    height: "28px",
                    border: `2px solid ${stepColor}`,
                    borderTopColor: "transparent",
                    borderRadius: "50%",
                    animation: "spin360 .7s linear infinite",
                  }}
                />
              ) : (
                <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
                  <rect width="28" height="28" fill={C.primary} />
                  <text
                    x="14"
                    y="20"
                    textAnchor="middle"
                    fill="#fff"
                    fontSize="13"
                    fontWeight="900"
                    fontStyle="italic"
                    fontFamily="monospace"
                  >
                    GP
                  </text>
                </svg>
              )}
              <span
                style={{
                  fontSize: "20px",
                  fontWeight: "900",
                  letterSpacing: "-.04em",
                  textTransform: "uppercase",
                  fontStyle: "italic",
                  color: "#fff",
                }}
              >
                Grand Prix Protocol
              </span>
            </div>
            <div style={{ width: "1px", height: "32px", background: C.grid }} />
            <div>
              <div
                style={{
                  fontSize: "9px",
                  color: C.muted,
                  fontWeight: "700",
                  textTransform: "uppercase",
                  letterSpacing: "3px",
                  lineHeight: "1",
                }}
              >
                Status
              </div>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  fontSize: "11px",
                  fontWeight: "700",
                  color: C.yellow,
                  textTransform: "uppercase",
                }}
              >
                <span
                  style={{
                    width: "8px",
                    height: "8px",
                    background: phase === "running" ? C.yellow : "#333",
                    borderRadius: "50%",
                    display: "inline-block",
                    animation:
                      phase === "running" ? "pulse 1s infinite" : "none",
                  }}
                />
                {phase === "running"
                  ? "Live Telemetry Active"
                  : phase === "done"
                    ? "Analysis Complete"
                    : "System Standby"}
              </div>
            </div>
          </div>

          {/* Right controls */}
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            {analysisComplete && (
              <button
                className="btn-primary"
                onClick={() => {
                  if (typeof onOpenChatbot === "function") {
                    onOpenChatbot({ fileIds });
                  }
                }}
                style={{ marginLeft: "8px" }}
              >
                💬 OPEN CHATBOT
              </button>
            )}
            {phase !== "idle" && (
              <button
                className="btn-ghost"
                onClick={() => (jobId ? abortJob() : reset())}
                style={{ marginLeft: "8px", color: C.red, borderColor: C.red }}
              >
                ■ ABORT
              </button>
            )}
          </div>
        </header>

        {/* ══ MAIN GRID (12 cols) ══════════════════════════════════════════════ */}
        <main
          style={{
            display: "grid",
            gridTemplateColumns: "3fr 6fr 3fr",
            gap: "20px",
            padding: "20px 24px",
            flex: 1,
          }}
        >
          {/* ── COL 1: LEFT ───────────────────────────────────────────────── */}
          <div
            style={{ display: "flex", flexDirection: "column", gap: "20px" }}
          >
            {/* Engine Telemetry */}
            <section
              style={{
                background: "#000",
                border: `1px solid ${C.grid}`,
                padding: "14px",
                order: 2,
              }}
            >
              <div
                style={{
                  fontSize: "10px",
                  fontWeight: "900",
                  textTransform: "uppercase",
                  letterSpacing: "3px",
                  color: C.muted,
                  marginBottom: "12px",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                }}
              >
                <span>⬡</span> ENGINE_TELEMETRY_V4
              </div>
              <div
                style={{
                  display: "flex",
                  gap: "4px",
                  alignItems: "flex-end",
                  height: "48px",
                  marginBottom: "10px",
                }}
              >
                {STEPS.map((s, i) => {
                  const done = doneIds.includes(s.id);
                  const active = curStep === i && phase === "running";
                  const h = done ? 42 : active ? (progress / 100) * 42 : 6;
                  return (
                    <div
                      key={i}
                      style={{
                        flex: 1,
                        background: done
                          ? `${s.color}55`
                          : active
                            ? `${s.color}33`
                            : "#1a1a1a",
                        height: `${h}px`,
                        borderTop: `2px solid ${done || active ? s.color : "#1a1a1a"}`,
                        transition: "height .3s ease",
                      }}
                    />
                  );
                })}
              </div>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  fontSize: "10px",
                  fontWeight: "700",
                }}
              >
                <span
                  style={{
                    color: C.muted,
                    textTransform: "uppercase",
                    letterSpacing: "1px",
                  }}
                >
                  MODEL_CONFIDENCE
                </span>
                <span style={{ color: C.yellow, fontStyle: "italic" }}>
                  {modelConfidenceValue != null
                    ? `${modelConfidenceValue.toFixed(1)}%`
                    : "—"}
                </span>
              </div>
            </section>

            {/* Completed sectors */}
            {doneIds.length > 0 && (
              <section
                className="skeuo-card"
                style={{ padding: "14px", order: 3 }}
              >
                <div
                  style={{
                    fontSize: "9px",
                    color: C.muted,
                    fontWeight: "700",
                    letterSpacing: "2px",
                    textTransform: "uppercase",
                    marginBottom: "10px",
                  }}
                >
                  COMPLETED SECTORS — {doneIds.length}/{STEPS.length}
                </div>
                {doneIds.map((id, i) => {
                  const s = STEPS.find((x) => x.id === id);
                  if (!s) return null;
                  return (
                    <div
                      key={id}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                        padding: "6px 0",
                        borderBottom: `1px solid ${C.grid}`,
                        animation: "slideRow .3s ease",
                      }}
                    >
                      <span
                        style={{
                          fontFamily: "monospace",
                          fontSize: "11px",
                          color: "#f8fafc",
                          width: "16px",
                        }}
                      >
                        {i + 1}
                      </span>
                      <span
                        style={{
                          fontSize: "10px",
                          fontWeight: "700",
                          flex: 1,
                          textTransform: "uppercase",
                          letterSpacing: "1px",
                          color: id === newId ? s.color : C.muted,
                        }}
                      >
                        {s.short}
                      </span>
                      <span
                        style={{
                          fontSize: "9px",
                          color: s.color,
                          fontWeight: "900",
                          fontStyle: "italic",
                        }}
                      >
                        ✓ DONE
                      </span>
                    </div>
                  );
                })}
              </section>
            )}

            {/* Track mini */}
            {phase !== "idle" && (
              <section
                className="skeuo-card"
                style={{ padding: "12px", aspectRatio: "1", order: 1 }}
              >
                <div
                  style={{
                    fontSize: "9px",
                    color: C.muted,
                    fontWeight: "700",
                    letterSpacing: "2px",
                    textTransform: "uppercase",
                    marginBottom: "8px",
                  }}
                >
                  ◉ RACE CIRCUIT
                </div>
                <TrackMap
                  progress={trackProg}
                  currentStep={curStep}
                  completedSteps={doneIds}
                  stepProgress={progress}
                />
              </section>
            )}
          </div>

          {/* ── COL 2: CENTRE ─────────────────────────────────────────────── */}
          <div
            style={{ display: "flex", flexDirection: "column", gap: "20px" }}
          >
            {/* HERO CARD */}
            {phase === "idle" ? (
              <section
                style={{
                  background: "#000",
                  border: `4px solid ${C.primary}`,
                  padding: "28px",
                  position: "relative",
                  animation: "slideInUp .4s ease",
                }}
              >
                <div
                  style={{
                    position: "absolute",
                    top: 0,
                    right: 0,
                    background: C.primary,
                    padding: "4px 16px",
                    fontSize: "11px",
                    fontWeight: "900",
                    fontStyle: "italic",
                    letterSpacing: "1px",
                  }}
                >
                  THE STEWARD'S VERDICT
                </div>
                <div style={{ textAlign: "center", paddingTop: "16px" }}>
                  <h2
                    style={{
                      fontSize: "28px",
                      fontWeight: "900",
                      fontStyle: "italic",
                      textTransform: "uppercase",
                      letterSpacing: "-.03em",
                      marginBottom: "8px",
                      lineHeight: "1.1",
                    }}
                  >
                    Load Document
                    <br />
                    To Begin Race
                  </h2>
                  <p
                    style={{
                      color: C.muted,
                      fontSize: "12px",
                      fontWeight: "600",
                      textTransform: "uppercase",
                      letterSpacing: "2px",
                      marginBottom: "20px",
                    }}
                  >
                    Paste policy paper, government report or research article
                  </p>
                  <textarea
                    rows={4}
                    value={inputText}
                    onChange={(e) => {
                      setInputText(e.target.value);
                      setInputError("");
                    }}
                    placeholder={"Paste document content here..."}
                    style={{ maxWidth: "500px", width: "100%" }}
                  />
                  {inputError && (
                    <div
                      style={{
                        margin: "8px auto",
                        padding: "8px 12px",
                        background: "#1a0000",
                        border: `1px solid ${C.red}`,
                        color: "#fca5a5",
                        fontFamily: "monospace",
                        fontSize: "10px",
                        maxWidth: "500px",
                        textAlign: "left",
                      }}
                    >
                      ⚠ {inputError}
                    </div>
                  )}
                  <div
                    style={{
                      display: "flex",
                      gap: "8px",
                      justifyContent: "center",
                      flexWrap: "wrap",
                      margin: "12px 0",
                      alignItems: "center",
                    }}
                  >
                    <button
                      className="btn-ghost"
                      onClick={() => fileRef.current?.click()}
                    >
                      📎 Upload Files
                    </button>
                    <input
                      ref={fileRef}
                      type="file"
                      accept=".pdf,.txt,.docx,.xml,.json,.png,.jpg,.jpeg,.bmp,.tiff,.webp,.wav"
                      multiple
                      style={{ display: "none" }}
                      onChange={async (e) => {
                        const selected = Array.from(e.target.files || []);
                        if (!selected.length) return;
                        await uploadFiles(selected);
                        setInputText(`[Files: ${selected.length}]`);
                      }}
                      disabled={isUploading}
                    />
                    {uploadedFiles.length > 0 && (
                      <span
                        style={{
                          fontFamily: "monospace",
                          fontSize: "9px",
                          color: C.green,
                        }}
                      >
                        ✓ {uploadedFiles.length} file(s) selected
                      </span>
                    )}
                  </div>
                  <div style={{ maxWidth: "340px", margin: "0 auto" }}>
                    <button className="btn-primary" onClick={handleRun}>
                      🏁 GREEN FLAG — START ANALYSIS
                    </button>
                  </div>
                </div>
              </section>
            ) : showVerdict && verdictStep ? (
              /* ── VERDICT CARD ── */
              <section
                style={{
                  background: "#000",
                  border: `4px solid ${verdictStep.color}`,
                  padding: "28px",
                  position: "relative",
                  boxShadow: `0 0 40px ${verdictStep.color}22`,
                  animation: "verdictIn .35s ease",
                }}
              >
                {/* Countdown bar */}
                <div
                  style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    right: 0,
                    height: "3px",
                    background: "#111",
                  }}
                >
                  <div
                    style={{
                      height: "100%",
                      background: verdictStep.color,
                      width: `${(verdictCountdown / 5) * 100}%`,
                      transition: "width .1s linear",
                    }}
                  />
                </div>

                <div
                  style={{
                    position: "absolute",
                    top: 0,
                    right: 0,
                    background: verdictStep.color,
                    padding: "4px 16px",
                    fontSize: "11px",
                    fontWeight: "900",
                    fontStyle: "italic",
                    letterSpacing: "1px",
                    color: "#000",
                  }}
                >
                  THE STEWARD'S VERDICT
                </div>

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "2fr 1fr",
                    gap: "28px",
                    paddingTop: "12px",
                  }}
                >
                  {/* Left */}
                  <div>
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                        marginBottom: "10px",
                      }}
                    >
                      <span
                        style={{
                          background: verdictStep.color,
                          padding: "2px 8px",
                          fontSize: "9px",
                          fontWeight: "900",
                          fontStyle: "italic",
                          letterSpacing: "1px",
                          color:
                            verdictStep.color === C.yellow ? "#000" : "#fff",
                        }}
                      >
                        {verdictStep.verdict.flash}
                      </span>
                      <span
                        style={{
                          fontSize: "9px",
                          color: C.muted,
                          fontFamily: "monospace",
                        }}
                      >
                        {verdictStep.sector} · {verdictStep.short}
                      </span>
                      <span
                        style={{
                          marginLeft: "auto",
                          fontSize: "10px",
                          color: C.muted,
                          fontFamily: "monospace",
                        }}
                      >
                        NEXT IN {verdictCountdown.toFixed(1)}s
                      </span>
                    </div>
                    <h2
                      style={{
                        fontSize: "26px",
                        fontWeight: "900",
                        fontStyle: "italic",
                        textTransform: "uppercase",
                        letterSpacing: "-.02em",
                        lineHeight: "1.1",
                        marginBottom: "8px",
                        color: "#fff",
                      }}
                    >
                      {verdictStep.verdict.title}
                    </h2>
                    <p
                      style={{
                        color: C.muted,
                        fontSize: "12px",
                        fontWeight: "600",
                        textTransform: "uppercase",
                        letterSpacing: "1.5px",
                        marginBottom: "20px",
                        lineHeight: "1.7",
                      }}
                    >
                      {verdictStep.verdict.sub}
                    </p>
                    <div
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        gap: "10px",
                      }}
                    >
                      {/* Alert */}
                      <div
                        style={{
                          display: "flex",
                          gap: "14px",
                          padding: "12px 14px",
                          background: C.card,
                          border: `1px solid ${C.grid}`,
                        }}
                      >
                        <span
                          style={{
                            color: verdictStep.color,
                            fontSize: "18px",
                            fontWeight: "900",
                            flexShrink: 0,
                          }}
                        >
                          !
                        </span>
                        <div>
                          <div
                            style={{
                              fontSize: "10px",
                              fontWeight: "900",
                              textTransform: "uppercase",
                              fontStyle: "italic",
                              color: verdictStep.color,
                              letterSpacing: "1px",
                              marginBottom: "4px",
                            }}
                          >
                            {verdictStep.verdict.alertLabel}
                          </div>
                          <div
                            style={{
                              fontSize: "12px",
                              fontWeight: "700",
                              lineHeight: "1.6",
                            }}
                          >
                            {verdictStep.verdict.alertText}
                          </div>
                        </div>
                      </div>
                      {/* Action */}
                      <div
                        style={{
                          display: "flex",
                          gap: "14px",
                          padding: "12px 14px",
                          background: C.card,
                          border: `1px solid ${C.grid}`,
                          opacity: 0.85,
                        }}
                      >
                        <span
                          style={{
                            color: C.yellow,
                            fontSize: "18px",
                            flexShrink: 0,
                          }}
                        >
                          ↗
                        </span>
                        <div>
                          <div
                            style={{
                              fontSize: "10px",
                              fontWeight: "900",
                              textTransform: "uppercase",
                              fontStyle: "italic",
                              color: C.yellow,
                              letterSpacing: "1px",
                              marginBottom: "4px",
                            }}
                          >
                            {verdictStep.verdict.actionLabel}
                          </div>
                          <div
                            style={{
                              fontSize: "12px",
                              fontWeight: "700",
                              lineHeight: "1.6",
                              color: "#e2e8f0",
                            }}
                          >
                            {verdictStep.verdict.actionText}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Right: big numbers */}
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      justifyContent: "space-between",
                      borderLeft: `1px solid ${C.grid}`,
                      paddingLeft: "24px",
                    }}
                  >
                    <div>
                      <div
                        style={{
                          fontSize: "9px",
                          color: C.muted,
                          fontWeight: "900",
                          textTransform: "uppercase",
                          letterSpacing: "1px",
                          marginBottom: "4px",
                        }}
                      >
                        {verdictStep.verdict.riskLabel}
                      </div>
                      <div
                        style={{
                          fontSize: "42px",
                          fontWeight: "900",
                          fontStyle: "italic",
                          color: verdictStep.color,
                          lineHeight: "1",
                        }}
                      >
                        {verdictStep.verdict.riskIndex}
                      </div>
                    </div>
                    <div>
                      <div
                        style={{
                          fontSize: "9px",
                          color: C.muted,
                          fontWeight: "900",
                          textTransform: "uppercase",
                          letterSpacing: "1px",
                          marginBottom: "4px",
                        }}
                      >
                        {verdictStep.verdict.economicLabel}
                      </div>
                      <div
                        style={{
                          fontSize: "36px",
                          fontWeight: "900",
                          fontStyle: "italic",
                          color: C.yellow,
                          lineHeight: "1",
                        }}
                      >
                        {verdictStep.verdict.economicVal}
                      </div>
                    </div>
                    <button
                      className="btn-primary"
                      style={{
                        marginTop: "8px",
                        fontSize: "11px",
                        padding: "12px 8px",
                      }}
                      onClick={() => downloadReport("json")}
                    >
                      DOWNLOAD BRIEFING
                    </button>
                  </div>
                </div>

                {/* Big stat numbers row */}
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(4,1fr)",
                    gap: "8px",
                    marginTop: "20px",
                    paddingTop: "16px",
                    borderTop: `1px solid ${C.grid}`,
                  }}
                >
                  {verdictStep.verdict.stats.map((s, i) => (
                    <div
                      key={i}
                      style={{
                        background: C.card,
                        border: `1px solid ${C.grid}`,
                        padding: "10px 8px",
                        textAlign: "center",
                      }}
                    >
                      <div
                        style={{
                          fontSize: "8px",
                          color: C.muted,
                          fontWeight: "700",
                          textTransform: "uppercase",
                          letterSpacing: "1px",
                          marginBottom: "4px",
                        }}
                      >
                        {s.k}
                      </div>
                      <div
                        style={{
                          fontSize: "20px",
                          fontWeight: "900",
                          fontStyle: "italic",
                          color: verdictStep.color,
                          lineHeight: "1",
                        }}
                      >
                        {s.v}
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            ) : (
              /* ── LIVE PROCESS CARD ── */
              <section
                style={{
                  background: "#000",
                  border: `4px solid ${stepColor}`,
                  padding: "24px",
                  position: "relative",
                  boxShadow: `0 0 30px ${stepColor}18`,
                }}
              >
                <div
                  style={{
                    position: "absolute",
                    top: 0,
                    right: 0,
                    background: stepColor,
                    padding: "4px 16px",
                    fontSize: "11px",
                    fontWeight: "900",
                    fontStyle: "italic",
                    color: stepColor === C.yellow ? "#000" : "#fff",
                  }}
                >
                  ◉ RUNNING
                </div>

                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "10px",
                    marginBottom: "10px",
                    paddingTop: "8px",
                  }}
                >
                  <span
                    style={{
                      background: stepColor,
                      padding: "2px 8px",
                      fontSize: "9px",
                      fontWeight: "900",
                      color: stepColor === C.yellow ? "#000" : "#fff",
                      letterSpacing: "1px",
                    }}
                  >
                    {step?.sector}
                  </span>
                  <span
                    style={{
                      fontSize: "9px",
                      color: C.muted,
                      fontFamily: "monospace",
                      letterSpacing: "1px",
                    }}
                  >
                    {step?.short} · {Math.round(progress)}% COMPLETE
                  </span>
                </div>

                <h2
                  style={{
                    fontSize: "26px",
                    fontWeight: "900",
                    fontStyle: "italic",
                    textTransform: "uppercase",
                    letterSpacing: "-.02em",
                    lineHeight: "1.1",
                    marginBottom: "6px",
                    color: "#fff",
                  }}
                >
                  {step?.label.toUpperCase()}
                </h2>
                <p
                  style={{
                    color: C.muted,
                    fontSize: "11px",
                    fontWeight: "600",
                    letterSpacing: "1px",
                    marginBottom: "18px",
                    lineHeight: "1.6",
                    textTransform: "uppercase",
                  }}
                >
                  {step?.desc}
                </p>

                {/* Master bar */}
                <div style={{ marginBottom: "20px" }}>
                  <div
                    className="skeuo-inset"
                    style={{
                      height: "12px",
                      background: "#000",
                      marginBottom: "4px",
                    }}
                  >
                    <div
                      style={{
                        height: "100%",
                        background: `linear-gradient(90deg,${stepColor}88,${stepColor})`,
                        width: `${progress}%`,
                        transition: "width .1s linear",
                      }}
                    />
                  </div>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      fontSize: "9px",
                      fontWeight: "700",
                      textTransform: "uppercase",
                    }}
                  >
                    <span style={{ color: C.muted }}>STAGE PROGRESS</span>
                    <span style={{ color: stepColor, fontStyle: "italic" }}>
                      {Math.round(progress)}%
                    </span>
                  </div>
                </div>

                {/* Sub tasks 2 col */}
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr 1fr",
                    gap: "8px 20px",
                    marginBottom: "20px",
                  }}
                >
                  {step?.subTasks.map((st, i) => {
                    const r = subRanges[i];
                    const p2 = progress / 100;
                    const done = p2 >= r.end,
                      active = !done && p2 >= r.start;
                    const lp = active
                      ? Math.min(
                          100,
                          ((p2 - r.start) / (r.end - r.start)) * 100,
                        )
                      : done
                        ? 100
                        : 0;
                    return (
                      <div
                        key={i}
                        style={{
                          opacity: !done && !active ? 0.2 : 1,
                          transition: "opacity .3s",
                        }}
                      >
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "6px",
                            marginBottom: "3px",
                          }}
                        >
                          <span
                            style={{
                              fontSize: "10px",
                              color: done
                                ? C.green
                                : active
                                  ? stepColor
                                  : "#2a2a2a",
                              fontFamily: "monospace",
                              fontWeight: "900",
                              width: "12px",
                              flexShrink: 0,
                            }}
                          >
                            {done ? "✓" : active ? "▶" : "·"}
                          </span>
                          <span
                            style={{
                              fontSize: "10px",
                              fontWeight: "700",
                              textTransform: "uppercase",
                              letterSpacing: ".5px",
                              color: done
                                ? C.muted
                                : active
                                  ? "#fff"
                                  : "#94a3b8",
                            }}
                          >
                            {st.label}
                          </span>
                          {active && (
                            <span
                              style={{
                                marginLeft: "auto",
                                fontSize: "9px",
                                color: stepColor,
                                fontFamily: "monospace",
                                fontWeight: "700",
                              }}
                            >
                              {Math.round(lp)}%
                            </span>
                          )}
                        </div>
                        <div
                          style={{
                            marginLeft: "18px",
                            height: "3px",
                            background: "#111",
                          }}
                        >
                          <div
                            style={{
                              height: "100%",
                              background: done ? `${stepColor}44` : stepColor,
                              width: `${lp}%`,
                              transition: "width .1s linear",
                            }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* Metrics grid */}
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(6,1fr)",
                    gap: "6px",
                    paddingTop: "16px",
                    borderTop: `1px solid ${C.grid}`,
                  }}
                >
                  {liveMetrics.map((m, i) => {
                    const shown =
                      progress / 100 > i / Math.max(liveMetrics.length, 1);
                    return (
                      <div
                        key={i}
                        style={{
                          background: C.card,
                          border: `1px solid ${shown ? stepColor + "44" : C.grid}`,
                          padding: "8px 6px",
                          textAlign: "center",
                          transition: "border-color .4s",
                        }}
                      >
                        <div
                          style={{
                            fontSize: "8px",
                            color: C.muted,
                            fontWeight: "700",
                            textTransform: "uppercase",
                            marginBottom: "3px",
                            letterSpacing: "1px",
                          }}
                        >
                          {m.key}
                        </div>
                        <div
                          style={{
                            fontSize: "12px",
                            fontWeight: "900",
                            fontStyle: "italic",
                            color: shown ? stepColor : "#cbd5e1",
                            transition: "color .5s",
                          }}
                        >
                          {shown ? m.val : "·"}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </section>
            )}

            {/* Middle row: Track Map Analysis + Scrutineering */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: "20px",
              }}
            >
              {/* Track Map Analysis / Topics */}
              <section
                className="skeuo-card"
                style={{ padding: "16px", order: 3 }}
              >
                <div className="section-title">
                  Track Map Analysis{" "}
                  <span className="section-sub">/ Topics</span>
                </div>
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "14px",
                  }}
                >
                  {topics.map((t, i) => (
                    <div key={i}>
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          fontSize: "10px",
                          fontWeight: "700",
                          textTransform: "uppercase",
                          marginBottom: "5px",
                        }}
                      >
                        <span>{t.label}</span>
                        <span>{panelDataLoaded ? `${t.pct}%` : "—"}</span>
                      </div>
                      <div
                        className="skeuo-inset"
                        style={{ height: "16px", background: "#000" }}
                      >
                        <div
                          style={{
                            height: "100%",
                            background: t.color,
                            width: panelDataLoaded ? `${t.pct}%` : "0%",
                            transition: "width 1s ease",
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </section>

              {/* Scrutineering / Clauses */}
              <section
                className="skeuo-card"
                style={{ padding: "16px", order: 4 }}
              >
                <div className="section-title">
                  Scrutineering <span className="section-sub">/ Clauses</span>
                </div>
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "8px",
                    maxHeight: "240px",
                    overflowY: "auto",
                    paddingRight: "4px",
                  }}
                >
                  {clauses.map((cl, i) => (
                    <div
                      key={i}
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "flex-start",
                        gap: "6px",
                        padding: "10px 12px",
                        background: "#000",
                        borderLeft: `3px solid ${cl.color}`,
                        minHeight: "72px",
                        maxHeight: "90px",
                        overflow: "hidden",
                      }}
                    >
                      <div
                        style={{
                          width: "100%",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          gap: "8px",
                        }}
                      >
                        <span
                          style={{
                            fontSize: "10px",
                            fontWeight: "700",
                            textTransform: "uppercase",
                            letterSpacing: "1px",
                          }}
                        >
                          {cl.label}
                        </span>
                        <button
                          className="btn-ghost"
                          onClick={() =>
                            toggleExpandedDetail({
                              key: `clause-${i}`,
                              kind: "CLAUSE",
                              title: cl.label,
                              color: cl.color,
                              body: String(cl.val || ""),
                            })
                          }
                          style={{ padding: "3px 8px", fontSize: "8px" }}
                        >
                          {expandedDetail?.key === `clause-${i}`
                            ? "CONTRACT"
                            : "EXPAND"}
                        </button>
                      </div>
                      <span
                        style={{
                          fontSize: "11px",
                          fontWeight: "700",
                          lineHeight: "1.35",
                          color: "#e2e8f0",
                          textTransform: "none",
                          display: "-webkit-box",
                          WebkitLineClamp: 2,
                          WebkitBoxOrient: "vertical",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          wordBreak: "break-word",
                          overflowWrap: "anywhere",
                        }}
                      >
                        {trimText(cl.val, 180)}
                      </span>
                    </div>
                  ))}
                </div>
              </section>
            </div>

            {/* Race Strategy / Recommendations */}
            <section
              className="skeuo-card"
              style={{ padding: "16px", order: 2 }}
            >
              <div className="section-title">
                Race Strategy{" "}
                <span className="section-sub">/ Recommendations</span>
              </div>
              <div
                style={{
                  marginBottom: "12px",
                  fontSize: "10px",
                  color: panelDataError ? C.red : C.muted,
                  textTransform: "uppercase",
                  letterSpacing: "1px",
                  fontWeight: "700",
                }}
              >
                {pipelineStatusNote}
              </div>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(3,minmax(0,1fr))",
                  gap: "12px",
                }}
              >
                {recommendations.slice(0, 3).map((item, i) => {
                  const priority = String(
                    item.priority || "INFO",
                  ).toUpperCase();
                  const priorityColor =
                    priority === "IMMEDIATE"
                      ? C.primary
                      : priority === "STRATEGIC"
                        ? C.yellow
                        : C.cyan;
                  const priorityTextColor =
                    priority === "STRATEGIC" ? "#000" : "#fff";

                  return (
                    <div
                      key={i}
                      style={{
                        background: "#000",
                        border: `1px solid ${C.grid}`,
                        padding: "16px 14px",
                        position: "relative",
                        paddingTop: "20px",
                        minHeight: "140px",
                        maxHeight: "160px",
                        overflow: "hidden",
                      }}
                    >
                      <div
                        style={{
                          position: "absolute",
                          top: "-2px",
                          left: "-2px",
                          background: priorityColor,
                          padding: "3px 10px",
                          fontSize: "9px",
                          fontWeight: "900",
                          color: priorityTextColor,
                          letterSpacing: "1px",
                        }}
                      >
                        {priority}
                      </div>
                      <div
                        style={{
                          width: "100%",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          gap: "8px",
                          marginTop: "4px",
                          marginBottom: "4px",
                        }}
                      >
                        <span
                          style={{
                            fontSize: "9px",
                            color: C.muted,
                            textTransform: "uppercase",
                            letterSpacing: "1px",
                            fontWeight: "700",
                          }}
                        >
                          DETAIL
                        </span>
                        <button
                          className="btn-ghost"
                          onClick={() =>
                            toggleExpandedDetail({
                              key: `recommendation-${i}`,
                              kind: "RECOMMENDATION",
                              title: priority,
                              color: priorityColor,
                              body: String(item.text || ""),
                            })
                          }
                          style={{ padding: "3px 8px", fontSize: "8px" }}
                        >
                          {expandedDetail?.key === `recommendation-${i}`
                            ? "CONTRACT"
                            : "EXPAND"}
                        </button>
                      </div>
                      <div
                        style={{
                          fontSize: "11px",
                          fontWeight: "700",
                          lineHeight: "1.5",
                          color: panelDataError ? "#94a3b8" : C.text,
                          textTransform: "none",
                          display: "-webkit-box",
                          WebkitLineClamp: 6,
                          WebkitBoxOrient: "vertical",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          wordBreak: "break-word",
                          overflowWrap: "anywhere",
                        }}
                      >
                        {trimText(item.text, 260)}
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>
          </div>

          {/* ── COL 3: RIGHT ──────────────────────────────────────────────── */}
          <div
            style={{ display: "flex", flexDirection: "column", gap: "20px" }}
          >
            {/* Race Results / Insights */}
            <section
              className="skeuo-card"
              style={{ padding: "16px", order: 2 }}
            >
              <div className="section-title">
                Race Results <span className="section-sub">/ Insights</span>
              </div>
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "10px",
                  maxHeight: "380px",
                  overflowY: "auto",
                  paddingRight: "4px",
                }}
              >
                {insights.map((ins, i) => (
                  <div
                    key={i}
                    style={{
                      background: "#000",
                      border: `1px solid ${C.grid}`,
                      padding: "12px",
                      opacity: ins.shown ? 1 : 0.2,
                      transition: "opacity .5s",
                      animation: ins.shown ? "slideRow .4s ease" : "none",
                      minHeight: "92px",
                      maxHeight: "140px",
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        marginBottom: "6px",
                      }}
                    >
                      <span
                        style={{
                          fontSize: "10px",
                          fontWeight: "900",
                          fontStyle: "italic",
                          color: ins.color,
                          letterSpacing: "1px",
                        }}
                      >
                        {ins.id}
                      </span>
                      <span
                        style={{
                          fontSize: "9px",
                          color: C.muted,
                          fontWeight: "700",
                          textTransform: "uppercase",
                          display: "flex",
                          alignItems: "center",
                          gap: "8px",
                        }}
                      >
                        <button
                          className="btn-ghost"
                          onClick={() =>
                            toggleExpandedDetail({
                              key: `insight-${i}`,
                              kind: "INSIGHT",
                              title: ins.id,
                              color: ins.color,
                              body: String(ins.text || ""),
                            })
                          }
                          style={{ padding: "3px 8px", fontSize: "8px" }}
                        >
                          {expandedDetail?.key === `insight-${i}`
                            ? "CONTRACT"
                            : "EXPAND"}
                        </button>
                        {ins.shown ? ins.conf : "—"}
                      </span>
                    </div>
                    <div
                      style={{
                        fontSize: "11px",
                        fontWeight: "700",
                        textTransform: "none",
                        lineHeight: "1.5",
                        color: ins.shown ? "#fff" : "#222",
                        display: "-webkit-box",
                        WebkitLineClamp: 5,
                        WebkitBoxOrient: "vertical",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        wordBreak: "break-word",
                        overflowWrap: "anywhere",
                      }}
                    >
                      {trimText(ins.text, 520)}
                    </div>
                  </div>
                ))}
              </div>
            </section>

            {/* Constructors Standings / Impact */}
            <section className="skeuo-card" style={{ padding: "16px" }}>
              <div className="section-title">
                Constructors Standings{" "}
                <span className="section-sub">/ Impact</span>
              </div>
              <div
                style={{ display: "flex", flexDirection: "column", gap: "8px" }}
              >
                {standings.map((s, i) => (
                  <div
                    key={i}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "10px",
                    }}
                  >
                    <span
                      style={{
                        fontSize: "11px",
                        fontWeight: "900",
                        color: C.muted,
                        width: "24px",
                        flexShrink: 0,
                        fontFamily: "monospace",
                      }}
                    >
                      {s.rank}
                    </span>
                    <div
                      style={{
                        flex: 1,
                        background: "#000",
                        height: "32px",
                        display: "flex",
                        alignItems: "center",
                        paddingLeft: "10px",
                        border: `1px solid ${C.grid}`,
                        position: "relative",
                        overflow: "hidden",
                      }}
                    >
                      <div
                        style={{
                          position: "absolute",
                          inset: 0,
                          background: `${s.color}22`,
                          width: `${(s.score / s.max) * 100}%`,
                          transition: "width 1.2s ease",
                        }}
                      />
                      <span
                        style={{
                          fontSize: "10px",
                          fontWeight: "900",
                          textTransform: "uppercase",
                          letterSpacing: "1px",
                          position: "relative",
                          zIndex: 1,
                        }}
                      >
                        {s.label}
                      </span>
                      <span
                        style={{
                          marginLeft: "auto",
                          marginRight: "10px",
                          fontSize: "13px",
                          fontWeight: "900",
                          fontStyle: "italic",
                          position: "relative",
                          zIndex: 1,
                          color: s.score > 0 ? C.text : "#f8fafc",
                        }}
                      >
                        {s.score > 0 ? s.score.toFixed(1) : "—"}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            {/* Track Conditions / Risk */}
            <section className="skeuo-card" style={{ padding: "16px" }}>
              <div className="section-title">
                Track Conditions <span className="section-sub">/ Risk</span>
              </div>
              <div
                style={{
                  display: "flex",
                  justifyContent: "center",
                  marginBottom: "16px",
                }}
              >
                <div
                  style={{
                    position: "relative",
                    width: "120px",
                    height: "120px",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <svg
                    viewBox="0 0 100 100"
                    width="120"
                    height="120"
                    style={{ position: "absolute", inset: 0 }}
                  >
                    <circle
                      cx="50"
                      cy="50"
                      r="45"
                      fill="none"
                      stroke="#1a1a1a"
                      strokeWidth="8"
                    />
                    <circle
                      cx="50"
                      cy="50"
                      r="45"
                      fill="none"
                      stroke={riskColor}
                      strokeWidth="8"
                      strokeDasharray={`${riskDash} ${riskCircumference}`}
                      strokeDashoffset={riskCircumference * 0.25}
                      strokeLinecap="round"
                      style={{
                        transition: "stroke-dasharray 1s ease,stroke .5s",
                      }}
                    />
                  </svg>
                  <div
                    style={{
                      textAlign: "center",
                      position: "relative",
                      zIndex: 1,
                    }}
                  >
                    <div
                      style={{
                        fontSize: "8px",
                        color: C.muted,
                        fontWeight: "900",
                        textTransform: "uppercase",
                        letterSpacing: "1px",
                      }}
                    >
                      RISK LEVEL
                    </div>
                    <div
                      style={{
                        fontSize: "28px",
                        fontWeight: "900",
                        fontStyle: "italic",
                        color: riskColor,
                        lineHeight: "1",
                      }}
                    >
                      {riskVal > 0 ? riskVal.toFixed(1) : "—"}
                    </div>
                  </div>
                </div>
              </div>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: "8px",
                }}
              >
                {[
                  {
                    label: "Sentiment",
                    val: panelDataLoaded
                      ? (riskData.sentiment || "unknown").toUpperCase()
                      : "—",
                    color: C.green,
                  },
                  {
                    label: "Volatility",
                    val: panelDataLoaded
                      ? (riskData.volatility || "unknown").toUpperCase()
                      : "—",
                    color: C.yellow,
                  },
                ].map((item, i) => (
                  <div key={i} style={{ textAlign: "center" }}>
                    <div
                      style={{
                        fontSize: "9px",
                        color: C.muted,
                        fontWeight: "700",
                        textTransform: "uppercase",
                        letterSpacing: "1px",
                        marginBottom: "3px",
                      }}
                    >
                      {item.label}
                    </div>
                    <div
                      style={{
                        fontSize: "11px",
                        fontWeight: "700",
                        fontStyle: "italic",
                        textTransform: "uppercase",
                        color: item.color,
                      }}
                    >
                      {item.val}
                    </div>
                  </div>
                ))}
              </div>
            </section>

            {/* Pit Stop Stats */}
            <section
              className="skeuo-card"
              style={{
                padding: "16px",
                borderLeft: `4px solid ${C.primary}`,
                order: 1,
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: "16px",
                }}
              >
                <div className="section-title" style={{ margin: 0 }}>
                  Pit Stop Stats
                </div>
                <span
                  style={{
                    fontSize: "9px",
                    background: C.primary,
                    padding: "2px 8px",
                    fontWeight: "700",
                    letterSpacing: "1px",
                  }}
                >
                  REAL-TIME
                </span>
              </div>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: "10px",
                  marginBottom: "14px",
                }}
              >
                <div
                  className="skeuo-inset"
                  style={{
                    background: "#000",
                    border: `1px solid ${C.grid}`,
                    padding: "10px",
                  }}
                >
                  <div
                    style={{
                      fontSize: "9px",
                      color: C.muted,
                      fontWeight: "700",
                      textTransform: "uppercase",
                      marginBottom: "4px",
                    }}
                  >
                    Processed
                  </div>
                  <div
                    style={{
                      fontSize: "22px",
                      fontWeight: "900",
                      color: "#fff",
                      fontStyle: "italic",
                      lineHeight: "1",
                    }}
                  >
                    {statsData ? statsData.processed.toLocaleString() : "—"}
                  </div>
                  <div
                    style={{
                      fontSize: "9px",
                      color: C.green,
                      fontWeight: "700",
                      marginTop: "2px",
                    }}
                  >
                    {statsData
                      ? `${statsData.delta >= 0 ? "+" : ""}${statsData.delta.toFixed(1)}%`
                      : "STANDBY"}
                  </div>
                </div>
                <div
                  className="skeuo-inset"
                  style={{
                    background: "#000",
                    border: `1px solid ${C.grid}`,
                    padding: "10px",
                  }}
                >
                  <div
                    style={{
                      fontSize: "9px",
                      color: C.muted,
                      fontWeight: "700",
                      textTransform: "uppercase",
                      marginBottom: "4px",
                    }}
                  >
                    Accuracy
                  </div>
                  <div
                    style={{
                      fontSize: "22px",
                      fontWeight: "900",
                      color: C.yellow,
                      fontStyle: "italic",
                      lineHeight: "1",
                    }}
                  >
                    {statsData ? `${statsData.accuracy.toFixed(1)}%` : "—"}
                  </div>
                  <div
                    style={{
                      fontSize: "9px",
                      color: C.muted,
                      fontWeight: "700",
                      marginTop: "2px",
                    }}
                  >
                    {statsData ? "API DATA" : "STANDBY"}
                  </div>
                </div>
              </div>
              <div>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    fontSize: "10px",
                    fontWeight: "700",
                    textTransform: "uppercase",
                    marginBottom: "6px",
                  }}
                >
                  <span>Processing Velocity</span>
                  <span style={{ color: C.primary }}>
                    {statsData ? `${statsData.velocity.toFixed(1)} / idx` : "—"}
                  </span>
                </div>
                <div
                  className="skeuo-inset"
                  style={{
                    height: "52px",
                    background: "#000",
                    position: "relative",
                    overflow: "hidden",
                  }}
                >
                  <svg
                    style={{
                      position: "absolute",
                      inset: 0,
                      width: "100%",
                      height: "100%",
                    }}
                    preserveAspectRatio="none"
                    viewBox="0 0 100 40"
                  >
                    {hasVelocitySeries ? (
                      <>
                        <path d={velocityAreaPath} fill={`${C.primary}22`} />
                        <path
                          d={velocityLinePath}
                          fill="none"
                          stroke={C.primary}
                          strokeWidth="2"
                        />
                      </>
                    ) : (
                      <path
                        d="M0 40 L100 40"
                        fill="none"
                        stroke="#334155"
                        strokeWidth="1.5"
                        strokeDasharray="4 3"
                      />
                    )}
                  </svg>
                </div>
              </div>
            </section>
          </div>
        </main>

        {/* ══ FOOTER ══════════════════════════════════════════════════════════ */}
        <footer
          style={{
            borderTop: "4px solid #000",
            background: C.card,
            padding: "8px 24px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexShrink: 0,
            fontSize: "10px",
            fontWeight: "900",
            textTransform: "uppercase",
            letterSpacing: "1px",
            fontStyle: "italic",
          }}
        >
          <div style={{ display: "flex", gap: "32px", alignItems: "center" }}>
            {[
              { label: "SESSION_TIME", val: sessionTime, color: "#fff" },
              {
                label: "SYSTEM_TEMP",
                val: phase === "running" ? "OPTIMAL" : "STANDBY",
                color: C.green,
              },
              { label: "UPTIME", val: "99.999%", color: "#fff" },
            ].map((item, i) => (
              <div
                key={i}
                style={{ display: "flex", gap: "6px", alignItems: "center" }}
              >
                <span style={{ color: C.muted }}>{item.label}:</span>
                <span style={{ color: item.color }}>{item.val}</span>
              </div>
            ))}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
            <span style={{ color: C.muted }}>
              PROTOCOL: GP_AI_ANALYTICS_V2.0
            </span>
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <span
                style={{
                  width: "6px",
                  height: "6px",
                  background: C.primary,
                  borderRadius: "50%",
                  display: "inline-block",
                  animation: phase === "running" ? "pulse 1s infinite" : "none",
                }}
              />
              <span>
                {phase === "running"
                  ? "ENCRYPTED_LINK_ESTABLISHED"
                  : "LINK_STANDBY"}
              </span>
            </div>
          </div>
        </footer>
      </div>

      {expandedDetail && (
        <div
          onClick={() => setExpandedDetail(null)}
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.6)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "24px",
            zIndex: 120,
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              width: "min(900px, 92vw)",
              height: "min(72vh, 620px)",
              background: "#07090f",
              border: `2px solid ${expandedDetail.color || C.primary}`,
              boxShadow: "10px 10px 0 #000",
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
              transform: "scale(1)",
              transition: "all .22s ease",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                padding: "10px 12px",
                borderBottom: `1px solid ${C.grid}`,
                background: "#000",
              }}
            >
              <div
                style={{
                  fontSize: "11px",
                  letterSpacing: "1px",
                  textTransform: "uppercase",
                  fontWeight: "900",
                  color: expandedDetail.color || C.primary,
                }}
              >
                {expandedDetail.kind} / {expandedDetail.title}
              </div>
              <button
                className="btn-ghost"
                onClick={() => setExpandedDetail(null)}
                style={{ fontSize: "9px" }}
              >
                CONTRACT
              </button>
            </div>

            <div
              style={{
                padding: "14px",
                fontSize: "13px",
                lineHeight: "1.6",
                color: "#f8fafc",
                overflowY: "auto",
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
                overflowWrap: "anywhere",
                textTransform: "none",
              }}
            >
              {expandedDetail.body}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
