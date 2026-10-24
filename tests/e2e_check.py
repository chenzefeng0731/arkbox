#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ArkBox 端到端冒烟：不登录、不读凭证，走真实 CLI 全链路。

检查项：
  C1 demo 全链路：fixtures → 海报 + HTML，关键数字/称号/页头/隐私断言
  C2 Markdown 输出：--detail --audit 的口径与人话
  C3 坏输入拒绝：格式错误 → 人话报错而非 traceback
  C4 未登录引导：无凭证 → 人话提示「请先登录」，无 traceback
  C5 站点目录：--site 生成 dist/robots/meta，noindex 且不落演示昵称

用法：python3 tests/e2e_check.py（仓库根或任意目录均可）
CI 与本地通用；需要网络（首次拉卡池表）与本机浏览器（可选，出 PNG）。
"""

import glob
import os
import re
import subprocess
import sys
import tempfile
import time

# Windows 终端默认编码（cp1252/GBK）无法输出 ⚠/✓ 等符号：统一强制 UTF-8 输出
for _stdio in (sys.stdout, sys.stderr):
    try:
        _stdio.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skill", "arkbox", "scripts")
GACHA = os.path.join(SCRIPTS, "ark_gacha.py")
FIXTURES = os.path.join(ROOT, "fixtures", "demo-records.jsonl")

sys.path.insert(0, SCRIPTS)

FAILED = []


def check(name, ok, detail=""):
    mark = "✓" if ok else "✗"
    print(f"  {mark} {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILED.append(name)


def run_cli(args, cwd, env_extra=None, timeout=300):
    env = dict(os.environ, ARKBOX_NO_OPEN="1")
    if env_extra:
        env.update(env_extra)
    return subprocess.run([sys.executable, GACHA, "analyze"] + args,
                          capture_output=True, text=True, cwd=cwd,
                          env=env, timeout=timeout)


def newest(pattern):
    files = glob.glob(os.path.expanduser(pattern))
    return max(files, key=os.path.getmtime) if files else None


def main():
    print("ArkBox E2E 冒烟（不登录）")
    tmp = tempfile.mkdtemp(prefix="arkbox_e2e_")

    # C1 demo 全链路 ---------------------------------------------------
    print("[C1] demo 全链路：fixtures → 海报 + HTML")
    r = run_cli(["--records", FIXTURES, "--nick", "演示博士",
                 "--tenure", "2023-01-15", "--poster", "--html", "--quiet"], tmp)
    check("CLI 退出码为 0", r.returncode == 0, r.stderr[-400:])
    check("海报生成提示", "海报已生成" in r.stderr, r.stderr[-300:])
    check("HTML 生成提示", "HTML 报告已生成" in r.stderr, r.stderr[-300:])
    html_path = newest("~/.arkbox/reports/gacha_*.html")
    check("报告文件存在", bool(html_path))
    page = open(html_path, encoding="utf-8").read() if html_path else ""
    check("称号=双金还债", "双金还债" in page)
    check("总抽数=294", "294" in page)
    check("池内均值=23.4", "23.4" in page)
    check("理论位置=95.3", "95.3" in page)
    check("页头入职段", "入职 2023-01-15" in page)
    check("页头昵称", "演示博士" in page)
    check("无 UID 展示", re.search(r"UID[^<\n]{0,4}\d{3,}", page) is None)
    from ark_gacha import _find_browser
    if _find_browser():
        png = newest("~/.arkbox/reports/poster_*.png")
        size = os.path.getsize(png) if png else 0
        check("海报 PNG 生成（>30KB）", size > 30 * 1024, f"size={size}")
    else:
        print("  - 本机无 Chrome/Edge，跳过 PNG 断言（CI 各平台均预装浏览器）")

    # C2 Markdown ------------------------------------------------------
    print("[C2] Markdown 口径输出")
    r = run_cli(["--records", FIXTURES, "--nick", "演示博士", "--detail", "--audit"], tmp)
    check("Markdown 退出码 0", r.returncode == 0, r.stderr[-300:])
    for kw in ("双金还债", "按池独立", "不跨池合并", "294", "95.3", "称号候选"):
        check(f"Markdown 含「{kw}」", kw in r.stdout)

    # C3 坏输入 --------------------------------------------------------
    print("[C3] 坏输入拒绝")
    bad = os.path.join(tmp, "bad.jsonl")
    with open(bad, "w", encoding="utf-8") as f:
        f.write('{"nope": 1}\n')
    r = run_cli(["--records", bad], tmp)
    check("退出码 2", r.returncode == 2)
    check("人话报错", "读取记录失败" in r.stderr, r.stderr[-300:])
    check("无裸 traceback", "Traceback" not in r.stderr)

    # C4 未登录 --------------------------------------------------------
    print("[C4] 未登录引导")
    fake_home = os.path.join(tmp, "home")
    os.makedirs(fake_home, exist_ok=True)
    r = run_cli([], tmp, env_extra={"HOME": fake_home, "USERPROFILE": fake_home})
    check("退出码 2", r.returncode == 2, r.stderr[-200:])
    check("提示先登录", "请先登录" in r.stderr, r.stderr[-300:])
    check("无裸 traceback", "Traceback" not in r.stderr)

    # C5 站点目录 ------------------------------------------------------
    print("[C5] 站点目录生成")
    site_dir = os.path.join(tmp, "site")
    r = run_cli(["--records", FIXTURES, "--site", "--site-dir", site_dir, "--quiet"], tmp)
    check("站点生成退出码 0", r.returncode == 0, r.stderr[-400:])
    index = os.path.join(site_dir, "dist", "index.html")
    check("dist/index.html 存在", os.path.exists(index))
    check("robots.txt 存在", os.path.exists(os.path.join(site_dir, "dist", "robots.txt")))
    check(".arkbox-site.json 存在", os.path.exists(os.path.join(site_dir, ".arkbox-site.json")))
    if os.path.exists(index):
        page = open(index, encoding="utf-8").read()
        check("noindex", 'name="robots" content="noindex,nofollow,noarchive"' in page)
        check("站点昵称固定博士", "公开分享页" in page and "演示博士" not in page)
        check("站点无 UID 展示", re.search(r"UID[^<\n]{0,4}\d{3,}", page) is None)

    print()
    if FAILED:
        print(f"✗ E2E 失败 {len(FAILED)} 项：{'、'.join(FAILED)}")
        sys.exit(1)
    print("✓ E2E 全部通过")


if __name__ == "__main__":
    main()
