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
    out = {}
    for name, value in re.findall(r"(--[a-z-]+):\s*([^;]+);", block):
        v = value.strip()
        m = re.fullmatch(r"rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)", v)
        if m:
            out[name] = (int(m[1]), float(m[4]))
            continue
        m = re.fullmatch(r"#([0-9a-fA-F]{6})", v)
        if m:
            out[name] = (int(m[1][:2], 16), 1.0)
    return out


def themes():
    css = CSS.read_text(encoding="utf-8")
    dark = re.search(r":root,\s*\[data-theme=\"dark\"\]\s*\{(.*?)\n\}", css, re.S)
    light = re.search(r"\[data-theme=\"light\"\]\s*\{(.*?)\n\}", css, re.S)
    return {"тёмная": parse(dark[1]), "светлая": parse(light[1])}


def check(verbose=False):
    problems = []
    for theme, tokens in themes().items():
        page = tokens["--surface"][0]
        card = round(page + (tokens["--surface-card"][0] - page) * tokens["--surface-card"][1])
        base = {"page": page, "card": card}

        shown = {}
        for name, (channel, alpha) in sorted(tokens.items()):
            ctx = CONTEXT.get(name)
            if not ctx:
                continue
            bg = base[ctx]
            shown[name] = (round(bg + (channel - bg) * alpha), ctx)

        if verbose:
            print(f"=== {theme} (фон {page}, карточка {card})")
            for name, (value, ctx) in sorted(shown.items(), key=lambda x: x[1][0]):
                print(f"  {name:22} на {ctx:5} -> {value}")

        names = list(shown)
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                va, ca = shown[a]
                vb, cb = shown[b]
                if ca != cb or FAMILY.get(a, "линия") != FAMILY.get(b, "линия"):
                    continue
                if abs(va - vb) < LIMIT:
                    problems.append(f"{theme}: {a} ({va}) и {b} ({vb}) неразличимы")
    return problems


if __name__ == "__main__":
    found = check(verbose=True)
    if found:
        print("\nблизкие оттенки:")
        for p in found:
            print("  " + p)
        sys.exit(1)
    print("\nблизких оттенков нет")
