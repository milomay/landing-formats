#!/usr/bin/env python3
"""Готовит веб-версии шрифтов: исходники из fonts/ → woff2 в assets/fonts/.

Берём только начертания, которые реально встречаются в макете:
Graphik 400/500/600 и SangBleu Sunrise 400.
"""

import pathlib

from fontTools.ttLib import TTFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "fonts"
DEST = ROOT / "assets" / "fonts"

FACES = [
    ("Graphik Kinopoisk LC-Regular.otf", "graphik-400.woff2"),
    ("Graphik Kinopoisk LC-Medium.otf", "graphik-500.woff2"),
    ("Graphik Kinopoisk LC-Semibold.otf", "graphik-600.woff2"),
    ("SangBleuSunrise-Regular.otf", "sangbleu-400.woff2"),
]


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    total = 0
    for src_name, out_name in FACES:
        src = SRC / src_name
        if not src.exists():
            print(f"нет исходника: {src_name}")
            continue
        font = TTFont(src)
        font.flavor = "woff2"
        out = DEST / out_name
        font.save(out)
        size = out.stat().st_size
        total += size
        print(f"{out_name:22s} {size // 1024:4d} КБ  ← {src_name}")
    print(f"итого {total // 1024} КБ")


if __name__ == "__main__":
    main()
