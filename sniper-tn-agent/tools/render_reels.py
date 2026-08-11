#!/usr/bin/env python3
"""Render Sniper-Tn week content into vertical MP4 Reels and thumbnails.

The script intentionally keeps captions burned into the video so every Reel stays
understandable with muted audio. It requires the packages in requirements.txt.
"""

from __future__ import annotations

import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path

import arabic_reshaper
import imageio_ffmpeg
from bidi.algorithm import get_display
from mutagen.mp3 import MP3
from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[2]
CONTENT_FILE = REPO / "sniper-tn-agent/content/week-01/content.json"
FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
W, H = 1080, 1920
GOLD = (221, 188, 92, 255)
WHITE = (255, 255, 255, 255)
PALE = (250, 245, 225, 255)
DARK = (5, 9, 13, 224)


def rtl(text: str) -> str:
    """Shape Arabic and apply bidirectional layout for Pillow."""
    return get_display(arabic_reshaper.reshape(text))


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def text_width(draw: ImageDraw.ImageDraw, text: str, selected_font: ImageFont.FreeTypeFont) -> int:
    box = draw.textbbox((0, 0), text, font=selected_font)
    return box[2] - box[0]


def fit_font(draw: ImageDraw.ImageDraw, text: str, width: int, start: int, minimum: int = 38) -> ImageFont.FreeTypeFont:
    for size in range(start, minimum - 1, -2):
        selected = font(BOLD, size)
        if text_width(draw, text, selected) <= width:
            return selected
    return font(BOLD, minimum)


def split_lines(draw: ImageDraw.ImageDraw, text: str, width: int, size: int = 66, max_lines: int = 2) -> list[str]:
    """Wrap logical Arabic text before shaping each final line."""
    words = text.split()
    lines: list[str] = []
    current = ""
    measure_font = font(BOLD, size)
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and text_width(draw, rtl(candidate), measure_font) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    if len(lines) <= max_lines:
        return lines
    # Merge any overflow into the final line; fit_font will reduce it if needed.
    return lines[: max_lines - 1] + [" ".join(lines[max_lines - 1 :])]


def centered(draw: ImageDraw.ImageDraw, text: str, y: int, selected_font: ImageFont.FreeTypeFont, color, stroke: int = 1) -> int:
    box = draw.textbbox((0, 0), text, font=selected_font, stroke_width=stroke)
    x = (W - (box[2] - box[0])) / 2
    draw.text(
        (x, y),
        text,
        font=selected_font,
        fill=color,
        stroke_width=stroke,
        stroke_fill=(0, 0, 0, 230),
    )
    return box[3] - box[1]


def crop_background(source: Image.Image, scene: int = 0) -> Image.Image:
    """Create a 1080x1920 crop with tiny per-scene movement."""
    base_ratio = max(W / source.width, H / source.height)
    zoom = base_ratio * (1.015 + (scene % 3) * 0.008)
    nw, nh = round(source.width * zoom), round(source.height * zoom)
    image = source.resize((nw, nh), Image.Resampling.LANCZOS)
    x_shift = ((scene % 3) - 1) * 10
    y_shift = ((scene % 2) * 2 - 1) * 7
    left = max(0, min(nw - W, (nw - W) // 2 + x_shift))
    top = max(0, min(nh - H, (nh - H) // 2 + y_shift))
    return image.crop((left, top, left + W, top + H)).convert("RGBA")


def dark_gradient() -> Image.Image:
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(shade)
    for y in range(H):
        alpha = int(8 + 96 * (y / H) ** 2)
        draw.line((0, y, W, y), fill=(0, 0, 0, alpha))
    return shade


def add_header(image: Image.Image) -> None:
    draw = ImageDraw.Draw(image)
    for left, right in ((62, 270), (810, 1018)):
        draw.line((left, 66, right, 66), fill=GOLD, width=3)
    draw.line((62, 66, 62, 155), fill=GOLD, width=3)
    draw.line((1018, 66, 1018, 155), fill=GOLD, width=3)
    draw.rounded_rectangle((250, 78, 830, 265), radius=36, fill=(4, 7, 10, 205), outline=GOLD, width=3)
    centered(draw, "SNIPER–TN", 95, font(BOLD, 66), GOLD)
    centered(draw, rtl("القنّاص"), 177, font(BOLD, 48), PALE)
    draw.rounded_rectangle((335, 1790, 745, 1850), radius=24, fill=(4, 7, 10, 190), outline=(221, 188, 92, 150), width=2)
    centered(draw, "AI  •  SHORTS", 1802, font(BOLD, 27), GOLD, 0)


def add_caption(image: Image.Image, logical_text: str, accent: bool = False) -> None:
    draw = ImageDraw.Draw(image)
    lines = split_lines(draw, logical_text, 800, 66, 2)
    y0 = 1280
    panel = (65, y0 - 65, W - 65, y0 + 280)
    draw.rounded_rectangle((panel[0] + 8, panel[1] + 12, panel[2] + 8, panel[3] + 12), radius=38, fill=(0, 0, 0, 105))
    draw.rounded_rectangle(panel, radius=38, fill=DARK, outline=(221, 188, 92, 175), width=3)
    draw.rounded_rectangle((108, y0 - 18, 122, y0 + 190), radius=7, fill=GOLD)
    yy = y0
    for index, logical_line in enumerate(lines):
        shaped = rtl(logical_line)
        selected = fit_font(draw, shaped, 800, 68, 40)
        color = GOLD if accent and index == len(lines) - 1 else WHITE
        height = centered(draw, shaped, yy, selected, color, 2)
        yy += height + 34


def make_thumbnail(source: Image.Image, post: dict, output: Path) -> None:
    image = crop_background(source, 1)
    image = Image.alpha_composite(image, dark_gradient())
    add_header(image)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((65, 1235, W - 65, 1638), radius=44, fill=(3, 7, 10, 230), outline=GOLD, width=4)
    lines = split_lines(draw, post["hook"], 820, 66, 3)
    yy = 1300
    for index, logical_line in enumerate(lines):
        shaped = rtl(logical_line)
        selected = fit_font(draw, shaped, 820, 68, 42)
        color = GOLD if index == len(lines) - 1 else WHITE
        height = centered(draw, shaped, yy, selected, color, 2)
        yy += height + 26
    image.convert("RGB").save(output, quality=94, optimize=True)


def allocate_durations(total: float, captions: list[str]) -> list[float]:
    # A small baseline keeps short punch lines visible; length adds reading time.
    weights = [1.5 + min(len(text), 45) / 30 for text in captions]
    scale = total / sum(weights)
    values = [weight * scale for weight in weights]
    # Keep exact total after floating-point rounding.
    values[-1] += total - sum(values)
    return values


def render_post(post: dict, work: Path) -> None:
    day = post["sequence"]
    asset_dir = CONTENT_FILE.parent / "assets" / f"day-{day:02d}"
    background_path = asset_dir / "background.png"
    voice_path = asset_dir / "voiceover.mp3"
    reel_path = asset_dir / "reel.mp4"
    thumbnail_path = asset_dir / "thumbnail.jpg"
    if not background_path.exists() or not voice_path.exists():
        raise FileNotFoundError(f"Missing background or voiceover for day {day}")

    duration = MP3(voice_path).info.length
    source = Image.open(background_path).convert("RGB")
    scene_dir = work / f"day-{day:02d}"
    scene_dir.mkdir(parents=True)
    captions = post["on_screen"]
    durations = allocate_durations(duration, captions)

    for index, caption in enumerate(captions):
        scene = crop_background(source, index)
        scene = Image.alpha_composite(scene, dark_gradient())
        add_header(scene)
        add_caption(scene, caption, accent=index in {0, len(captions) - 1})
        scene.convert("RGB").save(scene_dir / f"scene-{index + 1:02d}.jpg", quality=91, optimize=True)

    concat_path = scene_dir / "scenes.ffconcat"
    with concat_path.open("w", encoding="utf-8") as handle:
        handle.write("ffconcat version 1.0\n")
        for index, segment_duration in enumerate(durations):
            handle.write(f"file scene-{index + 1:02d}.jpg\n")
            handle.write(f"duration {segment_duration:.6f}\n")
        handle.write(f"file scene-{len(captions):02d}.jpg\n")

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    fade_out_start = max(0, duration - 0.72)
    audio_fade_start = max(0, duration - 0.52)
    progress = f"(iw-130)*min(t/{duration:.6f},1)"
    command = [
        ffmpeg,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_path),
        "-i",
        str(voice_path),
        "-vf",
        (
            "fps=30,"
            f"drawbox=x=65:y=1881:w='{progress}':h=8:color=0xDDBC5C@0.92:t=fill,"
            f"fade=t=in:st=0:d=0.55,fade=t=out:st={fade_out_start:.3f}:d=0.72,format=yuv420p"
        ),
        "-map",
        "0:v",
        "-map",
        "1:a",
        "-t",
        f"{duration:.6f}",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-profile:v",
        "high",
        "-level",
        "4.1",
        "-g",
        "90",
        "-keyint_min",
        "60",
        "-sc_threshold",
        "0",
        "-r",
        "30",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-af",
        f"afade=t=in:st=0:d=0.15,afade=t=out:st={audio_fade_start:.3f}:d=0.52",
        "-movflags",
        "+faststart",
        str(reel_path),
    ]
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    make_thumbnail(source, post, thumbnail_path)

    post["duration_seconds"] = round(duration, 3)
    post["asset"] = {
        "video": f"assets/day-{day:02d}/reel.mp4",
        "thumbnail": f"assets/day-{day:02d}/thumbnail.jpg",
        "voiceover": f"assets/day-{day:02d}/voiceover.mp3",
        "background": f"assets/day-{day:02d}/background.png",
    }
    print(f"Rendered day {day}: {duration:.2f}s -> {reel_path.relative_to(REPO)}")


def main() -> None:
    if not FONT.exists() or not BOLD.exists():
        raise RuntimeError("DejaVu Sans fonts are required to render Arabic captions")
    data = json.loads(CONTENT_FILE.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="sniper-tn-render-") as temp:
        work = Path(temp)
        for post in data["posts"]:
            if post["sequence"] >= 2:
                render_post(post, work)
    CONTENT_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
