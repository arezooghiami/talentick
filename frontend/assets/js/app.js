// ════════════════════════════════════════════════════════════════════
// Talentick — App Bootstrap (شِل مشترک super_admin / org_admin / manager)
// ════════════════════════════════════════════════════════════════════
// مسئول: نگه‌داری وضعیت کاربر فعلی + پرچم‌های نقش که همه‌ی page-module
// ها (dashboard.js, users.js, orgs.js, ...) به آن‌ها رجوع می‌کنند.
// هیچ منطق UI/CRUD اینجا نیست.

const App = {
  currentUser: null,
  isSuperAdmin: false,
  isOrgAdmin: false,
  isManager: false,

  /** باید قبل از هر چیز دیگری صدا زده شود (بعد از Auth.requireAuth). */
  init() {
    this.currentUser = Auth.getUser();
    this.isSuperAdmin = this.currentUser?.role === 'super_admin';
    this.isOrgAdmin   = this.currentUser?.role === 'org_admin';
    this.isManager    = this.currentUser?.role === 'manager';

    // سازمانی که ساختار/کاربرانش پیش‌فرض نمایش داده می‌شود:
    // super_admin از طریق صفحه‌ی «شرکت‌ها» سازمان را انتخاب می‌کند،
    // org_admin/manager همیشه روی سازمان خودشان قفل هستند.
    this.homeOrgId = this.currentUser?.org_id || null;

    Router.applyRoleVisibility(this.currentUser.role);
    this._fillSidebar();
    this._fillPanelLabel();
  },

  _fillSidebar() {
    fillSidebarUser(); // از utils.js — sidebar-user-name / role / init
  },

  _fillPanelLabel() {
    const el = document.getElementById('sidebarPanelLabel');
    if (!el) return;
    const labels = {
      super_admin: 'پنل مدیریت پلتفرم',
      org_admin:   'پنل مدیر سازمان',
      manager:     'پنل مدیر منابع انسانی',
    };
    el.textContent = labels[this.currentUser.role] || 'پنل مدیریت';
  },

  logout() {
    Auth.logout();
  },
};
