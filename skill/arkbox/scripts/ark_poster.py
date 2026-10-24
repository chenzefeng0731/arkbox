#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""寻访档案竖版海报（1080×1440 · 3:4，P0 数据口径版）。

保持 B 版「档案白 + 青色信号」的视觉骨架：
- 浅灰网格纸、黑色斜切称号板、青蓝警示条、红色印章、条码落款
- 本版只改数据与文案：称号、口径、UID 隐私、池型/UP 命中、池间汇总
- 不重排版式；分享变体留到 P1

用法（一般由 ark_gacha.py --poster 调用）:
  python3 ark_poster.py --records gacha_records.json --out poster.html
纯标准库；截图出 PNG 用 Chrome headless。
"""

import argparse
import html
import json
import os
import random
from datetime import datetime

AVATAR_URL = "https://raw.githubusercontent.com/yuanyan3060/ArknightsGameResource/main/avatar/{cid}.png"
# 加载失败先换 jsdelivr 镜像（raw.githubusercontent.com 在部分网络不可达），再失败隐藏
AVATAR_ONERROR = (
    "if(!this.dataset.f){this.dataset.f=1;"
    "this.src=this.src.replace('raw.githubusercontent.com','cdn.jsdelivr.net/gh')"
    ".replace('/main/','@main/');}"
    "else{this.style.visibility='hidden'}"
)

W, H = 1080, 1440


def _barcode(seed, n=46, h=26):
    rng = random.Random(seed)
    bars = "".join(
        f'<i style="width:{rng.choice([2,2,3,4,6])}px;margin-right:{rng.choice([2,3,4])}px"></i>'
        for _ in range(n)
    )
    return f'<div class="barcode">{bars}</div>'


def _seal(date_str):
    return f'''<div class="seal"><div class="seal-in">
      <span class="s1">ARKBOX</span><span class="s2">档案生成日</span>
      <span class="s3">{html.escape(date_str)}</span></div></div>'''


def _tape(label, sub=""):
    return f'''<div class="tape-wrap">
      <div class="tape">{html.escape(label)}</div>
      {f'<div class="tape-sub">{html.escape(sub)}</div>' if sub else ''}
    </div>'''


def _short_name(name):
    name = str(name or "")
    return name[:2] if len(name) > 4 else name


def _up_mark(s, uv):
    if s.get("is_up") is True:
        return "UP"
    if s.get("is_up") is False:
        return "歪"
    if uv and not uv.get("known"):
        return "待核"
    return ""


def _pool_card(p):
    uv = p.get("up_verdict") or {"known": False}
    type_label = p.get("pool_type_label") or "池型待核"
    tcls = {"limited": "lim", "linkage": "mid", "special": "mid"}.get(p.get("pool_type"), "std")
    type_tag = f'<span class="ptag {tcls}">{html.escape(type_label)}</span>'

    if p.get("six_count") and uv.get("known"):
        hit, total = uv.get("hit_count", 0), uv.get("total", 0)
        up_cls = "ok" if hit == total else ("bad" if hit == 0 else "mid")
        up_tag = f'<span class="ptag {up_cls}">UP {hit}/{total}</span>'
    elif p.get("six_count"):
        up_tag = '<span class="ptag std">UP 待核</span>'
    else:
        up_tag = '<span class="ptag std">暂无六星</span>'

    chips = []
    for s in p["six_stars"][:6]:
        mark = _up_mark(s, uv)
        off = "off" if s.get("is_up") is False else ""
        note = f'第{s["at_pull"]}抽' + (f' · {mark}' if mark else '')
        chips.append(
            f'<div class="op {off}"><img src="{AVATAR_URL.format(cid=html.escape(s["char_id"] or ""))}" alt="" onerror="{AVATAR_ONERROR}">'
            f'<div class="nmbar">{html.escape(s["name"] or "?")}<small>{html.escape(note)}</small></div></div>'
        )

    gaps_html = ""
    if p["gaps"]:
        mx = max(p["gaps"])
        bars = "".join(
            f'<i style="height:{max(10, int(g / mx * 66))}px" class="{"g" if g <= 34 else ("b" if g <= 50 else "r")}" title="间隔 {g} 抽"></i>'
            for g in p["gaps"][:14]
        )
        gaps_html = f'<div class="gapchart">{bars}</div>'

    return f'''<div class="pool">
      <div class="phead"><span class="pname">{html.escape(p["pool"])}</span>{type_tag}{up_tag}
        <span class="pmeta">{p["total"]} 抽 · {p["six_count"]} 六星 · 均值 {p["avg_gap"] if p["avg_gap"] is not None else "—"} · 六星垫 {p.get("display_pity", p.get("current_pity", 0))}</span></div>
      <div class="oprow">{"".join(chips) or '<span class="none">暂无六星</span>'}</div>
      {gaps_html}
    </div>'''


# 主题 A=黄黑警示派（黑底）  B=档案白+青色信号派（白底）
THEMES = {
    "A": {
        "bg": "#0a0a0c", "grid": "rgba(255,255,255,.035)", "ink": "#ffffff",
        "dim": "rgba(255,255,255,.55)", "dim2": "rgba(255,255,255,.45)",
        "line": "rgba(255,255,255,.14)", "line2": "rgba(255,255,255,.15)",
        "sig": "#ffd800", "sig_soft": "rgba(255,216,0,.18)", "sig_ink": "#000000",
        "gold": "#ffcd5c", "bad": "#ff3b30",
        "numborder": "rgba(255,255,255,.14)", "corner": "rgba(255,255,255,.18)",
        "hazard": "repeating-linear-gradient(-45deg,#ffd800 0 22px,#0a0a0c 22px 44px)",
        "bad_soft": "rgba(255,59,48,.75)", "bad_soft2": "rgba(255,59,48,.5)",
        "tape": "background:#ffd800;color:#000;",
        "wm": "rgba(255,255,255,.028)", "bar": "rgba(255,255,255,.1)",
        "poolbg": "rgba(255,255,255,.025)", "barcode": "#ffffff",
        "stdbg": "rgba(255,255,255,.06)", "stdink": "rgba(255,255,255,.65)",
    },
    "B": {
        "bg": "#F4F4F1", "grid": "rgba(21,23,24,.055)", "ink": "#151718",
        "dim": "rgba(21,23,24,.62)", "dim2": "rgba(21,23,24,.48)",
        "line": "rgba(21,23,24,.22)", "line2": "rgba(21,23,24,.28)",
        "sig": "#0098DC", "sig_soft": "rgba(0,152,220,.14)", "sig_ink": "#ffffff",
        "gold": "#B8860B", "bad": "#C82A36",
        "numborder": "rgba(21,23,24,.3)", "corner": "rgba(21,23,24,.35)",
        "hazard": "linear-gradient(90deg,#151718 0 46%,#0098DC 46% 54%,#151718 54% 100%)",
        "bad_soft": "rgba(200,42,54,.8)", "bad_soft2": "rgba(200,42,54,.45)",
        "tape": "background:#151718;color:#fff;border-left:10px solid #0098DC;",
        "wm": "rgba(21,23,24,.05)", "bar": "rgba(21,23,24,.14)",
        "poolbg": "rgba(21,23,24,.028)", "barcode": "#151718",
        "stdbg": "rgba(21,23,24,.06)", "stdink": "rgba(21,23,24,.55)",
    },
}


def render_poster(report, out_path, theme="B"):
    """report 来自 ark_report.build_report；B 版走最新池优先的生产布局。"""
    if theme == "B":
        from ark_poster_v4 import render_poster_v4
        return render_poster_v4(report, report["pools"]["all"], out_path)
    T = THEMES.get(theme, THEMES["B"])
    metrics = report["metrics"]
    lines = report["lines"]
    title = report["title"]
    totals = report["totals"]
    luck = report["luck"]
    pools = report["pools"]["display"]
    perc = luck.get("better_than")
    perc_width = float(perc) if perc is not None else 0.0
    perc_text = f"{perc}%" if perc is not None else "—"
    mean_gap = metrics.get("mean_gap")
    worst_gap = metrics.get("max_gap") or 0
    worst_at = metrics.get("max_gap_at") or "—"
    worst_pool = metrics.get("max_gap_pool") or "—"
    date_str = report.get("generated") or datetime.now().strftime("%Y.%m.%d")
    nick = report["doctor"]["nick"]
    pools_html = "".join(_pool_card(p) for p in pools)
    other_line = report["pools"].get("other_line") or ""
    other_html = f'<div class="other">{html.escape(other_line)}</div>' if other_line else ""
    pity_items = metrics.get("current_pity_by_pool") or []
    pity_parts = [f"{_short_name(x['pool'])} {x['pity']}" for x in pity_items[:3]]
    if len(pity_items) > 3:
        pity_parts.append(f"等 {len(pity_items)} 池")
    pity_compact = ("六星垫抽 " + " / ".join(pity_parts) + "（各池独立）") if pity_parts else ""
    metric_compact = "—"
    if metrics.get("mean_gap") is not None:
        metric_compact = (f"池内 {metrics['mean_gap']} 抽/六星（{metrics['gap_count']} 段，按池独立）"
                          f" · 整体 {metrics['overall_efficiency']}（含未结算 {metrics['current_pity_total']}）"
                          " · 首段可能承接档案外垫抽")

    page = f'''<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8"><style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{W}px;height:{H}px;overflow:hidden}}
body{{background:{T['bg']};color:{T['ink']};font-family:-apple-system,'PingFang SC','Helvetica Neue',sans-serif;position:relative}}
.grid{{position:absolute;inset:0;background-image:linear-gradient({T['grid']} 1px,transparent 1px),linear-gradient(90deg,{T['grid']} 1px,transparent 1px);background-size:44px 44px}}
.wm{{position:absolute;right:20px;top:560px;font:900 120px 'Helvetica Neue';color:{T['wm']};letter-spacing:8px;writing-mode:vertical-rl;white-space:nowrap}}
.hazard{{position:absolute;top:0;left:0;right:0;height:14px;background:{T['hazard']}}}
.wrap{{position:relative;padding:52px 56px;height:100%;display:flex;flex-direction:column}}
.kicker{{display:flex;justify-content:space-between;align-items:center;font:700 15px 'SF Mono',Menlo,monospace;color:{T['sig']};letter-spacing:3px}}
.kicker .r{{color:{T['dim2']};font-size:13px}}
h1{{font-size:44px;font-weight:900;letter-spacing:2px;margin-top:14px}}
h1 b{{color:{T['sig']}}}
.sub{{margin-top:6px;font:500 17px Menlo,monospace;color:{T['dim']};letter-spacing:1px}}
.sub b{{color:{T['ink']}}}
.doctor{{display:flex;align-items:center;gap:14px;margin-top:18px}}
.doctor .tag{{background:#fff;color:#000;font-weight:900;font-size:17px;padding:4px 14px;clip-path:polygon(0 0,100% 0,100% calc(100% - 10px),calc(100% - 10px) 100%,0 100%)}}
.tape-zone{{position:relative;margin:24px 0 22px;height:128px}}
.tape{{display:inline-block;{T['tape']}font-size:56px;font-weight:900;padding:16px 48px 20px;transform:rotate(-2deg);clip-path:polygon(2% 8%,98% 0,100% 88%,0 100%);box-shadow:0 8px 24px {T['sig_soft']};letter-spacing:4px}}
.tape-sub{{margin-top:10px;color:{T['dim2']};font-size:15px;letter-spacing:1px;white-space:nowrap}}
.seal{{position:absolute;right:0;top:-8px;width:172px;height:172px;border:5px solid {T['bad_soft']};border-radius:50%;transform:rotate(12deg);display:flex;align-items:center;justify-content:center}}
.seal-in{{text-align:center;color:{T['bad_soft']};border:2px solid {T['bad_soft2']};border-radius:50%;width:148px;height:148px;display:flex;flex-direction:column;justify-content:center;gap:2px}}
.seal .s1{{font:900 16px 'SF Mono',Menlo;letter-spacing:2px}}
.seal .s2{{font-size:13px}}
.seal .s3{{font-size:15px;font-weight:700}}
.nums{{display:grid;grid-template-columns:1.2fr 1fr 1fr;gap:14px;margin-top:4px}}
.num{{border:1px solid {T['numborder']};padding:16px 18px 12px;position:relative;clip-path:polygon(0 0,calc(100% - 16px) 0,100% 16px,100% 100%,0 100%)}}
.num .v{{font:800 76px/1 'SF Mono',Menlo,monospace;letter-spacing:-2px}}
.num .v small{{font-size:22px;letter-spacing:0;color:{T['dim']}}}
.num.gold .v{{color:{T['gold']}}}
.num .k{{margin-top:8px;font-size:14px;color:{T['dim2']};letter-spacing:2px}}
.num .corner{{position:absolute;right:4px;bottom:4px;color:{T['corner']};font:700 11px 'SF Mono',Menlo}}
.perc{{margin:14px 0 20px;display:flex;align-items:center;gap:12px;font-size:15px;color:{T['dim']};letter-spacing:.5px}}
.perc b{{font:800 30px 'SF Mono',Menlo;color:{T['ink']}}}
.perc .bar{{flex:1;height:8px;background:{T['bar']};position:relative}}
.perc .bar i{{position:absolute;left:0;top:0;bottom:0;background:{T['sig']};width:{perc_width}%}}
.perc .bar u{{position:absolute;top:-4px;bottom:-4px;width:3px;background:{T['ink']};left:{perc_width}%}}
.pool{{border:1px solid {T['numborder']};padding:18px 20px;margin-bottom:16px;clip-path:polygon(0 0,calc(100% - 18px) 0,100% 18px,100% 100%,0 100%);background:{T['poolbg']}}}
.phead{{display:flex;align-items:center;gap:10px;flex-wrap:wrap}}
.pname{{font-size:20px;font-weight:800}}
.ptag{{font-size:12px;font-weight:800;padding:2px 9px;letter-spacing:1px}}
.ptag.lim{{background:{T['sig']};color:{T['sig_ink']}}}
.ptag.ok{{background:{T['gold']};color:{T['sig_ink']}}}
.ptag.mid{{background:#fff;color:#000}}
.ptag.bad{{background:{T['bad']};color:#fff}}
.ptag.std{{background:{T['stdbg']};color:{T['stdink']}}}
.pmeta{{margin-left:auto;color:{T['dim2']};font-size:13px;font-family:'SF Mono',Menlo}}
.oprow{{display:flex;gap:10px;margin-top:12px;flex-wrap:wrap}}
.op{{width:72px;position:relative}}
.op img{{width:72px;height:72px;object-fit:cover;display:block;filter:grayscale(.15)}}
.op .nmbar{{background:#000;border:1px solid {T['line']};font-size:10.5px;text-align:center;padding:2px 0;margin-top:-1px;white-space:nowrap;overflow:hidden}}
.op .nmbar small{{display:block;color:rgba(255,255,255,.55);font-size:9px}}
.op.off img{{outline:2px solid {T['bad']};outline-offset:-2px}}
.op.off .nmbar{{border-color:{T['bad']};color:{T['bad']}}}
.none{{color:{T['dim2']};font-size:14px}}
.gapchart{{display:flex;align-items:flex-end;gap:6px;margin-top:12px;height:68px;border-bottom:1px solid {T['line2']};padding-bottom:0}}
.gapchart i{{width:16px;background:{T['gold']};display:block}}
.gapchart i.b{{background:{T['ink']}}}
.gapchart i.r{{background:{T['bad']}}}
.other{{margin:-4px 0 12px;color:{T['dim2']};font-size:13px;letter-spacing:.5px}}
.worst{{margin-top:16px;background:{T['sig']};color:{T['sig_ink']};display:flex;align-items:center;gap:16px;padding:14px 20px;font-size:19px;clip-path:polygon(0 0,100% 0,100% calc(100% - 14px),calc(100% - 14px) 100%,0 100%)}}
.worst b{{font-size:30px;font-weight:900;letter-spacing:1px}}
.worst .wk{{font-weight:800}}
.worst .wk2{{margin-left:auto;font:700 12px 'SF Mono',Menlo;letter-spacing:1px;opacity:.7}}
.dline{{margin-top:10px;font-size:12px;color:{T['dim2']};letter-spacing:.3px;line-height:1.5}}
.dline2{{font-size:12px;color:{T['dim2']};letter-spacing:.3px;line-height:1.5}}
.footer{{margin-top:auto;display:flex;align-items:flex-end;justify-content:space-between;border-top:1px solid {T['line2']};padding-top:14px}}
.tri{{display:flex;align-items:center;gap:12px;color:{T['dim2']};font-size:13px;letter-spacing:2px}}
.tri svg{{opacity:.85}}
.barcode{{display:flex;align-items:flex-end;height:26px}}
.barcode i{{background:{T['barcode']};height:100%;display:block}}
.foot-r{{text-align:right;color:{T['dim2']};font:500 12px 'SF Mono',Menlo;letter-spacing:1px}}
</style></head><body>
<div class="grid"></div><div class="wm">RHODES</div><div class="hazard"></div>
<div class="wrap">
  <div class="kicker"><span>ARKBOX // GACHA REPORT</span><span class="r">FILE NO. R-{totals['pulls'] % 1000:03d}</span></div>
  <h1>寻访档案 <b>/</b> 欧非鉴定</h1>
  <div class="sub">DOCTOR <b>{html.escape(nick)}</b></div>
  <div class="tape-zone">
    {_tape(title['label'], title['caption'])}
    {_seal(date_str)}
  </div>
  <div class="nums">
    <div class="num gold"><div class="v">{totals['pulls']}</div><div class="k">本区间抽数</div><div class="corner">PULLS</div></div>
    <div class="num"><div class="v">{totals['six']}</div><div class="k">六星干员</div><div class="corner">6★</div></div>
    <div class="num"><div class="v">{mean_gap if mean_gap is not None else '—'}<small> 抽</small></div><div class="k">池内均值/六星</div><div class="corner">AVG</div></div>
  </div>
  <div class="perc"><span>理论评估</span><b>{perc_text}</b><div class="bar"><i></i><u></u></div><span>优于约 {perc_text} 同段数样本 · 理论模型 · 非全服排名</span></div>
  {pools_html}
  {other_html}
  <div class="worst"><span class="wk">最长池内间隔</span><b>{worst_gap} 抽</b><span class="wk2">第 {worst_at} 抽出货 · {html.escape(worst_pool)}</span></div>
  <div class="dline">口径：{html.escape(metric_compact)}</div>
  <div class="dline2">{html.escape(pity_compact)}{(" · " + html.escape(lines['up'])) if lines.get('up') else ""}</div>
  <div class="dline2">范围：{html.escape(report['coverage']['short'])} · {html.escape(report['model']['caption'])} · 六星硬保底 99 · 非官方玩家工具 · 数据本地/头像 CDN</div>
  <div class="footer">
    <div class="tri">
      <svg width="30" height="34" viewBox="0 0 30 34"><path d="M15 1 L29 10 V24 L15 33 L1 24 V10 Z" fill="none" stroke="{T['ink']}" stroke-width="2"/><path d="M15 8 L22 12.5 V21 L15 25.5 L8 21 V12.5 Z" fill="none" stroke="{T['ink']}" stroke-width="1.4"/></svg>
      <span>RHODES ISLAND</span>
    </div>
    {_barcode(report['privacy']['barcode_seed'])}
    <div class="foot-r">GENERATED BY ARKBOX<br>{datetime.now().strftime("%Y.%m.%d %H:%M")} · DATA LOCAL · AVATAR CDN</div>
  </div>
</div>
</body></html>'''

    out_path = os.path.expanduser(out_path)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(page)
    return out_path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", required=True, help="fetch 保存的原始记录 json")
    ap.add_argument("--out", default="poster.html")
    ap.add_argument("--nick", default="博士")
    ap.add_argument("--theme", choices=("A", "B"), default="B")
    ap.add_argument("--hide-nick", action="store_true")
    a = ap.parse_args()
    from ark_gacha import analyze_records
    from ark_pools import PoolUpIndex
    from ark_archive import coverage_report
    from ark_domains import build_pool_stats, apply_pool_meta
    from ark_report import build_report
    recs = json.load(open(a.records, encoding="utf-8"))
    idx = PoolUpIndex()
    stats, _ = analyze_records(recs, idx)
    pool_data = build_pool_stats(recs, idx)
    apply_pool_meta(stats, pool_data)
    cov = coverage_report(recs)
    report = build_report(stats, a.nick, cov, hide_nick=a.hide_nick, domain=pool_data)
    print(render_poster(report, a.out, theme=a.theme))
