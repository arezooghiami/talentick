// Talentick — UI Utilities

// ─── Toast ────────────────────────────────────────────────────────
function toast(msg, type = 'info', duration = 3500) {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = msg;
  container.appendChild(el);
  setTimeout(() => { el.remove(); }, duration);
}

const toastSuccess = (m) => toast(m, 'success');
const toastError   = (m) => toast(m, 'error');
const toastInfo    = (m) => toast(m, 'info');

// ─── Modal ────────────────────────────────────────────────────────
function openModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.remove('hidden');
}

function closeModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.add('hidden');
}

// Close on overlay click
document.addEventListener('click', (e) => {
  if (e.target.classList.contains('modal-overlay')) {
    e.target.classList.add('hidden');
  }
});

// ─── Role display ─────────────────────────────────────────────────
function roleLabel(role) {
  const map = {
    super_admin: 'سوپر ادمین',
    org_admin:   'ادمین سازمان',
    manager:     'مدیر',
    employee:    'کارمند',
  };
  return map[role] || role;
}

function roleBadge(role) {
  const cls = {
    super_admin: 'badge-super',
    org_admin:   'badge-admin',
    manager:     'badge-manager',
    employee:    'badge-employee',
  }[role] || 'badge-employee';
  return `<span class="badge ${cls}">${roleLabel(role)}</span>`;
}

// ─── Status badge ─────────────────────────────────────────────────
function statusBadge(isActive) {
  return isActive
    ? '<span class="badge badge-active">فعال</span>'
    : '<span class="badge badge-inactive">غیرفعال</span>';
}

// ─── Initials avatar ─────────────────────────────────────────────
function initials(name = '') {
  return name.split(' ').slice(0, 2).map(w => w[0]).join('');
}

// ─── Date formatter ──────────────────────────────────────────────
function fmtDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('fa-IR');
}

// ─── تبدیل تاریخ جلالی ⇄ میلادی (الگوریتم jalaali-js) ───────────────
// برای ورودی‌های تاریخ که با jalaliDatepicker مقدار «۱۴۰۳/۰۶/۱۵» می‌گیرند
// ولی بک‌اند تاریخ ISO میلادی می‌خواهد.
const Jalaali = (() => {
  const breaks = [-61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210,
    1635, 2060, 2097, 2192, 2262, 2324, 2394, 2456, 3178];
  const div = (a, b) => ~~(a / b);
  const mod = (a, b) => a - ~~(a / b) * b;

  function jalCal(jy, withoutLeap) {
    const bl = breaks.length, gy = jy + 621;
    let leapJ = -14, jp = breaks[0], jm, jump, leap, leapG, march, n, i;
    if (jy < jp || jy >= breaks[bl - 1]) throw new Error('Invalid Jalaali year ' + jy);
    for (i = 1; i < bl; i += 1) {
      jm = breaks[i];
      jump = jm - jp;
      if (jy < jm) break;
      leapJ = leapJ + div(jump, 33) * 8 + div(mod(jump, 33), 4);
      jp = jm;
    }
    n = jy - jp;
    leapJ = leapJ + div(n, 33) * 8 + div(mod(n, 33) + 3, 4);
    if (mod(jump, 33) === 4 && jump - n === 4) leapJ += 1;
    leapG = div(gy, 4) - div((div(gy, 100) + 1) * 3, 4) - 150;
    march = 20 + leapJ - leapG;
    if (!withoutLeap) {
      if (jump - n < 6) n = n - jump + div(jump + 4, 33) * 33;
      leap = mod(mod(n + 1, 33) - 1, 4);
      if (leap === -1) leap = 4;
    }
    return { leap, gy, march };
  }

  function g2d(gy, gm, gd) {
    let d = div((gy + div(gm - 8, 6) + 100100) * 1461, 4)
      + div(153 * mod(gm + 9, 12) + 2, 5) + gd - 34840408;
    d = d - div(div(gy + 100100 + div(gm - 8, 6), 100) * 3, 4) + 752;
    return d;
  }

  function d2g(jdn) {
    let j = 4 * jdn + 139361631;
    j = j + div(div(4 * jdn + 183187720, 146097) * 3, 4) * 4 - 3908;
    const i = div(mod(j, 1461), 4) * 5 + 308;
    const gd = div(mod(i, 153), 5) + 1;
    const gm = mod(div(i, 153), 12) + 1;
    const gy = div(j, 1461) - 100100 + div(8 - gm, 6);
    return { gy, gm, gd };
  }

  function toJalaali(gy, gm, gd) {
    const jdn = g2d(gy, gm, gd);
    let gy2 = d2g(jdn).gy, jy = gy2 - 621;
    const r = jalCal(jy, false);
    const jdn1f = g2d(gy2, 3, r.march);
    let k = jdn - jdn1f, jm, jd;
    if (k >= 0) {
      if (k <= 185) { jm = 1 + div(k, 31); jd = mod(k, 31) + 1; return { jy, jm, jd }; }
      k -= 186;
    } else {
      jy -= 1;
      k += 179;
      if (r.leap === 1) k += 1;
    }
    jm = 7 + div(k, 30);
    jd = mod(k, 30) + 1;
    return { jy, jm, jd };
  }

  function toGregorian(jy, jm, jd) {
    const r = jalCal(jy, true);
    const jdn = g2d(r.gy, 3, r.march) + (jm - 1) * 31 - div(jm, 7) * (jm - 7) + jd - 1;
    return d2g(jdn);
  }

  return { toJalaali, toGregorian };
})();

// ISO/تاریخ میلادی → رشته‌ی ورودی جلالی «۱۴۰۳/۰۶/۱۵» (ارقام لاتین، چون
// jalaliDatepicker خودش با همین قالب کار می‌کند).
function isoToJalaliInput(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return '';
  const j = Jalaali.toJalaali(d.getFullYear(), d.getMonth() + 1, d.getDate());
  const pad = n => String(n).padStart(2, '0');
  return `${j.jy}/${pad(j.jm)}/${pad(j.jd)}`;
}

// رشته‌ی جلالی «۱۴۰۳/۰۶/۱۵» یا «1403/6/5» → ISO میلادی.
// endOfDay=true یعنی ۲۳:۵۹:۵۹ همان روز (برای تاریخ پایان بازه).
function jalaliInputToISO(value, endOfDay = false) {
  if (!value) return null;
  const norm = String(value)
    .replace(/[۰-۹]/g, d => '۰۱۲۳۴۵۶۷۸۹'.indexOf(d))
    .replace(/[٠-٩]/g, d => '٠١٢٣٤٥٦٧٨٩'.indexOf(d))
    .trim();
  const m = norm.match(/^(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})$/);
  if (!m) return null;
  let g;
  try { g = Jalaali.toGregorian(+m[1], +m[2], +m[3]); } catch { return null; }
  const d = new Date(g.gy, g.gm - 1, g.gd,
    endOfDay ? 23 : 0, endOfDay ? 59 : 0, endOfDay ? 59 : 0);
  return isNaN(d.getTime()) ? null : d.toISOString();
}

// ─── Loading button state ─────────────────────────────────────────
function setLoading(btn, loading, text = 'در حال پردازش...') {
  if (loading) {
    btn._originalText = btn.innerHTML;
    btn.innerHTML = `<span class="spinner"></span> ${text}`;
    btn.disabled = true;
  } else {
    btn.innerHTML = btn._originalText || 'تأیید';
    btn.disabled = false;
  }
}

// ─── Authed image loading ─────────────────────────────────────────
// /api/files/* فقط با هدر Authorization پاسخ می‌دهد — <img src="..."> این
// هدر را نمی‌فرستد، پس با fetch احراز هویت‌شده و blob URL پر می‌شود.
async function hydrateAuthedImages(container) {
  const token = Auth.getToken();
  const imgs = container.querySelectorAll('img[data-src]');
  await Promise.all(Array.from(imgs).map(async (img) => {
    const url = img.dataset.src;
    try {
      const res = await fetch(url, token ? { headers: { Authorization: `Bearer ${token}` } } : {});
      if (!res.ok) return;
      img.src = URL.createObjectURL(await res.blob());
    } catch { /* تصویر بارگذاری نمی‌شود — بی‌اهمیت */ }
  }));
}

// ─── Authed video playback ──────────────────────────────────────────
// برخلاف hydrateAuthedImages (که کل فایل را blob می‌کند — برای عکس مناسب
// است ولی برای ویدیوی حجیم یعنی پخش تا دانلود کامل فایل شروع نمی‌شود و
// seek کار نمی‌کند)، اینجا یک presigned URL کوتاه‌مدت از اپ می‌گیریم و
// مستقیم به <video> می‌دهیم — MinIO خودش Range request را هندل می‌کند.
async function resolveAuthedPlaybackUrl(internalUrl) {
  const token = Auth.getToken();
  const playbackEndpoint = internalUrl.replace('/api/files/', '/api/files/playback-url/');
  const res = await fetch(playbackEndpoint, token ? { headers: { Authorization: `Bearer ${token}` } } : {});
  if (!res.ok) throw new Error('خطا در دریافت لینک پخش');
  const data = await res.json();
  return data.url;
}

// ─── Authed file download ──────────────────────────────────────────
// /api/files/* فقط با Bearer پاسخ می‌دهد، پس یک <a href="..."> ساده کار
// نمی‌کند. قبلاً کل فایل با fetch از پشت اپ عبور داده و blob می‌شد، ولی
// برای ویدیوی حجیم این یعنی بافر کردن کل فایل در حافظه‌ی مرورگر و رد شدن
// از استریم FastAPI که در عمل به ERR_HTTP2_PROTOCOL_ERROR منجر می‌شد؛ به
// جایش مثل resolveAuthedPlaybackUrl یک presigned URL کوتاه‌مدت (این‌بار
// با response-content-disposition: attachment) می‌گیریم و مرورگر مستقیم
// از MinIO دانلود می‌کند — بدون بافر JS و بدون عبور بایت‌ها از اپ.
async function downloadAuthedFile(url, filename) {
  const token = Auth.getToken();
  try {
    const playbackEndpoint = url.replace('/api/files/', '/api/files/playback-url/') + `?download=${encodeURIComponent(filename || 'file')}`;
    const res = await fetch(playbackEndpoint, token ? { headers: { Authorization: `Bearer ${token}` } } : {});
    if (!res.ok) { toastError('خطا در دریافت فایل'); return; }
    const { url: presignedUrl } = await res.json();
    const a = document.createElement('a');
    a.href = presignedUrl;
    a.download = filename || '';
    document.body.appendChild(a);
    a.click();
    a.remove();
  } catch {
    toastError('خطا در دریافت فایل');
  }
}

// ─── HTML escaping ─────────────────────────────────────────────────
// باید هم برای متن (innerHTML) و هم برای مقدار attribute (بین "..." یا '...')
// امن باشد — به همین دلیل هر ۵ کاراکتر حساس HTML را escape می‌کند، نه فقط
// آن‌هایی که سریالایز کردن یک text node آن‌ها را نیاز دارد.
function esc(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// ─── Persian number formatting ─────────────────────────────────────
function numFa(n) {
  return Number(n ?? 0).toLocaleString('fa-IR');
}

// ─── حجم فایل با واحد فارسی ────────────────────────────────────────
function fmtFileSize(bytes) {
  if (!bytes) return '';
  const kb = bytes / 1024;
  if (kb < 1024) return `${numFa(Math.max(1, Math.round(kb)))} کیلوبایت`;
  return `${numFa((kb / 1024).toFixed(1))} مگابایت`;
}

// ─── Generic delete confirmation (آشنا با مودال #modal-confirm-delete) ──
// onConfirm باید یک تابع async باشد که خودِ عملیات حذف را انجام می‌دهد.
function confirmAction(message, onConfirm) {
  document.getElementById('confirm-msg').textContent = message;
  openModal('modal-confirm-delete');
  document.getElementById('btn-confirm-yes').onclick = async () => {
    closeModal('modal-confirm-delete');
    try {
      await onConfirm();
    } catch (e) {
      toastError(e.message);
    }
  };
}

// ─── Generic pagination renderer ───────────────────────────────────
// containerId: المان والد دکمه‌های صفحه‌بندی
// cur/total: صفحه فعلی و تعداد کل صفحات
// onPage(page): callback برای رفتن به صفحه‌ی مشخص
function renderPagination(containerId, cur, total, onPage) {
  const el = document.getElementById(containerId);
  if (!el) return;
  if (total <= 1) { el.innerHTML = ''; return; }

  const s = Math.max(1, cur - 2), e = Math.min(total, cur + 2);
  let btns = '';
  const pageBtn = (p, active) =>
    `<button class="page-btn${active ? ' active' : ''}" data-page="${p}">${numFa(p)}</button>`;

  if (s > 1) btns += pageBtn(1, false);
  if (s > 2) btns += `<span style="padding:0 4px;color:var(--gray-400)">…</span>`;
  for (let p = s; p <= e; p++) btns += pageBtn(p, p === cur);
  if (e < total - 1) btns += `<span style="padding:0 4px;color:var(--gray-400)">…</span>`;
  if (e < total) btns += pageBtn(total, false);

  el.innerHTML = `<span>صفحه ${numFa(cur)} از ${numFa(total)}</span>
    <div class="pagination-btns">
      <button class="page-btn" data-page="${cur - 1}" ${cur <= 1 ? 'disabled' : ''}>›</button>
      ${btns}
      <button class="page-btn" data-page="${cur + 1}" ${cur >= total ? 'disabled' : ''}>‹</button>
    </div>`;

  el.querySelectorAll('[data-page]').forEach(btn => {
    btn.addEventListener('click', () => {
      const p = parseInt(btn.dataset.page, 10);
      if (p >= 1 && p <= total) onPage(p);
    });
  });
}

// ─── Tabs ────────────────────────────────────────────────────────
function initTabs(tabsEl) {
  const buttons = tabsEl.querySelectorAll('.tab-btn');
  buttons.forEach(btn => {
    btn.addEventListener('click', () => {
      buttons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const target = btn.dataset.tab;
      document.querySelectorAll('.tab-content').forEach(tc => {
        tc.classList.toggle('active', tc.id === target);
      });
    });
  });
  // activate first
  if (buttons[0]) buttons[0].click();
}

// ─── Header avatar (عکس پروفایل یا حروف اول نام) ──────────────────
// el: کانتینر آواتار (span.ds-avatar یا span.emp-user-avatar) — محتوایش را
// یا با <img> عکس پروفایل (با data-src برای hydrateAuthedImages چون
// /api/files/* نیازمند Authorization است) یا با حروف اول نام پر می‌کند.
function renderAvatar(el, avatarUrl, fullName) {
  if (!el) return;
  if (avatarUrl) {
    el.innerHTML = `<img data-src="${esc(avatarUrl)}" alt="" style="width:100%;height:100%;object-fit:cover;border-radius:50%;display:block;">`;
    hydrateAuthedImages(el);
  } else {
    el.innerHTML = '';
    el.textContent = initials(fullName || '');
  }
}

// نام/آواتار نوار بالای پرتال کارمند را پر می‌کند — ابتدا از کش (بدون تاخیر)
// و سپس با GET /auth/me به‌روز می‌شود (چون avatar_url در tokenData لاگین
// ذخیره نمی‌شود) و کش را هم برای دفعات بعد به‌روز می‌کند.
async function fillHeaderUser() {
  const cached = Auth.getUser();
  if (!cached) return null;
  const nameEl = document.getElementById('empUserName');
  const avatarEl = document.getElementById('empUserAvatar');
  if (nameEl) nameEl.textContent = cached.full_name || '';
  renderAvatar(avatarEl, cached.avatar_url, cached.full_name);

  try {
    const me = await api.get('/auth/me');
    Auth.updateCachedUser({ avatar_url: me.avatar_url, full_name: me.full_name });
    if (nameEl) nameEl.textContent = me.full_name || '';
    renderAvatar(avatarEl, me.avatar_url, me.full_name);
    return me;
  } catch {
    return cached; // غیرحیاتی — اگر شکست بخورد، مقادیر کش‌شده باقی می‌ماند
  }
}

// ─── Fill user info in sidebar ────────────────────────────────────
function fillSidebarUser() {
  const user = Auth.getUser();
  if (!user) return;
  const nameEl = document.getElementById('sidebar-user-name');
  const roleEl = document.getElementById('sidebar-user-role');
  const initEl = document.getElementById('sidebar-user-init');
  if (nameEl) nameEl.textContent = user.full_name;
  if (roleEl) roleEl.textContent = roleLabel(user.role);
  if (initEl) initEl.textContent = initials(user.full_name);
}