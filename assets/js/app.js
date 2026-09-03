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

// --- ролик во весь экран ----------------------------------------------------
// В плитке лежит только постер: смотреть ролик в колонке 229 px нечего,
// по клику он открывается крупно поверх страницы.

let lightbox = null;
let lightboxVideo = null;
let openedFrom = null;

function buildLightbox() {
  lightbox = document.createElement('div');
  lightbox.className = 'lightbox';
  lightbox.hidden = true;
  lightbox.setAttribute('role', 'dialog');
  lightbox.setAttribute('aria-modal', 'true');
  lightbox.innerHTML =
    '<button class="lightbox__close" type="button" aria-label="Закрыть">×</button>' +
    '<video controls playsinline></video>';
  lightboxVideo = lightbox.querySelector('video');
  document.body.appendChild(lightbox);

  lightbox.addEventListener('click', (e) => {
    // клик мимо ролика и по крестику закрывают, клик по самому видео — нет
    if (e.target === lightbox || e.target.closest('.lightbox__close')) closeVideo();
  });
}

function openVideo(src, poster) {
  if (!lightbox) buildLightbox();
  lightboxVideo.src = src;
  lightboxVideo.poster = poster || '';
  lightbox.hidden = false;
  document.body.style.overflow = 'hidden';
  lightbox.querySelector('.lightbox__close').focus();
  lightboxVideo.play().catch(() => {
    /* браузер не дал автозапуск — контролы на месте, запустят руками */
  });
}

function closeVideo() {
  if (!lightbox || lightbox.hidden) return;
  lightboxVideo.pause();
  lightboxVideo.removeAttribute('src');
  lightboxVideo.load(); // иначе файл продолжает качаться в фоне
  lightbox.hidden = true;
  document.body.style.overflow = '';
  if (openedFrom) openedFrom.focus();
}

document.addEventListener('click', (e) => {
  const button = e.target.closest('[data-video-open]');
  if (!button) return;
  openedFrom = button;
  openVideo(button.dataset.src, button.querySelector('img')?.src);
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeVideo();
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
