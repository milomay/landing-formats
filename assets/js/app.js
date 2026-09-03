// Тема, мобильное меню и подсветка активного пункта оглавления.

// --- тема ------------------------------------------------------------------
// По умолчанию тёмная: системную настройку не слушаем, светлая включается
// только вручную. Значение уже выставлено инлайн-скриптом в <head>.

const root = document.documentElement;

function applyTheme(theme) {
  root.dataset.theme = theme;
  const label = document.querySelector('[data-theme-label]');
  if (label) label.textContent = theme === 'light' ? 'Светлая тема' : 'Тёмная тема';
}

applyTheme(root.dataset.theme === 'light' ? 'light' : 'dark');

document.addEventListener('click', (e) => {
  if (!e.target.closest('[data-theme-toggle]')) return;
  const next = root.dataset.theme === 'light' ? 'dark' : 'light';
  applyTheme(next);
  try {
    localStorage.setItem('theme', next);
  } catch (err) {
    /* приватный режим — тема просто не запомнится */
  }
});

// --- копирование чек-листа --------------------------------------------------

document.addEventListener('click', async (e) => {
  const button = e.target.closest('[data-copy-checklist]');
  if (!button) return;
  const items = [...button.closest('.checklist').querySelectorAll('li')];
  const text = items.map((li) => '- ' + li.textContent.trim()).join('\n');
  let copied = false;
  try {
    await navigator.clipboard.writeText(text);
    copied = true;
  } catch (err) {
    // Clipboard API недоступен — пробуем старый способ через скрытое поле
    const field = document.createElement('textarea');
    field.value = text;
    field.setAttribute('readonly', '');
    field.style.cssText = 'position:fixed;top:-1000px';
    document.body.appendChild(field);
    field.select();
    try {
      copied = document.execCommand('copy');
    } catch (e) {
      /* не вышло — пункты всегда можно выделить руками */
    }
    field.remove();
  }
  if (!copied) return;
  button.classList.add('is-done');
  setTimeout(() => button.classList.remove('is-done'), 1500);
});

// --- запуск ролика ----------------------------------------------------------
// В покое у видео нет контролов — поверх постера лежит кнопка play из макета.
// По клику отдаём управление нативной панели браузера.

document.addEventListener('click', (e) => {
  const button = e.target.closest('[data-video-play]');
  if (!button) return;
  const figure = button.closest('.video');
  const video = figure.querySelector('video');
  if (!video) return;
  video.controls = true;
  figure.classList.add('is-playing');
  video.play().catch(() => {
    /* автозапуск мог не разрешиться — контролы уже на месте, запустят руками */
  });
});

// --- мобильное меню ---------------------------------------------------------

document.addEventListener('click', (e) => {
  const toggle = e.target.closest('[data-nav-toggle]');
  if (toggle) document.getElementById('sidebar').classList.toggle('is-open');
});

// --- активный пункт оглавления ----------------------------------------------

const links = [...document.querySelectorAll('.toc a')];
const sections = links
  .map((a) => document.getElementById(decodeURIComponent(a.hash.slice(1))))
  .filter(Boolean);

if (sections.length && 'IntersectionObserver' in window) {
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        links.forEach((a) => a.classList.remove('is-active'));
        const active = links.find((a) => decodeURIComponent(a.hash.slice(1)) === entry.target.id);
        if (active) active.classList.add('is-active');
      });
    },
    { rootMargin: '-10% 0px -80% 0px', threshold: 0 }
  );
  sections.forEach((s) => observer.observe(s));
}
