# 发布 / 更新 ArkBox 固定站点

## 交付形态

- **有固定站点需求**：`poster.png` + 站点目录（发布到你用的静态托管）。
- **只要文件**：`poster.png` + 自包含 `report.html`。
- 不再对外交付：海报源 HTML、手机截图、Markdown、交付说明。

## 生成站点目录

```bash
cd <项目根目录>
python3 <skill>/scripts/ark_gacha.py analyze \
  --site --site-dir site --poster --quiet
```

产物：

- `site/dist/index.html`：公开报告，昵称显示为“博士”，不含 UID，`noindex,nofollow,noarchive`；页头带入职天数
- `site/dist/robots.txt`：`Disallow: /`
- `site/.arkbox-site.json`：ArkBox 自己的发布元数据
- `site/.arkbox-publish.json`：本次生成的精确发布请求（actionId/projectId/webDirectory），供具备站点发布能力的 Agent 直接读取

## 发布

方式一（任意静态托管）：把 `site/dist/` 整个目录上传到 GitHub Pages / Cloudflare Pages / Vercel /
Netlify 等任意静态托管，即得固定 URL。

方式二（Agent 代发）：把站点目录交给具备站点发布能力的 Agent（有 prepare/publish 类工具的），
让它读取 `site/.arkbox-publish.json` 作为本次发布请求：首次 `createNewSite: true`，
`projectRoot` 指向 `<项目根目录>/site`、`webDirectory: "dist"`；发布完成后把
`project_id` / `site_id` / `site_url` 写回 `site/.arkbox-site.json`，并记得把访问策略设为公开。

## 后续更新同一站点

1. 重新运行 `--site` 生成新的 `dist/`。
2. 方式一重新同步 `dist/` 到原托管位置，URL 不变。
3. 方式二从 `site/.arkbox-site.json` 读取 `project_id`，用 `.arkbox-publish.json` 里的新
   `actionId`、同一 `project_id` 再次 prepare/publish，不要 `createNewSite`。

## 隐私

- 站点模式固定使用昵称“博士”，不写真实昵称；产物不含 UID（UID 不进入报告模型）。
- 页面带 `noindex,nofollow,noarchive`，`robots.txt` 禁止抓取。
- 海报是独立文件，保留真实昵称、不含 UID；不要把带昵称的海报上传到公开站点。
- 如果用户要求站点显示真实昵称，需要显式改站点构建参数，并重新确认公开访问风险。

## 检查

```bash
# 不应出现 UID+数字 的展示（口径说明文字允许出现 UID 一词）
grep -oE 'UID[^<\n]{0,4}[0-9]{3,}' site/dist/index.html || echo "OK: 无 UID 展示"
# 应有 noindex 和 robots
grep -o 'noindex,nofollow,noarchive' site/dist/index.html
cat site/dist/robots.txt
```
