#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重新生成 README 演示图（docs/demo-*.png）。

数据口径（与 fixtures/README.md 一致）：
- 寻访记录：fixtures/demo-records.jsonl（合成，时间轴平移，无账号标识）；
- 干员持有：本脚本用 char_id 的 md5 确定性合成的演示 box，**不是任何真实账号的
  持有数据**；头像等展示元数据来自本地 operator_meta 缓存（公开游戏数据）。

需要：本机 Chrome/Edge/Chromium（截图）；~/.arkbox/cache/operator_meta.json
（缺省时先跑一次在线分析让它下载，或删除缓存触发重下）。

用法：python3 tools/make_demo_images.py
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skill" / "arkbox" / "scripts"))
os.environ.setdefault("ARKBOX_NO_OPEN", "1")  # 不弹浏览器

from ark_gacha import (  # noqa: E402
    _load_records_file, _find_browser, _demo_tenure, analyze_records,
    export_poster_png, _render_share_posters,
)
from ark_pools import PoolUpIndex  # noqa: E402
from ark_domains import build_pool_stats, apply_pool_meta  # noqa: E402
from ark_archive import coverage_report  # noqa: E402
from ark_report import build_report  # noqa: E402
from ark_archive_html import build_archive_html  # noqa: E402
from ark_meta import load_meta  # noqa: E402

NICK = "演示博士"
TENURE = "2024-07-14"  # 页头「入职 · N 天」演示日期
DOCS = ROOT / "docs"

# 每张截图的视口（CSS 像素；物理像素 ×2）。高度按页签内容取：
# 寻访分析长报告取首屏信息密度最高的上半段；泰拉图鉴要装下地图 + 地区面板；
# 分享弹层是固定遮罩，取遮罩整屏。
SHOTS = {
    "demo-archive.png": ("#gacha", 1440, 1560),
    "demo-terra.png": ("#terra", 1440, 1860),
    "demo-share.png": ("#share-modal", 1440, 1100),
}


def _h(cid: str) -> int:
    return int(hashlib.md5(cid.encode()).hexdigest()[:8], 16)


def synth_box(records, meta_chars):
    """确定性合成演示 box：让泰拉地图/干员网格有真实观感，且不对应任何真实账号。"""
    six_in_records = {r["charId"] for r in records
                      if r.get("rarity", 0) >= 5 and r.get("charId")}
    chars = []
    for cid, m in sorted(meta_chars.items()):
        rar = m.get("rarity") or 0
        h = _h(cid)
        if rar == 6:
            own = (h % 100 < 66) or (cid in six_in_records)
        elif rar == 5:
            own = h % 100 < 72
        elif rar == 4:
            own = h % 100 < 60
        else:
            own = h % 100 < 92
        if not own:
            continue
        h2, h3, h4, h5, h6, h7 = (_h(cid + s) for s in "234567")
        if rar == 6:
            evolve = 2 if h3 % 100 < 85 else 1
            level = (40 + h2 % 51) if evolve == 2 else (30 + h2 % 21)
        elif rar == 5:
            evolve = 2 if h3 % 100 < 55 else 1
            level = (30 + h2 % 51) if evolve == 2 else (20 + h2 % 31)
        elif rar == 4:
            evolve = 2 if h3 % 100 < 30 else 1
            level = (30 + h2 % 31) if evolve == 2 else (15 + h2 % 26)
        else:
            evolve = 1
            level = 30 + h2 % 26
        chars.append({
            "char_id": cid, "name": m.get("name") or cid, "rarity": rar,
            "profession": m.get("profession") or "?", "level": level,
            "evolve": evolve,
            "potential": 1 + (1 + h4 % 5 if h4 % 100 < 30 else 0),
            "skill": 7, "mastery": (3 if rar == 6 and evolve == 2 and h5 % 100 < 55 else 0),
            "mod": h6 % 100 < 25, "skin_id": f"skin#{h7}" if h7 % 100 < 30 else "",
        })
    return chars


def shot(browser, html_path, out_png, width, height, frag="", extra_js=""):
    url = f"file://{html_path}{frag}"
    tmp = None
    if extra_js:
        text = Path(html_path).read_text(encoding="utf-8")
        tmp = Path(str(html_path) + ".demo.html")
        tmp.write_text(text.replace("</body>", f"<script>{extra_js}</script></body>"),
                       encoding="utf-8")
        url = f"file://{tmp}"
    subprocess.run([browser, "--headless", "--disable-gpu", "--hide-scrollbars",
                    "--force-device-scale-factor=2",
                    "--virtual-time-budget=15000",  # 等懒加载头像落地
                    f"--screenshot={out_png}", f"--window-size={width},{height}", url],
                   capture_output=True, timeout=90)
    if tmp:
        tmp.unlink()
    if not Path(out_png).exists():
        raise SystemExit(f"截图失败：{out_png}")


def main():
    browser = _find_browser()
    if not browser:
        raise SystemExit("未找到 Chrome/Edge/Chromium，无法截图。")

    recs = _load_records_file(str(ROOT / "fixtures" / "demo-records.jsonl"))
    pool_index = PoolUpIndex()
    stats, _ = analyze_records(recs, pool_index)
    pool_data = build_pool_stats(recs, pool_index)
    apply_pool_meta(stats, pool_data)
    report = build_report(stats, NICK, coverage_report(recs),
                          domain=pool_data, tenure=_demo_tenure(TENURE))

    meta = load_meta()  # 返回 {char_id: {...}} 本身（见 ark_meta.load_meta）
    chars = synth_box(recs, meta)
    n6 = sum(1 for c in chars if c["rarity"] == 6)
    print(f"演示 box：{len(chars)} 名干员（六星 {n6}），合成数据", file=sys.stderr)

    work = Path(tempfile.mkdtemp(prefix="arkbox-demo-"))
    try:
        # 1) 海报 PNG（沿用生产海报管线）
        _, poster = export_poster_png(report, str(work / "poster.html"),
                                      theme="B", keep_source=False)
        shutil.copyfile(poster, DOCS / "demo-poster.png")
        print(f"✓ docs/demo-poster.png", file=sys.stderr)

        # 2) 档案页（内嵌分享海报，弹层才有内容可预览）
        posters = _render_share_posters(report, chars, str(work), "demo")
        html = build_archive_html(
            report, chars, str(work / "archive.html"), meta=meta,
            poster_b64=posters.get("gacha"), poster_terra_b64=posters.get("terra"))

        for name, (frag, w, hgt) in SHOTS.items():
            js = ""
            if frag == "#share-modal":  # 特殊标记：自动点分享按钮，截弹层
                js = ("window.addEventListener('load',function(){"
                      "setTimeout(function(){var b=document.getElementById('fab-share');"
                      "if(b)b.click();},500);});")
                frag = ""
            shot(browser, html, str(DOCS / name), w, hgt, frag=frag, extra_js=js)
            print(f"✓ docs/{name}", file=sys.stderr)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
