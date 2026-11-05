# Changelog

## 1.0.1

- `python` 解析：先试平台常见解释器（Windows `python`，macOS/Linux `python3`），可用 `JIPU_PYTHON` 覆盖；不再硬编码。
- 新增 `roles` 动作：列出七个角色；`role=<name>` 返回设定全文，可直接当 subagent prompt。
- 新增 `status` 动作：读 `项目配置.json` 与 `_tracking-state.json`，报项目名、已提交章、现金、开口的线、下一章。
- `run` 的 `project` 改为可选：省略时从当前目录向上找 `项目配置.json`，再退到当前目录。
- 14 个脚本的自检在 CI 双平台跑（新增 `scripts/selftest-all.mjs` 与 GitHub Actions）。

## 1.0.0

- 首个公开版本：单一 `jipu` 工具（skill / scripts / run / selftest），内含 338 行工序手册、12 份 references、14 个门禁脚本、12 类目模板、81 个剧情模板与桥段库。
