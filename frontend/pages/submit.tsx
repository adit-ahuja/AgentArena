import { useState } from "react";
import { useRouter } from "next/router";
import { apiClient } from "../hooks/useApi";

const AGENT_TYPES = [
  { value: "langchain",          label: "LangChain Agent",         desc: "ReAct, OpenAI Tools, or Structured Chat" },
  { value: "openai_assistants",  label: "OpenAI Assistants API",   desc: "Built with the Assistants API" },
  { value: "autogpt",            label: "AutoGPT",                 desc: "AutoGPT-based agent" },
  { value: "crewai",             label: "CrewAI",                  desc: "Multi-agent CrewAI pipeline" },
  { value: "custom",             label: "Custom (HTTP endpoint)",  desc: "Any agent exposing a /run REST endpoint" },
];

const MODELS = [
  "gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo",
  "claude-3-opus", "claude-3-sonnet", "claude-3-haiku",
  "gemini-1.5-pro", "gemini-1.5-flash", "other",
];

const SUITES = [
  { value: "full",        label: "Full Suite",       desc: "100+ tasks · ~30 min" },
  { value: "quick",       label: "Quick Suite",      desc: "10 tasks · ~3 min"    },
  { value: "adversarial", label: "Adversarial Only", desc: "25 tasks · ~8 min"    },
];

export default function SubmitPage() {
  const router = useRouter();
  const [step,      setStep]      = useState(1);
  const [loading,   setLoading]   = useState(false);
  const [error,     setError]     = useState("");

  const [form, setForm] = useState({
    name: "", description: "", agent_type: "", model_backbone: "",
    api_endpoint: "", docker_image: "", version: "1.0.0",
    submitter_email: "", suite: "full",
    config: {} as Record<string, string>,
  });

  const update = (key: string, val: string) =>
    setForm(f => ({ ...f, [key]: val }));

  const handleSubmit = async () => {
    setLoading(true); setError("");
    try {
      const agent = await apiClient.submitAgent({
        name:            form.name,
        description:     form.description,
        agent_type:      form.agent_type,
        model_backbone:  form.model_backbone,
        api_endpoint:    form.api_endpoint || undefined,
        docker_image:    form.docker_image || undefined,
        version:         form.version,
        submitter_email: form.submitter_email || undefined,
        config:          { api_endpoint: form.api_endpoint, ...form.config },
      });
      const run = await apiClient.createRun({
        agent_id: agent.id, task_suite: form.suite
      });
      router.push(`/run/${run.id}`);
    } catch (e: any) {
      setError(e?.response?.data?.detail || "Failed to submit. Is the backend running?");
      setLoading(false);
    }
  };

  return (
    <div className="fade-in" style={{ maxWidth: 640, margin: "0 auto" }}>
      <h1 style={{ fontSize: 26, fontWeight: 800, marginBottom: 4, letterSpacing: "-0.02em" }}>
        Submit Your Agent
      </h1>
      <p style={{ color: "var(--subtle)", fontSize: 14, marginBottom: 28 }}>
        3 steps to get your agent benchmarked and listed on the leaderboard.
      </p>

      {/* Step indicator */}
      <div className="flex gap-2 mb-8">
        {[1, 2, 3].map(s => (
          <div key={s} className="flex items-center gap-2">
            <div style={{
              width: 28, height: 28, borderRadius: "50%",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 12, fontWeight: 700,
              background: step >= s ? "var(--accent)" : "var(--muted)",
              color: step >= s ? "#fff" : "var(--subtle)",
              transition: "background 0.3s",
            }}>
              {step > s ? "✓" : s}
            </div>
            <span style={{ fontSize: 12, color: step >= s ? "var(--text)" : "var(--subtle)",
              fontWeight: step === s ? 600 : 400 }}>
              {["Agent Info", "Connection", "Run"][s - 1]}
            </span>
            {s < 3 && <div style={{ width: 40, height: 1, background: "var(--border)" }} />}
          </div>
        ))}
      </div>

      <div className="arena-card p-6">
        {/* ── Step 1: Agent Info ── */}
        {step === 1 && (
          <div>
            <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 20 }}>Agent Information</h2>
            <div className="flex flex-col gap-4">
              <Field label="Agent Name *" hint="e.g. 'MyCompany GPT-4o Coding Agent'">
                <input value={form.name} onChange={e => update("name", e.target.value)}
                  placeholder="My Awesome Agent" style={inputStyle} />
              </Field>

              <Field label="Description">
                <textarea value={form.description}
                  onChange={e => update("description", e.target.value)}
                  placeholder="Brief description of your agent's architecture and goals."
                  rows={3} style={{ ...inputStyle, resize: "vertical" }} />
              </Field>

              <Field label="Agent Type *">
                <div className="flex flex-col gap-2">
                  {AGENT_TYPES.map(t => (
                    <label key={t.value}
                      style={{ display: "flex", alignItems: "center", gap: 10,
                        padding: "10px 12px", borderRadius: 8, cursor: "pointer",
                        background: form.agent_type === t.value ? "rgba(124,58,237,0.12)" : "var(--muted)",
                        border: `1px solid ${form.agent_type === t.value ? "rgba(124,58,237,0.4)" : "var(--border)"}`,
                        transition: "all 0.15s",
                      }}>
                      <input type="radio" value={t.value}
                        checked={form.agent_type === t.value}
                        onChange={() => update("agent_type", t.value)}
                        style={{ accentColor: "var(--accent)" }} />
                      <div>
                        <div style={{ fontWeight: 600, fontSize: 13 }}>{t.label}</div>
                        <div style={{ fontSize: 11, color: "var(--subtle)" }}>{t.desc}</div>
                      </div>
                    </label>
                  ))}
                </div>
              </Field>

              <Field label="Model Backbone">
                <select value={form.model_backbone}
                  onChange={e => update("model_backbone", e.target.value)} style={inputStyle}>
                  <option value="">Select model…</option>
                  {MODELS.map(m => <option key={m} value={m}>{m}</option>)}
                </select>
              </Field>

              <Field label="Version">
                <input value={form.version} onChange={e => update("version", e.target.value)}
                  placeholder="1.0.0" style={inputStyle} />
              </Field>
            </div>

            <button
              disabled={!form.name || !form.agent_type}
              onClick={() => setStep(2)}
              style={{ ...btnPrimary, marginTop: 24, opacity: (!form.name || !form.agent_type) ? 0.5 : 1 }}>
              Next →
            </button>
          </div>
        )}

        {/* ── Step 2: Connection ── */}
        {step === 2 && (
          <div>
            <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 6 }}>Connect Your Agent</h2>
            <p style={{ color: "var(--subtle)", fontSize: 13, marginBottom: 20 }}>
              AgentArena needs to call your agent. Choose your connection method.
            </p>

            {(form.agent_type === "custom" || form.agent_type === "langchain") && (
              <Field label="HTTP Endpoint URL"
                hint="Your agent must accept POST /run with { task_id, prompt, environment }">
                <input value={form.api_endpoint}
                  onChange={e => update("api_endpoint", e.target.value)}
                  placeholder="https://my-agent.company.com/run"
                  style={inputStyle} />
              </Field>
            )}

            <Field label="Docker Image (optional)"
              hint="Alternative: ship your agent as a Docker container">
              <input value={form.docker_image}
                onChange={e => update("docker_image", e.target.value)}
                placeholder="mycompany/my-agent:latest" style={inputStyle} />
            </Field>

            <Field label="Email (optional)" hint="Get notified when your run completes">
              <input value={form.submitter_email} type="email"
                onChange={e => update("submitter_email", e.target.value)}
                placeholder="you@company.com" style={inputStyle} />
            </Field>

            {/* SDK snippet */}
            <div style={{ background: "var(--muted)", borderRadius: 8, padding: "14px 16px",
              marginTop: 20, fontFamily: "monospace", fontSize: 12 }}>
              <div style={{ color: "var(--subtle)", marginBottom: 8, fontFamily: "sans-serif",
                fontSize: 11, fontWeight: 600 }}>
                Or use the Python SDK:
              </div>
              <div style={{ color: "#7c3aed" }}>from agentarena_sdk import ArenaAgent</div>
              <div />
              <div style={{ color: "#94a3b8" }}>@ArenaAgent(name="{form.name || 'my-agent'}")</div>
              <div style={{ color: "var(--text)" }}>def run(task):</div>
              <div style={{ color: "var(--subtle)", paddingLeft: 20 }}>
                # your agent logic here
              </div>
              <div style={{ color: "var(--subtle)", paddingLeft: 20 }}>
                return {"{"} "final_answer": "..." {"}"}
              </div>
            </div>

            <div className="flex gap-3 mt-6">
              <button onClick={() => setStep(1)} style={btnSecondary}>← Back</button>
              <button onClick={() => setStep(3)} style={btnPrimary}>Next →</button>
            </div>
          </div>
        )}

        {/* ── Step 3: Run Config ── */}
        {step === 3 && (
          <div>
            <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 6 }}>Configure Benchmark Run</h2>
            <p style={{ color: "var(--subtle)", fontSize: 13, marginBottom: 20 }}>
              Choose which task suite to run your agent against.
            </p>

            <div className="flex flex-col gap-3 mb-6">
              {SUITES.map(s => (
                <label key={s.value}
                  style={{ display: "flex", alignItems: "center", gap: 12,
                    padding: "12px 14px", borderRadius: 8, cursor: "pointer",
                    background: form.suite === s.value ? "rgba(124,58,237,0.12)" : "var(--muted)",
                    border: `1px solid ${form.suite === s.value ? "rgba(124,58,237,0.4)" : "var(--border)"}`,
                  }}>
                  <input type="radio" value={s.value} checked={form.suite === s.value}
                    onChange={() => update("suite", s.value)}
                    style={{ accentColor: "var(--accent)" }} />
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 13 }}>{s.label}</div>
                    <div style={{ fontSize: 12, color: "var(--subtle)" }}>{s.desc}</div>
                  </div>
                </label>
              ))}
            </div>

            {/* Summary */}
            <div style={{ background: "rgba(16,185,129,0.06)", border: "1px solid rgba(16,185,129,0.2)",
              borderRadius: 8, padding: "12px 14px", marginBottom: 20 }}>
              <div style={{ fontSize: 12, color: "#10b981", fontWeight: 700, marginBottom: 8 }}>
                ✓ Ready to submit
              </div>
              <div style={{ fontSize: 12, color: "var(--subtle)" }}>
                <div>{form.name} · {form.agent_type} · {form.model_backbone || "unknown model"}</div>
                <div>Task suite: {form.suite}</div>
              </div>
            </div>

            {error && (
              <div style={{ background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)",
                borderRadius: 7, padding: "10px 14px", marginBottom: 16,
                color: "var(--red)", fontSize: 13 }}>
                {error}
              </div>
            )}

            <div className="flex gap-3">
              <button onClick={() => setStep(2)} style={btnSecondary}>← Back</button>
              <button onClick={handleSubmit} disabled={loading} style={{ ...btnPrimary,
                opacity: loading ? 0.7 : 1 }}>
                {loading ? "Submitting…" : "🚀 Submit & Run"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Helper components & styles ────────────────────────────────────────────────

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <label style={{ fontSize: 12, fontWeight: 600, color: "var(--subtle)",
        textTransform: "uppercase", letterSpacing: "0.05em", display: "block", marginBottom: 6 }}>
        {label}
      </label>
      {hint && <div style={{ fontSize: 11, color: "var(--subtle)", marginBottom: 6 }}>{hint}</div>}
      {children}
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: "100%", background: "var(--muted)", border: "1px solid var(--border)",
  borderRadius: 7, padding: "8px 12px", color: "var(--text)", fontSize: 13,
  outline: "none", fontFamily: "inherit",
};

const btnPrimary: React.CSSProperties = {
  background: "linear-gradient(135deg, #7c3aed, #6d28d9)", color: "#fff",
  padding: "9px 20px", borderRadius: 8, fontWeight: 700, fontSize: 13,
  border: "none", cursor: "pointer",
};

const btnSecondary: React.CSSProperties = {
  background: "var(--muted)", color: "var(--text)", padding: "9px 18px",
  borderRadius: 8, fontWeight: 600, fontSize: 13, border: "1px solid var(--border)",
  cursor: "pointer",
};
