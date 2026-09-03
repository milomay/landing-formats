// Тема, копирование чек-листа, ролик во весь экран, мобильное меню,
// сворачивание групп навигации, старт и подсветка оглавления.

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
  document.body.style.overflow = 'hidden';
  // без принудительного пересчёта браузер склеит появление и is-open в один кадр
  void lightbox.offsetWidth;
  lightbox.classList.add('is-open');
  lightbox.querySelector('.lightbox__close').focus();
  lightboxVideo.play().catch(() => {
    /* браузер не дал автозапуск — контролы на месте, запустят руками */
  });
}

function closeVideo() {
  if (!lightbox || !lightbox.classList.contains('is-open')) return;
  lightbox.classList.remove('is-open');
  lightboxVideo.pause();
  document.body.style.overflow = '';
  if (openedFrom) openedFrom.focus();
  // ролик выгружаем после анимации, иначе кадр пропадёт прямо на глазах
  setTimeout(() => {
    if (lightbox.classList.contains('is-open')) return;
    lightboxVideo.removeAttribute('src');
    lightboxVideo.load(); // иначе файл продолжает качаться в фоне
  }, 300);
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

// --- сворачивание групп в левом меню ----------------------------------------
// Шеврон у заголовка группы рабочий: сворачивает и разворачивает список.

document.addEventListener('click', (e) => {
  const title = e.target.closest('[data-nav-group]');
  if (!title) return;
  const open = title.getAttribute('aria-expanded') === 'true';
  title.setAttribute('aria-expanded', String(!open));
  try {
    const id = title.getAttribute('aria-controls');
    const was = JSON.parse(localStorage.getItem('nav-collapsed') || '[]');
    const now = open ? [...new Set([...was, id])] : was.filter((x) => x !== id);
    localStorage.setItem('nav-collapsed', JSON.stringify(now));
  } catch (err) {
    /* приватный режим — состояние просто не запомнится */
  }
});

// то, что свернули, остаётся свёрнутым и на соседней странице
try {
  JSON.parse(localStorage.getItem('nav-collapsed') || '[]').forEach((id) => {
    const title = document.querySelector('[data-nav-group][aria-controls="' + id + '"]');
    const body = document.getElementById(id);
    // группу с текущей страницей не сворачиваем — иначе непонятно, где находишься
    if (title && body && !body.querySelector('[aria-current="page"]')) {
      title.setAttribute('aria-expanded', 'false');
    }
  });
} catch (err) {
  /* localStorage недоступен — все группы просто открыты */
}

// --- старт оглавления по верху лида -----------------------------------------
// В CSS отбивка задана под однострочный заголовок. Если заголовок перенесётся
// или сменится кегль, считаем её от фактического положения лида.

const tocEl = document.querySelector('.toc');
const leadEl = document.querySelector('.lead');

if (tocEl && leadEl) {
  const alignToc = () => {
    // считаем от сетки, а не от окна: приклеенное оглавление своё место
    // в потоке уже не показывает, а родитель стоит на месте всегда
    const base = tocEl.parentElement.getBoundingClientRect().top;
    const shift = Math.round(leadEl.getBoundingClientRect().top - base);
    tocEl.style.marginTop = Math.max(0, shift) + 'px';
  };
  alignToc();
  // шрифты подъезжают позже разметки и меняют высоту заголовка — пересчитываем
  if (document.fonts) document.fonts.ready.then(alignToc);
  let queued = false;
  window.addEventListener('resize', () => {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      alignToc();
    });
  });
}

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
