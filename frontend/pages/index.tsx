import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { apiClient, LeaderboardEntry } from "../hooks/useApi";
import {
  ScoreBar, AASScore, StatusBadge, EloTier, ConfidenceBand
} from "../components/Charts";

const DIMS = [
  { key: "goal_completion", label: "Goal",       color: "#3b82f6" },
  { key: "hallucination",   label: "Anti-Halluc", color: "#7c3aed" },
  { key: "safety",          label: "Safety",     color: "#10b981" },
  { key: "adversarial",     label: "Adversarial", color: "#f97316" },
  { key: "cost",            label: "Cost Eff.",  color: "#f59e0b" },
];

const DEFAULT_WEIGHTS = {
  goal_completion: 0.30,
  hallucination:   0.20,
  safety:          0.20,
  adversarial:     0.20,
  cost:            0.10,
};

export default function LeaderboardPage() {
  const [entries,     setEntries]     = useState<LeaderboardEntry[]>([]);
  const [loading,     setLoading]     = useState(true);
  const [weights,     setWeights]     = useState(DEFAULT_WEIGHTS);
  const [customMode,  setCustomMode]  = useState(false);
  const [filterType,  setFilterType]  = useState("");
  const [filterModel, setFilterModel] = useState("");
  const [selected,    setSelected]    = useState<string[]>([]);

  const fetchLeaderboard = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = {};
      if (filterType)  params.agent_type = filterType;
      if (filterModel) params.model      = filterModel;

      const data = customMode
        ? await apiClient.rerankLeaderboard(weights)
        : await apiClient.getLeaderboard(params);
      setEntries(data);
    } catch {
      // backend not running - show demo data
      setEntries(DEMO_DATA);
    } finally {
      setLoading(false);
    }
  }, [weights, customMode, filterType, filterModel]);

  useEffect(() => { fetchLeaderboard(); }, [fetchLeaderboard]);

  const handleWeightChange = (key: string, val: number) => {
    setWeights(w => ({ ...w, [key]: val / 100 }));
  };

  const toggleSelect = (id: string) => {
    setSelected(s =>
      s.includes(id) ? s.filter(x => x !== id) :
      s.length < 2   ? [...s, id] : [s[1], id]
    );
  };

  return (
    <div className="fade-in">
      {/* ── Header ── */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <h1 style={{ fontSize: 28, fontWeight: 800, letterSpacing: "-0.03em" }}>
              ⚔ AgentArena Leaderboard
            </h1>
            <span className="flex items-center gap-1.5 text-xs"
              style={{ color: "var(--green)", background: "rgba(16,185,129,0.1)",
                border: "1px solid rgba(16,185,129,0.3)", padding: "2px 8px", borderRadius: 20 }}>
              <span className="live-dot" /> LIVE
            </span>
          </div>
          <p style={{ color: "var(--subtle)", fontSize: 14 }}>
            The world's first adversarial benchmark for AI agents.&nbsp;
            <strong style={{ color: "var(--text)" }}>{entries.length} agents</strong> ranked.
          </p>
        </div>
        {selected.length === 2 && (
          <Link href={`/compare?a=${selected[0]}&b=${selected[1]}`}
            style={{
              background: "linear-gradient(135deg, #7c3aed, #3b82f6)",
              color: "#fff", padding: "8px 18px", borderRadius: 8,
              fontWeight: 600, fontSize: 13, textDecoration: "none",
            }}>
            Compare Selected ({selected.length}/2)
          </Link>
        )}
      </div>

      {/* ── Controls ── */}
      <div className="arena-card p-4 mb-6">
        <div className="flex flex-wrap items-center gap-4">
          {/* Filters */}
          <select value={filterType} onChange={e => setFilterType(e.target.value)}
            style={{ background: "var(--muted)", border: "1px solid var(--border)",
              color: "var(--text)", borderRadius: 6, padding: "5px 10px", fontSize: 13 }}>
            <option value="">All Types</option>
            <option value="langchain">LangChain</option>
            <option value="openai_assistants">OpenAI Assistants</option>
            <option value="autogpt">AutoGPT</option>
            <option value="crewai">CrewAI</option>
            <option value="custom">Custom</option>
          </select>

          <select value={filterModel} onChange={e => setFilterModel(e.target.value)}
            style={{ background: "var(--muted)", border: "1px solid var(--border)",
              color: "var(--text)", borderRadius: 6, padding: "5px 10px", fontSize: 13 }}>
            <option value="">All Models</option>
            <option value="gpt-4o">GPT-4o</option>
            <option value="claude-3-sonnet">Claude 3 Sonnet</option>
            <option value="claude-3-opus">Claude 3 Opus</option>
            <option value="gemini-1.5-pro">Gemini 1.5 Pro</option>
          </select>

          <div className="ml-auto flex items-center gap-3">
            <label className="flex items-center gap-2 cursor-pointer" style={{ fontSize: 13 }}>
              <div
                onClick={() => setCustomMode(c => !c)}
                style={{
                  width: 36, height: 20, borderRadius: 10,
                  background: customMode ? "var(--accent)" : "var(--muted)",
                  position: "relative", cursor: "pointer", transition: "background 0.2s",
                }}>
                <div style={{
                  position: "absolute", top: 2, left: customMode ? 18 : 2,
                  width: 16, height: 16, borderRadius: "50%",
                  background: "#fff", transition: "left 0.2s",
                }} />
              </div>
              <span style={{ color: customMode ? "var(--text)" : "var(--subtle)" }}>
                Custom Weights
              </span>
            </label>
          </div>
        </div>

        {/* Custom weight sliders */}
        {customMode && (
          <div className="mt-4 pt-4" style={{ borderTop: "1px solid var(--border)" }}>
            <p style={{ fontSize: 12, color: "var(--subtle)", marginBottom: 12 }}>
              Drag sliders to re-weight scoring. Leaderboard re-ranks instantly.
            </p>
            <div className="grid grid-cols-5 gap-4">
              {DIMS.map(dim => (
                <div key={dim.key}>
                  <div className="flex justify-between mb-1">
                    <span style={{ fontSize: 11, color: "var(--subtle)" }}>{dim.label}</span>
                    <span style={{ fontSize: 11, color: dim.color, fontFamily: "monospace" }}>
                      {Math.round((weights as any)[dim.key] * 100)}%
                    </span>
                  </div>
                  <input type="range" min={0} max={60} step={5}
                    value={Math.round((weights as any)[dim.key] * 100)}
                    onChange={e => handleWeightChange(dim.key, Number(e.target.value))}
                    style={{ width: "100%", accentColor: dim.color }}
                  />
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ── Table ── */}
      <div className="arena-card overflow-hidden">
        {/* Table header */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "48px 1fr 80px 80px 80px 80px 80px 80px 100px 70px",
          gap: 8, padding: "10px 16px",
          borderBottom: "1px solid var(--border)",
          fontSize: 11, fontWeight: 700, color: "var(--subtle)",
          textTransform: "uppercase", letterSpacing: "0.06em",
        }}>
          <span>Rank</span>
          <span>Agent</span>
          <span style={{ textAlign: "center" }}>AAS</span>
          <span style={{ textAlign: "center" }}>Goal</span>
          <span style={{ textAlign: "center" }}>Halluc</span>
          <span style={{ textAlign: "center" }}>Safety</span>
          <span style={{ textAlign: "center" }}>Advers</span>
          <span style={{ textAlign: "center" }}>Cost</span>
          <span style={{ textAlign: "center" }}>Elo</span>
          <span style={{ textAlign: "center" }}>Pass%</span>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-16"
            style={{ color: "var(--subtle)" }}>
            <span style={{ fontSize: 14 }}>Loading leaderboard…</span>
          </div>
        ) : entries.map((e, i) => (
          <LeaderboardRow
            key={e.agent_id}
            entry={e}
            selected={selected.includes(e.agent_id)}
            onSelect={() => toggleSelect(e.agent_id)}
          />
        ))}
      </div>

      {/* ── Select hint ── */}
      {selected.length > 0 && selected.length < 2 && (
        <div className="text-center mt-4" style={{ fontSize: 13, color: "var(--subtle)" }}>
          Select one more agent to compare →
        </div>
      )}
    </div>
  );
}

function LeaderboardRow({
  entry, selected, onSelect
}: { entry: LeaderboardEntry; selected: boolean; onSelect: () => void }) {
  const isTop3 = entry.rank <= 3;
  const rankColor = entry.rank === 1 ? "#f59e0b" : entry.rank === 2 ? "#94a3b8" : entry.rank === 3 ? "#cd7f32" : "var(--subtle)";

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "48px 1fr 80px 80px 80px 80px 80px 80px 100px 70px",
        gap: 8, padding: "12px 16px", alignItems: "center",
        borderBottom: "1px solid var(--border)",
        cursor: "pointer",
        background: selected ? "rgba(124,58,237,0.08)" : "transparent",
        transition: "background 0.15s",
      }}
      onClick={onSelect}
      onMouseEnter={e => {
        if (!selected) (e.currentTarget as HTMLElement).style.background = "rgba(255,255,255,0.02)";
      }}
      onMouseLeave={e => {
        if (!selected) (e.currentTarget as HTMLElement).style.background = "transparent";
      }}
    >
      {/* Rank */}
      <span style={{ fontWeight: 800, fontSize: 15, color: rankColor, fontFamily: "monospace" }}>
        {entry.rank === 1 ? "🥇" : entry.rank === 2 ? "🥈" : entry.rank === 3 ? "🥉" : `#${entry.rank}`}
      </span>

      {/* Agent name */}
      <div>
        <div className="flex items-center gap-2">
          <Link href={`/agent/${entry.agent_id}`}
            style={{ color: "var(--text)", fontWeight: 600, fontSize: 13,
              textDecoration: "none" }}
            onClick={e => e.stopPropagation()}>
            {entry.agent_name}
          </Link>
          {entry.is_verified && (
            <span style={{ fontSize: 10, color: "#3b82f6" }} title="Verified - ran full task suite">✓</span>
          )}
        </div>
        <div className="flex items-center gap-2 mt-0.5">
          <span style={{ fontSize: 10, color: "var(--subtle)", background: "var(--muted)",
            padding: "1px 5px", borderRadius: 3 }}>
            {entry.agent_type}
          </span>
          {entry.model_backbone && (
            <span style={{ fontSize: 10, color: "var(--subtle)" }}>{entry.model_backbone}</span>
          )}
          <EloTier elo={entry.elo_rating} />
        </div>
      </div>

      {/* AAS */}
      <div style={{ textAlign: "center" }}>
        <ConfidenceBand low={entry.confidence_low} high={entry.confidence_high} value={entry.aas_score} />
      </div>

      {/* Dimension scores */}
      {[entry.goal_completion, entry.hallucination, entry.safety, entry.adversarial, entry.cost].map((v, i) => (
        <div key={i} style={{ textAlign: "center" }}>
          <span style={{
            fontSize: 12, fontFamily: "monospace", fontWeight: 600,
            color: v >= 75 ? "#10b981" : v >= 50 ? "#f59e0b" : "#ef4444"
          }}>
            {v.toFixed(0)}
          </span>
        </div>
      ))}

      {/* Elo */}
      <div style={{ textAlign: "center" }}>
        <span style={{ fontFamily: "monospace", fontSize: 12, fontWeight: 700,
          color: isTop3 ? "#f59e0b" : "var(--text)" }}>
          {Math.round(entry.elo_rating)}
        </span>
      </div>

      {/* Pass % */}
      <div style={{ textAlign: "center" }}>
        <span style={{ fontFamily: "monospace", fontSize: 12,
          color: entry.pass_rate >= 70 ? "#10b981" : entry.pass_rate >= 40 ? "#f59e0b" : "#ef4444" }}>
          {entry.pass_rate.toFixed(0)}%
        </span>
      </div>
    </div>
  );
}

// ── Demo data (shown when backend is offline) ─────────────────────────────────

const DEMO_DATA: LeaderboardEntry[] = [
  { rank: 1, agent_id: "a1", agent_name: "GPT-4o ReAct Agent",    agent_type: "langchain", model_backbone: "gpt-4o",          aas_score: 87.4, goal_completion: 91.2, hallucination: 88.0, safety: 92.1, adversarial: 78.5, cost: 72.3, pass_rate: 84.0, elo_rating: 1721, is_verified: true,  runs_count: 12, confidence_low: 85.1, confidence_high: 89.7 },
  { rank: 2, agent_id: "a2", agent_name: "Claude 3 Opus Agent",   agent_type: "custom",    model_backbone: "claude-3-opus",   aas_score: 85.1, goal_completion: 88.0, hallucination: 91.3, safety: 95.0, adversarial: 72.0, cost: 61.0, pass_rate: 82.0, elo_rating: 1680, is_verified: true,  runs_count: 8,  confidence_low: 83.0, confidence_high: 87.2 },
  { rank: 3, agent_id: "a3", agent_name: "CrewAI Multi-Agent",    agent_type: "crewai",    model_backbone: "gpt-4-turbo",     aas_score: 79.2, goal_completion: 82.1, hallucination: 80.0, safety: 88.4, adversarial: 70.1, cost: 58.0, pass_rate: 76.0, elo_rating: 1590, is_verified: true,  runs_count: 5,  confidence_low: 76.8, confidence_high: 81.6 },
  { rank: 4, agent_id: "a4", agent_name: "Gemini 1.5 Pro Agent",  agent_type: "custom",    model_backbone: "gemini-1.5-pro",  aas_score: 74.8, goal_completion: 78.4, hallucination: 76.2, safety: 82.0, adversarial: 63.5, cost: 71.0, pass_rate: 70.0, elo_rating: 1530, is_verified: false, runs_count: 3,  confidence_low: 71.0, confidence_high: 78.6 },
  { rank: 5, agent_id: "a5", agent_name: "AutoGPT v2.1",          agent_type: "autogpt",   model_backbone: "gpt-3.5-turbo",   aas_score: 61.3, goal_completion: 65.0, hallucination: 60.8, safety: 70.2, adversarial: 52.1, cost: 88.4, pass_rate: 55.0, elo_rating: 1380, is_verified: true,  runs_count: 9,  confidence_low: 58.0, confidence_high: 64.6 },
  { rank: 6, agent_id: "a6", agent_name: "LangChain GPT-3.5",     agent_type: "langchain", model_backbone: "gpt-3.5-turbo",   aas_score: 54.7, goal_completion: 58.3, hallucination: 55.1, safety: 65.0, adversarial: 44.2, cost: 92.1, pass_rate: 48.0, elo_rating: 1290, is_verified: false, runs_count: 4,  confidence_low: 51.2, confidence_high: 58.2 },
];
