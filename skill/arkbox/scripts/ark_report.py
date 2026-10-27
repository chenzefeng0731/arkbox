#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统一报告模型与称号引擎（P0）。

三形态（Markdown / HTML / 海报）都消费这里的同一个 report，避免各处
重算造成数字不一致。核心口径：

- 池内间隔均值 = Σ各池可见间隔 / 间隔段数（不含当前垫抽）
- 整体效率 = 总抽数 / 六星数（含当前垫抽，和间隔均值不等价）
- 当前垫抽 = 每池 since_last_six；各池独立，不可相加为一次连续
- 最长池内间隔 = max(各池可见间隔)；第 N 抽就是出货抽，不是“N 连未出”
- 理论位置 = 同段数理论样本中，平均间隔优于多少比例；越高越欧
- 称号 = 「结果词 + 人话」，只用真实事件，不写死固定故事

不跨池累计：官方标准/中坚的六星计数虽然跨池，但森空岛无法证明更早
历史完整，因此本工具不做跨池合并。每池从档案内第一条记录起算，
首段可能承接档案外垫抽，口径中明确标注。
"""

import hashlib
from datetime import datetime

from ark_odds import expected_gap, gap_report, next_six_rate


CN_NUM = {2: "双", 3: "三", 4: "四", 5: "五", 6: "六", 7: "七", 8: "八", 9: "九", 10: "十"}


def _up_label(pool):
    uv = pool.get("up_verdict")
    if not uv:
        return "UP 待核" if pool.get("six_count") else "暂无六星"
    if not uv.get("known"):
        return "UP 待核"
    return f"UP {uv.get('hit_count', 0)}/{uv.get('total', 0)}"


def _pool_type_label(pool):
    return pool.get("pool_type_label") or "池型待核"


SPARK_RULES = {
    "limited": 300,
    "linkage": 120,
}


def _pool_events(pool):
    """单池六星事件，带间隔和百分比位置；渲染器不再自己算。"""
    total = max(int(pool.get("total") or 0), 1)
    dup = {d["char_id"]: d["count"] for d in pool.get("duplicates") or []}
    events, prev = [], 0
    for s in pool.get("six_stars") or []:
        at = int(s.get("at_pull") or 0)
        gap = at - prev
        events.append({
            "at_pull": at,
            "gap": gap,
            "gap_class": "g" if gap <= 34 else ("m" if gap <= 50 else "r"),
            "is_first": prev == 0,
            "is_up": s.get("is_up"),
            "is_new": bool(s.get("is_new")),
            "name": s.get("name"),
            "char_id": s.get("char_id"),
            "date": s.get("date"),
            "dup_count": dup.get(s.get("char_id"), 0),
            "at_pct": round(at / total * 100, 3),
            "gap_start_pct": round(prev / total * 100, 3),
            "gap_width_pct": round(gap / total * 100, 3),
        })
        prev = at
    return events


def _spark_for_pool(pool):
    """兑换井进度：只对规则明确的池型展示，且只按档案内当期抽数估算。"""
    threshold = SPARK_RULES.get(pool.get("pool_type"))
    if not threshold:
        return None
    pulls = int(pool.get("total") or 0)
    remaining = max(0, threshold - pulls)
    return {
        "kind": pool.get("pool_type"),
        "threshold": threshold,
        "pulls": pulls,
        "remaining": remaining,
        "progress": round(min(100.0, pulls / threshold * 100), 1),
        "reached": remaining == 0,
        "label": (f"兑换井 {pulls}/{threshold} · "
                  + ("已到井" if remaining == 0 else f"还差 {remaining}")),
        "note": "按档案内当期抽数估算，以游戏内公告为准；不包含免费抽/赠送抽差异",
    }


def _pool_conclusion(pool, events):
    """单池一句人话，数据驱动，不写死故事。"""
    if not events:
        return f"{pool.get('total', 0)} 抽暂无六星"
    worst = max(events, key=lambda x: x["gap"])
    dup = (pool.get("duplicates") or [])
    dup_max = max((d.get("count", 0) for d in dup), default=0)
    dup_name = next((d.get("name") for d in dup if d.get("count") == dup_max), "")
    if dup_max >= 3 and worst["gap"] >= 50:
        return f"{dup_name} ×{dup_max} · 三顾茅庐 · 最长 {worst['gap']} 抽"
    if worst["gap"] >= 50:
        return f"第 {worst['at_pull']} 抽才出 {worst['name']} · 最长 {worst['gap']} 抽"
    if dup_max >= 3:
        return f"{dup_name} ×{dup_max} · 三顾茅庐"
    if dup_max >= 2:
        return f"{dup_name} ×{dup_max}"
    return f"池内均值 {pool.get('avg_gap') or '—'} · 最长 {pool.get('worst_gap') or '—'}"


def _pool_summary(pool):
    events = _pool_events(pool)
    gaps = [e["gap"] for e in events]
    current = pool.get("display_pity", pool.get("since_last_six", 0))
    return {
        "pool_id": pool.get("pool_id"),
        "pool": pool.get("pool"),
        "pool_type": pool.get("pool_type", "unknown"),
        "pool_type_label": _pool_type_label(pool),
        "limited": bool(pool.get("limited")),
        "total": pool.get("total", 0),
        "six_count": pool.get("six_count", 0),
        "avg_gap": pool.get("avg_gap"),
        "worst_gap": pool.get("worst_gap"),
        "best_gap": pool.get("best_gap"),
        "gap_count": len(gaps),
        "gap_sum": sum(gaps),
        "gaps": gaps,
        "events": events,
        "six_stars": pool.get("six_stars") or [],
        "up_verdict": pool.get("up_verdict"),
        "conclusion": _pool_conclusion(pool, events),
        "current_pity": current,
        "display_pity": current,
        "next_rate": next_six_rate(current),
        "display_pity_label": pool.get("display_pity_label") or "池内垫",
        "pity_domain": pool.get("pity_domain"),
        "pity_domain_label": pool.get("pity_domain_label") or "池型待核",
        "domain_shared": bool(pool.get("domain_shared")),
        "start_censored": bool(pool.get("start_censored")),
        "first_gap_note": pool.get("first_gap_note") or "",
        "official_pity_note": pool.get("official_pity_note") or "",
        "spark": _spark_for_pool(pool),
        "up_label": _up_label(pool),
        "up_hits": (pool.get("up_verdict") or {}).get("hit_count"),
        "up_total": (pool.get("up_verdict") or {}).get("total"),
        "up_known": bool((pool.get("up_verdict") or {}).get("known")),
        "first_ts": pool.get("first_ts"),
        "last_ts": pool.get("last_ts"),
    }


def _cn_gold(n):
    return CN_NUM.get(n, str(n))


def _pool_name_by_id(pools, pool_id):
    for p in pools:
        if p.get("pool_id") == pool_id:
            return p.get("pool")
    return "—"


def _short_label(label):
    return str(label or "池型待核").split("（")[0]


def _type_pity_line(items, limit=4):
    parts = [
        f'{_short_label(x.get("domain_label") or x.get("pool_type_label"))} {x.get("current", 0)}'
        for x in items[:limit]
    ]
    if len(items) > limit:
        parts.append(f"等 {len(items)} 池")
    return " / ".join(parts)


def _find_gap_event(pool, target_gap):
    """找到某池中等于 target_gap 的间隔，返回 (gap, 出货六星, 起点抽)。"""
    prev = 0
    for s in pool.get("six_stars") or []:
        g = s["at_pull"] - prev
        if g == target_gap:
            return g, s, prev
        prev = s["at_pull"]
    return target_gap, None, None


def _top_event_story(report):
    """按事件优先级挑最值得一讲的事件句。

    主称号固定为对人的评级后，事件降到 caption/副签/候选；这里保持
    与旧版主称号一致的事件优先级，保证"讲到的事"不变。
    """
    m = report["metrics"]
    best_ten = None
    for tp in report.get("ten_pulls") or []:
        if best_ten is None or (tp["six_count"], tp["ts"]) > (best_ten["six_count"], best_ten["ts"]):
            best_ten = tp

    long_gap = m.get("max_gap") or 0
    current_long = m.get("current_pity_max") or 0
    has_long_gap = bool(long_gap >= 50)

    if best_ten and best_ten["six_count"] >= 2:
        n = best_ten["six_count"]
        evidence = f"{best_ten['pool']} {best_ten.get('pulls', 10)} 抽{_cn_gold(n)}金"
        if has_long_gap:
            return f"{evidence}，但{m.get('max_gap_pool')} {long_gap} 抽才出", "ten_pull_debt"
        return evidence, "ten_pull_win" if n >= 3 else "ten_pull"

    up_total = m.get("up_total") or 0
    up_hits = m.get("up_hits") or 0
    if up_total >= 3 and up_hits == up_total:
        return f"UP {up_hits}/{up_total}", "up"
    if up_total >= 3 and up_hits == 0:
        return f"UP 0/{up_total}", "off"

    if (m.get("max_duplicate") or 0) >= 3:
        d = m["duplicates"][0]
        return f'{d["name"]} ×{d["count"]}', "duplicate"

    if has_long_gap:
        story = f"最长 {long_gap} 抽才出"
        if (m.get("best_gap") or 99) <= 10:
            story += f"，最快 {m['best_gap']} 抽"
        return story, "pity"
    if current_long >= 50:
        return f"当前垫 {current_long} 抽", "pity"

    streak = _max_off_streak(report)
    if streak >= 2:
        return f"单池内连续 {streak} 个六星不是当期 UP", "off_streak"
    return None


def _choose_title(report, display_pools):
    totals = report["totals"]
    m = report["metrics"]
    luck = report["luck"]
    all_pools = report["pools"]["all"]

    if totals["pulls"] == 0:
        return {
            "label": "档案新建",
            "evidence": "暂无寻访记录",
            "reversal": "",
            "caption": "暂无寻访记录",
            "kind": "empty",
        }
    if totals["six"] == 0:
        return {
            "label": "零金",
            "evidence": f"{totals['pulls']} 抽无六星",
            "reversal": "",
            "caption": f"{totals['pulls']} 抽无六星",
            "kind": "zero",
        }

    # 300 井是档案状态级事件，保留为主称号
    for p in all_pools:
        if p["total"] >= 300:
            return {
                "label": "吃井",
                "evidence": f"{p['pool']} {p['total']} 抽",
                "reversal": "",
                "caption": f"{p['pool']} {p['total']} 抽",
                "kind": "spark",
            }

    # 主称号 = 对博士的固定评级（零阶解码）；事件降为 caption/副签/候选
    story = _top_event_story(report)
    better = luck.get("better_than") or 0
    mean = m.get("mean_gap")
    if better >= 90:
        label, kind = "欧皇", "lucky"
    elif better >= 70:
        label, kind = "小欧", "small_lucky"
    elif better >= 20:
        label, kind = "正常发挥", "normal"
    elif better >= 5:
        label, kind = "小非", "small_unlucky"
    else:
        label, kind = "大非酋", "very_unlucky"
    tier_evidence = f"{luck.get('n', 0)} 段均值 {mean} 抽，理论优于 {better}%"
    return {"label": label, "evidence": tier_evidence, "reversal": "",
            "caption": story[0] if story else tier_evidence, "kind": kind}


def _pool_type_summary(report):
    groups = {}
    for p in report["pools"]["all"]:
        label = p.get("pool_type_label") or "池型待核"
        d = groups.setdefault(label, {
            "label": label,
            "pools": [],
            "pulls": 0,
            "six": 0,
            "gap_sum": 0,
            "gap_count": 0,
            "up_hits": 0,
            "up_total": 0,
            "latest": "",
        })
        d["pools"].append(p.get("pool"))
        d["pulls"] += p.get("total", 0)
        d["six"] += p.get("six_count", 0)
        d["gap_sum"] += p.get("gap_sum", 0)
        d["gap_count"] += p.get("gap_count", 0)
        d["up_hits"] += p.get("up_hits") or 0
        d["up_total"] += p.get("up_total") or 0
        d["latest"] = max(d["latest"], p.get("last_ts") or "")
    out = []
    for d in groups.values():
        d["mean_gap"] = round(d["gap_sum"] / d["gap_count"], 1) if d["gap_count"] else None
        d["up_rate"] = round(d["up_hits"] / d["up_total"], 3) if d["up_total"] else None
        out.append(d)
    out.sort(key=lambda x: (-x["pulls"], x["label"]))
    return out


def _max_off_streak(report):
    """单池内连续歪的最长次数；跨池不拼。"""
    best = 0
    for p in report.get("pool_stats") or []:
        cur = 0
        for e in p.get("events") or []:
            if e.get("is_up") is False:
                cur += 1
                best = max(best, cur)
            else:
                cur = 0
    return best


def _title_candidates(report):
    """主称号 + 可由同一份数据支撑的备选称号。"""
    primary = dict(report["title"])
    primary["selected"] = True
    candidates = [primary]

    def add(label, caption, kind):
        if not label or any(c["label"] == label for c in candidates):
            return
        candidates.append({
            "label": label, "caption": caption, "kind": kind,
            "evidence": caption, "reversal": "", "selected": False,
        })

    m = report["metrics"]
    luck = report["luck"]
    best = report.get("best_ten")
    long_gap = m.get("max_gap") or 0
    current_long = m.get("current_pity_max") or 0
    has_long = bool(long_gap >= 50)

    if best and best.get("six_count", 0) >= 2:
        n = best["six_count"]
        base = f'{best.get("pool")} {best.get("pulls", 10)} 抽{_cn_gold(n)}金'
        if has_long:
            add(f"{_cn_gold(n)}金，但 {long_gap} 抽才出", f"{base}，但{long_gap} 抽才出", "ten_pull_debt")
        elif n >= 3:
            add(f"{_cn_gold(n)}金血赚", base, "ten_pull_win")
        else:
            add("双金", base, "ten_pull")
        add("双金" if n == 2 else f"{_cn_gold(n)}金", base, "ten_pull")

    if (m.get("max_duplicate") or 0) >= 3:
        d = m["duplicates"][0]
        add("三顾茅庐", f'{d["name"]} ×{d["count"]}', "duplicate")

    if has_long:
        add("保底人", f"最长池内 {long_gap} 抽才出", "pity")
    elif current_long >= 50:
        add("保底人", f"当前垫 {current_long} 抽", "pity")

    if (m.get("up_total") or 0) >= 3:
        if m.get("up_hits") == m["up_total"]:
            add("不歪拿下", f'UP {m["up_hits"]}/{m["up_total"]}', "up")
        elif (m.get("up_hits") or 0) == 0:
            add("歪麻了", f'UP 0/{m["up_total"]}', "off")
    streak = _max_off_streak(report)
    if streak >= 2:
        add(f"连歪 {streak} 次", f"单池内连续 {streak} 个六星不是当期 UP", "off_streak")

    reached = [p for p in report.get("pool_stats") or []
               if (p.get("spark") or {}).get("reached")]
    if reached:
        add("吃井", f'{reached[0]["pool"]} 已到 {reached[0]["spark"]["threshold"]} 抽', "spark")

    return candidates

    return candidates


def _period_compare(report):
    pools = sorted(report.get("pools", {}).get("all") or [],
                   key=lambda p: (p.get("last_ts") or "", p.get("first_ts") or ""),
                   reverse=True)
    if len(pools) < 2:
        return None
    latest = pools[0]
    earlier = pools[1:]
    e_gap_count = sum(p.get("gap_count", 0) for p in earlier)
    e_gap_sum = sum(p.get("gap_sum", 0) for p in earlier)
    e_pulls = sum(p.get("total", 0) for p in earlier)
    e_six = sum(p.get("six_count", 0) for p in earlier)
    e_mean = round(e_gap_sum / e_gap_count, 1) if e_gap_count else None
    l_mean = latest.get("avg_gap")
    delta = round(l_mean - e_mean, 1) if l_mean is not None and e_mean is not None else None
    return {
        "latest": {
            "pool": latest.get("pool"), "pulls": latest.get("total", 0),
            "six": latest.get("six_count", 0), "mean_gap": l_mean,
        },
        "earlier": {
            "pools": len(earlier), "pulls": e_pulls, "six": e_six,
            "gap_count": e_gap_count, "mean_gap": e_mean,
        },
        "delta": delta,
        "note": "只比较档案内可见间隔；最近池首段可能承接档案外垫抽。",
    }


def _data_gaps(report):
    gaps = []
    cov = report.get("coverage") or {}
    if cov.get("status") in ("partial", "none", "known_gap"):
        gaps.append({
            "kind": "coverage",
            "title": "历史区间未知",
            "detail": f'{cov.get("label")}；官方接口不提供账号全历史证明。',
        })
    if cov.get("failed_pools"):
        gaps.append({
            "kind": "failed",
            "title": "同步失败",
            "detail": "、".join(cov["failed_pools"]) + " 本次拉取失败，已有档案不受影响。",
        })
    if cov.get("truncated_pools"):
        gaps.append({
            "kind": "truncated",
            "title": "分页截断",
            "detail": "、".join(cov["truncated_pools"]) + " 记录被截断，可能缺少更早抽数。",
        })
    std = [p for p in report.get("pool_stats") or [] if p.get("domain_shared")]
    if std:
        names = "、".join(f'{p["pool"]} {p["total"]} 抽' for p in std)
        gaps.append({
            "kind": "standard",
            "title": "标准/中坚垫抽无法追溯",
            "detail": f"{names}；更早同类型池的记录未知，因此不跨池合并，首段可能承接档案外垫抽。",
        })
    if report.get("metrics", {}).get("gap_count"):
        gaps.append({
            "kind": "first_segment",
            "title": "各池首段可能偏短",
            "detail": "每池从档案内第一条记录起算；如果档案起点晚于池起点，首段会少算之前的垫抽。",
        })
    if any((p.get("spark") is None and p.get("six_count")) for p in report.get("pool_stats") or []):
        gaps.append({
            "kind": "spark",
            "title": "部分池型不计算兑换井",
            "detail": "标准/中坚/特殊池的 UP 保底规则不统一，未用猜测值；限定 300、联动 120 的进度按档案内当期抽数估算。",
        })
    return gaps


def _privacy_note(report):
    if report.get("doctor", {}).get("nick_hidden"):
        return "昵称已隐藏；分享产物不包含 UID。"
    return "分享产物不包含 UID；如需隐藏昵称请用 --hide-nick。"


def _social_caption(report):
    m = report["metrics"]
    luck = report["luck"]
    cov = report.get("coverage") or {}
    nick = report["doctor"]["nick"]
    best = report.get("best_ten")
    hashtags = ["#明日方舟", "#寻访档案", "#ArkBox"]
    tag_line = " ".join(hashtags)
    if not report["totals"]["pulls"]:
        caption = f"{nick} 的寻访档案：暂无寻访记录。"
        return {"caption": caption, "hashtags": hashtags,
                "text": caption + "\n" + tag_line,
                "privacy_note": _privacy_note(report),
                "variants": [{"label": "主文案", "text": caption + "\n" + tag_line}]}
    if not report["totals"]["six"]:
        caption = (f"{nick} 的寻访档案｜零金：{report['totals']['pulls']} 抽暂无六星。"
                   f"数据范围 {cov.get('earliest')} ~ {cov.get('latest')}，仅本档案区间。")
        return {"caption": caption, "hashtags": hashtags,
                "text": caption + "\n" + tag_line,
                "privacy_note": _privacy_note(report),
                "variants": [{"label": "主文案", "text": caption + "\n" + tag_line}]}
    pieces = [
        f'{nick} 的寻访档案｜{report["title"]["label"]}：'
        f'{report["totals"]["pulls"]} 抽 {report["totals"]["six"]} 名六星，'
        f'池内 {m.get("mean_gap")} 抽/六星（{m.get("gap_count")} 段）。'
    ]
    if best and best.get("six_count", 0) >= 2:
        pieces.append(f'最佳十连 {best.get("pool")} {best.get("pulls", 10)} 抽'
                      f'{_cn_gold(best["six_count"])}金。')
    if m.get("max_gap"):
        pieces.append(f'最长池内 {m["max_gap"]} 抽才出。')
    pieces.append(f'UP {m.get("up_hits")}/{m.get("up_total")}，'
                  f'理论位置优于约 {luck.get("better_than")}% 的同段数样本。')
    pieces.append(f'数据范围 {cov.get("earliest")} ~ {cov.get("latest")}，'
                  "仅本档案区间；理论模型，非全服排名。")
    caption = "".join(pieces)
    short = (f'{report["title"]["label"]}｜{report["totals"]["pulls"]} 抽 '
             f'{report["totals"]["six"]} 名六星，池内 {m.get("mean_gap")} 抽/六星，'
             f'UP {m.get("up_hits")}/{m.get("up_total")}。')
    data_text = (f'{report["totals"]["pulls"]} 抽 / {report["totals"]["six"]} 名六星 / '
                 f'池内 {m.get("mean_gap")} 抽 / 理论位置 {luck.get("better_than")}% / '
                 f'UP {m.get("up_hits")}/{m.get("up_total")}。'
                 f'{report["title"]["label"]}，最长池内 {m.get("max_gap")} 抽。'
                 f'数据范围 {cov.get("earliest")} ~ {cov.get("latest")}，'
                 "理论模型，非全服排名。")
    privacy_note = _privacy_note(report)
    return {
        "caption": caption,
        "hashtags": hashtags,
        "text": caption + "\n" + tag_line,
        "privacy_note": privacy_note,
        "variants": [
            {"label": "主文案", "text": caption + "\n" + tag_line},
            {"label": "数据版", "text": data_text + "\n" + tag_line},
            {"label": "短句", "text": short + "\n" + tag_line},
        ],
    }


def _pity_line(pity_by_pool, limit=3):
    parts = [f"{p['pool']} {p['pity']}" for p in pity_by_pool[:limit]]
    if len(pity_by_pool) > limit:
        parts.append(f"等 {len(pity_by_pool)} 池")
    return " / ".join(parts)


def _other_line(other, total_pools, display_count):
    if not other:
        return ""
    pulls = sum(p["total"] for p in other)
    six = sum(p["six_count"] for p in other)
    names = "、".join(p["pool"] for p in other[:2])
    if len(other) > 2:
        names += " 等"
    return (f"重点 {display_count} / 共 {total_pools} 池 · "
            f"另有 {len(other)} 池 {pulls} 抽 {six} 名六星（{names}，未展开）")


def build_report(stats, nick, coverage, hide_nick=False,
                 seed_date=None, display_limit=2, domain=None, tenure=None):
    """把 analyze_records 的结果变成唯一报告模型。

    分享产物（海报 / HTML / 站点 / Markdown）一律不展示 UID；
    UID 只存在于本地凭证与归档目录，不进入报告模型。

    domain 来自 ark_domains.build_pool_stats（参数名保留兼容）：
    - all_gaps：按池独立的所有可见间隔 → 均值 / 理论位置主值
    - current_by_pool：每池当前垫抽，各池独立
    """
    all_pools = list(stats or [])
    total_pulls = sum(p["total"] for p in all_pools)
    total_six = sum(p["six_count"] for p in all_pools)

    if domain:
        gaps = list(domain.get("all_gaps") or [])
        intervals = list(domain.get("intervals") or [])
        current_by_pool = list(domain.get("current_by_pool") or [])
        current_total = int(domain.get("current_total") or 0)
    else:
        gaps, intervals = [], []
        current_by_pool = []
        for p in all_pools:
            pool_gaps = []
            for i, g in enumerate(p.get("gaps") or []):
                _, s, _ = _find_gap_event(p, g)
                iv = {
                    "gap": g,
                    "end_pool": p.get("pool_id"),
                    "end_at_pull": s["at_pull"] if s else None,
                    "end_name": s["name"] if s else None,
                    "first": i == 0,
                }
                intervals.append(iv)
                gaps.append(g)
                pool_gaps.append(g)
            current_by_pool.append({
                "pool": p["pool"],
                "pool_id": p.get("pool_id"),
                "pool_type_label": _pool_type_label(p),
                "domain_label": _short_label(p.get("pity_domain_label") or _pool_type_label(p)),
                "current": p.get("display_pity", p.get("since_last_six", 0)),
                "total": p.get("total", 0),
                "six_count": p.get("six_count", 0),
                "gap_count": len(pool_gaps),
                "gap_sum": sum(pool_gaps),
                "mean_gap": round(sum(pool_gaps) / len(pool_gaps), 1) if pool_gaps else None,
                "worst_gap": max(pool_gaps) if pool_gaps else None,
                "first_ts": p.get("first_ts"),
                "last_ts": p.get("last_ts"),
            })
        current_by_pool.sort(key=lambda x: (-x["current"], x["pool"]))
        current_total = sum(x["current"] for x in current_by_pool)

    gr = gap_report(gaps) or {}
    gap_count = len(gaps)
    gap_sum = sum(gaps)
    mean_gap = gr.get("avg_gap")
    better = gr.get("better_than")
    overall = round(total_pulls / total_six, 1) if total_six else None

    pity_by_pool = sorted(
        [{
            "pool": p["pool"],
            "pity": p.get("display_pity", p.get("since_last_six", 0)),
            "current": p.get("display_pity", p.get("since_last_six", 0)),
            "label": p.get("display_pity_label") or "池内垫",
            "pool_type_label": _pool_type_label(p),
            "domain": _short_label(p.get("pity_domain_label") or _pool_type_label(p)),
            "next_rate": next_six_rate(p.get("display_pity", p.get("since_last_six", 0))),
            "spark": _spark_for_pool(p),
        } for p in all_pools],
        key=lambda x: (-x["pity"], x["pool"]),
    )
    pity_total = current_total
    pity_max = max((x["current"] for x in current_by_pool), default=0)

    pool_details = []
    for d in current_by_pool:
        p = next((x for x in all_pools if x.get("pool_id") == d.get("pool_id")), {})
        events = _pool_events(p) if p else []
        pool_details.append({
            **d,
            "events": events,
            "gaps": [e["gap"] for e in events],
            "conclusion": _pool_conclusion(p, events) if p else "",
            "next_rate": next_six_rate(d.get("current", 0)),
            "spark": _spark_for_pool(p) if p else None,
            "start_censored": bool(p.get("start_censored")),
            "first_gap_note": p.get("first_gap_note") or "首段自档案首条记录起算",
            "official_pity_note": p.get("official_pity_note") or d.get("official_pity_note") or "",
        })

    max_iv = max(intervals, key=lambda x: x["gap"]) if intervals else None
    best_iv = min(intervals, key=lambda x: x["gap"]) if intervals else None
    max_gap = max_iv["gap"] if max_iv else 0
    best_gap = best_iv["gap"] if best_iv else 0
    max_gap_pool = _pool_name_by_id(all_pools, max_iv.get("end_pool")) if max_iv else "—"
    best_gap_pool = _pool_name_by_id(all_pools, best_iv.get("end_pool")) if best_iv else "—"
    max_gap_at = max_iv.get("end_at_pull") if max_iv else None
    max_gap_name = max_iv.get("end_name") if max_iv else None
    best_gap_at = best_iv.get("end_at_pull") if best_iv else None
    best_gap_name = best_iv.get("end_name") if best_iv else None
    best_gap_first = bool(best_iv and best_iv.get("first"))
    max_gap_first = bool(max_iv and max_iv.get("first"))

    known_up_pools = [p for p in all_pools if (p.get("up_verdict") or {}).get("known")]
    up_hits = sum((p.get("up_verdict") or {}).get("hit_count") or 0 for p in known_up_pools)
    up_total = sum((p.get("up_verdict") or {}).get("total") or 0 for p in known_up_pools)
    six_pools = [p for p in all_pools if p.get("six_count")]
    up_unknown = len([p for p in six_pools if not (p.get("up_verdict") or {}).get("known")])

    duplicates = []
    for p in all_pools:
        for d in p.get("duplicates") or []:
            duplicates.append({"char_id": d["char_id"], "name": d["name"], "count": d["count"]})
    duplicates.sort(key=lambda x: (-x["count"], x["name"] or ""))
    max_duplicate = duplicates[0]["count"] if duplicates else 0

    ten_pulls = [tp for p in all_pools for tp in p.get("ten_pulls") or []]
    ten_pulls.sort(key=lambda x: (x["six_count"], x["ts"]), reverse=True)

    display_pools = sorted(
        all_pools, key=lambda p: (-p["six_count"], -p["total"], p["first_ts"] or "")
    )[:display_limit]
    shown_ids = {id(p) for p in display_pools}
    other_pools = [p for p in all_pools if id(p) not in shown_ids]
    other_line = _other_line(other_pools, len(all_pools), len(display_pools))

    nick_display = "已隐藏" if hide_nick else (nick or "博士")
    generated = seed_date or datetime.now().strftime("%Y.%m.%d")
    barcode_seed = hashlib.sha1(
        f"{generated}|{total_pulls}|{len(all_pools)}|{gap_count}".encode("utf-8")
    ).hexdigest()[:12]

    coverage = dict(coverage or {})
    coverage_line = coverage.get("line") or "数据档案：暂无记录"
    coverage_short = coverage.get("short") or "暂无记录"
    model_caption = "2% 基础 / 50 抽未出后每抽 +2% / 99 抽必出"

    luck = {
        "better_than": better,
        "method": gr.get("method"),
        "n": gap_count,
        "observed_mean": mean_gap,
        "expected_gap": round(expected_gap(), 1),
        "label": f"优于约 {better}% 的同段数理论样本（按池独立）" if better is not None else "—",
        "caveat": "理论模型；非全服排名；各池从档案首条记录起算，首段可能承接档案外垫抽",
    }

    metrics = {
        "gap_count": gap_count,
        "gap_sum": gap_sum,
        "mean_gap": mean_gap,
        "gap_basis": "按池独立，档案内可见间隔",
        "overall_efficiency": overall,
        "expected_gap": round(expected_gap(), 1),
        "current_pity_by_pool": pity_by_pool,
        "current_pity_total": current_total,
        "current_pity_max": pity_max,
        "max_gap": max_gap or None,
        "max_gap_pool": max_gap_pool,
        "max_gap_at": max_gap_at,
        "max_gap_name": max_gap_name,
        "max_gap_first": max_gap_first,
        "best_gap": best_gap or None,
        "best_gap_pool": best_gap_pool,
        "best_gap_at": best_gap_at,
        "best_gap_name": best_gap_name,
        "best_gap_first": best_gap_first,
        "up_hits": up_hits,
        "up_total": up_total,
        "up_known_pools": len(known_up_pools),
        "up_unknown_pools": up_unknown,
        "up_rate": round(up_hits / up_total, 3) if up_total else None,
        "duplicates": duplicates[:8],
        "max_duplicate": max_duplicate,
        "cross_pool_applied": False,
    }

    pool_summaries = [_pool_summary(p) for p in all_pools]
    report = {
        "doctor": {
            "nick": nick_display,
            "nick_hidden": bool(hide_nick),
        },
        "totals": {
            "pulls": total_pulls,
            "six": total_six,
            "pools": len(all_pools),
            "display_pools": len(display_pools),
            "other_pools": len(other_pools),
        },
        "metrics": metrics,
        "luck": luck,
        "coverage": coverage,
        "tenure": tenure,
        "pool_stats": pool_details,
        "pools": {
            "all": pool_summaries,
            "display": display_pools,
            "other": [_pool_summary(p) for p in other_pools],
            "other_line": other_line,
            "display_note": (f"重点 {len(display_pools)} / 共 {len(all_pools)} 池"
                             if other_pools else f"全部 {len(all_pools)} 池"),
        },
        "ten_pulls": ten_pulls,
        "best_ten": ten_pulls[0] if ten_pulls else None,
        "privacy": {
            "nick_display": nick_display,
            "barcode_seed": barcode_seed,
            "shows_uid": False,
        },
        "model": {
            "base": 0.02,
            "ramp_start": 51,
            "hard_pity": 99,
            "expected_gap": round(expected_gap(), 1),
            "caption": model_caption,
        },
        "generated": generated,
        "lines": {
            "coverage": coverage_line,
            "coverage_short": coverage_short,
            "metric": (
                f"池内 {mean_gap} 抽/六星（{gap_count} 段，按池独立；首段可能承接档案外垫抽）"
                f" · 整体 {overall} 抽/六星（含未结算 {current_total} 抽）"
                if mean_gap is not None and overall is not None else "暂无数据"
            ),
            "pity": (f"六星垫（池内）：{_type_pity_line(current_by_pool)}"
                     "（各池独立，不跨池合并）"
                     if current_by_pool else ""),
            "up": (f"UP 命中 {up_hits}/{up_total}" +
                   (f"（{up_unknown} 池待核）" if up_unknown else "")) if up_total else "UP 待核",
            "worst": (f"最长池内间隔：{max_gap} 抽（{max_gap_pool}，"
                      f"第 {max_gap_at} 抽出货）"
                      + ("（该池首段）" if max_gap_first else "")
                      if max_gap else "暂无池内间隔"),
            "best": (f"最快池内间隔：{best_gap} 抽（{best_gap_pool}，第 {best_gap_at} 抽）"
                     + ("（该池首段）" if best_gap_first else "")
                     if best_gap else "暂无池内间隔"),
            "model": f"理论模型：{model_caption}；按池独立；非全服排名",
            "tenure": (f'入职 {tenure.get("register_date")} · {tenure.get("days")} 天'
                       if tenure else ""),
        },
    }
    report["title"] = _choose_title(report, display_pools)
    report["title_candidates"] = _title_candidates(report)
    report["pool_types"] = _pool_type_summary(report)
    report["period_compare"] = _period_compare(report)
    report["data_gaps"] = _data_gaps(report)
    report["share"] = _social_caption(report)
    report["audit"], report["verification"] = _build_audit(report)
    return report


def verify_report(report):
    """返回不一致项；空列表代表通过。"""
    errors = []
    totals = report["totals"]
    m = report["metrics"]
    all_pools = report["pools"]["all"]
    if sum(p["total"] for p in all_pools) != totals["pulls"]:
        errors.append("池抽数之和 ≠ 累计寻访")
    if sum(p["six_count"] for p in all_pools) != totals["six"]:
        errors.append("池六星之和 ≠ 六星总数")
    if m["gap_sum"] + m["current_pity_total"] != totals["pulls"]:
        errors.append("池内间隔 + 当前垫抽 ≠ 累计寻访")
    if m["gap_count"] and m["mean_gap"] != round(m["gap_sum"] / m["gap_count"], 1):
        errors.append("池内间隔均值 ≠ 间隔总和 ÷ 段数")
    if sum(x.get("current", 0) for x in m.get("current_pity_by_pool") or []) != m["current_pity_total"]:
        errors.append("各池垫抽之和 ≠ 未结算抽数")
    if m.get("cross_pool_applied"):
        errors.append("检测到跨池累计；当前口径要求按池独立")
    if totals["six"] and m["overall_efficiency"] != round(totals["pulls"] / totals["six"], 1):
        errors.append("整体效率 ≠ 总抽数 ÷ 六星数")
    if m["up_hits"] > m["up_total"]:
        errors.append("UP 命中数 > UP 总数")
    display_pulls = sum(p["total"] for p in report["pools"]["display"])
    other_pulls = sum(p["total"] for p in report["pools"]["other"])
    if display_pulls + other_pulls != totals["pulls"]:
        errors.append("展示池 + 其他池抽数 ≠ 总抽数")
    display_six = sum(p["six_count"] for p in report["pools"]["display"])
    other_six = sum(p["six_count"] for p in report["pools"]["other"])
    if display_six + other_six != totals["six"]:
        errors.append("展示池 + 其他池六星 ≠ 总六星")
    if not report["title"].get("label"):
        errors.append("称号为空")
    if not report.get("title_candidates"):
        errors.append("没有可用称号候选")
    if sum(x.get("pulls", 0) for x in report.get("pool_types") or []) != totals["pulls"]:
        errors.append("池型汇总抽数之和 ≠ 累计寻访")
    for p in report.get("pool_stats") or []:
        spark = p.get("spark")
        if not spark:
            continue
        if spark.get("pulls") != p.get("total"):
            errors.append("兑换井进度与池抽数不一致")
        if spark.get("remaining") != max(0, spark.get("threshold", 0) - spark.get("pulls", 0)):
            errors.append("兑换井剩余抽数计算不一致")
    return errors


def _build_audit(report):
    totals = report["totals"]
    m = report["metrics"]
    luck = report["luck"]
    errors = verify_report(report)
    ok = not errors
    mean_disp = m["mean_gap"] if m["mean_gap"] is not None else "—"
    overall_disp = m["overall_efficiency"] if m["overall_efficiency"] is not None else "—"
    better_disp = luck["better_than"] if luck["better_than"] is not None else "—"
    max_gap_disp = m["max_gap"] if m["max_gap"] is not None else "—"
    max_gap_at = m["max_gap_at"] if m["max_gap_at"] is not None else "—"
    pool_detail_txt = " / ".join(
        f"{p['pool']} {p['total']}抽（{p['six_count']}六星；{p['gap_count']}段；垫 {p['current']}）"
        for p in report.get("pool_stats") or []
    ) or "—"
    current_raw = " + ".join(
        f"{p['pool']} {p['current']}" for p in m.get("current_pity_by_pool") or []
    ) or "—"
    shared_pools = [p for p in report.get("pool_stats") or [] if p.get("domain_shared")]
    shared_txt = "、".join(
        f"{p['pool']} {p['total']}抽" for p in shared_pools
    )
    data_complete_txt = "；".join(filter(None, [
        "按池独立，不跨池合并",
        f"标准/中坚可见池：{shared_txt}；更早同域记录无法证明" if shared_txt else "",
        "各池首段自档案首条记录起算，可能承接档案外垫抽",
    ]))
    titles_txt = " / ".join(x["label"] for x in report.get("title_candidates") or [])
    spark_txt = " / ".join(
        f'{p["pool"]} {p["spark"]["label"]}'
        for p in report.get("pool_stats") or [] if p.get("spark")
    ) or "无规则明确的兑换井"
    gaps_txt = " / ".join(x["title"] for x in report.get("data_gaps") or []) or "无"
    rows = [
        {"指标": "本区间抽数", "原始值": f"Σ池抽数 = {totals['pulls']}",
         "公式/口径": "所有已归档池抽数之和", "显示值": f"{totals['pulls']}", "一致": ok},
        {"指标": "六星干员", "原始值": f"Σ池六星 = {totals['six']}",
         "公式/口径": "rarity≥六星阈值", "显示值": f"{totals['six']}", "一致": ok},
        {"指标": "池内间隔均值",
         "原始值": f"{m['gap_sum']} ÷ {m['gap_count']} = {mean_disp}",
         "公式/口径": "每池独立；首段从档案内首条记录起算",
         "显示值": f"{mean_disp} 抽", "一致": ok},
        {"指标": "整体效率",
         "原始值": f"{totals['pulls']} ÷ {totals['six']} = {overall_disp}",
         "公式/口径": "含未结算抽数；与间隔均值不等价",
         "显示值": f"{overall_disp} 抽/六星", "一致": ok},
        {"指标": "当前垫抽",
         "原始值": current_raw,
         "公式/口径": "每池总抽数 - 最后六星位置；各池独立，不跨池合并",
         "显示值": (f"{_type_pity_line(m['current_pity_by_pool'])}"
                    f"（池内，合计 {m['current_pity_total']} 仅作核对）")
                   if m["current_pity_by_pool"] else "—", "一致": ok},
        {"指标": "跨池累计", "原始值": "未采用",
         "公式/口径": "官方标准/中坚六星计数跨池累计；森空岛无法证明更早历史完整，故本工具不合并",
         "显示值": "按池独立", "一致": ok},
        {"指标": "最长池内间隔",
         "原始值": f"max(gaps) = {max_gap_disp}",
         "公式/口径": "单池内第 N 抽就是出货抽，不是 N 连未出",
         "显示值": (f"{max_gap_disp} 抽（{m['max_gap_pool']}，第 {max_gap_at} 抽）"
                    + ("（该池首段）" if m.get("max_gap_first") else "")), "一致": ok},
        {"指标": "最快池内间隔",
         "原始值": f"min(gaps) = {m['best_gap'] if m['best_gap'] is not None else '—'}",
         "公式/口径": "单池内第 N 抽就是出货抽",
         "显示值": (f"{m['best_gap']} 抽（{m['best_gap_pool']}，第 {m['best_gap_at']} 抽）"
                    + ("（该池首段）" if m.get("best_gap_first") else "")
                    if m["best_gap"] is not None else "—"), "一致": ok},
        {"指标": "理论期望", "原始值": f"{luck['expected_gap']}",
         "公式/口径": "2% / 51 抽起 +2% / 99 抽必出",
         "显示值": f"{luck['expected_gap']} 抽", "一致": ok},
        {"指标": "理论位置", "原始值": f"n={luck['n']}，均值 {mean_disp}",
         "公式/口径": f"1 - P(理论均值 ≤ 观测值)；{luck['method'] or '—'}；按池独立",
         "显示值": f"优于约 {better_disp}%；理论模型，非全服排名", "一致": ok},
        {"指标": "UP 命中", "原始值": f"{m['up_hits']} / {m['up_total']}",
         "公式/口径": f"仅统计已核验池；{m['up_unknown_pools']} 池待核",
         "显示值": report["lines"]["up"], "一致": ok},
        {"指标": "池型", "原始值": "PRTS limitedChar + RATE_UP_6",
         "公式/口径": "单 UP 不推断限定；联动/标准/限定分开",
         "显示值": " / ".join(p["pool_type_label"] for p in report["pools"]["all"]) or "—",
         "一致": ok},
        {"指标": "官方保底规则", "原始值": "标准/中坚跨池；限定/联动当期",
         "公式/口径": "仅作规则说明，不参与本报告计算；UP 保底/井另算",
         "显示值": "未跨池合并", "一致": ok},
        {"指标": "按池明细", "原始值": pool_detail_txt,
         "公式/口径": "卡池目录 → 单池间隔 → 单池垫抽",
         "显示值": _type_pity_line(m["current_pity_by_pool"]) or "—", "一致": ok},
        {"指标": "数据完整性", "原始值": f"本区间 {totals['pools']} 池 / {totals['pulls']} 抽",
         "公式/口径": "官方可查窗口内的记录；不保证更早历史",
         "显示值": data_complete_txt, "一致": ok},
        {"指标": "称号候选", "原始值": f"{len(report.get('title_candidates') or [])} 个",
         "公式/口径": "主称号 + 同一份数据可支撑的备选结果词",
         "显示值": titles_txt or "—", "一致": ok},
        {"指标": "兑换井", "原始值": "限定 300 / 联动 120",
         "公式/口径": "按档案内当期抽数估算；标准/中坚/特殊不硬算",
         "显示值": spark_txt, "一致": ok},
        {"指标": "数据缺口", "原始值": f"{len(report.get('data_gaps') or [])} 项",
         "公式/口径": "覆盖范围、同步失败、截断、首段偏差",
         "显示值": gaps_txt, "一致": ok},
        {"指标": "展示池", "原始值": f"{totals['display_pools']} / {totals['pools']}",
         "公式/口径": "重点卡池 + 其他池汇总",
         "显示值": report["pools"]["other_line"] or report["pools"]["display_note"], "一致": ok},
        {"指标": "覆盖范围",
         "原始值": f"{report['coverage'].get('earliest')} ~ {report['coverage'].get('latest')}",
         "公式/口径": "归档记录；官方未提供账号全历史证明",
         "显示值": report["coverage"].get("label"), "一致": ok},
        {"指标": "入职信息", "原始值": "status.registerTs",
         "公式/口径": "当前日期 - 入职日期 + 1；仅本地显示",
         "显示值": report["lines"].get("tenure") or "未获取", "一致": ok},
        {"指标": "隐私", "原始值": "UID 不进入报告模型",
         "公式/口径": "分享产物不展示 UID；昵称可用 --hide-nick 隐藏",
         "显示值": report["privacy"]["nick_display"], "一致": ok},
    ]
    if errors:
        rows.append({"指标": "校验", "原始值": "—", "公式/口径": "；".join(errors),
                     "显示值": "存在不一致", "一致": False})
    return rows, errors
