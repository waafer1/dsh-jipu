/**
 * dsh-jipu — 计谱（Jipu）的 DSH 宿主插件。
 *
 * 一个 `jipu` 工具：
 *   - skill    读 skill/ 下的手册与 references（分段读）
 *   - scripts  列出 15 个门禁脚本
 *   - roles    列出七个角色设定；给 role 则返回该角色全文（可当 subagent prompt）
 *   - run      在项目根目录跑指定脚本（project 可省略，自动向上找 项目配置.json）
 *   - selftest 跑脚本自检
 *   - status   读项目配置与追踪状态，报当前阶段、下一章、开口的线
 */
import { spawn } from 'node:child_process';
import { closeSync, mkdirSync, openSync, readFileSync, unlinkSync } from 'node:fs';
import { readFile, readdir, stat } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const name = 'jipu';
export const inject = ['tools'];

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SKILL_DIR = path.join(HERE, 'skill');
const TOOLS_DIR = path.join(SKILL_DIR, 'tools');
const AGENTS_DIR = path.join(SKILL_DIR, 'agents');
const RUNTIME_DIR = path.join(HERE, '.runtime');
const MAX_CHARS = 20000;

function clip(s) {
  if (typeof s !== 'string') return '';
  return s.length > MAX_CHARS ? s.slice(0, MAX_CHARS) + `\n…（截断，共 ${s.length} 字符）` : s;
}

function pythonCandidates() {
  if (process.env.JIPU_PYTHON) return [process.env.JIPU_PYTHON];
  // Windows 常见 python；macOS/Linux 通常只有 python3。
  return process.platform === 'win32' ? ['python', 'python3'] : ['python3', 'python'];
}

function runPythonOnce(cmd, script, args, cwd) {
  return new Promise((resolve) => {
    mkdirSync(RUNTIME_DIR, { recursive: true });
    const logPath = path.join(RUNTIME_DIR, `run-${Date.now()}-${Math.random().toString(36).slice(2)}.log`);
    const fd = openSync(logPath, 'w');
    const child = spawn(cmd, [path.join(TOOLS_DIR, script), ...args], {
      cwd,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
      windowsHide: true,
      stdio: ['ignore', fd, fd],
    });
    let done = false;
    const finish = (code, error) => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      try { closeSync(fd); } catch { /* already closed */ }
      let output = '';
      try { output = readFileSync(logPath, 'utf8'); } catch { /* missing */ }
      try { unlinkSync(logPath); } catch { /* locked */ }
      resolve({ exit: code, stdout: clip(output), stderr: error ? clip(String(error)) : '', spawnFailed: !!error });
    };
    const timer = setTimeout(() => {
      child.kill();
      finish(-1, 'timeout: 180s');
    }, 180000);
    child.on('error', (e) => finish(-1, e));
    child.on('close', (code) => finish(code));
  });
}

async function runPython(script, args, cwd) {
  let last;
  for (const cmd of pythonCandidates()) {
    const r = await runPythonOnce(cmd, script, args, cwd);
    if (!r.spawnFailed) return { ...r, python: cmd };
    last = r;
    if (r.spawnFailed && !/ENOENT/.test(r.stderr)) break;
  }
  return { ...(last || { exit: -1, stdout: '', stderr: 'no python found' }), python: null };
}

async function listScripts() {
  const names = (await readdir(TOOLS_DIR)).filter((n) => n.endsWith('.py')).sort();
  return names.map((n) => n.replace(/\.py$/, ''));
}

async function listRoles() {
  let names = [];
  try {
    names = (await readdir(AGENTS_DIR)).filter((n) => n.endsWith('.md')).sort();
  } catch {
    return [];
  }
  return names.map((n) => n.replace(/\.md$/, ''));
}

async function readSkill(relPath, offset, limit) {
  const base = path.resolve(SKILL_DIR);
  const target = path.resolve(SKILL_DIR, relPath || 'SKILL.md');
  if (target !== base && !target.startsWith(base + path.sep)) {
    throw new Error('path escapes skill directory');
  }
  const text = await readFile(target, 'utf8');
  const lines = text.split('\n');
  const start = Math.max(0, (offset || 1) - 1);
  const end = limit ? start + limit : lines.length;
  return {
    text: lines.slice(start, end).join('\n'),
    totalLines: lines.length,
    from: start + 1,
    to: Math.min(end, lines.length),
  };
}

async function climbForProject(from) {
  let dir = path.resolve(from || process.cwd());
  for (let i = 0; i < 8; i++) {
    try {
      await stat(path.join(dir, '项目配置.json'));
      return dir;
    } catch {
      const parent = path.dirname(dir);
      if (parent === dir) break;
      dir = parent;
    }
  }
  return null;
}

function readJsonSafe(p) {
  try { return JSON.parse(readFileSync(p, 'utf8')); } catch { return null; }
}

async function projectStatus(args) {
  const project = args.project || process.env.JIPU_ROOT || (await climbForProject(process.cwd()));
  if (!project) {
    return { text: '找不到项目根：请在参数里给 project，或把 项目配置.json 放在当前目录/上层。' };
  }
  const cfg = readJsonSafe(path.join(project, '项目配置.json'));
  const state = readJsonSafe(path.join(project, '06_追踪_状态账本', '_tracking-state.json'));
  const lines = [];
  lines.push(`项目：${cfg ? (cfg.title || '(未命名)') : '（缺 项目配置.json）'}`);
  lines.push(`路径：${project}`);

  let chapters = [];
  try {
    chapters = (await readdir(path.join(project, '04_正文_成品')))
      .filter((n) => /^第\d+章_.*\.md$/.test(n));
  } catch { /* no dir */ }
  lines.push(`正文：${chapters.length} 章`);

  if (state) {
    lines.push(`状态：rev ${state.state_revision}，已提交到第 ${state.last_committed_chapter} 章`);
    const chars = state.characters || {};
    const hero = Object.entries(chars).find(([, v]) => String((v && v.role) || '').includes('主角'))?.[1]
      || Object.values(chars)[0];
    if (hero && hero.cash_copper != null) {
      const c = hero.cash_copper;
      lines.push(`现金：${Math.floor(c / 100)} 银 ${c % 100} 铜（${c} 铜）`);
    }
    const openThreads = (state.threads || []).filter((t) => t.status === 'open');
    if (openThreads.length) {
      lines.push(`开口的线：${openThreads.length}`);
      for (const t of openThreads) lines.push(`  - ${t.id} ${t.name}（${t.due || '无到期'}）`);
    }
    const next = (state.last_committed_chapter || 0) + 1;
    lines.push(`下一章：第 ${String(next).padStart(3, '0')} 章`);
    lines.push('开下一章前：先 `jipu run 章检 ' + String(next - 1).padStart(3, '0') + '`，三项 PASS 才算上一章落地。');
  } else {
    lines.push('状态：缺 _tracking-state.json（还没有提交过，或路径不对）');
  }
  return { text: lines.join('\n') };
}

async function rolePrompt(role) {
  const roles = await listRoles();
  if (!role) {
    return { text: `计谱角色（${roles.length}）：\n- ` + roles.join('\n- ') + '\n\n用法：action=roles，role=<名字>，返回该角色设定全文。' };
  }
  const key = String(role).replace(/\.md$/, '');
  const hit = roles.find((r) => r === key || r === `jipu-${key}` || r.endsWith(key));
  if (!hit) throw new Error(`unknown role: ${role}；可选：${roles.join(', ')}`);
  const text = await readFile(path.join(AGENTS_DIR, hit + '.md'), 'utf8');
  return { text: `# ${hit}\n\n${clip(text)}` };
}

export function apply(ctx) {
  ctx.tools.register({
    name: 'jipu',
    description:
      '计谱（Jipu）长篇写作工序：读手册、看七个角色、查项目阶段、跑 15 个门禁脚本（句检/句病检/对白归属/画面检/章指标/数字体检/章体检/章检/读者判定/召回/账本体检/种子台账/开项目/选型体检/能力自测）。' +
      'action=skill 读 SKILL.md 或 references（offset/limit 分段）；action=scripts 列脚本；action=roles 列七个角色，给 role 返回设定全文（可作 subagent prompt）；' +
      'action=status 报当前阶段与下一章；action=seeds 按类目/主线列种子、查重或记账；action=run 在项目根跑脚本（project 可省略，自动向上找 项目配置.json）；action=selftest 跑脚本自检。' +
      '判稿以项目内 08_工具_脚本/ 的脚本为准，本包脚本只用于自检与开新书复制。',
    parameters: {
      type: 'object',
      additionalProperties: false,
      required: ['action'],
      properties: {
        action: { type: 'string', enum: ['skill', 'scripts', 'roles', 'seeds', 'run', 'selftest', 'status'], description: '要做的动作。' },
        path: { type: 'string', description: 'action=skill 时的相对路径，默认 SKILL.md；如 references/03-门禁手册.md。' },
        offset: { type: 'integer', description: 'action=skill 时的起始行（1 起）。' },
        limit: { type: 'integer', description: 'action=skill 时最多读多少行。' },
        role: { type: 'string', description: 'action=roles 时的角色名，如 writer 或 jipu-writer。' },
        script: { type: 'string', description: 'action=run/selftest 时的脚本名，如 章体检 或 章体检.py。' },
        args: { type: 'array', items: { type: 'string' }, description: '传给脚本的参数。' },
        project: { type: 'string', description: '项目根目录；省略时自动向上找 项目配置.json，再退到当前目录。' },
        genre: { type: 'string', description: 'action=seeds 时的类目编号，01—12。' },
        role: { type: 'string', enum: ['主线', '副线', '两用'], description: 'action=seeds 时按用途筛。' },
        seed: { type: 'string', description: 'action=seeds 时的种子钩子；给了就查重，配合 use=true 则记账。' },
        chapter: { type: 'string', description: 'action=seeds 记账时的章号，如 012。' },
        use: { type: 'boolean', description: 'action=seeds 且给了 seed 时，true 表示记进桥段账本。' },
      },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: true,
        properties: {
          text: { type: 'string' },
          exit: { type: 'integer' },
          stdout: { type: 'string' },
          stderr: { type: 'string' },
          files: { type: 'array', items: { type: 'string' } },
        },
      },
      render(_args, value) {
        return [{ type: 'text', text: value.text || value.stdout || '(no output)' }];
      },
    },
    async execute(args) {
      const action = args.action;

      if (action === 'seeds') {
        const cli = [];
        if (args.genre) cli.push('--genre', String(args.genre));
        if (args.role) cli.push('--role', String(args.role));
        if (args.seed && args.use) {
          cli.push('--seed', String(args.seed), '--chapter', String(args.chapter || '-'));
        } else if (args.seed) {
          cli.push('--check', String(args.seed));
        } else {
          cli.push('--list');
        }
        const project = args.project || process.env.JIPU_ROOT || (await climbForProject(process.cwd())) || process.cwd();
        const r = await runPython('种子台账.py', cli, project);
        return { ...r, text: `[seeds] ${cli.join(' ')}\nexit=${r.exit}\n\n${r.stdout}${r.stderr}` };
      }

      if (action === 'scripts') {
        const list = await listScripts();
        return {
          text: `计谱门禁脚本（${list.length} 个）：\n- ` + list.join('\n- ') +
            '\n\n用法：action=run，script=<脚本名>，args=[章号或文件路径]；project 可省略。',
          files: list,
        };
      }

      if (action === 'roles') {
        return rolePrompt(args.role);
      }

      if (action === 'status') {
        return projectStatus(args);
      }

      if (action === 'skill') {
        const r = await readSkill(args.path, args.offset, args.limit);
        return {
          text: `${args.path || 'SKILL.md'}（第 ${r.from}–${r.to} 行，共 ${r.totalLines} 行）\n\n${r.text}`,
        };
      }

      const script = String(args.script || '').replace(/\.py$/, '');
      const list = await listScripts();
      if (!list.includes(script)) {
        throw new Error(`unknown script: ${args.script}；可选：${list.join(', ')}`);
      }

      if (action === 'selftest') {
        const r = await runPython(script + '.py', ['--selftest'], TOOLS_DIR);
        return { ...r, text: `[selftest] ${script}（${r.python || 'no python'}）\nexit=${r.exit}\n\n${r.stdout}${r.stderr}` };
      }

      if (action === 'run') {
        const project = args.project || process.env.JIPU_ROOT || (await climbForProject(process.cwd())) || process.cwd();
        const r = await runPython(script + '.py', (args.args || []).map(String), project);
        return { ...r, text: `[run] ${script} @ ${project}（${r.python || 'no python'}）\nexit=${r.exit}\n\n${r.stdout}${r.stderr}` };
      }

      throw new Error(`unknown action: ${action}`);
    },
    presentCall(args) {
      return { card: 'generic', title: `jipu ${args.action}`, kind: 'other', rawInput: args };
    },
  });
}
