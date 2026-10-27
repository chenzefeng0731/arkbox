#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""泰拉图鉴数据层：干员 → 地区分桶 → 六边形布局 → 可嵌入 HTML 的 JSON。

口径（与 docs/地图图鉴-调研/调研报告.md 一致）：
  - nationId = 所属编制（非出身地）；萨卡兹无 nationId，按 groupId=babel / teamId=followers
    归卡兹戴尔（临光 char_148_nearl 除外：使徒成员但设定为卡西米尔人，归卡西米尔）；
  - 联动干员（彩虹六号/迷宫饭/P5R/MyGO）单列"非泰拉"；
  - 龙门是独立 nationId；玻利瓦尔暂无六星，显示为空档案；
  - 一个六边形 = 一名已实装六星；地图剪影为程序化示意，非官方测绘。

零第三方依赖。布局在生成期算死（确定性），前端只做渲染与交互。
"""

import heapq  # noqa: F401 (保留：未来扩展布局用)
import json
import math
import os

_ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
_SILHOUETTE_PATH = os.path.join(_ASSETS, "terra_silhouette.paths")

HEX_S = 12.0
SQRT3 = math.sqrt(3)

# id: (中文, 英文, 锚点, 强调色, 类型)
REGIONS = {
    "sami":        ("萨米", "SAMI", (496, 104), "#7fa89a", "land"),
    "ursus":       ("乌萨斯", "URSUS", (744, 128), "#7a8a9a", "land"),
    "higashi":     ("东", "HIGASHI", (1120, 95), "#b86f6f", "land"),
    "bolivar":     ("玻利瓦尔", "BOLIVAR", (216, 184), "#8a7a5a", "land"),
    "columbia":    ("哥伦比亚", "COLUMBIA", (372, 180), "#5b8fb8", "land"),
    "kazimierz":   ("卡西米尔", "KAZIMIERZ", (556, 160), "#8f8a6a", "land"),
    "kjerag":      ("谢拉格", "KJERAG", (476, 208), "#6f9aa8", "land"),
    "leithanien":  ("莱塔尼亚", "LEITHANIEN", (744, 208), "#7f6fa8", "land"),
    "kazdel":      ("卡兹戴尔", "KAZDEL", (896, 210), "#8f4f4f", "land"),
    "yan":         ("炎", "YAN", (1040, 185), "#c96b4a", "land"),
    "victoria":    ("维多利亚", "VICTORIA", (592, 252), "#b8a35b", "land"),
    "siracusa":    ("叙拉古", "SIRACUSA", (808, 240), "#8a6f8f", "land"),
    "minos":       ("米诺斯", "MINOS", (380, 284), "#b89a6a", "land"),
    "laterano":    ("拉特兰", "LATERANO", (752, 288), "#d8c27a", "land"),
    "rim":         ("雷姆必拓", "RIM BILLITON", (1050, 400), "#8a9a6a", "land"),
    "sargon":      ("萨尔贡", "SARGON", (272, 344), "#a8824a", "land"),
    "iberia":      ("伊比利亚", "IBERIA", (700, 384), "#4f8f7f", "land"),
    "lungmen":     ("龙门", "LUNGMEN", (960, 300), "#d98f4a", "land"),
    "egir":        ("阿戈尔", "ÆGIR", (720, 500), "#3f7f8f", "land"),
    "rhodes":      ("罗德岛本舰", "RHODES ISLAND", (140, 498), "#5fb6c9", "special"),
    "collab":      ("联动", "NON-TERRA", (1160, 498), "#6a6f78", "special"),
}
REGION_ORDER = list(REGIONS)

# nationId 为空的干员按 group/team 归桶
_FALLBACK_BUCKET = {
    "group": {"babel": "kazdel"},
    "team": {"followers": "kazdel", "rainbow": "collab",
             "laios": "collab", "sees": "collab", "mujica": "collab"},
}

MANUAL_LABELS = {
    "rhodes": (140, 583),
    "collab": (1160, 583),
    "bolivar": (216, 128),
}

# 显式覆写（世界观审计 2026-10-27）：临光虽为 teamId=followers（使徒），
# 但设定上是卡西米尔骑士，与其异格"耀骑士临光"（nationId=kazimierz）一致，归卡西米尔。
# 修掉"使徒 → 卡兹戴尔"的误归，防止设定党挑刺。
_MANUAL_BUCKET = {"char_148_nearl": "kazimierz"}


def bucket_of(cid, entry):
    """meta 条目 → 地区 id。"""
    manual = _MANUAL_BUCKET.get(cid)
    if manual:
        return manual
    nation = entry.get("nation") or ""
    if nation:
        return nation
    group = entry.get("group") or ""
    team = entry.get("team") or ""
    if _FALLBACK_BUCKET["group"].get(group):
        return _FALLBACK_BUCKET["group"][group]
    if _FALLBACK_BUCKET["team"].get(team):
        return _FALLBACK_BUCKET["team"][team]
    return "collab"  # 无归属的联动/特殊干员保守归"非泰拉"


# ── 六边形几何 ────────────────────────────────────────────

def _hex_to_pixel(q, r, s=HEX_S):
    return s * SQRT3 * (q + r / 2.0), s * 1.5 * r


def _pixel_to_hex(x, y, s=HEX_S):
    rf = y / (1.5 * s)
    qf = x / (s * SQRT3) - rf / 2.0
    xf, zf = qf, rf
    yf = -xf - zf
    rx, ry, rz = round(xf), round(yf), round(zf)
    dx, dy, dz = abs(rx - xf), abs(ry - yf), abs(rz - zf)
    if dx > dy and dx > dz:
        rx = -ry - rz
    elif dy > dz:
        ry = -rx - rz
    else:
        rz = -rx - ry
    return int(rx), int(rz)


def _hex_points(x, y, s=HEX_S):
    return " ".join(
        f"{x + s * math.cos(math.radians(30 + 60 * i)):.1f},{y + s * math.sin(math.radians(30 + 60 * i)):.1f}"
        for i in range(6))


def _block_widths(n):
    """把 n 个六星排成近 4:3 的块，返回每行宽度。"""
    if n <= 0:
        return []
    if n == 1:
        return [1]
    if n == 2:
        return [2]
    w = max(2, round(math.sqrt(n * 0.95)))
    rows = math.ceil(n / w)
    base, extra = divmod(n, rows)
    widths = [base] * rows
    order = sorted(range(rows), key=lambda i: (abs(i - (rows - 1) / 2), i))
    for i in order[:extra]:
        widths[i] += 1
    return widths


def _blob_cells(n):
    widths = _block_widths(n)
    cells = []
    for r, w in enumerate(widths):
        q0 = -((w - 1) // 2) - (r // 2) - (1 if (w % 2 == 0 and r % 2 == 1) else 0)
        cells.extend((q, r) for q in range(q0, q0 + w))
    return cells


def _blob_bbox(cells, s=HEX_S, pad=None):
    pad = pad if pad is not None else s * 1.05
    xs = [s * SQRT3 * (q + r / 2.0) for q, r in cells]
    ys = [s * 1.5 * r for q, r in cells]
    return min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad


def _layout(regions):
    """块状簇放置：按 6★ 数量从大到小；锚点被占则就近外推（确定性）。"""
    placed = {}
    order = sorted([r for r in regions if r["total6"] > 0],
                   key=lambda r: (-r["total6"], REGION_ORDER.index(r["id"])))
    shift_px = {(dq, dr): (HEX_S * SQRT3 * (dq + dr / 2.0), HEX_S * 1.5 * dr)
                for dq in range(-8, 9) for dr in range(-5, 6)}
    for reg in order:
        base = _blob_cells(reg["total6"])
        bx0, by0, bx1, by1 = _blob_bbox(base)
        bcx, bcy = (bx0 + bx1) / 2, (by0 + by1) / 2
        ax, ay = reg["anchor"]
        qa, ra = _pixel_to_hex(ax, ay - 6)
        ax_pix = HEX_S * SQRT3 * (qa + ra / 2.0)
        ay_pix = HEX_S * 1.5 * ra
        want_dx = ax - bcx - ax_pix
        want_dy = (ay - 6) - bcy - ay_pix
        cands = sorted(shift_px.items(),
                       key=lambda kv: math.hypot(kv[1][0] - want_dx, kv[1][1] - want_dy))
        chosen = None
        for (dq, dr), _ in cands:
            cells = [(q + qa + dq, r + ra + dr) for q, r in base]
            x0, y0, x1, y1 = _blob_bbox(cells, pad=HEX_S * 0.9)
            if x0 < 6 or x1 > 1274 or y0 < 84 or y1 > 596:
                continue
            clash = False
            for ocells in placed.values():
                ox0, oy0, ox1, oy1 = _blob_bbox(ocells, pad=HEX_S * 0.9)
                if x0 < ox1 and x1 > ox0 and y0 < oy1 and y1 > oy0:
                    clash = True
                    break
            if not clash:
                chosen = cells
                break
        if chosen is None:
            chosen = [(q + qa, r + ra) for q, r in base]
        placed[reg["id"]] = chosen
    return placed


def _label_layout(regions):
    """自动放标签：上/下/左/右 + 远档候选，按重叠面积最小兜底。"""
    boxes = {}
    for r in regions:
        cells = r.get("cells") or []
        if cells:
            boxes[r["id"]] = _blob_bbox(cells, pad=HEX_S * 0.6)
        else:
            x, y = r["anchor"]
            boxes[r["id"]] = (x - 24, y - 24, x + 24, y + 24)
    placed = []
    out = []
    h = 34
    for r in regions:
        full = r["total6"] > 0 and r["owned6"] == r["total6"]
        if r["total6"] == 0:
            count = "—"
        elif full:
            count = f"◆ {r['owned6']}/{r['total6']}"
        else:
            count = f"{r['owned6']}/{r['total6']}"
        name = r["name"]
        w = 128 if r["id"] == "rhodes" else max(76, 13 * len(name) + 56)
        bx0, by0, bx1, by1 = boxes[r["id"]]
        cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
        manual = MANUAL_LABELS.get(r["id"])
        if manual:
            cands = [(manual[0] - w / 2, manual[1])]
        else:
            cands = [(cx - w / 2, by0 - h - 7), (cx - w / 2, by1 + 7),
                     (bx0 - w - 12, cy - h / 2), (bx1 + 12, cy - h / 2),
                     (cx - w / 2, by0 - h - 45), (cx - w / 2, by1 + 45)]

        def overlap(rect):
            area = 0.0
            for oid, ob in boxes.items():
                if oid == r["id"]:
                    continue
                ox = min(rect[2], ob[2] + 4) - max(rect[0], ob[0] - 4)
                oy = min(rect[3], ob[3] + 4) - max(rect[1], ob[1] - 4)
                if ox > 0 and oy > 0:
                    area += ox * oy
            for pr in placed:
                ox = min(rect[2], pr[2] + 3) - max(rect[0], pr[0] - 3)
                oy = min(rect[3], pr[3] + 3) - max(rect[1], pr[1] - 3)
                if ox > 0 and oy > 0:
                    area += ox * oy
            return area

        best = None
        for lx, ly in cands:
            rect = (lx, ly, lx + w, ly + h)
            if rect[1] < 26 or rect[3] > 619 or rect[0] < 4 or rect[2] > 1276:
                continue
            a = overlap(rect)
            if a == 0:
                best = (lx, ly, rect, 0.0)
                break
            if best is None or a < best[3]:
                best = (lx, ly, rect, a)
        if best is None:
            lx, ly = cx - w / 2, max(28, by0 - h - 7)
            best = (lx, ly, (lx, ly, lx + w, ly + h), 0.0)
        lx, ly, rect, _ = best
        placed.append(rect)
        leader = ""
        gap = min(abs(rect[1] - by1), abs(by0 - rect[3]), abs(rect[0] - bx1), abs(bx0 - rect[2]))
        if gap > 14:
            if rect[3] <= by0:
                leader = (cx, rect[3], cx, by0 - 3)
            elif rect[1] >= by1:
                leader = (cx, rect[1], cx, by1 + 3)
            elif rect[2] <= bx0:
                leader = (rect[2], cy, bx0 - 3, cy)
            else:
                leader = (rect[0], cy, bx1 + 3, cy)
        out.append({"id": r["id"], "x": round(lx, 1), "y": round(ly, 1), "w": w,
                    "name": name, "count": count, "full": full,
                    "empty": r["total6"] == 0, "near": r["total6"] - r["owned6"] == 1,
                    "color": r["color"],
                    "ratio": round(r["owned6"] / r["total6"], 4) if r["total6"] else 0,
                    "leader": leader})
    return out


def load_silhouette():
    """大陆剪影（程序化示意，potrace 路径 JSON）。缺失时返回空列表（地图退化为无底图）。"""
    try:
        with open(_SILHOUETTE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def build_terra(meta, owned_ids, nick=None, date=None):
    """meta: ark_meta 元数据 dict；owned_ids: 已持有 charId 集合。

    返回可直接 json.dumps 进 HTML 的 dict。
    """
    buckets = {rid: [] for rid in REGION_ORDER}
    for cid, e in meta.items():
        buckets[bucket_of(cid, e)].append({
            "id": cid, "name": e.get("name") or cid,
            "dn": e.get("dn") or "", "rarity": e.get("rarity") or 0,
            "owned": cid in owned_ids,
        })
    regions = []
    for rid in REGION_ORDER:
        cn, en, anchor, color, area = REGIONS[rid]
        ops = buckets[rid]
        six = [o for o in ops if o["rarity"] == 6]
        six.sort(key=lambda o: (not o["owned"], o["dn"]))
        regions.append({
            "id": rid, "name": cn, "en": en, "color": color, "area": area,
            "anchor": list(anchor), "total6": len(six),
            "owned6": sum(o["owned"] for o in six),
            "totalAll": len(ops), "ownedAll": sum(o["owned"] for o in ops),
            "missing6": [o["name"] for o in six if not o["owned"]],
            "ops": six,
        })
    cells_map = _layout(regions)
    for r in regions:
        r["cells"] = sorted(cells_map.get(r["id"], []), key=lambda qr: (qr[1], qr[0]))
    labels = _label_layout(regions)

    land = [r for r in regions if r["area"] == "land"]
    full = [r for r in land if r["total6"] and r["owned6"] == r["total6"]]
    near = [r for r in land if r["total6"] and r["total6"] - r["owned6"] == 1]
    six_total = sum(r["total6"] for r in regions)
    six_owned = sum(r["owned6"] for r in regions)
    all_total = sum(r["totalAll"] for r in regions)
    all_owned = sum(r["ownedAll"] for r in regions)
    return {
        "silhouette": load_silhouette(),
        "regions": regions,
        "labels": labels,
        "meta": {
            "nick": nick, "date": date,
            "sixOwned": six_owned, "sixTotal": six_total,
            "allOwned": all_owned, "allTotal": all_total,
            "regionsFull": len(full), "regionsTotal": len([r for r in land if r["total6"]]),
            "near": [{"id": r["id"], "name": r["name"], "owned6": r["owned6"],
                      "total6": r["total6"], "missing": r["missing6"]} for r in
                     sorted(near, key=lambda r: -r["total6"])],
            "fullIds": [r["id"] for r in full],
            "pct": round(six_owned / six_total * 100, 1) if six_total else 0,
        },
    }


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from ark_meta import load_meta
    terra = build_terra(load_meta(), set(), date="test")
    m = terra["meta"]
    print(f"六星 {m['sixOwned']}/{m['sixTotal']} · 地区 {len(terra['regions'])} · "
          f"标签 {len(terra['labels'])} · 剪影路径 {len(terra['silhouette'])} 条")
    assert m["sixTotal"] == 138, f"六星总数漂移: {m['sixTotal']}"
    assert len(terra["regions"]) == 21
    cells = sum(len(r["cells"]) for r in terra["regions"])
    assert cells == 138, f"格子总数 {cells} != 138"
    print("self-check OK")
