"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ShieldCheck, Target } from "lucide-react";
import { mitreApi, complianceApi } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const FRAMEWORKS: { value: string; label: string }[] = [
  { value: "iso27001", label: "ISO 27001:2022" },
  { value: "pci_dss", label: "PCI DSS v4.0" },
  { value: "nist_csf", label: "NIST CSF 2.0" },
  { value: "gdpr", label: "RGPD" },
];

function CoverageBar({ percent, label }: { percent: number; label: string }) {
  const color = percent >= 70 ? "bg-emerald-500" : percent >= 40 ? "bg-amber-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-2 bg-secondary/50 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${percent}%` }} />
      </div>
      <span className="text-xs font-bold text-foreground w-24 text-right shrink-0">{label}</span>
    </div>
  );
}

export function CoveragePanel() {
  const [open, setOpen] = useState(false);
  const [framework, setFramework] = useState("iso27001");

  const { data: mitreCoverage } = useQuery({
    queryKey: ["mitre-coverage"],
    queryFn: () => mitreApi.getCoverage(),
    enabled: open,
  });

  const { data: complianceCoverage } = useQuery({
    queryKey: ["compliance-coverage", framework],
    queryFn: () => complianceApi.getCoverage(framework),
    enabled: open,
  });

  return (
    <Card className="card-gradient border-border/50">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between p-4 text-left"
      >
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-primary" />
          <span className="text-sm font-semibold text-foreground">
            Couverture MITRE ATT&CK &amp; Conformité (en continu)
          </span>
        </div>
        <ChevronDown className={`w-4 h-4 text-muted-foreground transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <CardContent className="pt-0 space-y-5">
          {/* MITRE ATT&CK */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
                <Target className="w-3.5 h-3.5" /> MITRE ATT&CK
              </p>
              {mitreCoverage && (
                <span className="text-xs text-muted-foreground">
                  {mitreCoverage.covered_count}/{mitreCoverage.total_count} techniques couvertes
                </span>
              )}
            </div>
            {mitreCoverage && <CoverageBar percent={mitreCoverage.coverage_percent} label={`${mitreCoverage.coverage_percent}%`} />}
            <div className="mt-3 space-y-2 max-h-64 overflow-y-auto">
              {mitreCoverage?.matrix.map((tactic) => (
                <div key={tactic.tactic_id}>
                  <p className="text-[11px] font-semibold text-muted-foreground mb-1">{tactic.tactic}</p>
                  <div className="flex flex-wrap gap-1.5">
                    {tactic.techniques.map((tech) => (
                      <span
                        key={tech.id}
                        title={tech.covered ? `Couvert par : ${tech.covering_rules?.join(", ")}` : "Non couvert"}
                        className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${
                          tech.covered
                            ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                            : "border-border bg-secondary/30 text-muted-foreground"
                        }`}
                      >
                        {tech.id}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Compliance */}
          <div>
            <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Contrôles de conformité
              </p>
              <div className="flex gap-1">
                {FRAMEWORKS.map((fw) => (
                  <button
                    key={fw.value}
                    onClick={() => setFramework(fw.value)}
                    className={`text-[11px] px-2 py-1 rounded border transition-colors ${
                      framework === fw.value
                        ? "border-primary/40 bg-primary/10 text-primary font-semibold"
                        : "border-border text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {fw.label}
                  </button>
                ))}
              </div>
            </div>
            {complianceCoverage && (
              <>
                <CoverageBar
                  percent={complianceCoverage.coverage_percent}
                  label={`${complianceCoverage.covered_count}/${complianceCoverage.total_count}`}
                />
                <div className="mt-3 space-y-1.5 max-h-64 overflow-y-auto">
                  {complianceCoverage.controls.map((control) => (
                    <div key={control.id} className="flex items-center justify-between gap-2 py-1 border-b border-border/20">
                      <div className="min-w-0">
                        <span className="text-xs font-mono text-foreground">{control.id}</span>
                        <span className="text-xs text-muted-foreground ml-2 truncate">{control.title}</span>
                      </div>
                      <Badge
                        variant="outline"
                        className={`text-[10px] shrink-0 ${
                          control.covered
                            ? "border-emerald-500/30 text-emerald-400"
                            : "border-border text-muted-foreground"
                        }`}
                      >
                        {control.covered ? `Couvert (${control.covering_rules.length})` : "Non couvert"}
                      </Badge>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </CardContent>
      )}
    </Card>
  );
}
