#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""轻量玩家档案：只取入职日期与天数，用于报告页头。"""

from datetime import datetime

from skland_core import ensure_auth, load_creds, player_info


def build_tenure(profile, today=None):
    status = profile.get("status") or {}
    ts = int(status.get("registerTs") or 0)
    if not ts:
        return None
    now = today or datetime.now()
    reg = datetime.fromtimestamp(ts)
    return {
        "register_date": reg.strftime("%Y-%m-%d"),
        "days": max(1, (now.date() - reg.date()).days + 1),
    }


def fetch_tenure(creds=None):
    """只读取 status.registerTs；失败时返回 None，不影响抽卡报告。"""
    try:
        creds = creds or load_creds()
        creds = ensure_auth(creds, uid=creds.get("uid"))
        profile = player_info(creds["cred"], creds["cred_token"], creds["uid"])
        return build_tenure(profile)
    except Exception:
        return None
