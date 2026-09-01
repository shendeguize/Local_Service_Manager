// @ts-check
import starlight from '@astrojs/starlight';
import { defineConfig } from 'astro/config';

// A GitHub Pages project site is served from a subdirectory, so nothing may
// assume it lives at the domain root. Links written inside Markdown stay
// relative for the same reason; see scripts/sync_site_docs.py.
const base = '/Local_Service_Manager';

export default defineConfig({
  site: 'https://shendeguize.github.io',
  base,
  trailingSlash: 'always',
  integrations: [
    starlight({
      title: 'LocalSM',
      // Chinese is the source language, but neither locale is the root: the
      // landing page owns `/` so it can be a custom page rather than a docs
      // index.
      defaultLocale: 'zh',
      locales: {
        zh: { label: '简体中文', lang: 'zh-CN' },
        en: { label: 'English', lang: 'en' },
      },
      social: [
        {
          icon: 'github',
          label: 'GitHub',
          href: 'https://github.com/shendeguize/Local_Service_Manager',
        },
      ],
      // This only switches the feature on. Every page carries its own editUrl,
      // written by scripts/sync_site_docs.py, because the file Starlight reads
      // is a generated copy and the one worth editing is in docs/.
      editLink: {
        baseUrl: 'https://github.com/shendeguize/Local_Service_Manager/edit/main/docs/',
      },
      customCss: ['./src/styles/site.css'],
      components: {
        // The generated pages carry no repository context, so the footer says
        // where they come from and that Chinese is the source.
        Footer: './src/components/DocsFooter.astro',
        // `/` and `/en/` are the landing pages, not docs indexes, so the title
        // must not link at a locale root that serves nothing.
        SiteTitle: './src/components/SiteTitle.astro',
      },
      // Group labels are written in the source language and translated, the same
      // way the pages are.
      sidebar: [
        {
          label: '上手',
          translations: { en: 'Getting started' },
          items: ['install', 'quickstart'],
        },
        {
          label: '日常使用',
          translations: { en: 'Daily use' },
          items: ['configuration', 'services', 'launchd', 'tunnels', 'remote', 'web'],
        },
        {
          label: '参考',
          translations: { en: 'Reference' },
          items: ['cli-reference', 'cli-contract', 'architecture', 'troubleshooting'],
        },
      ],
    }),
  ],
});
