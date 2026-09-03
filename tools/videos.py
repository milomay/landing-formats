#!/usr/bin/env python3
"""Показывает слоты под видео: куда какой файл класть и что уже на месте.

Ролик подхватывается автоматически: положить `assets/video/<id>.mp4` (или `.webm`)
и пересобрать `tools/build.py`. Файл в репозиторий не кладём — тогда вместо него
ссылка в `assets/video/links.json`: {"<id>": "https://.../clip.mp4"}.
"""

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTENT = ROOT / ".refs" / "content.json"
VIDEO_DIR = ROOT / "assets" / "video"
LINKS = VIDEO_DIR / "links.json"

EXT = (".mp4", ".webm")


def slots(page):
    """Все video-блоки страницы в порядке появления: (id, где находится)."""
    out = []

    def walk(blocks, where):
        for b in blocks:
            if b["type"] == "video":
                out.append((b["img"], where))

    walk((page["intro"] or {}).get("blocks", []), "интро")
    for chapter in page["chapters"]:
        for section in chapter["sections"]:
            walk(section["blocks"], section["title"])
    return out


def state(block_id, links):
    if block_id in links:
        return "ссылка: " + links[block_id]
    for ext in EXT:
        f = VIDEO_DIR / f"{block_id}{ext}"
        if f.exists():
            return f"файл {f.name}, {f.stat().st_size / 1024 / 1024:.1f} МБ"
    return "— пусто, лежит постер из макета"


def main():
    data = json.loads(CONTENT.read_text())
    links = json.loads(LINKS.read_text()) if LINKS.exists() else {}
    total = filled = 0
    for page in data["pages"]:
        rows = slots(page)
        if not rows:
            continue
        print(f"\n=== {page['title']} ({page['slug']})")
        section = None
        for i, (block_id, where) in enumerate(rows, 1):
            if where != section:
                section = where
                print(f"  {where}")
            st = state(block_id, links)
            total += 1
            filled += not st.startswith("—")
            print(f"    {i}. assets/video/{block_id}.mp4  →  {st}")
    print(f"\nвсего слотов: {total}, заполнено: {filled}")
    if filled < total:
        print("положить файлы и пересобрать: python3 tools/build.py")


if __name__ == "__main__":
    main()
