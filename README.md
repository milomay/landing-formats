# Лендинг форматов

Гайды по рекламным форматам Кинопоиска. Статический сайт, собран из макета Figma
[«Лендинг форматов»](https://www.figma.com/design/uYLX67r8VhmLg0TGH5Izrg) — страница `Alina`,
узлы `469:17008` (Преролл) и `469:17400` (Баннер).

## Страницы

- `index.html` — Преролл
- `banner.html` — Баннер

## Как устроено

Чистый HTML + CSS, без сборки и зависимостей в рантайме. Открывается двойным кликом,
кладётся на любой статический хостинг как есть.

```
assets/css/style.css   токены и вёрстка
assets/js/app.js       мобильное меню, подсветка активного пункта оглавления
assets/img/            иллюстрации, выгруженные из Figma (webp)
tools/                 скрипты пересборки из макета
```

## Пересобрать из макета

Нужен `FIGMA_TOKEN` в окружении и Pillow (`pip install pillow`).

```bash
curl -s "https://api.figma.com/v1/files/uYLX67r8VhmLg0TGH5Izrg/nodes?ids=469:17008,469:17400" \
  -H "X-Figma-Token: $FIGMA_TOKEN" -o .refs/full.json
python3 tools/extract.py       # макет → .refs/content.json
python3 tools/fetch_images.py  # рендер картинок в assets/img (webp, дубли склеиваются)
python3 tools/build.py         # content.json → index.html, banner.html
```

Правки контента делаются в макете и приезжают через пересборку — руками HTML не правим,
иначе следующая сборка их затрёт.

## Локальный просмотр

```bash
python3 -m http.server 4173
```

## Шрифты

В макете — `Graphik Kinopoisk LC` и `SangBleu Sunrise`. Оба лицензионные, в репозитории их нет:
на машине с установленными шрифтами сайт выглядит как макет, у остальных подставляются
системные аналоги из `--font` и `--font-display` в `assets/css/style.css`.
