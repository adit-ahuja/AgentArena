import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/router";
import { apiClient, RunSummary, TaskResult } from "../../hooks/useApi";
import { AASScore, AgentRadar, ResultBar, StatusBadge, ScoreBar } from "../../components/Charts";

interface LiveEvent {
  event: string;
  data: any;
}

export default function RunPage() {
  const router = useRouter();
  const { id } = router.query as { id: string };

  const [summary,       setSummary]       = useState<RunSummary | null>(null);
  const [taskResults,   setTaskResults]   = useState<TaskResult[]>([]);
  const [liveEvents,    setLiveEvents]    = useState<LiveEvent[]>([]);
  const [selectedTask,  setSelectedTask]  = useState<TaskResult | null>(null);
  const [traceOpen,     setTraceOpen]     = useState(false);
  const [loading,       setLoading]       = useState(true);
  const [isLive,        setIsLive]        = useState(false);

  const wsRef    = useRef<WebSocket | null>(null);
  const logRef   = useRef<HTMLDivElement>(null);

  // ── Load initial data ──────────────────────────────────────────────────────
  useEffect(() => {
    if (!id) return;

    const load = async () => {
      try {
        const [sum, results] = await Promise.all([
          apiClient.getRunSummary(id),
          apiClient.getRunResults(id),
        ]);
        setSummary(sum);
        setTaskResults(results);
        setIsLive(sum.run.status === "running" || sum.run.status === "queued");
      } catch {
        setSummary(DEMO_SUMMARY);
        setTaskResults(DEMO_RESULTS);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [id]);

  // ── WebSocket for live updates ─────────────────────────────────────────────
  useEffect(() => {
    if (!id || !isLive) return;

    const WS_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000")
      .replace("http", "ws");

    const ws = new WebSocket(`${WS_BASE}/ws/runs/${id}`);
    wsRef.current = ws;

    ws.onmessage = (e) => {
      const msg: LiveEvent = JSON.parse(e.data);
      if (msg.event === "heartbeat") return;

      setLiveEvents(prev => [...prev, msg].slice(-50)); // keep last 50

      if (msg.event === "task_completed") {
        // Refresh results
        apiClient.getRunResults(id).then(setTaskResults).catch(() => {});
      }
      if (msg.event === "run_completed") {
        setIsLive(false);
        apiClient.getRunSummary(id).then(setSummary).catch(() => {});
      }

      // Auto-scroll event log
      setTimeout(() => {
        logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" });
      }, 50);
    };

    ws.onclose = () => setIsLive(false);

    return () => ws.close();
  }, [id, isLive]);

  if (loading) return (
    <div className="flex items-center justify-center" style={{ height: 300, color: "var(--subtle)" }}>
      Loading run…
    </div>
  );

  if (!summary) return <div>Run not found</div>;

  const { run, score } = summary;

  return (
    <div className="fade-in">
      {/* ── Header ── */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="flex items-center gap-3">
            <h1 style={{ fontSize: 22, fontWeight: 800 }}>Benchmark Run</h1>
            {isLive && (
              <span className="flex items-center gap-1.5"
                style={{ color: "var(--blue)", background: "rgba(59,130,246,0.1)",
                  border: "1px solid rgba(59,130,246,0.3)", padding: "2px 8px",
                  borderRadius: 20, fontSize: 12, fontWeight: 600 }}>
                <span className="live-dot" style={{ background: "var(--blue)" }} />
                LIVE
              </span>
            )}
            <StatusBadge status={run.status} />
          </div>
          <p style={{ color: "var(--subtle)", fontSize: 12, fontFamily: "monospace", marginTop: 4 }}>
            {id}
          </p>
        </div>

        {score && <AASScore score={score.aas_score} size={80} />}
      </div>

      {/* ── Progress bar ── */}
      <div className="arena-card p-4 mb-6">
        <div className="flex justify-between mb-2" style={{ fontSize: 13 }}>
          <span style={{ color: "var(--subtle)" }}>Progress</span>
          <span style={{ fontFamily: "monospace" }}>
            {summary.completed_tasks} / {summary.total_tasks} tasks
          </span>
        </div>
        <div className="score-bar" style={{ height: 8 }}>
          <div className="score-bar-fill"
            style={{
              width: `${summary.total_tasks ? (summary.completed_tasks / summary.total_tasks) * 100 : 0}%`,
              background: "linear-gradient(90deg, #7c3aed, #3b82f6)",
            }}
          />
        </div>
        <div className="flex gap-6 mt-3" style={{ fontSize: 12, color: "var(--subtle)" }}>
          <span>💰 ${run.total_cost_usd.toFixed(4)}</span>
          <span>🔤 {run.total_tokens.toLocaleString()} tokens</span>
          <span>⏱ {run.wall_time_secs.toFixed(1)}s</span>
          <span>📋 {summary.pass_count} pass / {summary.partial_count} partial / {summary.fail_count} fail</span>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* ── Left: Task Results ── */}
        <div className="col-span-2">
          <h2 style={{ fontSize: 14, fontWeight: 700, marginBottom: 12,
            color: "var(--subtle)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
            Task Results
          </h2>
          <div className="arena-card overflow-hidden">
            {taskResults.length === 0 ? (
              <div className="p-6 text-center" style={{ color: "var(--subtle)" }}>
                {isLive ? "Waiting for first task…" : "No results yet."}
              </div>
            ) : taskResults.map(r => (
              <div
                key={r.id}
                onClick={() => { setSelectedTask(r); setTraceOpen(true); }}
                style={{
                  display: "grid",
                  gridTemplateColumns: "80px 1fr 60px 60px 60px",
                  gap: 8, padding: "10px 14px", alignItems: "center",
                  borderBottom: "1px solid var(--border)",
                  cursor: "pointer", transition: "background 0.15s",
                }}
                onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = "rgba(255,255,255,0.02)"; }}
                onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = "transparent"; }}
              >
                <StatusBadge status={r.status} />
                <div>
                  <span style={{ fontSize: 12, fontFamily: "monospace",
                    color: "var(--text)" }}>
                    Task {r.task_id.slice(0, 8)}…
                  </span>
                  {r.failure_reasons.length > 0 && (
                    <div style={{ fontSize: 11, color: "var(--red)", marginTop: 2 }}>
                      {r.failure_reasons[0].slice(0, 60)}
                    </div>
                  )}
                </div>
                <span style={{ fontFamily: "monospace", fontSize: 11, color: "var(--subtle)",
                  textAlign: "center" }}>
                  {r.tokens_used}t
                </span>
                <span style={{ fontFamily: "monospace", fontSize: 11, color: "var(--subtle)",
                  textAlign: "center" }}>
                  {r.time_seconds.toFixed(1)}s
                </span>
                <span style={{
                  fontFamily: "monospace", fontSize: 12, fontWeight: 700,
                  textAlign: "center",
                  color: (r.goal_completion_score || 0) >= 75 ? "#10b981" :
                         (r.goal_completion_score || 0) >= 50 ? "#f59e0b" : "#ef4444"
                }}>
                  {r.goal_completion_score?.toFixed(0) || "-"}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* ── Right: Live Event Log ── */}
        <div>
          <h2 style={{ fontSize: 14, fontWeight: 700, marginBottom: 12,
            color: "var(--subtle)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
            {isLive ? "Live Events" : "Event Log"}
          </h2>
          <div
            ref={logRef}
            className="arena-card p-3"
            style={{ height: 400, overflowY: "auto", fontFamily: "monospace", fontSize: 11 }}
          >
            {liveEvents.length === 0 ? (
              <p style={{ color: "var(--subtle)" }}>
                {isLive ? "Connecting…" : "No live events recorded."}
              </p>
            ) : liveEvents.map((e, i) => (
              <div key={i} className="mb-1.5">
                <span style={{
                  color: e.event === "run_completed" ? "#10b981" :
                         e.event === "task_completed" ? (e.data.status === "pass" ? "#10b981" : e.data.status === "partial" ? "#f59e0b" : "#ef4444") :
                         e.event === "task_started" ? "#3b82f6" :
                         "var(--subtle)",
                }}>
                  [{e.event}]
                </span>{" "}
                <span style={{ color: "var(--subtle)" }}>
                  {e.event === "task_completed"
                    ? `Task done · AAS: ${e.data.aas?.toFixed(1)}`
                    : e.event === "task_started"
                    ? `Starting: ${e.data.title?.slice(0, 30) || e.data.task_id?.slice(0, 8)}`
                    : JSON.stringify(e.data).slice(0, 60)}
                </span>
              </div>
            ))}
          </div>

          {/* Score summary (when done) */}
          {score && !isLive && (
            <div className="arena-card p-4 mt-4">
              <h3 style={{ fontSize: 12, fontWeight: 700, marginBottom: 12,
                color: "var(--subtle)", textTransform: "uppercase" }}>
                Final Scores
              </h3>
              <div className="flex flex-col gap-3">
                {[
                  { label: "Goal",       val: score.goal_completion_avg, color: "#3b82f6" },
                  { label: "Anti-Halluc",val: score.hallucination_avg,   color: "#7c3aed" },
                  { label: "Safety",     val: score.safety_avg,          color: "#10b981" },
                  { label: "Adversarial",val: score.adversarial_avg,     color: "#f97316" },
                  { label: "Cost",       val: score.cost_avg,            color: "#f59e0b" },
                ].map(s => (
                  <ScoreBar key={s.label} label={s.label} value={s.val} color={s.color} />
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Trace Drawer ── */}
      {traceOpen && selectedTask && (
        <div
          style={{
            position: "fixed", inset: 0,
            background: "rgba(0,0,0,0.7)", backdropFilter: "blur(4px)",
            zIndex: 100, display: "flex", justifyContent: "flex-end",
          }}
          onClick={() => setTraceOpen(false)}
        >
          <div
            style={{
              width: "min(680px, 95vw)", height: "100vh",
              background: "var(--surface)", borderLeft: "1px solid var(--border)",
              overflowY: "auto", padding: 24,
            }}
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h2 style={{ fontSize: 16, fontWeight: 800 }}>Trace Viewer</h2>
              <button onClick={() => setTraceOpen(false)}
                style={{ background: "var(--muted)", border: "none", color: "var(--text)",
                  padding: "4px 10px", borderRadius: 6, cursor: "pointer", fontSize: 14 }}>
                ✕
              </button>
            </div>

            <StatusBadge status={selectedTask.status} />

            {/* AI Analysis */}
            {selectedTask.ai_analysis && (
              <div style={{ background: "rgba(124,58,237,0.08)", border: "1px solid rgba(124,58,237,0.2)",
                borderRadius: 8, padding: "12px 14px", margin: "14px 0", fontSize: 13,
                color: "var(--text)", lineHeight: 1.7 }}>
                <div style={{ fontSize: 11, color: "#7c3aed", fontWeight: 700,
                  marginBottom: 6, textTransform: "uppercase" }}>
                  🤖 AI Copilot Analysis
                </div>
                {selectedTask.ai_analysis}
              </div>
            )}

            {/* Failure reasons */}
            {selectedTask.failure_reasons.length > 0 && (
              <div style={{ margin: "12px 0" }}>
                {selectedTask.failure_reasons.map((r, i) => (
                  <div key={i} style={{ fontSize: 12, color: "var(--red)",
                    background: "rgba(239,68,68,0.08)", borderRadius: 5,
                    padding: "5px 10px", marginBottom: 4 }}>
                    ⚠ {r}
                  </div>
                ))}
              </div>
            )}

            {/* Final answer */}
            {selectedTask.agent_output && (
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: "var(--subtle)",
                  textTransform: "uppercase", marginBottom: 6 }}>
                  Final Answer
                </div>
                <div style={{ background: "var(--muted)", borderRadius: 7, padding: "10px 12px",
                  fontSize: 12, fontFamily: "monospace", whiteSpace: "pre-wrap",
                  maxHeight: 120, overflowY: "auto" }}>
                  {selectedTask.agent_output}
                </div>
              </div>
            )}

            {/* Step-by-step trace */}
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--subtle)",
              textTransform: "uppercase", marginBottom: 8 }}>
              Execution Trace ({selectedTask.trace.length} steps)
            </div>
            <div className="flex flex-col gap-2">
              {selectedTask.trace.map((step, i) => (
                <div key={i} style={{
                  borderLeft: `3px solid ${
                    step.action === "tool_call"   ? "#f59e0b" :
                    step.action === "tool_result" ? "#10b981" :
                    step.action === "output"      ? "#7c3aed" : "#3b82f6"
                  }`,
                  paddingLeft: 10, marginLeft: 4,
                }}>
                  <div className="flex items-center gap-2 mb-0.5">
                    <span style={{ fontSize: 10, fontFamily: "monospace",
                      color: "var(--subtle)" }}>
                      #{step.step}
                    </span>
                    <span style={{ fontSize: 11, fontWeight: 700,
                      color: step.action === "tool_call" ? "#f59e0b" :
                             step.action === "tool_result" ? "#10b981" :
                             step.action === "output" ? "#7c3aed" : "#3b82f6",
                      textTransform: "uppercase" }}>
                      {step.action}
                    </span>
                    {step.tool && (
                      <span style={{ fontSize: 10, background: "var(--muted)",
                        padding: "1px 5px", borderRadius: 3, fontFamily: "monospace" }}>
                        {step.tool}
                      </span>
                    )}
                    {step.tokens > 0 && (
                      <span style={{ fontSize: 10, color: "var(--subtle)" }}>
                        {step.tokens}t
                      </span>
                    )}
                    {step.error && (
                      <span style={{ fontSize: 10, color: "var(--red)" }}>
                        ⚠ {step.error.slice(0, 40)}
                      </span>
                    )}
                  </div>
                  {step.input != null && (
                    <div style={{ fontSize: 11, color: "var(--subtle)", fontFamily: "monospace",
                      whiteSpace: "pre-wrap", overflow: "hidden",
                      maxHeight: 60 }}>
                      → {typeof step.input === "string" ? step.input.slice(0, 150) : JSON.stringify(step.input).slice(0, 150)}
                    </div>
                  )}
                  {step.output != null && (
                    <div style={{ fontSize: 11, color: "var(--text)", fontFamily: "monospace",
                      whiteSpace: "pre-wrap", overflow: "hidden", maxHeight: 60 }}>
                      ← {typeof step.output === "string" ? step.output.slice(0, 150) : JSON.stringify(step.output).slice(0, 150)}
                    </div>
                  )}
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

const DEMO_SUMMARY: RunSummary = {
  run: { id: "demo-run", agent_id: "a1", status: "completed",
    total_tasks: 20, completed_tasks: 20, total_tokens: 48200,
    total_cost_usd: 0.241, wall_time_secs: 142.3, created_at: new Date().toISOString() },
  score: { id: "s1", agent_id: "a1", run_id: "demo-run", aas_score: 87.4,
    goal_completion_avg: 91.2, hallucination_avg: 88.0, safety_avg: 92.1,
    adversarial_avg: 78.5, cost_avg: 72.3, pass_rate: 84.0,
    created_at: new Date().toISOString() },
  total_tasks: 20, completed_tasks: 20,
  pass_count: 17, partial_count: 2, fail_count: 1,
  failure_categories: { "Low goal completion": 1, "Safety violation detected": 1 },
  total_cost_usd: 0.241, total_tokens: 48200, wall_time_secs: 142.3,
};

const DEMO_RESULTS: TaskResult[] = Array.from({ length: 10 }, (_, i) => ({
  id: `tr${i}`, run_id: "demo-run", task_id: `task-${i.toString().padStart(3, "0")}`,
  status: i < 8 ? "pass" : i === 8 ? "partial" : "fail",
  agent_output: "The answer is: [computed result based on task analysis]",
  trace: [
    { step: 1, action: "reasoning", tokens: 120, timestamp: Date.now() / 1000,
      input: "Analyzing task requirements…", output: "I need to call the search API first." },
    { step: 2, action: "tool_call", tool: "search_api", tokens: 0, timestamp: Date.now() / 1000,
      input: { query: "relevant search" }, output: null },
    { step: 3, action: "tool_result", tool: "search_api", tokens: 0, timestamp: Date.now() / 1000,
      input: null, output: '{"results": ["item1", "item2"]}' },
    { step: 4, action: "output", tokens: 80, timestamp: Date.now() / 1000,
      input: null, output: "Final answer based on search results." },
  ],
  tokens_used: 200 + i * 50,
  time_seconds: 8.3 + i * 0.5,
  goal_completion_score: i < 8 ? 85 + i : i === 8 ? 55 : 20,
  hallucination_score: 88,
  safety_score: 92,
  adversarial_score: 78,
  cost_score: 72,
  failure_reasons: i >= 9 ? ["Low goal completion (20/100)"] : [],
  ai_analysis: i >= 8
    ? "The agent failed to use the required lookup_customer tool before attempting to answer. It instead relied on its training knowledge, which led to fabricated customer IDs. Fix: add a mandatory tool-call check at the start of customer-related tasks."
    : undefined,
}));
