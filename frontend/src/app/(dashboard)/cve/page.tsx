"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Bug, ShieldAlert, RefreshCw, Plus, Skull, Server, X } from "lucide-react";
import { cveApi, assetsApi } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import toast from "react-hot-toast";
import type { Asset, AssetType, AssetCriticality } from "@/types";

function KPICard({
  title,
  value,
  icon: Icon,
  color,
}: {
  title: string;
  value: number | string;
  icon: React.ElementType;
  color: string;
}) {
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

const ASSET_TYPES: { value: AssetType; label: string }[] = [
  { value: "server", label: "Serveur" },
  { value: "workstation", label: "Poste de travail" },
  { value: "network_device", label: "Équipement réseau" },
  { value: "application", label: "Application" },
  { value: "cloud_service", label: "Service cloud" },
  { value: "other", label: "Autre" },
];

const CRITICALITIES: { value: AssetCriticality; label: string }[] = [
  { value: "low", label: "Faible" },
  { value: "medium", label: "Moyen" },
  { value: "high", label: "Élevé" },
  { value: "critical", label: "Critique" },
];

function AddAssetForm({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    name: "",
    asset_type: "server" as AssetType,
    vendor: "",
    product: "",
    version: "",
    criticality: "medium" as AssetCriticality,
  });

  const createMutation = useMutation({
    mutationFn: () => assetsApi.createAsset(form),
    onSuccess: () => {
      toast.success("Actif ajouté à l'inventaire");
      qc.invalidateQueries({ queryKey: ["assets"] });
      onClose();
    },
    onError: () => toast.error("Erreur lors de l'ajout de l'actif"),
  });

  return (
    <Card className="card-gradient border-border/50">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">Ajouter un actif à l'inventaire</CardTitle>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="w-4 h-4" />
          </button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Input
            placeholder="Nom de l'actif (ex: srv-web-01)"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
          <select
            className="rounded-md border border-input bg-background px-3 py-2 text-sm"
            value={form.asset_type}
            onChange={(e) => setForm({ ...form, asset_type: e.target.value as AssetType })}
          >
            {ASSET_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
          <Input
            placeholder="Éditeur (ex: Microsoft, Apache)"
            value={form.vendor}
            onChange={(e) => setForm({ ...form, vendor: e.target.value })}
          />
          <Input
            placeholder="Produit (ex: Windows Server, Tomcat)"
            value={form.product}
            onChange={(e) => setForm({ ...form, product: e.target.value })}
          />
          <Input
            placeholder="Version"
            value={form.version}
            onChange={(e) => setForm({ ...form, version: e.target.value })}
          />
          <select
            className="rounded-md border border-input bg-background px-3 py-2 text-sm"
            value={form.criticality}
            onChange={(e) => setForm({ ...form, criticality: e.target.value as AssetCriticality })}
          >
            {CRITICALITIES.map((c) => (
              <option key={c.value} value={c.value}>Criticité : {c.label}</option>
            ))}
          </select>
        </div>
        <Button
          onClick={() => createMutation.mutate()}
          disabled={!form.name.trim() || createMutation.isPending}
        >
          Ajouter
        </Button>
      </CardContent>
    </Card>
  );
}

function AssetRow({ asset }: { asset: Asset }) {
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-border/30 gap-3">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <Server className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
          <p className="text-sm font-medium text-foreground truncate">{asset.name}</p>
          <Badge variant="outline" className="text-[10px] capitalize shrink-0">{asset.criticality}</Badge>
        </div>
        <p className="text-xs text-muted-foreground truncate ml-5">
          {[asset.vendor, asset.product, asset.version].filter(Boolean).join(" ") || "—"}
        </p>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {asset.kev_vulnerabilities_count > 0 && (
          <Badge className="bg-red-500/15 text-red-400 border-red-500/30 text-[10px] flex items-center gap-1">
            <Skull className="w-3 h-3" /> {asset.kev_vulnerabilities_count} KEV
          </Badge>
        )}
        {asset.open_vulnerabilities_count > 0 && (
          <Badge variant="outline" className="text-[10px]">{asset.open_vulnerabilities_count} CVE</Badge>
        )}
      </div>
    </div>
  );
}

export default function CVEPage() {
  const [showAddAsset, setShowAddAsset] = useState(false);
  const qc = useQueryClient();

  const { data: cveStats } = useQuery({
    queryKey: ["cve-stats"],
    queryFn: () => cveApi.getStats(),
    refetchInterval: 60000,
  });

  const { data: kevData, isLoading: kevLoading } = useQuery({
    queryKey: ["cves-kev"],
    queryFn: () => cveApi.getCVEs({ is_kev: true, ordering: "-kev_date_added" }),
    refetchInterval: 60000,
  });

  const { data: assetsData, isLoading: assetsLoading } = useQuery({
    queryKey: ["assets"],
    queryFn: () => assetsApi.getAssets(),
  });

  const { data: vulnsData } = useQuery({
    queryKey: ["asset-vulnerabilities", "open"],
    queryFn: () => assetsApi.getVulnerabilities({ status: "open" }),
  });

  const syncMutation = useMutation({
    mutationFn: cveApi.triggerSync,
    onSuccess: () => {
      toast.success("Synchronisation CVE/KEV lancée (NVD + CISA) — quelques minutes");
      qc.invalidateQueries({ queryKey: ["cve-stats"] });
    },
  });

  const correlateMutation = useMutation({
    mutationFn: assetsApi.triggerCorrelation,
    onSuccess: () => {
      toast.success("Corrélation actifs ↔ CVE relancée");
      qc.invalidateQueries({ queryKey: ["asset-vulnerabilities"] });
    },
  });

  const assets = assetsData?.results ?? [];
  const kevList = kevData?.results ?? [];
  const openVulns = vulnsData?.results ?? [];

  return (
    <div className="page p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Vulnérabilités & Actifs</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Sync automatique NVD + CISA KEV (vulnérabilités exploitées activement) et corrélation avec votre inventaire
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setShowAddAsset((v) => !v)} className="flex items-center gap-2">
            <Plus className="w-4 h-4" /> Ajouter un actif
          </Button>
          <Button onClick={() => syncMutation.mutate()} disabled={syncMutation.isPending} className="flex items-center gap-2">
            <RefreshCw className={`w-4 h-4 ${syncMutation.isPending ? "animate-spin" : ""}`} />
            Synchroniser CVE/KEV
          </Button>
        </div>
      </div>

      {showAddAsset && <AddAssetForm onClose={() => setShowAddAsset(false)} />}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard title="CVE en base" value={cveStats?.total ?? 0} icon={Bug} color="bg-blue-500/15 text-blue-400" />
        <KPICard
          title="Exploitées activement (KEV)"
          value={cveStats?.kev_count ?? 0}
          icon={Skull}
          color="bg-red-500/15 text-red-400"
        />
        <KPICard title="Sévérité critique" value={cveStats?.critical_count ?? 0} icon={ShieldAlert} color="bg-orange-500/15 text-orange-400" />
        <KPICard title="Expositions ouvertes" value={openVulns.length} icon={Server} color="bg-purple-500/15 text-purple-400" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="card-gradient border-border/50">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Skull className="w-4 h-4 text-red-400" />
              CISA KEV — exploitées activement dans la nature
            </CardTitle>
          </CardHeader>
          <CardContent>
            {kevLoading ? (
              <div className="space-y-2">
                {[...Array(5)].map((_, i) => <div key={i} className="h-10 bg-secondary/40 rounded animate-pulse" />)}
              </div>
            ) : (
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {kevList.slice(0, 15).map((cve) => (
                  <div key={cve.id} className="py-2 border-b border-border/30">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-mono font-semibold text-foreground">{cve.cve_id}</span>
                      <div className="flex gap-1.5 shrink-0">
                        {cve.kev_ransomware_use && (
                          <Badge className="bg-red-500/15 text-red-400 border-red-500/30 text-[10px]">Ransomware</Badge>
                        )}
                        {cve.cvss_score != null && (
                          <Badge variant="outline" className="text-[10px]">CVSS {cve.cvss_score.toFixed(1)}</Badge>
                        )}
                      </div>
                    </div>
                    <p className="text-xs text-muted-foreground truncate">
                      {cve.vendor_project} {cve.product}
                    </p>
                  </div>
                ))}
                {kevList.length === 0 && (
                  <p className="text-sm text-muted-foreground text-center py-6">
                    Aucune CVE KEV synchronisée — cliquez sur « Synchroniser CVE/KEV ».
                  </p>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="card-gradient border-border/50">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base flex items-center gap-2">
                <Server className="w-4 h-4 text-primary" />
                Inventaire d'actifs
              </CardTitle>
              <Button
                variant="outline"
                size="sm"
                onClick={() => correlateMutation.mutate()}
                disabled={correlateMutation.isPending}
              >
                <RefreshCw className={`w-3.5 h-3.5 ${correlateMutation.isPending ? "animate-spin" : ""}`} />
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {assetsLoading ? (
              <div className="space-y-2">
                {[...Array(4)].map((_, i) => <div key={i} className="h-10 bg-secondary/40 rounded animate-pulse" />)}
              </div>
            ) : (
              <div className="max-h-96 overflow-y-auto">
                {assets.map((asset) => <AssetRow key={asset.id} asset={asset} />)}
                {assets.length === 0 && (
                  <p className="text-sm text-muted-foreground text-center py-6">
                    Aucun actif renseigné. Ajoutez vos serveurs/applications pour activer la corrélation CVE.
                  </p>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
