#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P1-A demo：手机单列版寻访档案海报（1080×1440，保留档案皮肤）。

这不是默认 --poster，只用于让泽峰看版式方向。数据仍来自 ark_report.build_report。
设计目标：
- 单列全宽，不再有右侧大空场
- 结论 + 2×2 四数 + 标签 → 当前垫抽 → 全宽池卡 → 其他池 → 最快/最长
- 池卡：主角头像 + 事件排 + 本池结论 + 全宽出货时间轴
- 字体按 360px 反推，池名/核心数字优先
"""

import html
import os
import random
import sys
from collections import Counter
from datetime import datetime

AVATAR_URL = "https://raw.githubusercontent.com/yuanyan3060/ArknightsGameResource/main/avatar/{cid}.png"
W, H = 1080, 1440

INK = "#151718"
DIM = "rgba(21,23,24,.62)"
DIM2 = "rgba(21,23,24,.45)"
LINE = "rgba(21,23,24,.18)"
BLUE = "#0098DC"
GOLD = "#B8860B"
RED = "#C82A36"
BG = "#F4F4F1"


def _barcode(seed, n=44):
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


def _tag(text, cls=""):
    return f'<span class="tag {cls}">{html.escape(text)}</span>'


def _next_rate(pity):
    if pity >= 99:
        return 100
    if pity < 50:
        return 2
    return min(100, 2 + 2 * (pity - 49))


def _section(num, title):
    return f'''<div class="section"><span class="num">{num}</span>
      <span class="t">{html.escape(title)}</span><span class="line"></span></div>'''


def _stat(value, label, sub="", cls=""):
    return f'''<div class="stat {cls}"><div class="v">{value}</div>
      <div class="l">{html.escape(label)}</div>
      {f'<div class="s">{html.escape(sub)}</div>' if sub else ''}</div>'''


def _op(s, hero=False, dup=0):
    is_up = s.get("is_up")
    badge = ""
    if is_up is False:
        badge = '<span class="badge">歪</span>'
    elif dup > 1:
        badge = f'<span class="dup">×{dup}</span>'
    mark = "UP" if is_up is True else ("歪" if is_up is False else "待核")
    return f'''<div class="op {'hero' if hero else ''} {'off' if is_up is False else ''}">
      <img src="{AVATAR_URL.format(cid=html.escape(s['char_id'] or ''))}" alt="">
      {badge}
      <div class="nm">{html.escape(s['name'] or '?')}</div>
      <div class="pull">第{s['at_pull']}抽 · {mark}</div>
    </div>'''


def _timeline(p):
    total = max(int(p["total"]), 1)
    prev = 0
    segs, dots, labels = [], [], []
    max_gap, max_start, max_end = 0, 0, 0
    for s in p["six_stars"]:
        at = s["at_pull"]
        gap = at - prev
        cls = "g" if gap <= 34 else ("m" if gap <= 50 else "r")
        if gap > 0:
            segs.append((prev, gap, cls))
        dots.append(at)
        if gap > max_gap:
            max_gap, max_start, max_end = gap, prev, at
        prev = at
    current = total - prev
    if current > 0:
        segs.append((prev, current, "p"))
    seg_html = "".join(
        f'<i class="seg {cls}" style="left:{start / total * 100:.3f}%;width:{gap / total * 100:.3f}%"></i>'
        for start, gap, cls in segs
    )
    dot_html = "".join(
        f'<i class="dot" style="left:{at / total * 100:.3f}%"></i>' for at in dots
    )
    if max_gap >= 50:
        labels.append((max_start + max_gap / 2, f"{max_gap} 抽", "r"))
    if current > 0:
        labels.append((prev + current / 2, f"垫 {current}", "b"))
    label_html = "".join(
        f'<span class="tl-label {cls}" style="left:{pos / total * 100:.3f}%">{html.escape(text)}</span>'
        for pos, text, cls in labels
    )
    return f'''<div class="tl">
      <div class="tl-track">{seg_html}{dot_html}{label_html}</div>
      <div class="tl-ends"><span>0</span><span>{total} 抽</span></div>
      <div class="legend"><span><i class="g"></i>≤34</span><span><i class="m"></i>35–50</span>
        <span><i class="r"></i>&gt;50</span><span><i class="p"></i>当前垫</span></div>
    </div>'''


def _pool_card(p):
    uv = p.get("up_verdict") or {"known": False}
    type_label = p.get("pool_type_label") or "池型待核"
    type_cls = {"limited": "lim", "linkage": "mid", "special": "mid"}.get(p.get("pool_type"), "std")
    if p.get("six_count") and uv.get("known"):
        hit, total = uv.get("hit_count", 0), uv.get("total", 0)
        up_cls = "ok" if hit == total else ("bad" if hit == 0 else "mid")
        up_tag = f'<span class="ptag {up_cls}">UP {hit}/{total}</span>'
    elif p.get("six_count"):
        up_tag = '<span class="ptag std">UP 待核</span>'
    else:
        up_tag = '<span class="ptag std">暂无六星</span>'

    six = p["six_stars"]
    dup_counts = Counter(s["char_id"] for s in six)
    # 主角：优先 UP，其次重复次数，其次最早；车辙会是珊比×3，石白是结城理
    hero = max(
        six,
        key=lambda s: (bool(s.get("is_up")), dup_counts.get(s["char_id"], 0), -s["at_pull"]),
    ) if six else None
    others = [s for s in six if s is not hero][:5]
    ops = ""
    if hero:
        ops += _op(hero, hero=True, dup=dup_counts.get(hero["char_id"], 0))
    ops += "".join(_op(s, dup=dup_counts.get(s["char_id"], 0)) for s in others)

    non_up = (p["six_count"] - uv.get("hit_count", 0)) if uv.get("known") else None
    mini = f'''<div class="mini-grid">
      <div class="mini"><b>{p['avg_gap'] if p['avg_gap'] is not None else '—'}</b><span>均值</span></div>
      <div class="mini"><b class="{"red" if (p['worst_gap'] or 0) >= 50 else ''}">{p['worst_gap'] if p['worst_gap'] is not None else '—'}</b><span>最长</span></div>
      <div class="mini"><b class="blue">{p['since_last_six']}</b><span>当前垫</span></div>
      <div class="mini"><b>{non_up if non_up is not None else '—'}</b><span>非 UP</span></div>
    </div>'''

    callout = ""
    if p["six_count"] > 2:
        if dup_counts:
            top = max(dup_counts.items(), key=lambda kv: (kv[1], kv[0]))
            cid, count = top
            if count >= 2:
                name = next((s["name"] for s in six if s["char_id"] == cid), "?")
                up_txt = f'本池 UP {uv.get("hit_count", 0)}/{uv.get("total", 0)}' if uv.get("known") else "UP 待核"
                callout = f'''<div class="char-callout">
                  <div class="big">{html.escape(name or "?")} ×{count}</div>
                  <div class="txt">三顾茅庐 · {html.escape(up_txt)}</div>
                </div>'''
    elif p.get("worst_gap") and p["worst_gap"] >= 50:
        # 找该池最长间隔的结束六星
        prev, best = 0, None
        for s in six:
            gap = s["at_pull"] - prev
            if gap == p["worst_gap"]:
                best = (prev + 1, s["at_pull"], s["name"])
                break
            prev = s["at_pull"]
        if best:
            start, end, name = best
            callout = f'''<div class="callout">
              <div class="big">{p['worst_gap']} 抽</div>
              <div class="txt">第 {start}~{end} 抽未见六星<br>第 {end} 抽才出 {html.escape(name or '')}</div>
            </div>'''

    return f'''<div class="pool">
      <div class="pool-head">
        <span class="pool-name">{html.escape(p["pool"])}</span>
        <span class="ptag {type_cls}">{html.escape(type_label)}</span>
        {up_tag}
        <div class="pool-head-right"><span class="pool-total">{p["total"]}<small> 抽</small></span>
          <span class="pool-total">{p["six_count"]}<small> 六星</small></span></div>
      </div>
      <div class="pool-sub">{p["first_ts"]} ~ {p["last_ts"]}</div>
      <div class="pool-body">
        <div class="ops">{ops}</div>
        <div class="hero-panel">{callout}{mini}</div>
      </div>
      {_timeline(p)}
    </div>'''


def _pity_rows(report):
    rows = []
    for x in report["metrics"].get("current_pity_by_pool") or []:
        pity = x["pity"]
        rate = _next_rate(pity)
        rows.append(f'''<div class="pity-row">
          <div class="pity-name">{html.escape(x["pool"])}</div>
          <div class="pity-track"><i class="pity-fill" style="width:{min(pity / 99 * 100, 100):.2f}%"></i></div>
          <div class="pity-num">{pity}/99 · 下抽 {rate:g}%</div>
        </div>''')
    return "".join(rows)


def _other_row(report, stats):
    other = (report["pools"].get("other") or [])
    if not other:
        return ""
    o = other[0]
    full = next((p for p in stats if p["pool"] == o["pool"]), None)
    ops = ""
    if full:
        for s in full["six_stars"][:2]:
            ops += f'''<div class="op small"><img src="{AVATAR_URL.format(cid=html.escape(s['char_id'] or ''))}" alt="">
              <div class="nm">{html.escape(s['name'] or '?')}</div></div>'''
    best = ""
    if full and full["six_stars"]:
        best = f'第{full["six_stars"][0]["at_pull"]}抽 {html.escape(full["six_stars"][0]["name"] or "")}'
    return f'''<div class="other">
      <div class="other-l"><span class="other-k">其他池</span>
        <span class="other-name">{html.escape(o["pool"])}</span>
        <span class="ptag std">{html.escape(o["pool_type_label"])}</span>
        <span class="ptag ok">UP {o["up_hits"]}/{o["up_total"]}</span></div>
      <div class="other-m">{o["total"]} 抽 · {o["six_count"]} 六星 · {html.escape(best)}</div>
      <div class="other-r">{ops}<span class="other-tag">双金</span></div>
    </div>'''


def _title_tags(report):
    tags = []
    kind = report["title"].get("kind")
    label = report["title"]["label"]
    if kind and kind.startswith("ten_pull"):
        tags.append((label.split("还债")[0] if "还债" in label else label, "gold"))
    if kind == "ten_pull_debt":
        tags.append(("还债", "black"))
    if report["metrics"].get("max_duplicate", 0) >= 3:
        d = report["metrics"]["duplicates"][0]
        tags.append((f"三顾茅庐 · {d['name']}×{d['count']}", "blue"))
    if report["metrics"].get("up_total"):
        tags.append((f"UP {report['metrics']['up_hits']}/{report['metrics']['up_total']}", "blue"))
    # 最多 4 个，避免拥挤
    return "".join(_tag(t, c) for t, c in tags[:4])


def render_poster_v2(report, stats, out_path):
    m = report["metrics"]
    t = report["title"]
    luck = report["luck"]
    totals = report["totals"]
    worst = m.get("max_gap") or 0
    worst_at = m.get("max_gap_at") or "—"
    worst_pool = m.get("max_gap_pool") or "—"
    best = m.get("best_gap") or 0
    best_at = m.get("best_gap_at") or "—"
    best_pool = m.get("best_gap_pool") or "—"
    best_name = m.get("best_gap_name") or ""
    date_str = report.get("generated") or datetime.now().strftime("%Y.%m.%d")

    stats_html = (
        _stat(totals["pulls"], "累计寻访", f'{totals["pools"]} 池', "gold")
        + _stat(totals["six"], "六星干员", "全档案")
        + _stat(m["mean_gap"] if m["mean_gap"] is not None else "—", "已结算均值/六星",
                f'{m["gap_count"]} 段')
        + _stat(f'{luck["better_than"]}%' if luck["better_than"] is not None else "—",
                "理论位置", "优于同段数样本", "blue")
    )
    pools_html = "".join(_pool_card(p) for p in report["pools"]["display"])
    banner = f'''<div class="banner">
      <span class="banner-k">最长已结束间隔</span>
      <span class="banner-v">{worst} 抽</span>
      <span class="banner-x">第 {worst_at} 抽出 {html.escape(m.get("max_gap_name") or "")} · {html.escape(worst_pool)}</span>
      <span class="banner-r">最快 {best} 抽 · {html.escape(best_name)} · {html.escape(best_pool)}</span>
    </div>'''
    pity_numbers = " / ".join(str(x["pity"]) for x in m.get("current_pity_by_pool") or [])
    closing = f'''<div class="closing">
      <div class="closing-k">档案注</div>
      <div class="closing-line">口径：池内 {m["mean_gap"]} 抽/六星（{m["gap_count"]} 段） · 整体 {m["overall_efficiency"]} 抽/六星（含垫抽 {m["current_pity_total"]}） · 当前垫 {pity_numbers} 各池独立</div>
      <div class="closing-line">模型：2% 基础 / 50 抽未出后每抽 +2% / 99 抽必出 · 非全服排名 · 非官方玩家工具</div>
      <div class="closing-line">范围：{html.escape(report["coverage"]["short"])}</div>
    </div>'''

    page = f'''<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8"><style>{CSS}</style></head>
<body>
<div class="grid"></div><div class="hazard"></div>
<div class="wrap">
  <div class="header">
    <div class="header-left">
      <div class="kicker"><span>ARKBOX // GACHA REPORT</span><span class="file">FILE NO. R-{totals['pulls'] % 1000:03d}</span></div>
      <h1>寻访档案 <b>/</b> 欧非鉴定</h1>
      <div class="doctor"><span>DOCTOR <b>{html.escape(report["doctor"]["nick"])}</b></span>
        <span>· UID {html.escape(report["doctor"]["uid"])}</span>
        <span class="chip">本档案区间 · {html.escape(report["coverage"].get("earliest") or "")} ~ {html.escape(report["coverage"].get("latest") or "")}</span>
      </div>
    </div>
    {_seal(date_str)}
  </div>

  <div class="title-zone">
    <div class="title-box">
      <div class="title">{html.escape(t["label"])}</div>
      <div class="caption">{html.escape(t["caption"])}</div>
      <div class="tags">{_title_tags(report)}</div>
    </div>
  </div>

  {_section("01", "抽卡总结")}
  <div class="stats">{stats_html}</div>
  <div class="overall">整体 {m["overall_efficiency"]} 抽/六星（含当前垫抽 {m["current_pity_total"]}） · 理论期望 {luck["expected_gap"]} 抽/六星 · 档案区间 {totals["pools"]} 池</div>

  {_section("02", "当前垫抽")}
  <div class="pity">{_pity_rows(report)}
    <div class="pity-note">各池独立计数，不能相加为一次连续；99 抽硬保底。</div>
  </div>

  {_section("03", "重点卡池")}
  {pools_html}
  {_other_row(report, stats)}

  {banner}
  {closing}

  <div class="footer">
    <div class="foot-line">ARKBOX 本地生成 · 数据仅存本地 · 头像来自公开 CDN</div>
    <div class="foot-row">
      <div class="tri"><svg width="24" height="28" viewBox="0 0 30 34"><path d="M15 1 L29 10 V24 L15 33 L1 24 V10 Z" fill="none" stroke="{INK}" stroke-width="2"/><path d="M15 8 L22 12.5 V21 L15 25.5 L8 21 V12.5 Z" fill="none" stroke="{INK}" stroke-width="1.4"/></svg><span>RHODES ISLAND</span></div>
      {_barcode(report["privacy"]["barcode_seed"])}
      <div class="foot-r">GENERATED BY ARKBOX<br>{datetime.now().strftime("%Y.%m.%d %H:%M")} · DATA LOCAL ONLY</div>
    </div>
  </div>
</div>
</body></html>'''
    out_path = os.path.expanduser(out_path)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(page)
    return out_path


CSS = """
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1080px;height:1440px;overflow:hidden}
body{background:#F4F4F1;color:#151718;font-family:-apple-system,'PingFang SC','Helvetica Neue',sans-serif;position:relative}
.grid{position:absolute;inset:0;background-image:linear-gradient(rgba(21,23,24,.055) 1px,transparent 1px),linear-gradient(90deg,rgba(21,23,24,.055) 1px,transparent 1px);background-size:44px 44px}
.hazard{position:absolute;top:0;left:0;right:0;height:13px;background:linear-gradient(90deg,#151718 0 46%,#0098DC 46% 54%,#151718 54% 100%)}
.wrap{position:relative;padding:38px 48px 26px;height:100%;display:flex;flex-direction:column}
.header{display:flex;justify-content:space-between;align-items:flex-start;gap:18px}
.header-left{min-width:0;flex:1}
.kicker{display:flex;justify-content:space-between;align-items:center;font:700 12px 'SF Mono',Menlo,monospace;color:#0098DC;letter-spacing:2px}
.kicker .file{color:rgba(21,23,24,.45);font-size:11px;letter-spacing:1px}
h1{font-size:34px;font-weight:900;letter-spacing:1px;margin-top:7px}
h1 b{color:#0098DC}
.doctor{margin-top:5px;font:500 13px 'SF Mono',Menlo;color:rgba(21,23,24,.62);display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.doctor b{color:#151718}
.chip{font:700 10px 'SF Mono',Menlo;color:#0098DC;border:1px solid rgba(0,152,220,.4);padding:2px 7px;letter-spacing:.3px}
.seal{width:104px;height:104px;border:4px solid rgba(200,42,54,.8);border-radius:50%;transform:rotate(10deg);display:flex;align-items:center;justify-content:center;flex:0 0 auto;margin-top:2px}
.seal-in{text-align:center;color:rgba(200,42,54,.85);border:2px solid rgba(200,42,54,.45);border-radius:50%;width:86px;height:86px;display:flex;flex-direction:column;justify-content:center;gap:1px}
.seal .s1{font:900 11px 'SF Mono',Menlo;letter-spacing:1px}
.seal .s2{font-size:9px}
.seal .s3{font-size:10px;font-weight:700}
.title-zone{margin-top:14px}
.title{display:inline-block;background:#151718;color:#fff;border-left:10px solid #0098DC;font-size:46px;font-weight:900;padding:8px 30px 13px;transform:rotate(-1.5deg);clip-path:polygon(2% 8%,98% 0,100% 88%,0 100%);letter-spacing:3px;box-shadow:0 6px 18px rgba(0,152,220,.12)}
.caption{margin-top:7px;font-size:14px;color:rgba(21,23,24,.62);letter-spacing:.3px}
.tags{display:flex;gap:7px;margin-top:8px;flex-wrap:wrap}
.tag{font:800 11px -apple-system,'PingFang SC';padding:3px 9px;border:1px solid rgba(21,23,24,.2);letter-spacing:.5px}
.tag.gold{color:#B8860B;border-color:rgba(184,134,11,.5);background:rgba(184,134,11,.06)}
.tag.black{background:#151718;color:#fff;border-color:#151718}
.tag.blue{color:#0098DC;border-color:rgba(0,152,220,.45);background:rgba(0,152,220,.05)}
.section{display:flex;align-items:center;gap:9px;margin:15px 0 7px}
.section .num{font:700 10px 'SF Mono',Menlo;color:#0098DC;letter-spacing:1px}
.section .t{font-size:16px;font-weight:900;letter-spacing:1px}
.section .line{flex:1;height:1px;background:rgba(21,23,24,.18)}
.stats{display:grid;grid-template-columns:1fr 1fr;gap:9px}
.stat{background:rgba(255,255,255,.55);border:1px solid rgba(21,23,24,.22);padding:10px 14px 9px;clip-path:polygon(0 0,calc(100% - 12px) 0,100% 12px,100% 100%,0 100%)}
.stat .v{font:800 42px/1 'SF Mono',Menlo,monospace;letter-spacing:-1px}
.stat .l{font-size:15px;font-weight:700;color:rgba(21,23,24,.8);margin-top:4px}
.stat .s{font:500 10px 'SF Mono',Menlo;color:rgba(21,23,24,.45);margin-top:2px}
.stat.gold .v{color:#B8860B}
.stat.blue .v{color:#0098DC}
.overall{font:500 10.5px 'SF Mono',Menlo;color:rgba(21,23,24,.45);margin-top:6px}
.pity{padding:2px 0}
.pity-row{display:grid;grid-template-columns:210px 1fr 128px;gap:10px;align-items:center;margin:6px 0}
.pity-name{font-size:13px;font-weight:700;color:rgba(21,23,24,.8);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pity-track{height:8px;background:rgba(21,23,24,.08);border:1px solid rgba(21,23,24,.16);position:relative}
.pity-fill{position:absolute;left:0;top:0;bottom:0;background:#0098DC}
.pity-num{font:700 10px 'SF Mono',Menlo;color:rgba(21,23,24,.55);text-align:right;white-space:nowrap}
.pity-note{font-size:10px;color:rgba(21,23,24,.45);margin-top:3px}
.pool{background:rgba(255,255,255,.55);border:1px solid rgba(21,23,24,.22);padding:12px 14px 10px;margin-bottom:9px;clip-path:polygon(0 0,calc(100% - 14px) 0,100% 14px,100% 100%,0 100%)}
.pool-head{display:flex;align-items:center;gap:7px;flex-wrap:wrap}
.pool-name{font-size:23px;font-weight:900;letter-spacing:.5px}
.ptag{font:800 9px -apple-system,'PingFang SC';padding:2px 6px;letter-spacing:.5px;border:1px solid transparent}
.ptag.lim{background:#0098DC;color:#fff}
.ptag.mid{background:#fff;color:#151718;border-color:rgba(21,23,24,.2)}
.ptag.ok{background:#B8860B;color:#fff}
.ptag.bad{background:#C82A36;color:#fff}
.ptag.std{background:rgba(21,23,24,.06);color:rgba(21,23,24,.55);border-color:rgba(21,23,24,.18)}
.pool-head-right{margin-left:auto;display:flex;gap:12px;align-items:baseline}
.pool-total{font:800 21px 'SF Mono',Menlo;letter-spacing:-.5px}
.pool-total small{font-size:9px;color:rgba(21,23,24,.45);letter-spacing:0}
.pool-sub{font:500 9.5px 'SF Mono',Menlo;color:rgba(21,23,24,.45);margin-top:2px}
.pool-body{display:flex;gap:10px;align-items:flex-start;margin-top:8px}
.ops{display:flex;gap:7px;flex:0 0 auto}
.op{position:relative;width:86px}
.op.hero{width:118px}
.op.small{width:42px}
.op img{width:100%;aspect-ratio:1;object-fit:cover;display:block;border:1px solid rgba(21,23,24,.18);filter:grayscale(.06)}
.op.hero img{outline:2px solid #B8860B;outline-offset:-2px}
.op.off img{outline:2px solid #C82A36;outline-offset:-2px}
.op .nm{background:#000;color:#fff;font:700 10px -apple-system,'PingFang SC';text-align:center;padding:2px 1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.op.hero .nm{font-size:13px}
.op .pull{font:500 8px 'SF Mono',Menlo;color:rgba(21,23,24,.5);text-align:center;margin-top:1px;white-space:nowrap}
.op .badge{position:absolute;top:2px;left:2px;background:#C82A36;color:#fff;font:800 8px -apple-system;padding:1px 3px}
.op .dup{position:absolute;top:2px;right:2px;background:#B8860B;color:#fff;font:800 8px 'SF Mono',Menlo;padding:1px 3px}
.hero-panel{flex:1;min-width:0;display:flex;gap:8px;justify-content:flex-end;align-items:stretch}
.callout{flex:1;border:1px dashed rgba(200,42,54,.6);background:rgba(200,42,54,.05);padding:7px 9px;min-width:0}
.callout .big{font:800 25px 'SF Mono',Menlo;color:#C82A36;letter-spacing:-1px}
.callout .txt{font-size:9.5px;color:rgba(21,23,24,.6);line-height:1.4;margin-top:1px}
.mini-grid{width:236px;display:grid;grid-template-columns:1fr 1fr;gap:4px;background:rgba(21,23,24,.035);border:1px solid rgba(21,23,24,.14);padding:6px}
.mini{padding:2px 3px}
.mini b{display:block;font:800 17px 'SF Mono',Menlo;letter-spacing:-.5px}
.mini b.red{color:#C82A36}
.mini b.blue{color:#0098DC}
.mini span{font:500 8px -apple-system,'PingFang SC';color:rgba(21,23,24,.5)}
.tl{margin-top:8px}
.tl-track{position:relative;height:9px;background:rgba(21,23,24,.07);border:1px solid rgba(21,23,24,.15);margin-top:10px}
.seg{position:absolute;top:0;height:100%;display:block}
.seg.g{background:#0098DC}
.seg.m{background:#B8860B}
.seg.r{background:#C82A36}
.seg.p{background:repeating-linear-gradient(45deg,rgba(21,23,24,.35) 0 3px,rgba(21,23,24,.08) 3px 6px)}
.dot{position:absolute;top:-4px;width:2px;height:17px;background:#151718}
.tl-label{position:absolute;top:-16px;transform:translateX(-50%);font:800 9px 'SF Mono',Menlo;white-space:nowrap}
.tl-label.r{color:#C82A36}
.tl-label.b{color:#0098DC}
.tl-ends{display:flex;justify-content:space-between;font:500 8px 'SF Mono',Menlo;color:rgba(21,23,24,.4);margin-top:2px}
.legend{display:flex;gap:11px;font:500 8px 'SF Mono',Menlo;color:rgba(21,23,24,.45);margin-top:3px}
.legend i{display:inline-block;width:7px;height:7px;margin-right:3px;vertical-align:-1px}
.legend i.g{background:#0098DC}.legend i.m{background:#B8860B}.legend i.r{background:#C82A36}.legend i.p{background:repeating-linear-gradient(45deg,rgba(21,23,24,.35) 0 2px,rgba(21,23,24,.08) 2px 4px)}
.other{display:flex;align-items:center;gap:10px;border:1px dashed rgba(21,23,24,.25);padding:7px 10px;background:rgba(255,255,255,.35);margin-bottom:8px}
.other-l{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.other-k{font:800 9px 'SF Mono',Menlo;color:#0098DC;letter-spacing:1px}
.other-name{font-size:14px;font-weight:900}
.other-m{font:600 9.5px 'SF Mono',Menlo;color:rgba(21,23,24,.55)}
.other-r{margin-left:auto;display:flex;align-items:center;gap:5px}
.other-tag{font:800 9px -apple-system;background:#B8860B;color:#fff;padding:2px 6px}
.banner{background:#0098DC;color:#fff;display:flex;align-items:center;gap:9px;padding:10px 14px;clip-path:polygon(0 0,100% 0,100% calc(100% - 10px),calc(100% - 10px) 100%,0 100%);margin-top:2px}
.banner-k{font-size:14px;font-weight:800}
.banner-v{font:900 24px 'SF Mono',Menlo;letter-spacing:-.5px}
.banner-x{font-size:10px;opacity:.85}
.banner-r{margin-left:auto;font:700 9px 'SF Mono',Menlo;opacity:.9;text-align:right}
.footer{margin-top:auto;padding-top:10px;border-top:1px solid rgba(21,23,24,.2)}
.foot-line{font:500 9px 'SF Mono',Menlo;color:rgba(21,23,24,.42);line-height:1.5}
.foot-row{display:flex;align-items:flex-end;justify-content:space-between;margin-top:5px}
.tri{display:flex;align-items:center;gap:7px;font:700 9px 'SF Mono',Menlo;color:rgba(21,23,24,.45);letter-spacing:1px}
.barcode{display:flex;align-items:flex-end;height:18px}
.barcode i{background:#151718;height:100%;display:block}
.foot-r{text-align:right;font:500 8px 'SF Mono',Menlo;color:rgba(21,23,24,.4);letter-spacing:.5px}

/* P1-A tight tuning: 先保证 1440 内完整，再按 360 可读性调大关键项 */
.wrap{padding:30px 48px 18px}
h1{font-size:30px;margin-top:5px}
.doctor{font-size:12px;margin-top:4px}
.chip{font-size:9.5px;padding:2px 6px}
.seal{width:92px;height:92px;border-width:3px}
.seal-in{width:76px;height:76px}
.seal .s1{font-size:10px}
.seal .s2{font-size:8px}
.seal .s3{font-size:9px}
.title-zone{margin-top:10px}
.title{font-size:42px;padding:6px 26px 9px;border-left-width:8px;letter-spacing:2px}
.caption{font-size:13px;margin-top:6px}
.tags{margin-top:6px;gap:6px}
.tag{font-size:10.5px;padding:2px 8px}
.section{margin:10px 0 6px}
.section .num{font-size:9px}
.section .t{font-size:15px}
.stats{gap:7px}
.stat{padding:8px 12px 7px}
.stat .v{font-size:40px}
.stat .l{font-size:14px;margin-top:3px}
.stat .s{font-size:9.5px;margin-top:1px}
.overall{font-size:9.5px;margin-top:4px}
.pity-row{grid-template-columns:200px 1fr 118px;gap:8px;margin:4px 0}
.pity-name{font-size:12px}
.pity-track{height:7px}
.pity-num{font-size:9px}
.pity-note{font-size:9px;margin-top:2px}
.section{margin:12px 0 7px}
.pool{padding:8px 12px 7px;margin-bottom:7px}
.pool-head{gap:6px}
.pool-name{font-size:22px}
.ptag{font-size:8px;padding:2px 5px}
.pool-head-right{gap:10px}
.pool-total{font-size:19px}
.pool-total small{font-size:8px}
.pool-sub{font-size:9px;margin-top:2px}
.pool-body{gap:8px;margin-top:6px}
.ops{gap:6px}
.op{width:78px}
.op.hero{width:108px}
.op.small{width:36px}
.op .nm{font-size:9px;padding:1px 1px}
.op.hero .nm{font-size:12px}
.op .pull{font-size:7px;margin-top:0}
.op .badge,.op .dup{font-size:7px;padding:1px 2px}
.hero-panel{gap:8px}
.callout{padding:6px 8px}
.callout .big{font-size:22px}
.callout .txt{font-size:9px}
.char-callout{flex:1;border-left:3px solid #B8860B;background:rgba(184,134,11,.06);padding:6px 8px;min-width:0}
.char-callout .big{font:800 18px 'SF Mono',Menlo;color:#B8860B;letter-spacing:-.5px;white-space:nowrap}
.char-callout .txt{font:500 9px 'SF Mono',Menlo;color:rgba(21,23,24,.55);line-height:1.4;margin-top:2px}
.mini-grid{width:210px;padding:5px;gap:3px}
.mini{padding:1px 2px}
.mini b{font-size:16px}
.mini span{font-size:7.5px}
.tl{margin-top:5px}
.tl-track{height:8px;margin-top:8px}
.dot{top:-3px;height:15px}
.tl-label{font-size:8.5px;top:-14px}
.tl-ends{font-size:7.5px;margin-top:1px}
.legend{font-size:7.5px;gap:9px;margin-top:2px}
.legend i{width:6px;height:6px}
.other{padding:5px 8px;margin-bottom:6px;gap:8px}
.other-k{font-size:8px}
.other-name{font-size:13px}
.other-m{font-size:9px}
.other-r{gap:4px}
.other-tag{font-size:8px;padding:1px 5px}
.banner{padding:8px 12px;gap:8px}
.banner-k{font-size:13px}
.banner-v{font-size:22px}
.banner-x{font-size:9px}
.banner-r{font-size:8.5px}
.footer{padding-top:7px}
.foot-line{font-size:8.5px}
.foot-row{margin-top:4px}
.tri{font-size:8.5px;gap:5px}
.barcode{height:16px}
.foot-r{font-size:7.5px}
.closing{margin-top:8px;background:rgba(21,23,24,.03);border-left:3px solid #0098DC;padding:6px 10px}
.closing-k{font:800 9px 'SF Mono',Menlo;color:#0098DC;letter-spacing:1px;margin-bottom:2px}
.closing-line{font:500 9px 'SF Mono',Menlo;color:rgba(21,23,24,.5);line-height:1.55}
"""


if __name__ == "__main__":
    import argparse
    import json

    ap = argparse.ArgumentParser()
    ap.add_argument("--records", required=True)
    ap.add_argument("--out", default="poster_v2.html")
    ap.add_argument("--nick", default="博士")
    ap.add_argument("--uid", default="000000000")
    ap.add_argument("--privacy", choices=("full", "mask", "hide"), default="mask")
    ap.add_argument("--hide-nick", action="store_true")
    a = ap.parse_args()
    from ark_gacha import analyze_records
    from ark_pools import PoolUpIndex
    from ark_archive import coverage_report
    from ark_report import build_report
    recs = json.load(open(a.records, encoding="utf-8"))
    stats, _ = analyze_records(recs, PoolUpIndex())
    cov = coverage_report(recs)
    report = build_report(stats, a.nick, a.uid, cov, privacy=a.privacy, hide_nick=a.hide_nick)
    print(render_poster_v2(report, stats, a.out))
