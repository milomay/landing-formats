#!/usr/bin/env python3
"""Следит, чтобы в палитре не заводились неразличимые оттенки.

    python3 tools/palette.py          # таблица токенов и предупреждения

Считает, во что каждый токен превращается на своём фоне (полупрозрачные
складываются с подложкой), и сравнивает соседей внутри одной роли и одного
контекста. Если два токена расходятся меньше чем на `LIMIT` из 255, глаз их
не различит — значит один лишний.

Сравниваем не записанные значения, а отрисованные: 9% на карточке и 15% на
фоне страницы дают почти один и тот же серый, хотя в CSS выглядят по-разному.
build.py зовёт `check()` на каждой сборке, чтобы дубль не доехал до сайта.
"""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CSS = ROOT / "assets" / "css" / "style.css"

# ближе этого порога два тона на глаз не отличаются
LIMIT = 3

# на чём лежит токен: page — фон страницы, card — карточка или плашка.
# Всё, чего здесь нет, лежит поверх видео или вне темы и не сравнивается.
CONTEXT = {
    "--surface-card": "page",
    "--surface-card-hover": "page",
    "--border": "page",
    "--border-soft": "page",
    "--border-media": "page",
    "--border-button": "card",
}
FAMILY = {"--surface-card": "заливка", "--surface-card-hover": "заливка"}


def parse(block):
    """Токен → (цвет по трём каналам, альфа).

    Каналы держим все три: фон страницы тёплый, и на нём нейтральный серый
    и «10% белого» дают разные цвета, хотя по яркости совпадают.
    """
    out = {}
    for name, value in re.findall(r"(--[a-z-]+):\s*([^;]+);", block):
        v = value.strip()
        m = re.fullmatch(r"rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)", v)
        if m:
            out[name] = ((int(m[1]), int(m[2]), int(m[3])), float(m[4]))
            continue
        m = re.fullmatch(r"#([0-9a-fA-F]{6})", v)
        if m:
            rgb = tuple(int(m[1][i:i + 2], 16) for i in (0, 2, 4))
            out[name] = (rgb, 1.0)
    return out


def themes():
    css = CSS.read_text(encoding="utf-8")
    dark = re.search(r":root,\s*\[data-theme=\"dark\"\]\s*\{(.*?)\n\}", css, re.S)
    light = re.search(r"\[data-theme=\"light\"\]\s*\{(.*?)\n\}", css, re.S)
    return {"тёмная": parse(dark[1]), "светлая": parse(light[1])}


def blend(rgb, alpha, bg):
    return tuple(round(b + (c - b) * alpha) for c, b in zip(rgb, bg))


def hexed(rgb):
    return "#" + "".join(f"{c:02x}" for c in rgb)


def check(verbose=False):
    problems = []
    for theme, tokens in themes().items():
        page = tokens["--surface"][0]
        card = blend(*tokens["--surface-card"], page)
        base = {"page": page, "card": card}

        shown = {}
        for name, (rgb, alpha) in sorted(tokens.items()):
            ctx = CONTEXT.get(name)
            if not ctx:
                continue
            shown[name] = (blend(rgb, alpha, base[ctx]), ctx)

        if verbose:
            print(f"=== {theme} (фон {hexed(page)}, карточка {hexed(card)})")
            for name, (value, ctx) in sorted(shown.items(), key=lambda x: sum(x[1][0])):
                print(f"  {name:22} на {ctx:5} -> {hexed(value)}")

        names = list(shown)
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                va, ca = shown[a]
                vb, cb = shown[b]
                if ca != cb or FAMILY.get(a, "линия") != FAMILY.get(b, "линия"):
                    continue
                if max(abs(x - y) for x, y in zip(va, vb)) < LIMIT:
                    problems.append(f"{theme}: {a} ({hexed(va)}) и {b} ({hexed(vb)}) неразличимы")
    return problems


if __name__ == "__main__":
    found = check(verbose=True)
    if found:
        print("\nблизкие оттенки:")
        for p in found:
            print("  " + p)
        sys.exit(1)
    print("\nблизких оттенков нет")
