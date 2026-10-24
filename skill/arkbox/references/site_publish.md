# 发布 / 更新 ArkBox 站点（Qoder Sites）

## 交付形态

- **Qoder 用户**：`poster.png` + 固定站点 URL。
- **Hermes / workbuddy / codex 等**：`poster.png` + 自包含 `report.html`。
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
- `site/.arkbox-publish.json`：本次生成的精确发布请求（actionId/projectId/webDirectory）
- `site/.ArkBox 寻访档案.qoder.site`：Qoder Sites 生成的描述文件，**不要手写/编辑**

## 第一次发布

1. 在 Qoder 中读取当前站点目录与账号上下文：`qoder_sites get_context`。
2. 可直接读取 `site/.arkbox-publish.json` 作为首次 prepare 请求；确认 `createNewSite: true`。
3. `prepare_site`：
   - `actionId`: 新 UUID
   - `projectRoot`: `<项目根目录>/site`
   - `webDirectory`: `dist`
   - `createNewSite`: `true`
   - `displayName`: `ArkBox 寻访档案`
   - `slug`: `arkbox-archive`（或当前账号可用名）
   - `spa`: `false`
4. 读 `get_publish_status`，确认 `artifactReady/canPublish`。
5. `publish_site`，继续读状态到 `published: true`；把 `.arkbox-publish.json` 的 `state` 改为 `published` 并记录 publishOperationId。
6. `get_site_access` → `update_access_policy` 设 `public`，明确 `confirmPublic: true`。
7. 把 `project_id`、`site_id`、`site_url` 写回 `site/.arkbox-site.json`（不是 `.qoder.site`）。

## 后续更新同一站点

1. 重新运行 `--site` 生成新的 `dist/`。
2. 从 `site/.arkbox-site.json` 读取 `project_id`。
3. 读取 `site/.arkbox-publish.json`，用其中的新 `actionId`、同一 `project_id`、`webDirectory: "dist"` 调用 `prepare_site`，不要 `createNewSite`。
4. `publish_site` 同一个新 actionId，读状态到 `published: true`。
5. 站点 URL 不变；`site/.arkbox-site.json` 保留原 ID 和 URL。

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

## 其他 Agent

没有 Qoder Sites 时，直接生成：

```bash
python3 <skill>/scripts/ark_gacha.py analyze --poster --html
```

交付 `poster.png` + `report.html` 两个文件即可；`--poster` 默认不再保留海报源 HTML。
