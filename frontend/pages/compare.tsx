import { useState, useEffect } from "react";
import { useRouter } from "next/router";
import { apiClient } from "../hooks/useApi";
import { AgentRadar, ScoreBar, EloTier } from "../components/Charts";

export default function ComparePage() {
  const router    = useRouter();
  const { a, b }  = router.query as { a?: string; b?: string };

  const [agentA, setAgentA] = useState("");
  const [agentB, setAgentB] = useState("");
  const [agents,  setAgents]  = useState<any[]>([]);
  const [result,  setResult]  = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    apiClient.listAgents().then(setAgents).catch(() => {});
    if (a) setAgentA(a);
    if (b) setAgentB(b);
  }, [a, b]);

  useEffect(() => {
    if (agentA && agentB) compare();
  }, [agentA, agentB]);

  const compare = async () => {
    if (!agentA || !agentB) return;
    setLoading(true);
    try {
      const data = await apiClient.compareAgents(agentA, agentB);
      setResult(data);
    } catch {
      setResult(DEMO_COMPARE);
    } finally {
      setLoading(false);
    }
  };

  const DIMS = [
    { key: "goal_completion", label: "Goal Completion",    color: "#3b82f6" },
    { key: "hallucination",   label: "Anti-Hallucination", color: "#7c3aed" },
    { key: "safety",          label: "Safety",             color: "#10b981" },
    { key: "adversarial",     label: "Adversarial Resist", color: "#f97316" },
    { key: "cost",            label: "Cost Efficiency",    color: "#f59e0b" },
  ];

  return (
    <div className="fade-in">
      <h1 style={{ fontSize: 24, fontWeight: 800, marginBottom: 4 }}>⚔ Head-to-Head Compare</h1>
      <p style={{ color: "var(--subtle)", fontSize: 14, marginBottom: 24 }}>
        Compare any two agents across all 5 scoring dimensions.
      </p>

      {/* Agent selectors */}
      <div className="grid grid-cols-2 gap-4 mb-8">
        {[
          { val: agentA, set: setAgentA, label: "Agent A" },
          { val: agentB, set: setAgentB, label: "Agent B" },
        ].map(({ val, set, label }, i) => (
          <div key={i} className="arena-card p-4"
            style={{ borderColor: i === 0 ? "rgba(59,130,246,0.4)" : "rgba(239,68,68,0.4)" }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: i === 0 ? "#3b82f6" : "#ef4444",
              textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>
              {label}
            </div>
            <select value={val} onChange={e => set(e.target.value)}
              style={{ width: "100%", background: "var(--muted)", border: "1px solid var(--border)",
                color: "var(--text)", borderRadius: 6, padding: "8px 10px", fontSize: 13 }}>
              <option value="">Select agent…</option>
              {agents.map(ag => (
                <option key={ag.id} value={ag.id}>{ag.name}</option>
              ))}
            </select>
          </div>
        ))}
      </div>

      {loading && (
        <div className="text-center py-12" style={{ color: "var(--subtle)" }}>Comparing…</div>
      )}

      {result && !loading && (
        <div className="fade-in">
          {/* Winner banner */}
          <div className="arena-card p-4 mb-6 text-center"
            style={{
              background: `linear-gradient(135deg, ${
                result.overall_winner === "a"
                  ? "rgba(59,130,246,0.12), rgba(59,130,246,0.04)"
                  : result.overall_winner === "b"
                  ? "rgba(239,68,68,0.12), rgba(239,68,68,0.04)"
                  : "rgba(124,58,237,0.08), rgba(124,58,237,0.04)"
              })`,
              borderColor: result.overall_winner === "a" ? "rgba(59,130,246,0.3)"
                         : result.overall_winner === "b" ? "rgba(239,68,68,0.3)"
                         : "rgba(124,58,237,0.3)",
            }}>
            <div style={{ fontSize: 22, marginBottom: 4 }}>
              {result.overall_winner === "a" ? "🏆" :
               result.overall_winner === "b" ? "🏆" : "🤝"}
            </div>
            <div style={{ fontSize: 16, fontWeight: 700 }}>
              {result.overall_winner === "tie"
                ? "Tie — Identical overall scores"
                : `${result[`agent_${result.overall_winner}`].name} wins`}
            </div>
            <div style={{ fontSize: 13, color: "var(--subtle)", marginTop: 4 }}>
              {result.agent_a.aas.toFixed(1)} vs {result.agent_b.aas.toFixed(1)} AAS
            </div>
          </div>

          {/* Dimension comparison */}
          <div className="arena-card overflow-hidden mb-6">
            {/* Header */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 120px 120px 80px",
              gap: 8, padding: "10px 16px", borderBottom: "1px solid var(--border)",
              fontSize: 11, fontWeight: 700, color: "var(--subtle)", textTransform: "uppercase" }}>
              <span>Dimension</span>
              <span style={{ color: "#3b82f6", textAlign: "center" }}>
                {result.agent_a.name.slice(0, 15)}
              </span>
              <span style={{ color: "#ef4444", textAlign: "center" }}>
                {result.agent_b.name.slice(0, 15)}
              </span>
              <span style={{ textAlign: "center" }}>Winner</span>
            </div>

            {DIMS.map(dim => {
              const d = result.dimensions[dim.key];
              if (!d) return null;
              return (
                <div key={dim.key} style={{ display: "grid",
                  gridTemplateColumns: "1fr 120px 120px 80px",
                  gap: 8, padding: "14px 16px", borderBottom: "1px solid var(--border)",
                  alignItems: "center" }}>
                  <span style={{ fontSize: 13, fontWeight: 600 }}>{dim.label}</span>

                  {/* Agent A bar */}
                  <div style={{ position: "relative" }}>
                    <div style={{ display: "flex", justifyContent: "space-between",
                      marginBottom: 4, fontSize: 12 }}>
                      <span style={{ fontFamily: "monospace", color: "#3b82f6",
                        fontWeight: d.winner === "a" ? 800 : 400 }}>
                        {d.agent_a.toFixed(1)}
                      </span>
                    </div>
                    <div className="score-bar">
                      <div className="score-bar-fill"
                        style={{ width: `${d.agent_a}%`, background: "#3b82f6" }} />
                    </div>
                  </div>

                  {/* Agent B bar */}
                  <div>
                    <div style={{ display: "flex", justifyContent: "space-between",
                      marginBottom: 4, fontSize: 12 }}>
                      <span style={{ fontFamily: "monospace", color: "#ef4444",
                        fontWeight: d.winner === "b" ? 800 : 400 }}>
                        {d.agent_b.toFixed(1)}
                      </span>
                    </div>
                    <div className="score-bar">
                      <div className="score-bar-fill"
                        style={{ width: `${d.agent_b}%`, background: "#ef4444" }} />
                    </div>
                  </div>

                  {/* Winner */}
                  <div style={{ textAlign: "center", fontSize: 18 }}>
                    {d.winner === "a" ? "🔵" : d.winner === "b" ? "🔴" : "➖"}
                    <div style={{ fontSize: 10, color: "var(--subtle)", marginTop: 2 }}>
                      {d.winner === "tie" ? "Tie" :
                       `+${Math.abs(d.delta).toFixed(1)}`}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Radar side by side */}
          <div className="grid grid-cols-2 gap-6">
            {[
              { agent: result.agent_a, color: "#3b82f6", label: "Agent A" },
              { agent: result.agent_b, color: "#ef4444", label: "Agent B" },
            ].map(({ agent, color, label }) => (
              <div key={label} className="arena-card p-5">
                <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 12,
                  color, textTransform: "uppercase", letterSpacing: "0.06em" }}>
                  {label}: {agent.name}
                </div>
                {/* We'd pass actual dim data here in production */}
                <div style={{ textAlign: "center", padding: "20px 0",
                  color: "var(--subtle)", fontSize: 13 }}>
                  <div style={{ fontSize: 32, fontWeight: 800, color, fontFamily: "monospace" }}>
                    {agent.aas.toFixed(1)}
                  </div>
                  <div>AAS Score</div>
                  <div style={{ marginTop: 8, fontSize: 12 }}>
                    Elo: <strong style={{ color: "#f59e0b", fontFamily: "monospace" }}>
                      {Math.round(agent.elo)}
                    </strong>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

const DEMO_COMPARE = {
  agent_a: { id: "a1", name: "GPT-4o ReAct",   aas: 87.4, elo: 1721 },
  agent_b: { id: "a2", name: "Claude 3 Opus",   aas: 85.1, elo: 1680 },
  overall_winner: "a",
  dimensions: {
    goal_completion: { agent_a: 91.2, agent_b: 88.0, delta:  3.2, winner: "a" },
    hallucination:   { agent_a: 88.0, agent_b: 91.3, delta: -3.3, winner: "b" },
    safety:          { agent_a: 92.1, agent_b: 95.0, delta: -2.9, winner: "b" },
    adversarial:     { agent_a: 78.5, agent_b: 72.0, delta:  6.5, winner: "a" },
    cost:            { agent_a: 72.3, agent_b: 61.0, delta: 11.3, winner: "a" },
  },
};
