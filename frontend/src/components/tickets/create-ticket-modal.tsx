"use client";

import { useEffect, useState } from "react";
import { Plus, Ticket as TicketIcon } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useCreateTicket, useAssignableUsers } from "@/hooks/use-tickets";
import type { AlertSeverity, TicketPriority } from "@/types";
import toast from "react-hot-toast";

const SEVERITY_TO_PRIORITY: Record<AlertSeverity, TicketPriority> = {
  low: "low",
  medium: "medium",
  high: "high",
  critical: "critical",
};

export interface CreateTicketModalProps {
  open: boolean;
  onClose: () => void;
  onCreated?: (ticketId: string) => void;
  /** Pré-remplissage depuis une alerte (bouton "Créer un ticket" sur une alerte). */
  fromAlert?: {
    id: string;
    title: string;
    description: string;
    severity: AlertSeverity;
  } | null;
}

export function CreateTicketModal({ open, onClose, onCreated, fromAlert }: CreateTicketModalProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState<TicketPriority>("medium");
  const [assignee, setAssignee] = useState<string>("");
  const [dueDate, setDueDate] = useState("");

  const { data: users = [] } = useAssignableUsers();
  const createMutation = useCreateTicket();

  useEffect(() => {
    if (!open) return;
    if (fromAlert) {
      setTitle(fromAlert.title);
      setDescription(fromAlert.description);
      setPriority(SEVERITY_TO_PRIORITY[fromAlert.severity]);
    } else {
      setTitle("");
      setDescription("");
      setPriority("medium");
    }
    setAssignee("");
    setDueDate("");
  }, [open, fromAlert]);

  const handleSubmit = async () => {
    if (!title.trim()) {
      toast.error("Le titre est requis.");
      return;
    }
    try {
      const ticket = await createMutation.mutateAsync({
        title: title.trim(),
        description: description.trim(),
        priority,
        alert: fromAlert?.id,
        assignee: assignee || undefined,
        due_date: dueDate ? new Date(dueDate).toISOString() : undefined,
      });
      toast.success(`${ticket.display_id} créé avec succès.`);
      onCreated?.(ticket.id);
      onClose();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      toast.error(msg ?? "Erreur lors de la création du ticket.");
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-lg">
        <DialogHeader className="pb-1">
          <DialogTitle className="flex items-center gap-2 text-base font-semibold">
            <TicketIcon className="w-4 h-4 text-primary" />
            {fromAlert ? "Créer un ticket depuis cette alerte" : "Créer un ticket"}
          </DialogTitle>
          {fromAlert && (
            <p className="text-sm text-muted-foreground pt-1">
              Le ticket sera lié à l&apos;alerte et hérite de sa sévérité comme priorité — modifiable ci-dessous.
            </p>
          )}
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label className="text-sm font-medium text-foreground">
              Titre <span className="text-destructive">*</span>
            </Label>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Ex: Investiguer connexion suspecte depuis 10.0.0.5"
              className="h-10 text-sm"
              autoFocus
            />
          </div>

          <div className="space-y-2">
            <Label className="text-sm font-medium text-foreground">Description</Label>
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Détails, contexte, étapes de reproduction…"
              rows={4}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label className="text-sm font-medium text-foreground">Priorité</Label>
              <Select value={priority} onValueChange={(v) => setPriority(v as TicketPriority)}>
                <SelectTrigger className="h-10 text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="low">Faible</SelectItem>
                  <SelectItem value="medium">Moyenne</SelectItem>
                  <SelectItem value="high">Élevée</SelectItem>
                  <SelectItem value="critical">Critique</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label className="text-sm font-medium text-foreground">Assigné à</Label>
              <Select value={assignee} onValueChange={setAssignee}>
                <SelectTrigger className="h-10 text-sm">
                  <SelectValue placeholder="Non assigné" />
                </SelectTrigger>
                <SelectContent>
                  {users.map((u) => (
                    <SelectItem key={u.id} value={u.id}>
                      {u.full_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-2">
            <Label className="text-sm font-medium text-foreground">Échéance (optionnel)</Label>
            <Input type="datetime-local" value={dueDate} onChange={(e) => setDueDate(e.target.value)} className="h-10 text-sm" />
          </div>
        </div>

        <div className="flex justify-end gap-3 pt-4 border-t border-border">
          <Button variant="outline" onClick={onClose} className="text-sm">
            Annuler
          </Button>
          <Button onClick={handleSubmit} disabled={createMutation.isPending} className="gap-2 text-sm">
            <Plus className="w-4 h-4" />
            {createMutation.isPending ? "Création…" : "Créer le ticket"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
