import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis,
  PolarRadiusAxis, ResponsiveContainer, Tooltip,
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  BarChart, Bar, Cell,
} from "recharts";

// ── Score Bar ─────────────────────────────────────────────────────────────────

interface ScoreBarProps {
  value: number;
  max?: number;
  label?: string;
  color?: string;
  showLabel?: boolean;
}

export function ScoreBar({ value, max = 100, label, color, showLabel = true }: ScoreBarProps) {
  const pct = Math.min(100, (value / max) * 100);
  const barColor = color || (
    pct >= 75 ? "#10b981" :
    pct >= 50 ? "#f59e0b" :
    "#ef4444"
  );

  return (
    <div style={{ width: "100%" }}>
      {showLabel && (
        <div className="flex justify-between mb-1" style={{ fontSize: 12 }}>
          {label && <span style={{ color: "var(--subtle)" }}>{label}</span>}
          <span style={{ color: barColor, fontFamily: "monospace", fontWeight: 600 }}>
            {value.toFixed(1)}
          </span>
        </div>
      )}
      <div className="score-bar">
        <div
          className="score-bar-fill"
          style={{ width: `${pct}%`, background: barColor }}
        />
      </div>
    </div>
  );
}

// ── AAS Score Circle ──────────────────────────────────────────────────────────

export function AASScore({ score, size = 80 }: { score: number; size?: number }) {
  const color =
    score >= 80 ? "#10b981" :
    score >= 60 ? "#f59e0b" :
    score >= 40 ? "#f97316" :
    "#ef4444";

  const r = (size - 10) / 2;
  const circ = 2 * Math.PI * r;
  const dash = circ * (score / 100);

  return (
    <div style={{ position: "relative", width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={size/2} cy={size/2} r={r}
          fill="none" stroke="var(--muted)" strokeWidth={5} />
        <circle cx={size/2} cy={size/2} r={r}
          fill="none" stroke={color} strokeWidth={5}
          strokeDasharray={`${dash} ${circ - dash}`}
          strokeLinecap="round"
          style={{ transition: "stroke-dasharray 0.8s ease" }}
        />
      </svg>
      <div style={{
        position: "absolute", inset: 0,
        display: "flex", flexDirection: "column",
        alignItems: "center", justifyContent: "center",
      }}>
        <span style={{ fontSize: size * 0.22, fontWeight: 700, color, fontFamily: "monospace" }}>
          {score.toFixed(0)}
        </span>
        <span style={{ fontSize: size * 0.1, color: "var(--subtle)" }}>AAS</span>
      </div>
    </div>
  );
}

// ── Radar Chart ───────────────────────────────────────────────────────────────

interface RadarData {
  goal_completion: number;
  hallucination: number;
  safety: number;
  adversarial: number;
  cost: number;
}

export function AgentRadar({ data, height = 220 }: { data: RadarData; height?: number }) {
  const radarData = [
    { dim: "Goal",        value: data.goal_completion },
    { dim: "Safety",      value: data.safety          },
    { dim: "Anti-Halluc", value: data.hallucination   },
    { dim: "Adversarial", value: data.adversarial      },
    { dim: "Cost Eff.",   value: data.cost             },
  ];

  return (
    <div className="radar-container" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={radarData}>
          <PolarGrid stroke="var(--border)" />
          <PolarAngleAxis dataKey="dim" tick={{ fontSize: 11, fill: "var(--subtle)" }} />
          <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
          <Radar
            name="Score" dataKey="value"
            stroke="#7c3aed" fill="#7c3aed" fillOpacity={0.25}
            dot={{ fill: "#7c3aed", r: 3 }}
          />
          <Tooltip
            formatter={(v: any) => [`${Number(v).toFixed(1)}`, "Score"]}
            contentStyle={{
              background: "var(--surface)", border: "1px solid var(--border)",
              borderRadius: 8, fontSize: 12,
            }}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Elo Line Chart ────────────────────────────────────────────────────────────

export function EloChart({ data }: { data: { run_id: string; elo_after: number; created_at: string }[] }) {
  const chartData = data.map((d, i) => ({
    run: `Run ${i + 1}`,
    elo: d.elo_after,
  }));

  return (
    <ResponsiveContainer width="100%" height={160}>
      <LineChart data={chartData} margin={{ left: -10, right: 10 }}>
        <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
        <XAxis dataKey="run" tick={{ fontSize: 10, fill: "var(--subtle)" }} />
        <YAxis tick={{ fontSize: 10, fill: "var(--subtle)" }} />
        <Tooltip
          contentStyle={{
            background: "var(--surface)", border: "1px solid var(--border)",
            borderRadius: 8, fontSize: 12,
          }}
        />
        <Line type="monotone" dataKey="elo"
          stroke="#7c3aed" strokeWidth={2}
          dot={{ fill: "#7c3aed", r: 3 }}
          activeDot={{ r: 5 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

// ── Pass/Fail Bar ─────────────────────────────────────────────────────────────

export function ResultBar({
  pass, partial, fail
}: { pass: number; partial: number; fail: number }) {
  const total = pass + partial + fail || 1;
  const passW    = (pass    / total) * 100;
  const partialW = (partial / total) * 100;
  const failW    = (fail    / total) * 100;

  return (
    <div>
      <div className="flex gap-0.5 rounded-full overflow-hidden" style={{ height: 8 }}>
        <div style={{ width: `${passW}%`,    background: "#10b981" }} />
        <div style={{ width: `${partialW}%`, background: "#f59e0b" }} />
        <div style={{ width: `${failW}%`,    background: "#ef4444" }} />
      </div>
      <div className="flex gap-4 mt-1" style={{ fontSize: 11, color: "var(--subtle)" }}>
        <span style={{ color: "#10b981" }}>{pass} pass</span>
        <span style={{ color: "#f59e0b" }}>{partial} partial</span>
        <span style={{ color: "#ef4444" }}>{fail} fail</span>
      </div>
    </div>
  );
}

// ── Status Badge ──────────────────────────────────────────────────────────────

export function StatusBadge({ status }: { status: string }) {
  const cls = {
    pass:      "badge-pass",
    partial:   "badge-partial",
    fail:      "badge-fail",
    running:   "badge-running",
    completed: "badge-pass",
    failed:    "badge-fail",
    queued:    "badge-running",
    timeout:   "badge-fail",
  }[status] || "badge-partial";

  return (
    <span style={{
      fontSize: 11, fontWeight: 600, borderRadius: 4,
      padding: "2px 8px", textTransform: "uppercase", letterSpacing: "0.05em"
    }} className={cls}>
      {status}
    </span>
  );
}

// ── Tier Badge ────────────────────────────────────────────────────────────────

export function EloTier({ elo }: { elo: number }) {
  const tier =
    elo >= 1800 ? { label: "Champion", color: "#f59e0b" } :
    elo >= 1600 ? { label: "Expert",   color: "#7c3aed" } :
    elo >= 1400 ? { label: "Advanced", color: "#3b82f6" } :
    elo >= 1200 ? { label: "Intermediate", color: "#10b981" } :
    { label: "Beginner", color: "#94a3b8" };

  return (
    <span style={{
      fontSize: 10, fontWeight: 700, borderRadius: 4,
      padding: "1px 6px", color: tier.color,
      background: `${tier.color}22`,
      border: `1px solid ${tier.color}44`,
    }}>
      {tier.label}
    </span>
  );
}

// ── Confidence Band ───────────────────────────────────────────────────────────

export function ConfidenceBand({ low, high, value }: { low?: number; high?: number; value: number }) {
  if (!low || !high) return <span className="mono">{value.toFixed(1)}</span>;

  return (
    <div className="flex flex-col items-center">
      <span className="mono" style={{ fontWeight: 700 }}>{value.toFixed(1)}</span>
      <span style={{ fontSize: 10, color: "var(--subtle)", fontFamily: "monospace" }}>
        ±{((high - low) / 2).toFixed(1)}
      </span>
    </div>
  );
}
