// Talentick — Auth Helpers

const Auth = {
  getToken() {
    return localStorage.getItem(CONFIG.TOKEN_KEY);
  },

  getUser() {
    const raw = localStorage.getItem(CONFIG.USER_KEY);
    try { return raw ? JSON.parse(raw) : null; } catch { return null; }
  },

  setSession(tokenData) {
    localStorage.setItem(CONFIG.TOKEN_KEY, tokenData.access_token);
    localStorage.setItem(CONFIG.USER_KEY, JSON.stringify({
      id: tokenData.user_id,
      org_id: tokenData.org_id,
      role: tokenData.role,
      full_name: tokenData.full_name,
    }));
  },

  clear() {
    localStorage.removeItem(CONFIG.TOKEN_KEY);
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
      window.location.href = '/onboarding/index.html';
    }
  },

  logout() {
    this.clear();
    window.location.href = '/login.html';
  },
};
