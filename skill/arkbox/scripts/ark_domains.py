#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按池独立的寻访统计。

为什么不再跨池合并：
- 官方规则里，标准寻访 / 中坚寻访的六星连续未出计数会跨同类型卡池累计；
- 但森空岛只返回可查窗口内的记录，无法证明档案覆盖了更早的标准 / 中坚池；
- 跨池合并的首段可能承接未知垫抽，会把“不完整”混进平均值。

因此本工具默认：
- 每个卡池独立统计六星间隔，不跨池相加；
- 当前垫抽 = 该池总抽数 - 最后六星位置，各池独立；
- 每池从档案内第一条记录起算，首段可能承接档案外垫抽，表中标注但不剔除。
"""

from collections import defaultdict
from datetime import datetime


def _fmt_ts(ms):
    try:
        return datetime.fromtimestamp(int(ms) / 1000).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OSError):
        return "?"


def _pool_info(pool_index, pool_id):
    if pool_index:
        return pool_index.info(pool_id)
    return {
        "pity_domain": f"unknown:{pool_id}",
        "pity_domain_label": "池型待核",
        "domain_shared": False,
        "pool_type_label": "池型待核",
    }


def build_pool_stats(records, pool_index=None, six_star_at=None):
    """返回按池独立的间隔、当前垫抽和展示元数据。

    all_gaps：所有池内可见间隔（含每池首段），主值口径
    pool_gaps：按 pool_id 分组的间隔
    current_by_pool：每池当前垫抽，各池独立
    """
    if six_star_at is None:
        max_rarity = max((r.get("rarity", 0) for r in records), default=0)
        six_star_at = 6 if max_rarity >= 6 else 5

    by_pool = defaultdict(list)
    for r in records:
        by_pool[r.get("poolId") or ""].append(r)

    info_by_pool = {pid: _pool_info(pool_index, pid) for pid in by_pool}
    all_intervals = []
    pool_gaps = {}
    pool_meta = {}
    current_by_pool = []

    for pid, rs in by_pool.items():
        rs = sorted(rs, key=lambda r: (int(r["gachaTs"]), r.get("pos") or 0))
        by_pool[pid] = rs
        info = info_by_pool[pid]
        gaps = []
        count = 0
        six_positions = []
        for i, r in enumerate(rs, 1):
            count += 1
            if r.get("rarity", 0) >= six_star_at:
                gaps.append({
                    "gap": count,
                    "pool": rs[0].get("poolName") or pid,
                    "pool_id": pid,
                    "end_pool": pid,
                    "end_at_pull": i,
                    "end_name": r.get("charName"),
                    "first": len(gaps) == 0,
                })
                all_intervals.append(gaps[-1])
                six_positions.append(i)
                count = 0

        since = len(rs) - (six_positions[-1] if six_positions else 0)
        pool_gaps[pid] = gaps
        pool_type_label = info.get("pool_type_label") or "池型待核"
        domain_label = (info.get("pity_domain_label") or pool_type_label).split("（")[0]
        is_shared = bool(info.get("domain_shared"))
        pool_meta[pid] = {
            # 保留官方计数域元数据，只作说明，不参与计算
            "pity_domain": info.get("pity_domain"),
            "pity_domain_label": info.get("pity_domain_label") or "池型待核",
            "domain_shared": is_shared,
            "display_pity": since,
            "display_pity_label": "池内垫",
            "start_censored": True,
            "first_gap_note": "首段自档案首条记录起算",
            "official_pity_note": (
                "官方标准/中坚六星计数跨池累计；本工具因无法证明更早历史完整，未合并"
                if is_shared else ""
            ),
        }
        gap_values = [g["gap"] for g in gaps]
        current_by_pool.append({
            "pool": rs[0].get("poolName") or pid,
            "pool_id": pid,
            "pool_type_label": pool_type_label,
            "domain_label": domain_label,
            "domain_shared": is_shared,
            "start_censored": True,
            "current": since,
            "total": len(rs),
            "six_count": len(six_positions),
            "gap_count": len(gap_values),
            "gap_sum": sum(gap_values),
            "mean_gap": round(sum(gap_values) / len(gap_values), 1) if gap_values else None,
            "worst_gap": max(gap_values) if gap_values else None,
            "first_ts": _fmt_ts(rs[0].get("gachaTs")),
            "last_ts": _fmt_ts(rs[-1].get("gachaTs")),
            "official_pity_note": pool_meta[pid]["official_pity_note"],
        })

    current_by_pool.sort(key=lambda x: (-x["current"], x["pool"]))
    all_gaps = [iv["gap"] for iv in all_intervals]

    return {
        "mode": "per_pool",
        "cross_pool_applied": False,
        "all_gaps": all_gaps,
        "gap_sum": sum(all_gaps),
        "intervals": all_intervals,
        "pool_gaps": pool_gaps,
        "current_by_pool": current_by_pool,
        "current_total": sum(x["current"] for x in current_by_pool),
        "current_max": max((x["current"] for x in current_by_pool), default=0),
        "pool_meta": pool_meta,
    }


# 兼容旧调用；语义已变为按池独立，不再合并计数域。
def build_domain_stats(records, pool_index=None, six_star_at=None):
    return build_pool_stats(records, pool_index=pool_index, six_star_at=six_star_at)


def apply_pool_meta(stats, domain_data):
    """把按池统计的垫抽展示字段写回池统计。"""
    for p in stats:
        p.update(domain_data.get("pool_meta", {}).get(p.get("pool_id"), {}))
    return stats
