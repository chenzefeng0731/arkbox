#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Install the ArkBox skill into an agent's skills directory, or any custom path.

This is intentionally dependency-free. The skill itself is portable Python;
the target directory only decides where an agent reads SKILL.md and scripts.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Windows 终端默认编码（cp1252/GBK）无法输出 ⚠/✓ 等符号：统一强制 UTF-8 输出
for _stdio in (sys.stdout, sys.stderr):
    try:
        _stdio.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "skill" / "arkbox"


def _default_targets():
    home = Path.home()
    return {
        "qoder": home / ".qoder-cn" / "skills" / "arkbox",
        "qoder-global": home / ".qoder" / "skills" / "arkbox",
        "claude": home / ".claude" / "skills" / "arkbox",
        "generic": home / ".arkbox" / "skill" / "arkbox",
    }


def choose_target(value):
    targets = _default_targets()
    if value in targets:
        return targets[value]
    if value == "auto":
        for key in ("qoder", "qoder-global", "claude"):
            if targets[key].parent.exists():
                return targets[key]
        return targets["generic"]
    return Path(os.path.expanduser(value)).resolve()


def main():
    ap = argparse.ArgumentParser(description="安装 ArkBox skill")
    ap.add_argument("--target", default="auto",
                    help="auto | qoder | qoder-global | claude | generic | 自定义目录")
    ap.add_argument("--force", action="store_true", help="覆盖已有目标目录")
    ap.add_argument("--no-test", action="store_true", help="不跑自测")
    args = ap.parse_args()

    if sys.version_info < (3, 9):
        print("需要 Python 3.9+")
        sys.exit(2)
    if not SOURCE.exists():
        print(f"找不到 skill 源目录: {SOURCE}")
        sys.exit(2)
    target = choose_target(args.target)
    if target.exists() and not args.force:
        print(f"目标已存在: {target}")
        print("如果要覆盖，请加 --force；或把 --target 指向新的目录。")
        sys.exit(1)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and args.force:
        shutil.rmtree(target)
    shutil.copytree(SOURCE, target,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
    print(f"已安装: {target}")
    print("\n下一步：")
    print(f"  python3 {target / 'scripts' / 'skland_core.py'} login")
    print("\n在 Agent 里直接说「用 arkbox 分析我的抽卡记录」；")
    print("如果你在其他 Agent 中：让它读取目标目录的 SKILL.md，或直接调用 scripts/ark_gacha.py。")

    if not args.no_test:
        print("\n运行自测...")
        proc = subprocess.run([sys.executable, str(target / "scripts" / "selftest.py")],
                              capture_output=True, text=True)
        print(proc.stdout.strip())
        if proc.returncode != 0:
            print(proc.stderr.strip())
            print("自测失败；源码已复制，请保留现场排查。")
            sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
