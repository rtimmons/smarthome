const fs = require('node:fs');
const path = require('node:path');
const {spawnSync} = require('node:child_process');

const root = path.resolve(__dirname, '..');
const sourceRoot = path.join(root, 'src');

function discoverSpecs(directory) {
  return fs.readdirSync(directory, {withFileTypes: true})
    .flatMap(entry => {
      const fullPath = path.join(directory, entry.name);
      if (entry.isDirectory()) return discoverSpecs(fullPath);
      return entry.isFile() && entry.name.endsWith('.spec.ts') ? [fullPath] : [];
    });
}

const specs = discoverSpecs(sourceRoot).sort();
if (specs.length === 0) {
  console.error('No TypeScript spec files found under src/.');
  process.exit(1);
}

const tsxBin = path.join(root, 'node_modules', '.bin', process.platform === 'win32' ? 'tsx.cmd' : 'tsx');
if (!fs.existsSync(tsxBin)) {
  console.error(`Missing test runner at ${tsxBin}; run the repository setup first.`);
  process.exit(1);
}

for (const spec of specs) {
  const relative = path.relative(root, spec);
  console.log(`==> ${relative}`);
  const result = spawnSync(tsxBin, [relative], {
    cwd: root,
    env: process.env,
    stdio: 'inherit',
  });
  if (result.error) {
    console.error(result.error.message);
    process.exit(1);
  }
  if (result.status !== 0) process.exit(result.status ?? 1);
}
