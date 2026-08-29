#!/usr/bin/env python3
# coding: utf-8
# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.
"""重新生成 docs/images 下的三张架构图.

一张内容表驱动英文与中文两套 SVG, 防止两语几何漂移 (此前英文图里甚至混着
中文小注)。所有坐标由代码计算, 每条箭头都锚在真实盒子的边上, 而不是手拍的
坐标——这正是旧图「线悬空/穿底板/平行撞线」的根源。

用法::

    python scripts/gen_arch_svgs.py

输出到:
    docs/images/architecture-layers.{en,zh}.svg
    docs/images/architecture-dependencies.{en,zh}.svg
    docs/images/architecture-task-sequence.{en,zh}.svg

命中的方法: 改这张表里的文字/盒子坐标, 重跑脚本即可, 不要再手改 SVG。
"""

from __future__ import annotations

import html
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "images"

# ---------------------------------------------------------------- helpers

def esc(s: str) -> str:
    return html.escape(s, quote=False)


def T(x: float, y: float, s: str, cls: str = "", anchor: str = "middle",
      fill: str | None = None, size: int | None = None, rotate: bool = False,
      font: str = "node") -> str:
    """One <text> element. `font` only used when rotate needs the family set up."""
    attrs = f'x="{x}" y="{y}"'
    if anchor != "middle":
        attrs += f' text-anchor="{anchor}"'
    if cls:
        attrs += f' class="{cls}"'
    if fill:
        attrs += f' fill="{fill}"'
    if size:
        attrs += f' font-size="{size}"'
    if rotate:
        attrs += ' transform="rotate(-90 ' + f'{x} {y}"'
    return f"<text {attrs}>{esc(s)}</text>"


def path(d: str, cls: str = "edge") -> str:
    return f'<path d="{d}" class="{cls}"/>'


# ---------------------------------------------------------------- diagram 1

# Each entry: (chip, accent, stroke) color-keys, name, node, sub.
_LAYER_COLORS = [
    ("#2563eb", "#2563eb", "#9bbcea", "Agent", "RobotSession · build_robot_agent() · run_robot_task()",
     "task entry, assembly, session lifecycle, and model orchestration"),
    ("#d97706", "#d97706", "#efc36f", "Rails", "Safety · Recovery · VisualFeedback · Trace · Diagnosis",
     "checks, recovery, feedback, and execution evidence around tool calls"),
    ("#3b82f6", "#3b82f6", "#9bbcea", "Tool", "build_robot_tools · RobotControlTool · InProcessCodeTool",
     "exposes only the actions in the API ∩ Env capability intersection"),
    ("#8b5cf6", "#8b5cf6", "#b9a8ec", "API", "ActionSpec vocabulary · @implements(SPEC) · defaults",
     "action contract + adapter implementation (no Mixin / component layer)"),
    ("#059669", "#059669", "#83c5aa", "Env", "BaseRobotEnv · RobotObservation",
     "single hardware contract, capability declaration, structured state"),
    ("#047857", "#047857", "#69b396", "Hardware", "Vendor Driver · Robot · Gripper · Camera",
     "vendor SDKs, serial, CAN, sockets, and physical devices"),
]


def layers(TXT: dict) -> str:
    W, H = 1200, 820
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc">',
             f'<title id="title">{esc(TXT["title"])}</title><desc id="desc">{esc(TXT["desc"])}</desc>']
    parts.append(
        '<defs><marker id="arrow" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto">'
        '<path d="M0 0L9 4.5L0 9Z" fill="#2563eb"/></marker>'
        '<marker id="dash-arrow" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto">'
        '<path d="M0 0L9 4.5L0 9Z" fill="#d97706"/></marker>'
        '<filter id="shadow" x="-10%" y="-15%" width="120%" height="140%">'
        '<feDropShadow dx="0" dy="3" stdDeviation="4" flood-color="#19324d" flood-opacity="0.12"/></filter>')
    font = TXT["font"]
    parts.append(
        f"<style>text{{font-family:{font};fill:#172033}}"
        ".title{font-size:29px;font-weight:700}.subtitle{font-size:14px;fill:#5b6b82}"
        ".name{font-size:17px;font-weight:700;fill:#fff}.node{font-size:16px;font-weight:700}"
        ".sub{font-size:13px;fill:#5b6b82}.label{font-size:13px;font-weight:700}"
        ".legend{font-size:12px;fill:#526174}</style></defs>")
    parts.append(f'<rect width="{W}" height="{H}" rx="24" fill="#f4f7fc"/>')
    parts.append(T(42, 48, TXT["t_title"], "title", anchor="start"))
    parts.append(T(42, 73, TXT["t_sub"], "subtitle", anchor="start"))

    # left six-layer column
    x, w, h, y0, dy = 90, 720, 84, 110, 102
    parts.append('<g filter="url(#shadow)">')
    for i, (chip, accent, stroke, name, node, sub) in enumerate(_LAYER_COLORS):
        y = y0 + i * dy
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="#fff" stroke="{stroke}"/>')
        parts.append(f'<rect x="{x}" y="{y}" width="160" height="{h}" rx="14" fill="{chip}"/>')
        parts.append(f'<rect x="{x + 146}" y="{y}" width="160" height="{h}" fill="{chip}"/>')
        parts.append(f'<rect x="{x + 146}" y="{y}" width="14" height="{h}" fill="{accent}"/>')
        parts.append(T(x + 80, y + 50, name, "name"))
        parts.append(T(278, y + 35, node, "node", anchor="start"))
        parts.append(T(278, y + 59, sub, "sub", anchor="start"))
    parts.append("</g>")
    # chain arrows between layers (downward)
    for i in range(len(_LAYER_COLORS) - 1):
        y = y0 + i * dy + h
        parts.append(path(f"M{x + 360} {y}V{y + 18}", "edge"))
    parts[-1] = path(f"M{x + 360} {y0 + 4 * dy + h}V{y0 + 5 * dy}")  # down into last gap handled below

    # right side panels
    panel_x, panel_w = 870, 270
    ip = 0
    panel_defs = [
        ("#7c3aed", "#f3efff", "#aa94e7", TXT["p_skill_t"], TXT["p_skill_node"],
         TXT["p_skill_s1"], TXT["p_skill_s2"], TXT["p_skill_s3"], 110, 224),
        ("#059669", "#eefaf5", "#83c5aa", TXT["p_perc_t"], TXT["p_perc_node"],
         TXT["p_perc_s1"], TXT["p_perc_s2"], "", 346, 224),
        ("#2563eb", "#f2f7fd", "#9bbcea", TXT["p_plan_t"], TXT["p_plan_node"],
         TXT["p_plan_s1"], TXT["p_plan_s2"], TXT["p_plan_s3"], 582, 180),
    ]
    for chip, bg, stroke, ptitle, pnode, s1, s2, s3, py, ph in panel_defs:
        parts.append(f'<rect x="{panel_x}" y="{py}" width="{panel_w}" height="{ph}" rx="18" fill="{bg}" stroke="{stroke}" stroke-width="2"/>')
        parts.append(f'<rect x="{panel_x}" y="{py}" width="{panel_w}" height="58" rx="18" fill="{chip}"/>')
        parts.append(f'<rect x="{panel_x}" y="{py + 42}" width="{panel_w}" height="16" fill="{chip}"/>')
        pad = 74
        parts.append(T(panel_x + 135, py + 35, ptitle, "name"))
        parts.append(T(panel_x + 135, py + pad + 18, pnode, "node"))
        for j, s in enumerate([s1, s2, s3]):
            if s:
                parts.append(T(panel_x + 135, py + pad + 46 + 28 * j, s, "sub"))
        ip += 1

    # guide arrow: Skill panel -> Agent box right edge
    parts.append(path(f"M{panel_x} 152H{x + w}", "dash-guide"))
    parts[-1] = path(f'M{panel_x} 152H{x + w}', "dash-guide")  # anchor
    # feedback loop: Hardware left edge -> up the left gutter -> Agent left edge
    parts.append(path(f"M{x} 662H55V152H{x}", "dash-guide"))
    parts.append(T(42, 400, TXT["l_up"], "label", rotate=True))
    parts.append(T(920, 140, TXT["l_guide"], "label", fill="#b45309"))

    # legend
    ly = 775
    parts.append(f'<line x1="760" y1="{ly}" x2="800" y2="{ly}" stroke="#2563eb" stroke-width="2.5"/>')
    parts.append(T(810, ly + 4, TXT["leg_call"], "legend", anchor="start"))
    parts.append(f'<line x1="930" y1="{ly}" x2="970" y2="{ly}" stroke="#d97706" stroke-width="2.5" stroke-dasharray="8 6"/>')
    parts.append(T(980, ly + 4, TXT["leg_guide"], "legend", anchor="start"))
    parts.append("</svg>")
    return "\n".join(parts)
