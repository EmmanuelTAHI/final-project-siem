"use client";

import { useState, useEffect, useRef, useCallback, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  Shield, AlertTriangle, Globe, Search, RefreshCw, Eye, TrendingUp, Zap,
  CheckCircle2, XCircle, Info,
} from "lucide-react";
import { threatIntelApi } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import toast from "react-hot-toast";
import type { ThreatIndicator } from "@/types";

// ─── Sources side-by-side ────────────────────────────────────────────────────

type Verdict = "malicious" | "suspicious" | "clean" | "unknown";

function verdictTone(v: Verdict) {
  return v === "malicious"
    ? "border-red-500/40 bg-red-500/5 text-red-500"
    : v === "suspicious"
    ? "border-orange-500/40 bg-orange-500/5 text-orange-500"
    : v === "clean"
    ? "border-emerald-500/40 bg-emerald-500/5 text-emerald-500"
    : "border-border bg-secondary/30 text-muted-foreground";
}

interface SourceSummary {
  verdict: Verdict;
  scoreLabel: string;
  rows: Array<{ label: string; value: string }>;
  description: string;
}

function summarizeAbuseIPDB(raw: Record<string, unknown> | null): SourceSummary {
  if (!raw || Object.keys(raw).length === 0) {
    return {
      verdict: "unknown",
      scoreLabel: "—",
      rows: [],
      description:
        "Aucune donnée renvoyée par AbuseIPDB. La clé API n'est peut-être pas configurée ou cette adresse n'a jamais été signalée.",
    };
  }
  const score = Number(raw.abuseConfidenceScore ?? 0);
  const reports = Number(raw.totalReports ?? 0);
  const lastReport = (raw.lastReportedAt as string) || "—";
  const country = (raw.countryName as string) || (raw.countryCode as string) || "—";
  const isp = (raw.isp as string) || "—";
  const domain = (raw.domain as string) || "—";
  const usage = (raw.usageType as string) || "—";

  const verdict: Verdict =
    score >= 75 ? "malicious" : score >= 25 ? "suspicious" : reports > 0 ? "suspicious" : "clean";

  const description =
    score >= 75
      ? `Cette adresse est considérée comme malveillante : ${reports} signalements ont été déposés par d'autres analystes. La confiance d'abus est de ${score}/100. À bloquer en priorité.`
      : score >= 25
      ? `Cette adresse présente des signaux suspects (${reports} signalements, confiance ${score}/100). Restez vigilant et corrélez avec les logs internes.`
      : reports > 0
      ? `Quelques signalements isolés (${reports}), mais la confiance d'abus reste faible (${score}/100). Probablement bénin.`
      : "Aucun signalement sur les 90 derniers jours. Cette adresse semble sûre selon AbuseIPDB.";

  return {
    verdict,
    scoreLabel: `${score}/100`,
    rows: [
      { label: "Confiance d'abus", value: `${score}/100` },
      { label: "Signalements", value: String(reports) },
      { label: "Dernier signalement", value: lastReport === "—" ? "—" : new Date(lastReport).toLocaleString("fr-FR") },
      { label: "Pays", value: country },
      { label: "Fournisseur d'accès", value: isp },
      { label: "Domaine associé", value: domain },
      { label: "Usage", value: usage },
    ],
    description,
  };
}

function summarizeGeo(raw: Record<string, unknown> | null): SourceSummary {
  if (!raw || Object.keys(raw).length === 0) {
    return {
      verdict: "unknown",
      scoreLabel: "—",
      rows: [],
      description: "Géolocalisation indisponible (IP privée ou service momentanément injoignable).",
    };
  }
  const country = (raw.country as string) || "—";
  const city = (raw.city as string) || "";
  const region = (raw.regionName as string) || "";
  const isp = (raw.isp as string) || "—";
  const org = (raw.org as string) || "";
  const asn = (raw.as as string) || "—";
  const reverse = (raw.reverse as string) || "—";
  const isProxy = Boolean(raw.proxy);
  const isHosting = Boolean(raw.hosting);
  const isMobile = Boolean(raw.mobile);

  const verdict: Verdict = isProxy ? "suspicious" : isHosting ? "suspicious" : "clean";
  const flags: string[] = [];
  if (isProxy) flags.push("proxy/VPN");
  if (isHosting) flags.push("hébergeur/datacenter");
  if (isMobile) flags.push("réseau mobile");

  const description = isProxy
    ? "Cette IP passe par un proxy, VPN ou anonymiseur — fréquent chez les attaquants pour masquer leur origine."
    : isHosting
    ? "Cette IP appartient à un hébergeur / datacenter. Le trafic « humain » légitime en vient rarement — méfiance accrue."
    : `Localisation : ${[city, region, country].filter(Boolean).join(", ")}. Réseau résidentiel/entreprise classique.`;

  return {
    verdict,
    scoreLabel: raw.countryCode ? String(raw.countryCode) : "—",
    rows: [
      { label: "Pays", value: [city, region, country].filter(Boolean).join(", ") || country },
      { label: "Fournisseur (FAI)", value: isp },
      { label: "Organisation", value: org || "—" },
      { label: "ASN", value: asn },
      { label: "DNS inverse", value: reverse },
      { label: "Indicateurs réseau", value: flags.length ? flags.join(" · ") : "aucun" },
    ],
    description,
  };
}

function summarizeInternal(raw: Record<string, unknown> | null): SourceSummary {
  if (!raw || raw.seen === false || raw.seen === undefined) {
    return {
      verdict: "clean",
      scoreLabel: "0",
      rows: [{ label: "Statut", value: "Jamais vue localement" }],
      description:
        "Cette IP n'apparaît dans aucun de vos logs. Elle n'a jamais interagi avec votre infrastructure surveillée.",
    };
  }
  const failures = Number(raw.login_failures ?? 0);
  const alerts = Number(raw.alert_count ?? 0);
  const total = Number(raw.total_events ?? 0);
  const users = (raw.targeted_users as string[]) ?? [];
  const firstSeen = (raw.first_seen as string) || null;
  const lastSeen = (raw.last_seen as string) || null;

  const verdict: Verdict =
    alerts > 0 ? "malicious" : failures >= 5 ? "suspicious" : total > 0 ? "clean" : "unknown";

  const description =
    alerts > 0
      ? `⚠ Cette IP a déjà déclenché ${alerts} alerte(s) sur VOTRE infrastructure — c'est un attaquant connu localement. Blocage recommandé.`
      : failures >= 5
      ? `Cette IP cumule ${failures} échecs de connexion dans vos logs — comportement de brute force probable.`
      : `IP observée ${total} fois dans vos logs, sans activité malveillante caractérisée à ce jour.`;

  return {
    verdict,
    scoreLabel: alerts > 0 ? `${alerts} alerte(s)` : `${total} evt`,
    rows: [
      { label: "Événements observés", value: String(total) },
      { label: "Échecs de connexion", value: String(failures) },
      { label: "Alertes déclenchées", value: String(alerts) },
      { label: "Comptes ciblés", value: users.length ? users.slice(0, 5).join(", ") : "—" },
      { label: "Première vue", value: firstSeen ? new Date(firstSeen).toLocaleString("fr-FR") : "—" },
      { label: "Dernière vue", value: lastSeen ? new Date(lastSeen).toLocaleString("fr-FR") : "—" },
    ],
    description,
  };
}

function summarizeCriminalIP(raw: Record<string, unknown> | null): SourceSummary {
  if (!raw || Object.keys(raw).length === 0) {
    return {
      verdict: "unknown",
      scoreLabel: "—",
      rows: [],
      description: "Aucune donnée CriminalIP (clé non configurée ou IP inconnue).",
    };
  }
  const inb = Number(raw.inbound_score ?? 0);
  const outb = Number(raw.outbound_score ?? 0);
  const flags: string[] = [];
  if (raw.is_malicious) flags.push("malveillant");
  if (raw.is_scanner) flags.push("scanner");
  if (raw.is_tor) flags.push("Tor");
  if (raw.is_vpn) flags.push("VPN");
  if (raw.is_proxy) flags.push("proxy");
  if (raw.is_hosting) flags.push("hébergeur");
  if (raw.is_darkweb) flags.push("dark web");

  const verdict: Verdict =
    raw.is_malicious || inb >= 75 ? "malicious" : flags.length > 0 || inb >= 30 ? "suspicious" : "clean";

  const description = raw.is_malicious
    ? "CriminalIP classe cette IP comme malveillante. À bloquer."
    : flags.length > 0
    ? `CriminalIP signale : ${flags.join(", ")}. Score entrant ${inb}/100.`
    : `Aucun signal fort chez CriminalIP (score entrant ${inb}/100).`;

  return {
    verdict,
    scoreLabel: `${inb}/100`,
    rows: [
      { label: "Score entrant", value: `${inb}/100` },
      { label: "Score sortant", value: `${outb}/100` },
      { label: "Drapeaux", value: flags.length ? flags.join(" · ") : "aucun" },
      { label: "Ports ouverts", value: raw.open_ports != null ? String(raw.open_ports) : "—" },
      { label: "Pays", value: (raw.country as string) || "—" },
    ],
    description,
  };
}

function summarizeShodan(raw: Record<string, unknown> | null): SourceSummary {
  if (!raw || Object.keys(raw).length === 0 || raw.not_found) {
    return {
      verdict: raw?.not_found ? "clean" : "unknown",
      scoreLabel: "—",
      rows: raw?.not_found ? [{ label: "Statut", value: "Aucune exposition indexée" }] : [],
      description: raw?.not_found
        ? "Shodan n'a aucune entrée pour cette IP : aucun service exposé n'a été indexé (bon signe)."
        : "Aucune donnée Shodan (clé non configurée).",
    };
  }
  const ports = (raw.ports as number[]) ?? [];
  const vulnCount = Number(raw.vuln_count ?? 0);
  const vulns = (raw.vulns as string[]) ?? [];
  const org = (raw.org as string) || "—";

  const verdict: Verdict = vulnCount >= 1 ? "suspicious" : ports.length > 0 ? "clean" : "unknown";

  const description =
    vulnCount >= 1
      ? `Shodan expose ${vulnCount} vulnérabilité(s) connue(s) sur cette IP (${ports.length} ports ouverts). Surface d'attaque à surveiller.`
      : ports.length > 0
      ? `${ports.length} port(s) ouvert(s) exposé(s) sur Internet, sans CVE connue référencée.`
      : "Aucun service exposé indexé.";

  return {
    verdict,
    scoreLabel: `${ports.length} ports`,
    rows: [
      { label: "Ports ouverts", value: ports.length ? ports.slice(0, 15).join(", ") : "—" },
      { label: "Vulnérabilités (CVE)", value: vulnCount ? `${vulnCount} — ${vulns.slice(0, 5).join(", ")}` : "0" },
      { label: "Organisation", value: org },
      { label: "OS", value: (raw.os as string) || "—" },
      { label: "Hostnames", value: ((raw.hostnames as string[]) ?? []).slice(0, 3).join(", ") || "—" },
      { label: "Tags", value: ((raw.tags as string[]) ?? []).join(", ") || "—" },
    ],
    description,
  };
}

function summarizeVirusTotal(raw: Record<string, unknown> | null, type: string): SourceSummary {
  if (!raw || Object.keys(raw).length === 0) {
    return {
      verdict: "unknown",
      scoreLabel: "—",
      rows: [],
      description:
        "Aucune donnée renvoyée par VirusTotal. La clé API n'est peut-être pas configurée, ou cet indicateur est inconnu de la base.",
    };
  }
  const attrs = ((raw as { attributes?: Record<string, unknown> }).attributes ?? {}) as Record<string, unknown>;
  const stats = (attrs.last_analysis_stats ?? {}) as Record<string, number>;
  const malicious = stats.malicious ?? 0;
  const suspicious = stats.suspicious ?? 0;
  const harmless = stats.harmless ?? 0;
  const undetected = stats.undetected ?? 0;
  const total = malicious + suspicious + harmless + undetected;
  const reputation = Number(attrs.reputation ?? 0);
  const country = (attrs.country as string) || "—";
  const asnOwner = (attrs.as_owner as string) || "—";
  const lastAnalysis = attrs.last_analysis_date
    ? new Date(Number(attrs.last_analysis_date) * 1000).toLocaleString("fr-FR")
    : "—";

  const verdict: Verdict =
    malicious >= 5 ? "malicious" : malicious + suspicious >= 1 ? "suspicious" : total > 0 ? "clean" : "unknown";

  const description =
    malicious >= 5
      ? `Verdict clair : ${malicious} antivirus sur ${total} considèrent cet indicateur comme malveillant. Évitez tout contact et bloquez-le sur vos pare-feux.`
      : malicious >= 1
      ? `${malicious} moteur(s) signalent un risque (${suspicious} le jugent suspect). À traiter avec prudence et croiser avec les autres sources.`
      : total > 0
      ? `Aucun moteur antivirus n'a flaggé cet indicateur sur ${total} analyses. Considéré comme propre par VirusTotal.`
      : "VirusTotal ne dispose pas d'analyse pour cet indicateur.";

  const rows: Array<{ label: string; value: string }> =
    type === "ip"
      ? [
          { label: "Verdict global", value: `${malicious} malveillants / ${total} moteurs` },
          { label: "Suspects", value: String(suspicious) },
          { label: "Inoffensifs", value: String(harmless) },
          { label: "Réputation communauté", value: String(reputation) },
          { label: "Pays", value: country },
          { label: "Propriétaire ASN", value: asnOwner },
          { label: "Dernière analyse", value: lastAnalysis },
        ]
      : [
          { label: "Verdict global", value: `${malicious} malveillants / ${total} moteurs` },
          { label: "Suspects", value: String(suspicious) },
          { label: "Inoffensifs", value: String(harmless) },
          { label: "Réputation communauté", value: String(reputation) },
          { label: "Dernière analyse", value: lastAnalysis },
        ];

  return {
    verdict,
    scoreLabel: total > 0 ? `${malicious}/${total}` : "—",
    rows,
    description,
  };
}

function SourcePanel({
  name,
  subtitle,
  summary,
}: {
  name: string;
  subtitle: string;
  summary: SourceSummary;
}) {
  const tone = verdictTone(summary.verdict);
  const verdictLabel =
    summary.verdict === "malicious" ? "Malveillant"
    : summary.verdict === "suspicious" ? "Suspect"
    : summary.verdict === "clean" ? "Propre"
    : "Inconnu";
  const Icon =
    summary.verdict === "malicious" ? XCircle
    : summary.verdict === "suspicious" ? AlertTriangle
    : summary.verdict === "clean" ? CheckCircle2
    : Info;

  return (
    <div className="rounded-xl border border-border bg-card p-4 space-y-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-sm font-bold text-foreground">{name}</p>
          <p className="text-[11px] text-muted-foreground">{subtitle}</p>
        </div>
        <span className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-[11px] font-bold border ${tone}`}>
          <Icon className="w-3 h-3" />
          {verdictLabel}
          <span className="opacity-60">· {summary.scoreLabel}</span>
        </span>
      </div>

      <p className="text-xs text-foreground leading-relaxed">{summary.description}</p>

      {summary.rows.length > 0 && (
        <div className="rounded-lg border border-border/60 divide-y divide-border/40">
          {summary.rows.map((r) => (
            <div key={r.label} className="flex items-start justify-between gap-3 px-3 py-1.5">
              <span className="text-[11px] text-muted-foreground">{r.label}</span>
              <span className="text-xs font-medium text-foreground text-right break-all">{r.value}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function LookupResultPanel({
  result,
  lookupValue,
  lookupType,
}: {
  result: Record<string, unknown>;
  lookupValue: string;
  lookupType: string;
}) {
  const results = (result.results as Record<string, Record<string, unknown> | null>) ?? {};
  const value = (result.value as string) ?? lookupValue;
  const type = (result.type as string) ?? lookupType;
  const serverVerdict = (result.verdict as { level?: Verdict; score?: number; reasons?: string[] }) ?? {};
  const abuse = summarizeAbuseIPDB(results.abuseipdb ?? null);
  const vt = summarizeVirusTotal(results.virustotal ?? null, type);
  const geo = summarizeGeo(results.geo ?? null);
  const internal = summarizeInternal(results.internal ?? null);
  const criminalip = summarizeCriminalIP(results.criminalip ?? null);
  const shodan = summarizeShodan(results.shodan ?? null);

  // Le verdict global est calculé côté serveur (combine toutes les sources,
  // y compris l'empreinte interne et le réseau — fonctionne sans clé API).
  const overall: Verdict =
    serverVerdict.level ??
    (abuse.verdict === "malicious" || vt.verdict === "malicious"
      ? "malicious"
      : abuse.verdict === "suspicious" || vt.verdict === "suspicious"
      ? "suspicious"
      : "clean");
  const reasons = serverVerdict.reasons ?? [];

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="mt-4 space-y-3"
    >
      {/* Synthèse globale */}
      <div className={`rounded-xl border-2 p-4 ${verdictTone(overall)}`}>
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="min-w-0">
            <p className="text-[11px] uppercase tracking-wider opacity-70 font-semibold">Synthèse</p>
            <p className="text-sm font-mono break-all">{value}</p>
          </div>
          <span className="text-xs font-bold uppercase">
            {overall === "malicious" ? "À bloquer immédiatement"
              : overall === "suspicious" ? "Surveillance recommandée"
              : overall === "clean" ? "Aucun risque détecté"
              : "Données insuffisantes"}
          </span>
        </div>
        <p className="text-xs mt-2 leading-relaxed text-foreground/80">
          {overall === "malicious"
            ? "Activité malveillante confirmée par au moins une source. Bloquez cette adresse et lancez un playbook SOAR."
            : overall === "suspicious"
            ? "Signaux suspects détectés. Croisez avec vos logs internes avant d'agir."
            : overall === "clean"
            ? "Aucun signalement notable. L'indicateur est considéré sûr selon les données disponibles."
            : "Aucune source n'a pu qualifier cet indicateur."}
        </p>
        {reasons.length > 0 && (
          <ul className="mt-2 space-y-1">
            {reasons.map((r, i) => (
              <li key={i} className="text-[11px] flex items-start gap-1.5 text-foreground/70">
                <span className="mt-0.5 opacity-60">▸</span>
                <span>{r}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Panneaux de sources */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {type === "ip" && (
          <SourcePanel
            name="Empreinte interne (SIEM)"
            subtitle="Ce que VOTRE plateforme sait déjà de cette IP"
            summary={internal}
          />
        )}
        {type === "ip" && (
          <SourcePanel
            name="Géolocalisation & réseau"
            subtitle="ip-api — pays, FAI, ASN, proxy/hosting"
            summary={geo}
          />
        )}
        {type === "ip" && (
          <SourcePanel
            name="AbuseIPDB"
            subtitle="Base communautaire de signalements d'IPs"
            summary={abuse}
          />
        )}
        {type === "ip" && (
          <SourcePanel
            name="CriminalIP"
            subtitle="Réputation & exposition — scanner, Tor/VPN, malveillance"
            summary={criminalip}
          />
        )}
        {type === "ip" && (
          <SourcePanel
            name="Shodan"
            subtitle="Surface d'attaque — ports ouverts, services, CVE"
            summary={shodan}
          />
        )}
        <SourcePanel
          name="VirusTotal"
          subtitle={
            type === "ip" ? "Agrégateur multi-AV — analyse IP"
              : type === "domain" ? "Agrégateur multi-AV — analyse domaine"
              : "Agrégateur multi-AV — analyse de fichier"
          }
          summary={vt}
        />
      </div>

      {/* JSON brut repliable */}
      <details className="rounded-lg border border-border/50 bg-muted/30 px-3 py-2">
        <summary className="text-[11px] cursor-pointer text-muted-foreground hover:text-foreground select-none">
          Voir la réponse JSON brute (pour analystes)
        </summary>
        <pre className="text-[10px] text-muted-foreground overflow-auto max-h-64 mt-2 font-mono">
          {JSON.stringify(results, null, 2)}
        </pre>
      </details>
    </motion.div>
  );
}

function ScoreBadge({ score }: { score: number }) {
  const color =
    score >= 75 ? "bg-red-500/20 text-red-400 border-red-500/30" :
    score >= 50 ? "bg-orange-500/20 text-orange-400 border-orange-500/30" :
    score >= 25 ? "bg-yellow-500/20 text-yellow-400 border-yellow-500/30" :
    "bg-green-500/20 text-green-400 border-green-500/30";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold border ${color}`}>
      {score.toFixed(0)}/100
    </span>
  );
}

function KPICard({ title, value, icon: Icon, color }: { title: string; value: number | string; icon: React.ElementType; color: string }) {
  return (
    <Card className="card-gradient border-border/50">
      <CardContent className="p-5">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs text-muted-foreground">{title}</p>
            <p className="text-2xl font-bold text-foreground mt-1">{value}</p>
          </div>
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${color}`}>
            <Icon className="w-5 h-5" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ─── Auto-detection ──────────────────────────────────────────────────────────

type IndicatorType = "ip" | "domain" | "hash_md5" | "hash_sha256";

interface Detected {
  type: IndicatorType | "unknown";
  label: string;
  hint: string;
  pill: string; // tailwind classes for the badge
}

function detectIndicatorType(raw: string): Detected {
  const v = raw.trim();

  if (!v) return { type: "unknown", label: "", hint: "", pill: "" };

  // IPv4
  if (/^(\d{1,3}\.){3}\d{1,3}$/.test(v))
    return { type: "ip", label: "IPv4", hint: "Adresse IPv4 détectée", pill: "text-blue-400 bg-blue-500/10 border-blue-500/30" };

  // IPv6 (couvre les formes complètes et abrégées ::)
  if (/^[0-9a-fA-F]{0,4}(:[0-9a-fA-F]{0,4}){2,7}$/.test(v) && v.includes(":"))
    return { type: "ip", label: "IPv6", hint: "Adresse IPv6 détectée", pill: "text-blue-400 bg-blue-500/10 border-blue-500/30" };

  // MD5 — exactement 32 hex
  if (/^[a-fA-F0-9]{32}$/.test(v))
    return { type: "hash_md5", label: "MD5", hint: "Hash MD5 (32 caractères)", pill: "text-purple-400 bg-purple-500/10 border-purple-500/30" };

  // SHA-256 — exactement 64 hex
  if (/^[a-fA-F0-9]{64}$/.test(v))
    return { type: "hash_sha256", label: "SHA-256", hint: "Hash SHA-256 (64 caractères)", pill: "text-purple-400 bg-purple-500/10 border-purple-500/30" };

  // SHA-1 — exactement 40 hex (affiché mais mappé sur hash_md5)
  if (/^[a-fA-F0-9]{40}$/.test(v))
    return { type: "hash_md5", label: "SHA-1", hint: "Hash SHA-1 (40 caractères)", pill: "text-violet-400 bg-violet-500/10 border-violet-500/30" };

  // Domain — au moins un point, pas d'IP, pas d'espace
  if (/^(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$/.test(v))
    return { type: "domain", label: "Domaine", hint: "Nom de domaine détecté", pill: "text-emerald-400 bg-emerald-500/10 border-emerald-500/30" };

  // URL → extrait le hostname et re-détecte
  try {
    const url = new URL(v.startsWith("http") ? v : `https://${v}`);
    const host = url.hostname;
    if (host && /^(\d{1,3}\.){3}\d{1,3}$/.test(host))
      return { type: "ip", label: "URL (IP)", hint: "URL contenant une adresse IP", pill: "text-blue-400 bg-blue-500/10 border-blue-500/30" };
    if (host && /^(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$/.test(host))
      return { type: "domain", label: "URL", hint: "URL — domaine extrait automatiquement", pill: "text-emerald-400 bg-emerald-500/10 border-emerald-500/30" };
  } catch { /* pas une URL valide */ }

  return { type: "unknown", label: "?", hint: "Type non reconnu — vérifiez la valeur", pill: "text-muted-foreground bg-secondary/40 border-border" };
}

// ─── Page ─────────────────────────────────────────────────────────────────────

function ThreatIntelPageInner() {
  const [lookupValue, setLookupValue] = useState("");
  const [lookupResult, setLookupResult] = useState<Record<string, unknown> | null>(null);
  const [isLookingUp, setIsLookingUp] = useState(false);
  const searchParams = useSearchParams();
  const autoRanFor = useRef<string | null>(null);

  const detected = detectIndicatorType(lookupValue);
  const lookupType = detected.type !== "unknown" ? detected.type : "ip";
  const qc = useQueryClient();

  const { data: stats } = useQuery({
    queryKey: ["cti-stats"],
    queryFn: () => threatIntelApi.getStats(),
    refetchInterval: 60000,
  });

  const { data: indicatorsData, isLoading } = useQuery({
    queryKey: ["threat-indicators"],
    queryFn: () => threatIntelApi.getIndicators({ is_malicious: true }),
    refetchInterval: 30000,
  });

  const { data: threatsData } = useQuery({
    queryKey: ["enriched-threats"],
    queryFn: () => threatIntelApi.getEnrichedLogs({ is_threat: true }),
    refetchInterval: 30000,
  });

  const enrichMutation = useMutation({
    mutationFn: threatIntelApi.triggerEnrichment,
    onSuccess: () => {
      toast.success("Enrichissement CTI lancé");
      qc.invalidateQueries({ queryKey: ["cti-stats"] });
    },
  });

  const runLookup = useCallback(async (value: string, type: string) => {
    if (!value.trim()) return;
    setIsLookingUp(true);
    try {
      const result = await threatIntelApi.lookupIndicator(value.trim(), type);
      setLookupResult(result);
    } catch (err: unknown) {
      const e = err as { code?: string; response?: { status?: number; data?: { message?: string } } };
      if (e?.code === "ERR_NETWORK" || !e?.response) {
        toast.error("Impossible de joindre le backend. Vérifiez que le serveur est lancé.");
      } else {
        const msg = e?.response?.data?.message;
        toast.error(msg ?? `Erreur lookup (HTTP ${e?.response?.status ?? "?"}) — vérifiez la valeur saisie.`);
      }
    } finally {
      setIsLookingUp(false);
    }
  }, []);

  const handleLookup = () => runLookup(lookupValue, lookupType);

  // Pivot : /threat-intel?ip=1.2.3.4 pré-remplit et lance le lookup automatiquement.
  useEffect(() => {
    const ip = searchParams.get("ip") || searchParams.get("q");
    if (ip && autoRanFor.current !== ip) {
      autoRanFor.current = ip;
      setLookupValue(ip);
      const d = detectIndicatorType(ip);
      runLookup(ip, d.type !== "unknown" ? d.type : "ip");
    }
  }, [searchParams, runLookup]);

  const indicators = indicatorsData?.results ?? [];
  const threats = threatsData?.results ?? [];

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Threat Intelligence</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Enrichissement CTI — SIEM interne · géoloc · AbuseIPDB · CriminalIP · Shodan · VirusTotal
          </p>
        </div>
        <Button
          onClick={() => enrichMutation.mutate()}
          disabled={enrichMutation.isPending}
          className="flex items-center gap-2"
        >
          <RefreshCw className={`w-4 h-4 ${enrichMutation.isPending ? "animate-spin" : ""}`} />
          Enrichir maintenant
        </Button>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard title="Indicateurs totaux" value={stats?.total_indicators ?? 0} icon={Shield} color="bg-blue-500/15 text-blue-400" />
        <KPICard title="IoC malveillants" value={stats?.malicious_indicators ?? 0} icon={AlertTriangle} color="bg-red-500/15 text-red-400" />
        <KPICard title="Menaces 24h" value={stats?.threats_24h ?? 0} icon={Zap} color="bg-orange-500/15 text-orange-400" />
        <KPICard title="Menaces 7j" value={stats?.threats_7d ?? 0} icon={TrendingUp} color="bg-purple-500/15 text-purple-400" />
      </div>

      {/* Lookup */}
      <Card className="card-gradient border-border/50">
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Search className="w-4 h-4 text-primary" />
            Lookup d'indicateur
          </CardTitle>
        </CardHeader>
        <CardContent>
          {/* Champ de saisie avec détection automatique */}
          <div className="flex gap-3">
            <div className="relative flex-1">
              <Input
                placeholder="IP, domaine, hash MD5 / SHA-256 — détection automatique"
                value={lookupValue}
                onChange={(e) => {
                  setLookupValue(e.target.value);
                  setLookupResult(null);
                }}
                onKeyDown={(e) => e.key === "Enter" && handleLookup()}
                className="pr-24 font-mono text-sm"
                autoComplete="off"
                spellCheck={false}
              />
              {/* Badge de détection flottant dans le champ */}
              <div className="absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none">
                {lookupValue.trim() && (
                  <span
                    className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-bold border ${detected.pill}`}
                    title={detected.hint}
                  >
                    {detected.label}
                  </span>
                )}
              </div>
            </div>
            <Button
              onClick={handleLookup}
              disabled={!lookupValue.trim() || detected.type === "unknown" || isLookingUp}
            >
              {isLookingUp ? (
                <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Search className="w-4 h-4 mr-2" />
              )}
              Analyser
            </Button>
          </div>

          {/* Hint sous le champ */}
          <div className="mt-1.5 min-h-[16px]">
            {lookupValue.trim() && detected.type !== "unknown" && (
              <p className="text-[11px] text-muted-foreground">{detected.hint}</p>
            )}
            {lookupValue.trim() && detected.type === "unknown" && (
              <p className="text-[11px] text-orange-400">{detected.hint} — entrez une IP, un domaine ou un hash valide.</p>
            )}
            {!lookupValue.trim() && (
              <p className="text-[11px] text-muted-foreground">
                Exemples : <span className="font-mono">185.220.101.42</span> · <span className="font-mono">evil.example.com</span> · <span className="font-mono">d41d8cd98f00b204e9800998ecf8427e</span>
              </p>
            )}
          </div>

          {lookupResult && (
            <LookupResultPanel
              result={lookupResult}
              lookupValue={lookupValue}
              lookupType={lookupType}
            />
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top IPs malveillantes */}
        <Card className="card-gradient border-border/50">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-red-400" />
              Top IPs malveillantes
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="space-y-2">
                {[...Array(5)].map((_, i) => (
                  <div key={i} className="h-8 bg-secondary/40 rounded animate-pulse" />
                ))}
              </div>
            ) : (
              <div className="space-y-2">
                {(stats?.top_malicious_ips ?? []).map((item, i) => (
                  <div key={i} className="flex items-center justify-between py-2 border-b border-border/30">
                    <div className="flex items-center gap-2">
                      <Globe className="w-3 h-3 text-muted-foreground" />
                      <span className="text-sm font-mono text-foreground">{item.value}</span>
                      <Badge variant="outline" className="text-[10px] capitalize">{item.source}</Badge>
                    </div>
                    <ScoreBadge score={item.reputation_score} />
                  </div>
                ))}
                {(stats?.top_malicious_ips ?? []).length === 0 && (
                  <p className="text-sm text-muted-foreground text-center py-4">Aucune IP malveillante détectée</p>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Logs enrichis récents */}
        <Card className="card-gradient border-border/50">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Eye className="w-4 h-4 text-orange-400" />
              Logs enrichis — menaces actives
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {threats.slice(0, 8).map((threat) => (
                <div key={threat.id} className="flex items-center justify-between py-2 border-b border-border/30">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-mono text-foreground truncate">{threat.source_ip || "—"}</p>
                    <p className="text-xs text-muted-foreground truncate">{threat.user_email || "utilisateur inconnu"}</p>
                  </div>
                  <div className="flex items-center gap-2 ml-2">
                    <ScoreBadge score={threat.max_score} />
                  </div>
                </div>
              ))}
              {threats.length === 0 && (
                <p className="text-sm text-muted-foreground text-center py-4">
                  Aucune menace CTI active
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Distribution par source */}
      {stats && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card className="card-gradient border-border/50">
            <CardHeader>
              <CardTitle className="text-base">Distribution par source CTI</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {stats.by_source.map((s) => (
                  <div key={s.source} className="flex items-center gap-3">
                    <span className="text-sm text-muted-foreground w-24 capitalize">{s.source}</span>
                    <div className="flex-1 h-2 bg-secondary/50 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-primary rounded-full transition-all"
                        style={{ width: `${Math.min((s.count / (stats.total_indicators || 1)) * 100, 100)}%` }}
                      />
                    </div>
                    <span className="text-sm font-bold text-foreground w-10 text-right">{s.count}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card className="card-gradient border-border/50">
            <CardHeader>
              <CardTitle className="text-base">Distribution par type d'indicateur</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {stats.by_type.map((t) => (
                  <div key={t.indicator_type} className="flex items-center gap-3">
                    <span className="text-sm text-muted-foreground w-24 capitalize">{t.indicator_type}</span>
                    <div className="flex-1 h-2 bg-secondary/50 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-blue-500 rounded-full transition-all"
                        style={{ width: `${Math.min((t.count / (stats.total_indicators || 1)) * 100, 100)}%` }}
                      />
                    </div>
                    <span className="text-sm font-bold text-foreground w-10 text-right">{t.count}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

export default function ThreatIntelPage() {
  return (
    <Suspense fallback={null}>
      <ThreatIntelPageInner />
    </Suspense>
  );
}
