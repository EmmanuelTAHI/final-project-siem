import type { Metadata } from 'next';
import { RootProvider } from 'fumadocs-ui/provider/next';
import './global.css';
import { Inter } from 'next/font/google';

const inter = Inter({
  subsets: ['latin'],
});

export const metadata: Metadata = {
  title: {
    default: 'Log+ Docs',
    template: '%s — Log+ Docs',
  },
  description:
    "Documentation officielle de Log+, SIEM open source self-service : création d'organisation, déploiement d'agents, isolation multi-tenant, sécurité.",
};

export default function Layout({ children }: LayoutProps<'/'>) {
  return (
    <html lang="fr" className={inter.className} suppressHydrationWarning>
      <body className="flex flex-col min-h-screen">
        {/*
          Fix recherche : le client fumadocs-core calcule l'URL de l'API via
          import.meta.env.BASE_URL (convention Vite) — toujours vide sous
          Next.js, donc il appelait "/api/search" à la racine du domaine, que
          nginx route vers le frontend SIEM (pas ce conteneur). Cette app est
          montée avec basePath "/docs" (next.config.mjs) : sa vraie route est
          "/docs/api/search". On force l'URL exacte ici.
        */}
        <RootProvider search={{ options: { api: '/docs/api/search' } }}>{children}</RootProvider>
      </body>
    </html>
  );
}
