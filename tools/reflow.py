#!/usr/bin/env python3
"""Следит, чтобы смена состояния не двигала вёрстку.

    python3 tools/reflow.py

Наводишь мышь, переключаешься по меню — коробка элемента меняться не должна.
Иначе список под ним прыгает: так было в оглавлении, где активный пункт был
Medium, и «Как выбрать формат преролла» переставал помещаться в строку —
пункт рос с 35 до 55 при каждой прокрутке мимо этого раздела.

Проверяем не глазами: открываем страницы в headless Chrome, вешаем и снимаем
состояние на каждый пункт и сравниваем размеры коробки до и после. Ховер сюда
не входит — в headless он не воспроизводится (см. правило про непроверяемые
состояния), поэтому правила ховера пишем так, чтобы они меняли только цвет.
"""

import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAGES = ("index.html", "banner.html")
WIDTHS = (1800, 1300, 1000)
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# состояния, которые ставятся классом или атрибутом и не должны менять размеры
STATES = [
    ("оглавление", ".toc a", "class", "is-active"),
    ("меню", ".nav-list a", "attr", "aria-current"),
]

PROBE = """
<script>
window.addEventListener('load', function(){
  var STATES = %s;
  var bad = [];
  STATES.forEach(function(s){
    var name = s[0], sel = s[1], kind = s[2], key = s[3];
    var items = [].slice.call(document.querySelectorAll(sel));
    var had = items.filter(function(e){
      return kind === 'class' ? e.classList.contains(key) : e.hasAttribute(key);
    });
    function on(e){ kind === 'class' ? e.classList.add(key) : e.setAttribute(key, 'page'); }
    function off(e){ kind === 'class' ? e.classList.remove(key) : e.removeAttribute(key); }
    items.forEach(function(e){
      off(e);
      var a = e.getBoundingClientRect();
      on(e);
      var b = e.getBoundingClientRect();
      off(e);
      if (Math.round(a.height) !== Math.round(b.height) ||
          Math.round(a.width) !== Math.round(b.width)) {
        bad.push(name + ' «' + e.textContent.trim().slice(0, 34) + '» ' +
          Math.round(a.width) + 'x' + Math.round(a.height) + ' -> ' +
          Math.round(b.width) + 'x' + Math.round(b.height));
      }
    });
    had.forEach(on);
  });
  document.title = 'RESULT' + JSON.stringify(bad);
});
</script>
"""


def check(verbose=False):
    if not pathlib.Path(CHROME).exists():
        print("нет Chrome — проверку пропускаю")
        return []

    probe = PROBE % json.dumps(STATES, ensure_ascii=False)
    problems = []
    # копию кладём рядом с оригиналом, а не в подпапку: пути к стилям в разметке
    # относительные, и на уровень глубже страница грузится вообще без CSS —
    # тогда проверка «ничего не сдвинулось» проходит всегда и ничего не значит
    copies = []
    try:
        for page in PAGES:
            src = ROOT / page
            if not src.exists():
                continue
            copy = ROOT / f"_reflow-{page}"
            copies.append(copy)
            copy.write_text(
                src.read_text(encoding="utf-8").replace("</body>", probe + "</body>"),
                encoding="utf-8")
            for width in WIDTHS:
                out = subprocess.run(
                    [CHROME, "--headless", "--disable-gpu", f"--window-size={width},900",
                     "--virtual-time-budget=3000", "--dump-dom", copy.as_uri()],
                    capture_output=True, text=True).stdout
                m = re.search(r"<title>RESULT(.*?)</title>", out, re.S)
                if not m:
                    problems.append(f"{page} @{width}: страница не отдала замеры")
                    continue
                for bad in json.loads(m[1]):
                    problems.append(f"{page} @{width}: {bad}")
                if verbose:
                    print(f"  {page} @{width}: проверено")
    finally:
        for copy in copies:
            copy.unlink(missing_ok=True)
    return problems


if __name__ == "__main__":
    found = check(verbose=True)
    if found:
        print("\nсостояние двигает вёрстку:")
        for p in found:
            print("  " + p)
        sys.exit(1)
    print("\nсостояние вёрстку не двигает")
