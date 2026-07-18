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