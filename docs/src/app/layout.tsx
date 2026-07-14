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
        <RootProvider>{children}</RootProvider>
      </body>
    </html>
  );
}
