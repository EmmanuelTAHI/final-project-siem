import type { ReactNode } from 'react';

interface TerminalProps {
  /** Affiché dans la barre de titre (ex: "bash", "PowerShell", nom de fichier). */
  title?: string;
  children: ReactNode;
}

/**
 * Fenêtre façon macOS (barre de titre + 3 points) enveloppant un bloc de
 * code — utilisé en MDX pour mettre en valeur les commandes clés (install,
 * quickstart...). Le contenu doit être un bloc de code Markdown standard
 * (```lang ... ```), pas un composant personnalisé, pour garder la
 * coloration syntaxique et le bouton copier de fumadocs-ui.
 */
export function Terminal({ title, children }: TerminalProps) {
  return (
    <div className="docs-terminal not-prose">
      <div className="docs-terminal-bar">
        <span className="docs-terminal-dot docs-terminal-dot--red" />
        <span className="docs-terminal-dot docs-terminal-dot--yellow" />
        <span className="docs-terminal-dot docs-terminal-dot--green" />
        {title && <span className="docs-terminal-title">{title}</span>}
      </div>
      {children}
    </div>
  );
}
