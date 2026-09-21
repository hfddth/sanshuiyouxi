import { cp, mkdir, readdir, rm } from 'node:fs/promises';

const output = new URL('../dist/', import.meta.url);
await rm(output, { recursive: true, force: true });
await mkdir(new URL('./ui-preview/', output), { recursive: true });

for (const file of ['index.html', 'styles.css', 'app.js', 'agent-config.js', 'sample-script.json']) {
  await cp(new URL(`../${file}`, import.meta.url), new URL(file, output));
}
await cp(
  new URL('../ui-preview/ink-landscape.png', import.meta.url),
  new URL('./ui-preview/ink-landscape.png', output),
);

// EdgeOne packages each Agent route independently. Mirror the reusable Python
// core beside the route so the cloud runtime receives the modules and RAG data.
const agentSource = new URL('../agent/', import.meta.url);
const agentCore = new URL('../agents/chat/core/', import.meta.url);
await rm(agentCore, { recursive: true, force: true });
await mkdir(agentCore, { recursive: true });
for (const entry of await readdir(agentSource, { withFileTypes: true })) {
  if (entry.isFile() && entry.name.endsWith('.py')) {
    await cp(new URL(entry.name, agentSource), new URL(entry.name, agentCore));
  }
}
await cp(new URL('./data/nanxijiang/', agentSource), new URL('./data/nanxijiang/', agentCore), { recursive: true });
