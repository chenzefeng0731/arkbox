# GitHub 发布清单

## 1. 私密数据先移出仓库

不要提交（均已写入 `.gitignore`，2026-10-25 处理完毕）：

- `~/.arkbox/`（凭证、原始档案、缓存、reports）
- `site/`（Qoder 站点描述与发布状态）
- `docs/P0-验收/`、`docs/P1-demo/`、`docs/P1-final/`、`docs/真实数据*`、`docs/竞品参考/`
  （真实账号产物已移至 `~/Documents/Projects/历史归档/arkbox-真实账号产物-2026-10-25/`）
- 过程文档：`产品策划书.md`、`prompt-for-chatgpt.md`、`docs/Kimi评审验收-P0P1P2.md`、`docs/参考-ChatGPT独立方案原稿.md`
- `gacha_records.json`（fetch 的默认输出，含真实寻访记录）
- 任何含真实昵称/完整 UID 的 HTML、Markdown、截图

公开仓库的演示材料统一用 `fixtures/demo-records.jsonl` 生成（`docs/演示产物/` 为当前样例）。

## 2. 本地验证

```bash
python3 skill/arkbox/scripts/selftest.py
python3 skill/arkbox/scripts/ark_doctor.py
python3 skill/arkbox/scripts/ark_gacha.py analyze \
  --records fixtures/demo-records.jsonl --nick 演示博士 \
  --poster --html
```

确认 demo 海报、HTML、入职信息（需真实登录时）都正常。

## 3. 仓库内容

- `README.md`：三条命令跑通
- `LICENSE`：MIT（仅代码）
- `THIRD_PARTY_NOTICES.md`：游戏数据/头像/第三方组件
- `install.py`：跨平台安装
- `.github/workflows/test.yml`：macOS/Windows/Ubuntu × Python 3.9/3.12
- `fixtures/demo-records.jsonl`：合成 demo，不含真实账号

## 4. 发布前隐私扫描

```bash
# 在仓库根目录（把 <真实昵称>、<完整UID> 换成你自己的再跑）
grep -RIn "<真实昵称>\|<完整UID>" . --exclude-dir=.git
grep -RnoE "UID[^<\n]{0,4}[0-9]{3,}" . --exclude-dir=.git --include="*.html"
```

应当没有输出。站点 URL 可以保留；真实昵称和完整 UID 不应出现。

## 5. 平台边界

- Qoder：可以安装 skill，并用 `--site` 发布 Qoder Sites。
- 其他 Agent：读取 `SKILL.md` 或直接调用 Python CLI；没有 Qoder Sites 时交付 `report.html`。
- 没有 Chrome/Edge/Chromium 的机器：只生成 HTML，不生成 PNG；在 README 中说明。
- 跨平台视觉不承诺像素级一致；数据、HTML 结构、规则和文案一致。

## 6. 版本与 release

- `VERSION` 与 `CHANGELOG.md` 对齐。
- GitHub Release 附 `.skill`/zip 包和 demo 截图。
- 不要把本地 `site/` 或账号产物打进 release。
