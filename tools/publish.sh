#!/usr/bin/env bash
# Публикует сайт на GitHub Pages. Идемпотентно: можно запускать повторно.
# Перед первым запуском нужен `gh auth login`.

set -euo pipefail

REPO="${1:-landing-formats}"
cd "$(dirname "$0")/.."

if ! gh auth status >/dev/null 2>&1; then
  echo "Сначала: gh auth login" >&2
  exit 1
fi

OWNER=$(gh api user --jq .login)

if gh repo view "$OWNER/$REPO" >/dev/null 2>&1; then
  echo "Репозиторий $OWNER/$REPO уже есть — обновляю"
  git remote get-url origin >/dev/null 2>&1 || \
    git remote add origin "https://github.com/$OWNER/$REPO.git"
  git push -u origin main
else
  gh repo create "$OWNER/$REPO" --public --source=. --remote=origin --push \
    --description "Гайды по рекламным форматам Кинопоиска"
fi

# Pages из корня ветки main
gh api -X POST "repos/$OWNER/$REPO/pages" \
  -f "source[branch]=main" -f "source[path]=/" >/dev/null 2>&1 || \
gh api -X PUT "repos/$OWNER/$REPO/pages" \
  -f "source[branch]=main" -f "source[path]=/" >/dev/null 2>&1 || true

echo
echo "Репозиторий: https://github.com/$OWNER/$REPO"
echo "Сайт:        https://$OWNER.github.io/$REPO/"
echo "Первая сборка Pages занимает 1–2 минуты."
