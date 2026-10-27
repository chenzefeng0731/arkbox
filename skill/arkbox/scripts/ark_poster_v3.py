#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P1-B demo：最新卡池优先 + 手机可读的寻访档案主截图。

设计决策（按泽峰 2026-10-24 反馈）：
- 卡池按「最近一次寻访」倒序：最新池做完整卡，主角头像放大；
  往前池做紧凑行，头像缩小；不再按六星数排。
- 当前垫抽不再单独占三行，而是放回每个池子里；
  手机上一眼能把「哪个池垫了多少」和池名对上。
- 石白 60 抽空窗不再用宽红框，收成一行红字 + 蓝色最长横幅。
- 字号按 390–402px 手机屏反推：池名 40px / 四数 58px / 主角头像 150px；
  长 HTML 复用同一套组件，详情不塞进主截图。
- 默认 --poster 不动；本文件只是 demo。
"""

import html
import os
import random
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

CN = {2: "双", 3: "三", 4: "四", 5: "五", 6: "六"}


def _barcode(seed, n=42):
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


def _section(num, title, note=""):
    return f'''<div class="section"><span class="num">{num}</span>
      <span class="t">{html.escape(title)}</span>
      {f'<span class="note">{html.escape(note)}</span>' if note else ''}
      <span class="line"></span></div>'''


def _stat(value, label, sub="", cls=""):
    return f'''<div class="stat {cls}"><div class="v">{value}</div>
      <div class="l">{html.escape(label)}</div>
      {f'<div class="s">{html.escape(sub)}</div>' if sub else ''}</div>'''


def _op(s, cls="", dup=0):
    is_up = s.get("is_up")
    badge = ""
    if is_up is False:
        badge = '<span class="badge">歪</span>'
    elif dup > 1:
        badge = f'<span class="dup">×{dup}</span>'
    mark = "UP" if is_up is True else ("歪" if is_up is False else "待核")
    return f'''<div class="op {cls}">
      <img src="{AVATAR_URL.format(cid=html.escape(s['char_id'] or ''))}" alt="">
      {badge}
      <div class="nm">{html.escape(s['name'] or '?')}</div>
      <div class="pull">第{s['at_pull']}抽 · {mark}</div>
    </div>'''


def _timeline(p):
    total = max(int(p["total"]), 1)
    prev = 0
    segs, dots, labels = [], [], []
    max_gap, max_start = 0, 0
    for s in p["six_stars"]:
        at = s["at_pull"]
        gap = at - prev
        cls = "g" if gap <= 34 else ("m" if gap <= 50 else "r")
        if gap > 0:
            segs.append((prev, gap, cls))
        dots.append(at)
        if gap > max_gap:
            max_gap, max_start = gap, prev
        prev = at
    current = total - prev
    if current > 0:
        segs.append((prev, current, "p"))
    seg_html = "".join(
        f'<i class="seg {cls}" style="left:{start / total * 100:.3f}%;width:{gap / total * 100:.3f}%"></i>'
        for start, gap, cls in segs
    )
    dot_html = "".join(f'<i class="dot" style="left:{at / total * 100:.3f}%"></i>' for at in dots)
    if max_gap >= 50:
        labels.append((max_start + max_gap / 2, f"{max_gap} 抽", "r"))
    if current > 0:
        labels.append((prev + current / 2, f"垫 {current}", "b"))
    label_html = "".join(
        f'<span class="tl-label {cls}" style="left:{pos / total * 100:.3f}%">{html.escape(text)}</span>'
        for pos, text, cls in labels
    )
    return f'''<div class="tl"><div class="tl-track">{seg_html}{dot_html}{label_html}</div>
      <div class="tl-ends"><span>0</span><span>{total} 抽</span></div></div>'''


def _pitybar(pity, label=True, cls=""):
    pct = min(pity / 99 * 100, 100)
    lab = f'<span class="pity-lab">{pity}/99 · 下抽 {_next_rate(pity):g}%</span>' if label else ""
    return f'<div class="pitybar {cls}"><div class="pity-track"><i style="width:{pct:.2f}%"></i></div>{lab}</div>'


def _featured(p):
    uv = p.get("up_verdict") or {"known": False}
    six = p["six_stars"]
    n = len(six)
    dup_counts = Counter(s["char_id"] for s in six)
    up_txt = f'UP {uv.get("hit_count", 0)}/{uv.get("total", 0)}' if uv.get("known") else "UP 待核"
    up_cls = "ok" if uv.get("known") and uv.get("hit_count") == uv.get("total") else "mid"
    type_cls = {"limited": "lim", "linkage": "mid", "special": "mid"}.get(p.get("pool_type"), "std")
    gold = f"{CN.get(n, n)}金" if n >= 2 else f"{n} 六星"
    detail = " · ".join(f"第{s['at_pull']}抽 {s['name']}" for s in six[:3])
    if n > 3:
        detail += f" 等 {n} 位"

    if n <= 3:
        ops = "".join(_op(s, "feat", dup_counts.get(s["char_id"], 0)) for s in six)
    else:
        hero = max(six, key=lambda s: (bool(s.get("is_up")), dup_counts.get(s["char_id"], 0), -s["at_pull"]))
        others = [s for s in six if s is not hero][:3]
        ops = _op(hero, "feat", dup_counts.get(hero["char_id"], 0)) + "".join(
            _op(s, "seq", dup_counts.get(s["char_id"], 0)) for s in others
        ) + f'<div class="more">+{n - 1 - len(others)}</div>'

    return f'''<div class="feat">
      <div class="feat-head">
        <div class="feat-title"><span class="feat-name">{html.escape(p["pool"])}</span>
          <span class="ptag {type_cls}">{html.escape(p.get("pool_type_label") or "池型待核")}</span>
          <span class="ptag {up_cls}">{html.escape(up_txt)}</span>
          <span class="feat-new">最新</span></div>
        <div class="feat-nums"><b>{p["total"]}</b> 抽 <b>{p["six_count"]}</b> 六星</div>
      </div>
      <div class="feat-date">{p["first_ts"]} ~ {p["last_ts"]} · 均值 {p["avg_gap"] or "—"} · 最长 {p["worst_gap"] or "—"} · 当前垫 {p["since_last_six"]}/99</div>
      <div class="feat-body">
        <div class="feat-ops">{ops}</div>
        <div class="feat-concl">
          <div class="feat-big">{gold}</div>
          <div class="feat-line">{html.escape(detail)}</div>
          <div class="feat-line">{html.escape(up_txt)} · 当前垫 {p["since_last_six"]}/99</div>
          {_pitybar(p["since_last_six"])}
        </div>
      </div>
    </div>'''


def _compact(p):
    uv = p.get("up_verdict") or {"known": False}
    six = p["six_stars"]
    dup_counts = Counter(s["char_id"] for s in six)
    up_txt = f'UP {uv.get("hit_count", 0)}/{uv.get("total", 0)}' if uv.get("known") else "UP 待核"
    type_cls = {"limited": "lim", "linkage": "mid", "special": "mid"}.get(p.get("pool_type"), "std")
    dup_max = max(dup_counts.values()) if dup_counts else 0
    dup_name = ""
    if dup_max >= 2:
        cid = max(dup_counts.items(), key=lambda kv: kv[1])[0]
        dup_name = next((s["name"] for s in six if s["char_id"] == cid), "?")
    if dup_max >= 3 and p.get("worst_gap") and p["worst_gap"] >= 50:
        story = f'{dup_name} ×{dup_max} · 三顾茅庐 · 最长 {p["worst_gap"]} 抽'
        story_cls = "gold"
    elif p.get("worst_gap") and p["worst_gap"] >= 50:
        prev, best = 0, None
        for s in six:
            gap = s["at_pull"] - prev
            if gap == p["worst_gap"]:
                best = s
                break
            prev = s["at_pull"]
        story = f'第 {best["at_pull"]} 抽才出 {best["name"]} · 最长 {p["worst_gap"]} 抽' if best else f'最长 {p["worst_gap"]} 抽'
        story_cls = "red"
    elif dup_max >= 2:
        story = f'{dup_name} ×{dup_max} · 三顾茅庐'
        story_cls = "gold"
    else:
        story = f'均值 {p["avg_gap"] or "—"} · 最长 {p["worst_gap"] or "—"}'
        story_cls = ""

    hero = max(six, key=lambda s: (bool(s.get("is_up")), dup_counts.get(s["char_id"], 0), -s["at_pull"])) if six else None
    others = [s for s in six if s is not hero][:2]
    ops = ""
    if hero:
        ops += _op(hero, "comp", dup_counts.get(hero["char_id"], 0))
    ops += "".join(_op(s, "tiny") for s in others)

    return f'''<div class="compact">
      <div class="c-left">
        <div class="c-head"><span class="c-name">{html.escape(p["pool"])}</span>
          <span class="ptag {type_cls}">{html.escape(p.get("pool_type_label") or "池型待核")}</span>
          <span class="ptag mid">{html.escape(up_txt)}</span></div>
        <div class="c-meta">{p["total"]} 抽 · {p["six_count"]} 六星 · 均值 {p["avg_gap"] or "—"} · 当前垫 {p["since_last_six"]}/99</div>
        <div class="c-story {story_cls}">{html.escape(story)}</div>
        {_pitybar(p["since_last_six"], label=False, cls="small")}
      </div>
      <div class="c-ops">{ops}</div>
    </div>'''


_GOLD_CN = {2: "双", 3: "三", 4: "四", 5: "五", 6: "六"}


def _title_tags(report):
    """副签直接从事件数据生成，不依赖主称号 kind（主称号固定为评级）。"""
    tags = []
    m = report["metrics"]
    best = report.get("best_ten")
    if best and best.get("six_count", 0) >= 2:
        tags.append((_GOLD_CN.get(best["six_count"], str(best["six_count"])) + "金", "gold"))
        if (m.get("max_gap") or 0) >= 50:
            tags.append((f'{m["max_gap"]} 抽才出', "black"))
    if m.get("max_duplicate", 0) >= 3:
        d = m["duplicates"][0]
        tags.append((f"三顾茅庐 · {d['name']}×{d['count']}", "blue"))
    if m.get("up_total"):
        tags.append((f'UP {m["up_hits"]}/{m["up_total"]}', "blue"))
    return "".join(_tag(t, c) for t, c in tags[:4])


def render_poster_v3(report, stats, out_path):
    m = report["metrics"]
    t = report["title"]
    luck = report["luck"]
    totals = report["totals"]
    ordered = sorted(stats, key=lambda p: (p.get("last_ts") or "", p.get("first_ts") or ""), reverse=True)
    featured = ordered[0] if ordered else None
    others = ordered[1:3]
    extra = max(0, len(ordered) - 3)
    worst = m.get("max_gap") or 0
    worst_at = m.get("max_gap_at") or "—"
    worst_pool = m.get("max_gap_pool") or "—"
    best = m.get("best_gap") or 0
    best_name = m.get("best_gap_name") or ""
    best_pool = m.get("best_gap_pool") or ""
    date_str = report.get("generated") or datetime.now().strftime("%Y.%m.%d")

    if featured:
        feat_n = featured["six_count"]
        feat_gold = f"{CN.get(feat_n, feat_n)}金" if feat_n >= 2 else f"{feat_n} 六星"
        caption = f'最新一池 {featured["pool"]} {featured["total"]} 抽{feat_gold}；{worst_pool} {worst} 抽才出'
    else:
        caption = t["caption"]

    stats_html = (
        _stat(totals["pulls"], "累计寻访", f'{totals["pools"]} 池', "gold")
        + _stat(totals["six"], "六星干员", "全档案")
        + _stat(m["mean_gap"] if m["mean_gap"] is not None else "—", "已结算均值/六星",
                f'{m["gap_count"]} 段')
        + _stat(f'{luck["better_than"]}%' if luck["better_than"] is not None else "—",
                "理论位置", "优于同段数样本 · 理论模型", "blue")
    )
    comp_html = "".join(_compact(p) for p in others)
    extra_line = f'<div class="extra">还有 {extra} 池未展开 · 详见长 HTML</div>' if extra else ""

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
    <div class="title">{html.escape(t["label"])}</div>
    <div class="caption">{html.escape(caption)}</div>
    <div class="tags">{_title_tags(report)}</div>
  </div>

  {_section("01", "抽卡总结")}
  <div class="stats">{stats_html}</div>
  <div class="overall">整体 {m["overall_efficiency"]} 抽/六星（含当前垫抽 {m["current_pity_total"]}） · 期望 {luck["expected_gap"]} 抽/六星 · 非全服排名</div>

  {_section("02", "最新卡池", "最近在前")}
  {_featured(featured) if featured else ''}

  {_section("03", "往前卡池", "按最近寻访排序")}
  {comp_html}
  {extra_line}
  <div class="pity-note">当前垫抽在每个池子内独立计数，不能相加为一次连续；99 抽硬保底。</div>

  <div class="banner">
    <span class="banner-k">最长已结束间隔</span><span class="banner-v">{worst} 抽</span>
    <span class="banner-x">第 {worst_at} 抽出 {html.escape(m.get("max_gap_name") or "")} · {html.escape(worst_pool)}</span>
    <span class="banner-r">最快 {best} 抽 · {html.escape(best_name)} · {html.escape(best_pool)}</span>
  </div>

  <div class="footer">
    <div class="foot-line">本档案区间 {html.escape(report["coverage"].get("earliest") or "")} ~ {html.escape(report["coverage"].get("latest") or "")} · 仅部分历史（完整性未知） · 理论模型 99 抽硬保底 · 非全服排名 · 非官方玩家工具</div>
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
.wrap{position:relative;padding:30px 48px 18px;height:100%;display:flex;flex-direction:column}
.header{display:flex;justify-content:space-between;align-items:flex-start;gap:16px}
.header-left{min-width:0;flex:1}
.kicker{display:flex;justify-content:space-between;align-items:center;font:700 12px 'SF Mono',Menlo,monospace;color:#0098DC;letter-spacing:2px}
.kicker .file{color:rgba(21,23,24,.45);font-size:11px;letter-spacing:1px}
h1{font-size:34px;font-weight:900;letter-spacing:1px;margin-top:5px}
h1 b{color:#0098DC}
.doctor{margin-top:4px;font:500 14px 'SF Mono',Menlo;color:rgba(21,23,24,.62);display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.doctor b{color:#151718}
.chip{font:700 11px 'SF Mono',Menlo;color:#0098DC;border:1px solid rgba(0,152,220,.4);padding:2px 6px}
.seal{width:92px;height:92px;border:3px solid rgba(200,42,54,.8);border-radius:50%;transform:rotate(10deg);display:flex;align-items:center;justify-content:center;flex:0 0 auto;margin-top:2px}
.seal-in{text-align:center;color:rgba(200,42,54,.85);border:2px solid rgba(200,42,54,.45);border-radius:50%;width:76px;height:76px;display:flex;flex-direction:column;justify-content:center;gap:1px}
.seal .s1{font:900 10px 'SF Mono',Menlo;letter-spacing:1px}
.seal .s2{font-size:8px}
.seal .s3{font-size:9px;font-weight:700}
.title-zone{margin-top:10px}
.title{display:inline-block;background:#151718;color:#fff;border-left:10px solid #0098DC;font-size:54px;font-weight:900;padding:7px 28px 11px;transform:rotate(-1.5deg);clip-path:polygon(2% 8%,98% 0,100% 88%,0 100%);letter-spacing:3px;box-shadow:0 7px 20px rgba(0,152,220,.12)}
.caption{margin-top:7px;font-size:22px;color:rgba(21,23,24,.62);letter-spacing:.2px}
.tags{display:flex;gap:7px;margin-top:7px;flex-wrap:wrap}
.tag{font:800 17px -apple-system,'PingFang SC';padding:3px 9px;border:1px solid rgba(21,23,24,.2);letter-spacing:.3px}
.tag.gold{color:#B8860B;border-color:rgba(184,134,11,.5);background:rgba(184,134,11,.06)}
.tag.black{background:#151718;color:#fff;border-color:#151718}
.tag.blue{color:#0098DC;border-color:rgba(0,152,220,.45);background:rgba(0,152,220,.05)}
.section{display:flex;align-items:center;gap:9px;margin:12px 0 7px}
.section .num{font:700 11px 'SF Mono',Menlo;color:#0098DC;letter-spacing:1px}
.section .t{font-size:20px;font-weight:900;letter-spacing:1px}
.section .note{font:600 12px 'SF Mono',Menlo;color:rgba(21,23,24,.45)}
.section .line{flex:1;height:1px;background:rgba(21,23,24,.18)}
.stats{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.stat{background:rgba(255,255,255,.55);border:1px solid rgba(21,23,24,.22);padding:10px 14px 8px;clip-path:polygon(0 0,calc(100% - 12px) 0,100% 12px,100% 100%,0 100%)}
.stat .v{font:800 52px/1 'SF Mono',Menlo,monospace;letter-spacing:-1px}
.stat .l{font-size:24px;font-weight:700;color:rgba(21,23,24,.8);margin-top:3px}
.stat .s{font:500 15px 'SF Mono',Menlo;color:rgba(21,23,24,.45);margin-top:1px}
.stat.gold .v{color:#B8860B}
.stat.blue .v{color:#0098DC}
.overall{font:500 15px 'SF Mono',Menlo;color:rgba(21,23,24,.45);margin-top:5px}
.feat{background:rgba(255,255,255,.62);border:1px solid rgba(21,23,24,.24);padding:12px 14px 9px;clip-path:polygon(0 0,calc(100% - 14px) 0,100% 14px,100% 100%,0 100%)}
.feat-head{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.feat-title{display:flex;align-items:center;gap:7px;flex-wrap:wrap}
.feat-name{font-size:36px;font-weight:900;letter-spacing:.5px}
.feat-new{font:800 12px 'SF Mono',Menlo;color:#fff;background:#0098DC;padding:2px 6px;letter-spacing:1px}
.feat-nums{margin-left:auto;font:800 20px 'SF Mono',Menlo;color:rgba(21,23,24,.7);white-space:nowrap}
.feat-nums b{font-size:30px;color:#151718;letter-spacing:-1px}
.feat-date{font:500 13px 'SF Mono',Menlo;color:rgba(21,23,24,.45);margin-top:2px}
.feat-body{display:flex;gap:12px;align-items:flex-start;margin-top:8px}
.feat-ops{display:flex;gap:7px;flex:0 0 auto;align-items:flex-start}
.feat-concl{flex:1;min-width:0;padding-top:2px}
.feat-big{font:900 40px 'SF Mono',Menlo;color:#151718;letter-spacing:-1px;line-height:1}
.feat-line{font-size:21px;color:rgba(21,23,24,.68);margin-top:4px;line-height:1.3}
.pitybar{margin-top:5px}
.pitybar.small{margin-top:3px}
.pity-track{height:8px;background:rgba(21,23,24,.08);border:1px solid rgba(21,23,24,.16);position:relative}
.pitybar.small .pity-track{height:6px}
.pity-track i{position:absolute;left:0;top:0;bottom:0;background:#0098DC}
.pity-lab{display:block;font:700 12px 'SF Mono',Menlo;color:rgba(21,23,24,.5);margin-top:1px;text-align:right}
.tl{margin-top:6px}
.tl-track{position:relative;height:9px;background:rgba(21,23,24,.07);border:1px solid rgba(21,23,24,.15);margin-top:12px}
.seg{position:absolute;top:0;height:100%}
.seg.g{background:#0098DC}
.seg.m{background:#B8860B}
.seg.r{background:#C82A36}
.seg.p{background:repeating-linear-gradient(45deg,rgba(21,23,24,.35) 0 3px,rgba(21,23,24,.08) 3px 6px)}
.dot{position:absolute;top:-5px;width:2px;height:18px;background:#151718}
.tl-label{position:absolute;top:-17px;transform:translateX(-50%);font:800 10px 'SF Mono',Menlo;white-space:nowrap}
.tl-label.r{color:#C82A36}
.tl-label.b{color:#0098DC}
.tl-ends{display:flex;justify-content:space-between;font:500 10px 'SF Mono',Menlo;color:rgba(21,23,24,.4);margin-top:2px}
.op{position:relative;width:74px;flex:0 0 auto}
.op.feat{width:138px}
.op.seq{width:90px}
.op.comp{width:64px}
.op.tiny{width:48px}
.op img{width:100%;aspect-ratio:1;object-fit:cover;display:block;border:1px solid rgba(21,23,24,.18);filter:grayscale(.06)}
.op.feat img{outline:2px solid #B8860B;outline-offset:-2px}
.op.off img{outline:2px solid #C82A36;outline-offset:-2px}
.op .nm{background:#000;color:#fff;font:700 11px -apple-system,'PingFang SC';text-align:center;padding:2px 1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.op.feat .nm{font-size:19px}
.op.seq .nm{font-size:14px}
.op.comp .nm{font-size:12px}
.op.tiny .nm{font-size:10px}
.op .pull{font:500 9px 'SF Mono',Menlo;color:rgba(21,23,24,.5);text-align:center;margin-top:1px;white-space:nowrap}
.op.feat .pull{font-size:14px}
.op.comp .pull{font-size:9px}
.op.tiny .pull{font-size:8px}
.op .badge{position:absolute;top:2px;left:2px;background:#C82A36;color:#fff;font:800 9px -apple-system;padding:1px 3px}
.op .dup{position:absolute;top:2px;right:2px;background:#B8860B;color:#fff;font:800 9px 'SF Mono',Menlo;padding:1px 3px}
.op.feat .badge,.op.feat .dup{font-size:12px;padding:2px 4px}
.more{width:54px;height:138px;display:flex;align-items:center;justify-content:center;font:800 24px 'SF Mono',Menlo;color:rgba(21,23,24,.35);border:1px dashed rgba(21,23,24,.2)}
.compact{display:flex;align-items:center;gap:12px;border:1px solid rgba(21,23,24,.2);background:rgba(255,255,255,.5);padding:8px 12px;margin-bottom:7px}
.c-left{flex:1;min-width:0}
.c-head{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.c-name{font-size:26px;font-weight:900}
.c-meta{font:500 14px 'SF Mono',Menlo;color:rgba(21,23,24,.5);margin-top:2px}
.c-story{font-size:21px;font-weight:800;margin-top:2px}
.c-story.red{color:#C82A36}
.c-story.gold{color:#B8860B}
.c-ops{display:flex;gap:5px;flex:0 0 auto;align-items:flex-end}
.ptag{font:800 10px -apple-system,'PingFang SC';padding:2px 6px;letter-spacing:.5px;border:1px solid transparent;white-space:nowrap}
.ptag.lim{background:#0098DC;color:#fff}
.ptag.mid{background:#fff;color:#151718;border-color:rgba(21,23,24,.2)}
.ptag.ok{background:#B8860B;color:#fff}
.ptag.bad{background:#C82A36;color:#fff}
.ptag.std{background:rgba(21,23,24,.06);color:rgba(21,23,24,.55);border-color:rgba(21,23,24,.18)}
.extra{font:600 13px 'SF Mono',Menlo;color:rgba(21,23,24,.45);margin:3px 0 1px}
.pity-note{font:500 12px 'SF Mono',Menlo;color:rgba(21,23,24,.42);margin:2px 0 1px}
.banner{background:#0098DC;color:#fff;display:flex;align-items:center;gap:11px;padding:9px 14px;clip-path:polygon(0 0,100% 0,100% calc(100% - 10px),calc(100% - 10px) 100%,0 100%);margin-top:6px}
.banner-k{font-size:20px;font-weight:800}
.banner-v{font:900 32px 'SF Mono',Menlo;letter-spacing:-1px}
.banner-x{font-size:13px;opacity:.9}
.banner-r{margin-left:auto;font:700 11px 'SF Mono',Menlo;text-align:right;opacity:.9}
.footer{margin-top:auto;padding-top:8px;border-top:1px solid rgba(21,23,24,.2)}
.foot-line{font:500 12px 'SF Mono',Menlo;color:rgba(21,23,24,.42);line-height:1.5}
.foot-row{display:flex;align-items:flex-end;justify-content:space-between;margin-top:4px}
.tri{display:flex;align-items:center;gap:6px;font:700 10px 'SF Mono',Menlo;color:rgba(21,23,24,.45);letter-spacing:1px}
.barcode{display:flex;align-items:flex-end;height:18px}
.barcode i{background:#151718;height:100%;display:block}
.foot-r{text-align:right;font:500 9px 'SF Mono',Menlo;color:rgba(21,23,24,.4);letter-spacing:.5px}
"""


if __name__ == "__main__":
    import argparse
    import json

    ap = argparse.ArgumentParser()
    ap.add_argument("--records", required=True)
    ap.add_argument("--out", default="poster_v3.html")
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
    print(render_poster_v3(report, stats, a.out))
