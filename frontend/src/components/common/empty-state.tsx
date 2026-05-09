import { motion } from "framer-motion";
import { type LucideIcon, SearchX, Bell, FileText, GitBranch, Database, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
  className?: string;
}

export function EmptyState({ icon: Icon = SearchX, title, description, action, className }: EmptyStateProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className={`flex flex-col items-center justify-center py-16 px-8 text-center ${className}`}
    >
      {/* Animated icon container */}
      <div className="relative mb-6">
        <div
          className="w-20 h-20 rounded-2xl flex items-center justify-center"
          style={{
            background: "linear-gradient(135deg, rgba(59,130,246,0.1), rgba(6,182,212,0.05))",
            border: "1px solid rgba(59,130,246,0.2)",
          }}
        >
          <Icon className="w-9 h-9 text-muted-foreground" strokeWidth={1.2} />
        </div>
        {/* Decorative rings */}
        <div
          className="absolute inset-0 rounded-2xl border border-blue-500/10"
          style={{ transform: "scale(1.2)" }}
        />
        <div
          className="absolute inset-0 rounded-2xl border border-blue-500/05"
          style={{ transform: "scale(1.4)" }}
        />
      </div>

      <h3 className="text-base font-semibold text-foreground mb-2">{title}</h3>
      {description && (
        <p className="text-sm text-muted-foreground max-w-sm leading-relaxed mb-6">{description}</p>
      )}
      {action && (
        <Button onClick={action.onClick} size="sm">
          {action.label}
        </Button>
      )}
    </motion.div>
  );
}

// Preset empty states
export function NoAlertsState({ onClear }: { onClear?: () => void }) {
  return (
    <EmptyState
      icon={Bell}
      title="Aucune alerte trouvée"
      description="Il n'y a pas d'alertes correspondant à vos filtres actuels. Essayez de modifier vos critères de recherche."
      action={onClear ? { label: "Effacer les filtres", onClick: onClear } : undefined}
    />
  );
}

export function NoLogsState({ onClear }: { onClear?: () => void }) {
  return (
    <EmptyState
      icon={FileText}
      title="Aucun log trouvé"
      description="Aucun log ne correspond à votre recherche. Vérifiez vos filtres ou la plage de dates."
      action={onClear ? { label: "Réinitialiser", onClick: onClear } : undefined}
    />
  );
}

export function NoRulesState({ onCreate }: { onCreate?: () => void }) {
  return (
    <EmptyState
      icon={GitBranch}
      title="Aucune règle de corrélation"
      description="Commencez par créer des règles de corrélation pour détecter automatiquement les menaces."
      action={onCreate ? { label: "Créer une règle", onClick: onCreate } : undefined}
    />
  );
}

export function NoConnectorsState() {
  return (
    <EmptyState
      icon={Database}
      title="Aucun connecteur configuré"
      description="Configurez des connecteurs pour commencer à collecter des logs depuis vos sources de données."
    />
  );
}

export function ErrorState({ message, onRetry }: { message?: string; onRetry?: () => void }) {
  return (
    <EmptyState
      icon={AlertCircle}
      title="Une erreur est survenue"
      description={message || "Impossible de charger les données. Vérifiez votre connexion et réessayez."}
      action={onRetry ? { label: "Réessayer", onClick: onRetry } : undefined}
    />
  );
}
