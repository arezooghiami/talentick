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
    super_admin: 'badge-purple',
    org_admin:   'badge-blue',
    manager:     'badge-orange',
    employee:    'badge-green',
  }[role] || 'badge-gray';
  return `<span class="badge ${cls}">${roleLabel(role)}</span>`;
}

// ─── Status badge ─────────────────────────────────────────────────
function statusBadge(isActive) {
  return isActive
    ? '<span class="badge badge-green">فعال</span>'
    : '<span class="badge badge-red">غیرفعال</span>';
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
