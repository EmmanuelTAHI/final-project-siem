/**
 * Parseur de recherche façon Splunk/Kibana : `champ:valeur` combiné à du
 * texte libre, ex. `severity:critical severity:high source:wazuh échec`.
 * Les tokens non reconnus (pas de "champ:") sont concaténés en texte libre
 * et envoyés au paramètre `search` (recherche full-text backend).
 */

export interface ParsedLogQuery {
  freeText: string;
  severity: string[];
  outcome: string[];
  source_type?: string;
  action?: string;
  user_email?: string;
  source_ip?: string;
  geo_country?: string;
}

const FIELD_ALIASES: Record<string, keyof Omit<ParsedLogQuery, "freeText" | "severity" | "outcome">> = {
  source: "source_type",
  source_type: "source_type",
  src: "source_type",
  action: "action",
  event: "action",
  user: "user_email",
  user_email: "user_email",
  email: "user_email",
  ip: "source_ip",
  source_ip: "source_ip",
  country: "geo_country",
  geo_country: "geo_country",
};

/** Tokenise en respectant les guillemets ("valeur avec espaces"). */
function tokenize(input: string): string[] {
  const tokens: string[] = [];
  const re = /"([^"]*)"|(\S+)/g;
  let match: RegExpExecArray | null;
  while ((match = re.exec(input)) !== null) {
    tokens.push(match[1] !== undefined ? match[1] : match[2]);
  }
  return tokens;
}

export function parseLogSearch(input: string): ParsedLogQuery {
  const result: ParsedLogQuery = { freeText: "", severity: [], outcome: [] };
  const freeParts: string[] = [];

  for (const rawToken of tokenize(input.trim())) {
    const colonIdx = rawToken.indexOf(":");
    if (colonIdx > 0) {
      const field = rawToken.slice(0, colonIdx).toLowerCase();
      const value = rawToken.slice(colonIdx + 1).replace(/^"|"$/g, "");
      if (!value) {
        freeParts.push(rawToken);
        continue;
      }
      if (field === "severity" || field === "sev") {
        result.severity.push(value.toLowerCase());
        continue;
      }
      if (field === "outcome") {
        result.outcome.push(value.toLowerCase());
        continue;
      }
      const mapped = FIELD_ALIASES[field];
      if (mapped) {
        result[mapped] = value;
        continue;
      }
      // Champ non reconnu : on le garde tel quel dans le texte libre plutôt
      // que de le perdre silencieusement.
      freeParts.push(rawToken);
    } else if (rawToken) {
      freeParts.push(rawToken);
    }
  }

  result.freeText = freeParts.join(" ");
  return result;
}

/** Reconstruit la chaîne de recherche à partir de filtres structurés — utile
 * pour re-synchroniser la barre de recherche quand un filtre est posé depuis
 * la sidebar de facettes plutôt que tapé au clavier. */
export function serializeLogSearch(q: Partial<ParsedLogQuery>): string {
  const parts: string[] = [];
  (q.severity ?? []).forEach((s) => parts.push(`severity:${s}`));
  (q.outcome ?? []).forEach((o) => parts.push(`outcome:${o}`));
  if (q.source_type) parts.push(`source:${q.source_type}`);
  if (q.action) parts.push(`action:${q.action}`);
  if (q.user_email) parts.push(`user:${q.user_email}`);
  if (q.source_ip) parts.push(`ip:${q.source_ip}`);
  if (q.geo_country) parts.push(`country:${q.geo_country}`);
  if (q.freeText) parts.push(q.freeText);
  return parts.join(" ");
}
