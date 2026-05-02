import { copyFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const vendorScriptDir = resolve(projectRoot, 'app/static/js/vendor');
const vendorStyleDir = resolve(projectRoot, 'app/static/css/vendor');

mkdirSync(vendorScriptDir, { recursive: true });
mkdirSync(vendorStyleDir, { recursive: true });

const scriptFiles = [
  ['node_modules/alpinejs/dist/cdn.min.js', 'alpine.min.js'],
  ['node_modules/@alpinejs/focus/dist/cdn.min.js', 'alpine-focus.min.js'],
  ['node_modules/htmx.org/dist/htmx.min.js', 'htmx.min.js'],
  ['node_modules/htmx-ext-response-targets/dist/response-targets.min.js', 'htmx-ext-response-targets.min.js'],
  ['node_modules/sweetalert2/dist/sweetalert2.all.min.js', 'sweetalert2.all.min.js'],
  ['node_modules/dropzone/dist/min/dropzone.min.js', 'dropzone.min.js'],
  ['node_modules/izitoast/dist/js/iziToast.min.js', 'iziToast.min.js'],
];

const styleFiles = [
  ['node_modules/izitoast/dist/css/iziToast.min.css', 'iziToast.min.css'],
];

for (const [sourcePath, targetName] of scriptFiles) {
  copyFileSync(resolve(projectRoot, sourcePath), resolve(vendorScriptDir, targetName));
}
console.log(`Synced ${scriptFiles.length} vendor scripts to ${vendorScriptDir}`);

for (const [sourcePath, targetName] of styleFiles) {
  copyFileSync(resolve(projectRoot, sourcePath), resolve(vendorStyleDir, targetName));
}
console.log(`Synced ${styleFiles.length} vendor styles to ${vendorStyleDir}`);
