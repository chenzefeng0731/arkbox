# ArkBox · 明日方舟寻访档案

[![CI](https://github.com/chenzefeng0731/arkbox/actions/workflows/test.yml/badge.svg)](https://github.com/chenzefeng0731/arkbox/actions/workflows/test.yml)

**ArkBox 是明日方舟玩家的本地寻访档案馆**：森空岛扫码授权后，它把官方能查到的寻访记录
整理成一份工业档案风的个人档案——寻访分析、泰拉图鉴、分享海报。全部在本地生成，
发出去的产物不含 UID。

> 把你的抽卡史，装订成一份能晒的档案。

<p align="center">
  <img src="docs/demo-archive.png" alt="档案页 · 寻访分析" width="49%">
  <img src="docs/demo-terra.png" alt="档案页 · 泰拉图鉴" width="49%">
</p>

非官方玩家工具，和鹰角网络没有隶属或授权关系；**只支持国服官服**——寻访记录只有官服渠道能查，
B 服、国际服用不了。代码 MIT，游戏数据和素材版权归原权利方。

## 30 秒看效果（不用登录）

```bash
git clone https://github.com/chenzefeng0731/arkbox.git arkbox
cd arkbox
# Windows 用户请把 python3 换成 python
python3 skill/arkbox/scripts/ark_gacha.py analyze \
  --records fixtures/demo-records.jsonl --nick 演示博士 --tenure 2024-07-14 \
  --poster --html
```

这条命令用一份合成演示数据跑完整流程，会给你一张抽卡海报和一个单页档案报告。注意是单页：
没登录就拿不到你的干员持有数据。扫码登录后再跑同一条命令，档案页就变成
“寻访分析、泰拉图鉴”两个页签，还能导出分享图——就是上面两张截图的样子。

## 出什么

| 命令 | 产出 | 说明 |
|---|---|---|
| `analyze --poster --html` | 海报 PNG、档案页 HTML | 最常用的交付：2160×2880 海报，加双页签自包含网页 |
| `analyze --records 记录.json` | 同上 | 离线模式，不吃账号，用自己的记录文件 |
| `ark_box.py gallery --open` | 干员图鉴页 | 按职业、星级、等级、潜能、时装筛选 |
| `analyze --site --site-dir site` | 静态站点目录 | 自带 noindex、昵称固定“博士”；发布到任意静态托管（见 [docs/PUBLISHING.md](docs/PUBLISHING.md)） |

档案页里还有这些细节：卡池时间线、称号候选切换（欧皇、三顾茅庐、保底人……）、
分享文案一键复制、口径审计表。

## 数字怎么算

按池子分开统计，不跨池合并；池内均值、整体效率、当前垫抽、最长间隔各是各的，
海报上每个数字底下都标了口径。“理论位置”是和同段数理论样本比，**不是全服排名**；
数据缺了会直接说缺，不编。

## 开始之前

| 依赖 | 必需程度 | 说明 |
|---|---|---|
| Python 3.9+ | 必需 | macOS 自带；Windows 到 [python.org](https://www.python.org/downloads/) 安装（勾选 Add python.org to PATH） |
| 森空岛 App | 登录时需要 | 手机安装并绑定明日方舟角色，扫码授权；只玩离线记录（`--records`）则不需要 |
| Chrome、Edge、Chromium | 可选 | 生成海报 PNG 用；没有时交付 HTML，可自行截图 |
| `pip3 install qrcode` | 可选 | 登录二维码本地生成；不装则降级为本地 HTML 页（经公开 QR 服务渲染，只发送一次性 scanId） |

- **Windows 用户注意**：命令里的 `python3` 换成 `python` 或 `py -3`，其余一致。
- 除了上表的可选项，不装任何东西：纯标准库，所有网络请求都写在源码里（清单见 SKILL.md“网络出口清单”）。macOS、Windows、Linux 都能跑。

## 安装和登录

```bash
python3 install.py                                          # 装 skill（不想装也能直接跑命令）
python3 skill/arkbox/scripts/skland_core.py login           # 森空岛 App 扫码
python3 skill/arkbox/scripts/ark_doctor.py                  # 环境自检
```

- 不用 git 的话：GitHub 页面绿色 Code 按钮 → Download ZIP，解压后跑同一条 `install.py`。
- 凭证存在 `~/.arkbox/credentials.json`（权限 600）。失效大多不用重新扫码，`hg_token` 会自动续期；官方没承诺有效期，社区经验是不改密码、不在森空岛 App 登出或清设备就能一直用，真失效了 doctor 会提醒。

## 给 AI Agent 用

自带一个通用 Skill（`skill/arkbox/SKILL.md`），装好后直接跟 Agent 说
“用 arkbox 分析我的明日方舟抽卡记录，生成海报和 HTML”。`--json` 机器可读、
`--audit` 口径校验表、退出码明确——任何能跑本地命令的 Agent 用的都是同一套计算，
数字由 ArkBox 出，Agent 只负责转述，不能改数。

## 数据与隐私

- 海报、HTML、站点、图鉴都不显示 UID；UID 只存在本地凭证和归档里。想连昵称也隐掉加 `--hide-nick`，公开站点固定显示“博士”并禁止收录。
- 原始记录只在本机归档，不上传。凭证就是账号钥匙，别分享；要删本地凭证用 `skland_core.py logout`（彻底解绑去森空岛 App 的授权管理）。

## 测试

```bash
python3 skill/arkbox/scripts/selftest.py    # 单元与口径自测（不联网、不读凭证）
python3 tests/e2e_check.py                  # 端到端冒烟：fixtures 全链路、数字与隐私断言
```

CI 在 macOS、Windows、Linux × Python 3.9/3.12 上每次提交自动跑全部测试。

## 常见问题

- **会不会封号、盗号？** 只读官方可查接口、低频请求、不碰客户端；凭证只存本机不上传。但这不是官方工具，没人能承诺零风险，介意就别用。
- **为什么记录不全、只有几个月？** 森空岛只返回官方可查窗口内的记录，不是漏了；报告里写的是“本档案区间”。
- **平均抽数为什么和别人算的不一样？为什么没有全服排名？** 各池子分开统计、不跨池累计，四个口径各算各的，硬拉到一块比会失真；“理论位置”是和同抽数理论样本比，不是排名。
- **Windows 怎么用？** `python3` 换成 `python` 或 `py -3`；出 PNG 要本机有 Chrome 系浏览器，没有也能出 HTML。
- **能商用或二次分发吗？** 代码 MIT；游戏名称、头像、数据版权归鹰角网络等原权利方，本项目非官方、非商业。

## 已知边界

- 森空岛只返回可查窗口内的记录，证明不了账号全历史；每个池子的第一段可能接着档案外的垫抽，不做校正。
- 标准、中坚历史没法证明完整，默认不跨池累计；标准、中坚、特殊的兑换井规则不统一，不硬算（限定 300、联动 120 只显示档案内进度）。
- 截图 OCR 和需要登录态的记录链接不会自动导入；公开的 JSON 链接可以用 `--records URL`。
- 大陆直连 GitHub raw 不稳：元数据和头像有 jsdelivr 镜像兜底；真拉不动会降级（池型、UP 显示“待核”），不影响基础统计和出报告。
- 接口是社区逆向出来的，官方改版可能搞坏登录或拉取；遇到问题带上 `ark_doctor.py` 的输出去开 issue。
