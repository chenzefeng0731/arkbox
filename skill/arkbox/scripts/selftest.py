#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ArkBox P0 自测：不联网、不读凭证、不碰真实档案。

覆盖：
- 99 抽硬保底模型与 95.3% 口径
- 限定/联动/标准池型判定（单 UP 不再推断成限定）
- 294/10/23.4/29.4/60/41/17/2 口径
- 双金还债称号、UP 7/10、十连双金、重复六星
- UID 默认遮挡与三种隐私模式
- 三形态不泄露完整 UID
"""

import os
import sys
import re
import tempfile
import unittest

from ark_odds import expected_gap, gap_report, six_star_cdf
from ark_pools import PoolUpIndex, parse_pool_table
from ark_report import build_report, verify_report
from ark_archive import coverage_report
from ark_domains import build_pool_stats, apply_pool_meta
from ark_gacha import analyze_records, render_html, render_markdown, _load_records_file
from ark_site import build_site
from ark_profile import build_tenure
from skland_core import _qr_render, mask_uid
from ark_poster import render_poster

# Windows 终端默认编码（cp1252/GBK）无法输出 ⚠/✓ 等符号：统一强制 UTF-8 输出
for _stdio in (sys.stdout, sys.stderr):
    try:
        _stdio.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


TEST_UID = "123456789"


def _pool_table():
    return {
        "LIMITED_TEST": {
            "six_up": ["char_a", "char_c"],
            "limited": True,
            "pool_type": "limited",
            "pool_type_label": "限定",
            "rate_up_label": "限定寻访",
        },
        "LINKAGE_TEST": {
            "six_up": ["char_e"],
            "limited": False,
            "pool_type": "linkage",
            "pool_type_label": "联动",
            "rate_up_label": "联动寻访",
        },
        "SINGLE_TEST": {
            "six_up": ["char_g"],
            "limited": False,
            "pool_type": "standard",
            "pool_type_label": "标准",
            "rate_up_label": "标准寻访",
        },
    }


def _fake_index():
    idx = PoolUpIndex.__new__(PoolUpIndex)
    idx.table = _pool_table()
    return idx


def _records():
    """构造 294 条合成记录，复现真实档案的间隔结构，但不含真实昵称/UID。"""
    recs = []
    base = 1785556944842

    def add(pool_id, pool_name, i, ts, six=None, pos=0):
        if six:
            cid, name = six
            rarity = 5
            is_new = False
        else:
            cid, name, rarity, is_new = "char_123_fang", "芬", 3, False
        recs.append({
            "poolId": pool_id, "poolName": pool_name,
            "charId": cid, "charName": name, "rarity": rarity,
            "isNew": is_new, "gachaTs": str(ts), "pos": pos,
        })

    six_a = {
        18: ("char_a", "珊比"), 58: ("char_b", "引星棘刺"),
        75: ("char_a", "珊比"), 93: ("char_c", "予愿安洁莉娜"),
        151: ("char_d", "Mon3tr"), 160: ("char_a", "珊比"),
    }
    for i in range(1, 202):
        add("LIMITED_TEST", "车辙与风的归所", i, base + i * 1000,
            six=six_a.get(i))
    base_b = base + 3_000_000
    six_b = {60: ("char_e", "结城理"), 66: ("char_f", "谬因")}
    for i in range(1, 84):
        add("LINKAGE_TEST", "石白深蓝之夜", i, base_b + i * 1000,
            six=six_b.get(i))
    # 海渊：同一时间戳的十连，第 1、8 抽为六星（两种同角色）
    base_c = base + 6_000_000
    for pos in range(10):
        six = ("char_g", "克莱门莎") if pos in (0, 7) else None
        add("SINGLE_TEST", "海渊巡游", pos + 1, base_c, six=six, pos=pos)
    return recs


class P0Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = _records()
        idx = _fake_index()
        cls.stats, _ = analyze_records(cls.records, idx)
        cls.pool_data = build_pool_stats(cls.records, idx)
        apply_pool_meta(cls.stats, cls.pool_data)
        cls.coverage = coverage_report(cls.records)
        cls.report = build_report(
            cls.stats, "测试博士", cls.coverage,
            domain=cls.pool_data,
        )

    def test_model(self):
        self.assertAlmostEqual(expected_gap(), 34.5946, places=3)
        self.assertAlmostEqual(six_star_cdf(99), 1.0, places=9)
        self.assertLess(six_star_cdf(98), 1.0)
        gr = gap_report([18, 40, 17, 18, 58, 9, 60, 6, 1, 7])
        self.assertEqual(gr["avg_gap"], 23.4)
        self.assertEqual(gr["sum"], 234)
        self.assertAlmostEqual(gr["better_than"], 95.3, places=1)

    def test_pool_types_and_up(self):
        types = {p["pool"]: p["pool_type_label"] for p in self.stats}
        self.assertEqual(types["车辙与风的归所"], "限定")
        self.assertEqual(types["石白深蓝之夜"], "联动")
        self.assertEqual(types["海渊巡游"], "标准")
        up = {p["pool"]: p["up_verdict"] for p in self.stats}
        self.assertEqual(up["车辙与风的归所"]["hit_count"], 4)
        self.assertEqual(up["车辙与风的归所"]["total"], 6)
        self.assertEqual(up["石白深蓝之夜"]["hit_count"], 1)
        self.assertEqual(up["海渊巡游"]["hit_count"], 2)
        self.assertEqual(up["石白深蓝之夜"]["limited"], False)

    def test_parse_pool_table_single_up_not_limited(self):
        raw = {"gachaPoolClient": [
            {"gachaPoolId": "LINKAGE_X", "gachaPoolDetail": {"detailInfo": {
                "limitedChar": None,
                "upCharInfo": {"perCharList": [
                    {"rarityRank": 5, "charIdList": ["char_x"]}
                ]},
                "gachaObjList": [
                    {"gachaObject": "RATE_UP_6", "param": "联动寻访"}
                ],
            }}},
            {"gachaPoolId": "LIMITED_X", "gachaPoolDetail": {"detailInfo": {
                "limitedChar": ["char_y"],
                "upCharInfo": {"perCharList": [
                    {"rarityRank": 5, "charIdList": ["char_y"]}
                ]},
                "gachaObjList": [
                    {"gachaObject": "RATE_UP_6", "param": "限定寻访"}
                ],
            }}},
        ]}
        table = parse_pool_table(raw)
        self.assertFalse(table["LINKAGE_X"]["limited"])
        self.assertEqual(table["LINKAGE_X"]["pool_type"], "linkage")
        self.assertTrue(table["LIMITED_X"]["limited"])
        self.assertEqual(table["LIMITED_X"]["pool_type"], "limited")

    def test_report_metrics_and_title(self):
        m = self.report["metrics"]
        luck = self.report["luck"]
        self.assertEqual(self.report["totals"]["pulls"], 294)
        self.assertEqual(self.report["totals"]["six"], 10)
        self.assertEqual(m["gap_count"], 10)
        self.assertEqual(m["gap_sum"], 234)
        self.assertEqual(m["mean_gap"], 23.4)
        self.assertEqual(luck["better_than"], 95.3)
        self.assertEqual(m["overall_efficiency"], 29.4)
        self.assertEqual(m["current_pity_total"], 60)
        self.assertEqual(m["max_gap"], 60)
        self.assertEqual(m["best_gap"], 1)
        self.assertTrue(m["best_gap_first"])
        self.assertTrue(m["max_gap_first"])
        self.assertFalse(m["cross_pool_applied"])
        self.assertEqual(len(self.report["pool_stats"]), 3)
        self.assertEqual(m["up_hits"], 7)
        self.assertEqual(m["up_total"], 10)
        self.assertEqual(self.report["title"]["label"], "双金还债")
        self.assertIn("海渊巡游", self.report["title"]["caption"])
        self.assertEqual(self.report["pools"]["other_line"],
                         "重点 2 / 共 3 池 · 另有 1 池 10 抽 2 六星（海渊巡游，未展开）")
        self.assertEqual(self.report["verification"], [])
        self.assertEqual(verify_report(self.report), [])

    def test_no_cross_pool_merge(self):
        """两个标准池首尾相接，间隔和垫抽都不能合并。"""
        idx = _fake_index()
        idx.table = dict(idx.table)
        for pid, name in (("STANDARD_A", "标准甲"), ("STANDARD_B", "标准乙")):
            idx.table[pid] = {
                "six_up": ["char_a"], "limited": False,
                "pool_type": "standard", "pool_type_label": "标准",
                "rate_up_label": "标准寻访",
            }
        recs = []
        base = 1785556944842

        def add(pid, pname, i, six=False):
            recs.append({
                "poolId": pid, "poolName": pname,
                "charId": "char_a" if six else "char_123_fang",
                "charName": "珊比" if six else "芬",
                "rarity": 5 if six else 3, "isNew": False,
                "gachaTs": str(base + i * 1000), "pos": i,
            })

        for i in range(1, 11):
            add("STANDARD_A", "标准甲", i, six=(i == 5))
        for i in range(1, 11):
            add("STANDARD_B", "标准乙", i, six=(i == 3))

        stats, _ = analyze_records(recs, idx)
        pool_data = build_pool_stats(recs, idx)
        apply_pool_meta(stats, pool_data)
        self.assertEqual(pool_data["all_gaps"], [5, 3])
        self.assertNotIn(8, pool_data["all_gaps"])  # 没有把两池首尾拼成 8
        pity = {x["pool"]: x["current"] for x in pool_data["current_by_pool"]}
        self.assertEqual(pity, {"标准甲": 5, "标准乙": 7})
        report = build_report(stats, "测试博士",
                              coverage_report(recs), domain=pool_data)
        self.assertFalse(report["metrics"]["cross_pool_applied"])
        self.assertEqual(report["metrics"]["mean_gap"], 4.0)
        self.assertEqual(report["verification"], [])

    def test_p1p2_model(self):
        labels = [x["label"] for x in self.report["title_candidates"]]
        self.assertEqual(labels[0], "双金还债")
        self.assertIn("三顾茅庐", labels)
        self.assertIn("保底人", labels)
        self.assertIn("小欧", labels)
        types = {t["label"]: t for t in self.report["pool_types"]}
        self.assertEqual(types["限定"]["pulls"], 201)
        self.assertEqual(types["联动"]["mean_gap"], 33.0)
        self.assertEqual(sum(t["pulls"] for t in self.report["pool_types"]), 294)
        sparks = {p["pool"]: p["spark"] for p in self.report["pool_stats"] if p["spark"]}
        self.assertEqual(sparks["车辙与风的归所"]["remaining"], 99)
        self.assertEqual(sparks["石白深蓝之夜"]["remaining"], 37)
        self.assertTrue(any("标准" in g["title"] for g in self.report["data_gaps"]))
        self.assertIn("双金还债", self.report["share"]["text"])
        self.assertNotIn(TEST_UID, self.report["share"]["text"])
        self.assertIn("#明日方舟", self.report["share"]["text"])
        self.assertEqual(len(self.report["share"]["variants"]), 3)
        cmp = self.report["period_compare"]
        self.assertEqual(cmp["latest"]["pool"], "海渊巡游")
        self.assertEqual(cmp["latest"]["mean_gap"], 4.0)
        self.assertEqual(cmp["earlier"]["pools"], 2)

    def test_offline_loader(self):
        with tempfile.TemporaryDirectory() as td:
            p1 = os.path.join(td, "records.jsonl")
            with open(p1, "w", encoding="utf-8") as f:
                for r in self.records[:5]:
                    f.write(__import__("json").dumps(r, ensure_ascii=False) + "\n")
            self.assertEqual(len(_load_records_file(p1)), 5)
            p2 = os.path.join(td, "records.json")
            with open(p2, "w", encoding="utf-8") as f:
                __import__("json").dump(self.records[:3], f, ensure_ascii=False)
            self.assertEqual(len(_load_records_file(p2)), 3)

    def test_zero_six_and_current_pity_title(self):
        idx = _fake_index()
        idx.table = dict(idx.table)
        idx.table["ZERO_TEST"] = {
            "six_up": [], "limited": False, "pool_type": "standard",
            "pool_type_label": "标准", "rate_up_label": "标准寻访",
        }
        base = 1790000000000
        recs = [{
            "poolId": "ZERO_TEST", "poolName": "零金测试",
            "charId": "char_123_fang", "charName": "芬", "rarity": 3,
            "isNew": False, "gachaTs": str(base + i * 1000), "pos": i,
        } for i in range(1, 11)]
        stats, _ = analyze_records(recs, idx)
        pd = build_pool_stats(recs, idx)
        apply_pool_meta(stats, pd)
        report = build_report(stats, "零金博士",
                              coverage_report(recs), domain=pd)
        self.assertEqual(report["title"]["label"], "零金")
        self.assertEqual(report["verification"], [])
        with tempfile.TemporaryDirectory() as td:
            html_path = os.path.join(td, "zero.html")
            poster_path = os.path.join(td, "zero.html")
            render_html(report, stats, html_path)
            render_poster(report, poster_path)
            for path in (html_path, poster_path):
                with open(path, encoding="utf-8") as f:
                    text = f.read()
                self.assertNotIn("None%", text)
                self.assertNotIn("整体 None", text)
                self.assertNotIn("0/0", text)
            render_poster(report, os.path.join(td, "zero_a.html"), theme="A")

        # 当前垫 98、最长间隔 1：不能把“保底人”写成“最长 1 抽才出”
        idx.table["PITY_TEST"] = {
            "six_up": ["char_a"], "limited": False, "pool_type": "standard",
            "pool_type_label": "标准", "rate_up_label": "标准寻访",
        }
        recs = []
        for i in range(1, 100):
            six = i == 1
            recs.append({
                "poolId": "PITY_TEST", "poolName": "长垫测试",
                "charId": "char_a" if six else "char_123_fang",
                "charName": "珊比" if six else "芬",
                "rarity": 5 if six else 3, "isNew": False,
                "gachaTs": str(base + i * 1000), "pos": i,
            })
        stats, _ = analyze_records(recs, idx)
        pd = build_pool_stats(recs, idx)
        apply_pool_meta(stats, pd)
        report = build_report(stats, "测试博士",
                              coverage_report(recs), domain=pd)
        self.assertEqual(report["title"]["label"], "保底人")
        self.assertIn("当前垫 98", report["title"]["caption"])
        self.assertNotIn("最长 1", report["title"]["caption"])
        self.assertEqual(report["verification"], [])

    def test_tenure_and_no_assist_module(self):
        profile = {"status": {"registerTs": 1720920881}}
        tenure = build_tenure(profile)
        self.assertEqual(tenure["register_date"], "2024-07-14")
        self.assertGreater(tenure["days"], 700)
        report = build_report(self.stats, "测试博士",
                              self.coverage, domain=self.pool_data, tenure=tenure)
        self.assertEqual(report["verification"], [])
        self.assertNotIn("namecard", report)
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "tenure.html")
            render_html(report, self.stats, out)
            with open(out, encoding="utf-8") as f:
                page = f.read()
            self.assertIn("入职 2024-07-14", page)
            self.assertNotIn("当前助战", page)
            self.assertNotIn("namecard", page)

    def test_site_bundle_privacy(self):
        with tempfile.TemporaryDirectory() as td:
            site = build_site(self.stats, self.pool_data, self.coverage, td)
            with open(os.path.join(td, "dist", "index.html"), encoding="utf-8") as f:
                page = f.read()
            self.assertIn('name="robots" content="noindex,nofollow,noarchive"', page)
            self.assertIn("公开分享页", page)
            self.assertIn("博士", page)
            self.assertNotIn("测试博士", page)
            self.assertIsNone(re.search(r"UID[^\n<]{0,4}\d{3,}", page))
            with open(os.path.join(td, "dist", "robots.txt"), encoding="utf-8") as f:
                self.assertIn("Disallow: /", f.read())
            self.assertTrue(os.path.exists(os.path.join(td, ".arkbox-site.json")))
            self.assertTrue(os.path.exists(site["index"]))

    def test_qr_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            path = _qr_render("test-scan-id", os.path.join(td, "qr.png"))
            self.assertTrue(os.path.exists(path))
            self.assertTrue(path.endswith((".png", ".html")))
            if path.endswith(".html"):
                with open(path, encoding="utf-8") as f:
                    self.assertIn("scan_login", f.read())

    def test_privacy(self):
        # 本地诊断用遮挡展示；分享产物不出现 UID 字样
        self.assertEqual(mask_uid(TEST_UID), "123****89")
        self.assertNotIn("uid", self.report["doctor"])
        self.assertFalse(self.report["privacy"]["shows_uid"])

    def test_three_outputs_do_not_leak_uid(self):
        # “UID 后紧跟数字”才算展示；口径说明文字允许出现 UID 一词
        uid_shown = re.compile(r"UID[^\n<]{0,4}\d{3,}")
        with tempfile.TemporaryDirectory() as td:
            poster = os.path.join(td, "poster.html")
            report_html = os.path.join(td, "report.html")
            render_poster(self.report, poster)
            render_html(self.report, self.stats, report_html)
            for path in (poster, report_html):
                with open(path, encoding="utf-8") as f:
                    text = f.read()
                self.assertNotIn(TEST_UID, text)
                self.assertIsNone(uid_shown.search(text), uid_shown.search(text))
                self.assertIn("测试博士", text)
            md = render_markdown(self.report, self.stats, detail=True, with_audit=True)
            self.assertNotIn(TEST_UID, md)
            self.assertIsNone(uid_shown.search(md))
            self.assertIn("双金还债", md)
            self.assertIn("95.3", md)
            self.assertIn("按池独立", md)
            self.assertIn("不跨池合并", md)
            self.assertIn("29.4", md)
            self.assertIn("联动", md)
            self.assertIn("称号候选", md)
            self.assertIn("兑换井", md)
            with open(report_html, encoding="utf-8") as f:
                page = f.read()
            self.assertIn("title-chip", page)
            self.assertIn("复制文案", page)
            self.assertIn("按池独立", page)
            self.assertIn("分享文案", page)


if __name__ == "__main__":
    unittest.main(verbosity=2)
