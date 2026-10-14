// Bundle TypeScript tests using Vite's installed compiler; run with Node's test runner.
import { build } from 'esbuild';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
const directory=await mkdtemp(join(tmpdir(),'fair-editor-tests-'));
try {
  const outfile=join(directory,'editor.test.cjs');
  await build({entryPoints:['tests/editor.test.ts'],outfile,bundle:true,platform:'node',format:'cjs',logLevel:'warning'});
  const result=spawnSync(process.execPath,[outfile],{stdio:'inherit'});
  process.exitCode=result.status??1;
} finally {await rm(directory,{recursive:true,force:true});}
