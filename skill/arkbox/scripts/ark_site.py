#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成可发布的 ArkBox 公开站点（静态目录）。

产出：
  <site_dir>/dist/index.html   公开报告页（昵称=博士，UID 隐藏，noindex）
  <site_dir>/dist/robots.txt   禁止抓取
  <site_dir>/.arkbox-site.json 本工具自己的发布元数据（不是 Qoder 描述文件）

Qoder Sites 的 .qoder.site 描述文件由 prepare_site 生成，禁止手写。
后续更新复用 .arkbox-site.json 里的 projectId / siteId / site_url。
"""

import json
import os
import uuid
from datetime import datetime

from ark_report import build_report, verify_report
from ark_gacha import render_html


DEFAULT_DISPLAY_NAME = "ArkBox 寻访档案"


def _load_meta(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def build_site(stats, pool_data, coverage, site_dir, generated=None, tenure=None, chars=None,
               profile=None):
    """把同一份统计渲染成公开站点，不复制海报/截图/Markdown。"""
    site_dir = os.path.abspath(os.path.expanduser(site_dir))
    dist = os.path.join(site_dir, "dist")
    os.makedirs(dist, exist_ok=True)
    site_report = build_report(
        stats, "博士", coverage, hide_nick=False,
        seed_date=generated, domain=pool_data, tenure=tenure,
    )
    errors = verify_report(site_report)
    if errors:
        raise ValueError("站点报告校验失败：" + "；".join(errors))
    index = os.path.join(dist, "index.html")
    render_html(site_report, stats, index, site_mode=True, chars=chars, profile=profile)
    with open(os.path.join(dist, "robots.txt"), "w", encoding="utf-8") as f:
        f.write("User-agent: *\nDisallow: /\n")

    meta_path = os.path.join(site_dir, ".arkbox-site.json")
    old = _load_meta(meta_path)
    meta = {
        "tool": "arkbox",
        "display_name": old.get("display_name") or DEFAULT_DISPLAY_NAME,
        "site_dir": site_dir,
        "web_directory": "dist",
        "generated": generated or datetime.now().strftime("%Y.%m.%d"),
        "records": sum(p.get("total", 0) for p in stats),
        "pools": len(stats),
        "privacy": {"nick": "博士", "shows_uid": False, "noindex": True},
        "tenure": tenure,
        # 以下字段由第一次 prepare/publish 后填写，供后续复用同一站点
        "project_id": old.get("project_id"),
        "site_id": old.get("site_id"),
        "site_url": old.get("site_url"),
        "access": old.get("access") or "public",
        "publish_note": old.get("publish_note") or "首次发布后写入 projectId/siteId/URL；后续更新复用同一 projectId。",
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # 给 Qoder Agent 的精确发布请求；项目 ID 已知时复用同一站点。
    publish = {
        "operation": "prepare_site",
        "state": "pending",
        "published": False,
        "actionId": str(uuid.uuid4()),
        "projectRoot": site_dir,
        "webDirectory": "dist",
        "spa": False,
        "databaseAccess": "none",
        "projectId": meta.get("project_id"),
        "createNewSite": not bool(meta.get("project_id")),
        "afterPrepare": "get_publish_status -> publish_site(actionId) -> get_publish_status",
        "privacy": "public site uses 博士 nickname; no UID anywhere; noindex; poster is a separate file",
    }
    if not meta.get("project_id"):
        publish["displayName"] = meta.get("display_name") or DEFAULT_DISPLAY_NAME
        publish["slug"] = "arkbox-archive"
    publish_path = os.path.join(site_dir, ".arkbox-publish.json")
    with open(publish_path, "w", encoding="utf-8") as f:
        json.dump(publish, f, ensure_ascii=False, indent=2)
    return {
        "site_dir": site_dir,
        "index": index,
        "meta_path": meta_path,
        "publish_path": publish_path,
        "publish": publish,
        "meta": meta,
        "report": site_report,
    }
