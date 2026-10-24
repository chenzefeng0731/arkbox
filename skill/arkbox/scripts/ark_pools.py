#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""卡池 UP 与池型数据（歪不歪判断）。

数据源: https://weedy.prts.wiki/gacha_table.json（PRTS 维护的游戏卡池表镜像，
与官方寻访记录接口的 poolId 同源，均为游戏内 gachaPoolId）
缓存: ~/.arkbox/cache/gacha_pool_table.json

口径修正（v2）：
- 「限定」只认 limitedChar 或官方 RATE_UP_6 文案里的「限定寻访」；
  不再把「单 UP」推断成限定（联动池也常是单 UP）。
- 池型：限定 / 中坚 / 联动 / 标准 / 特殊 / 待核。
- 旧缓存没有池型字段时，统一标「待核」，不沿用旧的 limited 误判；
  联网拉取成功后自动写入 v2 缓存。
零第三方依赖。
"""

import json
import os
import sys
import urllib.request

# Windows 终端默认编码（cp1252/GBK）无法输出 ⚠/✓ 等符号：统一强制 UTF-8 输出
for _stdio in (sys.stdout, sys.stderr):
    try:
        _stdio.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

POOL_URL = "https://weedy.prts.wiki/gacha_table.json"
CACHE_PATH = os.path.expanduser("~/.arkbox/cache/gacha_pool_table.json")
CACHE_VERSION = 3

UNKNOWN_META = {
    "six_up": [],
    "limited": False,
    "pool_type": "unknown",
    "pool_type_label": "池型待核",
    "rate_up_label": None,
    "pity_domain": None,
    "pity_domain_label": "计数域待核",
    "domain_shared": False,
}


def _six_up(di):
    six_up = []
    up = di.get("upCharInfo") or {}
    for grp in up.get("perCharList") or []:
        if grp.get("rarityRank") == 5:  # 0-indexed，5 = 六星
            six_up.extend(grp.get("charIdList") or [])
    return six_up


def _rate_up_label(di):
    for obj in di.get("gachaObjList") or []:
        if obj.get("gachaObject") == "RATE_UP_6":
            return obj.get("param")
    return None


def _with_domain(pid, info):
    """补齐 v2 缓存缺少的官方计数域元数据字段（仅说明用）。"""
    info = dict(info or {})
    if not info.get("pity_domain"):
        pool_type = info.get("pool_type") or "unknown"
        if pool_type == "standard":
            domain, label, shared = "standard", "标准（跨期）", True
        elif pool_type == "kernel":
            domain, label, shared = "kernel", "中坚（跨期）", True
        elif pool_type == "limited":
            domain, label, shared = f"limited:{pid}", "限定（当期）", False
        elif pool_type == "linkage":
            domain, label, shared = f"linkage:{pid}", "联动（当期）", False
        elif pool_type == "special":
            domain, label, shared = f"special:{pid}", "特殊（当期）", False
        else:
            domain, label, shared = f"unknown:{pid}", "计数域待核", False
        info["pity_domain"] = domain
        info["pity_domain_label"] = label
        info["domain_shared"] = shared
    return info


def parse_pool_table(d):
    """把 PRTS gacha_table.json 解析成 {poolId: info}。可单测。"""
    out = {}
    for entry in d.get("gachaPoolClient", []):
        pid = entry.get("gachaPoolId")
        if not pid:
            continue
        gd = entry.get("gachaPoolDetail") or {}
        di = gd.get("detailInfo") or {}
        six_up = _six_up(di)
        rate_label = _rate_up_label(di)
        limited = bool(di.get("limitedChar")) or bool(rate_label and "限定" in rate_label)
        if limited:
            pool_type, type_label = "limited", "限定"
        elif rate_label and "中坚" in rate_label:
            pool_type, type_label = "kernel", "中坚"
        elif pid.startswith("LINKAGE") or (rate_label and "联动" in rate_label):
            pool_type, type_label = "linkage", "联动"
        elif rate_label and "标准" in rate_label:
            pool_type, type_label = "standard", "标准"
        elif rate_label:
            pool_type, type_label = "special", "特殊"
        else:
            pool_type, type_label = "unknown", "池型待核"

        # 官方六星保底计数域（仅元数据）：标准/中坚跨池；限定/联动/特殊按当期。
        # 计算层不跨池合并，见 ark_domains.py。
        if pool_type == "standard":
            domain, domain_label, shared = "standard", "标准（跨期）", True
        elif pool_type == "kernel":
            domain, domain_label, shared = "kernel", "中坚（跨期）", True
        elif pool_type == "limited":
            domain, domain_label, shared = f"limited:{pid}", "限定（当期）", False
        elif pool_type == "linkage":
            domain, domain_label, shared = f"linkage:{pid}", "联动（当期）", False
        elif pool_type == "special":
            domain, domain_label, shared = f"special:{pid}", "特殊（当期）", False
        else:
            domain, domain_label, shared = f"unknown:{pid}", "计数域待核", False

        out[pid] = {
            "six_up": six_up,
            "limited": limited,
            "pool_type": pool_type,
            "pool_type_label": type_label,
            "rate_up_label": rate_label,
            "pity_domain": domain,
            "pity_domain_label": domain_label,
            "domain_shared": shared,
        }
    return out


def _normalize_legacy(d):
    """旧缓存（无池型字段）只保留 UP 名单，池型统一标待核。"""
    out = {}
    for pid, info in d.items():
        if pid.startswith("_"):
            continue
        if not isinstance(info, dict) or "pool_type" in info:
            out[pid] = _with_domain(pid, info) if isinstance(info, dict) else info
            continue
        out[pid] = {
            "six_up": info.get("six_up") or [],
            "limited": False,          # 旧口径的 limited 不可信，不沿用
            "pool_type": "unknown",
            "pool_type_label": "池型待核",
            "rate_up_label": None,
            "pity_domain": f"unknown:{pid}",
            "pity_domain_label": "计数域待核",
            "domain_shared": False,
        }
    return out


def _read_cache():
    if not os.path.exists(CACHE_PATH):
        return None
    try:
        with open(CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _write_cache(table):
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    payload = dict(table)
    payload["_meta"] = {"version": CACHE_VERSION, "source": POOL_URL}
    tmp = CACHE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    os.replace(tmp, CACHE_PATH)


def _fetch():
    req = urllib.request.Request(POOL_URL, headers={"User-Agent": "arkbox/0.5"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        d = json.loads(resp.read().decode("utf-8"))
    return parse_pool_table(d)


def load_pool_table(force_refresh=False):
    """返回 {poolId: info}；失败时尽量回落旧缓存（池型标待核）。"""
    cached = None if force_refresh else _read_cache()
    if cached:
        version = (cached.get("_meta") or {}).get("version")
        if version == CACHE_VERSION:
            return {k: v for k, v in cached.items() if not k.startswith("_")}
    try:
        table = _fetch()
        _write_cache(table)
        return table
    except Exception as e:  # 网络/解析失败都优雅降级
        print(f"警告: 卡池表下载失败（UP/池型判断将降级）: {e}", file=sys.stderr)
        if cached:
            return _normalize_legacy(cached)
        return {}


class PoolUpIndex:
    """按 poolId 查 UP 与池型；无法匹配时返回 known=False，不硬判。"""

    def __init__(self):
        self.table = load_pool_table()

    def info(self, pool_id):
        info = self.table.get(pool_id)
        if info:
            return _with_domain(pool_id, info)
        meta = dict(UNKNOWN_META)
        meta["pity_domain"] = f"unknown:{pool_id}"
        return meta

    def judge(self, pool_id, six_star_char_ids):
        info = self.info(pool_id)
        known = bool(info.get("six_up"))
        ups = set(info.get("six_up") or [])
        results = [cid in ups for cid in six_star_char_ids] if known else [None] * len(six_star_char_ids)
        hit_count = sum(1 for x in results if x) if known else None
        return {
            "known": known,
            "up_list": list(ups),
            "limited": bool(info.get("limited")),
            "pool_type": info.get("pool_type") or "unknown",
            "pool_type_label": info.get("pool_type_label") or "池型待核",
            "pity_domain": info.get("pity_domain") or f"unknown:{pool_id}",
            "pity_domain_label": info.get("pity_domain_label") or "计数域待核",
            "domain_shared": bool(info.get("domain_shared")),
            "results": results,
            "hit_count": hit_count,
            "total": len(six_star_char_ids),
            "all_up": bool(known and results and all(results)),
            "any_up": bool(known and any(results)),
        }


if __name__ == "__main__":
    idx = PoolUpIndex()
    n = len(idx.table)
    from collections import Counter
    types = Counter(v.get("pool_type_label", "?") for v in idx.table.values())
    n_up = sum(1 for v in idx.table.values() if v.get("six_up"))
    print(f"✓ 卡池表加载：{n} 个池，含六星 UP 的 {n_up} 个")
    print("  池型：" + " / ".join(f"{k} {v}" for k, v in types.most_common()))
    for pid in ("LIMITED_76_0_1", "LINKAGE_77_0_1", "SINGLE_78_0_1"):
        if pid in idx.table:
            info = idx.table[pid]
            print(f"  {pid}: {info['pool_type_label']} / UP {info['six_up']}")
