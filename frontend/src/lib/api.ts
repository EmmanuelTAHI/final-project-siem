import axios, { type AxiosInstance, type AxiosResponse, type InternalAxiosRequestConfig } from "axios";
import { useAuthStore } from "@/stores/auth-store";
import type {
  Alert,
  AgentEnrollmentToken,
  AgentEnrollmentTokenCreated,
  AlertStats,
  AuthTokens,
  AuthUser,
  CollectorJob,
  Connector,
  Organization,
  OrganizationStats,
  PlatformOverview,
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
  GeneratedReportEntry,
  LogStats,
  LogHistogramResponse,
  Ticket,
  TicketStats,
  TicketUserBrief,
  TicketPriority,
  TicketStatus,
  CVERecord,
  CVEStats,
  Asset,
  AssetVulnerability,
  MitreTactic,
  MitreCoverage,
  CopilotConversation,
  CopilotAskResponse,
  AlertSummary,
  ComplianceCoverage,
  BlockedIP,
  IPTrafficOverview,
  IPTrafficPeriod,
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
    // Marque tout le trafic émis par ce client comme "app SPA officielle" —
    // nginx s'en sert pour exclure le polling interne (refetchInterval) de
    // l'ingestion syslog vers le pipeline SIEM, sans dépendre d'une IP qui
    // change au quotidien (voir nginx/nginx.conf, map $http_x_argus_ui).
    "X-Argus-UI": "1",
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
        useAuthStore.getState().updateTokens(inner.access_token, inner.refresh_token);
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

  revokeSession: async (id: string): Promise<void> => {
    await api.delete(`/api/auth/sessions/${id}/`);
  },

  refreshToken: async (refresh: string): Promise<AuthTokens> => {
    const { data } = await api.post("/api/auth/token/refresh/", { refresh });
    return unwrap<AuthTokens>(data);
  },

  getMe: async (): Promise<AuthUser> => {
    const { data } = await api.get("/api/users/me/");
    return unwrap<AuthUser>(data);
  },

  requestPasswordReset: async (email: string): Promise<void> => {
    await api.post("/api/auth/password-reset/", { email });
  },

  confirmPasswordReset: async (token: string, password: string): Promise<void> => {
    await api.post("/api/auth/password-reset/confirm/", { token, password });
  },

  register: async (payload: {
    email: string;
    password: string;
    first_name: string;
    last_name: string;
    organization_name: string;
  }): Promise<void> => {
    await api.post("/api/auth/register/", payload);
  },

  verifyEmail: async (token: string): Promise<void> => {
    await api.post("/api/auth/verify-email/", { token });
  },

  acceptInvite: async (token: string, password: string): Promise<void> => {
    await api.post("/api/users/accept-invite/", { token, password });
  },

  inviteUser: async (payload: {
    email: string;
    first_name: string;
    last_name: string;
    role: string;
  }): Promise<void> => {
    await api.post("/api/users/invite/", payload);
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
        change_percent_24h?: number;
      };
      logs?: { collected_last_24h?: number; change_percent_24h?: number };
      connectors?: { active?: number; total?: number };
      ml?: { anomalies_last_24h?: number; change_percent_24h?: number };
    }>(data);

    const sev = raw?.alerts?.all_by_severity ?? {};
    const n = (v: unknown) => (typeof v === "number" && isFinite(v) ? v : 0);
    return {
      open_alerts: n(raw?.alerts?.total_open),
      open_alerts_change: n(raw?.alerts?.change_percent_24h),
      logs_24h: n(raw?.logs?.collected_last_24h),
      logs_24h_change: n(raw?.logs?.change_percent_24h),
      active_connectors: n(raw?.connectors?.active),
      total_connectors: n(raw?.connectors?.total),
      ml_anomalies_24h: n(raw?.ml?.anomalies_last_24h),
      ml_anomalies_change: n(raw?.ml?.change_percent_24h),
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
    // Le backend renvoie {period, countries: [{geo_country, total, failures,
    // successes}], generated_at} — un objet, pas un tableau, avec des noms de
    // champs différents de GeoData. Sans cette adaptation, .map() plante.
    const raw = unwrap<Record<string, unknown>>(data);
    const countries = (raw.countries as Record<string, unknown>[]) ?? [];
    const total = countries.reduce((sum, c) => sum + Number(c.total ?? 0), 0);
    return countries.map((c) => ({
      country: (c.geo_country as string) ?? "Inconnu",
      country_code: (c.geo_country as string) ?? "",
      count: Number(c.total ?? 0),
      percentage: total > 0 ? Math.round((Number(c.total ?? 0) / total) * 1000) / 10 : 0,
      threat_count: Number(c.failures ?? 0),
    }));
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

// Le serializer backend expose rule_mitre_tactic / source_logs_brief / ... ;
// cette adaptation aligne la réponse sur le type Alert utilisé par les pages
// (mêmes noms de champs que le payload WebSocket temps réel).
interface RawAlertLog {
  id: string;
  event_time: string;
  source_type: string;
  action: string;
  outcome?: string;
  severity?: string;
  user_email?: string;
  source_ip?: string;
  geo_country?: string;
}

function mapAlert(raw: Record<string, unknown>): Alert {
  const logs = (raw.source_logs_brief as RawAlertLog[] | undefined) ?? [];
  const first = logs[0];
  return {
    ...(raw as unknown as Alert),
    rule_id: (raw.rule ?? raw.rule_id) as Alert["rule_id"],
    mitre_tactic: (raw.rule_mitre_tactic ?? raw.mitre_tactic) as string | undefined,
    mitre_technique: (raw.rule_mitre_technique ?? raw.mitre_technique) as string | undefined,
    event_count: (raw.event_count as number | undefined) ?? logs.length,
    source_ip: ((raw.source_ip as string | undefined) ?? first?.source_ip ?? "") as string,
    user_email: (raw.user_email as string | undefined) ?? first?.user_email,
    assigned_to_name: (raw.assigned_to_email ?? raw.assigned_to_name) as string | undefined,
    // `comments` n'est présent que dans le serializer de détail ; on le laisse
    // tel quel (tableau) ou vide pour que le panneau puisse l'afficher.
    comments: (raw.comments as Alert["comments"] | undefined) ?? [],
    log_sources: logs.map((l) => ({
      id: l.id as unknown as number,
      log_id: l.id as unknown as number,
      source_type: l.source_type,
      action: l.action,
      timestamp: l.event_time,
      raw_data: l as unknown as Record<string, unknown>,
    })),
  };
}

export const alertsApi = {
  getAlerts: async (params: AlertsQueryParams = {}): Promise<PaginatedResponse<Alert>> => {
    const { data } = await api.get("/api/alerts/", { params });
    const page = unwrapPaginated<Record<string, unknown>>(data);
    return { ...page, results: page.results.map(mapAlert) };
  },

  getAlert: async (id: number): Promise<Alert> => {
    const { data } = await api.get(`/api/alerts/${id}/`);
    return mapAlert(unwrap<Record<string, unknown>>(data));
  },

  updateAlert: async (id: number, updates: Partial<Alert>): Promise<Alert> => {
    const { data } = await api.patch(`/api/alerts/${id}/`, updates);
    return mapAlert(unwrap<Record<string, unknown>>(data));
  },

  addComment: async (id: number, content: string): Promise<Alert> => {
    const { data } = await api.post(`/api/alerts/${id}/comments/`, { content });
    return mapAlert(unwrap<Record<string, unknown>>(data));
  },

  getStats: async (): Promise<AlertStats> => {
    const { data } = await api.get("/api/alerts/stats/");
    return unwrap<AlertStats>(data);
  },
};

// ─── Tickets API ──────────────────────────────────────────────────────────────

export interface TicketsQueryParams {
  status?: string;
  priority?: string;
  assignee?: string;
  alert?: string;
  search?: string;
  unassigned?: boolean;
  overdue?: boolean;
  ordering?: string;
  page?: number;
  page_size?: number;
}

export interface TicketCreateInput {
  title: string;
  description?: string;
  priority?: TicketPriority;
  status?: TicketStatus;
  alert?: string;
  assignee?: string | null;
  due_date?: string | null;
}

export const ticketsApi = {
  getTickets: async (params: TicketsQueryParams = {}): Promise<PaginatedResponse<Ticket>> => {
    const { data } = await api.get("/api/tickets/", { params });
    return unwrapPaginated<Ticket>(data);
  },

  getTicket: async (id: string): Promise<Ticket> => {
    const { data } = await api.get(`/api/tickets/${id}/`);
    return unwrap<Ticket>(data);
  },

  createTicket: async (input: TicketCreateInput): Promise<Ticket> => {
    const { data } = await api.post("/api/tickets/", input);
    return unwrap<Ticket>(data);
  },

  updateTicket: async (
    id: string,
    updates: Partial<Omit<Ticket, "assignee">> & { assignee?: string | null },
  ): Promise<Ticket> => {
    const { data } = await api.patch(`/api/tickets/${id}/`, updates);
    return unwrap<Ticket>(data);
  },

  deleteTicket: async (id: string): Promise<void> => {
    await api.delete(`/api/tickets/${id}/`);
  },

  addComment: async (id: string, content: string): Promise<Ticket> => {
    const { data } = await api.post(`/api/tickets/${id}/comments/`, { content });
    return unwrap<Ticket>(data);
  },

  getStats: async (): Promise<TicketStats> => {
    const { data } = await api.get("/api/tickets/stats/");
    return unwrap<TicketStats>(data);
  },

  getAssignableUsers: async (): Promise<TicketUserBrief[]> => {
    const { data } = await api.get("/api/tickets/assignable-users/");
    return unwrap<TicketUserBrief[]>(data);
  },

  linkAlert: async (ticketId: string, alertId: string): Promise<Ticket> => {
    const { data } = await api.post(`/api/tickets/${ticketId}/link-alert/`, { alert_id: alertId });
    return unwrap<Ticket>(data);
  },

  unlinkAlert: async (ticketId: string, alertId: string): Promise<Ticket> => {
    const { data } = await api.post(`/api/tickets/${ticketId}/unlink-alert/`, { alert_id: alertId });
    return unwrap<Ticket>(data);
  },
};

// ─── Logs API ─────────────────────────────────────────────────────────────────

export interface LogsQueryParams {
  action?: string;
  // Sévérité/outcome en multi-sélection : le backend (NormalizedLogFilter)
  // attend des paramètres répétés (?severity=high&severity=critical), pas
  // de notation à crochets — voir buildLogQueryString ci-dessous.
  severity?: string[];
  outcome?: string[];
  user_email?: string;
  search?: string;
  source_type?: string;
  source_ip?: string;
  event_time_from?: string;
  event_time_to?: string;
  interval?: number;
  ordering?: string;
  page?: number;
  page_size?: number;
}

/**
 * Construit une query string à partir de LogsQueryParams en sérialisant les
 * tableaux (severity, outcome) en paramètres répétés — le comportement par
 * défaut d'axios pour les tableaux (souvent `key[]=`) n'est pas celui que
 * django-filter attend côté backend.
 */
function buildLogQueryString(params: LogsQueryParams): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") return;
    if (Array.isArray(value)) {
      value.forEach((v) => v !== "" && search.append(key, String(v)));
    } else {
      search.append(key, String(value));
    }
  });
  return search.toString();
}

// Le serializer backend expose event_time / extra_fields ; la UI logs lit
// timestamp / raw_data. On aligne les noms ici (comme mapAlert pour les alertes).
function mapLog(raw: Record<string, unknown>): NormalizedLog {
  return {
    ...(raw as unknown as NormalizedLog),
    timestamp: (raw.timestamp as string | undefined) ?? (raw.event_time as string),
    raw_data:
      (raw.raw_data as Record<string, unknown> | undefined) ??
      (raw.extra_fields as Record<string, unknown> | undefined) ??
      {},
    // Le backend n'a qu'un seul champ `geo_country` (pas de code ISO séparé) ;
    // la UI (FlagBadge) attend `geo_country_code`. Alias direct — sans ça le
    // drapeau ne s'affiche jamais même quand la géo est renseignée.
    geo_country_code:
      (raw.geo_country_code as string | undefined) ?? (raw.geo_country as string | undefined),
  };
}

export const logsApi = {
  getLogs: async (params: LogsQueryParams = {}): Promise<PaginatedResponse<NormalizedLog>> => {
    const { data } = await api.get(`/api/logs/normalized/?${buildLogQueryString(params)}`);
    const page = unwrapPaginated<Record<string, unknown>>(data);
    return { ...page, results: page.results.map(mapLog) };
  },

  getStats: async (): Promise<LogStats> => {
    const { data } = await api.get("/api/logs/stats/");
    return unwrap<LogStats>(data);
  },

  getHistogram: async (params: LogsQueryParams = {}): Promise<LogHistogramResponse> => {
    const { data } = await api.get(`/api/logs/histogram/?${buildLogQueryString(params)}`);
    return unwrap<LogHistogramResponse>(data);
  },

  getIPTraffic: async (period: IPTrafficPeriod = "24h"): Promise<IPTrafficOverview> => {
    const { data } = await api.get("/api/logs/ip-traffic/", { params: { period } });
    // Vue construite avec Response() DRF brut (pas success_response) — pas d'enveloppe à déballer.
    return data as IPTrafficOverview;
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

  deleteRule: async (id: number): Promise<void> => {
    await api.delete(`/api/correlation/rules/${id}/`);
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

  trainModel: async (config: { contamination: number }): Promise<{ task_id: string; status: string }> => {
    const { data } = await api.post("/api/ml/train/", config);
    return unwrap<{ task_id: string; status: string }>(data);
  },

  getTrainStatus: async (
    taskId: string
  ): Promise<{ task_id: string; status: string; result?: unknown; error?: string }> => {
    const { data } = await api.get(`/api/ml/train/${taskId}/status/`);
    return unwrap<{ task_id: string; status: string; result?: unknown; error?: string }>(data);
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

  testConnection: async (id: string): Promise<{ reachable: boolean; latency_ms?: number; message?: string }> => {
    const { data } = await api.post(`/api/collectors/connectors/${id}/test/`);
    // Le backend renvoie systématiquement "reachable" (voir
    // apps/collectors/sources/*_collector.py::test_connection, les 4 types
    // de connecteurs), jamais "success" — c'était le nom attendu ici avant
    // ce fix, donc le test affichait toujours un toast d'échec même quand
    // la connexion était parfaitement fonctionnelle.
    return unwrap<{ reachable: boolean; latency_ms?: number; message?: string }>(data);
  },

  updateConnector: async (id: string, updates: { is_active: boolean }): Promise<Connector> => {
    const { data } = await api.patch(`/api/collectors/connectors/${id}/`, updates);
    return unwrap<Connector>(data);
  },

  deleteConnector: async (id: string): Promise<void> => {
    await api.delete(`/api/collectors/connectors/${id}/`);
  },
};

// ─── Agents (enrôlement) API ────────────────────────────────────────────────────

export const agentsApi = {
  list: async (): Promise<AgentEnrollmentToken[]> => {
    const { data } = await api.get("/api/collectors/enrollment-tokens/");
    const raw = unwrap<AgentEnrollmentToken[]>(data);
    return Array.isArray(raw) ? raw : [];
  },

  generate: async (name: string): Promise<AgentEnrollmentTokenCreated> => {
    const { data } = await api.post("/api/collectors/enrollment-tokens/", { name });
    return unwrap<AgentEnrollmentTokenCreated>(data);
  },

  revoke: async (id: string): Promise<void> => {
    await api.delete(`/api/collectors/enrollment-tokens/${id}/`);
  },
};

// ─── Platform (super-admin) API ────────────────────────────────────────────────

export const platformApi = {
  listOrganizations: async (): Promise<Organization[]> => {
    const { data } = await api.get("/api/platform/organizations/");
    const raw = unwrap<Organization[]>(data);
    return Array.isArray(raw) ? raw : [];
  },

  getOverview: async (): Promise<PlatformOverview> => {
    const { data } = await api.get("/api/platform/organizations/overview/");
    return unwrap<PlatformOverview>(data);
  },

  getOrganizationStats: async (id: string): Promise<OrganizationStats> => {
    const { data } = await api.get(`/api/platform/organizations/${id}/stats/`);
    return unwrap<OrganizationStats>(data);
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

  updateMe: async (
    updates: Partial<
      Pick<
        User,
        "first_name" | "last_name" | "email"
      > & {
        email_notifications: boolean;
        critical_alert_emails: boolean;
        weekly_report_email: boolean;
      }
    >
  ): Promise<AuthUser> => {
    const { data } = await api.patch("/api/users/me/", updates);
    return unwrap<AuthUser>(data);
  },

  changePassword: async (current_password: string, new_password: string): Promise<void> => {
    // Le serializer backend attend old_password / new_password / new_password_confirm
    await api.post("/api/users/me/change-password/", {
      old_password: current_password,
      new_password,
      new_password_confirm: new_password,
    });
  },

  getAuditTrail: async (): Promise<AuditTrailEntry[]> => {
    const { data } = await api.get("/api/users/audit-trail/");
    const entries = unwrap<Record<string, unknown>[]>(data);
    // Le serializer backend expose user_full_name / target_model / target_id /
    // extra_data ; l'UI attend user / resource_type / resource_id / details.
    return entries.map((e) => ({
      ...(e as unknown as AuditTrailEntry),
      user: (e.user_full_name as string | undefined) || (e.user_email as string | undefined) || "—",
      resource_type: e.target_model as string,
      resource_id: e.target_id as string,
      details: (e.extra_data as Record<string, unknown>) ?? {},
    }));
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

  triggerCommunitySync: async (): Promise<{ task_id: string; status: string }> => {
    const { data } = await api.post("/api/threat-intel/indicators/trigger_community_sync/");
    return unwrap<{ task_id: string; status: string }>(data);
  },

  getGeoFlags: async (
    ips: string[]
  ): Promise<Record<string, { country_code: string | null; country: string | null }>> => {
    const { data } = await api.get("/api/threat-intel/geo-flags/", {
      params: { ips: ips.join(",") },
    });
    return unwrap<Record<string, { country_code: string | null; country: string | null }>>(data);
  },
};

// ─── CVE / Vulnérabilités & Actifs ─────────────────────────────────────────────

export const cveApi = {
  getCVEs: async (params: Record<string, unknown> = {}): Promise<PaginatedResponse<CVERecord>> => {
    const { data } = await api.get("/api/threat-intel/cves/", { params });
    return unwrapPaginated<CVERecord>(data);
  },

  getStats: async (): Promise<CVEStats> => {
    const { data } = await api.get("/api/threat-intel/cves/stats/");
    return unwrap<CVEStats>(data);
  },

  triggerSync: async (): Promise<{ kev_task_id: string; nvd_task_id: string; status: string }> => {
    const { data } = await api.post("/api/threat-intel/cves/trigger_sync/");
    return unwrap<{ kev_task_id: string; nvd_task_id: string; status: string }>(data);
  },
};

export const assetsApi = {
  getAssets: async (params: Record<string, unknown> = {}): Promise<PaginatedResponse<Asset>> => {
    const { data } = await api.get("/api/threat-intel/assets/", { params });
    return unwrapPaginated<Asset>(data);
  },

  createAsset: async (asset: Partial<Asset>): Promise<Asset> => {
    const { data } = await api.post("/api/threat-intel/assets/", asset);
    return unwrap<Asset>(data);
  },

  updateAsset: async (id: string, updates: Partial<Asset>): Promise<Asset> => {
    const { data } = await api.patch(`/api/threat-intel/assets/${id}/`, updates);
    return unwrap<Asset>(data);
  },

  deleteAsset: async (id: string): Promise<void> => {
    await api.delete(`/api/threat-intel/assets/${id}/`);
  },

  triggerCorrelation: async (): Promise<{ task_id: string; status: string }> => {
    const { data } = await api.post("/api/threat-intel/assets/trigger_correlation/");
    return unwrap<{ task_id: string; status: string }>(data);
  },

  getVulnerabilities: async (
    params: Record<string, unknown> = {}
  ): Promise<PaginatedResponse<AssetVulnerability>> => {
    const { data } = await api.get("/api/threat-intel/asset-vulnerabilities/", { params });
    return unwrapPaginated<AssetVulnerability>(data);
  },

  updateVulnerabilityStatus: async (id: string, statusValue: string): Promise<AssetVulnerability> => {
    const { data } = await api.patch(`/api/threat-intel/asset-vulnerabilities/${id}/status/`, {
      status: statusValue,
    });
    return unwrap<AssetVulnerability>(data);
  },
};

// ─── MITRE ATT&CK ───────────────────────────────────────────────────────────────

export const mitreApi = {
  getReference: async (): Promise<MitreTactic[]> => {
    const { data } = await api.get("/api/correlation/mitre-attack/");
    return unwrap<MitreTactic[]>(data);
  },

  getCoverage: async (): Promise<MitreCoverage> => {
    const { data } = await api.get("/api/correlation/mitre-attack/coverage/");
    return unwrap<MitreCoverage>(data);
  },
};

// ─── SOC Copilot IA ─────────────────────────────────────────────────────────────

export const copilotApi = {
  ask: async (question: string, conversationId?: string): Promise<CopilotAskResponse> => {
    const { data } = await api.post("/api/copilot/ask/", {
      question,
      conversation_id: conversationId,
    });
    return unwrap<CopilotAskResponse>(data);
  },

  getConversations: async (): Promise<PaginatedResponse<CopilotConversation>> => {
    const { data } = await api.get("/api/copilot/conversations/");
    return unwrapPaginated<CopilotConversation>(data);
  },

  getConversation: async (id: string): Promise<CopilotConversation> => {
    const { data } = await api.get(`/api/copilot/conversations/${id}/`);
    return unwrap<CopilotConversation>(data);
  },

  summarizeAlert: async (alertId: string): Promise<AlertSummary> => {
    const { data } = await api.post(`/api/copilot/alerts/${alertId}/summarize/`);
    return unwrap<AlertSummary>(data);
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

  getBlockedIPs: async (params: Record<string, unknown> = {}): Promise<PaginatedResponse<BlockedIP>> => {
    const { data } = await api.get("/api/soar/blocked-ips/", { params });
    return unwrapPaginated<BlockedIP>(data);
  },

  blockIP: async (ip_address: string, reason = ""): Promise<BlockedIP & { network_block?: "ok" | "failed" | "unavailable" }> => {
    const { data } = await api.post("/api/soar/blocked-ips/", { ip_address, reason });
    return unwrap<BlockedIP & { network_block?: "ok" | "failed" | "unavailable" }>(data);
  },

  unblockIP: async (id: string): Promise<{ is_active: boolean }> => {
    const { data } = await api.post(`/api/soar/blocked-ips/${id}/unblock/`);
    return unwrap<{ is_active: boolean }>(data);
  },
};

// ─── Conformité continue ────────────────────────────────────────────────────

export const complianceApi = {
  getCoverage: async (framework: string): Promise<ComplianceCoverage> => {
    const { data } = await api.get("/api/reports/compliance-coverage/", { params: { framework } });
    return unwrap<ComplianceCoverage>(data);
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

  /** Rapports PDF (SOC hebdo, top menaces, activité utilisateurs, frameworks). */
  generateReport: async (type: string, periodDays: number): Promise<Blob> => {
    const response = await api.get("/api/reports/generate/", {
      params: { type, period: periodDays },
      responseType: "blob",
    });
    return response.data;
  },

  /** Rapport personnalisé (sources sélectionnées, période, format pdf/csv/json). */
  exportCustom: async (
    sources: string[],
    periodDays: number,
    format: "pdf" | "csv" | "json"
  ): Promise<Blob> => {
    const response = await api.get("/api/reports/export/", {
      params: { sources: sources.join(","), period: periodDays, format },
      responseType: "blob",
    });
    return response.data;
  },

  getHistory: async (): Promise<GeneratedReportEntry[]> => {
    const { data } = await api.get("/api/reports/history/");
    return unwrap<GeneratedReportEntry[]>(data);
  },

  downloadHistoryItem: async (id: string): Promise<Blob> => {
    const response = await api.get(`/api/reports/history/${id}/download/`, {
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
    const result = unwrap<Record<string, unknown>>(data);
    return {
      ...(result as unknown as HuntingResult),
      results: ((result.results as Record<string, unknown>[]) ?? []).map(mapLog),
    };
  },

  runAdHoc: async (params: Record<string, unknown>, limit = 500): Promise<HuntingResult> => {
    const { data } = await api.post("/api/hunting/run/", { params, limit });
    const result = unwrap<Record<string, unknown>>(data);
    return {
      ...(result as unknown as HuntingResult),
      results: ((result.results as Record<string, unknown>[]) ?? []).map(mapLog),
    };
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
