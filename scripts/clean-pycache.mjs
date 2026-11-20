#!/usr/bin/env node
// prepack 前置：清掉 skill/ 下的 __pycache__。
// 起因：package.json 的 files: ["skill/**"] 会把 Python 运行时留下的
// __pycache__/*.pyc 一起打进 tgz，而 .gitignore 对 npm 打包不生效。
// 2026-11-20 首次打 1.33.0 包时混进 4 个 .pyc（146 条目），手清后 136。
import { readdir, rm, stat } from 'node:fs/promises'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = dirname(dirname(fileURLToPath(import.meta.url)))
const target = join(root, 'skill')

async function walk(dir, hits) {
  let entries
  try {
    entries = await readdir(dir, { withFileTypes: true })
  } catch {
    return hits
  }
  for (const e of entries) {
    if (!e.isDirectory()) continue
    const p = join(dir, e.name)
    if (e.name === '__pycache__') {
      hits.push(p)
      continue
    }
    await walk(p, hits)
  }
  return hits
}

const hits = await walk(target, [])
for (const p of hits) await rm(p, { recursive: true, force: true })
console.log(`[prepack] cleaned ${hits.length} __pycache__ dir(s) under skill/`)
