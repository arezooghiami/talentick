// Talentick — Auth Helpers
// از access_token (کوتاه‌مدت) + refresh_token (بلندمدت) پشتیبانی می‌کند تا
// کاربر هر ۶۰ دقیقه مجبور به لاگین دوباره نشود (تمدید خودکار در api.js).

const Auth = {
  getToken() {
    return localStorage.getItem(CONFIG.TOKEN_KEY);
  },

  getRefreshToken() {
    return localStorage.getItem(CONFIG.REFRESH_TOKEN_KEY);
  },

  getUser() {
    const raw = localStorage.getItem(CONFIG.USER_KEY);
    try { return raw ? JSON.parse(raw) : null; } catch { return null; }
  },

  setSession(tokenData) {
    localStorage.setItem(CONFIG.TOKEN_KEY, tokenData.access_token);
    if (tokenData.refresh_token) {
      localStorage.setItem(CONFIG.REFRESH_TOKEN_KEY, tokenData.refresh_token);
    }
    localStorage.setItem(CONFIG.USER_KEY, JSON.stringify({
      id: tokenData.user_id,
      org_id: tokenData.org_id,
      role: tokenData.role,
      full_name: tokenData.full_name,
    }));
  },

  clear() {
    localStorage.removeItem(CONFIG.TOKEN_KEY);
    localStorage.removeItem(CONFIG.REFRESH_TOKEN_KEY);
    localStorage.removeItem(CONFIG.USER_KEY);
  },

  isLoggedIn() {
    return !!this.getToken();
  },

  // Guard: redirect to login if not authenticated
  requireAuth(allowedRoles = []) {
    if (!this.isLoggedIn()) {
      window.location.href = '/login.html';
      return false;
    }
    if (allowedRoles.length > 0) {
      const user = this.getUser();
      if (!user || !allowedRoles.includes(user.role)) {
        this.redirectByRole();
        return false;
      }
    }
    return true;
  },

  redirectByRole() {
    const user = this.getUser();
    if (!user) { window.location.href = '/login.html'; return; }
    if (user.role === 'super_admin') {
      window.location.href = '/admin/index.html';
    } else if (user.role === 'org_admin' || user.role === 'manager') {
      window.location.href = '/admin/index.html';
    } else {
      window.location.href = '/home/index.html';
    }
  },

  // یک Promise مشترک برای جلوگیری از چند درخواست هم‌زمان /refresh
  // (مثلاً وقتی چند فراخوانی API به‌طور موازی همزمان 401 می‌گیرند).
  _refreshPromise: null,

  /**
   * تلاش برای گرفتن access_token جدید با refresh_token ذخیره‌شده.
   * @returns {Promise<boolean>} true اگر موفق بود.
   */
  async refreshSession() {
    const refreshToken = this.getRefreshToken();
    if (!refreshToken) return false;

    if (!this._refreshPromise) {
      this._refreshPromise = fetch(CONFIG.API_BASE + '/auth/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      })
        .then(async (res) => {
          if (!res.ok) return false;
          const data = await res.json();
          this.setSession(data);
          return true;
        })
        .catch(() => false)
        .finally(() => { this._refreshPromise = null; });
    }
    return this._refreshPromise;
  },

  async logout() {
    const refreshToken = this.getRefreshToken();
    const token = this.getToken();
    // best-effort: session را در سرور هم باطل کن — اگر شکست خورد مهم نیست،
    // چون localStorage در هر صورت پاک می‌شود.
    if (token) {
      try {
        await fetch(CONFIG.API_BASE + '/auth/logout', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ refresh_token: refreshToken || null }),
        });
      } catch {
        // نادیده گرفته می‌شود — logout سمت کلاینت در هر صورت انجام می‌شود
      }
    }
    this.clear();
    window.location.href = '/login.html';
  },
};
