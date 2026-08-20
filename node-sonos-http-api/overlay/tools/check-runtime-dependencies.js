'use strict';

const fs = require('fs');
const path = require('path');
const { builtinModules } = require('module');

const root = process.cwd();
const builtins = new Set(
  builtinModules.flatMap((name) => [name, name.replace(/^node:/, '')])
);
const ignoredDirectories = new Set(['.git', 'node_modules']);
const failures = [];

function sourceFiles(entryPath) {
  const stats = fs.statSync(entryPath);
  if (stats.isFile()) {
    return entryPath.endsWith('.js') ? [entryPath] : [];
  }

  return fs.readdirSync(entryPath, { withFileTypes: true }).flatMap((entry) => {
    if (ignoredDirectories.has(entry.name)) {
      return [];
    }

    const childPath = path.join(entryPath, entry.name);
    if (entry.isDirectory()) {
      return sourceFiles(childPath);
    }
    return entry.isFile() && entry.name.endsWith('.js') ? [childPath] : [];
  });
}

const runtimeRoots = ['server.js', 'settings.js', 'lib']
  .map((entry) => path.join(root, entry))
  .filter((entry) => fs.existsSync(entry));

for (const filename of runtimeRoots.flatMap(sourceFiles)) {
  const source = fs.readFileSync(filename, 'utf8');
  const requirePattern = /\brequire\(\s*(['"])([^'"]+)\1\s*\)/g;
  let match;

  while ((match = requirePattern.exec(source)) !== null) {
    const specifier = match[2];
    if (builtins.has(specifier) || specifier.startsWith('node:')) {
      continue;
    }

    try {
      if (specifier.startsWith('.')) {
        require.resolve(path.resolve(path.dirname(filename), specifier));
      } else {
        require.resolve(specifier, { paths: [path.dirname(filename)] });
      }
    } catch {
      failures.push(`${path.relative(root, filename)}: ${specifier}`);
    }
  }
}

if (failures.length > 0) {
  console.error('Unresolved runtime imports:');
  failures.sort().forEach((failure) => console.error(`  ${failure}`));
  process.exit(1);
}

console.log('Runtime dependency imports resolved.');
