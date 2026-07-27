// ════════════════════════════════════════════════════════════════════
// Talentick — Shell مشترک صفحات پرتال کارمند (سایدبار + نوار بالا + auth guard)
// ════════════════════════════════════════════════════════════════════
// هر صفحه‌ی کارمند (خانه، محتوا، سازمان، تیکت‌ها، امتیازات، آزمون) این
// فایل را بعد از config.js/auth.js/api.js/utils.js لود می‌کند و
// EmployeeShell.init() را صدا می‌زند.

const EmployeeShell = {
  init(activePage) {
    Auth.requireAuth();
    this._fillUser();
    this._highlightNav(activePage);
    this._wireDropdown();
    this._wireSidebarToggle();
    this._loadSidebarPoints();
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
    document.querySelectorAll('[data-nav]').forEach(el => {
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

  // سایدبار در موبایل/تبلت به‌صورت Drawer باز/بسته می‌شود (دکمه‌ی ☰ در نوار بالا).
  _wireSidebarToggle() {
    const toggle = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('empSidebar');
    const backdrop = document.getElementById('empSidebarBackdrop');
    if (!toggle || !sidebar) return;
    const close = () => {
      sidebar.classList.remove('open');
      if (backdrop) backdrop.classList.remove('open');
    };
    toggle.addEventListener('click', (e) => {
      e.stopPropagation();
      sidebar.classList.toggle('open');
      if (backdrop) backdrop.classList.toggle('open');
    });
    if (backdrop) backdrop.addEventListener('click', close);
    sidebar.querySelectorAll('a').forEach(a => a.addEventListener('click', close));
  },

  // کارت امتیاز پایین سایدبار — در همه‌ی صفحات پرتال کارمند نمایش داده می‌شود.
  async _loadSidebarPoints() {
    const el = document.getElementById('sidebarPointsValue');
    if (!el) return;
    try {
      const res = await api.get('/me/points/summary');
      el.textContent = numFa(res.total_points);
    } catch {
      el.textContent = '—';
    }
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
