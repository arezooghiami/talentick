// Talentick — API Client
// اگر access_token منقضی شود (401)، یک‌بار به‌صورت خودکار با refresh_token
// تمدید و درخواست اصلی دوباره تلاش می‌شود — کاربر معمولاً چیزی متوجه نمی‌شود.
// اگر تمدید هم شکست بخورد (refresh_token هم منقضی/باطل است)، به لاگین می‌رود.

const api = {
  async _fetch(method, path, body = null, _isRetry = false) {
    const token = Auth.getToken();
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const opts = { method, headers };
    if (body) opts.body = JSON.stringify(body);

    const res = await fetch(CONFIG.API_BASE + path, opts);

    if (res.status === 401 && !_isRetry) {
      const refreshed = await Auth.refreshSession();
      if (refreshed) {
        return this._fetch(method, path, body, true);
      }
      Auth.clear();
      window.location.href = '/login.html';
      throw new Error('Unauthorized');
    }
    if (res.status === 401) {
      Auth.clear();
      window.location.href = '/login.html';
      throw new Error('Unauthorized');
    }

    let data;
    try { data = await res.json(); } catch { data = null; }

    if (!res.ok) {
      const msg = data?.detail || `خطا: ${res.status}`;
      throw new Error(Array.isArray(msg) ? msg[0]?.msg || msg : msg);
    }
    return data;
  },

  get:    (path)       => api._fetch('GET', path),
  post:   (path, body) => api._fetch('POST', path, body),
  patch:  (path, body) => api._fetch('PATCH', path, body),
  delete: (path)       => api._fetch('DELETE', path),

  /** آپلود فایل (multipart/form-data) — برای تصویر/ویدیو/فایل محتوا. */
  async upload(path, file, _isRetry = false) {
    const token = Auth.getToken();
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const formData = new FormData();
    formData.append('file', file);

    const res = await fetch(CONFIG.API_BASE + path, { method: 'POST', headers, body: formData });

    if (res.status === 401 && !_isRetry) {
      const refreshed = await Auth.refreshSession();
      if (refreshed) {
        return this.upload(path, file, true);
      }
      Auth.clear();
      window.location.href = '/login.html';
      throw new Error('Unauthorized');
    }
    if (res.status === 401) {
      Auth.clear();
      window.location.href = '/login.html';
      throw new Error('Unauthorized');
    }

    let data;
    try { data = await res.json(); } catch { data = null; }

    if (!res.ok) {
      const msg = data?.detail || `خطا: ${res.status}`;
      throw new Error(Array.isArray(msg) ? msg[0]?.msg || msg : msg);
    }
    return data;
  },

  /** دانلود فایل باینری (Excel و ...) با هدر احراز هویت — دانلود مستقیم در مرورگر. */
  async download(path, filename, _isRetry = false) {
    const token = Auth.getToken();
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const res = await fetch(CONFIG.API_BASE + path, { headers });

    if (res.status === 401 && !_isRetry) {
      const refreshed = await Auth.refreshSession();
      if (refreshed) return this.download(path, filename, true);
      Auth.clear();
      window.location.href = '/login.html';
      throw new Error('Unauthorized');
    }
    if (res.status === 401) {
      Auth.clear();
      window.location.href = '/login.html';
      throw new Error('Unauthorized');
    }
    if (!res.ok) {
      let msg = `خطا: ${res.status}`;
      try { const data = await res.json(); msg = data?.detail || msg; } catch { /* body غیر JSON */ }
      throw new Error(Array.isArray(msg) ? msg[0]?.msg || msg : msg);
    }

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },
};
