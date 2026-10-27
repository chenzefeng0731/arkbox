#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""干员元数据（charId → 名字/职业/稀有度）下载与缓存。

数据源: Kengxxiao/ArknightsGameData (国服游戏数据镜像)
缓存: ~/.arkbox/cache/operator_meta.json
零第三方依赖。
"""

import json
import os
import sys
import urllib.error
import urllib.request

from skland_core import ArkApiError

# 主源 raw.githubusercontent.com 在部分网络不可达；jsdelivr 是同一仓库的 CDN 镜像
META_URLS = [
    "https://raw.githubusercontent.com/Kengxxiao/ArknightsGameData/"
    "master/zh_CN/gamedata/excel/character_table.json",
    "https://cdn.jsdelivr.net/gh/Kengxxiao/ArknightsGameData@"
    "master/zh_CN/gamedata/excel/character_table.json",
]
CACHE_PATH = os.path.expanduser("~/.arkbox/cache/operator_meta.json")
# 解析逻辑或上游结构变化时递增，旧缓存自动失效重下
# v2: 增加 nation/group/team/display_number（泰拉图鉴地区归属用）
CACHE_VERSION = 2

PROFESSION_ZH = {
    "PIONEER": "先锋", "WARRIOR": "近卫", "TANK": "重装", "SNIPER": "狙击",
    "CASTER": "术师", "MEDIC": "医疗", "SUPPORTER": "辅助", "SPECIALIST": "特种",
}


def parse_rarity(raw):
    """兼容两种口径：'TIER_6' 字符串（Kengxxiao 镜像，1-6 直接可用）与 0-indexed 数字（5=六星）。"""
    if isinstance(raw, str) and raw.startswith("TIER_"):
        return int(raw.split("_", 1)[1])          # 已是 1-6
    n = int(raw)
    return n + 1 if 0 <= n <= 5 else n            # 0-indexed 转换


def build_meta(raw_table):
    """从 character_table 提取精简映射。输出 rarity 统一为 1-6 星口径。"""
    meta = {}
    for char_id, e in raw_table.items():
        if not isinstance(e, dict):
            continue
        profession = e.get("profession")
        name = e.get("name")
        try:
            rarity = parse_rarity(e.get("rarity"))
        except (TypeError, ValueError):
            continue  # rarity 字段异常（非干员条目）
        if not profession or not name or rarity < 1:
            continue  # 过滤召唤物/装置等非干员条目
        # 排除 NPC 干员与剧情临时单位：正式干员均有 displayNumber 编号（如 R001）
        if not e.get("displayNumber") or char_id.startswith(("token_", "trap_")):
            continue
        meta[char_id] = {
            "name": name,
            "rarity": rarity,  # 统一 1-6 星口径
            "profession": PROFESSION_ZH.get(profession, profession),
            "sub": e.get("subProfessionId", ""),
            # 地区/阵营归属（泰拉图鉴用）：nationId=所属编制，空时按 group/team 推
            "nation": e.get("nationId") or "",
            "group": e.get("groupId") or "",
            "team": e.get("teamId") or "",
            "dn": e.get("displayNumber") or "",
        }
    return meta


def load_meta(force_refresh=False):
    """返回元数据 dict；缓存缺失/版本不符/强制刷新时下载。

    下载失败时降级用旧缓存（并警告）；既无缓存又下载失败才抛 ArkApiError。
    """
    legacy = None  # 版本不符的旧缓存，留作断网降级
    if not force_refresh and os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, encoding="utf-8") as f:
                raw = json.load(f)
            if (isinstance(raw, dict) and raw.get("_version") == CACHE_VERSION
                    and raw.get("chars")):
                return raw["chars"]
            legacy = raw
        except (OSError, json.JSONDecodeError):
            legacy = None
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    print(f"下载干员数据库（约 10MB，仅首次）...", file=sys.stderr)
    last_err = None
    meta = None
    for url in META_URLS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "arkbox/0.7"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = resp.read()
            meta = build_meta(json.loads(body.decode("utf-8")))
            break
        except (urllib.error.URLError, TimeoutError, OSError,
                json.JSONDecodeError, UnicodeDecodeError, ValueError) as e:
            last_err = e
            continue
    if meta is None:
        e = last_err or RuntimeError("未知错误")
        if isinstance(legacy, dict) and legacy:
            chars = {k: v for k, v in legacy.items() if not k.startswith("_")}
            if chars:
                print(f"警告: 干员元数据下载失败，使用旧缓存（干员名可能过时）: {e}",
                      file=sys.stderr)
                return chars
        raise ArkApiError(f"干员元数据下载失败（已试主源与 jsdelivr 镜像）: {e}")
    if not meta:
        raise ArkApiError("干员元数据解析结果为空，请检查上游数据源")
    tmp = CACHE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"_version": CACHE_VERSION, "chars": meta}, f, ensure_ascii=False)
    os.replace(tmp, CACHE_PATH)
    print(f"已缓存 {len(meta)} 名干员元数据 → {CACHE_PATH}", file=sys.stderr)
    return meta


if __name__ == "__main__":
    meta = load_meta(force_refresh="--refresh" in sys.argv)
    # 简单自检输出
    from collections import Counter
    c = Counter(v["rarity"] for v in meta.values())
    print(f"共 {len(meta)} 名干员：六星 {c.get(6, 0)}、五星 {c.get(5, 0)}、四星 {c.get(4, 0)}")
