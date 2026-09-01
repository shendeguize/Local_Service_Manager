import { docsLoader } from '@astrojs/starlight/loaders';
import { docsSchema } from '@astrojs/starlight/schema';
import { defineCollection } from 'astro:content';

// The pages under src/content/docs are generated from the repository's docs/
// tree by scripts/sync_site_docs.py, so they are not committed.
export const collections = {
  docs: defineCollection({ loader: docsLoader(), schema: docsSchema() }),
};
