// ════════════════════════════════════════════════════════════════════
// Talentick — Shell مشترک صفحات پرتال کارمند (navbar + auth guard)
// ════════════════════════════════════════════════════════════════════
// هر صفحه‌ی کارمند (onboarding/index.html، content/list.html،
// content/detail.html، quiz/index.html) این فایل را بعد از
// config.js/auth.js/api.js/utils.js لود می‌کند و EmployeeShell.init()
// را صدا می‌زند.

const EmployeeShell = {
  init(activePage) {
    Auth.requireAuth();
    this._fillUser();
    this._highlightNav(activePage);
    this._wireDropdown();
    this._checkMustChangePassword();
  },

  _fillUser() {
    const user = Auth.getUser();
    if (!user) return;
    const nameEl = document.getElementById('empUserName');
    const avatarEl = document.getElementById('empUserAvatar');
    if (nameEl) nameEl.textContent = user.full_name || '';
    if (avatarEl) avatarEl.textContent = (user.full_name || '').split(' ').slice(0, 2).map(w => w[0]).join('');
  },

  _highlightNav(activePage) {
    document.querySelectorAll('.emp-nav-links [data-nav]').forEach(el => {
      el.classList.toggle('active', el.dataset.nav === activePage);
    });
  },

  _wireDropdown() {
    const btn = document.getElementById('empUserBtn');
    const dropdown = document.getElementById('empUserDropdown');
    if (!btn || !dropdown) return;
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      dropdown.classList.toggle('open');
    });
    document.addEventListener('click', () => dropdown.classList.remove('open'));
  },

  // اگر با وجود گذر از Auth.requireAuth کاربر همچنان وضعیتش قدیمی مانده
  // (نادر) دوباره چک می‌کند — دفاع در عمق، منبع اصلی enforcement بک‌اند است.
  _checkMustChangePassword() {
    const user = Auth.getUser();
    if (user?.must_change_password) {
      window.location.href = '/change-password.html';
    }
  },

  logout() {
    Auth.logout();
  },
};
