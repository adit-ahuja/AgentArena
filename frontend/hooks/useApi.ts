import axios from "axios";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = axios.create({ baseURL: BASE });

// ── Types ─────────────────────────────────────────────────────────────────────

export interface Agent {
  id: string;
  name: string;
  description?: string;
  agent_type: string;
  model_backbone?: string;
  version: string;
  elo_rating: number;
  is_verified: boolean;
  status: string;
  created_at: string;
}

export interface LeaderboardEntry {
  rank: number;
  agent_id: string;
  agent_name: string;
  agent_type: string;
  model_backbone?: string;
  aas_score: number;
  goal_completion: number;
  hallucination: number;
  safety: number;
  adversarial: number;
  cost: number;
  pass_rate: number;
  elo_rating: number;
  is_verified: boolean;
  runs_count: number;
  confidence_low?: number;
  confidence_high?: number;
}

export interface Run {
  id: string;
  agent_id: string;
  status: string;
  total_tasks: number;
  completed_tasks: number;
  total_tokens: number;
  total_cost_usd: number;
  wall_time_secs: number;
  error?: string;
  started_at?: string;
  finished_at?: string;
  created_at: string;
}

export interface TaskResult {
  id: string;
  run_id: string;
  task_id: string;
  status: string;
  agent_output?: string;
  trace: TraceStep[];
  tokens_used: number;
  time_seconds: number;
  goal_completion_score?: number;
  hallucination_score?: number;
  safety_score?: number;
  adversarial_score?: number;
  cost_score?: number;
  failure_reasons: string[];
  ai_analysis?: string;
}

export interface TraceStep {
  step: number;
  action: string;
  tool?: string;
  input?: any;
  output?: any;
  timestamp: number;
  tokens: number;
  error?: string;
}

export interface AgentScore {
  id: string;
  agent_id: string;
  run_id: string;
  aas_score: number;
  goal_completion_avg: number;
  hallucination_avg: number;
  safety_avg: number;
  adversarial_avg: number;
  cost_avg: number;
  pass_rate: number;
  elo_before?: number;
  elo_after?: number;
  confidence_interval_low?: number;
  confidence_interval_high?: number;
  created_at: string;
}

export interface RunSummary {
  run: Run;
  score: AgentScore;
  total_tasks: number;
  completed_tasks: number;
  pass_count: number;
  partial_count: number;
  fail_count: number;
  failure_categories: Record<string, number>;
  total_cost_usd: number;
  total_tokens: number;
  wall_time_secs: number;
}

export interface BehavioralFingerprint {
  avg_tokens_per_task: number;
  avg_time_seconds: number;
  avg_steps_per_task: number;
  pass_rate: number;
  total_tool_errors: number;
  reasoning_style: string;
  risk_profile: string;
  summary: string;
}

// ── API Calls ─────────────────────────────────────────────────────────────────

export const apiClient = {
  // Leaderboard
  getLeaderboard:    (params?: any) => api.get<LeaderboardEntry[]>("/api/leaderboard/", { params }).then(r => r.data),
  rerankLeaderboard: (weights: any)  => api.post<LeaderboardEntry[]>("/api/leaderboard/rerank", weights).then(r => r.data),
  compareAgents:     (a: string, b: string) => api.get("/api/leaderboard/compare", { params: { agent_a: a, agent_b: b } }).then(r => r.data),
  getTopElo:         ()              => api.get("/api/leaderboard/elo/top").then(r => r.data),

  // Agents
  submitAgent:       (data: any)     => api.post<Agent>("/api/agents/", data).then(r => r.data),
  listAgents:        ()              => api.get<Agent[]>("/api/agents/").then(r => r.data),
  getAgent:          (id: string)    => api.get<Agent>(`/api/agents/${id}`).then(r => r.data),
  getAgentScores:    (id: string)    => api.get<AgentScore[]>(`/api/agents/${id}/scores`).then(r => r.data),
  getAgentRuns:      (id: string)    => api.get<Run[]>(`/api/agents/${id}/runs`).then(r => r.data),
  getFingerprint:    (id: string)    => api.get<BehavioralFingerprint>(`/api/agents/${id}/fingerprint`).then(r => r.data),
  getEloHistory:     (id: string)    => api.get(`/api/agents/${id}/elo-history`).then(r => r.data),

  // Runs
  createRun:         (data: any)     => api.post<Run>("/api/runs/", data).then(r => r.data),
  listRuns:          (params?: any)  => api.get<Run[]>("/api/runs/", { params }).then(r => r.data),
  getRun:            (id: string)    => api.get<Run>(`/api/runs/${id}`).then(r => r.data),
  getRunResults:     (id: string)    => api.get<TaskResult[]>(`/api/runs/${id}/results`).then(r => r.data),
  getRunScore:       (id: string)    => api.get<AgentScore>(`/api/runs/${id}/score`).then(r => r.data),
  getRunSummary:     (id: string)    => api.get<RunSummary>(`/api/runs/${id}/summary`).then(r => r.data),

  // Tasks
  listTasks:         (params?: any)  => api.get("/api/tasks/", { params }).then(r => r.data),
  getTask:           (id: string)    => api.get(`/api/tasks/${id}`).then(r => r.data),
  getTaskStats:      (id: string)    => api.get(`/api/tasks/${id}/stats`).then(r => r.data),
};
