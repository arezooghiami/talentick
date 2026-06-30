// ════════════════════════════════════════════════════════════════════
// Talentick — Dashboard Router
// ════════════════════════════════════════════════════════════════════
// مسئول: نمایش/پنهان‌سازی منو بر اساس نقش + سوییچ بین .view ها +
// فراخوانی تابع load هر صفحه. هیچ منطق تجاری (CRUD) اینجا نیست —
// هر صفحه منطق خودش را در assets/js/pages/*.js دارد و از طریق
// Router.register ثبت می‌شود.

const Router = {
  _pages: {},
  _currentPage: null,

  /**
   * ثبت یک صفحه.
   * @param {string} name - شناسه‌ی صفحه (با data-page روی nav-item و id="view-<name>" یکی باشد)
   * @param {object} meta
   * @param {string} meta.title - عنوان نمایش‌داده‌شده در هدر
   * @param {function} [meta.load] - تابعی که هر بار ورود به صفحه صدا زده می‌شود
   */
  register(name, meta) {
    this._pages[name] = meta;
  },

  /**
   * منوی سایدبار و هر المان دیگری با data-roles را بر اساس نقش
   * کاربر فعلی نمایش/پنهان می‌کند. مقدار data-roles مثل
   * "super_admin,org_admin" است (کاما-جدا).
   */
  applyRoleVisibility(role) {
    document.querySelectorAll('[data-roles]').forEach(el => {
      const allowed = el.dataset.roles.split(',').map(s => s.trim());
      el.classList.toggle('hidden', !allowed.includes(role));
    });
  },

  navigate(name) {
    const meta = this._pages[name];
    if (!meta) return;
    this._currentPage = name;

    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    const view = document.getElementById('view-' + name);
    if (view) view.classList.add('active');

    document.querySelectorAll('.sidebar-nav [data-page]').forEach(el =>
      el.classList.toggle('active', el.dataset.page === name));

    const titleEl = document.getElementById('headerTitle');
    if (titleEl) titleEl.textContent = meta.title;

    if (meta.load) meta.load();
  },

  current() {
    return this._currentPage;
  },

  /** برای سایدبار-آیتم‌هایی با ساب‌منو (محتوا، گزارش) */
  toggleSubmenu(id, el) {
    const submenu = document.getElementById(id);
    const isOpen = submenu.classList.contains('open');
    document.querySelectorAll('.nav-submenu').forEach(e => e.classList.remove('open'));
    document.querySelectorAll('.nav-item').forEach(e => e.classList.remove('open'));
    if (!isOpen) {
      submenu.classList.add('open');
      el.classList.add('open');
    }
  },
};