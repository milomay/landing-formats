#!/usr/bin/env python3
"""Достаёт содержимое страниц лендинга из выгрузки Figma REST API в content.json.

Вход:  .refs/full.json — ответ /v1/files/:key/nodes для узлов страниц.
Выход: .refs/content.json — семантическое дерево блоков + список узлов на экспорт.
"""

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / ".refs" / "full.json"
OUT = ROOT / ".refs" / "content.json"

PAGES = [
    {"id": "469:17008", "slug": "preroll", "title": "Преролл"},
    {"id": "469:17400", "slug": "banner", "title": "Баннер"},
]

# узлы, которые надо отрендерить в картинки
exports = []


def visible(node):
    return node.get("visible", True)


def kids(node):
    return [c for c in node.get("children", []) if visible(c)]


def name(node):
    return node.get("name", "")


def texts(node, limit=None):
    """Собирает видимый текст поддерева в порядке обхода."""
    out = []

    def walk(n):
        if not visible(n):
            return
        if n["type"] == "TEXT":
            t = n.get("characters", "").strip()
            if t:
                out.append(t)
        for c in n.get("children", []):
            walk(c)

    walk(node)
    return out[:limit] if limit else out


def first_text(node):
    t = texts(node, 1)
    return t[0] if t else ""


def rich_text(node):
    """Текст TEXT-узла с сохранением ссылок из characterStyleOverrides."""
    chars = node.get("characters", "")
    if not chars:
        return ""
    overrides = node.get("characterStyleOverrides") or []
    table = node.get("styleOverrideTable") or {}
    link_ids = {
        int(k): v["hyperlink"]["url"]
        for k, v in table.items()
        if isinstance(v, dict) and v.get("hyperlink", {}).get("url")
    }
    if not link_ids:
        return chars
    parts, buf, cur = [], [], None
    for i, ch in enumerate(chars):
        oid = overrides[i] if i < len(overrides) else 0
        url = link_ids.get(oid)
        if url != cur:
            if buf:
                parts.append((cur, "".join(buf)))
            buf, cur = [], url
        buf.append(ch)
    if buf:
        parts.append((cur, "".join(buf)))
    return parts


def text_node(node):
    """Находит первый видимый TEXT в поддереве и возвращает его rich-представление."""
    if not visible(node):
        return None
    if node["type"] == "TEXT":
        return node
    for c in node.get("children", []):
        r = text_node(c)
        if r is not None:
            return r
    return None


def export(node_id, kind):
    exports.append({"id": node_id, "kind": kind})
    return re.sub(r"[:;]", "-", node_id)


# --- распознавание блоков -------------------------------------------------


def text_nodes(node):
    """Все видимые TEXT-узлы поддерева, кроме маркеров списка."""
    out = []

    def walk(n):
        if not visible(n):
            return
        if n["type"] == "TEXT":
            if n.get("characters", "").strip() not in ("", "•"):
                out.append(n)
        for c in n.get("children", []):
            walk(c)

    walk(node)
    return out


def has_checkbox(node):
    """Список-чеклист: вместо буллета в макете стоит инстанс Checkbox."""
    if not visible(node):
        return False
    if name(node) == "Checkbox":
        return True
    return any(has_checkbox(c) for c in node.get("children", []))


def bullet_items(node):
    """Paragraph With Bullet List → список пунктов со ссылками."""
    items = []
    for frame in kids(node):
        if frame["type"] != "FRAME":
            continue
        for row in kids(frame):
            tns = text_nodes(row)
            if tns:
                items.append(rich_text(tns[0]) if len(tns) == 1
                             else " ".join(t["characters"].strip() for t in tns))
    if not items:  # плоский вариант без вложенной обёртки
        items = [rich_text(t) for t in text_nodes(node)]
    return items


def table_row(node):
    """Spec Table Row → {kind: header|body|bullets, cells: [...]}"""
    props = node.get("componentProperties") or {}
    kind = (props.get("Type", {}) or {}).get("value", "body")
    cells = []
    for cell in kids(node):
        tns = text_nodes(cell)
        if not tns:
            continue
        # ячейка-буллеты: несколько строк
        cells.append({"items": [rich_text(t) for t in tns]} if len(tns) > 1
                     else rich_text(tns[0]))
    return {"kind": kind, "cells": cells}


def has_image_fill(node):
    return any(f.get("type") == "IMAGE" for f in node.get("fills", []) or [])


def block(node):
    """Один узел → список блоков документа."""
    n = name(node)
    t = node["type"]

    if n in ("Divider", "divider"):
        return [{"type": "hr"}]

    if n == "Header H2":
        return [{"type": "h2", "text": first_text(node)}]

    if n == "Chapter Header":
        return [{"type": "chapter", "text": first_text(node)}]

    if n == "Paragraph H1":
        return [{"type": "h3", "text": first_text(node)}]

    if n in ("Paragraph", "Subheading", "Guidance Paragraphs With Links"):
        tn = text_node(node)
        if tn is None:
            return []
        return [{"type": "p", "text": rich_text(tn), "lead": n == "Subheading"}]

    if n == "Paragraph With Bullet List":
        kind = "checklist" if has_checkbox(node) else "ul"
        return [{"type": kind, "items": bullet_items(node)}]

    if n == "BulletList":
        items, checklist = [], False
        for c in kids(node):
            checklist = checklist or has_checkbox(c)
            items += bullet_items(c)
        return [{"type": "checklist" if checklist else "ul", "items": items}]

    if n == "SpecTable":
        rows = [table_row(c) for c in kids(node) if name(c).startswith("Spec Table Row")]
        return [{"type": "table", "rows": rows}]

    if n == "Spec Table Row":
        return [{"type": "table", "rows": [table_row(node)]}]

    if n == "Checkbox":
        return [{"type": "checkbox", "text": " ".join(texts(node))}]

    if n == "Note":
        tns = text_nodes(node)
        if not tns:
            return []
        return [{"type": "note",
                 "title": tns[0]["characters"].strip() if len(tns) > 1 else "",
                 "text": rich_text(tns[-1])}]

    if n == "video snippet":
        # кнопку play рисуем в CSS — экспортируем только постер
        poster = next((c for c in kids(node) if name(c) == "image"), node)
        return [{"type": "video", "img": export(poster["id"], "video"),
                 "caption": first_text(node)}]

    # композиция из наложенных слоёв — забираем одной картинкой, а не по частям
    if t == "GROUP":
        return [{"type": "figure", "img": export(node["id"], "figure"), "caption": ""}]

    if n == "Figure" or (t == "RECTANGLE" and has_image_fill(node)):
        target = node if t == "RECTANGLE" else (kids(node)[0] if kids(node) else node)
        return [{"type": "figure", "img": export(target["id"], "figure"),
                 "caption": ""}]

    if n == "Content":  # вводная карточка с превью-видео
        poster = next((c for c in kids(node) if name(c) == "image"), node)
        return [{"type": "video", "img": export(poster["id"], "video"),
                 "caption": first_text(node), "wide": True}]

    if n == "bento-grid":
        cards = []
        for row in kids(node):
            for card in kids(row):
                if name(card) != "bento-card":
                    continue
                ts = texts(card)
                cards.append({"title": ts[0] if ts else "",
                              "body": " ".join(ts[1:]) if len(ts) > 1 else ""})
        return [{"type": "bento", "cards": cards}]

    # неизвестная обёртка — спускаемся глубже
    if t in ("FRAME", "GROUP", "INSTANCE", "COMPONENT"):
        out = []
        for c in kids(node):
            out += block(c)
        return out

    if t == "TEXT":
        txt = node.get("characters", "").strip()
        return [{"type": "p", "text": rich_text(node)}] if txt else []

    return []


def parse_nav(sidebar):
    groups = []
    for grp in kids(sidebar):
        if not name(grp).startswith("NavGroup"):
            continue
        items = []
        title = name(grp).replace("NavGroup — ", "")
        for wrap in kids(grp):
            for inner in kids(wrap):
                for item in kids(inner):
                    if name(item).startswith("NavItem"):
                        items.append(first_text(item))
        if items:
            groups.append({"title": title, "items": items})
    return groups


def parse_intro(intro):
    out = {"breadcrumbs": [], "title": "", "lead": "", "blocks": []}
    for c in kids(intro):
        n = name(c)
        if n == "Intro Text":
            for cc in kids(c):
                if name(cc) == "breadcrumbs":
                    out["breadcrumbs"] = [t for t in texts(cc) if t != "/"]
                elif cc["type"] == "TEXT":
                    if not out["title"]:
                        out["title"] = cc.get("characters", "").strip()
                    else:
                        out["lead"] = cc.get("characters", "").strip()
                else:
                    ts = texts(cc)
                    if ts and not out["title"]:
                        out["title"] = ts[0]
        else:
            out["blocks"] += block(c)
    return out


def parse_page(doc, meta):
    layout = kids(doc)[0]
    sidebar = next(c for c in kids(layout) if name(c) == "Sidebar Left")
    main = next(c for c in kids(layout) if name(c) == "Main")

    page = {"slug": meta["slug"], "title": meta["title"],
            "nav": parse_nav(next(c for c in kids(sidebar) if name(c) == "Nav")),
            "intro": None, "chapters": []}

    for c in kids(main):
        n = name(c)
        if n == "Intro":
            page["intro"] = parse_intro(c)
        elif n.startswith("Chapter"):
            chapter = {"title": n.replace("Chapter — ", ""), "sections": []}
            current = None
            for sc in kids(c):
                sn = name(sc)
                if sn == "Chapter Header":
                    chapter["title"] = first_text(sc) or chapter["title"]
                elif sn.startswith("Section"):
                    current = {"title": sn.replace("Section — ", ""), "blocks": []}
                    for b in block(sc):
                        if b["type"] == "h2" and not current["blocks"]:
                            current["title"] = b["text"]
                        else:
                            current["blocks"].append(b)
                    chapter["sections"].append(current)
            page["chapters"].append(chapter)
    return page


def main():
    raw = json.loads(RAW.read_text())
    pages = []
    for meta in PAGES:
        node = raw["nodes"].get(meta["id"])
        if not node:
            continue
        pages.append(parse_page(node["document"], meta))
    OUT.write_text(json.dumps({"pages": pages, "exports": exports},
                              ensure_ascii=False, indent=1))
    for p in pages:
        total = sum(len(s["blocks"]) for ch in p["chapters"] for s in ch["sections"])
        print(f"{p['slug']}: глав {len(p['chapters'])}, "
              f"секций {sum(len(ch['sections']) for ch in p['chapters'])}, "
              f"блоков {total}")
    print(f"на экспорт: {len(exports)} узлов")


if __name__ == "__main__":
    main()
