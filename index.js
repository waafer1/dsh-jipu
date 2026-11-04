/**
 * dsh-jipu — 计谱（Jipu）的 DSH 宿主插件。
 *
 * 一个 `jipu` 工具：
 *   - skill    读 skill/ 下的手册与 references（分段读）
 *   - scripts  列出 14 个门禁脚本
 *   - run      在项目根目录跑指定脚本
 *   - selftest 跑脚本自检
 */
import { spawn } from 'node:child_process';
import { closeSync, mkdirSync, openSync, readFileSync, unlinkSync } from 'node:fs';
import { readFile, readdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const name = 'jipu';
export const inject = ['tools'];

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SKILL_DIR = path.join(HERE, 'skill');
const TOOLS_DIR = path.join(SKILL_DIR, 'tools');
const RUNTIME_DIR = path.join(HERE, '.runtime');
const MAX_CHARS = 20000;

function clip(s) {
  if (typeof s !== 'string') return '';
  return s.length > MAX_CHARS ? s.slice(0, MAX_CHARS) + `\n…（截断，共 ${s.length} 字符）` : s;
}

function runPython(script, args, cwd) {
  return new Promise((resolve) => {
    mkdirSync(RUNTIME_DIR, { recursive: true });
    const logPath = path.join(RUNTIME_DIR, `run-${Date.now()}-${Math.random().toString(36).slice(2)}.log`);
    const fd = openSync(logPath, 'w');
    const child = spawn('python', [path.join(TOOLS_DIR, script), ...args], {
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
      resolve({
        exit: code,
        stdout: clip(output),
        stderr: error ? clip(String(error)) : '',
      });
    };
    const timer = setTimeout(() => {
      child.kill();
      finish(-1, 'timeout: 180s');
    }, 180000);
    child.on('error', (e) => finish(-1, e));
    child.on('close', (code) => finish(code));
  });
}

async function listScripts() {
  const names = (await readdir(TOOLS_DIR)).filter((n) => n.endsWith('.py')).sort();
  return names.map((n) => n.replace(/\.py$/, ''));
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

export function apply(ctx) {
  ctx.tools.register({
    name: 'jipu',
    description:
      '计谱（Jipu）长篇写作工序：读手册、列出并运行 14 个门禁脚本（句检/句病检/对白归属/画面检/章指标/数字体检/章体检/章检/读者判定/召回/账本体检/开项目/选型体检/能力自测）。' +
      'action=skill 读 skill/ 下的 SKILL.md 或 references（用 offset/limit 分段读）；' +
      'action=scripts 列出脚本名；action=run 在项目根目录跑脚本（必须给 project）；action=selftest 跑某脚本 --selftest。' +
      '判稿一律以项目内 08_工具_脚本/ 的那份脚本为准，本包脚本只用于自检与开新书复制。',
    parameters: {
      type: 'object',
      additionalProperties: false,
      required: ['action'],
      properties: {
        action: { type: 'string', enum: ['skill', 'scripts', 'run', 'selftest'], description: '要做的动作。' },
        path: { type: 'string', description: 'action=skill 时的相对路径，默认 SKILL.md；如 references/03-门禁手册.md。' },
        offset: { type: 'integer', description: 'action=skill 时的起始行（1 起）。' },
        limit: { type: 'integer', description: 'action=skill 时最多读多少行。' },
        script: { type: 'string', description: 'action=run/selftest 时的脚本名，如 章体检 或 章体检.py。' },
        args: { type: 'array', items: { type: 'string' }, description: '传给脚本的参数。' },
        project: { type: 'string', description: '项目根目录（含 项目配置.json 与 00_—08_ 九层）。action=run 必填。' },
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

      if (action === 'scripts') {
        const list = await listScripts();
        return {
          text: `计谱门禁脚本（${list.length} 个）：\n- ` + list.join('\n- ') +
            '\n\n用法：action=run，project=<项目根>，script=<脚本名>，args=[章号或文件路径]。',
          files: list,
        };
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
        return { ...r, text: `[selftest] ${script}\nexit=${r.exit}\n\n${r.stdout}${r.stderr}` };
      }

      if (action === 'run') {
        const project = args.project || process.env.JIPU_ROOT;
        if (!project) throw new Error('action=run 需要 project（项目根目录），或设置环境变量 JIPU_ROOT');
        const r = await runPython(script + '.py', (args.args || []).map(String), project);
        return { ...r, text: `[run] ${script} @ ${project}\nexit=${r.exit}\n\n${r.stdout}${r.stderr}` };
      }

      throw new Error(`unknown action: ${action}`);
    },
    presentCall(args) {
      return { card: 'generic', title: `jipu ${args.action}`, kind: 'other', rawInput: args };
    },
  });
}
