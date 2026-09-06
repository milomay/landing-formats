#!/usr/bin/env python3
"""Собирает HTML-страницы лендинга из .refs/content.json."""

import hashlib
import html
import json
import pathlib
import re

import palette

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
    path = ROOT / src.split("?")[0]
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

# Ссылку на макет ещё не дали. Пока её нет, кнопка рисуется, но не кликается —
# мёртвая ссылка на «#» хуже: она прокручивает страницу наверх.
# Появится адрес — вписать сюда, разметка сама станет ссылкой.
FIGMA_LINKS = {"preroll": "", "banner": ""}


def esc(s):
    return html.escape(str(s), quote=False)


def slug(text, used):
    base = re.sub(r"[^a-zа-яё0-9]+", "-", str(text).lower()).strip("-")[:60] or "section"
    s, i = base, 2
    while s in used:
        s, i = f"{base}-{i}", i + 1
    used.add(s)
    return s


# Короткие предлоги и союзы не оставляем висеть в конце строки: в узких
# колонках таблицы «до» отрывалось от «релиза». Привязываем неразрывным
# пробелом к следующему слову.
HANGING = re.compile(r"\b([а-яёa-z]{1,2}|для|под|при|над|без|про|или|как)\s+", re.IGNORECASE)

# Тире не переносится на новую строку — оно остаётся в конце строки, за словом.
# Поэтому пробел перед ним неразрывный, а перенос возможен только после него.
DASH = re.compile(r"[ \u00a0]+([—–])")


# Shift+Enter в Figma кладёт в текст U+2028, и браузер рвёт по нему строку
# насмерть. Такие переносы бывают двух сортов, и обходиться с ними надо
# по-разному, поэтому смотрим, что идёт следом.
SOFT_BREAK = re.compile(r"[ \t]*[\u2028\u2029][ \t]*")
EXTRA_SPACE = re.compile(r"[ \t\n\r\f\v]{2,}")


def unbreak(text, keep=True):
    """Жёсткий перенос из макета: где он по делу, а где под ширину колонки.

    Со строчной буквы после переноса — это продолжение фразы, перенос
    расставлен под макетную колонку. У нас она другая, и посреди фразы такой
    разрыв читается как ошибка: убираем. С заглавной или цифры — новое
    предложение или отдельный факт («Размер файла: … ⏎ Количество модулей: …»),
    его нельзя склеивать в одну строку: оставляем переносом.

    Неразрывный пробел не трогаем — он в исходнике поставлен намеренно.
    """
    def repl(m):
        nxt = m.string[m.end():m.end() + 1]
        return "<br>" if keep and (nxt.isupper() or nxt.isdigit()) else " "

    return EXTRA_SPACE.sub(" ", SOFT_BREAK.sub(repl, text))


def typography(text, breaks=True):
    text = unbreak(text, breaks)
    text = HANGING.sub(lambda m: m.group(1) + "\u00a0", text)
    return DASH.sub("\u00a0\\1", text)


def label(text):
    """Заголовок, пункт меню или подпись: экранирование плюс типографика.

    Узкие колонки меню и оглавления ломают строку где придётся, поэтому
    предлоги и тире привязываем и здесь, а не только в основном тексте.
    """
    return typography(esc(text), breaks=False)


def render_text(value):
    """Текст блока: строка или список кусков (url, text) со ссылками."""
    if isinstance(value, str):
        return typography(esc(value))
    out = []
    for part in value:
        url, chunk = part
        if url:
            out.append(
                f'<a href="{esc(url)}" target="_blank" rel="noopener">'
                f"{typography(esc(chunk))}</a>"
            )
        else:
            out.append(typography(esc(chunk)))
    return "".join(out)


def render_pill(href, text, file=False):
    """Кнопка: подпись и знак — стрелка «открыть» или «скачать».

    Без адреса кнопка рисуется, но не кликается: мёртвая ссылка на «#» хуже,
    она прокручивает страницу наверх.
    """
    tag = "a" if href else "span"
    attrs = f' href="{esc(href)}" target="_blank" rel="noopener"' if href else ""
    cls = "pill pill--file" if file else "pill"
    icon = "pill__download" if file else "pill__arrow"
    return (f'<{tag} class="{cls}"{attrs}>'
            f'<span class="pill__text">{label(text)}'
            f'<span class="{icon}" aria-hidden="true"></span></span></{tag}>')


# Абзац, который начинается со ссылки и кроме неё почти ничего не содержит, —
# это призыв к действию, а не текст: показываем его кнопкой. Абзац, где ссылка
# стоит внутри фразы, под правило не попадает — там она часть предложения.
CALL_TO_ACTION_TAIL = 20


def as_button(block):
    """Абзац-призыв → (адрес, подпись). Не призыв → None."""
    parts = block.get("text")
    if not isinstance(parts, list) or not parts or not parts[0][0]:
        return None
    if sum(1 for url, _ in parts if url) != 1:
        return None
    tail = "".join(chunk for url, chunk in parts[1:] if not url)
    if len(tail.strip()) > CALL_TO_ACTION_TAIL:
        return None
    return parts[0][0], parts[0][1] + tail


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
    # версию по содержимому картинки ставим по той же причине, что стилям:
    # заменённый постер под тем же именем иначе неделю висит из кеша браузера
    return f'<img class="media" src="{asset_url(src)}" alt="{alt}"{mode}{img_size(src)}>'


def render_video(block):
    cls = "video video--wide" if block.get("wide") else "video"
    cap = f'<figcaption>{label(block["caption"])}</figcaption>' if block.get("caption") else ""
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
    # кадр в своей обёртке: кнопка Play отсчитывается от него, а не от figure,
    # иначе с подписью внизу она села бы на её плашку
    return (f'<figure class="{cls}"><span class="video__frame">{img_tag(src_img, alt)}'
            f'<span class="video__play" aria-hidden="true"></span></span>{cap}</figure>')


ALERT_WORDS = {"важно", "внимание"}

# Секции, где перечисление читается как набор вариантов, а не как россыпь
# однородных пунктов: там нумерация помогает — на вариант можно сослаться
# номером. Ключ — заголовок секции из макета; переименуют его — сборка
# предупредит, а не вернёт молча буллеты.
NUMBERED_SECTIONS = {
    "Что можно продвигать",
    "Что можно размещать на баннерах",
}
_numbered_seen = set()
_dropped = []


def numbered(section):
    """Списки такой секции нумеруем кружками вместо буллетов.

    Заодно убираем строку-подводку перед списком — абзац, который кончается
    двоеточием и ничего не добавляет к заголовку секции («С помощью баннеров
    можно:» под заголовком «Что можно размещать на баннерах»). Что выкинули,
    сборка пишет в лог: молча терять текст из макета нельзя.
    """
    if section["title"] not in NUMBERED_SECTIONS:
        return section["blocks"]
    _numbered_seen.add(section["title"])

    blocks = [dict(b, variant="steps") if b["type"] == "ul" else b
              for b in section["blocks"]]
    out = []
    for i, b in enumerate(blocks):
        nxt = blocks[i + 1] if i + 1 < len(blocks) else None
        lead_in = (b["type"] == "p" and isinstance(b.get("text"), str)
                   and b["text"].strip().endswith(":")
                   and nxt and nxt.get("variant") == "steps")
        if lead_in:
            _dropped.append((section["title"], b["text"].strip()))
            continue
        out.append(b)
    return out

# Значок в начале заголовка — это пометка для списка под ним, а не текст.
# Эмодзи рисуется шрифтом системы: цвет, размер и вид у всех разные, поэтому
# в разметку он не едет — вместо него вектор из макета в маркерах списка.
MARKS = {"❌": "deny", "✅": "allow"}


def mark_lists(blocks):
    """Заголовок со значком и блок под ним — одна пометка: ✅ или ❌.

    Собираем их в один блок с заголовком и содержимым: дальше `pair_marks`
    решит, встанут они рядом или пойдут по одному. Маркеры пунктов при этом
    остаются обычными: метку несёт значок в заголовке плашки, повторять её
    в каждой строке незачем.
    """
    out, i = [], 0
    while i < len(blocks):
        b = blocks[i]
        text = b.get("text") if isinstance(b.get("text"), str) else None
        mark = next((m for m in MARKS if text and text.startswith(m)), None)
        if not mark:
            out.append(b)
            i += 1
            continue

        title = text[len(mark):].lstrip()
        kind = MARKS[mark]
        nxt = blocks[i + 1] if i + 1 < len(blocks) else None
        if nxt:
            out.append({"type": kind, "title": title, "blocks": [nxt]})
            i += 2
            continue

        out.append(dict(b, text=title))
        i += 1
    return out


def pair_marks(blocks):
    """✅ и ❌ подряд — это одна мысль, а не два блока.

    Ставим их в две равные колонки, как пары Do / Don't в доке Shopify:
    разрешённое и запрещённое сравнивают построчно, а не пролистывая одно,
    чтобы добраться до другого. Одинокий ❌ остаётся плашкой во всю ширину,
    одинокий ✅ — обычным заголовком со списком: сравнивать ему не с чем.
    """
    out, i = [], 0
    while i < len(blocks):
        b = blocks[i]
        nxt = blocks[i + 1] if i + 1 < len(blocks) else None
        if b.get("type") == "allow" and nxt and nxt.get("type") == "deny":
            out.append({"type": "do-dont", "cols": [b, nxt]})
            i += 2
            continue
        out.append(b)
        i += 1
    return out


def fold_alerts(blocks):
    """Абзац из одного слова «Важно» и следующий за ним — это плашка Alert.

    В макете такие места набраны обычным текстом, а не компонентом, поэтому
    компонент здесь не за что зацепить — собираем плашку по разметке текста.
    """
    out, i = [], 0
    while i < len(blocks):
        b = blocks[i]
        word = b.get("text") if b.get("type") == "p" else None
        nxt = blocks[i + 1] if i + 1 < len(blocks) else None
        if (isinstance(word, str) and word.strip().rstrip(":.").lower() in ALERT_WORDS
                and nxt and nxt.get("type") == "p"):
            out.append({"type": "note", "variant": "alert",
                        "title": word.strip().rstrip(":."), "text": nxt["text"]})
            i += 2
            continue
        out.append(b)
        i += 1
    return out


def render_mark_card(b):
    """Плашка «можно» или «нельзя»: геометрия одна, отличается только цвет."""
    kind = b["type"]  # allow | deny — класс плашки совпадает с типом блока
    return (f'<aside class="note note--{kind}">'
            f'<h3>{label(b["title"])}</h3>'
            f'{render_blocks(b["blocks"])}</aside>')


def render_blocks(blocks):
    """Блоки секции в HTML. Подряд идущие video собираются в ряд."""
    blocks = pair_marks(mark_lists(fold_alerts(blocks)))
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
        elif t == "p" and as_button(b):
            href, text = as_button(b)
            out.append(render_pill(href, text, file=True))
        elif t == "p":
            # внутри разделов абзацы обычные: в макете подзаголовочная строка
            # набрана тем же Regular, что и остальной текст. Лид — только один,
            # под заголовком страницы, он ставится в шаблоне.
            out.append(f"<p>{render_text(b['text'])}</p>")
        elif t == "h3":
            out.append(f"<h3>{label(b['text'])}</h3>")
        elif t == "ul":
            items = "".join(f"<li>{render_text(x)}</li>" for x in b["items"])
            cls = f' class="{b["variant"]}"' if b.get("variant") else ""
            # нумерованный список — это ol: номера рисует счётчик, а не текст,
            # и порядок остаётся в разметке, а не только в оформлении
            tag = "ol" if b.get("variant") == "steps" else "ul"
            out.append(f"<{tag}{cls}>{items}</{tag}>")
        elif t == "do-dont":
            cols = "".join(render_mark_card(c) for c in b["cols"])
            out.append(f'<div class="do-dont">{cols}</div>')
        elif t == "deny":
            out.append(render_mark_card(b))
        elif t == "allow":
            # без пары подсвечивать нечего: разрешённое и так набрано текстом
            out.append(f'<h3>{label(b["title"])}</h3>{render_blocks(b["blocks"])}')
        elif t == "checklist":
            items = "".join(f"<li>{render_text(x)}</li>" for x in b["items"])
            out.append(
                '<div class="checklist">'
                '<button class="checklist__copy" type="button" data-copy-checklist '
                'aria-label="Скопировать чек-лист">'
                # вектор `icon / copy` из макета (504:20177), выгружен как есть
                '<svg viewBox="0 0 20 20" aria-hidden="true">'
                '<path d="M13.75 17.5H2.91699V5.83301H13.75V17.5ZM4.91699 15.5H11.75V7.833'
                '01H4.91699V15.5ZM17.001 14.5H15.001V4.5H5.83398V2.5H17.001V14.5Z"/>'
                "</svg></button>"
                f'<ul class="checklist__list">{items}</ul>'
                "</div>")
        elif t == "table":
            out.append(render_table(b["rows"]))
        elif t == "note":
            title = f'<p class="note__title">{label(b["title"])}</p>' if b.get("title") else ""
            cls = "note note--alert" if b.get("variant") == "alert" else "note"
            out.append(f'<aside class="{cls}">{title}<p>{render_text(b["text"])}</p></aside>')
        elif t == "checkbox":
            out.append(f'<ul><li>{label(b["text"])}</li></ul>')
        elif t == "figure":
            cap = f'<figcaption>{label(b["caption"])}</figcaption>' if b.get("caption") else ""
            out.append(f'<figure>{img_tag(img_src(b["img"]))}{cap}</figure>')
        elif t == "bento":
            cards = "".join(
                f'<div class="bento__card"><p class="bento__title">{label(c["title"])}</p>'
                f'<p class="bento__body">{label(c["body"])}</p></div>'
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
                rows.append(f'<li><a href="{href}"{cur}>{label(item)}</a></li>')
            else:
                rows.append(f'<li><a href="#" aria-disabled="true">{label(item)}</a></li>')
        # шеврон в макете не декорация: группа сворачивается и разворачивается
        gid = "nav-" + slug(g["title"], set())
        parts.append(
            f'<div class="nav-group">'
            f'<button class="nav-group__title" type="button" data-nav-group'
            f' aria-expanded="true" aria-controls="{gid}">{label(g["title"])}</button>'
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

    # Вступление — такой же пункт оглавления, как разделы: id занимаем первым,
    # чтобы раздел с тем же названием получил номерной, а не наоборот
    intro_id = slug("Введение", used)

    body, toc = [], [f'<li><a href="#{intro_id}">Введение</a></li>']

    def drop_trailing_divider():
        """Линию снимаем там, где разделять уже нечего: перед заголовком главы
        (новый смысловой блок отбит антиквой) и в самом низу страницы."""
        if body and body[-1].endswith('<hr class="divider">'):
            body[-1] = body[-1][: -len('\n      <hr class="divider">')]

    for chapter in page["chapters"]:
        drop_trailing_divider()
        body.append(f'<h2 class="chapter__title">{label(chapter["title"])}</h2>')
        for section in chapter["sections"]:
            sid = slug(section["title"], used)
            toc.append(f'<li><a href="#{sid}">{label(section["title"])}</a></li>')
            body.append(
                f'<section class="section" id="{sid}">\n'
                f'        <h2><a class="anchor" href="#{sid}">{label(section["title"])}'
                f'<span class="anchor__icon" aria-hidden="true"></span></a></h2>\n'
                f'        {render_blocks(numbered(section))}\n'
                f'      </section>\n'
                f'      <hr class="divider">')

    drop_trailing_divider()

    crumbs = "".join(f"<span>{label(c)}</span>" for c in intro["breadcrumbs"])
    # в описании для поиска и соцсетей переносы из макета не нужны тем более:
    # там строку ломает уже сам сервис
    description = unbreak(intro["lead"] or "", keep=False)[:160]

    figma_button = render_pill(FIGMA_LINKS.get(page["slug"], ""), "Макеты в Figma")

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
  <meta name="theme-color" content="#12110c" media="(prefers-color-scheme: dark)">
  <meta name="theme-color" content="#ffffff" media="(prefers-color-scheme: light)">
  <meta property="og:title" content="{esc(intro["title"])} — гайд по формату">
  <meta property="og:description" content="{esc(description)}">
  <meta property="og:type" content="article">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&amp;family=Playfair+Display:wght@400;500&amp;display=swap">
  <link rel="stylesheet" href="{asset_url("assets/css/style.css")}">
</head>
<body>
  <div class="layout">
    <aside class="sidebar" id="sidebar">
      <div class="sidebar__head">
        <a class="brand" href="index.html" aria-label="Форматы Кинопоиска">{LOGO}</a>
        <button class="theme-switch" type="button" data-theme-toggle
                role="switch" aria-checked="false" aria-label="Светлая тема">
          <span class="theme-switch__window" aria-hidden="true">
            <svg data-icon="dark" viewBox="0 0 20 20"><path d="M8.47278 2.50001C7.65938 3.5789 7.17688 4.92172 7.17688 6.37697C7.17693 9.93688 10.0632 12.8223 13.6232 12.8223C15.0784 12.8223 16.4212 12.3408 17.5001 11.5274C16.7933 15.0243 13.7026 17.6572 9.99719 17.6572C5.76992 17.6571 2.34304 14.2302 2.3429 10.0029C2.3429 6.29755 4.97577 3.20679 8.47278 2.50001Z"/></svg>
            <svg data-icon="light" viewBox="0 0 20 20"><path d="M11 18.3335H9V15.7476C9.32491 15.8037 9.65905 15.8325 10 15.8325C10.3408 15.8325 10.6752 15.8037 11 15.7476V18.3335ZM5.22949 13.3569C5.61614 13.9053 6.09512 14.3844 6.64355 14.771L4.87402 16.5405L3.45996 15.1265L5.22949 13.3569ZM16.541 15.1265L15.127 16.5405L13.3574 14.771C13.9059 14.3844 14.3848 13.9054 14.7715 13.3569L16.541 15.1265ZM10 5.83252C12.3012 5.83252 14.167 7.69833 14.167 9.99951C14.167 12.3007 12.3012 14.1665 10 14.1665C7.69881 14.1665 5.83301 12.3007 5.83301 9.99951C5.83301 7.69833 7.69881 5.83252 10 5.83252ZM4.25195 8.99951C4.19582 9.32443 4.16699 9.65856 4.16699 9.99951C4.16699 10.3404 4.19586 10.6747 4.25195 10.9995H1.66699V8.99951H4.25195ZM18.334 10.9995H15.748C15.8041 10.6747 15.833 10.3404 15.833 9.99951C15.833 9.65856 15.8042 9.32443 15.748 8.99951H18.334V10.9995ZM16.541 4.87353L14.7715 6.64307C14.3849 6.09463 13.9058 5.61565 13.3574 5.229L15.127 3.45947L16.541 4.87353ZM6.64258 5.22803C6.0941 5.61467 5.61516 6.09361 5.22852 6.64209L3.45996 4.87353L4.87402 3.45947L6.64258 5.22803ZM11 4.25146C10.6752 4.19537 10.3408 4.1665 10 4.1665C9.65905 4.1665 9.32491 4.19533 9 4.25146V1.6665H11V4.25146Z"/></svg>
          </span>
        </button>
      </div>
      <button class="nav-toggle" type="button" data-nav-toggle>Разделы</button>
      <div class="nav-groups">
          {render_nav(page["nav"], meta["nav"])}
      </div>
    </aside>

    <main class="main">
      <nav class="breadcrumbs">{crumbs}</nav>
      <div class="intro" id="{intro_id}">
        <div class="page-head">
          <h1 class="page-title">{label(intro["title"])}</h1>
          {figma_button}
        </div>
        <p class="lead">{label(intro["lead"])}</p>
        {intro_html}
      </div>

      {"".join(body)}
    </main>

    <aside class="toc" aria-label="Содержание">
      <ol>
        <span class="toc__marker" aria-hidden="true"></span>
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

    # палитру проверяем на каждой сборке: неразличимые оттенки заводятся
    # незаметно и вылезают уже на сайте
    for problem in palette.check():
        print(f"близкие оттенки — {problem}")

    # секцию могли переименовать в макете — тогда нумерация тихо исчезнет
    for title in sorted(NUMBERED_SECTIONS - _numbered_seen):
        print(f"нумерованной секции нет в тексте: «{title}»")

    for title, text in _dropped:
        print(f"убрала подводку в «{title}»: «{text}»")


if __name__ == "__main__":
    main()
