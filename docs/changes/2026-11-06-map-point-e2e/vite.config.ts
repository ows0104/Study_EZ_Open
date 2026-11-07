import original from '../../../web/vite.config';
import { fileURLToPath } from 'node:url';

export default (env: Parameters<typeof original>[0]) => ({
  ...original(env),
  root: fileURLToPath(new URL('../../../web', import.meta.url)),
  cacheDir: fileURLToPath(new URL('../../../../../runs/_e2e/26110507/local-app/vite-cache', import.meta.url)),
});
