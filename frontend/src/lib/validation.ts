export function validatePasswordChange(
  current: string,
  next: string,
  confirm: string
): string | null {
  if (!current || !next) return "Remplissez tous les champs";
  if (next !== confirm) return "Les mots de passe ne correspondent pas";
  if (next.length < 8) return "Min. 8 caractères";
  return null;
}
