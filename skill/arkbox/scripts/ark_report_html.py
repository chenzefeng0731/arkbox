#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""响应式长报告：与海报共用档案纸/黑斜切/蓝信号/条码语言。

单文件、零外部 JS/CSS；头像来自公开 CDN。默认 UID 已在 report 里遮蔽，
HTML 不落完整 UID。移动端按 360–430px 设计，桌面端只加宽边距。
"""

import html
import os
from datetime import datetime

from ark_poster_v4 import AVATAR_URL, _barcode, _seal, _title_tags

CN = {2: "双", 3: "三", 4: "四", 5: "五", 6: "六"}

# 头像加载失败：先换 jsdelivr 镜像（raw.githubusercontent.com 在部分网络不可达），再失败才隐藏
AVATAR_ONERROR = (
    "if(!this.dataset.f){this.dataset.f=1;"
    "this.src=this.src.replace('raw.githubusercontent.com','cdn.jsdelivr.net/gh')"
    ".replace('/main/','@main/');}"
    "else{this.style.display='none';this.parentNode.classList.add('noimg')}"
)


def _h(value):
    return html.escape(str(value if value is not None else ""))


def _ts_range(p):
    if p.get("first_ts") == p.get("last_ts"):
        return p.get("last_ts") or "—"
    return f'{p.get("first_ts") or "—"} ~ {p.get("last_ts") or "—"}'


def _op(event, cls="", featured=False):
    name = event.get("name") or "?"
    is_up = event.get("is_up")
    mark = "UP" if is_up is True else ("歪" if is_up is False else "待核")
    badge = ""
    if is_up is False:
        badge = '<span class="badge off">歪</span>'
    elif event.get("dup_count", 0) > 1:
        badge = f'<span class="badge dup">×{event["dup_count"]}</span>'
    return f'''<div class="op {cls}">
      <div class="avatar"><img src="{AVATAR_URL.format(cid=_h(event.get('char_id') or ''))}"
        alt="" loading="lazy" onerror="{AVATAR_ONERROR}">
        <span class="fallback">{_h(name[:1])}</span></div>
      {badge}
      <div class="nm">{_h(name)}</div>
      <div class="pull">第 {event.get("at_pull") or "?"} 抽 · {mark}</div>
    </div>'''


def _timeline(p):
    events = p.get("events") or []
    total = max(int(p.get("total") or 0), 1)
    current = int(p.get("display_pity", p.get("current_pity", 0)) or 0)
    segs = "".join(
        f'<i class="seg {_h(e.get("gap_class"))}" style="left:{e.get("gap_start_pct", 0):.3f}%;'
        f'width:{e.get("gap_width_pct", 0):.3f}%"></i>' for e in events
    )
    if current:
        segs += (f'<i class="seg p" style="left:{100 - current / total * 100:.3f}%;'
                 f'width:{current / total * 100:.3f}%"></i>')
    dots = "".join(
        f'<i class="dot" style="left:{e.get("at_pct", 0):.3f}%"></i>' for e in events
    )
    labels = []
    worst = max(events, key=lambda x: x.get("gap", 0)) if events else None
    if worst and worst.get("gap", 0) >= 50:
        labels.append((worst.get("gap_start_pct", 0) + worst.get("gap_width_pct", 0) / 2,
                       f'{worst["gap"]} 抽', "r"))
    if current:
        labels.append((100 - current / total * 50, f"垫 {current}", "b"))
    label_html = "".join(
        f'<span class="tl-label {cls}" style="left:{pos:.3f}%">{_h(text)}</span>'
        for pos, text, cls in labels
    )
    return f'''<div class="tl"><div class="tl-track">{segs}{dots}{label_html}</div>
      <div class="tl-ends"><span>0</span><span>{total} 抽</span></div></div>'''


def _pity(p):
    pity = int(p.get("display_pity", p.get("current_pity", 0)) or 0)
    rate = p.get("next_rate")
    pct = min(pity / 99 * 100, 100)
    return f'''<div class="bar-row">
      <div class="bar-info"><span>六星垫 <b>{pity}</b>/99</span>
        <span>下抽六星率 {rate:g}%</span></div>
      <div class="bar"><i style="width:{pct:.2f}%"></i></div>
      <div class="bar-note">六星硬保底，不代表 UP 保底</div>
    </div>'''


def _spark(p):
    spark = p.get("spark")
    if not spark:
        return '<div class="bar-note">该池型 UP 兑换井规则不统一，不计算井进度。</div>'
    return f'''<div class="bar-row spark">
      <div class="bar-info"><span>兑换井 <b>{spark["pulls"]}</b>/{spark["threshold"]}</span>
        <span>{'已到井' if spark["reached"] else '还差 ' + str(spark["remaining"]) + ' 抽'}</span></div>
      <div class="bar"><i style="width:{spark["progress"]:.2f}%"></i></div>
      <div class="bar-note">{_h(spark["note"])}</div>
    </div>'''


def _event_rows(p):
    rows = []
    for e in p.get("events") or []:
        mark = "UP" if e.get("is_up") is True else ("歪" if e.get("is_up") is False else "UP 待核")
        cls = "up" if e.get("is_up") is True else ("off" if e.get("is_up") is False else "")
        first = " · 首段" if e.get("is_first") else ""
        rows.append(f'''<div class="event">
          <div class="e-at">第 {e.get("at_pull")} 抽</div>
          <div class="e-name">{_h(e.get("name"))}<span class="{cls}">{mark}</span></div>
          <div class="e-gap">+{e.get("gap")} 抽{first}</div>
          <div class="e-date">{_h(e.get("date"))}</div>
        </div>''')
    return "".join(rows) or '<div class="empty">该池暂无六星记录</div>'


def _pool_card(p, index):
    events = p.get("events") or []
    cls = "featured" if index == 0 else ""
    ops = "".join(_op(e, "big" if index == 0 else "small", index == 0) for e in events[:4])
    if len(events) > 4:
        ops += f'<div class="more">+{len(events) - 4}</div>'
    up_label = p.get("up_label") or "UP 待核"
    type_cls = {"limited": "lim", "linkage": "link", "standard": "std"}.get(p.get("pool_type"), "other")
    return f'''<article class="pool {cls}">
      <header class="pool-head">
        <div class="pool-title"><h3>{_h(p.get("pool"))}</h3>
          <span class="ptag {type_cls}">{_h(p.get("pool_type_label"))}</span>
          <span class="ptag plain">{_h(up_label)}</span>
          {('<span class="ptag recent">记录最近</span>' if index == 0 else '')}
        </div>
        <div class="pool-count"><b>{p.get("total")}</b> 抽 · <b>{p.get("six_count")}</b> 六星</div>
      </header>
      <div class="pool-meta">{_ts_range(p)} · 池内均值 {p.get("avg_gap") or "—"} · 最长 {p.get("worst_gap") or "—"}</div>
      <div class="pool-story">{_h(p.get("conclusion"))}</div>
      <div class="ops">{ops or '<div class="empty">该池暂无六星记录</div>'}</div>
      {_pity(p)}
      {_spark(p)}
      {_timeline(p)}
      <div class="events">{_event_rows(p)}</div>
    </article>'''


def _title_chips(report):
    return "".join(
        f'<button class="title-chip{" active" if i == 0 else ""}" data-label="{_h(t["label"])}" '
        f'data-caption="{_h(t.get("caption") or t.get("evidence") or "")}" '
        f'aria-pressed="{"true" if i == 0 else "false"}">{_h(t["label"])}</button>'
        for i, t in enumerate(report.get("title_candidates") or [])
    )


def _type_cards(report):
    cards = []
    for t in report.get("pool_types") or []:
        cards.append(f'''<div class="type-card">
          <div class="type-top"><b>{_h(t.get("label"))}</b><span>{t.get("pulls")} 抽</span></div>
          <div class="type-nums"><span>{t.get("six")} 六星</span>
            <span>池内均值 {t.get("mean_gap") if t.get("mean_gap") is not None else "—"}</span>
            <span>UP {(str(t.get("up_hits")) + "/" + str(t.get("up_total"))) if t.get("up_total") else "—"}</span></div>
          <div class="type-pools">{_h("、".join(t.get("pools") or []))}</div>
        </div>''')
    return "".join(cards)


def _compare(report):
    c = report.get("period_compare")
    if not c:
        return ""
    latest, earlier, delta = c["latest"], c["earlier"], c.get("delta")
    delta_txt = "—" if delta is None else (f"{delta:+} 抽" if delta else "持平")
    l_mean = latest["mean_gap"] if latest["mean_gap"] is not None else "—"
    e_mean = earlier["mean_gap"] if earlier["mean_gap"] is not None else "—"
    return f'''<div class="compare">
      <div class="cmp-card"><span class="cmp-k">最近一池</span>
        <b>{_h(latest["pool"])}</b><strong>{l_mean}</strong>
        <span class="cmp-s">池内均值 · {latest["pulls"]} 抽 / {latest["six"]} 六星</span></div>
      <div class="cmp-card"><span class="cmp-k">更早 {earlier["pools"]} 池</span>
        <b>合计</b><strong>{e_mean}</strong>
        <span class="cmp-s">池内均值 · {earlier["pulls"]} 抽 / {earlier["six"]} 六星</span></div>
      <div class="cmp-delta">最近一池相对更早池：<b>{delta_txt}</b><br><span>{_h(c.get("note"))}</span></div>
    </div>'''


def _gap_cards(report):
    return "".join(
        f'''<div class="gap-card"><b>{_h(g.get("title"))}</b><p>{_h(g.get("detail"))}</p></div>'''
        for g in report.get("data_gaps") or []
    )


def _audit_table(report):
    rows = "".join(
        f'<tr><td>{_h(r["指标"])}</td><td>{_h(r["原始值"])}</td>'
        f'<td>{_h(r["公式/口径"])}</td><td>{_h(r["显示值"])}</td>'
        f'<td>{"✓" if r["一致"] else "✗"}</td></tr>'
        for r in report.get("audit") or []
    )
    return f'''<div class="table-wrap"><table>
      <thead><tr><th>指标</th><th>原始值</th><th>公式/口径</th><th>显示值</th><th>一致</th></tr></thead>
      <tbody>{rows}</tbody></table></div>'''


def _pool_table(report):
    rows = []
    for p in sorted(report.get("pool_stats") or [], key=lambda x: x.get("last_ts") or "", reverse=True):
        rows.append(f'''<tr><td>{_h(p.get("pool"))}</td><td>{_h(p.get("pool_type_label"))}</td>
          <td>{p.get("total")}</td><td>{p.get("six_count")}</td>
          <td>{p.get("mean_gap") if p.get("mean_gap") is not None else "—"}</td>
          <td>{p.get("current", p.get("current_pity", 0))}</td><td>{_h(_ts_range(p))}</td></tr>''')
    return f'''<div class="table-wrap"><table>
      <thead><tr><th>卡池</th><th>池型</th><th>抽数</th><th>六星</th><th>池内均值</th><th>当前垫</th><th>记录范围</th></tr></thead>
      <tbody>{"".join(rows)}</tbody></table></div>'''


def render_html(report, out_path, limit=None, site_mode=False):
    m = report["metrics"]
    luck = report["luck"]
    totals = report["totals"]
    cov = report.get("coverage") or {}
    share = report.get("share") or {}
    pools = sorted(report.get("pools", {}).get("all") or [],
                   key=lambda p: (p.get("last_ts") or "", p.get("first_ts") or ""), reverse=True)
    if limit:
        pools = pools[:limit]
    pool_html = "".join(_pool_card(p, i) for i, p in enumerate(pools))
    more_note = (f'<p class="note">本页只展示最近 {len(pools)} 池；上方汇总仍为全部 {totals["pools"]} 池。</p>'
                 if limit and len(pools) < totals["pools"] else "")
    up_hits = m.get("up_hits") or 0
    up_total = m.get("up_total") or 0
    up_rate = round(up_hits / up_total * 100) if up_total else None
    up_disp = f"{up_hits}/{up_total}" if up_total else "待核"
    up_sub = f"{up_rate}% · 只算已核验六星" if up_rate is not None else "UP 待核或数据不可用"
    overall_disp = m.get("overall_efficiency") if m.get("overall_efficiency") is not None else "—"
    best = m.get("best_gap")
    worst = m.get("max_gap")
    best_first = "（首段）" if m.get("best_gap_first") else ""
    worst_first = "（首段）" if m.get("max_gap_first") else ""
    better_disp = f"{luck.get('better_than')}%" if luck.get("better_than") is not None else "—"
    best_disp = f"{best} 抽" if best is not None else "—"
    worst_disp = f"{worst} 抽" if worst is not None else "—"
    best_detail = (f'{_h(m.get("best_gap_name"))} · {_h(m.get("best_gap_pool"))}{best_first}'
                   if best is not None else "暂无池内间隔")
    worst_detail = (f'{_h(m.get("max_gap_name"))} · {_h(m.get("max_gap_pool"))}{worst_first}'
                    if worst is not None else "暂无池内间隔")
    date_str = report.get("generated") or datetime.now().strftime("%Y.%m.%d")
    pity_bits = " / ".join(
        f'{p.get("pool_type_label") or "池"} {p.get("current", 0)}'
        for p in report.get("pool_stats") or []
    )
    pity_note = (f"当前垫抽 {pity_bits}，各池独立，不能相加成一次连续。" if pity_bits
                 else "当前没有垫抽记录。")
    privacy_note = ("公开站点：昵称显示为“博士”，UID 已隐藏；页面已加 noindex，链接不会被主动收录。"
                    if site_mode else (share.get("privacy_note") or ""))
    share_text = _h(share.get("text") or "")
    share_variants = "".join(
        f'<button class="share-chip{" active" if i == 0 else ""}" data-text="{_h(v.get("text") or "")}">{_h(v.get("label"))}</button>'
        for i, v in enumerate(share.get("variants") or [])
    )
    title_tags = _title_tags(report)
    page_title = ("明日方舟寻访档案 · ArkBox" if site_mode
                  else f'寻访档案 · {_h(report["doctor"]["nick"])}')
    robots = ('<meta name="robots" content="noindex,nofollow,noarchive">\n'
              if site_mode else "")
    site_note = ('<div class="site-note">公开分享页 · 昵称显示为博士 · 不含 UID · '
                 '数据仅覆盖本档案区间 · 非全服排名</div>' if site_mode else "")
    html_text = f'''<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
{robots}<title>{page_title}</title>
<style>{CSS}</style></head><body>
<div class="grid"></div><div class="hazard"></div>
<main class="wrap">
  {site_note}
  <header class="header">
    <div class="header-left">
      <div class="kicker"><span>ARKBOX // GACHA REPORT</span><span class="file">FILE NO. R-{totals["pulls"] % 1000:03d}</span></div>
      <h1>寻访档案 <b>/</b> 欧非鉴定</h1>
      <div class="doctor">DOCTOR <b>{_h(report["doctor"]["nick"])}</b>
        {f'<span class="tenure">入职 {_h(report["tenure"].get("register_date"))} · {report["tenure"].get("days")} 天</span>' if report.get("tenure") else ''}
        <span class="chip">本次记录 · 截至 {_h(cov.get("latest") or "—")}</span>
      </div>
    </div>
    {_seal(date_str)}
  </header>

  <section class="hero">
    <h2 id="hero-title">{_h(report["title"]["label"])}</h2>
    <p id="hero-caption">{_h(report["title"]["caption"])}</p>
    <div class="tags">{title_tags}</div>
  </section>

  <section class="summary">
    <div class="stat gold"><div class="v">{m.get("mean_gap") if m.get("mean_gap") is not None else "—"}</div>
      <div class="l">池内均值 / 六星</div><div class="s">{m.get("gap_count")} 段 · 按池独立 · 不含当前垫</div></div>
    <div class="stat blue"><div class="v">{better_disp}</div>
      <div class="l">理论位置</div><div class="s">同段数理论样本 · 不是全服排名</div></div>
    <div class="stat"><div class="v">{totals["six"]}</div><div class="l">六星干员</div>
      <div class="s">本区间 {totals["pulls"]} 抽 · {totals["pools"]} 池</div></div>
    <div class="stat"><div class="v">{up_disp}</div><div class="l">UP 命中</div>
      <div class="s">{up_sub}</div></div>
  </section>
  <div class="overall">整体 {overall_disp} 抽/六星（含当前垫 {m.get("current_pity_total")} 抽） · 期望 {luck.get("expected_gap")} 抽/六星 · 非全服排名</div>

  <div class="banner">
    <div class="bcell"><span class="bk">最欧</span><span class="bv">{best_disp}</span>
      <span class="bx">{best_detail}</span></div>
    <div class="bcell"><span class="bk">最非</span><span class="bv">{worst_disp}</span>
      <span class="bx">{worst_detail}</span></div>
    <div class="bcell"><span class="bk">UP 命中</span><span class="bv">{up_disp}</span>
      <span class="bx">{up_sub}</span></div>
  </div>

  <div class="section"><span class="num">01</span><span class="t">卡池时间线</span><span class="line"></span></div>
  <p class="note">按最近一次寻访倒序；每池独立统计，不跨池合并。每池首段可能承接档案外垫抽。</p>
  {pool_html}
  {more_note}

  <div class="section"><span class="num">02</span><span class="t">池型对照</span><span class="line"></span></div>
  <div class="types">{_type_cards(report)}</div>
  {_compare(report)}

  <div class="section"><span class="num">03</span><span class="t">换个说法</span><span class="line"></span></div>
  <p class="note">点一个称号，标题会切换；海报使用主称号。所有候选都由同一份数据支撑。</p>
  <div class="title-chips" id="title-chips">{_title_chips(report)}</div>

  <div class="section"><span class="num">04</span><span class="t">分享文案</span><span class="line"></span></div>
  <div class="share-box">
    <div class="share-chips" id="share-chips">{share_variants}</div>
    <p id="share-text">{share_text}</p>
    <button class="copy" id="copy-btn" type="button">复制文案</button>
    <div class="privacy">{_h(privacy_note)}</div>
  </div>

  <div class="section"><span class="num">05</span><span class="t">数据说明</span><span class="line"></span></div>
  <div class="gaps">{_gap_cards(report)}</div>
  <div class="privacy-box"><b>隐私</b><p>产物不展示 UID · {_h(privacy_note)}</p></div>
  <p class="note">{_h(cov.get("line"))}</p>

  <details class="audit"><summary>数据口径与校验（点开核对）</summary>
    <h3>按池独立明细</h3>
    {_pool_table(report)}
    <h3>审计表</h3>
    {_audit_table(report)}
    <p>口径：六星间隔按池独立统计，不跨池合并；理论位置是模型推算，不是全服排名。{pity_note}</p>
  </details>

  <footer class="footer">
    <div class="tri"><span class="mark">◇</span> RHODES ISLAND <span>· ARKBOX ARCHIVE</span></div>
    {_barcode(report["privacy"]["barcode_seed"])}
    <div class="foot-line">{_h(cov.get("short"))} · 99 抽为六星硬保底 · 非官方玩家工具 · 数据本地 / 头像公开 CDN · 生成于 {date_str}</div>
  </footer>
</main>
<script>
(function() {{
  var title = document.getElementById('hero-title');
  var caption = document.getElementById('hero-caption');
  var chips = document.querySelectorAll('.title-chip');
  chips.forEach(function(chip) {{
    chip.addEventListener('click', function() {{
      chips.forEach(function(c) {{ c.classList.remove('active'); c.setAttribute('aria-pressed','false'); }});
      chip.classList.add('active');
      chip.setAttribute('aria-pressed','true');
      title.textContent = chip.dataset.label;
      caption.textContent = chip.dataset.caption || '';
    }});
  }});
  var shareChips = document.querySelectorAll('.share-chip');
  var shareText = document.getElementById('share-text');
  shareChips.forEach(function(chip) {{
    chip.addEventListener('click', function() {{
      shareChips.forEach(function(c) {{ c.classList.remove('active'); }});
      chip.classList.add('active');
      if (shareText) shareText.innerText = chip.dataset.text;
    }});
  }});
  var btn = document.getElementById('copy-btn');
  var text = document.getElementById('share-text');
  if (btn && text) {{
    btn.addEventListener('click', function() {{
      var value = text.innerText;
      function done() {{ btn.textContent = '已复制'; setTimeout(function() {{ btn.textContent = '复制文案'; }}, 1600); }}
      if (navigator.clipboard && navigator.clipboard.writeText) {{
        navigator.clipboard.writeText(value).then(done).catch(function() {{ fallback(); }});
      }} else {{ fallback(); }}
      function fallback() {{
        var ta = document.createElement('textarea'); ta.value = value; document.body.appendChild(ta);
        ta.select(); try {{ document.execCommand('copy'); done(); }} catch (e) {{}}
        document.body.removeChild(ta);
      }}
    }});
  }}
}})();
</script>
</body></html>'''
    out_path = os.path.expanduser(out_path)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_text)
    return out_path


CSS = """
:root{
  --paper:#F4F4F1;--ink:#151718;--blue:#0098DC;--gold:#B8860B;--red:#C82A36;
  --dim:rgba(21,23,24,.64);--dim2:rgba(21,23,24,.46);--line:rgba(21,23,24,.18);
  --card:rgba(255,255,255,.66);
}
*{margin:0;padding:0;box-sizing:border-box}
html{background:#E9E9E4}
body{background:var(--paper);color:var(--ink);font:16px/1.6 -apple-system,'PingFang SC','Helvetica Neue',sans-serif;position:relative;min-height:100vh}
.grid{position:fixed;inset:0;pointer-events:none;background-image:linear-gradient(rgba(21,23,24,.05) 1px,transparent 1px),linear-gradient(90deg,rgba(21,23,24,.05) 1px,transparent 1px);background-size:32px 32px}
.site-note{font:700 9px 'SF Mono',Menlo,monospace;color:var(--blue);letter-spacing:.4px;margin:0 0 10px;padding:5px 7px;border:1px solid rgba(0,152,220,.28);background:rgba(0,152,220,.05)}
.hazard{height:10px;background:linear-gradient(90deg,#151718 0 46%,#0098DC 46% 54%,#151718 54% 100%)}
.wrap{position:relative;max-width:860px;margin:0 auto;padding:22px 18px 42px}
.header{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}
.header-left{min-width:0;flex:1}
.kicker{display:flex;justify-content:space-between;gap:8px;font:700 9px 'SF Mono',Menlo,monospace;color:var(--blue);letter-spacing:1px}
.kicker .file{color:var(--dim2);letter-spacing:.5px}
h1{font-size:28px;font-weight:900;letter-spacing:.5px;margin-top:5px}
h1 b{color:var(--blue)}
.doctor{margin-top:5px;font:600 11px 'SF Mono',Menlo,monospace;color:var(--dim);display:flex;gap:6px;flex-wrap:wrap;align-items:center}
.doctor b{color:var(--ink)}
.tenure{color:var(--blue);font-weight:700;white-space:nowrap}
.chip{font:700 10px 'SF Mono',Menlo,monospace;color:var(--blue);border:1px solid rgba(0,152,220,.4);padding:2px 6px;background:rgba(255,255,255,.5)}
.seal{width:78px;height:78px;border:3px solid rgba(200,42,54,.8);border-radius:50%;transform:rotate(9deg);display:flex;align-items:center;justify-content:center;flex:0 0 auto}
.seal-in{text-align:center;color:rgba(200,42,54,.85);border:2px solid rgba(200,42,54,.45);border-radius:50%;width:64px;height:64px;display:flex;flex-direction:column;justify-content:center;gap:1px}
.seal .s1{font:900 8px 'SF Mono',Menlo;letter-spacing:1px}
.seal .s2{font-size:7px}
.seal .s3{font-size:8px;font-weight:700}
.hero{margin:18px 0 6px}
#hero-title{display:inline-block;background:var(--ink);color:#fff;border-left:9px solid var(--blue);font-size:42px;font-weight:900;line-height:1.15;padding:7px 22px 10px;transform:rotate(-1.5deg);clip-path:polygon(2% 8%,98% 0,100% 88%,0 100%);letter-spacing:2px;box-shadow:0 7px 20px rgba(0,152,220,.12)}
#hero-caption{margin-top:10px;font-size:15px;color:var(--dim);line-height:1.5}
.tags{display:flex;gap:6px;margin-top:9px;flex-wrap:wrap}
.tag{font:800 13px -apple-system,'PingFang SC';padding:3px 8px;border:1px solid var(--line);letter-spacing:.2px}
.tag.gold{color:var(--gold);border-color:rgba(184,134,11,.5);background:rgba(184,134,11,.06)}
.tag.black{background:var(--ink);color:#fff;border-color:var(--ink)}
.tag.blue{color:var(--blue);border-color:rgba(0,152,220,.45);background:rgba(0,152,220,.05)}
.summary{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:14px}
.stat{background:var(--card);border:1px solid rgba(21,23,24,.22);padding:11px 12px 9px;clip-path:polygon(0 0,calc(100% - 11px) 0,100% 11px,100% 100%,0 100%)}
.stat .v{font:800 40px/1 'SF Mono',Menlo,monospace;letter-spacing:-1px}
.stat.gold .v{color:var(--gold)}
.stat.blue .v{color:var(--blue)}
.stat .l{font-size:17px;font-weight:800;margin-top:4px}
.stat .s{font:500 11px 'SF Mono',Menlo,monospace;color:var(--dim2);margin-top:2px;line-height:1.35}
.overall{font:500 11px 'SF Mono',Menlo,monospace;color:var(--dim2);margin-top:7px;line-height:1.5}
.banner{display:grid;grid-template-columns:repeat(3,1fr);background:var(--blue);color:#fff;margin-top:12px;clip-path:polygon(0 0,100% 0,100% calc(100% - 9px),calc(100% - 9px) 100%,0 100%)}
.bcell{padding:8px 8px 9px;border-left:1px solid rgba(255,255,255,.35);min-width:0}
.bcell:first-child{border-left:0}
.bk{display:block;font-size:12px;font-weight:800;opacity:.9}
.bv{display:block;font:900 22px 'SF Mono',Menlo;letter-spacing:-1px;line-height:1.2}
.bx{display:block;font:600 9px 'SF Mono',Menlo;opacity:.92;line-height:1.35;margin-top:1px;overflow:hidden;text-overflow:ellipsis}
.section{display:flex;align-items:center;gap:8px;margin:24px 0 8px}
.section .num{font:700 10px 'SF Mono',Menlo;color:var(--blue);letter-spacing:1px}
.section .t{font-size:19px;font-weight:900;letter-spacing:.5px}
.section .line{flex:1;height:1px;background:var(--line)}
.note{font:500 11px 'SF Mono',Menlo;color:var(--dim2);line-height:1.6;margin:2px 0 10px}
.pool{background:var(--card);border:1px solid rgba(21,23,24,.22);padding:13px 13px 11px;margin-bottom:10px;clip-path:polygon(0 0,calc(100% - 12px) 0,100% 12px,100% 100%,0 100%)}
.pool.featured{border-color:rgba(0,152,220,.42);box-shadow:0 4px 16px rgba(0,152,220,.06)}
.pool-head{display:flex;align-items:flex-start;justify-content:space-between;gap:8px;flex-wrap:wrap}
.pool-title{display:flex;align-items:center;gap:6px;flex-wrap:wrap;min-width:0}
.pool-title h3{font-size:24px;font-weight:900;letter-spacing:.3px}
.pool-count{font:700 12px 'SF Mono',Menlo;color:var(--dim);white-space:nowrap}
.pool-count b{font-size:18px;color:var(--ink)}
.ptag{font:800 10px -apple-system,'PingFang SC';padding:2px 6px;border:1px solid transparent;white-space:nowrap}
.ptag.lim{background:var(--blue);color:#fff}
.ptag.link{background:#fff;color:var(--ink);border-color:var(--line)}
.ptag.std{background:rgba(21,23,24,.06);color:var(--dim);border-color:var(--line)}
.ptag.other{background:#fff;color:var(--dim);border-color:var(--line)}
.ptag.plain{background:rgba(255,255,255,.7);color:var(--dim);border-color:var(--line)}
.ptag.recent{background:var(--blue);color:#fff}
.pool-meta{font:500 10px 'SF Mono',Menlo;color:var(--dim2);margin-top:3px}
.pool-story{font-size:14px;font-weight:800;margin-top:5px;color:rgba(21,23,24,.78)}
.ops{display:flex;gap:7px;flex-wrap:wrap;align-items:flex-start;margin-top:9px}
.op{position:relative;width:56px;flex:0 0 auto}
.op.big{width:82px}
.op .avatar{position:relative;aspect-ratio:1;background:rgba(21,23,24,.06);border:1px solid var(--line);overflow:hidden}
.op img{position:relative;z-index:1;width:100%;height:100%;object-fit:cover;display:block}
.op .fallback{display:flex;position:absolute;inset:0;align-items:center;justify-content:center;font:900 22px 'SF Mono',Menlo;color:var(--dim2);background:rgba(21,23,24,.04);z-index:0}
.op .avatar.noimg .fallback{display:flex}
.op .nm{background:#000;color:#fff;font:700 9px -apple-system,'PingFang SC';text-align:center;padding:2px 1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.op.big .nm{font-size:11px}
.op .pull{font:500 8px 'SF Mono',Menlo;color:var(--dim2);text-align:center;margin-top:1px;white-space:nowrap}
.op.big .pull{font-size:9px}
.op .badge{position:absolute;top:2px;left:2px;background:var(--red);color:#fff;font:800 8px -apple-system;padding:1px 3px;z-index:2}
.op .badge.dup{background:var(--gold);left:auto;right:2px}
.more{width:56px;height:82px;display:flex;align-items:center;justify-content:center;font:800 16px 'SF Mono',Menlo;color:var(--dim2);border:1px dashed var(--line)}
.bar-row{margin-top:9px}
.bar-row.spark{margin-top:7px}
.bar-info{display:flex;justify-content:space-between;gap:8px;font:600 10px 'SF Mono',Menlo;color:var(--dim);margin-bottom:3px}
.bar-info b{color:var(--ink)}
.bar{height:6px;background:rgba(21,23,24,.08);border:1px solid var(--line);position:relative;overflow:hidden}
.bar i{display:block;height:100%;background:var(--blue)}
.bar-row.spark .bar i{background:var(--gold)}
.bar-note{font:500 9px 'SF Mono',Menlo;color:var(--dim2);margin-top:2px;line-height:1.4}
.tl{margin-top:12px}
.tl-track{position:relative;height:8px;background:rgba(21,23,24,.07);border:1px solid var(--line);margin-top:14px}
.seg{position:absolute;top:0;height:100%}
.seg.g{background:var(--blue)}
.seg.m{background:var(--gold)}
.seg.r{background:var(--red)}
.seg.p{background:repeating-linear-gradient(45deg,rgba(21,23,24,.35) 0 3px,rgba(21,23,24,.08) 3px 6px)}
.dot{position:absolute;top:-5px;width:2px;height:18px;background:var(--ink)}
.tl-label{position:absolute;top:-17px;transform:translateX(-50%);font:800 9px 'SF Mono',Menlo;white-space:nowrap}
.tl-label.r{color:var(--red)}
.tl-label.b{color:var(--blue)}
.tl-ends{display:flex;justify-content:space-between;font:500 9px 'SF Mono',Menlo;color:var(--dim2);margin-top:2px}
.events{margin-top:11px;border-top:1px solid var(--line)}
.event{display:grid;grid-template-columns:54px 1fr 84px 60px;gap:4px;align-items:baseline;padding:5px 0;border-bottom:1px solid rgba(21,23,24,.08);font:500 10px 'SF Mono',Menlo}
.e-at{color:var(--dim2)}
.e-name{font:700 11px -apple-system,'PingFang SC';color:var(--ink)}
.e-name span{font:700 9px 'SF Mono',Menlo;margin-left:4px;color:var(--dim2)}
.e-name .up{color:var(--gold)}
.e-name .off{color:var(--red)}
.e-gap{color:var(--red);text-align:right;white-space:nowrap}
.e-date{color:var(--dim2);text-align:right;font-size:9px;white-space:nowrap}
.empty{font:500 11px 'SF Mono',Menlo;color:var(--dim2);padding:10px 0}
.types{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.type-card{background:var(--card);border:1px solid var(--line);padding:11px 12px}
.type-top{display:flex;justify-content:space-between;gap:8px;font:800 13px -apple-system,'PingFang SC'}
.type-top span{font:700 10px 'SF Mono',Menlo;color:var(--dim2)}
.type-nums{display:flex;gap:8px;flex-wrap:wrap;font:500 9px 'SF Mono',Menlo;color:var(--dim);margin-top:5px}
.type-pools{font:500 9px 'SF Mono',Menlo;color:var(--dim2);margin-top:4px;line-height:1.4}
.compare{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:9px;background:var(--card);border:1px solid var(--line);padding:10px}
.cmp-card{border-right:1px solid var(--line);padding-right:8px}
.cmp-card:nth-child(2){border-right:0}
.cmp-k{display:block;font:700 9px 'SF Mono',Menlo;color:var(--blue);letter-spacing:.5px}
.cmp-card b{display:block;font-size:13px;margin-top:2px}
.cmp-card strong{display:block;font:900 30px 'SF Mono',Menlo;letter-spacing:-1px;line-height:1.1}
.cmp-s{display:block;font:500 8px 'SF Mono',Menlo;color:var(--dim2)}
.cmp-delta{grid-column:1 / -1;border-top:1px solid var(--line);padding-top:6px;font:600 9px 'SF Mono',Menlo;color:var(--dim)}
.cmp-delta b{color:var(--red)}
.cmp-delta span{color:var(--dim2)}
.title-chips{display:flex;gap:6px;flex-wrap:wrap}
.title-chip{font:800 13px -apple-system,'PingFang SC';padding:6px 10px;border:1px solid var(--line);background:rgba(255,255,255,.6);color:var(--dim);cursor:pointer}
.title-chip.active{background:var(--ink);color:#fff;border-color:var(--ink)}
.title-chip:focus-visible{outline:2px solid var(--blue);outline-offset:2px}
.share-box{background:var(--card);border:1px solid var(--line);padding:12px}
.share-box p{font-size:13px;line-height:1.65;color:rgba(21,23,24,.82);white-space:pre-wrap;margin-top:8px}
.share-chips{display:flex;gap:5px;flex-wrap:wrap}
.share-chip{font:700 10px 'SF Mono',Menlo;padding:4px 7px;border:1px solid var(--line);background:rgba(255,255,255,.55);color:var(--dim);cursor:pointer}
.share-chip.active{background:var(--blue);border-color:var(--blue);color:#fff}
.copy{margin-top:9px;font:800 12px -apple-system,'PingFang SC';background:var(--blue);color:#fff;border:0;padding:7px 12px;cursor:pointer}
.copy:active{transform:translateY(1px)}
.privacy{font:500 9px 'SF Mono',Menlo;color:var(--dim2);margin-top:8px;line-height:1.5}
.gaps{display:grid;gap:7px}
.gap-card{background:rgba(184,134,11,.06);border-left:4px solid var(--gold);padding:8px 10px}
.gap-card b{font-size:12px}
.gap-card p{font:500 10px 'SF Mono',Menlo;color:var(--dim);line-height:1.55;margin-top:2px}
.privacy-box{margin-top:9px;background:rgba(0,152,220,.05);border-left:4px solid var(--blue);padding:8px 10px}
.privacy-box b{font-size:12px}
.privacy-box p{font:500 10px 'SF Mono',Menlo;color:var(--dim);line-height:1.55;margin-top:2px}
.audit{margin-top:20px;background:var(--card);border:1px solid var(--line);padding:12px 12px 14px;font-size:11px}
.audit summary{cursor:pointer;font-weight:800;color:var(--dim)}
.audit h3{font-size:12px;margin:14px 0 6px}
.table-wrap{overflow-x:auto;border:1px solid var(--line)}
.audit table{border-collapse:collapse;min-width:620px;width:100%;font-size:9px}
.audit th,.audit td{border-bottom:1px solid var(--line);padding:5px 4px;text-align:left;vertical-align:top}
.audit th{color:var(--dim2);font-weight:600;white-space:nowrap}
.audit p{font:500 10px 'SF Mono',Menlo;color:var(--dim2);line-height:1.55;margin-top:8px}
.footer{margin-top:26px;padding-top:10px;border-top:1px solid var(--line)}
.footer .tri{font:700 9px 'SF Mono',Menlo;color:var(--dim2);letter-spacing:1px}
.footer .mark{color:var(--blue)}
.footer .barcode{display:flex;align-items:flex-end;height:16px;margin:7px 0}
.footer .barcode i{background:var(--ink);height:100%;display:block}
.foot-line{font:500 9px 'SF Mono',Menlo;color:var(--dim2);line-height:1.55}
@media (max-width:430px){
  .kicker .file{display:none}
}
@media (max-width:380px){
  .wrap{padding:18px 13px 36px}
  h1{font-size:25px}
  #hero-title{font-size:36px}
  .stat .v{font-size:35px}
  .stat .l{font-size:15px}
  .pool-title h3{font-size:21px}
  .event{grid-template-columns:50px 1fr 78px 62px;font-size:8px}
  .e-date{font-size:8px}
  .types{grid-template-columns:1fr}
  .kicker .file{display:none}
  .kicker{font-size:9px;letter-spacing:1px}
}
@media (min-width:700px){
  .summary{grid-template-columns:repeat(4,1fr)}
  .types{grid-template-columns:repeat(3,1fr)}
  #hero-title{font-size:48px}
  .pool{padding:16px}
  .op{width:64px}.op.big{width:96px}
}
@media print{
  .grid,.hazard,.copy,.title-chips{display:none}
  body{background:#fff}
  .wrap{max-width:none}
  .audit{break-inside:avoid}
}
"""
