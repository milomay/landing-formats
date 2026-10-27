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
BUDGET_MS = 3000
# Один повтор — страховка от холодного старта Chrome, не лечение. Когда проба
# висела на requestAnimationFrame (см. PROBE), повтор лишь уменьшал долю
# промахов и маскировал причину; сейчас замер доезжает с первого раза.
ATTEMPTS = 2

# состояния, которые ставятся классом или атрибутом и не должны менять размеры
STATES = [
    ("оглавление", ".toc a", "class", "is-active"),
    ("меню", ".nav-list a", "attr", "aria-current"),
]

PROBE = """
<script>
// Ждём шрифт: скрипт страницы по этому же событию расставляет переносы в
// оглавлении. Померить раньше — значит померить не то, что увидит читатель,
// и пропустить настоящий скачок (или найти несуществующий).
//
// Дальше — таймер, а не requestAnimationFrame. Колбэк кадра вызывается только
// когда страница этот кадр рисует, а под `--dump-dom` Chrome часто не рисует
// ничего: замер показал, что rAF доезжает три раза из восьми, и сторож на
// ровном месте объявлял вёрстку сломанной. Таймер под виртуальным временем
// срабатывает всегда и, как макрозадача, всё равно встаёт после обработчика
// самой страницы.
document.fonts.ready.then(function(){ setTimeout(function(){
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
}, 50); });
</script>
"""


def measure(copy, width):
    """Замеры одной страницы на одной ширине. None — проба не доехала."""
    for _ in range(ATTEMPTS):
        out = subprocess.run(
            [CHROME, "--headless", "--disable-gpu", f"--window-size={width},900",
             f"--virtual-time-budget={BUDGET_MS}", "--dump-dom", copy.as_uri()],
            capture_output=True, text=True).stdout
        found = re.search(r"<title>RESULT(.*?)</title>", out, re.S)
        if found:
            return json.loads(found[1])
    return None


def check(verbose=False):
    if not pathlib.Path(CHROME).exists():
        print("нет Chrome — проверку пропускаю")
        return [], []

    probe = PROBE % json.dumps(STATES, ensure_ascii=False)
    problems = []
    # Замер, который не доехал, держим отдельно от находок: он ничего не
    # доказывает ни в одну сторону, а в общем списке читался приговором
    # «состояние двигает вёрстку», хотя сторож никакого прыжка не видел.
    missed = []
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
                bad_list = measure(copy, width)
                if bad_list is None:
                    missed.append(f"{page} @{width}")
                    if verbose:
                        print(f"  {page} @{width}: замер не доехал")
                    continue
                for bad in bad_list:
                    problems.append(f"{page} @{width}: {bad}")
                if verbose:
                    print(f"  {page} @{width}: проверено")
    finally:
        for copy in copies:
            copy.unlink(missing_ok=True)
    return problems, missed


if __name__ == "__main__":
    found, missed = check(verbose=True)
    if found:
        print("\nсостояние двигает вёрстку:")
        for p in found:
            print("  " + p)
        sys.exit(1)
    if missed:
        # Не приговор вёрстке, но и не «всё хорошо»: часть страниц осталась
        # непроверенной, и сказать об этом надо прямо.
        print("\nвёрстку не двигает там, где удалось померить;"
              f" не померили: {', '.join(missed)}")
        sys.exit(2)
    print("\nсостояние вёрстку не двигает")
