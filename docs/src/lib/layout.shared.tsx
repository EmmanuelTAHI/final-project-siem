import type { BaseLayoutProps } from 'fumadocs-ui/layouts/shared';
import { appName, gitConfig } from './shared';

export function baseOptions(): BaseLayoutProps {
  return {
    nav: {
      title: (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontWeight: 700 }}>
          <span className="docs-brand-mark" aria-hidden>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path
                d="M12 2L3 6v6c0 5 3.8 8.4 9 10 5.2-1.6 9-5 9-10V6l-9-4z"
                fill="currentColor"
              />
            </svg>
          </span>
          {appName}
        </span>
      ),
    },
    githubUrl: `https://github.com/${gitConfig.user}/${gitConfig.repo}`,
  };
}
