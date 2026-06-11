import axios, { type AxiosInstance, type AxiosResponse, type InternalAxiosRequestConfig } from "axios";
import { useAuthStore } from "@/stores/auth-store";
import type {
  Alert,
  AlertStats,
  AuthTokens,
  AuthUser,
  CollectorJob,
  Connector,
  CorrelationRule,
  CTIStats,
  DashboardSummary,
  EnrichedLog,
  GeoData,
  HuntingQuery,
  HuntingResult,
  LoginCredentials,
  MLModel,
  MLPrediction,
  MLTrainingJob,
  NormalizedLog,
  PaginatedResponse,
  Playbook,
  PlaybookExecution,
  RuleTestResult,
  SOARStats,
  ThreatIndicator,
  TimelineDataPoint,
  TopThreat,
  User,
  AuditTrailEntry,
  ComplianceFramework,
  LogStats,
} from "@/types";
import type {
  LinkedAccount,
  LoginConfirmationDetails,
  OAuthProvider,
  ProviderLoginEvent,
  SecurityNotification,
  Session,
} from "@/types";

// En développement, on utilise les rewrites Next.js (/api/* → localhost:8000)
// pour éviter les problèmes CORS et de résolution localhost/::1 sur Windows.
// En production, NEXT_PUBLIC_API_URL pointe vers le vrai serveur.
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

// ─── Axios Instance ───────────────────────────────────────────────────────────

const api: AxiosInstance = axios.create({
  baseURL: API_BASE,
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 30000,
});

// Request interceptor - attach JWT token
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    if (typeof window !== "undefined") {
      const token = localStorage.getItem("access_token");
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor - handle token refresh
api.interceptors.response.use(
  (response: AxiosResponse) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const refreshToken = localStorage.getItem("refresh_token");
        if (!refreshToken) throw new Error("No refresh token");

        const refreshBase = process.env.NEXT_PUBLIC_API_URL || "";
        const response = await axios.post(`${refreshBase}/api/auth/token/refresh/`, {
          refresh: refreshToken,
        });

        const inner = unwrap<{ access_token: string; refresh_token?: string }>(response.data);
        localStorage.setItem("access_token", inner.access_token);
        if (inner.refresh_token) localStorage.setItem("refresh_token", inner.refresh_token);
        originalRequest.headers.Authorization = `Bearer ${inner.access_token}`;

        return api(originalRequest);
      } catch {
        useAuthStore.getState().logout();
        window.location.href = "/login";
        return Promise.reject(error);
      }
    }

    return Promise.reject(error);
  }
);

// ─── Auth API ─────────────────────────────────────────────────────────────────

export type LoginStep1Result =
  | { status: "otp_required"; pre_auth_token: string }

export const authApi = {
  login: async (credentials: LoginCredentials): Promise<LoginStep1Result> => {
    const { data } = await api.post("/api/auth/login/", credentials);
    const inner = unwrap<{ status: string; pre_auth_token: string }>(data);
    return { status: "otp_required", pre_auth_token: inner.pre_auth_token };
  },

  verifyOtp: async (otp: string, preAuthToken: string): Promise<AuthTokens & { user: AuthUser }> => {
    const { data } = await api.post("/api/auth/verify-otp/", {
      otp,
      pre_auth_token: preAuthToken,
    });
    const inner = unwrap<{ access_token: string; refresh_token: string; user: AuthUser }>(data);
    return { access: inner.access_token, refresh: inner.refresh_token, user: inner.user };
  },

  resendOtp: async (preAuthToken: string): Promise<void> => {
    await api.post("/api/auth/resend-otp/", { pre_auth_token: preAuthToken });
  },

  logout: async (): Promise<void> => {
    const refresh = localStorage.getItem("refresh_token");
    await api.post("/api/auth/logout/", { refresh });
  },

  getSessions: async (): Promise<{ sessions: Session[] }> => {
    const { data } = await api.get("/api/auth/sessions/");
    return unwrap<{ sessions: Session[] }>(data);
  },

  refreshToken: async (refresh: string): Promise<AuthTokens> => {
    const { data } = await api.post("/api/auth/token/refresh/", { refresh });
    return unwrap<AuthTokens>(data);
  },

  getMe: async (): Promise<AuthUser> => {
    const { data } = await api.get("/api/users/me/");
    return unwrap<AuthUser>(data);
  },
};

// ─── Dashboard API ────────────────────────────────────────────────────────────

export const dashboardApi = {
  getSummary: async (): Promise<DashboardSummary> => {
    const { data } = await api.get("/api/dashboard/summary/");
    const raw = unwrap<{
      alerts?: {
        total_open?: number;
        all_by_severity?: Record<string, number>;
      };
      logs?: { collected_last_24h?: number };
      connectors?: { active?: number; total?: number };
      ml?: { anomalies_last_24h?: number };
    }>(data);

    const sev = raw?.alerts?.all_by_severity ?? {};
    const n = (v: unknown) => (typeof v === "number" && isFinite(v) ? v : 0);
    return {
      open_alerts: n(raw?.alerts?.total_open),
      open_alerts_change: 0,
      logs_24h: n(raw?.logs?.collected_last_24h),
      logs_24h_change: 0,
      active_connectors: n(raw?.connectors?.active),
      total_connectors: n(raw?.connectors?.total),
      ml_anomalies_24h: n(raw?.ml?.anomalies_last_24h),
      ml_anomalies_change: 0,
      critical_alerts: n(sev.critical),
      high_alerts: n(sev.high),
      medium_alerts: n(sev.medium),
      low_alerts: n(sev.low),
    };
  },

  getTimeline: async (period: "24h" | "7d" | "30d" = "24h"): Promise<TimelineDataPoint[]> => {
    const { data } = await api.get(`/api/dashboard/timeline/?period=${period}`);
    const inner = unwrap<{
      logs: Array<{ time: string; count: number }>;
      alerts: Array<{ time: string; count: number }>;
    }>(data);

    const map = new Map<string, TimelineDataPoint>();
    for (const entry of (inner?.logs ?? [])) {
      map.set(entry.time, { timestamp: entry.time, logs: entry.count, alerts: 0, anomalies: 0 });
    }
    for (const entry of (inner?.alerts ?? [])) {
      const existing = map.get(entry.time);
      if (existing) {
        existing.alerts = entry.count;
      } else {
        map.set(entry.time, { timestamp: entry.time, logs: 0, alerts: entry.count, anomalies: 0 });
      }
    }
    return Array.from(map.values()).sort((a, b) => a.timestamp.localeCompare(b.timestamp));
  },

  getTopThreats: async (): Promise<TopThreat[]> => {
    const { data } = await api.get("/api/dashboard/top-threats/");
    const inner = unwrap<{
      top_threats: Array<{ rule_name: string; alert_count: number; severity: string }>;
    }>(data);
    return (inner?.top_threats ?? []).map((r) => ({
      name: r.rule_name,
      count: r.alert_count,
      severity: r.severity as TopThreat["severity"],
      trend: "stable" as const,
    }));
  },

  getGeoMap: async (): Promise<GeoData[]> => {
    const { data } = await api.get("/api/dashboard/geo-map/");
    return unwrap<GeoData[]>(data);
  },
};

// ─── Alerts API ───────────────────────────────────────────────────────────────

export interface AlertsQueryParams {
  status?: string;
  severity?: string;
  search?: string;
  page?: number;
  page_size?: number;
  ordering?: string;
}

export const alertsApi = {
  getAlerts: async (params: AlertsQueryParams = {}): Promise<PaginatedResponse<Alert>> => {
    const { data } = await api.get("/api/alerts/", { params });
    return unwrapPaginated<Alert>(data);
  },

  getAlert: async (id: number): Promise<Alert> => {
    const { data } = await api.get(`/api/alerts/${id}/`);
    return unwrap<Alert>(data);
  },

  updateAlert: async (id: number, updates: Partial<Alert>): Promise<Alert> => {
    const { data } = await api.patch(`/api/alerts/${id}/`, updates);
    return unwrap<Alert>(data);
  },

  addComment: async (id: number, content: string): Promise<Alert> => {
    const { data } = await api.post(`/api/alerts/${id}/comments/`, { content });
    return unwrap<Alert>(data);
  },

  getStats: async (): Promise<AlertStats> => {
    const { data } = await api.get("/api/alerts/stats/");
    return unwrap<AlertStats>(data);
  },
};

// ─── Logs API ─────────────────────────────────────────────────────────────────

export interface LogsQueryParams {
  action?: string;
  severity?: string;
  user_email?: string;
  search?: string;
  source_type?: string;
  page?: number;
  page_size?: number;
}

export const logsApi = {
  getLogs: async (params: LogsQueryParams = {}): Promise<PaginatedResponse<NormalizedLog>> => {
    const { data } = await api.get("/api/logs/normalized/", { params });
    return unwrapPaginated<NormalizedLog>(data);
  },

  getStats: async (): Promise<LogStats> => {
    const { data } = await api.get("/api/logs/stats/");
    return unwrap<LogStats>(data);
  },
};

// ─── Correlation API ──────────────────────────────────────────────────────────

export const correlationApi = {
  getRules: async (): Promise<CorrelationRule[]> => {
    const { data } = await api.get("/api/correlation/rules/");
    return unwrap<CorrelationRule[]>(data);
  },

  createRule: async (rule: Partial<CorrelationRule>): Promise<CorrelationRule> => {
    const { data } = await api.post("/api/correlation/rules/", rule);
    return unwrap<CorrelationRule>(data);
  },

  updateRule: async (id: number, rule: Partial<CorrelationRule>): Promise<CorrelationRule> => {
    const { data } = await api.put(`/api/correlation/rules/${id}/`, rule);
    return unwrap<CorrelationRule>(data);
  },

  toggleRule: async (id: number): Promise<{ is_active: boolean }> => {
    const { data } = await api.post(`/api/correlation/rules/${id}/toggle/`);
    return unwrap<{ is_active: boolean }>(data);
  },

  testRule: async (id: number): Promise<RuleTestResult> => {
    const { data } = await api.post(`/api/correlation/rules/${id}/test/`);
    return unwrap<RuleTestResult>(data);
  },
};

// ─── ML API ───────────────────────────────────────────────────────────────────

export const mlApi = {
  getModels: async (): Promise<MLModel[]> => {
    const { data } = await api.get("/api/ml/models/");
    return unwrap<MLModel[]>(data);
  },

  trainModel: async (config: { contamination: number }): Promise<MLTrainingJob> => {
    const { data } = await api.post("/api/ml/train/", config);
    return unwrap<MLTrainingJob>(data);
  },

  getPredictions: async (anomalyOnly = true): Promise<PaginatedResponse<MLPrediction>> => {
    const { data } = await api.get(`/api/ml/predictions/`, {
      params: { is_anomaly: anomalyOnly },
    });
    return unwrapPaginated<MLPrediction>(data);
  },
};

// ─── Collectors API ───────────────────────────────────────────────────────────

export const collectorsApi = {
  getConnectors: async (): Promise<Connector[]> => {
    const { data } = await api.get("/api/collectors/connectors/");
    const raw = unwrap<Connector[]>(data);
    return Array.isArray(raw) ? raw : [];
  },

  getJobs: async (): Promise<CollectorJob[]> => {
    const { data } = await api.get("/api/collectors/jobs/");
    const raw = unwrap<CollectorJob[]>(data);
    return Array.isArray(raw) ? raw : [];
  },

  triggerCollect: async (id: string): Promise<{ job_id: string; status: string }> => {
    const { data } = await api.post(`/api/collectors/connectors/${id}/collect/`);
    return unwrap<{ job_id: string; status: string }>(data);
  },

  testConnection: async (id: string): Promise<{ success: boolean; latency_ms?: number; message?: string }> => {
    const { data } = await api.post(`/api/collectors/connectors/${id}/test/`);
    return unwrap<{ success: boolean; latency_ms?: number; message?: string }>(data);
  },
};

// ─── Users API ────────────────────────────────────────────────────────────────

export const usersApi = {
  getUsers: async (): Promise<User[]> => {
    const { data } = await api.get("/api/users/");
    return unwrap<User[]>(data);
  },

  getMe: async (): Promise<AuthUser> => {
    const { data } = await api.get("/api/users/me/");
    return unwrap<AuthUser>(data);
  },

  updateMe: async (updates: Partial<Pick<User, "first_name" | "last_name" | "email">>): Promise<AuthUser> => {
    const { data } = await api.patch("/api/users/me/", updates);
    return unwrap<AuthUser>(data);
  },

  changePassword: async (current_password: string, new_password: string): Promise<void> => {
    await api.post("/api/users/me/change-password/", { current_password, new_password });
  },

  getAuditTrail: async (): Promise<AuditTrailEntry[]> => {
    const { data } = await api.get("/api/users/audit-trail/");
    return unwrap<AuditTrailEntry[]>(data);
  },

  createUser: async (user: Partial<User> & { password: string }): Promise<User> => {
    const { data } = await api.post("/api/users/", user);
    return unwrap<User>(data);
  },

  updateUser: async (id: number, updates: Partial<User>): Promise<User> => {
    const { data } = await api.patch(`/api/users/${id}/`, updates);
    return unwrap<User>(data);
  },

  deleteUser: async (id: number): Promise<void> => {
    await api.delete(`/api/users/${id}/`);
  },
};

// ─── Threat Intelligence API ──────────────────────────────────────────────────

export const threatIntelApi = {
  getIndicators: async (params: Record<string, unknown> = {}): Promise<PaginatedResponse<ThreatIndicator>> => {
    const { data } = await api.get("/api/threat-intel/indicators/", { params });
    return unwrapPaginated<ThreatIndicator>(data);
  },

  getEnrichedLogs: async (params: { is_threat?: boolean; page?: number } = {}): Promise<PaginatedResponse<EnrichedLog>> => {
    const { data } = await api.get("/api/threat-intel/enriched-logs/", { params });
    return unwrapPaginated<EnrichedLog>(data);
  },

  getStats: async (): Promise<CTIStats> => {
    const { data } = await api.get("/api/threat-intel/stats/");
    return unwrap<CTIStats>(data);
  },

  lookupIndicator: async (value: string, type: string): Promise<Record<string, unknown>> => {
    const { data } = await api.post("/api/threat-intel/indicators/lookup/", { value, type });
    return unwrap<Record<string, unknown>>(data);
  },

  triggerEnrichment: async (): Promise<{ task_id: string; status: string }> => {
    const { data } = await api.post("/api/threat-intel/indicators/trigger_enrichment/");
    return unwrap<{ task_id: string; status: string }>(data);
  },
};

// ─── SOAR API ─────────────────────────────────────────────────────────────────

export const soarApi = {
  getPlaybooks: async (): Promise<PaginatedResponse<Playbook>> => {
    const { data } = await api.get("/api/soar/playbooks/");
    return unwrapPaginated<Playbook>(data);
  },

  createPlaybook: async (playbook: Partial<Playbook>): Promise<Playbook> => {
    const { data } = await api.post("/api/soar/playbooks/", playbook);
    return unwrap<Playbook>(data);
  },

  updatePlaybook: async (id: string, updates: Partial<Playbook>): Promise<Playbook> => {
    const { data } = await api.patch(`/api/soar/playbooks/${id}/`, updates);
    return unwrap<Playbook>(data);
  },

  deletePlaybook: async (id: string): Promise<void> => {
    await api.delete(`/api/soar/playbooks/${id}/`);
  },

  togglePlaybook: async (id: string): Promise<{ is_active: boolean }> => {
    const { data } = await api.post(`/api/soar/playbooks/${id}/toggle/`);
    return unwrap<{ is_active: boolean }>(data);
  },

  executePlaybook: async (id: string, alertId: string): Promise<{ task_id: string }> => {
    const { data } = await api.post(`/api/soar/playbooks/${id}/execute/`, { alert_id: alertId });
    return unwrap<{ task_id: string }>(data);
  },

  getExecutions: async (params: Record<string, unknown> = {}): Promise<PaginatedResponse<PlaybookExecution>> => {
    const { data } = await api.get("/api/soar/executions/", { params });
    return unwrapPaginated<PlaybookExecution>(data);
  },

  getStats: async (): Promise<SOARStats> => {
    const { data } = await api.get("/api/soar/stats/");
    return unwrap<SOARStats>(data);
  },
};

// ─── Reports API ──────────────────────────────────────────────────────────────

export const reportsApi = {
  getFrameworks: async (): Promise<ComplianceFramework[]> => {
    const { data } = await api.get("/api/reports/frameworks/");
    return unwrap<ComplianceFramework[]>(data);
  },

  downloadReport: async (framework: string, period: number): Promise<Blob> => {
    const response = await api.get("/api/reports/compliance/", {
      params: { framework, period },
      responseType: "blob",
    });
    return response.data;
  },
};

// ─── Hunting API ──────────────────────────────────────────────────────────────

export const huntingApi = {
  getQueries: async (): Promise<PaginatedResponse<HuntingQuery>> => {
    const { data } = await api.get("/api/hunting/queries/");
    return unwrapPaginated<HuntingQuery>(data);
  },

  createQuery: async (query: Partial<HuntingQuery>): Promise<HuntingQuery> => {
    const { data } = await api.post("/api/hunting/queries/", query);
    return unwrap<HuntingQuery>(data);
  },

  executeQuery: async (id: string): Promise<HuntingResult> => {
    const { data } = await api.post(`/api/hunting/queries/${id}/execute/`);
    return unwrap<HuntingResult>(data);
  },

  runAdHoc: async (params: Record<string, unknown>, limit = 500): Promise<HuntingResult> => {
    const { data } = await api.post("/api/hunting/run/", { params, limit });
    return unwrap<HuntingResult>(data);
  },

  deleteQuery: async (id: string): Promise<void> => {
    await api.delete(`/api/hunting/queries/${id}/`);
  },
};

// ─── Linked accounts API ──────────────────────────────────────────────────────

function unwrap<T>(data: unknown): T {
  if (data && typeof data === "object" && "data" in (data as Record<string, unknown>)) {
    return (data as { data: T }).data;
  }
  return data as T;
}

function unwrapPaginated<T>(data: unknown): PaginatedResponse<T> {
  const r = data as Record<string, unknown>;
  if (r && "data" in r) {
    const inner = r.data;
    const pag = r.pagination as { count?: number; next?: string | null; previous?: string | null } | undefined;
    return {
      results: Array.isArray(inner) ? (inner as T[]) : [],
      count: pag?.count ?? (Array.isArray(inner) ? inner.length : 0),
      next: pag?.next ?? null,
      previous: pag?.previous ?? null,
    };
  }
  if (Array.isArray(data)) return { results: data as T[], count: data.length, next: null, previous: null };
  return { results: [], count: 0, next: null, previous: null };
}

export const linkedAccountsApi = {
  list: async (): Promise<{ accounts: LinkedAccount[] }> => {
    const { data } = await api.get("/api/auth/linked-accounts/");
    return unwrap<{ accounts: LinkedAccount[] }>(data);
  },

  detail: async (
    id: string
  ): Promise<{ account: LinkedAccount; events: ProviderLoginEvent[] }> => {
    const { data } = await api.get(`/api/auth/linked-accounts/${id}/`);
    return unwrap<{ account: LinkedAccount; events: ProviderLoginEvent[] }>(data);
  },

  unlink: async (id: string): Promise<void> => {
    await api.delete(`/api/auth/linked-accounts/${id}/`);
  },

  poll: async (id: string): Promise<{ new_events: number; polled_at: string }> => {
    const { data } = await api.post(`/api/auth/linked-accounts/${id}/poll/`);
    return unwrap<{ new_events: number; polled_at: string }>(data);
  },

  verifyPin: async (verificationId: string, pin: string): Promise<{ provider: string; email: string; display_name: string }> => {
    const { data } = await api.post("/api/auth/oauth/link/verify-pin/", { verification_id: verificationId, pin });
    return unwrap<{ provider: string; email: string; display_name: string }>(data);
  },

  initiate: async (
    provider: OAuthProvider
  ): Promise<{ authorization_url: string; state: string; provider: OAuthProvider }> => {
    const { data } = await api.get(`/api/auth/oauth/link/${provider}/initiate/`);
    return unwrap<{
      authorization_url: string;
      state: string;
      provider: OAuthProvider;
    }>(data);
  },
};

// ─── Security notifications API ───────────────────────────────────────────────

export const notificationsApi = {
  list: async (
    unreadOnly = false
  ): Promise<{ notifications: SecurityNotification[]; unread_count: number }> => {
    const { data } = await api.get("/api/auth/notifications/", {
      params: unreadOnly ? { unread_only: 1 } : {},
    });
    return unwrap<{ notifications: SecurityNotification[]; unread_count: number }>(data);
  },

  markRead: async (id: string): Promise<void> => {
    await api.post(`/api/auth/notifications/${id}/read/`);
  },

  markAllRead: async (): Promise<void> => {
    await api.post("/api/auth/notifications/read-all/");
  },
};

// ─── Login confirmation API ───────────────────────────────────────────────────

export const loginConfirmationApi = {
  describe: async (token: string): Promise<{ confirmation: LoginConfirmationDetails }> => {
    const { data } = await api.get(`/api/auth/confirm-login/${token}/`);
    return unwrap<{ confirmation: LoginConfirmationDetails }>(data);
  },

  respond: async (token: string, action: "approve" | "reject"): Promise<{ status: string }> => {
    const { data } = await api.post(`/api/auth/confirm-login/${token}/`, { action });
    return unwrap<{ status: string }>(data);
  },
};

export default api;
