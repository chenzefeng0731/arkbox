# Changelog

## 0.7.1 — 2026-10-25

- 上架准备落地：新增 `tests/e2e_check.py` 端到端冒烟（33 项断言：demo 全链路 / Markdown 口径 / 坏输入 / 未登录引导 / 站点目录）并挂入 CI；新增 Issue 模板（纠错 / 许愿）。
- 大陆网络适配：干员元数据下载加 jsdelivr 镜像回退；海报/报告/图鉴头像加载失败自动换 jsdelivr 镜像再隐藏。
- README 补强：开始之前的前置条件表（Python/森空岛 App/浏览器/qrcode）、Windows `python` 命令注记、Download ZIP 安装方式、已知边界（大陆网络 / 接口失效预期）、零依赖可审计说明。
- 新增 `ARKBOX_NO_OPEN=1` 环境变量（CI/自动化不弹浏览器）；新增冷启动演练记录（`docs/冷启动演练-2026-10-25.md`）。

## 0.7.0 — 2026-10-25

- **分享产物全面移除 UID**：海报/HTML/站点/图鉴/Markdown 不再展示 UID；UID 不进入报告模型，只存在于本地凭证与归档目录。`--privacy` / `--uid` 参数移除，`--hide-nick` 保留。
- 报告页头重排：昵称后紧跟 `入职 YYYY-MM-DD · N 天`，再接本次记录截止日期。
- **demo 保真度**：`fixtures/demo-records.jsonl` 改为真实档案结构复刻（294 抽/10 六星，时间轴平移 180 天，无账号信息）；新增 `--tenure` 让离线演示也能展示完整页头。
- **两条线隔离**：仓库（GitHub 公开线）与已安装 skill（自用线）职责明确，见 `docs/两条线说明.md`；登录态与真实档案在 `~/.arkbox/`，两条线共享、永不进仓库。
- Bug 修复：未登录时人话报错（不再裸 traceback）；`fetch --out` 支持 `~`；官网 cookie 接口支持 gzip 响应；网络超时/重置统一转友好错误；干员元数据缓存加版本控制、下载失败降级旧缓存；浏览器截图超时不再崩溃；`pos` 为 null 的记录不再导致排序崩溃。
- 安全：新增 `skland_core.py logout` 删除本地凭证；SKILL.md 增加网络出口清单；`--records` 链接仅支持 https 且限 20MB；图鉴头像 URL 补转义。
- 文档：SKILL/README 同步跨平台定位（不再写"Mac 本地"）；api_notes 修正 X-Account-Token 表述；删除无引用的旧版 HTML 渲染器（ark_gacha.py -188 行）。

## 0.6.0 — 2026-10-25

- 抽卡海报专注抽卡，不塞助战/名片。
- 报告页头新增入职日期与天数；00 当前助战/博士数据模块和名片海报移除。
- 新增固定站点发布：`--site` 生成 `site/dist`、`.arkbox-site.json`、`.arkbox-publish.json`。
- 默认交付收敛为海报 PNG + 报告/站点；`--poster` 默认删除源 HTML。
- 凭证失效优先用 `hg_token` 静默续期；二维码缺失时降级为本地 HTML。
- 新增跨平台浏览器检测、`webbrowser` 打开、macOS/Windows/Linux CI。
- 新增 MIT License、第三方声明、`install.py` 与 README。
