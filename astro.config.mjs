import { defineConfig } from 'astro/config';

export default defineConfig({
  site: 'https://ayewo.github.io',
  base: '/nativelink-rbe-benchmarks',
  output: 'static',
  build: {
    assets: '_astro'
  }
});
