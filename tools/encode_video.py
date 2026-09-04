#!/usr/bin/env python3
"""Готовит исходник ролика к вебу: H.264 mp4 под нужный слот лендинга.

    python3 tools/encode_video.py <исходник> <id-слота> [--wide]
                                 [--poster-at СЕК | --poster-file ФАЙЛ]

Кладёт результат в `assets/video/<id-слота>.mp4`. Без `--wide` — превью
в ряду по три (960×540), с `--wide` — широкий блок в интро (1280×720).
Список слотов — `python3 tools/videos.py`.

Почему не оставляем исходник как есть: превью показывается в колонке ~230 px,
а исходники приходят в 1080p и 4K по 20–40 МБ. Git хранит историю вечно,
поэтому жмём до коммита, а не после.
"""

import argparse
import pathlib
import shutil
import subprocess
import sys
import tempfile

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
VIDEO_DIR = ROOT / "assets" / "video"
IMG_DIR = ROOT / "assets" / "img"

# crf 25 — предел, за которым на градиентах появляется бандинг;
# faststart двигает индекс в начало файла, иначе видео не стартует до полной загрузки
PRESETS = {
    False: {"scale": "960:-2", "crf": "25", "audio": "96k"},
    True: {"scale": "1280:-2", "crf": "23", "audio": "128k"},
}


def encode(src, dest, wide):
    p = PRESETS[wide]
    cmd = [
        "ffmpeg", "-y", "-i", str(src),
        "-vf", f"scale={p['scale']}:flags=lanczos",
        "-c:v", "libx264", "-profile:v", "high", "-preset", "slow",
        "-crf", p["crf"], "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", p["audio"], "-ac", "2",
        "-movflags", "+faststart",
        "-map_metadata", "-1",  # из исходников не тащим таймкод и служебные дорожки
        str(dest),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        check=True, capture_output=True, text=True).stdout
    return float(out.strip())


def poster(video, slot, wide, at=None, ready=None):
    """Кадр из ролика в постер блока.

    В макете у трёх превью одного формата лежит одна и та же картинка — они
    склеились по md5. Как только появляется настоящий ролик, постер берём из
    него, иначе три разных клипа выглядят одинаково. Имя с суффиксом, чтобы не
    затереть общий файл: на него опираются блоки, где ролика ещё нет.

    Секунду можно задать руками: автоматический кадр иногда попадает на моргание
    или на смазанное движение, а постер — первое, что видит читатель. А если
    заглушку нарисовали отдельно — берём её файлом, кадр из ролика не нужен.
    """
    width = 1480 if wide else 640
    dest = IMG_DIR / f"{slot}-poster.webp"

    def save(path):
        im = Image.open(path).convert("RGB")
        if im.width != width:
            im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
        im.save(dest, "WEBP", quality=82, method=6)

    if ready:
        save(ready)
        return dest

    at = duration(video) / 3 if at is None else at  # первые кадры часто на затемнении
    # ffmpeg из brew собран без энкодера webp — снимаем кадр в png и жмём Pillow,
    # тем же путём, что и картинки из макета в fetch_images.py
    with tempfile.TemporaryDirectory() as tmp:
        frame = pathlib.Path(tmp) / "frame.png"
        subprocess.run(
            ["ffmpeg", "-y", "-ss", f"{at:.2f}", "-i", str(video), "-frames:v", "1",
             "-vf", f"scale={width}:-2:flags=lanczos", str(frame)],
            check=True, capture_output=True)
        save(frame)
    return dest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("slot")
    ap.add_argument("--wide", action="store_true")
    ap.add_argument("--poster-at", type=float, default=None,
                    metavar="СЕК", help="секунда, с которой снять постер")
    ap.add_argument("--poster-file", default=None, metavar="ФАЙЛ",
                    help="готовая заглушка вместо кадра из ролика")
    args = ap.parse_args()

    if not shutil.which("ffmpeg"):
        sys.exit("нужен ffmpeg: brew install ffmpeg")

    src = pathlib.Path(args.source)
    if not src.exists():
        sys.exit(f"нет файла: {src}")

    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    dest = VIDEO_DIR / f"{args.slot}.mp4"
    encode(src, dest, args.wide)
    shot = poster(dest, args.slot, args.wide, args.poster_at, args.poster_file)

    before = src.stat().st_size / 1024 / 1024
    after = dest.stat().st_size / 1024 / 1024
    print(f"{src.name}: {before:.1f} МБ → {dest.name}: {after:.1f} МБ, "
          f"постер {shot.name} ({shot.stat().st_size // 1024} КБ)")


if __name__ == "__main__":
    main()
