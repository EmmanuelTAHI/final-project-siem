"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import {
  Plus,
  Search,
  Edit,
  Trash2,
  CheckCircle,
  XCircle,
  Shield,
  User,
  Eye,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useUsers, useAuditTrail } from "@/hooks/use-users";
import { usersApi } from "@/lib/api";
import { cn, getInitials, timeAgo, formatDate } from "@/lib/utils";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import type { User as UserType, UserRole } from "@/types";
import toast from "react-hot-toast";

const roleConfig: Record<UserRole, { label: string; variant: "info" | "cyan" | "secondary"; icon: React.ElementType }> = {
  admin: { label: "Admin", variant: "info", icon: Shield },
  analyst: { label: "Analyste", variant: "cyan", icon: User },
  viewer: { label: "Lecteur", variant: "secondary", icon: Eye },
};

export default function UsersPage() {
  const { data: users = [], refetch } = useUsers();
  const { data: apiAuditTrail } = useAuditTrail();
  const [search, setSearch] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<UserType | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<UserType | null>(null);
  const [saving, setSaving] = useState(false);

  const [form, setForm] = useState({ first_name: "", last_name: "", email: "", role: "analyst" as UserRole, password: "" });

  const filtered = users.filter((u) => {
    if (!search) return true;
    const s = search.toLowerCase();
    return u.full_name.toLowerCase().includes(s) || u.email.toLowerCase().includes(s);
  });

  const handleEdit = (user: UserType) => {
    setEditingUser(user);
    setForm({ first_name: user.first_name, last_name: user.last_name, email: user.email, role: user.role, password: "" });
    setModalOpen(true);
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await usersApi.deleteUser(deleteTarget.id);
      toast.success("Utilisateur supprimé");
      refetch();
    } catch {
      toast.error("Erreur lors de la suppression");
    } finally {
      setDeleteTarget(null);
    }
  };

  const handleSave = async () => {
    if (!form.first_name || !form.email) {
      toast.error("Prénom et email requis");
      return;
    }
    setSaving(true);
    try {
      if (editingUser) {
        await usersApi.updateUser(editingUser.id, {
          first_name: form.first_name,
          last_name: form.last_name,
          email: form.email,
          role: form.role,
        });
        toast.success("Utilisateur mis à jour");
      } else {
        if (!form.password) {
          toast.error("Mot de passe requis pour un nouvel utilisateur");
          return;
        }
        await usersApi.createUser({ ...form });
        toast.success("Utilisateur créé");
      }
      refetch();
      setModalOpen(false);
      setEditingUser(null);
      setForm({ first_name: "", last_name: "", email: "", role: "analyst", password: "" });
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      toast.error(msg ?? "Erreur lors de l'enregistrement");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="page p-4 lg:p-6 space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-bold text-foreground">Gestion des utilisateurs</h1>
          <p className="text-xs text-muted-foreground mt-0.5">{users.length} utilisateurs · {users.filter((u) => u.is_active).length} actifs</p>
        </div>
        <Button onClick={() => { setEditingUser(null); setForm({ first_name: "", last_name: "", email: "", role: "analyst", password: "" }); setModalOpen(true); }} className="gap-2">
          <Plus className="w-4 h-4" />
          Nouvel utilisateur
        </Button>
      </motion.div>

      {/* Search */}
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.1 }}>
        <Input
          placeholder="Rechercher un utilisateur..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          leftIcon={<Search className="w-3.5 h-3.5" />}
          className="max-w-sm"
        />
      </motion.div>

      {/* Users table */}
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.15 }} className="rounded-xl border border-border overflow-hidden" style={{ background: "hsl(var(--card))" }}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-secondary/30">
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Utilisateur</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Email</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Rôle</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Statut</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Créé le</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Dernière connexion</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((user, i) => {
                const role = roleConfig[user.role];
                const RoleIcon = role.icon;
                return (
                  <motion.tr
                    key={user.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.2 + i * 0.04 }}
                    className="border-b border-border hover:bg-secondary/50 transition-colors"
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <Avatar className="h-8 w-8">
                          <AvatarFallback className="text-xs">{getInitials(user.full_name)}</AvatarFallback>
                        </Avatar>
                        <span className="font-medium text-foreground text-sm">{user.full_name}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground text-xs">{user.email}</td>
                    <td className="px-4 py-3">
                      <Badge variant={role.variant} className="text-xs gap-1">
                        <RoleIcon className="w-3 h-3" />
                        {role.label}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      <div className={cn("inline-flex items-center gap-1.5 text-xs px-2 py-0.5 rounded border", user.is_active ? "text-emerald-400 bg-emerald-400/10 border-emerald-400/30" : "text-gray-400 bg-gray-400/10 border-gray-400/30")}>
                        {user.is_active ? <CheckCircle className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                        {user.is_active ? "Actif" : "Inactif"}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{formatDate(user.date_joined, "dd/MM/yyyy")}</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{timeAgo(user.last_login)}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        <Button variant="ghost" size="icon-sm" onClick={() => handleEdit(user)}>
                          <Edit className="w-3.5 h-3.5 text-blue-400" />
                        </Button>
                        <Button variant="ghost" size="icon-sm" onClick={() => setDeleteTarget(user)}>
                          <Trash2 className="w-3.5 h-3.5 text-red-400" />
                        </Button>
                      </div>
                    </td>
                  </motion.tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </motion.div>

      {/* Audit Trail */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }} className="rounded-xl border border-border" style={{ background: "hsl(var(--card))" }}>
        <div className="p-5 pb-3 border-b border-border">
          <h3 className="text-sm font-semibold text-foreground">Audit Trail</h3>
          <p className="text-xs text-muted-foreground mt-0.5">Historique des actions administratives</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border bg-secondary/30">
                <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">Utilisateur</th>
                <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">Action</th>
                <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">Ressource</th>
                <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">IP</th>
                <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">Date</th>
              </tr>
            </thead>
            <tbody>
              {(apiAuditTrail ?? []).map((entry, i) => (
                <motion.tr key={entry.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5 + i * 0.03 }} className="border-b border-border hover:bg-secondary/50">
                  <td className="px-4 py-2.5">
                    <div>
                      <p className="font-medium text-foreground">{entry.user}</p>
                      <p className="text-[10px] text-muted-foreground">{entry.user_email}</p>
                    </div>
                  </td>
                  <td className="px-4 py-2.5">
                    <span className={cn("px-1.5 py-0.5 rounded border text-[10px] font-medium font-mono",
                      entry.action === "LOGIN" ? "text-blue-400 bg-blue-400/10 border-blue-400/30" :
                      entry.action === "RESOLVE" || entry.action === "CREATE" ? "text-emerald-400 bg-emerald-400/10 border-emerald-400/30" :
                      entry.action === "TOGGLE" || entry.action === "UPDATE" ? "text-amber-400 bg-amber-400/10 border-amber-400/30" :
                      "text-muted-foreground bg-secondary border-border"
                    )}>
                      {entry.action}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-muted-foreground">{entry.resource_type} #{entry.resource_id}</td>
                  <td className="px-4 py-2.5 font-mono text-muted-foreground">{entry.ip_address}</td>
                  <td className="px-4 py-2.5 text-muted-foreground whitespace-nowrap">{timeAgo(entry.timestamp)}</td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
      </motion.div>

      {/* User form modal */}
      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="text-lg">
              {editingUser ? "Modifier l'utilisateur" : "Nouvel utilisateur"}
            </DialogTitle>
            <p className="text-sm text-muted-foreground mt-1">
              {editingUser
                ? "Modifiez les informations du compte utilisateur."
                : "Créez un nouveau compte avec accès au dashboard Log+."}
            </p>
          </DialogHeader>

          <div className="space-y-5 px-6 py-5">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>
                  Prénom <span className="text-red-400">*</span>
                </Label>
                <Input
                  value={form.first_name}
                  onChange={(e) => setForm((f) => ({ ...f, first_name: e.target.value }))}
                  placeholder="Jean"
                  autoComplete="given-name"
                />
              </div>
              <div className="space-y-2">
                <Label>Nom</Label>
                <Input
                  value={form.last_name}
                  onChange={(e) => setForm((f) => ({ ...f, last_name: e.target.value }))}
                  placeholder="Dupont"
                  autoComplete="family-name"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label>
                Adresse email <span className="text-red-400">*</span>
              </Label>
              <Input
                type="email"
                value={form.email}
                onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                placeholder="jean.dupont@example.com"
                autoComplete="email"
              />
              <p className="text-xs text-muted-foreground">Sert d&apos;identifiant de connexion pour ce compte.</p>
            </div>

            <div className="space-y-2">
              <Label>Rôle</Label>
              <Select value={form.role} onValueChange={(v) => setForm((f) => ({ ...f, role: v as UserRole }))}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="admin">
                    <div className="flex flex-col gap-0.5">
                      <span>Administrateur</span>
                      <span className="text-xs text-muted-foreground font-normal">Accès complet à toutes les fonctionnalités</span>
                    </div>
                  </SelectItem>
                  <SelectItem value="analyst">
                    <div className="flex flex-col gap-0.5">
                      <span>Analyste</span>
                      <span className="text-xs text-muted-foreground font-normal">Gestion des alertes et des règles</span>
                    </div>
                  </SelectItem>
                  <SelectItem value="viewer">
                    <div className="flex flex-col gap-0.5">
                      <span>Lecteur</span>
                      <span className="text-xs text-muted-foreground font-normal">Consultation uniquement</span>
                    </div>
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>

            {!editingUser && (
              <div className="space-y-2">
                <Label>
                  Mot de passe <span className="text-red-400">*</span>
                </Label>
                <Input
                  type="password"
                  value={form.password}
                  onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                  placeholder="••••••••"
                  autoComplete="new-password"
                />
                <p className="text-xs text-muted-foreground">Minimum 8 caractères recommandé.</p>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setModalOpen(false)}>Annuler</Button>
            <Button onClick={handleSave}>{editingUser ? "Mettre à jour" : "Créer le compte"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Confirmation suppression */}
      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleDelete}
        title="Supprimer l'utilisateur"
        description={`Êtes-vous sûr de vouloir supprimer ${deleteTarget?.full_name ?? "cet utilisateur"} ? Cette action est irréversible.`}
        confirmLabel="Supprimer"
      />
    </div>
  );
}
