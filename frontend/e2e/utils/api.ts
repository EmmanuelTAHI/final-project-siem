/**
 * Petit client API authentifié pour le nettoyage direct des ressources
 * QA_AUDIT_* créées pendant les tests, indépendamment de l'UI.
 *
 * But : si un test crée une ressource (connecteur, règle de corrélation,
 * playbook SOAR, requête de hunting, utilisateur...) et que la suppression
 * via l'UI échoue ou n'est pas testée dans ce test précis, un hook
 * afterEach/afterAll peut appeler ces méthodes pour garantir qu'on ne laisse
 * jamais de résidu QA_AUDIT_* en prod.
 *
 * Reprend les mêmes routes que frontend/src/lib/api.ts (collectorsApi,
 * correlationApi, soarApi, huntingApi, usersApi, agentsApi).
 */
import type { APIRequestContext } from "@playwright/test";

export const QA_PREFIX = "QA_AUDIT_";

/** Génère un nom unique préfixé QA_AUDIT_, pour retrouver/nettoyer facilement. */
export function qaName(label: string): string {
  return `${QA_PREFIX}${label}_${Date.now()}`;
}

export class ApiClient {
  constructor(private request: APIRequestContext, private accessToken: string) {}

  private baseURL(): string {
    return process.env.E2E_BASE_URL || "https://logplus.duckdns.org";
  }

  private headers() {
    return { Authorization: `Bearer ${this.accessToken}` };
  }

  private unwrap<T>(data: unknown): T {
    if (data && typeof data === "object" && "data" in (data as Record<string, unknown>)) {
      return (data as { data: T }).data;
    }
    return data as T;
  }

  async get<T = unknown>(path: string): Promise<T> {
    const res = await this.request.get(`${this.baseURL()}${path}`, { headers: this.headers() });
    return this.unwrap<T>(await res.json());
  }

  async post<T = unknown>(path: string, data?: Record<string, unknown>): Promise<T> {
    const res = await this.request.post(`${this.baseURL()}${path}`, { headers: this.headers(), data });
    return this.unwrap<T>(await res.json());
  }

  async patch<T = unknown>(path: string, data?: Record<string, unknown>): Promise<T> {
    const res = await this.request.patch(`${this.baseURL()}${path}`, { headers: this.headers(), data });
    return this.unwrap<T>(await res.json());
  }

  async delete(path: string): Promise<void> {
    await this.request.delete(`${this.baseURL()}${path}`, { headers: this.headers() });
  }

  // ─── Nettoyages ciblés par domaine ─────────────────────────────────────

  async deleteConnectorsMatchingPrefix(): Promise<void> {
    const list = await this.get<Array<{ id: string; name: string }>>("/api/collectors/connectors/");
    for (const c of list ?? []) {
      if (c.name?.startsWith(QA_PREFIX)) await this.delete(`/api/collectors/connectors/${c.id}/`);
    }
  }

  async deleteCorrelationRulesMatchingPrefix(): Promise<void> {
    const list = await this.get<Array<{ id: number; name: string }>>("/api/correlation/rules/");
    for (const r of list ?? []) {
      if (r.name?.startsWith(QA_PREFIX)) await this.delete(`/api/correlation/rules/${r.id}/`);
    }
  }

  async deletePlaybooksMatchingPrefix(): Promise<void> {
    const list = await this.get<{ results?: Array<{ id: string; name: string }> } | Array<{ id: string; name: string }>>(
      "/api/soar/playbooks/"
    );
    const arr = Array.isArray(list) ? list : list?.results ?? [];
    for (const p of arr) {
      if (p.name?.startsWith(QA_PREFIX)) await this.delete(`/api/soar/playbooks/${p.id}/`);
    }
  }

  async deleteHuntingQueriesMatchingPrefix(): Promise<void> {
    const list = await this.get<{ results?: Array<{ id: string; name: string }> } | Array<{ id: string; name: string }>>(
      "/api/hunting/queries/"
    );
    const arr = Array.isArray(list) ? list : list?.results ?? [];
    for (const q of arr) {
      if (q.name?.startsWith(QA_PREFIX)) await this.delete(`/api/hunting/queries/${q.id}/`);
    }
  }

  async deleteEnrollmentTokensMatchingPrefix(): Promise<void> {
    const list = await this.get<Array<{ id: string; name: string }>>("/api/collectors/enrollment-tokens/");
    for (const t of list ?? []) {
      if (t.name?.startsWith(QA_PREFIX)) await this.delete(`/api/collectors/enrollment-tokens/${t.id}/`);
    }
  }

  async deleteUsersMatchingPrefix(): Promise<void> {
    const list = await this.get<Array<{ id: number; email: string; first_name: string }>>("/api/users/");
    for (const u of list ?? []) {
      if (u.email?.startsWith(QA_PREFIX.toLowerCase()) || u.first_name?.startsWith(QA_PREFIX)) {
        await this.delete(`/api/users/${u.id}/`);
      }
    }
  }
}
