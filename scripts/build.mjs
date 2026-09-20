import { cp, mkdir, rm } from 'node:fs/promises';

const output = new URL('../dist/', import.meta.url);
await rm(output, { recursive: true, force: true });
await mkdir(new URL('./ui-preview/', output), { recursive: true });

for (const file of ['index.html', 'styles.css', 'app.js', 'sample-script.json']) {
  await cp(new URL(`../${file}`, import.meta.url), new URL(file, output));
}
await cp(
  new URL('../ui-preview/ink-landscape.png', import.meta.url),
  new URL('./ui-preview/ink-landscape.png', output),
);
