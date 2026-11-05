import { spawnSync } from 'node:child_process';
import { readdirSync } from 'node:fs';
import path from 'node:path';
import process from 'node:process';

const tools = path.join(process.cwd(), 'skill', 'tools');
const names = readdirSync(tools).filter((n) => n.endsWith('.py')).sort();
const candidates = process.env.JIPU_PYTHON
  ? [process.env.JIPU_PYTHON]
  : process.platform === 'win32' ? ['python', 'python3'] : ['python3', 'python'];

let python = null;
for (const c of candidates) {
  const probe = spawnSync(c, ['--version'], { encoding: 'utf8' });
  if (probe.status === 0) { python = c; break; }
}
if (!python) {
  console.error('no python interpreter found');
  process.exit(1);
}
console.log(`python: ${python} (${process.platform})`);

let failed = 0;
for (const n of names) {
  const r = spawnSync(python, [path.join(tools, n), '--selftest'], { encoding: 'utf8', timeout: 120000 });
  const ok = r.status === 0;
  if (!ok) failed++;
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${n}`);
  if (!ok) {
    console.log((r.stdout || '').slice(-800));
    console.log((r.stderr || '').slice(-800));
  }
}
console.log(`\n${names.length - failed}/${names.length} passed`);
process.exit(failed === 0 ? 0 : 1);
