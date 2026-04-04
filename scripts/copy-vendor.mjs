import { copyFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const vendorDir = resolve(projectRoot, 'app/static/js/vendor');

mkdirSync(vendorDir, { recursive: true });

const files = [
  ['node_modules/alpinejs/dist/cdn.min.js', 'alpine.min.js'],
  ['node_modules/@alpinejs/focus/dist/cdn.min.js', 'alpine-focus.min.js'],
  ['node_modules/htmx.org/dist/htmx.min.js', 'htmx.min.js'],
  ['node_modules/htmx-ext-response-targets/dist/response-targets.min.js', 'htmx-ext-response-targets.js'],
];

for (const [sourcePath, targetName] of files) {
  copyFileSync(resolve(projectRoot, sourcePath), resolve(vendorDir, targetName));
}

console.log(`Synced ${files.length} vendor files to ${vendorDir}`);
