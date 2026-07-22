// ─── Authentication ───────────────────────────────────────────────────────────

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface AuthTokens {
  access: string;
  refresh: string;
}

export interface AuthUser {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  avatar?: string;
  date_joined: string;
  last_login: string;
  is_superuser?: boolean;
  organization_id?: string | null;
  organization_name?: string | null;
  is_demo?: boolean;
  email_notifications?: boolean;
  critical_alert_emails?: boolean;
  weekly_report_email?: boolean;
}

export interface Session {
  id: string;
  device: string;
  ip: string;
  location: string;
  current: boolean;
  created_at: string;
  expires_at: string;
}

// ─── Linked accounts ──────────────────────────────────────────────────────────

export type OAuthProvider = "google" | "microsoft" | "github";

export type LinkedAccountStatus = "active" | "paused" | "revoked" | "error";

export interface LinkedAccount {
  id: string;
  provider: OAuthProvider;
  provider_user_id: string;
  provider_email: string;
  provider_display_name: string;
  avatar_url: string;
  scopes: string;
  status: LinkedAccountStatus;
  last_polled_at: string | null;
  linked_at: string;
}

export interface ProviderLoginEvent {
  id: string;
  event_type:
    | "login_success"
    | "login_failure"
    | "mfa_challenge"
    | "mfa_failure"
    | "password_reset"
    | "suspicious_activity"
    | "token_revoked"
    | "unknown";
  occurred_at: string;
  ip_address: string | null;
  browser: string;
  os: string;
  device_type: string;
  geo_country: string;
  geo_city: string;
  is_known_device: boolean;
  is_known_location: boolean;
  risk_score: number;
}

// ─── Security notifications ───────────────────────────────────────────────────

export type SecurityNotificationLevel = "info" | "warning" | "critical";

export type SecurityNotificationKind =
  | "login_new_device"
  | "login_new_location"
  | "brute_force"
  | "account_locked"
  | "account_unlinked"
  | "provider_error"
  | "info";

export interface SecurityNotification {
  id: string;
  kind: SecurityNotificationKind;
  level: SecurityNotificationLevel;
  title: string;
  body: string;
  metadata: Record<string, unknown>;
  is_read: boolean;
  created_at: string;
  read_at: string | null;
  confirmation_token: string | null;
  confirmation_status: "pending" | "approved" | "rejected" | "expired" | null;
}

export interface LoginConfirmationDetails {
  id: string;
  status: "pending" | "approved" | "rejected" | "expired";
  ip_address: string | null;
  browser: string;
  os: string;
  device_type: string;
  geo_city: string;
  geo_country: string;
  created_at: string;
  expires_at: string;
  user_email: string;
  provider: OAuthProvider | null;
  provider_email: string | null;
}

// ─── Users ────────────────────────────────────────────────────────────────────

export type UserRole = "admin" | "analyst" | "viewer";

export interface User {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  avatar?: string;
  date_joined: string;
  last_login: string;
}

export interface AuditTrailEntry {
  id: number;
  user: string;
  user_email: string;
  action: string;
  resource_type: string;
  resource_id: string;
  details: Record<string, unknown>;
  ip_address: string;
  timestamp: string;
}

// ─── Alerts ───────────────────────────────────────────────────────────────────

export type AlertSeverity = "low" | "medium" | "high" | "critical";
export type AlertStatus = "open" | "in_progress" | "resolved" | "false_positive";

export interface Alert {
  id: number;
  title: string;
  description: string;
  severity: AlertSeverity;
  status: AlertStatus;
  rule_name: string;
  rule_id: number;
  source_ip: string;
  destination_ip?: string;
  user_email?: string;
  mitre_tactic?: string;
  mitre_technique?: string;
  event_count: number;
  assigned_to?: number;
  assigned_to_name?: string;
  created_at: string;
  updated_at: string;
  resolved_at?: string;
  log_sources: AlertLogSource[];
  comments: AlertComment[];
  ai_summary?: string;
  ai_recommended_actions?: string[];
  ai_summary_generated_at?: string | null;
}

export interface AlertLogSource {
  id: number;
  log_id: number;
  source_type: string;
  action: string;
  timestamp: string;
  raw_data: Record<string, unknown>;
}

export interface AlertComment {
  id: number;
  author: string;
  author_email: string;
  content: string;
  created_at: string;
}

export interface AlertStats {
  total: number;
  open: number;
  in_progress: number;
  resolved: number;
  false_positive: number;
  by_severity: {
    low: number;
    medium: number;
    high: number;
    critical: number;
  };
}

// ─── Tickets ──────────────────────────────────────────────────────────────────

export type TicketStatus = "open" | "in_progress" | "pending" | "resolved" | "closed";
export type TicketPriority = "low" | "medium" | "high" | "critical";

export interface TicketUserBrief {
  id: string;
  email: string;
  full_name: string;
}

export interface TicketComment {
  id: string;
  ticket: string;
  author: string | null;
  author_email: string | null;
  author_full_name: string | null;
  content: string;
  created_at: string;
}

export type TicketActivityAction =
  | "created"
  | "status_changed"
  | "priority_changed"
  | "assigned"
  | "commented"
  | "updated";

export interface TicketActivity {
  id: string;
  ticket: string;
  actor: string | null;
  actor_email: string | null;
  actor_full_name: string | null;
  action: TicketActivityAction;
  action_display: string;
  from_value: string;
  to_value: string;
  created_at: string;
}

export interface Ticket {
  id: string;
  display_id: string;
  number: number;
  title: string;
  description: string;
  status: TicketStatus;
  priority: TicketPriority;
  alert: string | null;
  alert_title?: string | null;
  alert_severity?: AlertSeverity | null;
  linked_alerts?: Array<{ id: string; title: string; severity: AlertSeverity; status: string }>;
  linked_alerts_count?: number;
  reporter?: TicketUserBrief | null;
  reporter_email?: string | null;
  assignee: TicketUserBrief | null;
  assignee_email?: string | null;
  assignee_full_name?: string | null;
  due_date: string | null;
  is_overdue: boolean;
  resolution_note: string | null;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
  closed_at: string | null;
  comments_count: number;
  comments?: TicketComment[];
  activities?: TicketActivity[];
}

export interface TicketStats {
  by_status: Partial<Record<TicketStatus, number>>;
  by_priority: Partial<Record<TicketPriority, number>>;
  mttr_hours: number | null;
  overdue_count: number;
  unassigned_count: number;
  open_count: number;
  total: number;
}

// ─── Logs ─────────────────────────────────────────────────────────────────────

// Taxonomie réelle du backend (normalizer) : high / medium / low.
// critical / info gardés en secours pour d'éventuelles sources tierces.
export type LogSeverity = "critical" | "high" | "medium" | "low" | "info";

export interface NormalizedLog {
  id: number;
  source_type: string;
  action: string;
  user_email?: string;
  source_ip?: string;
  destination_ip?: string;
  geo_country?: string;
  geo_country_code?: string;
  geo_city?: string;
  severity: LogSeverity;
  event_time?: string;
  timestamp: string;
  raw_data: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}

export interface LogStats {
  total_24h: number;
  total_7d: number;
  by_source: Record<string, number>;
  by_severity: Record<LogSeverity, number>;
  by_action: Array<{ action: string; count: number }>;
}

export interface LogHistogramBucket {
  t: string;
  count: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
  info: number;
}

export type LogFacetField =
  | "source_type"
  | "severity"
  | "action"
  | "user_email"
  | "source_ip"
  | "geo_country"
  | "outcome";

export interface LogFacetValue {
  value: string;
  count: number;
}

export interface LogHistogramResponse {
  total: number;
  interval_seconds: number;
  range_from: string;
  range_to: string;
  buckets: LogHistogramBucket[];
  facets: Record<LogFacetField, LogFacetValue[]>;
}

// ─── Dashboard ────────────────────────────────────────────────────────────────

export interface DashboardSummary {
  open_alerts: number;
  open_alerts_change: number;
  logs_24h: number;
  logs_24h_change: number;
  active_connectors: number;
  total_connectors: number;
  ml_anomalies_24h: number;
  ml_anomalies_change: number;
  critical_alerts: number;
  high_alerts: number;
  medium_alerts: number;
  low_alerts: number;
}

export interface TimelineDataPoint {
  timestamp: string;
  logs: number;
  alerts: number;
  anomalies: number;
}

export interface TopThreat {
  name: string;
  count: number;
  severity: AlertSeverity;
  trend: "up" | "down" | "stable";
}

export interface GeoData {
  country: string;
  country_code: string;
  count: number;
  percentage: number;
  threat_count: number;
}

// ─── Correlation Rules ────────────────────────────────────────────────────────

export type RuleType = "threshold" | "impossible_travel" | "time_based" | "sequence";
export type RuleSeverity = AlertSeverity;

export interface CorrelationRule {
  id: number;
  name: string;
  description: string;
  severity: RuleSeverity;
  rule_type: RuleType;
  condition_logic: Record<string, unknown>;
  mitre_tactic?: string;
  mitre_technique?: string;
  compliance_controls?: string[];
  is_active: boolean;
  alert_count: number;
  last_triggered?: string;
  created_at: string;
  updated_at: string;
  created_by: string;
}

// ─── Conformité continue ────────────────────────────────────────────────────

export interface ComplianceControlCoverage {
  id: string;
  title: string;
  covered: boolean;
  covering_rules: string[];
}

export interface ComplianceCoverage {
  framework: string;
  label: string;
  controls: ComplianceControlCoverage[];
  covered_count: number;
  total_count: number;
  coverage_percent: number;
}

// ─── SOAR : blocages IP ─────────────────────────────────────────────────────

export interface BlockedIP {
  id: string;
  ip_address: string;
  reason: string;
  source: "soar_playbook" | "manual" | "threat_intel";
  is_active: boolean;
  expires_at: string | null;
  created_at: string;
}

export interface RuleTestResult {
  matched_logs: number;
  sample_matches: NormalizedLog[];
  would_trigger: boolean;
  execution_time_ms: number;
}

// ─── Machine Learning ─────────────────────────────────────────────────────────

export interface MLModel {
  id: number;
  name: string;
  version: string;
  algorithm: string;
  accuracy: number;
  precision: number;
  recall: number;
  f1_score: number;
  contamination: number;
  is_active: boolean;
  trained_at: string;
  training_samples: number;
  features: string[];
}

export interface MLPrediction {
  id: number;
  log_id: number;
  log: NormalizedLog;
  anomaly_score: number;
  is_anomaly: boolean;
  prediction_time: string;
  model_version: string;
  top_features: Array<{ feature: string; importance: number }>;
}

export interface MLTrainingJob {
  id: number;
  status: "pending" | "running" | "completed" | "failed";
  progress: number;
  started_at: string;
  completed_at?: string;
  error_message?: string;
  metrics?: {
    accuracy: number;
    f1_score: number;
    training_samples: number;
  };
}

// ─── Collectors ───────────────────────────────────────────────────────────────

export type ConnectorStatus = "active" | "inactive" | "error" | "connecting";
export type ConnectorType = "microsoft365" | "google_workspace" | "wazuh" | "syslog" | "custom";

export interface Connector {
  id: string;
  name: string;
  source_type: ConnectorType;
  connector_type: ConnectorType;
  display_name: string;
  description: string;
  status: ConnectorStatus;
  is_active: boolean;
  logs_collected: number;
  logs_collected_24h: number;
  last_job_status: "success" | "failed" | "running" | "pending" | null;
  last_job_at: string | null;
  polling_interval_seconds: number;
  last_collected_at: string | null;
  created_at: string;
}

export interface CollectorJob {
  id: string;
  connector: string;
  connector_name: string;
  connector_type: string;
  status: "success" | "failed" | "running" | "pending";
  logs_collected: number;
  logs_collected_count: number;
  started_at: string;
  completed_at?: string | null;
  finished_at?: string | null;
  error_message?: string | null;
  duration_seconds?: number | null;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  plan: string;
  is_active: boolean;
  is_platform_internal: boolean;
  user_count: number;
  created_at: string;
  updated_at: string;
}

export interface PlatformOverview {
  organization_count: number;
  active_organization_count: number;
  total_user_count: number;
  platform_staff_count: number;
}

export interface OrganizationStats {
  user_count: number;
  connector_count: number;
  active_connector_count: number;
  log_count: number;
  open_alert_count: number;
}

export interface AgentEnrollmentToken {
  id: string;
  name: string;
  token_prefix: string;
  connector: string | null;
  connector_name: string | null;
  created_by: string | null;
  created_by_email: string | null;
  is_active: boolean;
  last_used_at: string | null;
  last_used_ip: string | null;
  expires_at: string | null;
  created_at: string;
}

export interface AgentEnrollmentTokenCreated extends AgentEnrollmentToken {
  /** Uniquement présent dans la réponse de création — jamais récupérable ensuite. */
  token: string;
}

// ─── API Pagination ───────────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface ApiError {
  message: string;
  code?: string;
  details?: Record<string, string[]>;
}

// ─── UI Types ─────────────────────────────────────────────────────────────────

export interface NavItem {
  label: string;
  href: string;
  icon: React.ElementType;
  badge?: number;
}

export interface FilterState {
  search: string;
  status?: AlertStatus;
  severity?: AlertSeverity;
  dateFrom?: string;
  dateTo?: string;
  page: number;
  pageSize: number;
}

export interface ChartDataPoint {
  name: string;
  value: number;
  [key: string]: string | number;
}

// ─── Threat Intelligence ──────────────────────────────────────────────────────

export type IndicatorType = "ip" | "domain" | "hash_md5" | "hash_sha256" | "url" | "email";
export type CTISource = "abuseipdb" | "virustotal" | "manual" | "otx";

export interface ThreatIndicator {
  id: string;
  indicator_type: IndicatorType;
  value: string;
  reputation_score: number;
  confidence: number;
  source: CTISource;
  tags: string[];
  is_malicious: boolean;
  last_seen: string;
  first_seen: string;
  raw_data: Record<string, unknown>;
}

export interface EnrichedLog {
  id: string;
  log_id: string;
  source_ip: string;
  user_email: string;
  indicators: ThreatIndicator[];
  max_score: number;
  is_threat: boolean;
  enriched_at: string;
}

export interface CTIStats {
  total_indicators: number;
  malicious_indicators: number;
  threats_24h: number;
  threats_7d: number;
  avg_score_malicious: number;
  by_source: Array<{ source: string; count: number }>;
  by_type: Array<{ indicator_type: string; count: number }>;
  top_malicious_ips: Array<{ value: string; reputation_score: number; source: string }>;
}

// ─── CVE / Vulnérabilités & Actifs ─────────────────────────────────────────────

export interface CVERecord {
  id: string;
  cve_id: string;
  description: string;
  cvss_score: number | null;
  severity: "low" | "medium" | "high" | "critical" | "";
  vendor_project: string;
  product: string;
  published_date: string | null;
  modified_date: string | null;
  is_kev: boolean;
  kev_date_added: string | null;
  kev_due_date: string | null;
  kev_ransomware_use: boolean;
  kev_required_action: string;
}

export interface CVEStats {
  total: number;
  kev_count: number;
  critical_count: number;
  high_count: number;
  ransomware_associated: number;
}

export type AssetType = "server" | "workstation" | "network_device" | "application" | "cloud_service" | "other";
export type AssetCriticality = "low" | "medium" | "high" | "critical";

export interface Asset {
  id: string;
  name: string;
  asset_type: AssetType;
  vendor: string;
  product: string;
  version: string;
  hostname: string;
  ip_address: string | null;
  criticality: AssetCriticality;
  source: "manual" | "auto_detected";
  last_seen: string | null;
  created_at: string;
  updated_at: string;
  open_vulnerabilities_count: number;
  kev_vulnerabilities_count: number;
}

export interface AssetVulnerability {
  id: string;
  asset: string;
  asset_name: string;
  cve: string;
  cve_id: string;
  cve_cvss_score: number | null;
  cve_is_kev: boolean;
  cve_description: string;
  status: "open" | "acknowledged" | "mitigated" | "false_positive";
  matched_reason: string;
  matched_at: string;
}

// ─── MITRE ATT&CK ───────────────────────────────────────────────────────────────

export interface MitreTechnique {
  id: string;
  name: string;
  covered?: boolean;
  covering_rules?: string[];
}

export interface MitreTactic {
  tactic: string;
  tactic_id: string;
  techniques: MitreTechnique[];
}

export interface MitreCoverage {
  matrix: MitreTactic[];
  coverage_percent: number;
  covered_count: number;
  total_count: number;
}

// ─── SOC Copilot IA ─────────────────────────────────────────────────────────────

export interface CopilotToolCall {
  tool: string;
  input: Record<string, unknown>;
  output_summary: string;
}

export interface CopilotMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  tool_calls: CopilotToolCall[];
  created_at: string;
}

export interface CopilotConversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages?: CopilotMessage[];
}

export interface CopilotAskResponse {
  conversation_id: string;
  answer: string;
  tool_calls: CopilotToolCall[];
  configured: boolean;
}

export interface AlertSummary {
  summary: string;
  recommended_actions: string[];
  generated_at: string;
}

// ─── SOAR ─────────────────────────────────────────────────────────────────────

export type TriggerType = "severity" | "rule_match" | "ml_anomaly" | "cti_match" | "manual";

export interface PlaybookAction {
  type: "send_email" | "webhook" | "block_ip" | "create_ticket";
  params: Record<string, unknown>;
}

export interface Playbook {
  id: string;
  name: string;
  description: string;
  trigger_type: TriggerType;
  trigger_conditions: Record<string, unknown>;
  actions: PlaybookAction[];
  is_active: boolean;
  execution_count: number;
  created_by: string;
  created_by_name: string;
  created_at: string;
  updated_at: string;
}

export interface PlaybookExecution {
  id: string;
  playbook: string;
  playbook_name: string;
  alert: string | null;
  alert_title: string;
  status: "pending" | "running" | "success" | "partial" | "failed";
  actions_taken: Array<{ type: string; status: string; [key: string]: unknown }>;
  error_message: string;
  triggered_by: string;
  started_at: string;
  finished_at: string | null;
  duration_seconds: number | null;
}

export interface SOARStats {
  total_playbooks: number;
  active_playbooks: number;
  executions_24h: number;
  executions_7d: number;
  success_rate: number;
  by_status: Array<{ status: string; count: number }>;
  top_playbooks: Array<{ name: string; execution_count: number }>;
}

// ─── Reports ──────────────────────────────────────────────────────────────────

export interface ComplianceFramework {
  id: string;
  label: string;
  description: string;
}

export interface GeneratedReportEntry {
  id: string;
  report_type: string;
  report_type_label: string;
  label: string;
  format: "pdf" | "csv" | "json";
  period_days: number;
  file_size: number;
  created_at: string;
  requested_by_name: string;
}

// ─── Threat Hunting ───────────────────────────────────────────────────────────

export interface HuntingQuery {
  id: string;
  name: string;
  description: string;
  query_params: Record<string, unknown>;
  mitre_tactic: string;
  mitre_technique: string;
  last_run_at: string | null;
  last_results_count: number;
  run_count: number;
  is_scheduled: boolean;
  created_by: string;
  created_by_name: string;
  created_at: string;
  updated_at: string;
}

export interface HuntingResult {
  count: number;
  returned: number;
  results: NormalizedLog[];
}

// ─── WebSocket Notifications ─────────────────────────────────────────────────

export type NotificationType = "new_alert" | "alert_updated" | "cti_threat" | "playbook_executed" | "system";

export interface WSNotification {
  type: NotificationType;
  alert?: Partial<Alert>;
  data?: Record<string, unknown>;
  message?: string;
  level?: "info" | "warning" | "error" | "success";
  timestamp: string;
}

// ─── User Risk Score ──────────────────────────────────────────────────────────

export interface UserRiskScore {
  user_email: string;
  risk_score: number;
  ml_anomalies: number;
  correlation_hits: number;
  cti_threats: number;
  failed_logins: number;
  computed_at: string;
}
