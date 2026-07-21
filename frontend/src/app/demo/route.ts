import { NextResponse } from "next/server";

// Redirection courte vers le lien magique de démonstration (compte
// spectateur lecture-seule, voir DemoAccessView / demo_readonly_middleware
// côté backend). Le token du lien a un TTL de ~10 ans, pas de renouvellement
// nécessaire avant la soutenance.
const DEMO_ACCESS_URL =
  "https://argussiem.com/api/auth/demo-access/eyJkZW1vX3VzZXJfaWQiOiI5NTI1N2VjYS04YzI5LTRiMWEtYTZkMy1iODYwZGNiNTVlMGYiLCJ0dGwiOjMxNTM2MDAwMH0:1wm6GT:Ol3yZ9g3vyfq_0cHkZFqqL3MLeZSFjTNsocPQ0HxLCA/";

export function GET() {
  return NextResponse.redirect(DEMO_ACCESS_URL, 302);
}
