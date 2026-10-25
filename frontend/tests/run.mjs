// Discover every TypeScript test and run them in this process with node:test.
import { build } from 'esbuild';
import { mkdtemp, readdir, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const directory = await mkdtemp(join(tmpdir(), 'fair-editor-tests-'));
try {
  const tests = (await readdir('tests', { recursive: true }))
    .filter((name) => name.endsWith('.test.ts'))
    .sort();
  if (!tests.length) throw new Error('No TypeScript tests found.');
  const outfile = join(directory, 'tests.cjs');
  await build({
    stdin: {
      contents: tests.map((name) => `import ${JSON.stringify(resolve('tests', name))};`).join('\n'),
      resolveDir: process.cwd(),
    },
    outfile,
    bundle: true,
    platform: 'node',
    format: 'cjs',
    logLevel: 'warning',
  });
  // node:test registers the tests on import and sets the process exit code on failure.
  await import(pathToFileURL(outfile).href);
} finally {
  await rm(directory, { recursive: true, force: true });
}
