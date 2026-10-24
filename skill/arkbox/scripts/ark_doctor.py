#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""环境与凭证自检：给新手的 one-command doctor。"""

import os
import platform
import sys

from skland_core import ArkApiError, ensure_auth, load_creds, mask_uid
from ark_archive import load as archive_load

# Windows 终端默认编码（cp1252/GBK）无法输出 ⚠/✓ 等符号：统一强制 UTF-8 输出
for _stdio in (sys.stdout, sys.stderr):
    try:
        _stdio.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def main():
    print("ArkBox doctor")
    print(f"- 系统: {platform.system()} {platform.release()}")
    print(f"- Python: {sys.version.split()[0]} ({platform.python_implementation()})")
    print(f"- 项目: {os.path.dirname(os.path.dirname(os.path.abspath(__file__)))}")
    try:
        import qrcode  # noqa
        print("- 二维码: 本地 qrcode 可用；缺失时会降级为本地 HTML")
    except Exception:
        print("- 二维码: 未安装 qrcode，将降级为本地 HTML（不阻断）")
    try:
        from ark_gacha import _find_browser
        browser = _find_browser()
        print(f"- 浏览器: {browser or '未找到 Chrome/Edge/Chromium；仅生成 HTML'}")
    except Exception as e:
        print(f"- 浏览器检查失败: {e}")
    try:
        creds = load_creds(required=False)
    except Exception as e:
        print(f"- 凭证读取失败: {e}")
        return
    if not creds:
        print("- 凭证: 未登录。运行 skland_core.py login")
        return
    print(f"- 凭证: 昵称 {creds.get('nick_name') or '—'} | UID {mask_uid(creds.get('uid'))}")
    try:
        creds = ensure_auth(creds, uid=creds.get("uid"))
        print("- 凭证健康: 有效（或已静默续期）")
    except ArkApiError as e:
        print(f"- 凭证健康: 需要重新登录（{e}）")
        return
    records = archive_load(creds.get("uid"))
    print(f"- 本地档案: {len(records)} 条")
    if not records:
        print("  下一步: ark_gacha.py analyze --html")


if __name__ == "__main__":
    main()
