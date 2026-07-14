import { createMDX } from 'fumadocs-mdx/next';

const withMDX = createMDX();

/** @type {import('next').NextConfig} */
const config = {
  reactStrictMode: true,
  output: 'standalone',
  // Servi sous /docs/ sur le domaine principal (nginx location /docs/ →
  // ce conteneur) — pas de sous-domaine dédié nécessaire (DuckDNS ne
  // permet pas d'ajouter un sous-domaine par API sans passer par le compte
  // web ; basePath évite cette dépendance).
  basePath: '/docs',
};

export default withMDX(config);
