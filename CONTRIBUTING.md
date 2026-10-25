# 参与贡献

## 提 issue 之前

1. 先跑自测：`python3 skill/arkbox/scripts/selftest.py`（不联网、不读凭证）；
2. 登录 / 拉取类问题附上 `python3 skill/arkbox/scripts/ark_doctor.py` 的输出；
3. 使用 issue 模板（bug / feature），一句话说清「做了什么、期望什么、实际什么」。

## 提交 PR 的规矩

- **严禁提交任何真实账号数据**：真实昵称、UID、寻访记录、登录截图一律不进仓库；
  演示与测试统一使用 `fixtures/demo-records.jsonl`（合成数据）。
- `selftest.py` 与 `tests/e2e_check.py` 必须通过（CI 会在 macOS / Windows / Linux × Python 3.9 / 3.12 跑）。
- **零第三方依赖是硬约束**：不要引入任何 pip 包。
- 文案遵循现有口径：按池独立、非全服排名、"本档案区间"、不承诺零风险、仅国服官服。

## 开发与发布

- 目录结构与测试命令见 README「目录」「测试」两节。
- 维护者的发布流程与隐私核查清单见 `docs/PUBLISHING.md`。
