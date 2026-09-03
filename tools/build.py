#!/usr/bin/env python3
"""Собирает HTML-страницы лендинга из .refs/content.json."""

import hashlib
import html
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTENT = ROOT / ".refs" / "content.json"
IMG_MAP_FILE = ROOT / "assets" / "img" / "map.json"
IMG_MAP = json.loads(IMG_MAP_FILE.read_text()) if IMG_MAP_FILE.exists() else {}

# ролики: файл assets/video/<id блока>.mp4 либо внешняя ссылка в links.json
VIDEO_DIR = ROOT / "assets" / "video"
VIDEO_LINKS_FILE = VIDEO_DIR / "links.json"
VIDEO_LINKS = json.loads(VIDEO_LINKS_FILE.read_text()) if VIDEO_LINKS_FILE.exists() else {}
VIDEO_EXT = (".mp4", ".webm")


def img_src(node_name):
    """Имя узла → путь к картинке с учётом склейки дубликатов.

    Кадр, снятый с настоящего ролика (`<id>-poster.webp`), главнее склейки:
    иначе три разных клипа делят одну картинку из макета. Отдельное имя нужно,
    чтобы не затирать общий файл — на него опираются соседние блоки.
    """
    if (ROOT / "assets" / "img" / f"{node_name}-poster.webp").exists():
        return f"assets/img/{node_name}-poster.webp"
    return f"assets/img/{IMG_MAP.get(node_name, node_name)}.webp"


_SIZES = {}


def img_size(src):
    """Атрибуты width/height файла — место под картинку резервируется до её
    загрузки: на медленной сети видна подложка нужного размера, а текст под
    ней не прыгает, когда файл наконец приезжает."""
    if src in _SIZES:
        return _SIZES[src]
    path = ROOT / src
    attrs = ""
    if path.exists():
        try:
            from PIL import Image

            with Image.open(path) as im:
                attrs = f' width="{im.width}" height="{im.height}"'
        except Exception:
            pass  # без размеров просто нет резерва места, сборку это не ломает
    _SIZES[src] = attrs
    return attrs


def video_src(block_id):
    """Ролик для блока: локальный файл в assets/video или ссылка из links.json.

    Нет ни того, ни другого — блок остаётся картинкой-постером, как сейчас.
    """
    url = VIDEO_LINKS.get(block_id)
    if url:
        return url
    for ext in VIDEO_EXT:
        if (VIDEO_DIR / f"{block_id}{ext}").exists():
            return asset_url(f"assets/video/{block_id}{ext}")
    return None


def asset_url(rel):
    """Путь к стилям/скрипту с версией по содержимому.

    GitHub Pages отдаёт css и js с долгим кешем, поэтому без версии правка
    может неделю не доезжать до тех, кто уже открывал сайт.
    """
    path = ROOT / rel
    if not path.exists():
        return rel
    digest = hashlib.md5(path.read_bytes()).hexdigest()[:8]
    return f"{rel}?v={digest}"

# какой пункт навигации подсвечен и в какой файл пишем
PAGES = {
    "preroll": {"file": "index.html", "nav": "Преролл"},
    "banner": {"file": "banner.html", "nav": "Баннеры"},
}
NAV_LINKS = {"Преролл": "index.html", "Баннеры": "banner.html"}

# логотип вставляется в разметку, а не картинкой: так он берёт currentColor
# и работает в обеих темах одним файлом
LOGO = (ROOT / "assets" / "img" / "logo-kinopoisk.svg").read_text().strip()


def esc(s):
    return html.escape(str(s), quote=False)


def slug(text, used):
    base = re.sub(r"[^a-zа-яё0-9]+", "-", str(text).lower()).strip("-")[:60] or "section"
    s, i = base, 2
    while s in used:
        s, i = f"{base}-{i}", i + 1
    used.add(s)
    return s


# короткие предлоги и союзы не оставляем висеть в конце строки: в узких
# колонках таблицы «до» отрывалось от «релиза». Привязываем неразрывным
# пробелом к следующему слову.
HANGING = re.compile(r"\b([а-яёa-z]{1,2}|для|под|при|над|без|про|или|как)\s+", re.IGNORECASE)


def tie_prepositions(text):
    return HANGING.sub(lambda m: m.group(1) + "\u00a0", text)


def render_text(value):
    """Текст блока: строка или список кусков (url, text) со ссылками."""
    if isinstance(value, str):
        return tie_prepositions(esc(value))
    out = []
    for part in value:
        url, chunk = part
        if url:
            out.append(
                f'<a href="{esc(url)}" target="_blank" rel="noopener">'
                f"{tie_prepositions(esc(chunk))}</a>"
            )
        else:
            out.append(tie_prepositions(esc(chunk)))
    return "".join(out)


def render_table(rows):
    head, body = [], []
    for row in rows:
        cells = row["cells"]
        if row["kind"] == "header":
            head.append("<tr>" + "".join(f"<th>{render_text(c)}</th>" for c in cells) + "</tr>")
            continue
        tds = []
        for c in cells:
            if isinstance(c, dict):  # список пунктов внутри ячейки
                items = "".join(f"<li>{render_text(i)}</li>" for i in c["items"])
                tds.append(f"<td><ul>{items}</ul></td>")
            else:
                tds.append(f"<td>{render_text(c)}</td>")
        body.append("<tr>" + "".join(tds) + "</tr>")
    thead = f"<thead>{''.join(head)}</thead>" if head else ""
    cols = max((len(r["cells"]) for r in rows), default=2)
    # обёртка нужна, чтобы широкая таблица скроллилась сама, а не растягивала страницу
    return (f'<div class="table-wrap"><table class="spec-table spec-table--{min(cols, 4)}">'
            f'{thead}<tbody>{"".join(body)}</tbody></table></div>')


_HERO = {"used": False}


def img_tag(src, alt=""):
    """Тег картинки с подложкой и зарезервированным размером.

    Ленивой загрузки нет намеренно: всех картинок сайта на 740 КБ, зато с
    `loading="lazy"` они запрашиваются после раскладки и при каждом обновлении
    страницы на их месте моргает подложка. Первой добавляем приоритет и
    синхронное декодирование — она в первом экране и должна прийти с версткой.
    """
    mode = ""
    if not _HERO["used"]:
        _HERO["used"] = True
        mode = ' fetchpriority="high" decoding="sync"'
    return f'<img class="media" src="{src}" alt="{alt}"{mode}{img_size(src)}>'


def render_video(block):
    cls = "video video--wide" if block.get("wide") else "video"
    cap = f'<figcaption>{esc(block["caption"])}</figcaption>' if block.get("caption") else ""
    src = video_src(block["img"])
    src_img = img_src(block["img"])
    if src:
        # В плитке лежит только постер: ролик открывается крупно в оверлее,
        # смотреть его в колонке 229 px смысла нет. Кликабельна вся карточка.
        return (f'<figure class="{cls}">'
                f'<button class="video__open" type="button" data-video-open '
                f'data-src="{esc(src)}" aria-label="Смотреть ролик">'
                f'{img_tag(src_img)}'
                f'<span class="video__play" aria-hidden="true"></span>'
                f'</button>{cap}</figure>')
    alt = esc(block.get("caption") or "Превью видео")
    return (f'<figure class="{cls}">{img_tag(src_img, alt)}'
            f'<span class="video__play" aria-hidden="true"></span>{cap}</figure>')


def render_blocks(blocks):
    """Блоки секции в HTML. Подряд идущие video собираются в ряд."""
    out, i = [], 0
    while i < len(blocks):
        b = blocks[i]
        t = b["type"]

        if t == "video" and not b.get("wide"):
            group = []
            while i < len(blocks) and blocks[i]["type"] == "video" and not blocks[i].get("wide"):
                group.append(blocks[i])
                i += 1
            # плитки без ролика не показываем, но обёртку-ряд оставляем всегда:
            # сетка из трёх колонок держит ширину, иначе оставшийся ролик
            # растянулся бы на всю ширину контента
            shown = [v for v in group if video_src(v["img"])]
            if not shown:
                continue
            inner = "".join(render_video(v) for v in shown)
            out.append(f'<div class="video-row">{inner}</div>' if len(group) > 1 else inner)
            continue

        if t == "video":
            out.append(render_video(b))
        elif t == "p":
            # внутри разделов абзацы обычные: в макете подзаголовочная строка
            # набрана тем же Regular, что и остальной текст. Лид — только один,
            # под заголовком страницы, он ставится в шаблоне.
            out.append(f"<p>{render_text(b['text'])}</p>")
        elif t == "h3":
            out.append(f"<h3>{esc(b['text'])}</h3>")
        elif t == "ul":
            items = "".join(f"<li>{render_text(x)}</li>" for x in b["items"])
            out.append(f"<ul>{items}</ul>")
        elif t == "checklist":
            items = "".join(f"<li>{render_text(x)}</li>" for x in b["items"])
            out.append(
                '<div class="checklist">'
                '<button class="checklist__copy" type="button" data-copy-checklist '
                'aria-label="Скопировать чек-лист">'
                '<svg viewBox="0 0 20 20" aria-hidden="true">'
                '<rect x="7.25" y="7.25" width="9.5" height="9.5" rx="2.5"/>'
                '<path d="M12.75 4.75A1.5 1.5 0 0 0 11.25 3.25h-6.5a1.5 1.5 0 0 0-1.5 1.5v6.5'
                'a1.5 1.5 0 0 0 1.5 1.5"/>'
                "</svg></button>"
                f'<ul class="checklist__list">{items}</ul>'
                "</div>")
        elif t == "table":
            out.append(render_table(b["rows"]))
        elif t == "note":
            title = f'<p class="note__title">{esc(b["title"])}</p>' if b.get("title") else ""
            out.append(f'<aside class="note">{title}<p>{render_text(b["text"])}</p></aside>')
        elif t == "checkbox":
            out.append(f'<ul><li>{esc(b["text"])}</li></ul>')
        elif t == "figure":
            cap = f'<figcaption>{esc(b["caption"])}</figcaption>' if b.get("caption") else ""
            out.append(f'<figure>{img_tag(img_src(b["img"]))}{cap}</figure>')
        elif t == "bento":
            cards = "".join(
                f'<div class="bento__card"><p class="bento__title">{esc(c["title"])}</p>'
                f'<p class="bento__body">{esc(c["body"])}</p></div>'
                for c in b["cards"])
            out.append(f'<div class="bento">{cards}</div>')
        elif t == "hr":
            out.append('<hr class="divider">')
        i += 1
    return "\n        ".join(out)


def render_nav(groups, current):
    parts = []
    for g in groups:
        # первый пункт группы дублирует её название — в макете это и есть
        # заголовок группы с шевроном, отдельной строкой он не повторяется
        items = list(g["items"])
        if items and items[0] == g["title"]:
            items = items[1:]

        rows = []
        for item in items:
            href = NAV_LINKS.get(item)
            cur = ' aria-current="page"' if item == current else ""
            if href:
                rows.append(f'<li><a href="{href}"{cur}>{esc(item)}</a></li>')
            else:
                rows.append(f'<li><a href="#" aria-disabled="true">{esc(item)}</a></li>')
        # шеврон в макете не декорация: группа сворачивается и разворачивается
        gid = "nav-" + slug(g["title"], set())
        parts.append(
            f'<div class="nav-group">'
            f'<button class="nav-group__title" type="button" data-nav-group'
            f' aria-expanded="true" aria-controls="{gid}">{esc(g["title"])}</button>'
            f'<div class="nav-group__body" id="{gid}">'
            f'<ul class="nav-list">{"".join(rows)}</ul></div></div>')
    return "\n          ".join(parts)


def render_page(page):
    meta = PAGES[page["slug"]]
    used = set()
    _HERO["used"] = False  # первая картинка считается заново на каждой странице
    intro = page["intro"] or {"breadcrumbs": [], "title": page["title"], "lead": "", "blocks": []}

    # интро собираем до глав: порядок вызовов задаёт, какая картинка на
    # странице первая, а первая грузится не лениво
    intro_html = render_blocks(intro["blocks"])

    body, toc = [], []

    def drop_trailing_divider():
        """Линию снимаем там, где разделять уже нечего: перед заголовком главы
        (новый смысловой блок отбит антиквой) и в самом низу страницы."""
        if body and body[-1].endswith('<hr class="divider">'):
            body[-1] = body[-1][: -len('\n      <hr class="divider">')]

    for chapter in page["chapters"]:
        drop_trailing_divider()
        body.append(f'<h2 class="chapter__title">{esc(chapter["title"])}</h2>')
        for section in chapter["sections"]:
            sid = slug(section["title"], used)
            toc.append(f'<li><a href="#{sid}">{esc(section["title"])}</a></li>')
            body.append(
                f'<section class="section" id="{sid}">\n'
                f'        <h2><a class="anchor" href="#{sid}">{esc(section["title"])}'
                f'<span class="anchor__icon" aria-hidden="true"></span></a></h2>\n'
                f'        {render_blocks(section["blocks"])}\n'
                f'      </section>\n'
                f'      <hr class="divider">')

    drop_trailing_divider()

    crumbs = "".join(f"<span>{esc(c)}</span>" for c in intro["breadcrumbs"])
    description = (intro["lead"] or "")[:160]

    return f"""<!DOCTYPE html>
<html lang="ru" data-theme="dark">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <script>
    // по умолчанию тёмная — системную настройку намеренно не слушаем.
    // Ставим до первой отрисовки, иначе у выбравших светлую мигает тёмный фон.
    (function () {{
      var saved = null;
      try {{ saved = localStorage.getItem('theme'); }} catch (e) {{}}
      document.documentElement.dataset.theme = saved === 'light' ? 'light' : 'dark';
    }})();
  </script>
  <title>{esc(intro["title"])} — Лендинг форматов</title>
  <meta name="description" content="{esc(description)}">
  <meta name="theme-color" content="#0d0d0d" media="(prefers-color-scheme: dark)">
  <meta name="theme-color" content="#ffffff" media="(prefers-color-scheme: light)">
  <meta property="og:title" content="{esc(intro["title"])} — гайд по формату">
  <meta property="og:description" content="{esc(description)}">
  <meta property="og:type" content="article">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&amp;family=Playfair+Display:wght@400&amp;display=swap">
  <link rel="stylesheet" href="{asset_url("assets/css/style.css")}">
</head>
<body>
  <div class="layout">
    <aside class="sidebar" id="sidebar">
      <a class="brand" href="index.html" aria-label="Форматы Кинопоиска">{LOGO}</a>
      <button class="nav-toggle" type="button" data-nav-toggle>Разделы</button>
      <div class="nav-groups">
          {render_nav(page["nav"], meta["nav"])}
          <button class="theme-switch" type="button" data-theme-toggle
                  role="switch" aria-checked="false" aria-label="Светлая тема">
            <span class="theme-switch__track" aria-hidden="true">
              <span class="theme-switch__knob">
                <svg data-icon="dark" viewBox="0 0 16 16">
                  <path d="M13.5 9.6A5.8 5.8 0 0 1 6.4 2.5a5.8 5.8 0 1 0 7.1 7.1z"/>
                </svg>
                <svg data-icon="light" viewBox="0 0 16 16">
                  <circle cx="8" cy="8" r="3.2"/>
                  <path d="M8 1v1.6M8 13.4V15M15 8h-1.6M2.6 8H1M12.9 3.1l-1.1 1.1M4.2 11.8l-1.1 1.1M12.9 12.9l-1.1-1.1M4.2 4.2 3.1 3.1"/>
                </svg>
              </span>
            </span>
          </button>
      </div>
    </aside>

    <main class="main">
      <nav class="breadcrumbs">{crumbs}</nav>
      <h1 class="page-title">{esc(intro["title"])}</h1>
      <p class="lead">{esc(intro["lead"])}</p>
      {intro_html}

      {"".join(body)}
    </main>

    <aside class="toc" aria-label="Содержание">
      <ol>
        {"".join(toc)}
      </ol>
    </aside>
  </div>
  <script src="{asset_url("assets/js/app.js")}"></script>
</body>
</html>
"""


def main():
    data = json.loads(CONTENT.read_text())
    for page in data["pages"]:
        if page["slug"] not in PAGES:
            continue
        dest = ROOT / PAGES[page["slug"]]["file"]
        dest.write_text(render_page(page))
        print(f"собрано: {dest.name} ({dest.stat().st_size // 1024} КБ)")


if __name__ == "__main__":
    main()
