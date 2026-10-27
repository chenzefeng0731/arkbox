#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""明日方舟寻访（抽卡）记录分析 v0.6（P1/P2 交付版）。

用法:
  python3 ark_gacha.py analyze [--pool 关键词] [--limit N] [--detail]
                               [--html] [--poster]
                               [--site --site-dir site] [--json] [--audit] [--keep-poster-source]
                               [--privacy full|mask|hide] [--hide-nick]
                               [--theme A|B]
  python3 ark_gacha.py analyze --records 记录.json [--nick 昵称] [--uid UID]
  python3 ark_gacha.py fetch [--out file.json]

v0.6 要点:
- 官方 99 抽硬保底；按池独立统计，不跨池合并
- “池内间隔均值 / 整体效率 / 当前垫抽 / 最长池内间隔”四口径分开
- 称号候选、分享文案变体、兑换井、池型对照、单池时间线、数据缺口
- B 版海报：最新池优先 + 手机可读；HTML：响应式长报告 + 可点选称号
- 默认交付只留 poster.png + report.html/site；海报源 HTML 默认删除
- --site 生成公开站点目录（博士、UID 隐藏、noindex）
- 默认遮挡 UID；--audit 输出数据校验清单
- 三形态统一消费 ark_report.build_report()
"""

import argparse
import json
import os
import shutil
import webbrowser
import sys
import time
from collections import defaultdict
from datetime import datetime

from skland_core import (
    ArkApiError, load_creds, gacha_categories, gacha_history_all, ensure_auth,
)
from ark_odds import gap_report
from ark_pools import PoolUpIndex
from ark_archive import merge as archive_merge, load as archive_load, coverage_report

# Windows 终端默认编码（cp1252/GBK）无法输出 ⚠/✓ 等符号：统一强制 UTF-8 输出
for _stdio in (sys.stdout, sys.stderr):
    try:
        _stdio.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
from ark_domains import build_pool_stats, apply_pool_meta
from ark_report import build_report, verify_report


RARE_NAME = {6: "六星", 5: "五星", 4: "四星", 3: "三星", 2: "二星", 1: "一星"}


def fmt_ts(ms):
    try:
        return datetime.fromtimestamp(int(ms) / 1000).strftime("%Y-%m-%d")
    except (ValueError, OSError):
        return "?"


def _extract_ten_pulls(rs_sorted, six_star_at, pool_name):
    """识别同一时间戳下的十连，返回 [{pulls, six_count, six_names, ...}]。"""
    groups = defaultdict(list)
    for r in rs_sorted:
        groups[r.get("gachaTs")].append(r)
    out = []
    for ts, group in groups.items():
        group = sorted(group, key=lambda r: (int(r.get("gachaTs") or 0), r.get("pos") or 0))
        for start in range(0, len(group), 10):
            chunk = group[start:start + 10]
            if len(chunk) < 10:
                continue
            six = [(i + 1, r) for i, r in enumerate(chunk)
                   if r.get("rarity", 0) >= six_star_at]
            if not six:
                continue
            out.append({
                "ts": int(ts),
                "date": fmt_ts(ts),
                "pool": pool_name,
                "pulls": len(chunk),
                "six_count": len(six),
                "six_names": [r.get("charName") for _, r in six],
                "positions": [i for i, _ in six],
            })
    out.sort(key=lambda x: (x["six_count"], x["ts"]), reverse=True)
    return out


def analyze_records(records, pool_index=None):
    """按卡池分组统计，附池型、UP 判定、十连与重复六星。"""
    pools = defaultdict(list)
    for r in records:
        pools[(r.get("poolId") or "", r.get("poolName") or "未知卡池")].append(r)

    max_rarity = max((r.get("rarity", 0) for r in records), default=0)
    six_star_at = 6 if max_rarity >= 6 else 5

    result = []
    for (pool_id, pool_name), rs in pools.items():
        rs_sorted = sorted(rs, key=lambda r: (int(r["gachaTs"]), r.get("pos") or 0))
        six = []
        for i, r in enumerate(rs_sorted, 1):
            if r.get("rarity", 0) >= six_star_at:
                six.append({
                    "at_pull": i,
                    "name": r.get("charName"),
                    "char_id": r.get("charId"),
                    "date": fmt_ts(r["gachaTs"]),
                    "ts": int(r["gachaTs"]),
                    "pos": r.get("pos"),
                    "is_new": bool(r.get("isNew")),
                })
        gaps, prev = [], 0
        for s in six:
            gaps.append(s["at_pull"] - prev)
            prev = s["at_pull"]
        gr = gap_report(gaps)

        meta = pool_index.info(pool_id) if pool_index else {}
        up_verdict = None
        if pool_index and six:
            up_verdict = pool_index.judge(pool_id, [s["char_id"] for s in six])
            if up_verdict.get("known"):
                for s, is_up in zip(six, up_verdict["results"]):
                    if is_up is not None:
                        s["is_up"] = is_up

        ten_pulls = _extract_ten_pulls(rs_sorted, six_star_at, pool_name)

        dup_map = {}
        for s in six:
            cid = s["char_id"]
            if cid not in dup_map:
                dup_map[cid] = {"char_id": cid, "name": s["name"], "count": 0}
            dup_map[cid]["count"] += 1
        duplicates = sorted(dup_map.values(), key=lambda x: (-x["count"], x["name"] or ""))

        since_last = len(rs_sorted) - (six[-1]["at_pull"] if six else 0)
        result.append({
            "pool_id": pool_id,
            "pool": pool_name,
            "pool_type": meta.get("pool_type", "unknown"),
            "pool_type_label": meta.get("pool_type_label", "池型待核"),
            "limited": bool(meta.get("limited")),
            "rate_up_label": meta.get("rate_up_label"),
            "pity_domain": meta.get("pity_domain") or f"unknown:{pool_id}",
            "pity_domain_label": meta.get("pity_domain_label") or "池型待核",
            "domain_shared": bool(meta.get("domain_shared")),
            "total": len(rs_sorted),
            "first_ts": fmt_ts(rs_sorted[0]["gachaTs"]),
            "last_ts": fmt_ts(rs_sorted[-1]["gachaTs"]),
            "six_stars": six,
            "six_count": len(six),
            "gaps": gaps,
            "avg_gap": gr["avg_gap"] if gr else None,
            "worst_gap": gr["worst"] if gr else None,
            "best_gap": gr["best"] if gr else None,
            "since_last_six": since_last,
            "up_verdict": up_verdict,
            "ten_pulls": ten_pulls,
            "duplicates": [d for d in duplicates if d["count"] >= 2],
        })
    result.sort(key=lambda p: (p["first_ts"], p["pool"]))
    return result, six_star_at


# ---------------------------------------------------------------- Markdown

def _md(s):
    return str(s if s is not None else "—").replace("|", "\\|")


def _up_text(p):
    uv = p.get("up_verdict")
    if not uv:
        return "待核" if p["six_count"] else "—"
    if not uv.get("known"):
        return "待核"
    hit, total = uv.get("hit_count", 0), uv.get("total", 0)
    if hit == total:
        return f"{hit}/{total}"
    return f"{hit}/{total}（歪 {total - hit}）"


def _audit_markdown(report):
    lines = ["### 数据口径校验", "",
             "| 指标 | 原始值 | 公式/口径 | 显示值 | 一致 |",
             "|---|---|---|---|---|"]
    for row in report["audit"]:
        lines.append(
            f"| {_md(row['指标'])} | {_md(row['原始值'])} | {_md(row['公式/口径'])} "
            f"| {_md(row['显示值'])} | {'✓' if row['一致'] else '✗'} |"
        )
    if report.get("verification"):
        lines.append("")
        lines.append("**校验失败：** " + "；".join(report["verification"]))
    return "\n".join(lines)


def render_markdown(report, stats, detail=False, limit=None, with_audit=False):
    lines = [f"## 寻访档案 · {report['doctor']['nick']}", ""]
    lines.append(f"> **{report['title']['label']}** — {report['title']['caption']}")
    lines.append("")
    lines.append(f"- 本区间 **{report['totals']['pulls']}** 抽，六星 **{report['totals']['six']}** 位；"
                 f"{report['lines']['metric']}。")
    lines.append(f"- 理论位置：**{report['luck']['label']}**（期望 {report['luck']['expected_gap']} 抽/六星；"
                 f"{report['luck']['caveat']}）。")
    lines.append(f"- {report['lines']['pity']}。")
    lines.append(f"- {report['lines']['worst']}；{report['lines']['best']}。")
    lines.append(f"- {report['lines']['up']}。")
    coverage_line = (report.get("coverage") or {}).get("line") or "暂无记录"
    lines.append(f"- 覆盖：{coverage_line.replace('数据档案：', '', 1)}")
    if report.get("tenure"):
        lines.append(f"- 入职：{report['tenure']['register_date']}（{report['tenure']['days']} 天）")
    if report["pools"]["other_line"]:
        lines.append(f"- 展示：{report['pools']['other_line']}")
    else:
        lines.append(f"- 展示：{report['pools']['display_note']}")
    lines.append(f"- 版本：ArkBox v0.6 · {report['lines']['model']}")
    titles = " / ".join(x["label"] for x in report.get("title_candidates") or [])
    if titles:
        lines.append(f"- 称号候选：{titles}")
    sparks = " / ".join(
        f'{p["pool"]} {p["spark"]["pulls"]}/{p["spark"]["threshold"]}'
        + ("（已到井）" if p["spark"]["reached"] else f'（还差 {p["spark"]["remaining"]}）')
        for p in report.get("pool_stats") or [] if p.get("spark")
    )
    if sparks:
        lines.append(f"- 兑换井：{sparks}（按档案内当期抽数估算）")
    gaps = " / ".join(x["title"] for x in report.get("data_gaps") or [])
    if gaps:
        lines.append(f"- 数据缺口：{gaps}")

    pool_stats = report.get("pool_stats") or []
    if pool_stats:
        lines.append("\n### 按池独立与数据完整性\n")
        lines.append("| 卡池 | 池型 | 抽数 | 六星 | 池内均值 | 当前垫 | 记录范围 | 首段 |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for p in pool_stats:
            first = p.get("first_gap_note") or "首段自档案首条记录起算"
            lines.append(
                f"| {_md(p['pool'])} | {_md(p['pool_type_label'])} | {p['total']} | {p['six_count']} "
                f"| {p['mean_gap'] if p['mean_gap'] is not None else '—'} | {p['current']} "
                f"| {p['first_ts']} ~ {p['last_ts']} | {_md(first)} |"
            )
        lines.append("")
        lines.append("> 口径：六星间隔按池独立统计，不跨池合并。官方规则中标准/中坚六星计数跨同类型池累计，"
                     "但森空岛只返回可查窗口内的记录，无法证明更早历史完整，因此本工具不采用跨池口径。")
        lines.append("> 每池从档案内首条记录起算，首段可能承接档案外垫抽；当前垫也只反映档案内可见部分。"
                     "理论位置为模型推算，不是全服排名。")

    pool_source = report.get("pools", {}).get("all") or stats
    pool_source = sorted(pool_source, key=lambda p: (p.get("last_ts") or "", p.get("first_ts") or ""), reverse=True)
    pools = pool_source[:limit] if limit else pool_source
    if limit:
        lines.append(f"\n> 表格仅显示最近 {len(pools)} 池；上方汇总仍为本区间。")
    lines.append("")
    lines.append("| 卡池 | 池型 | 抽数 | 六星 | 池内均值 | 六星垫 | UP | 最长间隔 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for p in pools:
        lines.append(
            f"| {_md(p['pool'])} | {_md(p['pool_type_label'])} | {p['total']} | {p['six_count']} "
            f"| {p['avg_gap'] if p.get('avg_gap') is not None else '—'} "
            f"| {p.get('display_pity', p.get('current_pity', 0))} "
            f"| {_md(_up_text(p))} | {p['worst_gap'] if p.get('worst_gap') is not None else '—'} |"
        )

    share = report.get("share") or {}
    if share.get("text"):
        lines.append("\n### 分享文案")
        lines.append("")
        lines.append("```text")
        lines.append(share["text"])
        lines.append("```")

    if detail:
        lines.append("\n### 六星详情")
        lines.append("")
        for p in pools:
            if not p["six_stars"]:
                continue
            lines.append(f"**{p['pool']}**（{p['pool_type_label']}）")
            for s in p["six_stars"]:
                if s.get("is_up") is True:
                    mark = " UP"
                elif s.get("is_up") is False:
                    mark = " 歪"
                elif p.get("up_verdict") and not p["up_verdict"].get("known"):
                    mark = " UP待核"
                else:
                    mark = ""
                lines.append(f"- 第 {s['at_pull']} 抽：{s['name']}（{s['date']}）{mark}")
            lines.append("")

    if with_audit:
        lines.append("")
        lines.append(_audit_markdown(report))
    lines.append("")
    lines.append("ArkBox 本地生成 · 非官方玩家工具 · 数据仅存本地 · 头像来自公开 CDN")
    return "\n".join(lines)


# ---------------------------------------------------------------- HTML

def render_html(report, stats, out_path, limit=None, site_mode=False, chars=None,
                profile=None, poster_b64=None, poster_terra_b64=None):
    """全能档案页（v1.0）：有 chars → 两页签（寻访/泰拉）+ 分享弹层；无 → 单页报告。"""
    from ark_archive_html import build_archive_html
    return build_archive_html(report, chars, out_path, site_mode=site_mode, limit=limit,
                              profile=profile, poster_b64=poster_b64,
                              poster_terra_b64=poster_terra_b64)


# ---------------------------------------------------------------- Poster

def _find_browser():
    """跨平台找 Chrome/Edge/Chromium；找不到就只交付 HTML。"""
    home = os.path.expanduser("~")
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        os.path.join(home, "Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        os.path.join(home, "Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
    ]
    for name in ("google-chrome", "google-chrome-stable", "chromium",
                 "chromium-browser", "microsoft-edge", "microsoft-edge-stable",
                 "chrome", "msedge"):
        found = shutil.which(name)
        if found:
            candidates.append(found)
    for env in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        base = os.environ.get(env)
        if base:
            candidates.extend([
                os.path.join(base, "Google/Chrome/Application/chrome.exe"),
                os.path.join(base, "Microsoft/Edge/Application/msedge.exe"),
            ])
    return next((c for c in candidates if c and os.path.exists(c)), None)


def _screenshot_html(html_path, png, width, height):
    chrome = _find_browser()
    if not chrome:
        return None
    import subprocess
    try:
        subprocess.run([chrome, "--headless", "--disable-gpu", "--hide-scrollbars",
                        # 2x 渲染：README/社媒展示会缩图，1x 物理像素在高分屏下发虚
                        "--force-device-scale-factor=2",
                        f"--screenshot={png}", f"--window-size={width},{height}",
                        f"file://{os.path.abspath(html_path)}"],
                       capture_output=True, timeout=60)
    except (subprocess.TimeoutExpired, OSError) as e:
        print(f"  ⚠ 浏览器截图失败（交付 HTML，可自行截图）: {e}", file=sys.stderr)
        return None
    return png if os.path.exists(png) else None


def _drop_source(path, keep_source):
    if not keep_source:
        try:
            os.remove(path)
        except OSError:
            pass


def _open_path(path):
    if os.environ.get("ARKBOX_NO_OPEN"):
        return  # CI / 自动化环境不弹浏览器
    try:
        webbrowser.open("file://" + os.path.abspath(os.path.expanduser(path)))
    except Exception:
        pass


def export_poster_png(report, html_path, theme="B", keep_source=False):
    """海报 HTML + 浏览器 headless 截 PNG（电脑生成、手机竖屏传播 3:4）。"""
    from ark_poster import render_poster
    render_poster(report, html_path, theme=theme)
    png = html_path[:-5] + ".png"
    ok = _screenshot_html(html_path, png, 1080, 1440)
    if ok:
        _drop_source(html_path, keep_source)
        return html_path, png
    return html_path, None


def _render_share_posters(report, chars, out_dir, ts):
    """--html 时顺手把两张分享海报渲染成 PNG（Chrome headless）并读回 base64。

    寻访走 ark_poster_v4；泰拉走 ark_poster_terra（同一设计体系）。
    渲染失败不阻断档案页：对应页签退回页面内 canvas 兜底或提示。
    """
    import base64
    posters = {}
    tmp = os.path.join(out_dir, f"_share_gacha_{ts}.html")
    try:
        from ark_poster_v4 import render_poster_v4
        render_poster_v4(report, report["pools"]["all"], tmp)
        png = _screenshot_html(tmp, tmp[:-5] + ".png", 1080, 1440)
        if png:
            with open(png, "rb") as f:
                posters["gacha"] = base64.b64encode(f.read()).decode("ascii")
            try:
                os.remove(png)
            except OSError:
                pass
    except Exception as e:
        print(f"  ⚠ 寻访分享海报渲染失败（档案页仍可生成）: {e}", file=sys.stderr)
    finally:
        _drop_source(tmp, keep_source=False)

    if chars:
        tmp2 = os.path.join(out_dir, f"_share_terra_{ts}.html")
        try:
            from ark_archive_html import build_features
            from ark_meta import load_meta
            from ark_poster_terra import render_poster_terra
            from ark_terra import build_terra
            meta = load_meta()
            owned = {c["char_id"] for c in chars}
            nick = report.get("doctor", {}).get("nick") or "博士"
            date_str = report.get("generated") or datetime.now().strftime("%Y.%m.%d")
            terra = build_terra(meta, owned, nick=nick, date=date_str)
            # 六维与页面雷达同口径：剔除 rar=0 占位（审计 D-01，359 口径）
            feat = build_features([c for c in chars if (c.get("rarity") or 0) > 0], terra)
            render_poster_terra(terra, feat, nick, date_str, tmp2, meta=meta)
            png2 = _screenshot_html(tmp2, tmp2[:-5] + ".png", 1080, 1440)
            if png2:
                with open(png2, "rb") as f:
                    posters["terra"] = base64.b64encode(f.read()).decode("ascii")
                try:
                    os.remove(png2)
                except OSError:
                    pass
        except Exception as e:
            print(f"  ⚠ 泰拉分享海报渲染失败（泰拉页签退回 canvas）: {e}", file=sys.stderr)
        finally:
            _drop_source(tmp2, keep_source=False)
    return posters


# ---------------------------------------------------------------- CLI

RECORDS_URL_MAX_BYTES = 20 * 1024 * 1024  # 离线记录链接的下载上限


def _load_records_file(path):
    """读取离线记录：本地 JSON/JSONL，或显式传入的 https JSON 链接。"""
    if str(path).startswith(("http://", "https://")):
        url = str(path)
        if not url.startswith("https://"):
            raise ValueError("记录链接仅支持 https")
        import urllib.request
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = resp.read(RECORDS_URL_MAX_BYTES + 1)
            if len(data) > RECORDS_URL_MAX_BYTES:
                raise ValueError("记录文件超过 20MB 上限")
            text = data.decode("utf-8")
    else:
        with open(os.path.expanduser(path), encoding="utf-8") as f:
            text = f.read()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            recs = data
        elif isinstance(data, dict):
            wrapped = data.get("records")
            if not isinstance(wrapped, list):
                wrapped = data.get("list")
            if isinstance(wrapped, list):
                recs = wrapped
            elif data.get("poolId") and data.get("gachaTs"):
                recs = [data]
            else:
                recs = []
        else:
            recs = []
    except json.JSONDecodeError:
        recs = [json.loads(line) for line in text.splitlines() if line.strip()]
    if not recs:
        raise ValueError("记录为空")
    for r in recs:
        if not isinstance(r, dict) or not r.get("poolId") or not r.get("gachaTs"):
            raise ValueError("每条记录至少需要 poolId 和 gachaTs")
    return recs


def _demo_tenure(date_str):
    """--tenure YYYY-MM-DD → 页头演示入职信息；无效则返回 None。"""
    if not date_str:
        return None
    try:
        from ark_profile import build_tenure
        return build_tenure({"status": {"registerTs": int(
            datetime.strptime(date_str, "%Y-%m-%d").timestamp())}})
    except ValueError:
        print(f"警告: --tenure 日期格式应为 YYYY-MM-DD，已忽略：{date_str}", file=sys.stderr)
        return None


def _finish_analysis(analyze_src, nick, cov, args, chars=None, profile=None):
    pool_index = None
    if not getattr(args, "no_up", False):
        pool_index = PoolUpIndex()
        if not pool_index.table:
            print("（卡池表不可用，UP/池型显示待核）", file=sys.stderr)

    stats, _ = analyze_records(analyze_src, pool_index)
    pool_data = build_pool_stats(analyze_src, pool_index)
    apply_pool_meta(stats, pool_data)
    tenure = None
    if getattr(args, "records", None):
        tenure = _demo_tenure(getattr(args, "tenure", None))
    else:
        try:
            from ark_profile import fetch_tenure
            tenure = fetch_tenure()
        except Exception:
            tenure = None
    report = build_report(stats, nick, cov, hide_nick=args.hide_nick,
                          domain=pool_data, tenure=tenure)
    errors = verify_report(report)
    if errors:
        print("内部校验失败，未生成产物：", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(2)

    if args.json:
        print(json.dumps({"report": report, "pools": stats},
                         ensure_ascii=False, indent=2))
        return
    if args.audit and (args.poster or args.html):
        print(_audit_markdown(report))
        print()
    # 产物落盘目录：默认 ~/.arkbox/reports（通用 skill 的可移植默认），
    # 在项目里跑时用 --out-dir 指到项目内，免得产物躺进 Finder 看不见的隐藏目录。
    out_dir = os.path.expanduser(getattr(args, "out_dir", None) or "~/.arkbox/reports")
    if args.poster or args.html:
        os.makedirs(out_dir, exist_ok=True)
    if args.poster:
        ts = time.strftime("%Y%m%d_%H%M")
        hpath, ppath = export_poster_png(
            report, os.path.join(out_dir, f"poster_{ts}.html"),
            theme=args.theme, keep_source=getattr(args, "keep_poster_source", False))
        if ppath:
            print(f"海报已生成: {ppath}", file=sys.stderr)
            _open_path(ppath)
        else:
            print(f"海报 HTML 已生成（未找到 Chrome/Edge，无法自动截图）: {hpath}", file=sys.stderr)
            _open_path(hpath)
    if args.html:
        ts = time.strftime("%Y%m%d_%H%M")
        # 分享图统一走海报 HTML 模板管线（ark_poster_v4 / ark_poster_terra），
        # 渲染成 PNG 嵌进档案页；无 Chrome 时不嵌入（泰拉侧由页面 canvas 兜底）。
        posters = {}
        if not getattr(args, "site", False):
            posters = _render_share_posters(report, chars, out_dir, ts)
        path = render_html(report, stats, os.path.join(out_dir, f"gacha_{ts}.html"),
                           args.limit, chars=chars, profile=profile,
                           poster_b64=posters.get("gacha"),
                           poster_terra_b64=posters.get("terra"))
        print(f"HTML 报告已生成: {path}"
              + ("" if chars else "（未取到干员数据，仅寻访分析单页）"), file=sys.stderr)
        _open_path(path)
    if getattr(args, "site", False):
        from ark_site import build_site
        site_dir = args.site_dir or os.path.join(os.getcwd(), "site")
        site = build_site(stats, pool_data, cov, site_dir, tenure=tenure, chars=chars,
                          profile=profile)
        print(f"站点已生成: {site['index']}", file=sys.stderr)
        print(f"站点元数据: {site['meta_path']}", file=sys.stderr)
        print(f"发布请求: {site['publish_path']}", file=sys.stderr)
        print("发布：在 Qoder 中由 Agent 读取 .arkbox-publish.json 调用 Qoder Sites prepare/publish。",
              file=sys.stderr)
    if (args.poster or args.html or getattr(args, "site", False)):
        return
    print(render_markdown(report, stats, detail=args.detail, limit=args.limit,
                          with_audit=args.audit))


def main():
    ap = argparse.ArgumentParser(description="明日方舟寻访记录分析")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pa = sub.add_parser("analyze", help="拉取并分析")
    pa.add_argument("--pool", help="只拉取名字含此关键词的卡池目录")
    pa.add_argument("--limit", type=int, help="报告页/表格只展示最近 N 个卡池")
    pa.add_argument("--detail", action="store_true", help="markdown 输出六星详情")
    pa.add_argument("--html", action="store_true", help="生成 HTML 报告页并打开")
    pa.add_argument("--poster", action="store_true", help="生成竖版传播海报 PNG（1080x1440）")
    pa.add_argument("--keep-poster-source", action="store_true", help="保留海报源 HTML；默认只交付 PNG")
    pa.add_argument("--site", action="store_true", help="生成可发布的公开站点目录（隐藏昵称/UID，noindex）")
    pa.add_argument("--site-dir", default=None, help="站点目录，默认当前工作目录/site")
    pa.add_argument("--out-dir", default=None,
                    help="HTML 报告与海报的输出目录，默认 ~/.arkbox/reports（在项目里跑时建议显式指到项目内，免得产物落在隐藏目录）")
    pa.add_argument("--theme", choices=("A", "B"), default="B", help="海报主题，默认 B")
    pa.add_argument("--no-up", action="store_true", help="跳过 UP/池型判断")
    pa.add_argument("--json", action="store_true", help="输出 JSON")
    pa.add_argument("--audit", action="store_true", help="输出数据校验清单")
    pa.add_argument("--hide-nick", action="store_true", help="隐藏昵称（分享产物默认不含 UID）")
    pa.add_argument("--quiet", action="store_true")
    pa.add_argument("--records", help="离线分析本地 JSON/JSONL 或公开 JSON 链接，跳过扫码与归档；rarity 口径与官方一致（0-indexed，六星=5）")
    pa.add_argument("--no-box", action="store_true", help="跳过干员持有数据（档案页不含图鉴/泰拉/分享页签）")
    pa.add_argument("--nick", help="离线模式昵称，默认 博士")
    pa.add_argument("--tenure", help="离线模式演示入职日期 YYYY-MM-DD，用于页头完整展示；不传则隐藏入职段")

    pf = sub.add_parser("fetch", help="仅拉取保存原始记录")
    pf.add_argument("--out", default="gacha_records.json")
    args = ap.parse_args()

    if getattr(args, "records", None):
        try:
            recs = _load_records_file(args.records)
        except Exception as e:
            print(f"读取记录失败: {e}", file=sys.stderr)
            sys.exit(2)
        _finish_analysis(recs, args.nick or "博士",
                         coverage_report(recs), args)
        return

    try:
        creds = ensure_auth(load_creds())
    except ArkApiError as e:
        print(f"错误: {e}", file=sys.stderr)
        print("请先登录：python3 scripts/skland_core.py login", file=sys.stderr)
        sys.exit(2)
    uid = creds["uid"]
    nick = creds.get("nick_name") or "博士"
    if str(nick) == str(uid):
        nick = "博士"

    def progress(count, page):
        if not args.quiet:
            print(f"  已拉取 {count} 条（第 {page} 页）...", file=sys.stderr)

    try:
        cates = gacha_categories(creds, uid)
        if not cates:
            print("官方未返回任何卡池目录（可能账号暂无寻访记录）")
            return
        if args.cmd == "analyze" and args.pool:
            cates = [c for c in cates if args.pool in (c.get("name") or "")]

        all_records, failed_pools, truncated_pools = [], [], []
        # 干员持有（图鉴/泰拉页签用）：失败不阻断寻访分析
        chars, profile = None, None
        if not getattr(args, "no_box", False):
            try:
                from ark_box import extract_profile, fetch_chars
                chars, pdata = fetch_chars(creds, uid)
                profile = extract_profile(pdata, chars)
            except Exception as e:
                print(f"（干员数据不可用，档案页仅含寻访分析：{e}）", file=sys.stderr)
        for c in cates:
            if not args.quiet:
                print(f"拉取卡池目录「{c['name']}」...", file=sys.stderr)
            try:
                recs, truncated = gacha_history_all(creds, uid, c["id"], progress=progress)
                all_records.extend(recs)
                if truncated:
                    truncated_pools.append(c.get("name") or c.get("id") or "?")
            except ArkApiError as e:
                failed_pools.append(c.get("name") or c.get("id") or "?")
                print(f"  ⚠ 该目录拉取失败（不影响已有档案，稍后可重试）: {e}", file=sys.stderr)

        # 本地档案化：合并去重后基于档案全量分析
        if all_records:
            merged, added = archive_merge(uid, all_records)
            if not args.quiet and added:
                print(f"  归档新增 {added} 条，本地档案共 {len(merged)} 条", file=sys.stderr)
            analyze_src = merged
            cov = coverage_report(merged, failed_pools, truncated_pools)
        elif failed_pools or truncated_pools:
            analyze_src = archive_load(uid)
            cov = coverage_report(analyze_src, failed_pools, truncated_pools)
        else:
            analyze_src = []
            cov = coverage_report([])

        if args.cmd == "fetch":
            out_path = os.path.expanduser(args.out)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(all_records, f, ensure_ascii=False)
            print(f"共 {len(all_records)} 条记录已保存到 {out_path}")
            return
        if not analyze_src:
            archived = archive_load(uid)
            if getattr(args, "pool", None):
                archived = [r for r in archived
                            if args.pool in (r.get("poolName") or "")]
            if archived:
                analyze_src = archived
                cov = coverage_report(archived, failed_pools, truncated_pools)
                if not args.quiet:
                    print(f"  远端本次无新记录，改用本地档案 {len(archived)} 条", file=sys.stderr)
            else:
                if getattr(args, "pool", None):
                    print(f"没有匹配「{args.pool}」的卡池目录或本地档案")
                else:
                    print("该账号没有寻访记录")
                return

        _finish_analysis(analyze_src, nick, cov, args, chars=chars, profile=profile)
    except ArkApiError as e:
        print(f"错误: {e}", file=sys.stderr)
        if "失效" in str(e) or "cookie" in str(e).lower() or "token" in str(e).lower():
            print("凭证可能已过期，请重新登录：python3 skland_core.py login", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
