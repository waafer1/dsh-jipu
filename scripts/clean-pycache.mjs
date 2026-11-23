#!/usr/bin/env node
// prepack 前置：清掉 skill/ 下的 __pycache__，并保证 package.json 不带 BOM。
// 起因一：package.json 的 files: ["skill/**"] 会把 Python 运行时留下的
// __pycache__/*.pyc 一起打进 tgz，而 .gitignore 对 npm 打包不生效。
// 2026-11-20 首次打 1.33.0 包时混进 4 个 .pyc（146 条目），手清后 136。
// 起因二：Windows 上 Set-Content -Encoding UTF8 会写 BOM，打出来的包里
// package.json 带 U+FEFF，DSH 装包时报 "Unexpected token '﻿'" 直接拒绝安装。
// 2026-11-23 打 1.34.0 时踩到，这里一并兜住：有 BOM 就剥掉。
import { readdir, readFile, rm, writeFile } from 'node:fs/promises'
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

// package.json 去 BOM（Windows 下 Set-Content 会加，npm 打包会原样带进去）
const pkg = join(root, 'package.json')
const buf = await readFile(pkg)
if (buf[0] === 0xef && buf[1] === 0xbb && buf[2] === 0xbf) {
  await writeFile(pkg, buf.subarray(3))
  console.log('[prepack] stripped UTF-8 BOM from package.json')
}
try {
  JSON.parse(await readFile(pkg, 'utf8'))
} catch (err) {
  console.error(`[prepack] package.json 不是合法 JSON：${err.message}`)
  process.exit(1)
}

