"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Ban, ShieldOff, Plus } from "lucide-react";
import { soarApi } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import toast from "react-hot-toast";

const SOURCE_LABELS: Record<string, string> = {
  soar_playbook: "Playbook SOAR",
  manual: "Manuel",
  threat_intel: "Threat Intel",
};

export function BlockedIPsPanel() {
  const [newIp, setNewIp] = useState("");
  const qc = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["blocked-ips"],
    queryFn: () => soarApi.getBlockedIPs({ is_active: true }),
    refetchInterval: 30000,
  });

  const blockMutation = useMutation({
    mutationFn: () => soarApi.blockIP(newIp.trim(), "Blocage manuel depuis le tableau de bord"),
    onSuccess: () => {
      toast.success(`IP ${newIp.trim()} bloquée — effective sur toute la plateforme`);
      setNewIp("");
      qc.invalidateQueries({ queryKey: ["blocked-ips"] });
    },
    onError: () => toast.error("Erreur lors du blocage"),
  });

  const unblockMutation = useMutation({
    mutationFn: (id: string) => soarApi.unblockIP(id),
    onSuccess: () => {
      toast.success("Blocage levé");
      qc.invalidateQueries({ queryKey: ["blocked-ips"] });
    },
  });

  const blockedIPs = data?.results ?? [];

  return (
    <Card className="card-gradient border-border/50">
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          <Ban className="w-4 h-4 text-red-400" />
          IP bloquées ({blockedIPs.length})
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          Blocage effectif immédiatement sur la plateforme (403 sur toute requête API), en plus d'un éventuel firewall externe.
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex gap-2">
          <Input
            placeholder="Bloquer une IP manuellement (ex: 185.220.101.42)"
            value={newIp}
            onChange={(e) => setNewIp(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && newIp.trim() && blockMutation.mutate()}
            className="font-mono text-sm"
          />
          <Button onClick={() => blockMutation.mutate()} disabled={!newIp.trim() || blockMutation.isPending}>
            <Plus className="w-4 h-4" />
          </Button>
        </div>

        {isLoading ? (
          <div className="space-y-2">
            {[...Array(3)].map((_, i) => <div key={i} className="h-9 bg-secondary/40 rounded animate-pulse" />)}
          </div>
        ) : (
          <div className="space-y-1.5 max-h-64 overflow-y-auto">
            {blockedIPs.map((b) => (
              <div key={b.id} className="flex items-center justify-between gap-2 py-1.5 border-b border-border/30">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-mono text-foreground">{b.ip_address}</span>
                    <Badge variant="outline" className="text-[10px]">{SOURCE_LABELS[b.source] ?? b.source}</Badge>
                  </div>
                  <p className="text-xs text-muted-foreground truncate">{b.reason}</p>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => unblockMutation.mutate(b.id)}
                  className="text-xs h-7 gap-1.5 shrink-0"
                >
                  <ShieldOff className="w-3 h-3" /> Débloquer
                </Button>
              </div>
            ))}
            {blockedIPs.length === 0 && (
              <p className="text-sm text-muted-foreground text-center py-4">Aucune IP bloquée actuellement</p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
