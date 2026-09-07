#!/usr/bin/env python3
"""Следит, чтобы оглавление не дёргалось при загрузке.

    python3 tools/toc.py

Оглавление стоит в правой колонке и должно начинаться ровно от верха лида.
Отбивку задаёт число в CSS, а скрипт на странице уточняет её по фактическому
положению лида — на случай, если заголовок перенесётся на вторую строку.

Пока число в CSS верное, скрипт пересчитывает то же самое и ничего не двигает.
Стоит числу отстать от вёрстки — например, поменялась верхняя отбивка текста, —
и при каждой загрузке колонка прыгает на разницу: сперва рисуется по CSS, потом
её сдвигает скрипт. Глазами это ловится плохо, числом — сразу.

Считаем на собранных страницах: сбрасываем то, что проставил скрипт, и
сравниваем чистый CSS с тем, что нужно вёрстке.
"""

import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PAGES = ("index.html", "banner.html")
# ширины, на которых оглавление вообще показано (ниже 1200 оно скрыто)
WIDTHS = (1280, 1440, 1920)

PROBE = """<script>
  const toc = document.querySelector('.toc'), lead = document.querySelector('.lead');
  toc.style.marginTop = '';
  document.title = JSON.stringify({
    css: Math.round(parseFloat(getComputedStyle(toc).marginTop)),
    need: Math.round(lead.getBoundingClientRect().top
                     - toc.parentElement.getBoundingClientRect().top)
  });
</script></body>"""


def measure(page, width):
    html = (ROOT / page).read_text(encoding="utf-8").replace("</body>", PROBE)
    tmp = ROOT / "_toc-probe.html"
    tmp.write_text(html, encoding="utf-8")
    try:
        dom = subprocess.run(
            [CHROME, "--headless", "--disable-gpu", "--virtual-time-budget=6000",
             f"--window-size={width},900", "--dump-dom", "file://" + str(tmp)],
            capture_output=True, text=True, check=True).stdout
    finally:
        tmp.unlink(missing_ok=True)
    found = re.search(r"<title>(.*?)</title>", dom, re.S)
    if not found:
        return None
    return json.loads(found[1])


def main():
    if not pathlib.Path(CHROME).exists():
        sys.exit("нужен Chrome — замер снимается им же, чем и остальные проверки")
    problems = []
    for page in PAGES:
        for width in WIDTHS:
            got = measure(page, width)
            if got is None:
                print(f"  {page} @{width}: страница не отдала замеры")
                continue
            mark = "проверено" if got["css"] == got["need"] else "РАСХОЖДЕНИЕ"
            print(f"  {page} @{width}: CSS {got['css']}, нужно {got['need']} — {mark}")
            if got["css"] != got["need"]:
                problems.append(
                    f"{page} @{width}: колонка прыгнет на {got['need'] - got['css']}px")
    if problems:
        print("\nоглавление дёргается при загрузке:")
        for p in problems:
            print("  " + p)
        sys.exit(1)
    print("\nоглавление стоит на месте")


if __name__ == "__main__":
    main()
