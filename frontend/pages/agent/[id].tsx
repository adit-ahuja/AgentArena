import { useState, useEffect } from "react";
import { useRouter } from "next/router";
import Link from "next/link";
import { apiClient, Agent, AgentScore, Run, BehavioralFingerprint } from "../../hooks/useApi";
import { AASScore, AgentRadar, EloChart, ScoreBar, StatusBadge, EloTier, ResultBar } from "../../components/Charts";

export default function AgentPage() {
  const router = useRouter();
  const { id } = router.query as { id: string };

  const [agent,       setAgent]       = useState<Agent | null>(null);
  const [scores,      setScores]      = useState<AgentScore[]>([]);
  const [runs,        setRuns]        = useState<Run[]>([]);
  const [fingerprint, setFingerprint] = useState<BehavioralFingerprint | null>(null);
  const [eloHistory,  setEloHistory]  = useState<any[]>([]);
  const [tab,         setTab]         = useState<"overview"|"runs"|"fingerprint">("overview");
  const [loading,     setLoading]     = useState(true);

  useEffect(() => {
    if (!id) return;
    Promise.all([
      apiClient.getAgent(id),
      apiClient.getAgentScores(id),
      apiClient.getAgentRuns(id),
      apiClient.getFingerprint(id),
      apiClient.getEloHistory(id),
    ]).then(([a, s, r, f, e]) => {
      setAgent(a); setScores(s); setRuns(r);
      setFingerprint(f); setEloHistory(e);
    }).catch(() => {
      // Demo mode
      setAgent(DEMO_AGENT);
      setScores(DEMO_SCORES);
      setRuns([]);
      setFingerprint(DEMO_FINGERPRINT);
      setEloHistory(DEMO_ELO);
    }).finally(() => setLoading(false));
  }, [id]);

  const latestScore = scores[0];

  if (loading) return (
    <div className="flex items-center justify-center" style={{ height: 300, color: "var(--subtle)" }}>
      Loading agent…
    </div>
  );

  if (!agent) return <div style={{ color: "var(--red)" }}>Agent not found</div>;

  return (
    <div className="fade-in">
      {/* ── Agent Header ── */}
      <div className="arena-card p-6 mb-6" style={{
        background: "linear-gradient(135deg, rgba(124,58,237,0.08), rgba(59,130,246,0.04))",
        borderColor: "rgba(124,58,237,0.2)",
      }}>
        <div className="flex items-start gap-6">
          {/* AAS circle */}
          {latestScore && <AASScore score={latestScore.aas_score} size={90} />}

          {/* Meta */}
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-1">
              <h1 style={{ fontSize: 22, fontWeight: 800, letterSpacing: "-0.02em" }}>
                {agent.name}
              </h1>
              {agent.is_verified && (
                <span style={{ background: "rgba(59,130,246,0.15)", color: "#3b82f6",
                  border: "1px solid rgba(59,130,246,0.3)", fontSize: 11,
                  padding: "2px 8px", borderRadius: 20, fontWeight: 600 }}>
                  ✓ Verified
                </span>
              )}
              <EloTier elo={agent.elo_rating} />
              <StatusBadge status={agent.status} />
            </div>
            {agent.description && (
              <p style={{ color: "var(--subtle)", fontSize: 13, marginBottom: 10 }}>
                {agent.description}
              </p>
            )}
            <div className="flex flex-wrap gap-4" style={{ fontSize: 12, color: "var(--subtle)" }}>
              <span>Type: <strong style={{ color: "var(--text)" }}>{agent.agent_type}</strong></span>
              {agent.model_backbone && (
                <span>Model: <strong style={{ color: "var(--text)" }}>{agent.model_backbone}</strong></span>
              )}
              <span>Version: <strong style={{ color: "var(--text)" }}>{agent.version}</strong></span>
              <span>Elo: <strong style={{ color: "#f59e0b", fontFamily: "monospace" }}>
                {Math.round(agent.elo_rating)}</strong></span>
              <span>Benchmarks: <strong style={{ color: "var(--text)" }}>{scores.length}</strong></span>
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex gap-2">
            <Link href={`/compare?a=${id}`}
              style={{ background: "var(--muted)", color: "var(--text)", padding: "7px 14px",
                borderRadius: 7, fontSize: 13, fontWeight: 600, textDecoration: "none",
                border: "1px solid var(--border)" }}>
              Compare
            </Link>
            <button
              onClick={async () => {
                try {
                  const run = await apiClient.createRun({ agent_id: id, task_suite: "full" });
                  router.push(`/run/${run.id}`);
                } catch {
                  alert("Backend offline — demo mode");
                }
              }}
              style={{ background: "linear-gradient(135deg, #7c3aed, #6d28d9)", color: "#fff",
                padding: "7px 16px", borderRadius: 7, fontSize: 13, fontWeight: 600,
                border: "none", cursor: "pointer" }}>
              Run Benchmark
            </button>
          </div>
        </div>
      </div>

      {/* ── Tabs ── */}
      <div className="flex gap-1 mb-6" style={{ borderBottom: "1px solid var(--border)", paddingBottom: 0 }}>
        {(["overview", "runs", "fingerprint"] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            style={{
              padding: "8px 16px", fontSize: 13, fontWeight: 500,
              background: "transparent", border: "none", cursor: "pointer",
              color: tab === t ? "var(--text)" : "var(--subtle)",
              borderBottom: tab === t ? "2px solid var(--accent)" : "2px solid transparent",
              textTransform: "capitalize", marginBottom: -1,
            }}>
            {t}
          </button>
        ))}
      </div>

      {/* ── Tab: Overview ── */}
      {tab === "overview" && latestScore && (
        <div className="grid grid-cols-3 gap-6">
          {/* Radar */}
          <div className="arena-card p-5">
            <h3 style={{ fontSize: 13, fontWeight: 700, marginBottom: 16, color: "var(--subtle)",
              textTransform: "uppercase", letterSpacing: "0.06em" }}>
              Score Profile
            </h3>
            <AgentRadar data={{
              goal_completion: latestScore.goal_completion_avg,
              hallucination:   latestScore.hallucination_avg,
              safety:          latestScore.safety_avg,
              adversarial:     latestScore.adversarial_avg,
              cost:            latestScore.cost_avg,
            }} />
          </div>

          {/* Score breakdown */}
          <div className="arena-card p-5">
            <h3 style={{ fontSize: 13, fontWeight: 700, marginBottom: 16, color: "var(--subtle)",
              textTransform: "uppercase", letterSpacing: "0.06em" }}>
              Score Breakdown
            </h3>
            <div className="flex flex-col gap-4">
              {[
                { label: "Goal Completion",   val: latestScore.goal_completion_avg, color: "#3b82f6" },
                { label: "Anti-Hallucination",val: latestScore.hallucination_avg,   color: "#7c3aed" },
                { label: "Safety",            val: latestScore.safety_avg,          color: "#10b981" },
                { label: "Adversarial Resist",val: latestScore.adversarial_avg,     color: "#f97316" },
                { label: "Cost Efficiency",   val: latestScore.cost_avg,            color: "#f59e0b" },
              ].map(s => (
                <ScoreBar key={s.label} label={s.label} value={s.val} color={s.color} />
              ))}
            </div>
          </div>

          {/* Elo history */}
          <div className="arena-card p-5">
            <h3 style={{ fontSize: 13, fontWeight: 700, marginBottom: 16, color: "var(--subtle)",
              textTransform: "uppercase", letterSpacing: "0.06em" }}>
              Elo Trajectory
            </h3>
            {eloHistory.length > 1
              ? <EloChart data={eloHistory} />
              : <p style={{ color: "var(--subtle)", fontSize: 13 }}>
                  Run 2+ benchmarks to see Elo trend.
                </p>
            }
            <div className="flex items-center justify-between mt-3">
              <span style={{ fontSize: 11, color: "var(--subtle)" }}>Current Elo</span>
              <span style={{ fontFamily: "monospace", fontWeight: 700, color: "#f59e0b", fontSize: 18 }}>
                {Math.round(agent.elo_rating)}
              </span>
            </div>
          </div>

          {/* Pass/fail breakdown */}
          <div className="arena-card p-5 col-span-3">
            <h3 style={{ fontSize: 13, fontWeight: 700, marginBottom: 16, color: "var(--subtle)",
              textTransform: "uppercase", letterSpacing: "0.06em" }}>
              Pass Rate
            </h3>
            <ResultBar pass={Math.round(latestScore.pass_rate)} partial={0} fail={100 - Math.round(latestScore.pass_rate)} />
          </div>
        </div>
      )}

      {/* ── Tab: Runs ── */}
      {tab === "runs" && (
        <div className="arena-card overflow-hidden">
          {runs.length === 0 ? (
            <div className="p-8 text-center" style={{ color: "var(--subtle)" }}>
              No benchmark runs yet.
            </div>
          ) : runs.map(run => (
            <div key={run.id}
              style={{ display: "grid", gridTemplateColumns: "1fr 100px 100px 100px 120px",
                gap: 8, padding: "12px 16px", borderBottom: "1px solid var(--border)",
                alignItems: "center" }}>
              <div>
                <Link href={`/run/${run.id}`}
                  style={{ color: "var(--text)", fontFamily: "monospace", fontSize: 12,
                    textDecoration: "none" }}>
                  {run.id.slice(0, 16)}…
                </Link>
                <div style={{ fontSize: 11, color: "var(--subtle)", marginTop: 2 }}>
                  {run.total_tasks} tasks · ${run.total_cost_usd.toFixed(4)} · {run.wall_time_secs.toFixed(1)}s
                </div>
              </div>
              <StatusBadge status={run.status} />
              <span style={{ fontFamily: "monospace", fontSize: 12 }}>
                {run.completed_tasks}/{run.total_tasks}
              </span>
              <span style={{ fontFamily: "monospace", fontSize: 12 }}>
                {run.total_tokens.toLocaleString()} tok
              </span>
              <span style={{ fontSize: 11, color: "var(--subtle)" }}>
                {new Date(run.created_at).toLocaleDateString()}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* ── Tab: Fingerprint ── */}
      {tab === "fingerprint" && fingerprint && (
        <div className="grid grid-cols-2 gap-6">
          <div className="arena-card p-6">
            <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 16 }}>
              Behavioral Profile
            </h3>
            <p style={{ color: "var(--subtle)", fontSize: 13, lineHeight: 1.7, marginBottom: 20 }}>
              {fingerprint.summary}
            </p>
            <div className="flex gap-4">
              <div style={{ background: "var(--muted)", borderRadius: 8, padding: "10px 16px" }}>
                <div style={{ fontSize: 10, color: "var(--subtle)", marginBottom: 4 }}>REASONING STYLE</div>
                <div style={{ fontSize: 15, fontWeight: 700, textTransform: "capitalize",
                  color: fingerprint.reasoning_style === "deliberate" ? "#7c3aed" : "#3b82f6" }}>
                  {fingerprint.reasoning_style}
                </div>
              </div>
              <div style={{ background: "var(--muted)", borderRadius: 8, padding: "10px 16px" }}>
                <div style={{ fontSize: 10, color: "var(--subtle)", marginBottom: 4 }}>RISK PROFILE</div>
                <div style={{ fontSize: 15, fontWeight: 700, textTransform: "capitalize",
                  color: fingerprint.risk_profile === "cautious" ? "#10b981" :
                         fingerprint.risk_profile === "aggressive" ? "#ef4444" : "#f59e0b" }}>
                  {fingerprint.risk_profile}
                </div>
              </div>
            </div>
          </div>

          <div className="arena-card p-6">
            <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 16 }}>Usage Metrics</h3>
            <div className="flex flex-col gap-3">
              {[
                { label: "Avg Tokens / Task",  val: fingerprint.avg_tokens_per_task.toLocaleString() },
                { label: "Avg Time / Task",    val: `${fingerprint.avg_time_seconds}s` },
                { label: "Avg Steps / Task",   val: fingerprint.avg_steps_per_task.toFixed(1) },
                { label: "Pass Rate",          val: `${fingerprint.pass_rate}%` },
                { label: "Tool Errors",        val: fingerprint.total_tool_errors.toString() },
              ].map(m => (
                <div key={m.label} className="flex justify-between items-center"
                  style={{ borderBottom: "1px solid var(--border)", paddingBottom: 8 }}>
                  <span style={{ fontSize: 13, color: "var(--subtle)" }}>{m.label}</span>
                  <span style={{ fontFamily: "monospace", fontWeight: 700, fontSize: 14 }}>{m.val}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Demo Data ─────────────────────────────────────────────────────────────────

const DEMO_AGENT: Agent = {
  id: "demo", name: "GPT-4o ReAct Agent", description: "A LangChain ReAct agent backed by GPT-4o with tool use.",
  agent_type: "langchain", model_backbone: "gpt-4o", version: "1.2.0",
  elo_rating: 1721, is_verified: true, status: "active",
  created_at: new Date().toISOString(),
};

const DEMO_SCORES: AgentScore[] = [{
  id: "s1", agent_id: "demo", run_id: "r1", aas_score: 87.4,
  goal_completion_avg: 91.2, hallucination_avg: 88.0, safety_avg: 92.1,
  adversarial_avg: 78.5, cost_avg: 72.3, pass_rate: 84.0,
  elo_before: 1680, elo_after: 1721,
  confidence_interval_low: 85.1, confidence_interval_high: 89.7,
  created_at: new Date().toISOString(),
}];

const DEMO_FINGERPRINT: BehavioralFingerprint = {
  avg_tokens_per_task: 2840, avg_time_seconds: 14.3, avg_steps_per_task: 7.2,
  pass_rate: 84.0, total_tool_errors: 12, reasoning_style: "deliberate",
  risk_profile: "cautious",
  summary: "This agent operates in a deliberate style with a cautious risk profile. It completes 84% of tasks and averages 7.2 steps per task, suggesting thorough reasoning before committing to answers.",
};

const DEMO_ELO = [
  { run_id: "r0", elo_after: 1200, created_at: "2024-01-01" },
  { run_id: "r1", elo_after: 1350, created_at: "2024-01-05" },
  { run_id: "r2", elo_after: 1480, created_at: "2024-01-12" },
  { run_id: "r3", elo_after: 1590, created_at: "2024-01-18" },
  { run_id: "r4", elo_after: 1650, created_at: "2024-01-25" },
  { run_id: "r5", elo_after: 1721, created_at: "2024-02-01" },
];
