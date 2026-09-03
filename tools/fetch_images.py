#!/usr/bin/env python3
"""Рендерит узлы из .refs/content.json в PNG и складывает в assets/img/."""

import hashlib
import json
import os
import pathlib
import urllib.parse
import urllib.request

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTENT = ROOT / ".refs" / "content.json"
IMG = ROOT / "assets" / "img"
FILE_KEY = "uYLX67r8VhmLg0TGH5Izrg"
TOKEN = os.environ["FIGMA_TOKEN"]
BATCH = 12


def api(url):
    req = urllib.request.Request(url, headers={"X-Figma-Token": TOKEN})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def main():
    data = json.loads(CONTENT.read_text())
    ids = sorted({e["id"] for e in data["exports"]})
    IMG.mkdir(parents=True, exist_ok=True)

    urls = {}
    for i in range(0, len(ids), BATCH):
        chunk = ids[i:i + BATCH]
        q = urllib.parse.urlencode({"ids": ",".join(chunk), "format": "png", "scale": "2"})
        res = api(f"https://api.figma.com/v1/images/{FILE_KEY}?{q}")
        if res.get("err"):
            print("ошибка:", res["err"], chunk)
            continue
        urls.update({k: v for k, v in res.get("images", {}).items() if v})

    # скачиваем, склеиваем дубликаты (один постер стоит в нескольких снипетах)
    # и пережимаем в webp — PNG с кадрами видео весит в разы больше
    seen, mapping = {}, {}
    for nid, url in urls.items():
        stem = nid.replace(":", "-").replace(";", "-")
        tmp = IMG / (stem + ".png")
        urllib.request.urlretrieve(url, tmp)
        digest = hashlib.md5(tmp.read_bytes()).hexdigest()
        if digest in seen:
            tmp.unlink()
            mapping[stem] = seen[digest]
            continue
        Image.open(tmp).convert("RGB").save(IMG / (stem + ".webp"), "WEBP", quality=82,
                                            method=6)
        tmp.unlink()
        seen[digest] = stem
        mapping[stem] = stem

    (IMG / "map.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=1))
    missing = [i for i in ids if i not in urls]
    print(f"скачано {len(urls)}, уникальных файлов {len(seen)}")
    if missing:
        print("не отрендерились:", missing)


if __name__ == "__main__":
    main()
