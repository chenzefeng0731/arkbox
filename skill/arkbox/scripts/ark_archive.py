#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地档案化归档（产品红线：重复同步不丢档、不重复记账）。

存储：~/.arkbox/archive/<uid>/records.jsonl（每行一条寻访记录 JSON）
去重键：(poolId, gachaTs, pos, charId) —— 官方记录里该四元组唯一
原则：原始记录不可静默改写，只增并修订；远端窗口收紧不影响已归档数据。

覆盖口径（v0.5 修正）：
- 不再把「本次拉到的最早记录」当成官方窗口起点，也不轻易写「完整」。
- 官方接口不提供账号全历史证明，因此默认「本档案区间 / 仅部分历史（完整性未知）」。
- 有同步失败或分页截断 → 已知缺口；未来若有可验证的全量导入，再标完整连续。
零第三方依赖。
"""

import json
import os
from datetime import datetime

ARCHIVE_ROOT = os.path.expanduser("~/.arkbox/archive")


def _dir(uid):
    return os.path.join(ARCHIVE_ROOT, str(uid))


def _key(r):
    return (r.get("poolId"), str(r.get("gachaTs")), r.get("pos"), r.get("charId"))


def load(uid):
    """读归档，返回记录列表（按时间正序）。文件损坏时返回空并备份坏档。"""
    path = os.path.join(_dir(uid), "records.jsonl")
    if not os.path.exists(path):
        return []
    out = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
    except json.JSONDecodeError:
        # 坏档不覆盖：改名保留，重新开始
        os.replace(path, path + ".corrupt")
        return []
    out.sort(key=lambda r: (int(r.get("gachaTs") or 0), r.get("pos") or 0))
    return out


def _read_meta(uid):
    path = os.path.join(_dir(uid), "meta.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _touch_meta(uid, total, added):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    old = _read_meta(uid)
    meta = {
        "created_at": old.get("created_at") or now,
        "updated_at": now,
        "total": total,
        "last_added": added,
    }
    path = os.path.join(_dir(uid), "meta.json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)
    os.replace(tmp, path)


def merge(uid, new_records):
    """合并新拉取记录进归档。返回 (全量正序记录, 新增条数)。"""
    os.makedirs(_dir(uid), exist_ok=True)
    path = os.path.join(_dir(uid), "records.jsonl")
    old = {_key(r): r for r in load(uid)}
    added = []
    for r in new_records:
        k = _key(r)
        if k not in old:
            old[k] = r
            added.append(r)
    merged = sorted(old.values(), key=lambda r: (int(r.get("gachaTs") or 0), r.get("pos") or 0))
    # 原子写：先写临时文件再替换，避免写一半损坏
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for r in merged:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, path)
    _touch_meta(uid, len(merged), len(added))
    return merged, len(added)


def coverage(records):
    """数据覆盖区间与可信度标签所需信息。"""
    if not records:
        return {"count": 0, "earliest": None, "latest": None}
    ts = [int(r.get("gachaTs", 0)) for r in records]
    fmt = lambda t: datetime.fromtimestamp(t / 1000).strftime("%Y-%m-%d")
    return {"count": len(records), "earliest": fmt(min(ts)), "latest": fmt(max(ts))}


def coverage_report(records, failed_pools=None, truncated_pools=None,
                    complete_verified=False):
    """统一的覆盖状态。

    status:
      none       暂无记录
      known_gap  已知缺口（同步失败 / 分页截断）
      complete   完整连续（仅在调用方有可验证依据时）
      partial    仅部分历史（默认；完整性未知）
    """
    cov = coverage(records)
    failed = list(failed_pools or [])
    truncated = list(truncated_pools or [])
    if not cov["count"]:
        return {
            "count": 0, "earliest": None, "latest": None,
            "status": "none", "label": "暂无记录", "short": "暂无记录",
            "line": "数据档案：暂无记录",
            "failed_pools": failed, "truncated_pools": truncated,
            "integrity_unknown": True,
        }
    if failed or truncated:
        status, label = "known_gap", "本档案区间（已知缺口）"
    elif complete_verified:
        status, label = "complete", "完整连续"
    else:
        status, label = "partial", "本档案区间（仅部分历史，完整性未知）"
    line = (f"数据档案：{label} · 已归档 {cov['count']} 抽"
            f"（{cov['earliest']} ~ {cov['latest']}）")
    if failed:
        line += f" · 本次同步失败 {len(failed)} 池"
    if truncated:
        line += f" · {len(truncated)} 池记录被截断"
    short = f"{label} · {cov['earliest']} ~ {cov['latest']}"
    return {
        "count": cov["count"], "earliest": cov["earliest"], "latest": cov["latest"],
        "status": status, "label": label, "short": short, "line": line,
        "failed_pools": failed, "truncated_pools": truncated,
        "integrity_unknown": status == "partial",
    }


def label_line(report):
    """给三形态输出统一用的数据范围说明行。"""
    return report["line"]
