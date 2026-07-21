export const appName = 'Argus Docs';
// Contenu servi à la racine de cette app (elle-même montée sous /docs/ sur
// le domaine principal via basePath — voir next.config.mjs et nginx.conf).
export const docsRoute = '';
export const docsImageRoute = '/og/docs';
export const docsContentRoute = '/llms.mdx/docs';

export const gitConfig = {
  user: 'argus',
  repo: 'argus',
  branch: 'main',
};
