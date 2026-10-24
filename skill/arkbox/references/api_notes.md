# ArkBox API 备忘（2026-10 验证）

来源：ProbiusOfficial/Skland_API、FrostN0v0/nonebot-plugin-skland（交叉验证），自行探测确认。

## 登录链路（鹰角通行证 as.hypergryph.com）

- 发验证码：`POST /general/v1/send_phone_code` body `{phone, type: 2}`
- 验证码换 token：`POST /user/auth/v2/token_by_phone_code` body `{phone, code}` → `data.token`
- 扫码：`POST /general/v1/gen_scan/login` body `{appCode: "4ca99fa6b56cc2ba"}` → `scanId`；
  二维码内容 `hypergryph://scan_login?scanId=<scanId>`；
  轮询 `GET /general/v1/scan_status?scanId=` → `scanCode`；
  `POST /user/auth/v1/token_by_scan_code` body `{scanCode}` → `data.token`
- 森空岛授权：`POST /user/oauth2/v2/grant` `{appCode: "4ca99fa6b56cc2ba", token, type: 0}` → `code`
- 官网授权：同上但 `appCode: "be36d44aa36bfb5b", type: 1` → 直接返回 `data.token`（官网通行证 token）
- cred：`POST https://zonai.skland.com/api/v1/user/auth/generate_cred_by_code` `{kind: 1, code}` → `data.cred` + `data.token`（token 用于签名）
- cred token 刷新：`GET /api/v1/auth/refresh`，header 带 cred

## 官网寻访记录（ak.hypergryph.com）

请求头：`X-Account-Token: <原始扫码/验证码 token（hg_token）>`、`X-Role-Token: <role_token>`、`Cookie: ak-user-center=<cookie>`

- role_token：`POST https://binding-api-account-prod.hypergryph.com/account/binding/v1/u8_token_by_uid` `{uid, token: <官网通行证 token（grant type=1 换发）>}`
- cookie：`POST https://ak.hypergryph.com/user/api/role/login` `{token: <role_token>}` → Set-Cookie `ak-user-center`
- 卡池目录：`GET /user/api/inquiry/gacha/cate?uid=<uid>` → `[{id, name}]`
- 记录（分页）：`GET /user/api/inquiry/gacha/history?uid=&category=<id>&size=100[&gachaTs=&pos=]`
  - 翻页游标：上一页最后一条的 `gachaTs`（毫秒）+ `pos`
  - 每条 = 一抽：`poolId, poolName, charId, charName, rarity, isNew, gachaTs, pos`
  - 六星口径：rarity≥5（0-indexed）；脚本内做 max 自适应兜底
  - `pos` 是十连内的 0–9 位次，不是卡池总抽数；卡池内第几抽由时间正序枚举
  - 分页到 `max_pages` 仍有 `hasMore` 时标 `truncated`，覆盖状态记“已知缺口”，
    不要冒充全量
- 六星概率规则（2026-10 核验）：2% 基础；连续 50 抽未出后第 51 抽起每抽 +2%；
  第 99 抽必出；期望 34.59 抽。不同卡池计数独立。
- 账号全历史无法由官方接口证明：默认标“本档案区间（仅部分历史，完整性未知）”，
  不要写“生涯/全量/完整连续”。

## 卡池表与池型（PRTS 镜像）

源：`https://weedy.prts.wiki/gacha_table.json`，缓存 `~/.arkbox/cache/gacha_pool_table.json`（v3）。

- `gachaPoolDetail.detailInfo.limitedChar`：限定角色；非空才是限定池。
- `detailInfo.upCharInfo.perCharList`：当期 UP；`rarityRank == 5` 是六星。
- `detailInfo.gachaObjList` 里 `gachaObject == "RATE_UP_6"` 的 `param` 是卡池文案：
  “标准寻访 / 限定寻访 / 中坚寻访 / 联动活动名 …”，用于分池型。
- **单 UP ≠ 限定**：联动池也常是单 UP；旧逻辑用 `len(six_up)==1` 推断限定，
  会把 `LINKAGE_77_0_1`（石白深蓝之夜）误标成限定。
- 池型：limited / kernel / linkage / standard / special / unknown；
  匹配不到时标“池型待核”，不硬判。
- 官方保底计数：标准/中坚同类型跨池累计；限定/联动/特殊各自当期域。
  **但本工具不跨池合并**：森空岛只返回可查窗口，无法证明更早标准/中坚历史；
  每池从档案内首条记录起算，首段可能承接档案外垫抽，报告会标注该偏差。
- UP 命中：六星 `charId` 是否在当期六星 UP 名单；未匹配池标“UP 待核”，
  不计入总命中率分母。UP 保底/120/150/300 井是另一套字段，不与六星垫混用。

## 森空岛玩家数据（zonai.skland.com/api/v1，需签名）

- 绑定：`GET /game/player/binding` → `list[].appCode=="arknights"` 的 `bindingList[]`（uid、channelMasterId、nickName）
- 玩家详情：`GET /game/player/info?uid=<uid>` → `chars[]`（charId、level、evolvePhase、potentialRank、skillLevel、skinId、equip）、`skins[]`
- 业务码：0 成功；10000 未授权；10002 未登录

### 签名算法

```
ts = int(time.time()) - 1
sign_map = {"platform":"","timestamp":ts,"dId":"","vName":""}
query = GET ? url.query : json.dumps(body, ensure_ascii=False, separators=(", ", ": "))
secret = path + query + ts + json.dumps(sign_map, separators=(",",":"))
sign = md5( hex( hmac_sha256(key=cred_token, msg=secret) ) )
headers = {cred, sign, platform:"", timestamp:ts, dId:"", vName:"", UA}
```

注意 POST body 序列化必须与签名一致（separators=(", ", ": ")，很反直觉但必须照做）。

## 干员元数据

源：`https://raw.githubusercontent.com/Kengxxiao/ArknightsGameData/master/zh_CN/gamedata/excel/character_table.json`（约 10MB）
- `rarity` 为 `"TIER_6"` 字符串（已是 1-6 口径）；若遇 0-5 数字则 +1
- 正式干员判定：`displayNumber` 非空（NPC/召唤物/剧情单位均为 null）
- profession 映射：PIONEER 先锋 / WARRIOR 近卫 / TANK 重装 / SNIPER 狙击 / CASTER 术师 / MEDIC 医疗 / SUPPORTER 辅助 / SPECIALIST 特种


## 玩家名片字段（player/info）

- `status.secretary`：看板 1 人 `{charId, skinId}`。
- `assistChars`：助战 3 人，含等级/精英化/潜能/技能专精/模组；不等于“收藏夹”。
- `charAssets`：可能的展示干员列表，当前测试账号为空，不能当稳定字段。
- `skinAssets` / `skinAssetList`：展示时装。
- `showConfig`：`charSwitch` / `skinSwitch` / `standingsSwitch`，公开产物需尊重。
- `chars[].favorPercent` / `gainTime`：信赖与获得时间；`skins[]`：时装与获得时间；`medal`：勋章。
- 不把 `ap`、`lastOnlineTs`、`building`、`recruit` 等实时/私密字段放进公开产物。
