#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""干员筛选（我的干员 / box）v0.2 —— 新增图鉴式浏览页。

用法:
  python3 ark_box.py filter [选项]      # 表格筛选（同 v0.1）
  python3 ark_box.py gallery [筛选条件] [--open]   # 图鉴式浏览页（HTML）
  python3 ark_box.py stats              # 持有总览

gallery 筛选条件与 filter 相同：--rarity/--profession/--min-level/--evolved/
--potential-min/--name/--skin/--sort/--limit
"""

import argparse
import html
import json
import os
import sys
import time
import webbrowser
from collections import Counter
from datetime import datetime

from skland_core import ArkApiError, load_creds, player_info, ensure_auth
from ark_meta import load_meta

# Windows 终端默认编码（cp1252/GBK）无法输出 ⚠/✓ 等符号：统一强制 UTF-8 输出
for _stdio in (sys.stdout, sys.stderr):
    try:
        _stdio.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 图源已验证 content-type=image/png（勿改回 yituliu——其路径返回 HTML fallback 假 200）
AVATAR_URL = "https://raw.githubusercontent.com/yuanyan3060/ArknightsGameResource/main/avatar/{cid}.png"
# 加载失败先换 jsdelivr 镜像（raw.githubusercontent.com 在部分网络不可达），再失败隐藏
AVATAR_ONERROR = (
    "if(!this.dataset.f){this.dataset.f=1;"
    "this.src=this.src.replace('raw.githubusercontent.com','cdn.jsdelivr.net/gh')"
    ".replace('/main/','@main/');}"
    "else{this.style.visibility='hidden'}"
)

GALLERY_CSS = """
:root{--bg:#14161b;--card:#1e222b;--ink:#e8e6e3;--dim:#9aa0ab;--line:#2c313d}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,'PingFang SC',sans-serif;padding:28px 16px;max-width:1080px;margin:0 auto}
h1{font-size:20px}.sub{color:var(--dim);font-size:13px;margin:4px 0 20px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(96px,1fr));gap:10px}
details{position:relative}
summary{list-style:none;cursor:pointer}
summary::-webkit-details-marker{display:none}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden;text-align:center;transition:transform .12s}
.card:hover{transform:translateY(-2px)}
.imgbox{position:relative;padding-top:100%;overflow:hidden}
.imgbox img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.r6{border-color:#b8860b;box-shadow:0 0 0 1.5px rgba(245,197,66,.55)}
.r5{border-color:#7b68ee;box-shadow:0 0 0 1px rgba(155,120,255,.4)}
.r4{border-color:#4a90d9;box-shadow:0 0 0 1px rgba(74,144,217,.35)}
.pot{position:absolute;top:4px;right:4px;background:rgba(0,0,0,.65);border-radius:6px;font-size:10px;padding:1px 5px}
.e2{position:absolute;top:4px;left:4px;background:rgba(245,197,66,.9);color:#000;font-weight:700;border-radius:6px;font-size:10px;padding:1px 5px}
.nm{font-size:12px;padding:5px 4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.info{display:none;position:absolute;z-index:9;left:50%;transform:translateX(-50%);top:calc(100% + 6px);width:200px;background:#262b36;border:1px solid var(--line);border-radius:10px;padding:12px;font-size:12.5px;text-align:left;box-shadow:0 8px 24px rgba(0,0,0,.5)}
details[open] .info{display:block}
.info b{font-size:14px}.info .row{display:flex;justify-content:space-between;color:var(--dim);margin-top:4px}
.footer{color:var(--dim);font-size:12px;text-align:center;margin-top:24px}
"""


def fetch_chars(creds, uid):
    """拉取干员持有列表，合并元数据（v0.1 逻辑）。"""
    creds = ensure_auth(creds, uid=uid)
    data = player_info(creds["cred"], creds["cred_token"], uid)
    meta = load_meta()
    chars = []
    for c in data.get("chars", []):
        char_id = c.get("charId", "")
        m = meta.get(char_id, {})
        equips = c.get("equip") or []
        skills = c.get("skills") or []
        chars.append({
            "char_id": char_id,
            "name": m.get("name") or char_id,
            "rarity": m.get("rarity") or 0,
            "profession": m.get("profession") or "?",
            "level": c.get("level", 0),
            "evolve": c.get("evolvePhase", 0),
            "potential": c.get("potentialRank", 0) + 1,
            # 官方 API 无 skillLevel 字段（旧映射恒 0）：主技能等级=mainSkillLvl(1-7)，
            # 专精=skills[].specializeLevel 取最大(0-3)。ark_archive_html 的 mas=专精语义。
            "skill": c.get("mainSkillLvl", 0),
            "mastery": max([0] + [(s.get("specializeLevel") or 0) for s in skills]),
            "mod": any((e.get("level") or 0) > 0 for e in equips),
            "skin_id": c.get("skinId", ""),
        })
    return chars, data


def extract_profile(data, chars):
    """从 player_info 抽「名片级」信息：看板娘 + 助战干员。

    看板娘来自 status.secretary（只给 charId/skinId），等级练度回 chars 里补；
    助战来自 assistChars（自带等级/精英化/潜能/专精/模组）。
    纯读取，不写归档；取不到就返回空，不影响其他页签。
    """
    by_id = {c.get("char_id"): c for c in (chars or [])}

    def _fill(cid, skin_id="", src=None):
        base = by_id.get(cid) or {}
        src = src or {}
        return {
            "id": cid,
            "name": base.get("name") or cid,
            "rarity": base.get("rarity") or 0,
            "profession": base.get("profession") or "?",
            "level": src.get("level") or base.get("level") or 0,
            "evolve": src.get("evolvePhase") if src.get("evolvePhase") is not None
                      else (base.get("evolve") or 0),
            "potential": (src.get("potentialRank") + 1) if src.get("potentialRank") is not None
                         else (base.get("potential") or 1),
            "skill": src.get("mainSkillLvl") or 0,
            "mastery": src.get("specializeLevel") or 0,
            "mod": bool((src.get("equip") or {}).get("level")) if isinstance(src.get("equip"), dict)
                   else bool(base.get("mod")),
            "skin": skin_id or src.get("skinId") or base.get("skin_id") or "",
        }

    status = data.get("status") or {}
    sec = status.get("secretary") or {}
    secretary = _fill(sec.get("charId"), sec.get("skinId")) if sec.get("charId") else None
    assist = [_fill(a.get("charId"), a.get("skinId"), a)
              for a in (data.get("assistChars") or []) if a.get("charId")]
    return {"secretary": secretary, "assist": assist}


def render_gallery(chars, nick, out_path):
    cards = []
    for c in chars:
        rcls = f"r{c['rarity']}" if c["rarity"] >= 4 else ""
        pot = f'<span class="pot">潜{c["potential"]}</span>' if c["potential"] > 1 else ""
        e2 = '<span class="e2">精二</span>' if c["evolve"] == 2 else ""
        skin = " · 穿时装" if "#" in c["skin_id"] else ""
        mod = " · 有模组" if c["mod"] else ""
        cards.append(f'''<details><summary><div class="card {rcls}">
 <div class="imgbox"><img loading="lazy" src="{AVATAR_URL.format(cid=html.escape(c['char_id'] or ''))}" alt="{html.escape(c['name'])}" onerror="{AVATAR_ONERROR}">{pot}{e2}</div>
 <div class="nm">{html.escape(c["name"])}</div>
</div></summary><div class="info">
 <b>{html.escape(c["name"])}</b> <span style="color:var(--dim)">{"★" * c["rarity"]}</span>
 <div class="row"><span>职业</span><span>{html.escape(c["profession"])}</span></div>
 <div class="row"><span>等级</span><span>Lv.{c["level"]} · {["未精","精一","精二"][c["evolve"]]}</span></div>
 <div class="row"><span>潜能</span><span>{c["potential"]}</span></div>
 <div class="row"><span>技能</span><span>Lv.{c["skill"]}{" · 专%d" % c["mastery"] if c["mastery"] else ""}</span></div>
 <div class="row"><span>其他</span><span>{(skin + mod).strip(" ·") or "—"}</span></div>
</div></details>''')

    page = f'''<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>我的干员 · {html.escape(nick)}</title><style>{GALLERY_CSS}</style></head><body>
<h1>🏅 我的干员图鉴</h1>
<div class="sub">{html.escape(nick)} · 共 {len(chars)} 名 · 点击干员卡查看详情 · 生成于 {datetime.now().strftime("%Y-%m-%d %H:%M")}</div>
<div class="grid">{"".join(cards)}</div>
<div class="footer">ArkBox 生成 · 头像来自社区资源镜像（yuanyan3060/ArknightsGameResource）· 数据仅存本地</div>
</body></html>'''
    out_path = os.path.expanduser(out_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(page)
    return out_path


def parse_args():
    ap = argparse.ArgumentParser(description="明日方舟干员筛选")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--rarity", help="稀有度，如 6 或 6,5")
        p.add_argument("--profession", help="职业中文名")
        p.add_argument("--min-level", type=int)
        p.add_argument("--evolved", type=int, choices=[0, 1, 2])
        p.add_argument("--potential-min", type=int)
        p.add_argument("--name", help="名字关键词")
        p.add_argument("--skin", action="store_true")
        p.add_argument("--sort", default="level", choices=["level", "potential", "rarity", "name"])
        p.add_argument("--limit", type=int, default=200)
        p.add_argument("--json", action="store_true")

    f = sub.add_parser("filter", help="筛选干员（表格）")
    common(f)
    g = sub.add_parser("gallery", help="图鉴式浏览页")
    common(g)
    g.add_argument("--open", action="store_true", help="生成后用浏览器打开")
    sub.add_parser("stats", help="持有总览")
    return ap.parse_args()


def apply_filters(chars, args):
    if args.rarity:
        want = {int(x) for x in args.rarity.split(",")}
        chars = [c for c in chars if c["rarity"] in want]
    if args.profession:
        chars = [c for c in chars if c["profession"] == args.profession]
    if args.min_level:
        chars = [c for c in chars if c["level"] >= args.min_level]
    if args.evolved is not None:
        chars = [c for c in chars if c["evolve"] == args.evolved]
    if args.potential_min:
        chars = [c for c in chars if c["potential"] >= args.potential_min]
    if args.name:
        chars = [c for c in chars if args.name in c["name"]]
    if args.skin:
        chars = [c for c in chars if "#" in c["skin_id"]]
    keymap = {
        "level": lambda c: (-c["level"], -c["rarity"]),
        "potential": lambda c: (-c["potential"], -c["level"]),
        "rarity": lambda c: (-c["rarity"], -c["level"]),
        "name": lambda c: c["name"],
    }
    chars.sort(key=keymap[args.sort])
    return chars


def main():
    args = parse_args()
    try:
        creds = load_creds()
        uid = creds["uid"]
        nick = creds.get("nick_name") or uid
        chars, info = fetch_chars(creds, uid)

        if args.cmd == "stats":
            by_r = Counter(c["rarity"] for c in chars)
            e2 = sum(1 for c in chars if c["evolve"] == 2)
            lv90 = sum(1 for c in chars if c["level"] >= 90)
            skins = info.get("skins") or []
            print("\n".join([
                f"## 干员持有总览 · {nick}\n",
                f"- 持有干员 **{len(chars)}** 名",
                f"- 六星 **{by_r.get(6, 0)}** / 五星 **{by_r.get(5, 0)}** / 四星 **{by_r.get(4, 0)}**",
                f"- 精二 **{e2}** 名，满级(90) **{lv90}** 名",
                f"- 拥有时装 **{len(skins)}** 套",
            ]))
            return

        chars = apply_filters(chars, args)
        total = len(chars)

        if args.cmd == "gallery":
            path = render_gallery(chars[: args.limit], nick,
                                  f"~/.arkbox/reports/box_{time.strftime('%Y%m%d_%H%M')}.html")
            print(f"图鉴页已生成: {path}（{min(total, args.limit)} 名）", file=sys.stderr)
            if getattr(args, "open", False):
                try:
                    webbrowser.open("file://" + os.path.abspath(os.path.expanduser(path)))
                except Exception:
                    pass
            return

        shown = chars[: args.limit]
        if args.json:
            print(json.dumps({"total": total, "list": shown}, ensure_ascii=False, indent=2))
            return
        star = {6: "★★★★★★", 5: "★★★★★", 4: "★★★★", 3: "★★★", 2: "★★", 1: "★"}
        ev_zh = {0: "未精", 1: "精一", 2: "精二"}
        lines = [f"## 干员筛选 · {nick}", f"匹配 **{total}** 名（展示前 {len(shown)}）\n"]
        lines.append("| 干员 | 星级 | 职业 | 等级 | 精英化 | 潜能 | 技能 | 备注 |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for c in shown:
            notes = []
            if c["mod"]:
                notes.append("有模组")
            if "#" in c["skin_id"]:
                notes.append("穿时装")
            lines.append(
                f"| {c['name']} | {star.get(c['rarity'], '?')} | {c['profession']} "
                f"| {c['level']} | {ev_zh.get(c['evolve'], '?')} | {c['potential']} "
                f"| Lv.{c['skill']}{'·专%d' % c['mastery'] if c['mastery'] else ''} "
                f"| {'、'.join(notes) or '—'} |"
            )
        if total > len(shown):
            lines.append(f"\n（还有 {total - len(shown)} 名未展示，可加 --limit 调整）")
        print("\n".join(lines))
    except ArkApiError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
