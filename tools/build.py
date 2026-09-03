#!/usr/bin/env python3
"""Собирает HTML-страницы лендинга из .refs/content.json."""

import html
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTENT = ROOT / ".refs" / "content.json"
IMG_MAP_FILE = ROOT / "assets" / "img" / "map.json"
IMG_MAP = json.loads(IMG_MAP_FILE.read_text()) if IMG_MAP_FILE.exists() else {}


def img_src(node_name):
    """Имя узла → путь к картинке с учётом склейки дубликатов."""
    return f"assets/img/{IMG_MAP.get(node_name, node_name)}.webp"

# какой пункт навигации подсвечен и в какой файл пишем
PAGES = {
    "preroll": {"file": "index.html", "nav": "Преролл"},
    "banner": {"file": "banner.html", "nav": "Баннеры"},
}
NAV_LINKS = {"Преролл": "index.html", "Баннеры": "banner.html"}


def esc(s):
    return html.escape(str(s), quote=False)


def slug(text, used):
    base = re.sub(r"[^a-zа-яё0-9]+", "-", str(text).lower()).strip("-")[:60] or "section"
    s, i = base, 2
    while s in used:
        s, i = f"{base}-{i}", i + 1
    used.add(s)
    return s


def render_text(value):
    """Текст блока: строка или список кусков (url, text) со ссылками."""
    if isinstance(value, str):
        return esc(value)
    out = []
    for part in value:
        url, chunk = part
        if url:
            out.append(f'<a href="{esc(url)}" target="_blank" rel="noopener">{esc(chunk)}</a>')
        else:
            out.append(esc(chunk))
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


def render_video(block):
    cls = "video video--wide" if block.get("wide") else "video"
    cap = f'<figcaption>{esc(block["caption"])}</figcaption>' if block.get("caption") else ""
    return (f'<figure class="{cls}"><img src="{img_src(block["img"])}" '
            f'alt="{esc(block.get("caption") or "Превью видео")}" loading="lazy">'
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
            inner = "".join(render_video(v) for v in group)
            out.append(f'<div class="video-row">{inner}</div>' if len(group) > 1 else inner)
            continue

        if t == "video":
            out.append(render_video(b))
        elif t == "p":
            cls = ' class="lead"' if b.get("lead") else ""
            out.append(f"<p{cls}>{render_text(b['text'])}</p>")
        elif t == "h3":
            out.append(f"<h3>{esc(b['text'])}</h3>")
        elif t == "ul":
            items = "".join(f"<li>{render_text(x)}</li>" for x in b["items"])
            out.append(f"<ul>{items}</ul>")
        elif t == "table":
            out.append(render_table(b["rows"]))
        elif t == "note":
            title = f'<p class="note__title">{esc(b["title"])}</p>' if b.get("title") else ""
            out.append(f'<aside class="note">{title}<p>{render_text(b["text"])}</p></aside>')
        elif t == "checkbox":
            out.append(f'<ul><li>{esc(b["text"])}</li></ul>')
        elif t == "figure":
            cap = f'<figcaption>{esc(b["caption"])}</figcaption>' if b.get("caption") else ""
            out.append(f'<figure><img src="{img_src(b["img"])}" alt="" '
                       f'loading="lazy">{cap}</figure>')
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
        items = []
        for item in g["items"]:
            href = NAV_LINKS.get(item)
            cur = ' aria-current="page"' if item == current else ""
            if href:
                items.append(f'<li><a href="{href}"{cur}>{esc(item)}</a></li>')
            else:
                items.append(f'<li><a href="#" aria-disabled="true">{esc(item)}</a></li>')
        parts.append(
            f'<div class="nav-group"><p class="nav-group__title">{esc(g["title"])}</p>'
            f'<ul class="nav-list">{"".join(items)}</ul></div>')
    return "\n          ".join(parts)


def render_page(page):
    meta = PAGES[page["slug"]]
    used = set()
    intro = page["intro"] or {"breadcrumbs": [], "title": page["title"], "lead": "", "blocks": []}

    body, toc = [], []
    for chapter in page["chapters"]:
        body.append(f'<h2 class="chapter__title">{esc(chapter["title"])}</h2>')
        for section in chapter["sections"]:
            sid = slug(section["title"], used)
            toc.append(f'<li><a href="#{sid}">{esc(section["title"])}</a></li>')
            body.append(
                f'<section class="section" id="{sid}">\n'
                f'        <h2>{esc(section["title"])}</h2>\n'
                f'        {render_blocks(section["blocks"])}\n'
                f'      </section>\n'
                f'      <hr class="divider">')

    crumbs = "".join(f"<span>{esc(c)}</span>" for c in intro["breadcrumbs"])
    description = (intro["lead"] or "")[:160]

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(intro["title"])} — Лендинг форматов</title>
  <meta name="description" content="{esc(description)}">
  <meta property="og:title" content="{esc(intro["title"])} — гайд по формату">
  <meta property="og:description" content="{esc(description)}">
  <meta property="og:type" content="article">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&amp;family=Playfair+Display:wght@400&amp;display=swap">
  <link rel="stylesheet" href="assets/css/style.css">
</head>
<body>
  <div class="layout">
    <aside class="sidebar" id="sidebar">
      <a class="brand" href="index.html">Форматы Кинопоиска</a>
      <button class="nav-toggle" type="button" data-nav-toggle>Разделы</button>
      <div class="nav-groups">
          {render_nav(page["nav"], meta["nav"])}
      </div>
    </aside>

    <main class="main">
      <nav class="breadcrumbs">{crumbs}</nav>
      <h1 class="page-title">{esc(intro["title"])}</h1>
      <p class="lead">{esc(intro["lead"])}</p>
      {render_blocks(intro["blocks"])}

      {"".join(body)}
    </main>

    <aside class="toc">
      <p class="toc__title">Содержание</p>
      <ol>
        {"".join(toc)}
      </ol>
    </aside>
  </div>
  <script src="assets/js/app.js"></script>
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
