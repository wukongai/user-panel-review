#!/usr/bin/env python3
"""把公开脱敏对话渲染为可重复生成的中文长截图。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


WIDTH = 1440
MARGIN = 92
CONTENT_WIDTH = WIDTH - MARGIN * 2
TEXT_WIDTH = 1040
LINE_GAP = 14
TURN_GAP = 34
FILES = {
    "demo": "01-demo.png",
    "customize": "02-customize.png",
    "save": "03-save.png",
    "own-content": "04-own-content.png",
    "special-user": "05-special-user.png",
}


def font_path() -> str:
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    for candidate in candidates:
        if Path(candidate).is_file():
            return candidate
    raise FileNotFoundError("未找到可渲染中文的系统字体")


def wrap_line(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, width: int) -> list[str]:
    if not text:
        return [""]
    lines: list[str] = []
    current = ""
    for char in text:
        candidate = current + char
        if current and draw.textlength(candidate, font=font) > width:
            lines.append(current.rstrip())
            current = char.lstrip()
        else:
            current = candidate
    lines.append(current.rstrip())
    return lines


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines():
        if paragraph.startswith("### "):
            paragraph = paragraph[4:]
        lines.extend(wrap_line(draw, paragraph, font, width))
    return lines


def stage_height(stage: dict, body_font: ImageFont.FreeTypeFont) -> tuple[int, list[list[str]]]:
    probe = Image.new("RGB", (WIDTH, 100), "white")
    draw = ImageDraw.Draw(probe)
    wrapped: list[list[str]] = []
    total = 250
    line_height = body_font.size + LINE_GAP
    for turn in stage["turns"]:
        lines = wrap_text(draw, turn["text"], body_font, TEXT_WIDTH)
        wrapped.append(lines)
        total += 72 + len(lines) * line_height + TURN_GAP
    return total + 110, wrapped


def draw_stage(stage: dict, destination: Path) -> Path:
    regular = font_path()
    title_font = ImageFont.truetype(regular, 46)
    subtitle_font = ImageFont.truetype(regular, 24)
    body_font = ImageFont.truetype(regular, 29)
    role_font = ImageFont.truetype(regular, 23)
    height, wrapped_turns = stage_height(stage, body_font)
    image = Image.new("RGB", (WIDTH, height), "#F6F7F9")
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle((42, 38, WIDTH - 42, height - 42), radius=34, fill="#FFFFFF")
    draw.text((MARGIN, 86), stage["title"], font=title_font, fill="#172033")
    draw.text((MARGIN, 152), "user-review 真实交互记录", font=subtitle_font, fill="#7A8496")
    draw.line((MARGIN, 203, WIDTH - MARGIN, 203), fill="#E3E7ED", width=2)

    y = 240
    line_height = body_font.size + LINE_GAP
    for turn, lines in zip(stage["turns"], wrapped_turns, strict=True):
        is_user = turn["role"] == "user"
        bubble_width = TEXT_WIDTH + 64
        x = WIDTH - MARGIN - bubble_width if is_user else MARGIN
        bubble_height = 62 + len(lines) * line_height
        fill = "#E8F1FF" if is_user else "#F1F3F6"
        role_color = "#2563EB" if is_user else "#596579"
        draw.rounded_rectangle((x, y, x + bubble_width, y + bubble_height), radius=26, fill=fill)
        draw.text((x + 32, y + 20), "你" if is_user else "目标用户反馈", font=role_font, fill=role_color)
        text_y = y + 60
        for line in lines:
            draw.text((x + 32, text_y), line, font=body_font, fill="#202838")
            text_y += line_height
        y += bubble_height + TURN_GAP

    draw.text(
        (MARGIN, height - 86),
        "真实多轮隔离体验 · 公开版仅展示自然语言交互 · AI 模拟不等于真人研究",
        font=subtitle_font,
        fill="#8A93A3",
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, format="PNG", optimize=True)
    return destination


def render(transcript: Path, output_dir: Path) -> list[Path]:
    value = json.loads(transcript.read_text(encoding="utf-8"))
    outputs: list[Path] = []
    for stage in value["stages"]:
        outputs.append(draw_stage(stage, output_dir / FILES[stage["id"]]))
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transcript", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    for output in render(args.transcript, args.output_dir):
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
