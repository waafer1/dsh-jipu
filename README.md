# dsh-jipu

Jipu (计谱) manuscript crew for DeepSeek Harness — a reader-first, gate-driven pipeline for long-form fiction, packaged as a DSH host plugin.

## What it gives you

A single `jipu` tool with four actions:

| action | does |
|---|---|
| `skill` | read the manuscript manual (`SKILL.md`) and its 12 references, paginated with `offset` / `limit` |
| `scripts` | list the 14 gate scripts |
| `run` | run a gate script inside a project root (requires `project`) |
| `selftest` | run a script's built-in `--selftest` |

The 14 scripts cover: project scaffold, option-card check, capability self-test, recall pack, sentence check, object inventory, dialogue attribution, image/filter check, chapter metrics, number ledger, chapter physical, chapter gate, reader verdict, ledger check.

The skill ships the full manuscript workflow: outline-first chapter construction, eight-beat outline, three hard gates, T0/T1/T2 delivery tiers, three revision loops, plus 12 genre template libraries, 81 beat templates and a trope library.

## Install

```sh
dsh plugin --profile web add dsh-jipu
```

Or add it as a bundle in a profile's `dsh.profile.bundles`.

## Use

```
jipu { action: "scripts" }
jipu { action: "skill", path: "SKILL.md", offset: 1, limit: 80 }
jipu { action: "run", project: "D:/books/my-book", script: "章体检", args: ["3"] }
jipu { action: "selftest", script: "句检" }
```

Gate scripts are copied into a project's `08_工具_脚本/` by the project scaffold; the copies inside this package are for self-test and for opening a new project. Judge a manuscript with the project's own copy, not this one.

## Layout

```
index.js            host plugin, registers the jipu tool
cordis.patch.yml    loader patch
skill/              SKILL.md, references/, assets/, tools/, agents/
locale/             en + zh display metadata
icon.svg
```

## License

MIT
