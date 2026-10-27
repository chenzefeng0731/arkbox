# Changelog

## 1.0.0 — 2026-10-28 · 首个公开发行版

市场定位收口为「明日方舟玩家的本地寻访档案馆」：本地优先、口径诚实、舟味设计。

- **README 全面重写**：一句话定位 + 海报主视觉 +「晒得出 / 看得懂 / 留得住」三支柱；
  修正档案页描述与实现一致（两个页签 + 分享弹层，原「四页签」表述废弃）。
- **撤下英文版 README**：产品一切原点是森空岛扫码授权，仅服务国服官服玩家，英文页属于过度承诺。
- **演示图全量重制**：新增 `tools/make_demo_images.py`（fixtures 合成记录 + md5 确定性
  合成演示 box，非任何真实账号数据），一键重产 `docs/demo-poster / demo-archive /
  demo-terra / demo-share` 四张 2x 图，与封板视觉同源。
- **版本口径统一**：`VERSION`、SKILL metadata、代码注释中的 0.7/v0.8 叙述统一为 v1.0；
  0.6–0.7 系列的全部能力（按池独立统计、隐私硬化、跨平台 CI、泰拉图鉴口径修正等）归入本版。

## 0.7.3 — 2026-10-27

- **泰拉图鉴世界观口径修正**（对照游戏解包数据 `character_table.json` 全量核验后修）：临光（5★，使徒成员）设定上为卡西米尔骑士，从卡兹戴尔桶改归卡西米尔——`ark_terra.py` 新增 `_MANUAL_BUCKET` 显式例外表，`bucket_of()` 改为 `(char_id, entry)` 双参签名（`ark_archive_html.py` 调用点同步）。
- 口径注释如实化：档案页与泰拉分享海报的口径行从"按 nationId 归档"改为完整描述——nationId 为主；空值萨卡兹系按 `groupId=babel`（巴别塔）/ `teamId=followers`（使徒）归并卡兹戴尔（临光例外）；nationId 为空的联动干员归"非泰拉"，怪物猎人联动干员游戏编码属罗德岛、随本舰归档。
- 泰拉分享海报"差一枚"清单与档案页面板统一口径：不再过滤 owned6=0 的地区，2×3 满排 6 张头像卡（含 0/1 地区），"距全泰拉还差 N 枚"迁入圆环区。
- 注：`output/` 档案页与海报 PNG 属真实数据产物（.gitignore），本版只含生成器侧修改；重跑 `analyze --html` 即产出修正后的档案页。

## 0.7.2 — 2026-10-25

- **README 批注修正**：①「干员筛选」表述拆清——筛选/图鉴是 `ark_box.py` 独立命令（filter 表格 / gallery 图鉴页），抽卡报告页为纯浏览交付；②安装章收敛为一条 `python3 install.py`（自动探测 Agent skills 目录，文案品牌中性，删「其他 Agent」分节）；③「首次登录」补充 token 有效期说明：官方无有效期承诺，社区经验为不改密码/不在森空岛 App 登出或清理设备即可一直使用，失效后 `ark_doctor.py` 明确提示重登、历史归档不受影响。
- **新增英文版 `README_EN.md`**，与中文版顶部互链语言切换。
- **海报与演示图全面升 2x**：headless 截图统一加 `--force-device-scale-factor=2`，海报输出 2160×2880（高分屏展示与社媒二次压缩不再发虚）；`docs/` 四张演示图（干员图鉴页 / 抽卡报告页 / 海报A / 海报B）同管道重制，图鉴页与海报A/B 均为合成演示数据。
- demo 海报移至 ASCII 路径 `docs/demo-poster.png`（照顾英文页面引用）。

## 0.7.1 — 2026-10-25

- **Windows 兼容修复**：所有 CLI 入口强制 UTF-8 输出——Windows 终端默认编码（cp1252/GBK）无法输出 ⚠/✓ 等符号，此前在"卡池拉取失败"等场景会直接崩溃（CI 首跑发现）。
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
