#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ArkBox 全能档案页：一个自包含 HTML，四个页签（寻访分析 / 干员筛选 / 泰拉图鉴 / 分享）。

视觉：与寻访报告同一套"档案纸"语言（纸白 + 黑斜切 + 蓝信号 + 金进度）。
数据：全部在生成期算死并内嵌 JSON；头像走公开 CDN（加载失败自动换镜像）。
降级：无干员数据（离线 --records / 未同步）时退回 v0.7 单页报告，老观感不变。
隐私：不落 UID；site_mode 昵称显示"博士"。
"""

import html
import json
import math
import os
from datetime import datetime

from ark_report_html import CSS as REPORT_CSS, render_body, render_html as render_single
from ark_meta import load_meta
from ark_terra import build_terra, bucket_of

AVATAR_URL = ("https://raw.githubusercontent.com/yuanyan3060/ArknightsGameResource/"
              "main/avatar/{cid}.png")

TAB_GACHA, TAB_BOX, TAB_TERRA, TAB_SHARE = "gacha", "box", "terra", "share"


def _h(value):
    return html.escape(str(value if value is not None else ""))


# ── 壳样式：页签导航 + 各 tab 组件（与报告 CSS 同 token） ─────────────

SHELL_CSS = """
.ab-nav{position:sticky;top:0;z-index:50;background:rgba(244,244,241,.96);backdrop-filter:blur(4px);
  border-bottom:1.5px solid var(--ink);display:flex;align-items:center;gap:14px;
  padding:0 16px;height:46px;overflow-x:auto;scrollbar-width:none}
.ab-nav::-webkit-scrollbar{display:none}
.ab-brand{font:800 11px 'SF Mono',Menlo,monospace;letter-spacing:1.5px;white-space:nowrap}
.ab-brand b{color:var(--blue)}
.ab-tabs{display:flex;gap:2px;flex:1;min-width:0}
.ab-tab{font:800 13px -apple-system,'PingFang SC';padding:5px 12px 7px;border:0;background:none;
  color:var(--dim);cursor:pointer;white-space:nowrap;box-shadow:inset 0 -2.5px 0 transparent}
.ab-tab:hover{color:var(--ink)}
.ab-tab.on{color:var(--ink);box-shadow:inset 0 -2.5px 0 var(--blue)}
.ab-meta{font:600 9px 'SF Mono',Menlo,monospace;color:var(--dim2);white-space:nowrap}
.ab-meta .live{color:var(--blue)}
/* 窄屏：品牌与日期会挤到页签上，收掉日期、压缩页签内边距 */
@media(max-width:560px){
  .ab-meta{display:none}
  .ab-brand{font-size:10px;letter-spacing:1px}
  .ab-nav{gap:8px;padding:0 10px}
  .ab-tab{font-size:12px;padding:5px 8px 7px}
}
.ab-page{display:none}
.ab-page.on{display:block}
.ab-page>.wrap{max-width:960px}
"""

TERRA_CSS = """
.tc-head{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:12px}
.tc-head>div{flex:1;min-width:0}
.tc-head h2{font-size:24px;font-weight:900}
.tc-head .sub{font:600 11px 'SF Mono',Menlo,monospace;color:var(--dim)}
.tc-card{background:var(--card);border:1px solid var(--line);position:relative}
.tc-card::before{content:"";position:absolute;top:-1px;left:-1px;width:12px;height:12px;
  border-top:2px solid var(--ink);border-left:2px solid var(--ink)}
.tc-scroll{overflow-x:auto}
#tc-map{display:block;width:100%;min-width:860px;height:auto}
.tc-legend{display:flex;gap:16px;flex-wrap:wrap;align-items:center;padding:8px 12px;border-top:1px solid var(--line);
  font:600 10px 'SF Mono',Menlo,monospace;color:var(--dim)}
.tc-legend .sw{display:inline-block;width:10px;height:10px;margin-right:5px;vertical-align:-1px}
.sw-hx-o{background:#C9A25E}
.sw-hx-f{background:#B8860B;box-shadow:0 0 0 1.5px rgba(184,134,11,.4)}
.sw-hx-m{background:#fff;border:1px dashed #9A948A}
.sw-hx-e{background:transparent;border:1px dashed #B3AEA2}
#tc-map text{user-select:none}
.tcl line{stroke:#B3AEA2;stroke-width:1;stroke-dasharray:1 3}
.tcl .plate{fill:rgba(255,255,255,.94);stroke:rgba(21,23,24,.3);stroke-width:.7}
.tcl:hover .plate{stroke:var(--blue)}
.tcl.sel .plate{stroke:var(--blue);stroke-width:1.6}
.tcl .rname{fill:var(--ink);font:800 12px -apple-system,'PingFang SC'}
.tcl .rcount{font:700 10px 'SF Mono',Menlo;fill:var(--dim)}
.tcl.is-full .rcount{fill:var(--gold);font-weight:800}
.tcl.is-empty .rname,.tcl.is-empty .rcount{fill:rgba(21,23,24,.38)}
.tcl .rbar-bg{fill:rgba(21,23,24,.1)}
.tcl .rbar{fill:var(--gold)}
.tcl .accent{fill:var(--blue)}
.tc-region{cursor:pointer;outline:none}
.tc-region:hover .hx{filter:brightness(.92)}
.tc-region.sel .hx{stroke:var(--ink);stroke-width:1.2}
.hx{stroke-width:.8}
.hx-o{fill:#C9A25E;stroke:#8F6E2F}
.hx-f{fill:#B8860B;stroke:#6E520A;stroke-width:1.1}
.hx-m{fill:rgba(255,255,255,.85);stroke:#9A948A;stroke-dasharray:2.2 2}
.tc-region.sp .hx-o{fill:#8FBDD3;stroke:#3E7EA3}
.tc-region.sp .hx-f{fill:#0098DC;stroke:#006FA1}
.landmass{fill:#E8E4DA;stroke:#A9A396;stroke-width:1.6}
.landshadow{fill:#D8D4C8}
.unch-cn{font:600 18px 'Songti SC','Noto Serif SC',serif;fill:#B3AEA2;letter-spacing:12px}
.unch-en{font:600 8px 'SF Mono',Menlo;fill:#C2BDB0;letter-spacing:4px}
.sea-tag{font:600 9px 'SF Mono',Menlo;fill:#C2BDB0;letter-spacing:5px}
.north{font:700 10px 'SF Mono',Menlo;fill:rgba(21,23,24,.4)}
.empty-ring{fill:none;stroke:#B3AEA2;stroke-width:1;stroke-dasharray:3 4}
.ship-ring{fill:rgba(0,152,220,.03);stroke:#8FBDD3;stroke-width:1;stroke-dasharray:5 5}
.collab-ring{fill:rgba(21,23,24,.02);stroke:#B3AEA2;stroke-width:1;stroke-dasharray:5 5}
.ship-tag{font:600 8px 'SF Mono',Menlo;fill:#8FBDD3;letter-spacing:2px}
.tc-panel{margin-top:10px;background:var(--card);border:1px solid var(--line);padding:14px 16px}
.tc-p-head{display:flex;justify-content:space-between;align-items:baseline;gap:10px;flex-wrap:wrap}
.tc-p-kicker{font:700 9px 'SF Mono',Menlo;color:var(--blue);letter-spacing:1.5px}
.tc-p-title{font-size:20px;font-weight:900}
.tc-p-title small{font:700 10px 'SF Mono',Menlo;color:var(--dim2);margin-left:8px;letter-spacing:1px}
.tc-back{font:700 10px 'SF Mono',Menlo;color:var(--blue);background:none;border:0;cursor:pointer;padding:0}
.tc-p-body{display:flex;gap:16px;flex-wrap:wrap;margin-top:10px}
.tc-ring{position:relative;width:96px;height:96px;flex:0 0 auto}
.tc-ring svg{width:96px;height:96px}
.tc-ring .pct{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
  font:800 19px 'SF Mono',Menlo;color:var(--gold)}
.tc-ring-bg{fill:none;stroke:rgba(21,23,24,.12);stroke-width:8}
.tc-ring-fg{fill:none;stroke:var(--gold);stroke-width:8;stroke-linecap:round;
  transform:rotate(-90deg);transform-origin:center}
.tc-near{flex:1;min-width:240px}
.tc-near-row{display:flex;justify-content:space-between;gap:8px;padding:4px 0;
  border-bottom:1px solid rgba(21,23,24,.1);font:600 11px 'SF Mono',Menlo}
.tc-near-row:last-child{border-bottom:0}
.tc-near-row .miss{color:var(--red)}
.tc-near-row b{color:var(--ink)}
.tc-chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.tc-chip{font:700 10px 'SF Mono',Menlo;padding:3px 8px;border:1px solid var(--line);
  background:rgba(184,134,11,.07);color:var(--gold);cursor:pointer}
.tc-chip.e{border-style:dashed;background:none;color:var(--dim2)}
.tc-detail{display:flex;gap:14px;flex-wrap:wrap;margin-top:8px}
.tc-gap{margin:10px 0 4px;padding:7px 11px;border:1px solid rgba(184,134,11,.5);
  background:rgba(184,134,11,.07);font:700 12px 'SF Mono',Menlo}
.tc-gap.all{border-color:rgba(0,152,220,.5);background:rgba(0,152,220,.06);color:var(--blue)}
.tc-ops{display:grid;grid-template-columns:repeat(auto-fill,minmax(58px,1fr));gap:7px;margin-top:10px}
.tc-ops .op{width:auto}
.tc-note{font:500 10px 'SF Mono',Menlo;color:var(--dim2);line-height:1.6;margin-top:10px}
/* 总览口径注记：通栏脚注，不吃正文 38em 行长限制 */
.tc-ways{max-width:none;margin-top:14px;padding-top:10px;border-top:1px solid var(--line);font-weight:500;font-size:10px;color:var(--dim2);line-height:1.7}
.tc-ways .k{display:inline-block;margin-right:8px;color:var(--blue);font-weight:700;letter-spacing:1px}
/* 我的名片 + 干员池特征 */
.pf-row{display:grid;grid-template-columns:300px 1fr;gap:16px;margin-top:12px}
.pf-k{font:700 9px 'SF Mono',Menlo;color:var(--blue);letter-spacing:1.5px;margin-bottom:8px}
.pf-card{background:var(--card);border:1px solid var(--line);display:flex;gap:12px;align-items:center;padding:10px}
.pf-card .im{position:relative;width:64px;height:64px;flex:0 0 auto;background:rgba(21,23,24,.05);overflow:hidden}
.pf-card.big .im{width:104px;height:104px}
.pf-card .im img{position:relative;z-index:1;width:100%;height:100%;object-fit:cover}
.pf-card .fb{position:absolute;inset:0;z-index:0;display:flex;align-items:center;justify-content:center;
  font:800 22px 'SF Mono',Menlo;color:var(--dim2)}
.pf-card .meta{display:flex;flex-direction:column;gap:3px;min-width:0}
.pf-card .meta b{font-size:15px;font-weight:800}
.pf-card.big .meta b{font-size:19px}
.pf-card .meta span{font:600 11px 'SF Mono',Menlo;color:var(--dim)}
.pf-list{display:flex;gap:10px;flex-wrap:wrap}
.pf-list .pf-card{flex:1 1 190px}
.ft-row{display:grid;grid-template-columns:264px 1fr;gap:18px;margin-top:12px;align-items:center}
.ft-svg{width:100%;max-width:248px;height:auto;display:block;margin:0 auto}
.ft-callout{background:rgba(184,134,11,.08);border:1px solid rgba(184,134,11,.45);padding:9px 12px;
  font-size:13px;font-weight:700;line-height:1.5}
.ft-callout b{color:var(--gold);font-size:15px}
.ft-bars{margin-top:10px;display:flex;flex-direction:column;gap:6px}
.ft-bar{display:grid;grid-template-columns:56px 1fr 92px;gap:8px;align-items:center;font:600 11px 'SF Mono',Menlo}
.ft-bar .k{color:var(--ink);font-weight:800}
.ft-bar .t{height:8px;background:rgba(21,23,24,.1);display:block}
.ft-bar .t i{display:block;height:8px;background:var(--gold)}
.ft-bar .v{text-align:right;color:var(--dim)}
@media(max-width:760px){.pf-row{grid-template-columns:1fr}.ft-row{grid-template-columns:1fr}}
/* 干员池总览：看板娘 + 六维 + 结论，压成一行 */
.ov-row{display:grid;grid-template-columns:200px 240px 1fr;gap:22px;align-items:center;margin-top:10px}
.ov-mg{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:2px}
.ov-m{background:var(--card);border:1px solid var(--line);padding:9px 12px}
.ov-m .v{font:900 26px 'SF Mono',Menlo;line-height:1.1;color:var(--ink)}
.ov-m .l{font:700 10.5px 'SF Mono',Menlo;color:var(--dim2);margin-top:3px}
.ov-m.gold .v{color:#C9A25E}
.ov-m.gold2 .v{color:var(--gold)}
.ov-m.red .v{color:var(--red)}
.ov-score{display:flex;align-items:baseline;gap:4px}
.ov-score b{font:900 44px 'SF Mono',Menlo;color:var(--ink);line-height:1}
.ov-score span{font:700 12px 'SF Mono',Menlo;color:var(--dim2)}
.ov-title{font:900 22px -apple-system,'PingFang SC';margin-top:4px;letter-spacing:.5px}
.ov-tline{font:600 11px 'SF Mono',Menlo;color:var(--dim2);margin-top:3px}
.ov-tags{display:flex;flex-wrap:wrap;gap:6px;margin-top:9px}
.ov-tag{font:800 11px -apple-system,'PingFang SC';padding:3px 9px;border:1px solid rgba(184,134,11,.5);
  background:rgba(184,134,11,.09);color:var(--gold)}
.ov-k{font:700 9px 'SF Mono',Menlo;color:var(--blue);letter-spacing:1.5px;margin-bottom:6px}
.ov-card{display:flex;gap:10px;align-items:center;background:var(--card);border:1px solid var(--line);padding:8px}
.ov-card .im{position:relative;width:76px;height:76px;flex:0 0 auto;background:rgba(21,23,24,.05);overflow:hidden}
.ov-card .im img{position:relative;z-index:1;width:100%;height:100%;object-fit:cover}
.ov-card .fb{position:absolute;inset:0;z-index:0;display:flex;align-items:center;justify-content:center;
  font:800 22px 'SF Mono',Menlo;color:var(--dim2)}
.ov-card .meta{display:flex;flex-direction:column;gap:2px;min-width:0}
.ov-card .meta b{font-size:15px;font-weight:800}
.ov-card .meta span{font:600 10.5px 'SF Mono',Menlo;color:var(--dim)}
.ov-radar{display:flex;flex-direction:column;align-items:center}
.ov-radar .ft-svg{width:200px;height:200px;max-width:100%}
.ov-dimvals{display:grid;grid-template-columns:1fr 1fr;gap:2px 14px;margin-top:2px;font:700 10.5px 'SF Mono',Menlo;color:var(--dim2)}
.ov-dimvals span{display:flex;justify-content:space-between;gap:6px}
.ov-dimvals em{font-style:normal}
.ov-dimvals b{color:var(--ink);font-weight:800}
.ov-callout{background:rgba(184,134,11,.08);border:1px solid rgba(184,134,11,.45);padding:6px 10px;
  font-size:12.5px;font-weight:700;line-height:1.45}
.ov-callout b{color:var(--gold);font-size:14px}
.ov-bars{display:grid;grid-template-columns:1fr 1fr;gap:5px 16px;margin-top:9px}
.ov-pb{display:grid;grid-template-columns:34px 1fr 24px;gap:7px;align-items:center;
  font:700 10.5px 'SF Mono',Menlo;color:var(--dim)}
.ov-pb .tb{display:block;height:6px;background:rgba(21,23,24,.1)}
.ov-pb .tb i{display:block;height:6px;background:var(--gold)}
.ov-pb em{font-style:normal;color:var(--ink)}
.ov-pb b{text-align:right;font-weight:800;color:var(--ink)}
.ov-foot{margin-top:9px;font:600 10.5px 'SF Mono',Menlo;color:var(--dim2)}
@media(max-width:880px){.ov-row{grid-template-columns:1fr 1fr}.ov-side{grid-column:1/-1}}
/* 右下角悬浮按钮 */
.fab{position:fixed;right:18px;bottom:18px;z-index:80;display:flex;flex-direction:column;gap:8px}
.fab button{width:48px;height:48px;border:1.5px solid var(--ink);background:var(--paper);color:var(--ink);
  font:800 11px -apple-system,'PingFang SC';cursor:pointer;box-shadow:3px 3px 0 rgba(21,23,24,.16);
  display:flex;align-items:center;justify-content:center;flex-direction:column;line-height:1.15;padding:0}
.fab button:hover{background:var(--blue);color:#fff;border-color:var(--blue)}
.fab .ic{font-size:15px;font-weight:900}
/* 分享预览弹层 */
.shm{position:fixed;inset:0;z-index:90;background:rgba(21,23,24,.72);display:none;
  align-items:center;justify-content:center;padding:20px}
.shm.on{display:flex}
.shm-box{background:var(--paper);border:1.5px solid var(--ink);max-height:92vh;display:flex;
  flex-direction:column;box-shadow:8px 8px 0 rgba(0,0,0,.25)}
.shm-head{display:flex;justify-content:space-between;align-items:center;gap:16px;
  padding:8px 14px;border-bottom:1.5px solid var(--ink);font:800 13px -apple-system,'PingFang SC'}
.shm-head button{font:700 11px 'SF Mono',Menlo;background:none;border:0;color:var(--dim);cursor:pointer}
.shm-body{padding:14px;overflow:auto;text-align:center}
.shm-body img{display:block;max-height:66vh;max-width:100%;height:auto;border:1px solid var(--line)}
.shm-foot{padding:0 14px 14px;text-align:center}

"""

BOX_CSS = """
.bx-bar{display:flex;gap:6px;flex-wrap:wrap;align-items:center;padding:10px 12px;background:var(--card);
  border:1px solid var(--line);margin-bottom:10px}
.bx-bar label{font:700 9px 'SF Mono',Menlo;color:var(--dim2);letter-spacing:1px}
.bx-bar select,.bx-bar input{font:700 12px -apple-system,'PingFang SC';padding:4px 7px;border:1px solid var(--line);
  background:rgba(255,255,255,.8);color:var(--ink)}
.bx-bar input[type=text]{width:110px}
.bx-count{margin-left:auto;font:700 11px 'SF Mono',Menlo;color:var(--dim)}
.bx-count b{color:var(--blue)}
.bx-more{margin:14px 0 0;text-align:center;font:600 11px 'SF Mono',Menlo;color:var(--dim2)}
.bx-more span{margin-left:10px}
.bx-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(92px,1fr));gap:9px}
.bx-card{position:relative;background:rgba(255,255,255,.82);border:1px solid var(--line);cursor:pointer}
.bx-card.r6{border:1.5px solid var(--gold);box-shadow:0 1px 6px rgba(184,134,11,.16)}
.bx-card.r5{border-color:rgba(0,152,220,.55)}
.bx-card .im{position:relative;aspect-ratio:1;overflow:hidden;background:rgba(21,23,24,.05)}
.bx-card img{position:absolute;inset:0;z-index:1;width:100%;height:100%;object-fit:cover}
.bx-card .fb{position:absolute;inset:0;z-index:0;display:flex;align-items:center;justify-content:center;
  font:800 26px 'SF Mono',Menlo;color:var(--dim2)}
.bx-card .nm{font:700 11px -apple-system,'PingFang SC';text-align:center;padding:3px 2px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bx-badge{position:absolute;top:3px;right:3px;font:800 9px 'SF Mono',Menlo;padding:1px 4px;background:rgba(21,23,24,.72);color:#fff}
.bx-badge.e2{left:3px;right:auto;background:var(--gold);color:#fff}
.bx-info{position:fixed;z-index:60;display:none;width:240px;background:#fff;border:1.5px solid var(--ink);
  padding:12px;box-shadow:6px 6px 0 rgba(21,23,24,.14)}
.bx-info.show{display:block}
.bx-info b{font-size:16px}
.bx-info .row{display:flex;justify-content:space-between;font:600 11px 'SF Mono',Menlo;
  color:var(--dim);padding:3px 0;border-bottom:1px dashed rgba(21,23,24,.12)}
.bx-info .row:last-child{border-bottom:0}
"""

SHARE_CSS = """
.sh-grid{display:grid;grid-template-columns:1fr;gap:14px}
@media(min-width:860px){.sh-grid{grid-template-columns:340px 1fr}}
.sh-ctrl{background:var(--card);border:1px solid var(--line);padding:14px}
.sh-ctrl h3{font-size:15px;font-weight:900}
.sh-type{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0}
.sh-btn{font:800 12px -apple-system,'PingFang SC';padding:6px 12px;border:1px solid var(--line);
  background:rgba(255,255,255,.7);color:var(--dim);cursor:pointer}
.sh-btn.on{background:var(--ink);color:#fff;border-color:var(--ink)}
.sh-btn.go{background:var(--blue);border-color:var(--blue);color:#fff;font-weight:800}
.sh-ctrl select{width:100%;font:700 13px -apple-system,'PingFang SC';padding:6px 8px;
  border:1px solid var(--line);background:#fff;margin:6px 0 14px}
.sh-hint{font:500 10px 'SF Mono',Menlo;color:var(--dim2);line-height:1.7;margin-top:10px}
.sh-poster-wrap{margin-top:12px}
.sh-poster{display:block;width:100%;max-width:430px;height:auto;border:1.5px solid var(--ink)}
.sh-poster-note{font:500 11px 'SF Mono',Menlo;color:var(--dim2);line-height:1.7;margin-top:8px;max-width:520px}
.sh-out{background:var(--card);border:1px solid var(--line);padding:14px;display:flex;
  flex-direction:column;align-items:center;gap:12px}
#sh-canvas{width:100%;max-width:420px;height:auto;border:1px solid var(--line);background:#fff}
"""

# ── 泰拉地图 SVG（服务端渲染，几何来自 ark_terra） ────────────────────

# 地图自带一份内联样式：分享卡把 SVG 序列化成图片画进 Canvas 时，
# 页面 <style> 不随之带入，没有这段就会整张图退化成纯黑剪影。
# 颜色与 TERRA_CSS 一一对应（此处必须是字面值，图片里的 SVG 解析不了 var()）。
TERRA_SVG_CSS = """<style>
.landmass{fill:#E8E4DA;stroke:#A9A396;stroke-width:1.6}
.landshadow{fill:#D8D4C8}
.unch-cn{font:600 18px 'Songti SC','Noto Serif SC',serif;fill:#B3AEA2;letter-spacing:12px}
.unch-en{font:600 8px 'SF Mono',Menlo;fill:#C2BDB0;letter-spacing:4px}
.sea-tag{font:600 9px 'SF Mono',Menlo;fill:#C2BDB0;letter-spacing:5px}
.north{font:700 10px 'SF Mono',Menlo;fill:rgba(21,23,24,.4)}
.empty-ring{fill:none;stroke:#B3AEA2;stroke-width:1;stroke-dasharray:3 4}
.ship-ring{fill:rgba(0,152,220,.03);stroke:#8FBDD3;stroke-width:1;stroke-dasharray:5 5}
.collab-ring{fill:rgba(21,23,24,.02);stroke:#B3AEA2;stroke-width:1;stroke-dasharray:5 5}
.ship-tag{font:600 8px 'SF Mono',Menlo;fill:#8FBDD3;letter-spacing:2px}
.hx{stroke-width:.8}
.hx-o{fill:#C9A25E;stroke:#8F6E2F}
.hx-f{fill:#B8860B;stroke:#6E520A;stroke-width:1.1}
.hx-m{fill:rgba(255,255,255,.85);stroke:#9A948A;stroke-dasharray:2.2 2}
.tc-region.sp .hx-o{fill:#8FBDD3;stroke:#3E7EA3}
.tc-region.sp .hx-f{fill:#0098DC;stroke:#006FA1}
.tcl .plate{fill:rgba(255,255,255,.94);stroke:rgba(21,23,24,.3);stroke-width:.7}
.tcl .rname{fill:#151718;font:800 12px -apple-system,'PingFang SC'}
.tcl .rcount{font:700 10px 'SF Mono',Menlo;fill:rgba(21,23,24,.64)}
.tcl.is-full .rcount{fill:#B8860B;font-weight:800}
.tcl.is-empty .rname,.tcl.is-empty .rcount{fill:rgba(21,23,24,.38)}
.tcl .rbar-bg{fill:rgba(21,23,24,.1)}
.tcl .rbar{fill:#B8860B}
.tcl .accent{fill:#0098DC}
</style>"""


def _terra_svg(terra):
    sil = "".join(f'<path d="{p}"/>' for p in terra["silhouette"])
    out = []
    out.append('<svg id="tc-map" viewBox="0 0 1280 620" xmlns="http://www.w3.org/2000/svg" '
               'role="img" aria-label="泰拉大陆六星归档图">')
    out.append('<defs><pattern id="tc-hatch" width="7" height="7" patternTransform="rotate(45)" '
               'patternUnits="userSpaceOnUse"><line x1="0" y1="0" x2="0" y2="7" stroke="#151718" '
               'stroke-opacity=".03"/></pattern></defs>')
    out.append(TERRA_SVG_CSS)
    # 海陆剪影（阴影 + 主体），程序化示意
    out.append(f'<g class="landshadow" transform="translate(4,7)">'
               f'<g transform="translate(0,461) scale(0.1,-0.1)">{sil}</g></g>')
    out.append(f'<g class="landmass" transform="translate(0,15) scale(1.28)">'
               f'<g transform="translate(0,461) scale(0.1,-0.1)">{sil}</g></g>')
    out.append('<text class="unch-cn" x="640" y="46" text-anchor="middle">未探明区域</text>')
    out.append('<text class="unch-en" x="640" y="60" text-anchor="middle">UNCHARTED TERRA</text>')
    out.append('<text class="unch-cn" x="640" y="602" text-anchor="middle">未探明区域</text>')
    out.append('<text class="unch-en" x="640" y="616" text-anchor="middle">UNCHARTED TERRA</text>')
    out.append('<text class="north" x="26" y="50">N ↑</text>')
    out.append('<text class="sea-tag" x="1212" y="330" text-anchor="middle" '
               'transform="rotate(90 1212 330)">TERRA · SCHEMATIC</text>')
    # 特殊块
    import math
    for r in terra["regions"]:
        x, y = r["anchor"]
        if r["id"] == "bolivar":
            out.append(f'<circle class="empty-ring" cx="{x}" cy="{y}" r="21"/>')
        elif r["id"] == "rhodes":
            out.append(f'<circle class="ship-ring" cx="{x}" cy="{y}" r="72"/>')
            out.append(f'<text class="ship-tag" x="{x}" y="{y - 84}" text-anchor="middle">MOBILE / 移动中</text>')
        elif r["id"] == "collab":
            out.append(f'<rect class="collab-ring" x="{x - 58}" y="{y - 48}" width="116" height="96" rx="2"/>')
            out.append(f'<text class="ship-tag" x="{x}" y="{y - 62}" text-anchor="middle">NON-TERRA / 非泰拉</text>')
    # 六边形（1 hex = 1 六星）
    for r in terra["regions"]:
        if not r["cells"]:
            continue
        full = r["total6"] > 0 and r["owned6"] == r["total6"]
        sp = " sp" if r["area"] == "special" else ""
        out.append(f'<g class="tc-region{sp}" data-id="{r["id"]}" tabindex="0" role="button" '
                   f'aria-label="{_h(r["name"])} {r["owned6"]}/{r["total6"]}">')
        for i, (q, rr) in enumerate(r["cells"]):
            s = 12.0
            x = s * 1.7320508 * (q + rr / 2)
            y = s * 1.5 * rr
            pts = " ".join(f"{x + s * math.cos(math.radians(30 + 60 * k)):.1f},"
                           f"{y + s * math.sin(math.radians(30 + 60 * k)):.1f}" for k in range(6))
            op = r["ops"][i] if i < len(r["ops"]) else None
            if op and op["owned"]:
                cls = "hx-f" if full else "hx-o"
            else:
                cls = "hx-m"
            attr = ""
            if op:
                attr = (f' data-name="{_h(op["name"])}" data-dn="{_h(op["dn"])}"'
                        f' data-owned="{int(op["owned"])}"')
            out.append(f'<polygon class="hx {cls}" points="{pts}"{attr}/>')
        out.append('</g>')
    # 标签
    out.append('<g class="tcl-root">')
    for lb in terra["labels"]:
        cls = "tcl"
        if lb["full"]:
            cls += " is-full"
        if lb["empty"]:
            cls += " is-empty"
        x, y, w = lb["x"], lb["y"], lb["w"]
        if lb["leader"]:
            lx1, ly1, lx2, ly2 = lb["leader"]
            out.append(f'<line class="tcl" x1="{lx1:.0f}" y1="{ly1:.0f}" x2="{lx2:.0f}" y2="{ly2:.0f}"/>')
        out.append(f'<g class="{cls}" data-id="{lb["id"]}">')
        out.append(f'<rect class="plate" x="{x}" y="{y}" width="{w}" height="34" rx="2"/>')
        out.append(f'<rect class="accent" x="{x + 4}" y="{y + 8}" width="2" height="18"/>')
        nfs = 12 if len(lb["name"]) <= 4 else 11
        out.append(f'<text class="rname" x="{x + 12}" y="{y + 15}" font-size="{nfs}">{_h(lb["name"])}</text>')
        out.append(f'<text class="rcount" x="{x + w - 8}" y="{y + 15}" text-anchor="end">{_h(lb["count"])}</text>')
        out.append(f'<rect class="rbar-bg" x="{x + 12}" y="{y + 24}" width="{w - 20}" height="2"/>')
        if lb["ratio"]:
            out.append(f'<rect class="rbar" x="{x + 12}" y="{y + 24}" width="{(w - 20) * lb["ratio"]:.1f}" height="2"/>')
        out.append('</g>')
    out.append('</g></svg>')
    return "".join(out)



# ── 我的名片：看板娘 + 助战（原「干员筛选」页签的内容，收进泰拉页置顶） ──

PROF_CN = {"SPECIAL": "特种", "SUPPORT": "辅助", "CASTER": "术师", "SNIPER": "狙击",
           "GUARD": "近卫", "DEFENDER": "重装", "MEDIC": "医疗", "VANGUARD": "先锋",
           "PIONEER": "先锋", "TANK": "重装", "WARRIOR": "近卫", "CLOSERANGE": "近卫"}


def prof_cn(value):
    value = value or "?"
    return PROF_CN.get(value, value)


def build_features(chars, terra):
    """干员池特征：六维画像 + 六星职业分布 + 一句可传播的结论。纯本地数据。"""
    from collections import Counter
    n = len(chars) or 1
    six = [c for c in chars if (c.get("rarity") or 0) == 6]
    m = (terra or {}).get("meta") or {}
    all_total = m.get("allTotal") or n
    six_total = m.get("sixTotal") or (len(six) or 1)
    e2 = sum(1 for c in chars if (c.get("evolve") or 0) == 2)
    pot4 = sum(1 for c in chars if (c.get("potential") or 1) >= 4)
    mod = sum(1 for c in chars if c.get("mod"))
    lv90 = sum(1 for c in chars if (c.get("level") or 0) >= 90)

    def pct(a, b):
        return round(a / b * 100, 1) if b else 0.0

    dims = [("广度", pct(n, all_total), "%d/%d" % (n, all_total)),
            ("六星", pct(len(six), six_total), "%d/%d" % (len(six), six_total)),
            ("精二", pct(e2, n), "%d 人" % e2),
            ("潜能", pct(pot4, n), "%d 人" % pot4),
            ("模组", pct(mod, n), "%d 人" % mod),
            ("满级", pct(lv90, n), "%d 人" % lv90)]
    profs = Counter(prof_cn(c.get("profession")) for c in six).most_common()
    top_prof, top_n = (profs[0] if profs else ("—", 0))
    # 职业梗：该职业占六星 ≥25%，且该职业六星里精二 ≥25%，且排第一 →「XX方舟」
    e2_of = Counter(prof_cn(c.get("profession")) for c in six if (c.get("evolve") or 0) == 2)
    top_e2_share = pct(e2_of.get(top_prof, 0), top_n) if top_n else 0.0
    prof_tag = ("%s方舟" % top_prof) if (top_n and pct(top_n, len(six)) >= 25
                                          and top_e2_share >= 25) else ""

    # 评级：六维加权，权重按"投入含金量"给，合计 100
    W = {"六星": 25, "精二": 20, "广度": 15, "模组": 15, "满级": 15, "潜能": 10}
    score = round(sum(W.get(d["name"], 0) * d["pct"] / 100.0 for d in
                      [{"name": a, "pct": b} for a, b, _c in dims]), 1)
    # 称号锚定六星收集率（玩家对收集率有直觉，对加权黑箱没感觉）；
    # 加权分保留给雷达/综合分展示。
    spct = pct(len(six), six_total) if six_total else 0.0
    miss = (six_total - len(six)) if six_total else 0
    if six_total and spct >= 100:
        title, line = "全图鉴博士", "真·满图鉴"
    elif spct >= 80:
        title, line = "泰拉收藏家", f"差 {miss} 名满图鉴"
    elif spct >= 60:
        title, line = "资深图鉴党", f"六星 {len(six)}/{six_total}"
    elif spct >= 40:
        title, line = "在编博士", "骨架搭起来了"
    else:
        title, line = "见习博士", "慢慢来"

    STRONG = {"模组": "模组拉满", "潜能": "潜能大户", "满级": "满级狂魔",
              "六星": "六星收割机", "精二": "精二狂", "广度": "收集癖"}
    EASY = {"模组": "模组随缘", "潜能": "潜能佛系", "满级": "满级随缘",
            "六星": "六星随缘", "精二": "精二随缘", "广度": "随缘抽卡"}
    ds = [{"name": a, "pct": b} for a, b, _c in dims]
    best = max(ds, key=lambda d: d["pct"])
    worst = min(ds, key=lambda d: d["pct"])
    _strong = STRONG.get(best["name"], "")
    _second = prof_tag or EASY.get(worst["name"], "")   # 最多两个，别让标签折成两行
    tags = [_strong, _second]
    return {"dims": [{"name": a, "pct": b, "label": c} for a, b, c in dims],
            "profs": [{"name": a, "n": b, "pct": pct(b, len(six))} for a, b in profs],
            "topProf": top_prof, "topN": top_n, "topShare": pct(top_n, len(six)),
            "score": score, "title": title, "titleLine": line,
            "tags": [t for t in tags if t], "profTag": prof_tag,
            "six": len(six), "n": n}


def _avatar(cid, name=None):
    """头像 + 失败自动换 jsdelivr 镜像（与页面其他渲染器同一套回写逻辑）。"""
    onerr = ("this.dataset.f=1;this.src=this.src.replace('raw.githubusercontent.com',"
             "'cdn.jsdelivr.net/gh').replace('/main/','@main/')")
    return ('<img loading="lazy" src="%s" alt="" onerror="%s">'
            % (AVATAR_URL.format(cid=_h(cid or "")), _h(onerr)))


def _profile_card(op, big=False):
    if not op:
        return ""
    cls = "pf-card big" if big else "pf-card"
    star = "★" * int(op.get("rarity") or 0)
    sub = "%s · %s" % (star or "—", prof_cn(op.get("profession")))
    line2 = "精%s Lv.%s · 潜%s" % (["未","一","二"][min(int(op.get("evolve") or 0), 2)],
                                  op.get("level") or 0, op.get("potential") or 1)
    extra = []
    if op.get("mastery"):
        extra.append("专%d" % int(op["mastery"]))
    if op.get("mod"):
        extra.append("模组")
    if extra:
        line2 += " · " + " ".join(extra)
    return ('<div class="' + cls + '"><div class="im"><span class="fb">'
            + _h((op.get("name") or "?")[:1]) + '</span>' + _avatar(op.get("id"), op.get("name"))
            + '</div><div class="meta"><b>' + _h(op.get("name") or "?") + '</b><span>' + _h(sub)
            + '</span><span>' + _h(line2) + '</span></div></div>')


def _profile_html(profile):
    if not profile:
        return ""
    sec = profile.get("secretary")
    asst = [a for a in (profile.get("assist") or []) if a]
    if not sec and not asst:
        return ""
    cards = "".join(_profile_card(a) for a in asst) or '<p class="note">当前没有设置助战干员。</p>'
    return ('<div class="section"><span class="t">我的名片</span><span class="line"></span></div>'
            '<p class="note">看板娘与助战来自森空岛名片，只读取展示，不参与统计。</p>'
            '<div class="pf-row">'
            '<div class="pf-sec"><div class="pf-k">看板娘 / SECRETARY</div>'
            + (_profile_card(sec, big=True) or '<p class="note">未设置看板娘。</p>')
            + '</div><div class="pf-asst"><div class="pf-k">助战干员 / SUPPORT</div>'
            '<div class="pf-list">' + cards + '</div></div></div>')


def _radar_svg(dims, size=248):
    cx = cy = size / 2.0
    r = size / 2.0 - 52
    n = len(dims) or 1

    def pt(i, ratio):
        a = -math.pi / 2 + 2 * math.pi * i / n
        return cx + r * ratio * math.cos(a), cy + r * ratio * math.sin(a)

    rings = "".join(
        '<polygon points="%s" fill="none" stroke="rgba(21,23,24,.13)" stroke-width="1"/>'
        % " ".join("%.1f,%.1f" % pt(i, k / 4.0) for i in range(n)) for k in (1, 2, 3, 4))
    axes = "".join('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="rgba(21,23,24,.13)"/>'
                   % ((cx, cy) + pt(i, 1)) for i in range(n))
    poly = " ".join("%.1f,%.1f" % pt(i, max(0.04, d["pct"] / 100.0)) for i, d in enumerate(dims))
    labels = ""
    for i, d in enumerate(dims):
        lx, ly = pt(i, 1.30)
        labels += ('<text x="%.1f" y="%.1f" text-anchor="middle" font-size="12" font-weight="800" '
                   'fill="#151718">%s</text>' % (lx, ly, _h(d["name"])))

    return ('<svg viewBox="0 0 %d %d" class="ft-svg" role="img" aria-label="干员池六维画像">%s%s'
            '<polygon points="%s" fill="rgba(184,134,11,.18)" stroke="#B8860B" stroke-width="2"/>'
            '%s</svg>' % (size, size, rings, axes, poly, labels))


def _features_html(feat):
    if not feat or not feat.get("n"):
        return ""
    bars = "".join(
        '<div class="ft-bar"><span class="k">%s</span>'
        '<span class="t"><i style="width:%.1f%%"></i></span>'
        '<span class="v">%d · %.0f%%</span></div>'
        % (_h(x["name"]), max(1.5, x["pct"]), x["n"], x["pct"])
        for x in feat["profs"][:6])
    callout = ('六星里 <b>%s</b> 最多，%d 人（占六星 %.0f%%）'
               % (_h(feat["topProf"]), feat["topN"], feat["topShare"]))
    return ('<div class="section"><span class="t">干员池特征</span><span class="line"></span></div>'
            '<p class="note">六维由持有数据实时算出：广度＝持有/全服，六星＝六星归档/全服，'
            '其余按持有干员比例。职业分布只统计六星。</p>'
            '<div class="ft-row"><div class="ft-radar">' + _radar_svg(feat["dims"]) + '</div>'
            '<div class="ft-side"><div class="ft-callout">' + callout + '</div>'
            '<div class="ft-bars">' + bars + '</div></div></div>')


def _terra_stats_html(terra, profile=None, feat=None):
    """泰拉页首：从左到右 = 评级结果 → 六维 → 4 个指标块（与下方地图同口径呼应）。"""
    m = terra["meta"]
    radar = _radar_svg(feat["dims"], size=176) if feat and feat.get("dims") else ""
    tags = "".join('<span class="ov-tag">%s</span>' % _h(t)
                   for t in ((feat or {}).get("tags") or []))
    score = (feat or {}).get("score", 0)
    title = (feat or {}).get("title", "—")
    tline = (feat or {}).get("titleLine", "")
    metrics = [
        ("六星归档", "%d/%d" % (m["sixOwned"], m["sixTotal"]), "gold"),
        ("地区全档案", "%d/%d" % (m["regionsFull"], m["regionsTotal"]), "gold2"),
        ("地区各差 1 名", "%d" % len(m["near"]), "red"),
        ("全干员持有", "%d/%d" % (m["allOwned"], m["allTotal"]), "ink"),
    ]
    dimvals = "".join('<span><em>%s</em><b>%s%%</b></span>' % (_h(d["name"]), d["pct"])
                      for d in ((feat or {}).get("dims") or []))
    metric_html = "".join(
        '<div class="ov-m %s"><div class="v">%s</div><div class="l">%s</div></div>'
        % (cls, _h(val), _h(lab)) for lab, val, cls in metrics)
    return f'''
<div class="tc-head">
  <div><h2>泰拉图鉴 <b style="color:var(--blue)">/</b> 地区收集档案</h2>
    <div class="sub">每个六边形 = 1 名已实装六星 · 点击地图区域查看档案 · 数据快照 {m["date"] or ""}</div></div>
</div>
<div class="section"><span class="t">干员池档案</span><span class="line"></span></div>
<div class="ov-row">
  <div class="ov-rate">
    <div class="ov-score"><b>{score}</b><span>/100</span></div>
    <div class="ov-title">{title}</div>
    <div class="ov-tline">{tline}</div>
    <div class="ov-tags">{tags}</div>
  </div>
  <div class="ov-radar">{radar}<div class="ov-dimvals">{dimvals}</div></div>
  <div class="ov-metrics"><div class="ov-mg">{metric_html}</div></div>
</div>
<div class="tc-card">
  <div class="tc-scroll">{_terra_svg(terra)}</div>
  <div class="tc-legend">
    <span><i class="sw sw-hx-o"></i>已归档六星</span>
    <span><i class="sw sw-hx-f"></i>地区全档案</span>
    <span><i class="sw sw-hx-m"></i>未归档</span>
    <span><i class="sw sw-hx-e"></i>无六星地区</span>
    <span style="margin-left:auto">海陆轮廓为程序化示意 · 非官方测绘 · 所属口径 nationId</span>
  </div>
</div>
'''


# ── 干员筛选 / 泰拉下半部（共用 JS 渲染网格） ────────────────────────

BOX_BODY = '''
<div class="tc-head">
  <div><h2>干员筛选 <b style="color:var(--blue)">/</b> 我的 Box</h2>
    <div class="sub">点击卡片查看详情 · 头像来自公开镜像 · 数据仅存本地</div></div>
</div>
<div class="bx-bar" id="bx-bar">
  <label>地区</label><select id="bx-region"></select>
  <label>星级</label><select id="bx-rarity">
    <option value="">全部</option><option value="6">6★</option><option value="5">5★</option>
    <option value="4">4★</option><option value="3">3★</option><option value="2">2★</option><option value="1">1★</option></select>
  <label>职业</label><select id="bx-prof"><option value="">全部</option>
    <option>先锋</option><option>近卫</option><option>重装</option><option>狙击</option>
    <option>术师</option><option>医疗</option><option>辅助</option><option>特种</option></select>
  <label>搜索</label><input type="text" id="bx-q" placeholder="名字…">
  <label>只看</label><select id="bx-flag">
    <option value="">无</option><option value="e2">已精二</option><option value="skin">有时装</option><option value="mod">有模组</option></select>
  <label>排序</label><select id="bx-sort">
    <option value="level">等级↓</option><option value="rarity">星级↓</option>
    <option value="potential">潜能↓</option><option value="name">名字</option></select>
  <span class="bx-count" id="bx-count"></span>
</div>
<div class="bx-grid" id="bx-grid"></div>
<div class="bx-info" id="bx-info"></div>
'''

TERRA_OPS_BODY = '''
<div class="section"><span class="t">地区干员档案</span><span class="line"></span></div>
<p class="note">点击上方地图选择地区；这里显示该地区的干员与六星缺口，筛选逻辑与「干员筛选」页一致。</p>
<div class="bx-bar" id="to-bar">
  <label>地区</label><select id="to-region"></select>
  <label>星级</label><select id="to-rarity"><option value="">全部</option><option value="6">6★</option><option value="5">5★</option></select>
  <label>职业</label><select id="to-prof"><option value="">全部</option>
    <option>先锋</option><option>近卫</option><option>重装</option><option>狙击</option>
    <option>术师</option><option>医疗</option><option>辅助</option><option>特种</option></select>
  <label>只看</label><select id="to-flag"><option value="">无</option><option value="missing">六星缺口</option><option value="e2">已精二</option></select>
  <span class="bx-count" id="to-count"></span>
</div>
<div id="to-gap"></div>
<div class="bx-grid" id="to-grid"></div>
'''

SHARE_BODY = '''
<div class="tc-head">
  <div><h2>分享 <b style="color:var(--blue)">/</b> 生成档案卡</h2>
    <div class="sub">寻访海报＝抽卡海报本身（同一套版式）；泰拉图鉴卡在本页 Canvas 现场绘制</div></div>
</div>
<div class="section"><span class="t">寻访海报</span><span class="line"></span></div>
<div class="sh-poster-wrap">__POSTER__</div>
<div class="section"><span class="t">泰拉图鉴卡</span><span class="line"></span></div>
<div class="sh-grid">
  <div class="sh-ctrl">
    <button class="sh-btn go" id="sh-gen" type="button">生成 / 更新图片</button>
    <button class="sh-btn" id="sh-dl" type="button" style="display:none">下载 PNG</button>
    <p class="sh-hint">· 头像来自公开镜像，首次生成需加载<br>· 手机浏览器：生成后长按图片保存<br>· 卡片由本页 Canvas 现场绘制，无网络请求</p>
  </div>
  <div class="sh-out"><canvas id="sh-canvas" width="1080" height="1440"></canvas></div>
</div>
'''



# ── 前端逻辑 ─────────────────────────────────────────────────────────

SHELL_JS = r"""
(function(){
'use strict';
var ARK = window.ARK;
var $ = function(s){ return document.querySelector(s); };
var $$ = function(s){ return Array.prototype.slice.call(document.querySelectorAll(s)); };
function esc(s){ return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];}); }
function av(cid){ return ARK.avBase + cid + '.png'; }
var AVERR = "if(!this.dataset.f){this.dataset.f=1;this.src=this.src.replace('raw.githubusercontent.com','cdn.jsdelivr.net/gh').replace('/main/','@main/');}else{this.style.display='none';this.parentNode.classList.add('noimg')}";

/* ── 页签 ── */
var TABS = ['gacha','terra'];
var shareDrawn = false;
/* 干员网格首批条数与"已展开"状态：必须早于下面 showTab 的首次调用，
   否则 applyFilter 里读到 undefined 会直接抛错、整页空白。 */
var moreState = {}, FIRST_BATCH = { bx: 120, to: 60 };
function showTab(id){
  TABS.forEach(function(t){
    var p = document.getElementById('ab-'+t); if(p) p.classList.toggle('on', t===id);
    var b = document.getElementById('abt-'+t); if(b) b.classList.toggle('on', t===id);
  });
  try{ history.replaceState(null,'','#'+id); }catch(e){}
  window.scrollTo(0,0);
  if(id==='terra'){ ensureTerraInit(); }
}
$$('.ab-tab').forEach(function(b){ b.addEventListener('click', function(){ showTab(b.dataset.tab); }); });
var h = location.hash.replace('#','');
showTab(TABS.indexOf(h)>=0 ? h : 'gacha');

/* ── 干员网格（干员筛选 + 泰拉地区档案共用） ── */
var boxInit=false, terraInit=false;
var OPS = { p2:['未精','精一','精二'] };
function cardHTML(c){
  // 卡面只留"练度徽章"：E2 与潜能。地区原来做成蓝色药丸压在立绘上，
  // 361 张卡叠在一起太吵，已移到详情浮层 + 顶部地区筛选。
  var badges = '';
  if(c.ev===2) badges += '<span class="bx-badge e2">E2</span>';
  if(c.pot>1) badges += '<span class="bx-badge">潜'+c.pot+'</span>';
  return '<div class="bx-card r'+c.rar+'" data-id="'+c.id+'">'
    + '<div class="im"><span class="fb">'+esc((c.nm||'?').slice(0,1))+'</span>'
    + '<img loading="lazy" src="'+av(c.id)+'" alt="" onerror="'+AVERR.replace(/"/g,'&quot;')+'">'
    + badges+'</div>'
    + '<div class="nm">'+esc(c.nm)+'</div></div>';
}
function renderRegionSelect(selId){
  var sel = document.getElementById(selId); if(!sel) return;
  var html = '<option value="">全部地区</option>';
  ARK.terra.regions.forEach(function(r){ if(r.totalAll>0) html += '<option value="'+r.id+'">'+esc(r.name)+' · '+r.ownedAll+'/'+r.totalAll+'</option>'; });
  sel.innerHTML = html;
}
function applyFilter(prefix){
  var reg = (document.getElementById(prefix+'-region')||{}).value||'';
  var rar = (document.getElementById(prefix+'-rarity')||{}).value||'';
  var prof = (document.getElementById(prefix+'-prof')||{}).value||'';
  var flag = (document.getElementById(prefix+'-flag')||{}).value||'';
  var q = ((document.getElementById(prefix+'-q')||{}).value||'').trim();
  var sort = (document.getElementById(prefix+'-sort')||{}).value||'level';
  var list = ARK.chars.filter(function(c){
    if(reg && c.reg!==reg) return false;
    if(rar && String(c.rar)!==rar) return false;
    if(prof && c.pf!==prof) return false;
    if(q && c.nm.indexOf(q)<0) return false;
    if(flag==='e2' && c.ev!==2) return false;
    if(flag==='skin' && !c.sk) return false;
    if(flag==='mod' && !c.md) return false;
    if(flag==='missing' && !(c.rar===6 && !c.ow)) return false;
    return true;
  });
  var key = {level:function(c){return -(c.lv*10+c.rar);}, rarity:function(c){return -(c.rar*100+c.lv);},
             potential:function(c){return -(c.pot*1000+c.lv);}, name:function(c){return c.nm;}}[sort];
  list.sort(function(a,b){ var x=key(a),y=key(b); return x<y?-1:x>y?1:0; });
  var grid = document.getElementById(prefix+'-grid');
  /* 首屏别一次铺几百张卡：先给一批，再"显示全部"（评审 P0-04 / P0-05） */
  var shown = moreState[prefix] ? list.length : Math.min(list.length, FIRST_BATCH[prefix]||120);
  if(list.length===0){ grid.innerHTML='<p class="note">没有匹配的干员。</p>'; }
  else grid.innerHTML = list.slice(0, shown).map(cardHTML).join('');
  var more = document.getElementById(prefix+'-more');
  if(!more){
    more = document.createElement('p'); more.id = prefix+'-more'; more.className='bx-more';
    grid.parentNode.insertBefore(more, grid.nextSibling);
  }
  if(list.length > shown){
    more.innerHTML = '<button type="button" class="sh-btn" id="'+prefix+'-more-btn">显示全部 '
      + list.length + ' 名</button><span>已显示 '+shown+' 名</span>';
    document.getElementById(prefix+'-more-btn').onclick = function(){
      moreState[prefix] = true; applyFilter(prefix);
    };
  } else { more.innerHTML=''; }
  var cnt = document.getElementById(prefix+'-count');
  if(cnt) cnt.innerHTML = '匹配 <b>'+list.length+'</b> / '+ARK.chars.length;
}
['bx-region','bx-rarity','bx-prof','bx-q','bx-flag','bx-sort'].forEach(function(id){
  var el = document.getElementById(id); if(el) el.addEventListener('input', function(){ applyFilter('bx'); });
});
['to-region','to-rarity','to-prof','to-flag'].forEach(function(id){
  var el = document.getElementById(id); if(el) el.addEventListener('input', function(){ applyFilter('to'); });
});
/* 详情浮层 */
var info = document.getElementById('bx-info');
document.addEventListener('click', function(e){
  var card = e.target.closest ? e.target.closest('.bx-card') : null;
  if(!card){ if(info && !e.target.closest('#bx-info')) hideInfo(); return; }
  var c = ARK.charMap[card.dataset.id]; if(!c) return;
  info.innerHTML = '<b>'+esc(c.nm)+'</b> <span style="color:var(--gold)">'+'★'.repeat(c.rar)+'</span>'
    +'<div class="row"><span>地区</span><span>'+esc(ARK.regName[c.reg]||'—')+'</span></div>'
    +'<div class="row"><span>职业</span><span>'+esc(c.pf)+'</span></div>'
    +'<div class="row"><span>等级</span><span>Lv.'+c.lv+' · '+OPS.p2[c.ev]+'</span></div>'
    +'<div class="row"><span>潜能</span><span>'+c.pot+'</span></div>'
    +'<div class="row"><span>技能</span><span>Lv.'+c.msl+(c.mas?' · 专'+c.mas:'')+'</span></div>'
    +'<div class="row"><span>其他</span><span>'+((c.sk?'时装 ':'')+(c.md?'模组':'')||'—')+'</span></div>';
  var x = Math.min(e.clientX+14, window.innerWidth-260), y = Math.min(e.clientY+10, window.innerHeight-230);
  info.style.left=x+'px'; info.style.top=y+'px'; info.classList.add('show');
});
function hideInfo(){ if(info) info.classList.remove('show'); }

/* ── 泰拉图鉴 ── */
function terraById(id){ for(var i=0;i<ARK.terra.regions.length;i++){ if(ARK.terra.regions[i].id===id) return ARK.terra.regions[i]; } return null; }
function ringSVG(pct){ var C=263.9; return '<svg viewBox="0 0 100 100"><circle class="tc-ring-bg" cx="50" cy="50" r="42"/><circle class="tc-ring-fg" cx="50" cy="50" r="42" stroke-dasharray="'+C+'" stroke-dashoffset="'+(C*(1-pct)).toFixed(1)+'"/></svg>'; }
function regionPanel(r){
  var idx = ARK.terra.regions.indexOf(r)+1;
  var miss = r.total6-r.owned6, pct = r.total6? r.owned6/r.total6 : 0;
  var gap = miss===0
    ? '<div class="tc-gap all">◆ 该地区六星已全部归档</div>'
    : '<div class="tc-gap">距全档案还差 <b style="color:var(--red)">'+miss+'</b> 名：'+esc(r.missing6.join('、'))+'</div>';
  var ops = r.ops.map(function(o){
    return '<div class="op'+(o.owned?'':' miss')+'" style="opacity:'+(o.owned?1:.45)+'">'
      +'<div class="avatar"><img loading="lazy" src="'+av(o.id)+'" alt="" onerror="'+AVERR.replace(/"/g,'&quot;')+'">'
      +(o.owned?'':'<span class="badge off">缺</span>')+'</div>'
      +'<div class="nm">'+esc(o.name)+'</div><div class="pull">'+esc(o.dn)+'</div></div>';
  }).join('');
  return '<div class="tc-p-head"><div><div class="tc-p-kicker">REGION '+String(idx).padStart(2,'0')+' / '+ARK.terra.regions.length+' · '+esc(r.en)+'</div>'
    +'<div class="tc-p-title">'+esc(r.name)+'<small>'+esc(r.en)+'</small></div></div>'
    +'<button class="tc-back" id="tc-back">← 返回总览</button></div>'
    +'<div class="tc-detail"><div class="tc-ring">'+ringSVG(pct)+'<div class="pct">'+Math.round(pct*100)+'%</div></div>'
    +'<div style="flex:1;min-width:220px"><div style="font:800 20px \'SF Mono\',Menlo">'+r.owned6+' <span style="color:var(--dim2);font-size:13px">/ '+r.total6+' 六星</span></div>'
    +'<div class="tc-note">全干员 '+r.ownedAll+'/'+r.totalAll+' · 按游戏内所属国家/阵营归档</div>'+gap+'</div></div>'
    +'<div class="tc-ops">'+ops+'</div>';
}
function selectRegion(id){
  var r = terraById(id); if(!r) return;
  $$('.tc-region,.tcl').forEach(function(g){ g.classList.toggle('sel', g.dataset.id===id); });
  var panel = document.getElementById('tc-panel');
  panel.innerHTML = regionPanel(r);
  var back = document.getElementById('tc-back');
  if(back) back.addEventListener('click', function(){ location.hash=''; resetPanel(); });
  var toSel = document.getElementById('to-region');
  if(toSel){ toSel.value = (terraById(id).totalAll>0)? id : ''; applyFilter('to'); renderGap(id); }
}
function renderGap(id){
  var r = terraById(id), el = document.getElementById('to-gap'); if(!el||!r) return;
  var miss = r.total6-r.owned6;
  el.innerHTML = miss===0 ? '' : '<div class="tc-gap" style="margin:0 0 10px">'+esc(r.name)+' 六星缺口 '+miss+' 名：<b style="color:var(--red)">'+esc(r.missing6.join('、'))+'</b></div>';
}
function resetPanel(){
  $$('.tc-region,.tcl').forEach(function(g){ g.classList.remove('sel'); });
  var m = ARK.terra.meta;
  var near = m.near.slice(0,6).map(function(n){
    return '<div class="tc-near-row" data-go="'+n.id+'" style="cursor:pointer"><span><b>'+esc(n.name)+'</b> '+n.owned6+'/'+n.total6+'</span><span class="miss">差 '+esc(n.missing.join('、'))+'</span></div>';
  }).join('') || '<div class="tc-near-row"><span>——</span></div>';
  var chips = m.fullIds.map(function(id){ return '<button class="tc-chip" data-go="'+id+'">'+esc(ARK.regName[id])+' ✓</button>'; }).join('');
  document.getElementById('tc-panel').innerHTML =
    '<div class="tc-p-head"><div><div class="tc-p-kicker">REGION OVERVIEW</div><div class="tc-p-title">全档案进度<small>TERRA CODEX</small></div></div></div>'
    +'<div class="tc-p-body"><div class="tc-ring">'+ringSVG(m.pct/100)+'<div class="pct">'+m.pct+'%</div></div>'
    +'<div class="tc-near"><div class="tc-p-kicker" style="margin-bottom:4px">差 1 名就全档案 · NEARLY DONE</div>'+near
    +'<div class="tc-p-kicker" style="margin:10px 0 0">已全档案地区 · COMPLETED ('+m.fullIds.length+')</div>'
    +'<div class="tc-chips">'+chips+'<span class="tc-chip e">玻利瓦尔 · 暂无六星</span></div></div></div>'
    +'<p class="tc-note tc-ways"><span class="k">口径：</span>以游戏数据 character_table.nationId（所属国家）为主，是"编制"不是"出身地"；nationId 为空的萨卡兹系干员按 groupId=babel（巴别塔）/ teamId=followers（使徒）归入卡兹戴尔，其中临光为卡西米尔干员、归卡西米尔；罗德岛为移动本舰单列；nationId 为空的联动干员归入"非泰拉"，怪物猎人联动干员游戏编码属罗德岛、随本舰归档。</p>';
}
function ensureTerraInit(){
  if(terraInit) return; terraInit=true;
  renderRegionSelect('to-region');
  applyFilter('to'); renderGap('');
  document.getElementById('tc-map').addEventListener('click', function(e){
    var g = e.target.closest('.tc-region') || e.target.closest('.tcl');
    if(g && g.dataset.id) selectRegion(g.dataset.id);
  });
  document.getElementById('tc-map').addEventListener('keydown', function(e){
    if(e.key!=='Enter' && e.key!==' ') return;
    var g = e.target.closest('.tc-region'); if(g && g.dataset.id){ e.preventDefault(); selectRegion(g.dataset.id); }
  });
  /* 悬浮卡 */
  var tip = document.getElementById('tc-tip');
  document.getElementById('tc-map').addEventListener('mousemove', function(e){
    var hx = e.target.closest ? e.target.closest('.hx[data-name]') : null;
    if(!hx){ tip.style.display='none'; return; }
    var rg = hx.closest('.tc-region'); var r = terraById(rg.dataset.id);
    tip.innerHTML = '<b>'+esc(hx.dataset.name)+'</b><span class="'+(hx.dataset.owned==='1'?'ow':'no')+'">'
      +(hx.dataset.owned==='1'?'已归档':'未归档')+'</span><br><i>'+esc(r.name)+' · 6★ · '+esc(hx.dataset.dn||'')+'</i>';
    tip.style.display='block';
    tip.style.left = Math.min(e.clientX+14, window.innerWidth-200)+'px';
    tip.style.top = Math.max(8, e.clientY-64)+'px';
  });
  document.getElementById('tc-map').addEventListener('mouseleave', function(){ tip.style.display='none'; });
  resetPanel();
}
document.addEventListener('click', function(e){
  var go = e.target.closest ? e.target.closest('[data-go]') : null;
  if(go && go.dataset.go){ selectRegion(go.dataset.go); return; }
});

/* ── 右下角悬浮按钮：回到顶部 / 分享导出 ── */
document.getElementById('fab-top').addEventListener('click', function(){
  try{ window.scrollTo({top:0, behavior:'smooth'}); }catch(e){ window.scrollTo(0,0); }
});
function _saveBlob(cv, name){
  try{
    cv.toBlob(function(b){ var a=document.createElement('a');
      a.href=URL.createObjectURL(b); a.download=name; a.click();
      setTimeout(function(){URL.revokeObjectURL(a.href);},2000); }, 'image/png');
  }catch(e){ alert('导出失败，请换个浏览器再试'); }
}
var shm = document.getElementById('share-modal'), shmImg = document.getElementById('shm-img');
function showShare(src, name){
  shmImg.src = src; shmImg.dataset.name = name; shm.classList.add('on');
}
function hideShare(){ shm.classList.remove('on'); }
document.getElementById('shm-close').addEventListener('click', hideShare);
shm.addEventListener('click', function(e){ if(e.target === shm) hideShare(); });
document.getElementById('shm-dl').addEventListener('click', function(){
  if(!shmImg.src) return;
  var a = document.createElement('a');
  a.href = shmImg.src; a.download = shmImg.dataset.name || 'arkbox.png'; a.click();
});
document.getElementById('fab-share').addEventListener('click', function(){
  var page = document.querySelector('.ab-page.on');
  var id = page ? page.id : 'ab-gacha';
  if(id === 'ab-gacha'){
    var img = document.getElementById('share-poster');
    if(!img){ alert('这张海报还没生成：在命令里加 --poster 重跑一次，就能预览并保存。'); return; }
    showShare(img.src, 'arkbox-poster.png');
    return;
  }
  if(!ARK.terra){ alert('当前没有干员数据，泰拉图鉴卡无法生成。'); return; }
  var timg = document.getElementById('share-terra');
  if(timg){ showShare(timg.src, 'arkbox-terra-poster.png'); return; }
  var cv = document.getElementById('sh-canvas'), ctx = cv.getContext('2d');
  drawTerra(ctx, function(){ showShare(cv.toDataURL('image/png'), 'arkbox-terra-card.png'); });
});
function roundRect(x,y,w,h,r,ctx){ ctx.beginPath(); ctx.moveTo(x+r,y); ctx.arcTo(x+w,y,x+w,y+h,r);
  ctx.arcTo(x+w,y+h,x,y+h,r); ctx.arcTo(x,y+h,x,y,r); ctx.arcTo(x,y,x+w,y,r); ctx.closePath(); }
function barcode(ctx,x,y,w,seed){
  var rnd=seed||7, px=x;
  while(px<x+w){ rnd=(rnd*9301+49297)%233280; var bw=1+Math.floor(rnd/233280*3);
    ctx.fillRect(px,y,bw,16); px+=bw+1+Math.floor(rnd/233280*3); }
}
var HAZ_H=10;   /* 与页面 .hazard 的 10px 警示条一致 */
/* 分享卡栅格常量：三张卡共用，别再每处现算坐标（空白/错位反复出现的根因） */
var W=1080, HH=1440, M=64, CW=W-2*M, CARD_R=4, H2=28, BAR_H=6;
function hazard(ctx,y){
  ctx.fillStyle='#151718'; ctx.fillRect(0,y,1080,HAZ_H);
  ctx.fillStyle='#0098DC'; ctx.fillRect(1080*0.46,y,1080*0.08,HAZ_H);
}
function paper(ctx){
  ctx.fillStyle='#F4F4F1'; ctx.fillRect(0,0,1080,1440);
  ctx.strokeStyle='rgba(21,23,24,.05)'; ctx.lineWidth=1;
  for(var x=0;x<=1080;x+=36){ ctx.beginPath(); ctx.moveTo(x,0); ctx.lineTo(x,1440); ctx.stroke(); }
  for(var y=0;y<=1440;y+=36){ ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(1080,y); ctx.stroke(); }
}
function footer(ctx,seed,label){
  hazard(ctx,1332);
  ctx.fillStyle='#151718'; ctx.font='800 22px "SF Mono",Menlo,monospace';
  ctx.fillText('ARKBOX // '+label,M,1392);
  ctx.fillStyle='rgba(21,23,24,.6)'; ctx.font='600 19px "SF Mono",Menlo,monospace';
  ctx.fillText('DOCTOR '+ARK.nick+' · '+ARK.date+' · 非官方玩家工具 · 无 UID',M,1424);
  ctx.fillStyle='#151718'; barcode(ctx,848,1384,168,seed);
}
function ring(ctx,cx,cy,r,pct,lineW){
  ctx.lineWidth=lineW||26; ctx.strokeStyle='rgba(21,23,24,.12)';
  ctx.beginPath(); ctx.arc(cx,cy,r,0,Math.PI*2); ctx.stroke();
  ctx.strokeStyle='#B8860B'; ctx.beginPath();
  ctx.arc(cx,cy,r,-Math.PI/2,-Math.PI/2+Math.PI*2*pct); ctx.stroke();
}

function drawGacha(ctx){
  var g=ARK.gacha;
  paper(ctx); hazard(ctx,0);
  ctx.fillStyle='#0098DC'; ctx.font='800 24px "SF Mono",Menlo,monospace';
  ctx.fillText('ARKBOX // GACHA REPORT',M,120);
  ctx.fillStyle='#151718'; ctx.font='900 92px -apple-system,"PingFang SC",sans-serif';
  ctx.fillText(g.label,M,240);
  ctx.font='700 26px "SF Mono",Menlo,monospace'; ctx.fillStyle='rgba(21,23,24,.55)';
  ctx.fillText('DOCTOR '+ARK.nick+' · 记录截至 '+g.date,M,300);
  /* 四个数横排铺满一行，别再挤在左半边留一大块空 */
  var stats=[['六星均值',g.mean,'抽 / 六星'],['理论位置',g.better+'%','同段数样本'],
             ['六星总数',g.six,'本区间 '+g.pulls+' 抽'],['UP 命中',g.up,'已核验六星']];
  var bw=220,bh=180,by=352,bgap=20;
  stats.forEach(function(s,i){
    var x=M+i*(bw+bgap), y=by;
    ctx.fillStyle='rgba(255,255,255,.78)'; roundRect(x,y,bw,bh,CARD_R,ctx); ctx.fill();
    ctx.strokeStyle='rgba(21,23,24,.25)'; ctx.lineWidth=1.5; ctx.stroke();
    /* 数值一律墨色：金色只留给进度条 / UP 这类语义点缀 */
    ctx.fillStyle='#151718'; ctx.font='900 56px "SF Mono",Menlo,monospace';
    ctx.fillText(String(s[1]),x+20,y+80);
    ctx.font='800 24px -apple-system,"PingFang SC",sans-serif';
    ctx.fillText(s[0],x+20,y+124);
    ctx.fillStyle='rgba(21,23,24,.5)'; ctx.font='600 17px "SF Mono",Menlo,monospace';
    ctx.fillText(s[2],x+20,y+156);
  });
  ctx.fillStyle='#151718'; ctx.font='800 '+H2+'px -apple-system,"PingFang SC",sans-serif';
  ctx.fillText('当前垫抽',M,606);
  g.pity.forEach(function(p,i){
    var x=M,y=626+i*74;
    ctx.fillStyle='rgba(255,255,255,.78)'; roundRect(x,y,CW,58,CARD_R,ctx); ctx.fill();
    ctx.strokeStyle='rgba(21,23,24,.22)'; ctx.stroke();
    ctx.fillStyle='#151718'; ctx.font='800 26px -apple-system,"PingFang SC",sans-serif';
    ctx.fillText(p.label,x+18,y+34);
    ctx.font='900 30px "SF Mono",Menlo,monospace'; ctx.fillStyle='#0098DC';
    ctx.fillText(p.current+' / 99',x+820,y+34);
    /* 条高 3px 缩到聊天窗就看不见，抬到 6px 并加深槽色 */
    ctx.fillStyle='rgba(21,23,24,.18)'; ctx.fillRect(x+18,y+44,CW-36,BAR_H);
    ctx.fillStyle='#0098DC'; ctx.fillRect(x+18,y+44,(CW-36)*Math.min(p.current/99,1),BAR_H);
  });
  /* 最近六星：补「卡池」列 + 日期右对齐，把整行撑满 */
  var rec=g.recent||[];
  ctx.fillStyle='#151718'; ctx.font='800 '+H2+'px -apple-system,"PingFang SC",sans-serif';
  ctx.fillText('最近六星',M,896);
  if(!rec.length){
    ctx.fillStyle='rgba(21,23,24,.4)'; ctx.font='600 20px "SF Mono",Menlo,monospace';
    ctx.fillText('档案内暂无六星记录',M,930);
  }
  rec.forEach(function(r,i){
    var y=916+i*62;
    ctx.fillStyle='rgba(255,255,255,.78)'; roundRect(M,y,CW,50,CARD_R,ctx); ctx.fill();
    ctx.strokeStyle='rgba(21,23,24,.22)'; ctx.lineWidth=1.5; ctx.stroke();
    ctx.fillStyle='#151718'; ctx.font='800 24px -apple-system,"PingFang SC",sans-serif';
    ctx.fillText(r.name,M+20,y+34);
    ctx.font='700 20px "SF Mono",Menlo,monospace';
    ctx.fillStyle=r.up===true?'#0098DC':(r.up===false?'#C82A36':'rgba(21,23,24,.45)');
    ctx.fillText(r.up===true?'UP':(r.up===false?'歪':'—'),M+236,y+34);
    ctx.fillStyle='#B8860B'; ctx.font='800 22px "SF Mono",Menlo,monospace';
    ctx.fillText('第 '+r.gap+' 抽',M+308,y+34);
    ctx.fillStyle='rgba(21,23,24,.55)'; ctx.font='600 20px -apple-system,"PingFang SC",sans-serif';
    ctx.fillText(r.pool||'',M+456,y+34);
    ctx.fillStyle='rgba(21,23,24,.42)'; ctx.font='600 19px "SF Mono",Menlo,monospace';
    ctx.textAlign='right'; ctx.fillText(r.date,M+CW-20,y+34); ctx.textAlign='left';
  });
  ctx.fillStyle='rgba(21,23,24,.5)'; ctx.font='600 19px "SF Mono",Menlo,monospace';
  ctx.fillText('最近 '+rec.length+' 条六星记录 · 六星硬保底 99 抽 · 各池独立统计 · 非全服排名',M,1292);
  footer(ctx,g.seed,'GACHA ARCHIVE');
}
function seal(ctx,x,y,r){
  ctx.save(); ctx.strokeStyle='#C82A36'; ctx.lineWidth=2;
  ctx.beginPath(); ctx.arc(x,y,r,0,Math.PI*2); ctx.stroke();
  ctx.lineWidth=1; ctx.beginPath(); ctx.arc(x,y,r-5,0,Math.PI*2); ctx.stroke();
  ctx.fillStyle='#C82A36'; ctx.textAlign='center';
  ctx.font='800 13px "SF Mono",Menlo,monospace'; ctx.fillText('ARKBOX',x,y-6);
  ctx.font='700 10px -apple-system,"PingFang SC"'; ctx.fillText('档案生成日',x,y+8);
  ctx.font='800 10px "SF Mono",Menlo,monospace'; ctx.fillText(ARK.date,x,y+22);
  ctx.restore(); ctx.textAlign='left';
}
function banner(ctx,y,cells){
  ctx.fillStyle='#0098DC'; ctx.fillRect(0,y,W,86);
  cells.forEach(function(c,i){
    var x=M+i*(CW/3);
    ctx.fillStyle='rgba(255,255,255,.78)'; ctx.font='800 17px -apple-system,"PingFang SC",sans-serif';
    ctx.fillText(c[0],x,y+30);
    ctx.fillStyle='#fff'; ctx.font='900 36px "SF Mono",Menlo,monospace';
    ctx.fillText(c[1],x,y+72);
  });
}
function secHead(ctx,num,title,y){
  ctx.fillStyle='#0098DC'; ctx.font='700 16px "SF Mono",Menlo,monospace';
  ctx.fillText(num,M,y);
  ctx.fillStyle='#151718'; ctx.font='800 '+H2+'px -apple-system,"PingFang SC",sans-serif';
  ctx.fillText(title,M+34,y);
  var w=ctx.measureText(title).width;
  ctx.fillStyle='rgba(21,23,24,.18)';
  ctx.fillRect(M+34+w+12,y-9,Math.max(0,CW-(34+w+12)),1.5);
}
function drawTerra(ctx, done){
  var cb = done || function(){};
  var m=ARK.terra.meta;
  paper(ctx); hazard(ctx,0);
  ctx.fillStyle='#0098DC'; ctx.font='800 24px "SF Mono",Menlo,monospace';
  ctx.fillText('ARKBOX // TERRA CODEX',M,120);
  ctx.fillStyle='#151718'; ctx.font='900 92px -apple-system,"PingFang SC",sans-serif';
  ctx.fillText('泰拉图鉴',M,240);
  ctx.font='700 26px "SF Mono",Menlo,monospace'; ctx.fillStyle='rgba(21,23,24,.55)';
  ctx.fillText('六星 '+m.sixOwned+' / '+m.sixTotal+' · 地区全档案 '+m.regionsFull+' / '+m.regionsTotal,M,300);
  seal(ctx,968,158,54);
  banner(ctx,340,[['六星归档',m.sixOwned+' / '+m.sixTotal],
                  ['地区全档案',m.regionsFull+' / '+m.regionsTotal],
                  ['地区各差 1 名',(m.near||[]).length]]);
  /* 环与地图同占 366 起，顶部对齐；环内两行文字整体居中于圆心 470 */
  ring(ctx,190,616,104,m.pct/100,28);
  ctx.fillStyle='#151718'; ctx.font='900 54px "SF Mono",Menlo,monospace'; ctx.textAlign='center';
  ctx.fillText(m.pct+'%',190,624); ctx.font='700 19px "SF Mono",Menlo,monospace';
  ctx.fillStyle='rgba(21,23,24,.5)'; ctx.fillText('六星归档率',190,660); ctx.textAlign='left';
  /* 各差 1 名清单：两列三行，把纵向空间让给下面的地区进度 */
  secHead(ctx,'01','差 1 名就全档案',820);
  var near=m.near.slice(0,6);
  near.forEach(function(n,i){
    var x=M+(i%2)*488, y=840+Math.floor(i/2)*62;
    ctx.fillStyle='rgba(255,255,255,.78)'; roundRect(x,y,464,52,CARD_R,ctx); ctx.fill();
    ctx.strokeStyle='rgba(21,23,24,.22)'; ctx.lineWidth=1.5; ctx.stroke();
    ctx.fillStyle='#151718'; ctx.font='800 24px -apple-system,"PingFang SC",sans-serif';
    ctx.fillText(n.name+'　'+n.owned6+'/'+n.total6,x+18,y+34);
    ctx.fillStyle='#C82A36'; ctx.font='700 21px -apple-system,"PingFang SC",sans-serif';
    ctx.textAlign='right'; ctx.fillText('差 '+n.missing.join('、'),x+446,y+34); ctx.textAlign='left';
  });
  /* 地区进度条：六星最多的 6 个地区，填掉原来的空白带；条尾与数字衔接 */
  secHead(ctx,'02','地区归档进度',1040);
  var regs=(ARK.terra.regions||[]).filter(function(r){ return r.area==='land' && r.total6>0; })
    .sort(function(a,b){ return b.total6-a.total6; }).slice(0,6);
  regs.forEach(function(r,i){
    var y=1062+i*38, pct=r.total6?r.owned6/r.total6:0;
    ctx.fillStyle='#151718'; ctx.font='800 22px -apple-system,"PingFang SC",sans-serif';
    ctx.fillText(r.name,M,y+22);
    ctx.fillStyle='rgba(21,23,24,.1)'; ctx.fillRect(200,y+10,720,8);
    ctx.fillStyle=pct>=1?'#0098DC':'#B8860B'; ctx.fillRect(200,y+10,720*pct,8);
    ctx.fillStyle='rgba(21,23,24,.6)'; ctx.font='700 20px "SF Mono",Menlo,monospace';
    ctx.textAlign='right'; ctx.fillText(r.owned6+' / '+r.total6,M+CW,y+22); ctx.textAlign='left';
  });
  ctx.fillStyle='rgba(21,23,24,.5)'; ctx.font='600 19px "SF Mono",Menlo,monospace';
  ctx.fillText('一个六边形 = 1 名六星 · 所属口径 nationId · 进度仅列六星数前 6 地区 · 轮廓为示意',M,1312);
  /* 地图：导出专用简化版——克隆后删掉全部 <text>。
     SVG 缩到 0.5 倍后标签只剩 5px 糊字，去掉反而干净；地区名由下方进度条承担。 */
  var svg=document.getElementById('tc-map');
  var clone=svg.cloneNode(true);
  /* 标签组 .tcl-root 里含底板/引导线/文字，整组删；再清掉散落的 <text>。
     只留陆块 + 点阵 + 特殊块圆圈，缩小后反而干净。 */
  var junk=clone.querySelectorAll('.tcl-root, text');
  for(var ti=junk.length-1; ti>=0; ti--){
    if(junk[ti] && junk[ti].parentNode) junk[ti].parentNode.removeChild(junk[ti]);
  }
  var xml=new XMLSerializer().serializeToString(clone);
  var url=URL.createObjectURL(new Blob([xml],{type:'image/svg+xml;charset=utf-8'}));
  var img=new Image();
  img.onload=function(){ ctx.drawImage(img,376,460,648,314); URL.revokeObjectURL(url);
    footer(ctx,m.sixTotal*7+m.sixOwned,'TERRA CODEX'); cb(); };
  img.onerror=function(){ URL.revokeObjectURL(url); footer(ctx,m.sixTotal*7+m.sixOwned,'TERRA CODEX'); cb(); };
  img.src=url;
}
function drawOp(ctx){
  var sel=document.getElementById('sh-op');
  var c=ARK.charMap[sel && sel.value] || ARK.chars[0]; if(!c) return;
  paper(ctx); hazard(ctx,0);
  ctx.fillStyle='#0098DC'; ctx.font='800 24px "SF Mono",Menlo,monospace';
  ctx.fillText('ARKBOX // OPERATOR FILE',M,120);
  ctx.fillStyle='#151718'; ctx.font='900 92px -apple-system,"PingFang SC",sans-serif';
  ctx.fillText(c.nm,M,240);
  ctx.font='700 26px "SF Mono",Menlo,monospace'; ctx.fillStyle='rgba(21,23,24,.55)';
  ctx.fillText((ARK.regName[c.reg]||'未归类')+' · '+esc(c.dn||''),M,300);
  var img=new Image(); img.crossOrigin='anonymous';
  var done=function(){
    ctx.save(); roundRect(M,360,640,640,8,ctx); ctx.clip();
    ctx.drawImage(img,M,360,640,640); ctx.restore();
    ctx.strokeStyle='#151718'; ctx.lineWidth=3; roundRect(M,360,640,640,8,ctx); ctx.stroke();
    rest();
  };
  img.onload=done;
  img.onerror=function(){
    ctx.fillStyle='rgba(21,23,24,.08)'; roundRect(M,360,640,640,8,ctx); ctx.fill();
    ctx.fillStyle='#B8860B'; ctx.font='900 200px "PingFang SC",sans-serif'; ctx.textAlign='center';
    ctx.fillText(c.nm.slice(0,1),M+320,720); ctx.textAlign='left'; rest();
  };
  function rest(){
    var rows=[['星级','★'.repeat(c.rar)],['职业',c.pf],['等级','Lv.'+c.lv+' · '+OPS.p2[c.ev]],
      ['潜能',String(c.pot)],['技能专精',String(c.mas)],['其他',(c.sk?'时装 ':'')+(c.md?'模组':'')||'—']];
    /* 行距 100：右列底边 976 贴住立绘底边 1000，两列不再一高一低 */
    rows.forEach(function(r,i){
      var y=400+i*100;
      ctx.fillStyle='rgba(255,255,255,.75)'; roundRect(748,y,268,76,CARD_R,ctx); ctx.fill();
      ctx.strokeStyle='rgba(21,23,24,.22)'; ctx.lineWidth=1.5; ctx.stroke();
      ctx.fillStyle='rgba(21,23,24,.5)'; ctx.font='700 19px "SF Mono",Menlo,monospace';
      ctx.fillText(r[0],768,y+30);
      ctx.fillStyle='#151718'; ctx.font='800 26px -apple-system,"PingFang SC",sans-serif';
      ctx.fillText(String(r[1]),768,y+62);
    });
    /* 所属档案：通栏铺满 64→1016，右侧不再空一条 */
    var reg=null;
    (ARK.terra.regions||[]).forEach(function(x){ if(x.id===c.reg) reg=x; });
    ctx.fillStyle='#151718'; ctx.font='800 '+H2+'px -apple-system,"PingFang SC",sans-serif';
    ctx.fillText('所属档案',M,1032);
    if(reg){
      ctx.font='900 48px -apple-system,"PingFang SC",sans-serif';
      ctx.fillText(reg.name,M,1094);
      ctx.font='900 48px "SF Mono",Menlo,monospace'; ctx.fillStyle='#B8860B';
      ctx.textAlign='right'; ctx.fillText(reg.owned6+' / '+reg.total6,M+CW,1094); ctx.textAlign='left';
      var pct=reg.total6?reg.owned6/reg.total6:0;
      ctx.fillStyle='rgba(21,23,24,.12)'; ctx.fillRect(M,1116,CW,8);
      ctx.fillStyle=pct>=1?'#0098DC':'#B8860B'; ctx.fillRect(M,1116,CW*pct,8);
      ctx.fillStyle='rgba(21,23,24,.5)'; ctx.font='600 20px "SF Mono",Menlo,monospace';
      ctx.fillText('全服该地区 '+reg.total6+' 名六星 · 已归档 '+reg.owned6+' 名',M,1166);
    }else{
      /* 联动等无泰拉归属的干员：别留一个悬空标题 */
      ctx.fillStyle='rgba(21,23,24,.5)'; ctx.font='600 22px -apple-system,"PingFang SC",sans-serif';
      ctx.fillText('未编入泰拉地区档案（联动 / 特殊编制）',M,1094);
    }
    ctx.fillStyle='rgba(21,23,24,.5)'; ctx.font='600 19px "SF Mono",Menlo,monospace';
    ctx.fillText('头像来自公开镜像 · 数据取自森空岛 · 不含 UID',M,1292);
    footer(ctx,c.id.length*131+c.lv,'OPERATOR FILE');
  }
  img.src=av(c.id);
}
})();
"""


def build_archive_html(report, chars, out_path, site_mode=False, limit=None,
                       meta=None, profile=None, poster_b64=None,
                       poster_terra_b64=None):
    """chars: ark_box.fetch_chars 的干员列表；None 时降级为 v0.7 单页报告。

    meta 可注入（测试离线用）；默认取本地缓存的干员元数据。
    """
    if not chars:
        return render_single(report, out_path, limit=limit, site_mode=site_mode)

    meta = meta if meta is not None else load_meta()
    owned = {c["char_id"] for c in chars}
    nick = ("博士" if site_mode else
            (report.get("doctor", {}).get("nick") or "博士"))
    date_str = report.get("generated") or datetime.now().strftime("%Y.%m.%d")
    terra = build_terra(meta, owned, nick=nick, date=date_str)

    reg_name = {r["id"]: r["name"] for r in terra["regions"]}
    chars_js = []
    for c in chars:
        m = meta.get(c["char_id"]) or {}
        chars_js.append({
            "id": c["char_id"], "nm": c.get("name") or c["char_id"],
            "rar": c.get("rarity") or 0, "pf": c.get("profession") or "?",
            "lv": c.get("level") or 0, "ev": c.get("evolve") or 0,
            "pot": c.get("potential") or 1, "mas": c.get("mastery") or 0,
            "msl": c.get("skill") or 0,
            "md": bool(c.get("mod")), "sk": "#" in (c.get("skin_id") or ""),
            "ow": c["char_id"] in owned, "dn": m.get("dn") or "",
            "reg": bucket_of(c["char_id"], m) if m else "",
        })
    chars_js.sort(key=lambda c: (-c["lv"], -c["rar"]))

    m = report.get("metrics") or {}
    g = report.get("luck") or {}
    t = report.get("totals") or {}
    gacha = {
        "label": (report.get("title") or {}).get("label") or "寻访档案",
        # 分享卡页头要写"记录截至 X"：取档案覆盖区间的最新日期，缺省用"—"
        "date": (report.get("coverage") or {}).get("latest") or "—",
        "mean": m.get("mean_gap") or "—",
        "better": g.get("better_than") if g.get("better_than") is not None else "—",
        "six": t.get("six", 0), "pulls": t.get("pulls", 0),
        "up": f'{m.get("up_hits", 0)}/{m.get("up_total", 0)}' if m.get("up_total") else "待核",
        "pity": [{"label": p.get("pool_type_label") or "池", "current": p.get("current", 0)}
                 for p in report.get("pool_stats") or []][:6],
        "seed": t.get("pulls", 0) * 7 + t.get("six", 0),
    }
    # 分享卡下半部要"最近六星"流水：从各池 events 拍平，按日期+出货位置取最近 5 条
    _recent = []
    for _p in (report.get("pools") or {}).get("all") or []:
        for _e in _p.get("events") or []:
            _recent.append((_e.get("date") or "", _e.get("at_pull") or 0, {
                "name": _e.get("name") or "?",
                "gap": _e.get("gap") or 0,
                "date": _e.get("date") or "",
                "up": _e.get("is_up"),
                "pool": _p.get("pool") or "",
            }))
    _recent.sort(key=lambda _t: (_t[0], _t[1]))
    gacha["recent"] = [_t[2] for _t in _recent[-5:]][::-1]
    # 内嵌 JSON 瘦身：cells/silhouette 已渲染成 SVG，前端不需要
    terra_lite = {
        "regions": [{k: v for k, v in r.items() if k != "cells"} for r in terra["regions"]],
        "meta": terra["meta"],
    }
    ark = {
        "nick": nick, "date": date_str,
        "avBase": "https://raw.githubusercontent.com/yuanyan3060/ArknightsGameResource/main/avatar/",
        "site": bool(site_mode), "chars": chars_js, "terra": terra_lite,
        "regName": reg_name, "gacha": gacha,
    }
    char_map = {c["id"]: c for c in chars_js}

    tabs = [
        (TAB_GACHA, "寻访分析"),
        (TAB_TERRA, "泰拉图鉴"),
    ]
    nav = "".join(
        f'<button class="ab-tab{" on" if tid == TAB_GACHA else ""}" id="abt-{tid}" '
        f'data-tab="{tid}" type="button">{label}</button>' for tid, label in tabs)

    page_title = ("明日方舟档案 · ArkBox" if site_mode
                  else f'明日方舟档案 · {_h(nick)}')
    robots = ('<meta name="robots" content="noindex,nofollow,noarchive">\n'
              if site_mode else "")

    # 分享：寻访/泰拉两个页签各嵌一张海报 PNG（ark_poster_v4 / ark_poster_terra），
    # 不在页面里用 canvas 重画一套；缺失时回落 canvas（泰拉）或提示（寻访）。
    if poster_b64 and not site_mode:
        poster_tag = ('<img id="share-poster" alt="" style="display:none" '
                      'src="data:image/png;base64,' + poster_b64 + '">')
    else:
        poster_tag = '<span id="share-poster-missing" style="display:none"></span>'
    if poster_terra_b64 and not site_mode:
        terra_tag = ('<img id="share-terra" alt="" style="display:none" '
                     'src="data:image/png;base64,' + poster_terra_b64 + '">')
    else:
        terra_tag = '<span id="share-terra-missing" style="display:none"></span>'

    # 六维/称号与页面雷达同口径：剔除 rar=0 占位（审计 D-01，359 口径）
    _feat = build_features([c for c in (chars or []) if (c.get("rarity") or 0) > 0], terra)
    terra_page = ('<div class="wrap">'
                  + _terra_stats_html(terra, profile=profile, feat=_feat)
                  + '<div class="tc-panel" id="tc-panel"></div>'
                  + TERRA_OPS_BODY + '</div>')

    html_text = f'''<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
{robots}<title>{page_title}</title>
<style>{REPORT_CSS}{SHELL_CSS}{TERRA_CSS}{BOX_CSS}{SHARE_CSS}
.bx-info{{position:fixed}}#tc-tip{{position:fixed;z-index:70;display:none;width:190px;background:#fff;
border:1.5px solid var(--ink);padding:8px 10px;font:600 12px -apple-system,'PingFang SC';box-shadow:4px 4px 0 rgba(21,23,24,.12)}}
#tc-tip b{{font-size:14px}}#tc-tip .ow{{color:var(--gold);font:700 10px 'SF Mono',Menlo;margin-left:6px}}
#tc-tip .no{{color:var(--red);font:700 10px 'SF Mono',Menlo;margin-left:6px}}#tc-tip i{{font-style:normal;color:var(--dim2);font-size:10px}}
</style></head><body>
<div class="grid"></div><div class="hazard"></div>
<nav class="ab-nav">
  <div class="ab-brand"><b>ARKBOX</b> // ARCHIVE</div>
  <div class="ab-tabs">{nav}</div>
  <div class="ab-meta"><span class="live">● LOCAL</span> {date_str}</div>
</nav>
<section class="ab-page on" id="ab-gacha"><div class="wrap">{render_body(report, site_mode=site_mode, limit=limit)}</div></section>
<section class="ab-page" id="ab-terra">{terra_page}</section>
<div id="tc-tip"></div>
{poster_tag}
{terra_tag}
<canvas id="sh-canvas" width="1080" height="1440" style="display:none"></canvas>
<div id="share-modal" class="shm"><div class="shm-box"><div class="shm-head"><b>分享图预览</b><button type="button" id="shm-close">关闭</button></div><div class="shm-body"><img id="shm-img" alt=""></div><div class="shm-foot"><button type="button" id="shm-dl" class="sh-btn go">下载 PNG</button></div></div></div>
<div class="fab"><button id="fab-share" type="button" title="预览并保存分享图"><span class="ic">↓</span>分享</button><button id="fab-top" type="button" title="回到顶部"><span class="ic">↑</span>顶部</button></div>
<script>
window.ARK = {json.dumps(ark, ensure_ascii=False, separators=(",", ":"))};
window.ARK.charMap = {json.dumps(char_map, ensure_ascii=False, separators=(",", ":"))};
</script>
<script>{SHELL_JS}</script>
</body></html>'''

    out_path = os.path.expanduser(out_path)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_text)
    return out_path
