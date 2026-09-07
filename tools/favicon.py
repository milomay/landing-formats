#!/usr/bin/env python3
"""Растровые иконки сайта из assets/img/favicon.svg.

SVG-иконку понимают все актуальные браузеры, но не понимают старые и не
понимают iOS при добавлении на домашний экран. Поэтому рядом с вектором
лежат две сборки, и обе делаются отсюда, а не руками:

  favicon.ico          16/32/48 — запасной вариант для старых браузеров;
  apple-touch-icon.png 180×180 — плитка на домашнем экране iOS.

Плитка для iOS без скругления и без прозрачности: система накладывает свою
маску, и наши скруглённые углы дали бы вокруг иконки светлую кайму.

Запуск: python3 tools/favicon.py
"""

import pathlib
import subprocess
import sys

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "img" / "favicon.svg"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

ICO_SIZES = (16, 32, 48)
TOUCH_SIZE = 180


def render(svg, size, square):
    """Кадр size×size из SVG. square — залить углы вместо скругления."""
    page = ROOT / "_favicon-render.html"
    # SVG растягиваем ровно на окно, фон страницы прозрачный: скруглённые
    # углы должны остаться пустыми, иначе кайма
    corners = (
        '<style>svg rect:first-of-type{rx:0}</style>' if square else ""
    )
    page.write_text(
        '<body style="margin:0">'
        f'<div style="width:{size}px;height:{size}px">'
        + svg.replace("<svg", '<svg style="width:100%;height:100%"', 1)
        + "</div>" + corners + "</body>"
    )
    out = ROOT / "_favicon-render.png"
    try:
        subprocess.run(
            [CHROME, "--headless", "--disable-gpu", "--virtual-time-budget=2000",
             f"--window-size={size},{size}", "--default-background-color=00000000",
             f"--screenshot={out}", "file://" + str(page)],
            capture_output=True, check=True,
        )
        return Image.open(out).convert("RGBA").copy()
    finally:
        page.unlink(missing_ok=True)
        out.unlink(missing_ok=True)


def main():
    if not SRC.exists():
        sys.exit(f"нет исходника: {SRC}")
    if not pathlib.Path(CHROME).exists():
        sys.exit("нужен Chrome — растр снимается им же, чем и проверки вёрстки")
    svg = SRC.read_text()

    frames = [render(svg, s, square=False) for s in ICO_SIZES]
    ico = ROOT / "assets" / "img" / "favicon.ico"
    frames[-1].save(ico, format="ICO",
                    sizes=[(s, s) for s in ICO_SIZES])
    print(f"собрано: {ico.relative_to(ROOT)} ({', '.join(str(s) for s in ICO_SIZES)})")

    touch = render(svg, TOUCH_SIZE, square=True)
    # прозрачность iOS не поддерживает и подкладывает чёрное — кладём фон сами
    flat = Image.new("RGB", touch.size, "#FF5500")
    flat.paste(touch, mask=touch.split()[3])
    png = ROOT / "assets" / "img" / "apple-touch-icon.png"
    flat.save(png, format="PNG")
    print(f"собрано: {png.relative_to(ROOT)} ({TOUCH_SIZE}×{TOUCH_SIZE})")


if __name__ == "__main__":
    main()
