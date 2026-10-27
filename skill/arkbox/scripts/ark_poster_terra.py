#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""泰拉图鉴分享海报：与寻访海报（ark_poster_v4）同一设计体系。

2026-10-27 起替代档案页内 canvas 自绘的泰拉分享卡（drawTerra）：
设计源唯一（HTML/CSS 模板 + Chrome 截图），不再有两条各自漂移的产线。

v2（2026-10-27 用户反馈）：
- 「差一枚」文字卡 → 头像卡（寻访海报 op 卡语言，红虚线 = 未获得），2×3 满排
- 新增六维画像横条 / 综合分 / 已全档案 chips（解放 banner 小字）/ 泰拉总进度条
"""
import html
import os
import re
from datetime import datetime

from ark_poster_v4 import (
    CSS as BASE_CSS, _barcode, _seal, _section, _tag,
)

# 头像主源用 jsdelivr（与档案页一致），失败回退 raw.githubusercontent
TERRA_AVATAR_URL = ("https://cdn.jsdelivr.net/gh/yuanyan3060/"
                    "ArknightsGameResource@main/avatar/{cid}.png")
TERRA_AVATAR_ONERROR = (
    "if(!this.dataset.f){this.dataset.f=1;"
    "this.src=this.src.replace('cdn.jsdelivr.net/gh','raw.githubusercontent.com')"
    ".replace('@main/','/main/');}"
    "else{this.style.visibility='hidden'}"
)

RING_C = 2 * 3.1416 * 80  # 归档率圆环周长（r=80）


def _map_svg(terra):
    """复用档案页的泰拉地图 SVG，剥掉文字标签（标签由进度条承担）。"""
    from ark_archive_html import _terra_svg
    svg = _terra_svg(terra)
    svg = re.sub(r'<text[^>]*>.*?</text>', '', svg, flags=re.S)
    svg = re.sub(r'<g class="tcl-root">.*</g></svg>', '</svg>', svg, flags=re.S)
    svg = svg.replace('id="tc-map"', 'id="pmap"')
    # 原版完整视野（0 0 1280 620）：用户反馈裁切版"不全"，宁可进度条让位。
    # 横向加负边距——剪影坐标本来就画满 1280 宽，左右各留 ~4% 白边防贴边。
    svg = re.sub(r'viewBox="[^"]*"', 'viewBox="-60 0 1400 620"', svg)
    return svg


def _ring(pct):
    off = RING_C * (1 - pct / 100)
    return (
        '<svg viewBox="0 0 200 200" class="ring">'
        f'<circle cx="100" cy="100" r="80" class="ring-bg"/>'
        f'<circle cx="100" cy="100" r="80" class="ring-fg" '
        f'stroke-dasharray="{RING_C:.1f}" stroke-dashoffset="{off:.1f}"/>'
        f'<text x="100" y="97" text-anchor="middle" class="ring-v">{pct}%</text>'
        '<text x="100" y="122" text-anchor="middle" class="ring-l">六星归档率</text>'
        '</svg>'
    )


def _near_card(region_name, missing, cid_map):
    """各差 1 名头像卡：未获得干员红虚线框；>1 名 missing 时右上角 ×N。"""
    first = missing[0] if missing else "?"
    cid = cid_map.get(first) or ""
    img = (f'<img src="{TERRA_AVATAR_URL.format(cid=html.escape(cid))}" alt="" '
           f'onerror="{TERRA_AVATAR_ONERROR}">' if cid else "")
    badge = f'<span class="dup">×{len(missing)}</span>' if len(missing) > 1 else ""
    return (f'<div class="mop">{img}{badge}'
            f'<div class="info"><div class="nm">{html.escape(first)}</div>'
            f'<div class="rg">{html.escape(region_name)} · 差 {len(missing)} 名</div></div></div>')


def _dim_strip(dims):
    """六维画像：一行 6 组「标签 + 细条 + 百分比」。"""
    cells = "".join(
        f'<div class="dim"><div class="dim-t"><span>{html.escape({"潜能": "潜能≥4"}.get(d["name"], d["name"]))}</span>'
        f'<b>{d["pct"]}%</b></div>'
        f'<div class="dim-bar"><i style="width:{min(d["pct"], 100):.1f}%"></i></div></div>'
        for d in dims[:6])
    return f'<div class="dims">{cells}</div>'


EXTRA_CSS = """
.pmap{width:100%;border:1px solid rgba(21,23,24,.2);background:rgba(255,255,255,.5)}
.pmap svg{display:block;width:100%;height:auto}
.terra-top{display:flex;gap:10px;align-items:stretch;margin-bottom:8px}
.ring-box{width:236px;flex:0 0 auto;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;
  background:rgba(255,255,255,.55);border:1px solid rgba(21,23,24,.22);padding:8px;clip-path:polygon(0 0,calc(100% - 12px) 0,100% 12px,100% 100%,0 100%)}
.ring{width:150px;height:150px}
.ring-bg{fill:none;stroke:rgba(21,23,24,.12);stroke-width:15}
.ring-fg{fill:none;stroke:#B8860B;stroke-width:15;stroke-linecap:round;transform:rotate(-90deg);transform-origin:center}
.ring-v{font:900 37px 'SF Mono',Menlo;fill:#151718}
.ring-l{font:600 12px -apple-system,'PingFang SC';fill:rgba(21,23,24,.55)}
.all-line{font:600 13px 'SF Mono',Menlo;color:rgba(21,23,24,.55)}
.all-line b{color:#151718;font-size:17px}
.miss-line{font:800 15px -apple-system,'PingFang SC';color:#B8860B;margin-top:2px}
.miss-line b{font:900 20px 'SF Mono',Menlo}
.near-grid{flex:1;display:grid;grid-template-columns:1fr 1fr;gap:8px;align-content:stretch}
.mop{position:relative;background:rgba(255,255,255,.6);border:1.5px dashed rgba(200,42,54,.55);
  padding:8px 10px;display:flex;align-items:center;gap:10px;clip-path:polygon(0 0,calc(100% - 12px) 0,100% 12px,100% 100%,0 100%)}
.mop img{width:64px;height:64px;object-fit:cover;border:1px solid rgba(21,23,24,.2);filter:grayscale(.35);background:rgba(21,23,24,.06);flex:0 0 auto}
.mop .info{min-width:0}
.mop .nm{font-size:23px;font-weight:900;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mop .rg{font:600 13px 'SF Mono',Menlo;color:rgba(21,23,24,.5);margin-top:2px}
.mop .dup{position:absolute;top:3px;right:3px;background:#B8860B;color:#fff;font:800 10px 'SF Mono',Menlo;padding:1px 4px}
.mop.sum{border:1.5px solid rgba(21,23,24,.3);background:rgba(184,134,11,.07);flex-direction:column;align-items:flex-start;justify-content:center;gap:2px}
.mop.sum .k{font-size:15px;font-weight:800;color:rgba(21,23,24,.6)}
.mop.sum .big{font:900 34px/1 'SF Mono',Menlo;color:#B8860B}
.dims{display:flex;gap:8px;margin:2px 0 8px}
.dim{flex:1;min-width:0;background:rgba(255,255,255,.5);border:1px solid rgba(21,23,24,.16);padding:5px 8px 6px}
.dim-t{display:flex;justify-content:space-between;align-items:baseline;font-size:13px;font-weight:700;color:rgba(21,23,24,.7)}
.dim-t b{font:800 14px 'SF Mono',Menlo;color:#151718}
.dim-bar{height:6px;background:rgba(21,23,24,.08);border:1px solid rgba(21,23,24,.14);margin-top:3px;position:relative}
.dim-bar i{position:absolute;left:0;top:0;bottom:0;background:#0098DC}
.full-row{display:flex;gap:6px;flex-wrap:wrap;margin:2px 0 4px}
.fchip{font:800 13px -apple-system,'PingFang SC';color:#B8860B;border:1px solid rgba(184,134,11,.5);
  background:rgba(184,134,11,.07);padding:2px 8px;white-space:nowrap}
.fchip b{margin-right:3px}
.bar-row{display:flex;align-items:center;gap:10px;margin-bottom:5px}
.bar-row .n{width:96px;flex:0 0 auto;font-size:18px;font-weight:800;text-align:right}
.bar-row .tr{flex:1;height:9px;background:rgba(21,23,24,.08);border:1px solid rgba(21,23,24,.16);position:relative}
.bar-row .tr i{position:absolute;left:0;top:0;bottom:0;background:#B8860B}
.bar-row .c{width:84px;flex:0 0 auto;font:700 14px 'SF Mono',Menlo;color:rgba(21,23,24,.55);text-align:right}
.bar-row.full .c{color:#B8860B;font-weight:800}
.bar-row.total{margin-bottom:9px}
.bar-row.total .n{font-size:19px}
.bar-row.total .tr{height:13px}
.bar-row.total .tr i{background:repeating-linear-gradient(90deg,#B8860B 0 10px,#9a6f08 10px 20px)}
.bar-row.total .c{width:110px;font:800 15px 'SF Mono',Menlo;color:#151718}
"""


def render_poster_terra(terra, feat, nick, date_str, out_path, meta=None):
    m = terra["meta"]
    reg_name = {r["id"]: r["name"] for r in terra["regions"]}
    pct = m.get("pct") or 0
    # 名字 → char_id（头像用）；meta 缺失时退回无头像文字卡。
    # load_meta() 直接返回 {char_id: {...}}；容错包一层 "chars" 的原始 JSON 形状。
    cid_map = {}
    if meta:
        chars_meta = meta.get("chars") if isinstance(meta.get("chars"), dict) else meta
        cid_map = {v.get("name"): c for c, v in chars_meta.items()
                   if isinstance(v, dict) and v.get("name")}
    # 与档案页"差 1 名就全档案"面板同口径（含 0/1 的米诺斯），2×3 满排；
    # 2026-10-27 世界观审计：不再过滤 owned6==0 的地区，避免"5 地区"与面板 6 地区打架。
    near = (m.get("near") or [])[:6]
    near_html = "".join(
        _near_card(n["name"], n.get("missing") or ["?"], cid_map) for n in near)
    miss_total = max((m.get("sixTotal") or 0) - (m.get("sixOwned") or 0), 0)
    dims = feat.get("dims") or []
    score = feat.get("score")
    score_note = f"综合 {score}/100 · 内部启发式" if score is not None else "内部启发式"
    regs = [r for r in terra["regions"] if r.get("area") == "land" and r.get("total6")]
    regs = sorted(regs, key=lambda r: -r["total6"])[:4]
    bars = "".join(
        f'<div class="bar-row{" full" if r["owned6"] == r["total6"] else ""}">'
        f'<span class="n">{html.escape(r["name"])}</span>'
        f'<span class="tr"><i style="width:{(r["owned6"] / r["total6"] * 100):.1f}%"></i></span>'
        f'<span class="c">{r["owned6"]} / {r["total6"]}</span></div>'
        for r in regs)
    total_pct = (m.get("sixOwned") or 0) / max(m.get("sixTotal") or 1, 1) * 100
    total_bar = (f'<div class="bar-row total"><span class="n">泰拉总进度</span>'
                 f'<span class="tr"><i style="width:{total_pct:.1f}%"></i></span>'
                 f'<span class="c">{m["sixOwned"]} / {m["sixTotal"]}</span></div>')
    full_chips = "".join(
        f'<span class="fchip"><b>✓</b>{html.escape(reg_name.get(i, i))}</span>'
        for i in (m.get("fullIds") or []))
    tag_list = (feat.get("tags") or [])[:3]
    tag_cls = ["gold", "blue", "black"]
    tags = "".join(_tag(t, tag_cls[i]) for i, t in enumerate(tag_list))
    title = feat.get("title") or "泰拉图鉴"
    line = feat.get("titleLine") or ""
    tri = (
        '<svg width="22" height="26" viewBox="0 0 30 34"><path d="M15 1 L29 10 V24 L15 33 L1 24 V10 Z" '
        'fill="none" stroke="#151718" stroke-width="2"/>'
        '<path d="M15 8 L22 12.5 V21 L15 25.5 L8 21 V12.5 Z" fill="none" stroke="#151718" stroke-width="1.4"/></svg>'
        '<span>RHODES ISLAND</span>')

    page = f'''<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8"><style>{BASE_CSS}{EXTRA_CSS}</style></head>
<body>
<div class="grid"></div><div class="hazard"></div>
<div class="wrap">
  <div class="header">
    <div class="header-left">
      <div class="kicker"><span>ARKBOX // TERRA CODEX</span><span class="file">数据快照 {html.escape(date_str)}</span></div>
      <h1>泰拉图鉴 <b>/</b> 地区收集档案</h1>
      <div class="doctor"><span>DOCTOR <b>{html.escape(nick)}</b></span>
        <span class="chip">1 个六边形 = 1 名六星</span></div>
    </div>
    {_seal(date_str)}
  </div>

  <div class="title-zone">
    <div class="title">{html.escape(title)}</div>
    <div class="caption">{html.escape(line)}</div>
    <div class="tags">{tags}</div>
  </div>
  <div class="full-row">{full_chips}</div>

  {_section("01", "六星归档", f'{len(near)} 个地区各差 1 名 · {score_note} · 按游戏内 nationId（编制）归档')}
  <div class="terra-top">
    <div class="ring-box">{_ring(pct)}
      <div class="all-line">全干员持有 <b>{m["allOwned"]}/{m["allTotal"]}</b></div>
      <div class="miss-line">距全泰拉还差 <b>{miss_total}</b> 名</div>
    </div>
    <div class="near-grid">{near_html}</div>
  </div>
  {_dim_strip(dims)}
  <div class="pmap">{_map_svg(terra)}</div>

  {_section("02", "地区归档进度", "泰拉总进度 + 六星数前 4")}
  <div class="bars">{total_bar}{bars}</div>
  <div class="pity-note">口径：以游戏数据 nationId（所属编制）归档；nationId 为空的萨卡兹系干员按 groupId=babel（巴别塔）/ teamId=followers（使徒）归卡兹戴尔，临光归卡西米尔；罗德岛本舰单列，nationId 为空的联动干员归"非泰拉"；地图轮廓为程序化示意。</div>

  <div class="footer">
    <div class="foot-line">数据快照 {html.escape(date_str)} · 非官方玩家工具 · 数据本地 / 头像公开 CDN</div>
    <div class="foot-row">
      <div class="tri">{tri}</div>
      {_barcode(m.get("sixTotal", 7) * 7 + m.get("sixOwned", 0))}
      <div class="foot-r">GENERATED BY ARKBOX<br>{datetime.now().strftime("%Y.%m.%d %H:%M")} · TERRA CODEX</div>
    </div>
  </div>
</div>
</body></html>'''
    out_path = os.path.expanduser(out_path)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(page)
    return out_path
